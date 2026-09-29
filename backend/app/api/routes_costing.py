"""Costing API — the BOM for a persisted design, and the rate-card state.

Endpoints refuse rather than approximate, exactly as the layer beneath them
does: an unfilled rate card produces an INCOMPLETE BOM with named gaps and
HTTP 200 (the report is a legitimate answer), while an over-budget design
produces HTTP 422 carrying the real numbers — the same shape the geometry
routes already use for a ConstraintViolation.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Response

from app.core.config import load_config_bundle
from app.costing.bom import build_assembly_bom, build_bom
from app.costing.budget import (
    BUDGET_SOURCE_QUERY,
    BudgetViolation,
    budget_from_intake,
    check_budget,
)
from app.costing.drivers import (
    IncompleteMassError,
    drivers_for_assembly,
    drivers_from_validation,
    drivers_per_element,
)
from app.costing.report import render_bom
from app.db.database import get_default_db
from app.db.models import DesignRow, IntakeRow, ValidationReportRow
from app.geometry.validate import AssemblyValidationReport, ValidationReport

# main.py mounts every router under /api, so the prefix here must NOT repeat it.
router = APIRouter(prefix="/costing", tags=["costing"])


@router.get("/rate-card")
def rate_card() -> dict:
    """What is filled in and what is not — the operator's to-do list."""
    bundle = load_config_bundle()
    missing = bundle.costing.missing_entries()
    return {
        "costing_version": bundle.costing.costing_version,
        "filled": not missing,
        "missing_count": len(missing),
        "missing_entries": missing,
        "note": ("Every path listed here is null in config/costing.yaml. "
                 "No cost is computed from a null rate and none is guessed."),
    }


#: gate_name -> the report class stored under it. THREE shapes share the
#: validation_reports table and only these two are mesh reports; the Phase 8
#: layered gates (structure/hydraulics/fabrication) write a third. Reading
#: every row as a ValidationReport is what made this endpoint return HTTP
#: 500 for every assembly ever built — an assembly stores an
#: AssemblyValidationReport, which deliberately has no material_id and no
#: single mass_kg. Found and fixed 2026-08-27 (ADR-056).
_MESH_REPORTS = {
    "assembly_mesh": AssemblyValidationReport,
    "mesh": ValidationReport,
}


def _load(design_id: str):
    db = get_default_db()
    with db.get_session() as s:
        design = s.get(DesignRow, design_id)
        if design is None:
            raise HTTPException(404, f"design {design_id} not found")
        row = (s.query(ValidationReportRow)
               .filter_by(design_id=design_id)
               .filter(ValidationReportRow.gate_name.in_(tuple(_MESH_REPORTS)))
               .order_by(ValidationReportRow.created_at.desc())
               .first())
        if row is None:
            present = sorted({
                r.gate_name for r in s.query(ValidationReportRow)
                .filter_by(design_id=design_id).all()
            })
            raise HTTPException(
                409,
                f"design {design_id} has no mesh validation report — costs "
                "derive from validation numbers, so there is nothing to cost "
                f"yet (gates on record: {', '.join(present) or 'none'})")
        report = _MESH_REPORTS[row.gate_name](**json.loads(row.numbers_json))
        params = json.loads(design.parameter_json)
        return design.spec_hash or "", params, report, design.created_at


def _materials_of(params: dict, report) -> list[str]:
    """Every material this design is made of, sorted.

    One entry -> the single-material BOM (build_bom, bytes unchanged since
    ADR-056). Several -> the per-element BOM (PR-6, ADR-074), which replaced
    the HTTP 409 "mixed_material_assembly" refusal: a bronze figure on a
    basalt basin is now priced element by element, each in its own
    material, with every joint billed once to its owner.
    """
    manifest = params.get("manifest") or {}
    elements = manifest.get("elements") or []
    if elements:
        return sorted({str(e.get("material_id")) for e in elements})
    single = getattr(report, "material_id", "") or params.get("material_id", "")
    return [single] if single else []


def _bom_for(design_id: str, *, reproducible: bool = False):
    """The BOM for a persisted design.

    ``reproducible`` stamps the report with the DESIGN's creation time
    instead of the wall clock. The LUXEXCHANGE package seals the BOM, and
    a package must hash the same on every export (ADR-035/037) — a
    ``generated_at`` of "now" silently breaks that. The hole was invisible
    until slice C2, because costing raised for every assembly and the
    package simply omitted the BOM (ADR-056).
    """
    bundle = load_config_bundle()
    spec_hash, params, report, created_at = _load(design_id)
    material_ids = _materials_of(params, report)
    for mid in material_ids:
        if mid not in bundle.materials.materials:
            raise HTTPException(
                409, f"design material {mid!r} is not in materials.yaml")
    manifest = params.get("manifest")
    now_iso = created_at if reproducible else None
    try:
        if isinstance(report, AssemblyValidationReport):
            drivers = drivers_for_assembly(report, manifest)
        else:
            drivers = drivers_from_validation(report)
        if len(material_ids) > 1:
            # PR-6 (ADR-074): per-element, each in its own material; joints
            # once to their owner; install once at assembly level.
            elements, joints = drivers_per_element(report, manifest)
            bom = build_assembly_bom(
                bundle.costing, drivers, elements, joints,
                bundle.materials.materials, design_id=design_id,
                spec_hash=spec_hash, now_iso=now_iso)
        else:
            material_id = material_ids[0] if material_ids else ""
            material = bundle.materials.materials.get(material_id)
            if material is None:
                raise HTTPException(
                    409, f"design material {material_id!r} is not in "
                         f"materials.yaml")
            bom = build_bom(bundle.costing, drivers,
                            material_id, material, design_id=design_id,
                            spec_hash=spec_hash, now_iso=now_iso)
    except IncompleteMassError as exc:
        # FF-A1 (ADR-065): an incomplete mass can never price anything —
        # material, transport and crane lines all derive from it. The BOM
        # and every quote are not_computable until the named inputs exist.
        raise HTTPException(409, {
            "error": "incomplete_mass",
            "message": ("costing is not computable: the design's mass is "
                        "INCOMPLETE and a known-geometry mass must never be "
                        "priced as a total (ADR-065)"),
            "known_geometry_mass_kg": exc.known_geometry_mass_kg,
            "missing_mass_inputs": list(exc.missing_mass_inputs),
        }) from exc
    return bundle, bom, params


def _budget_for(params: dict, budget_amount: float | None,
                budget_currency: str, budget_fx_date: str | None
                ) -> dict | None:
    """Which ceiling binds this BOM (PR-6, ADR-074).

    Precedence, stated: an EXPLICIT request parameter wins; otherwise the
    design's CONFIRMED intake supplies ``budget.amount_max``; otherwise
    none and no BUDGET row is produced. Both channels are printed as the
    row's source so the operator knows which number bound.
    """
    if budget_amount is not None:
        return {"amount": budget_amount, "currency": budget_currency,
                "fx_date": budget_fx_date, "source": BUDGET_SOURCE_QUERY,
                # Use normal decimal text, not :g: a large ceiling such as
                # 9,999,999 otherwise becomes 1e+07 and the audit trail no
                # longer preserves the value the operator typed.
                "source_detail": (f"?budget_amount={budget_amount}"
                                  f"&budget_currency={budget_currency}")}
    # Assembly designs persist the original request under `request`; the
    # direct top-level form is retained for older/single-primitive records.
    intake_id = (params.get("intake_id")
                 or (params.get("request") or {}).get("intake_id"))
    if not intake_id:
        return None
    db = get_default_db()
    with db.get_session() as s:
        row = s.get(IntakeRow, intake_id)
        if row is None:
            return None
        return budget_from_intake(json.loads(row.normalized_json),
                                  row.status, intake_id)


# ROUTE ORDER IS LOAD-BEARING (found 2026-08-27, ADR-056). FastAPI matches
# in registration order and `{design_id}` matches "<uuid>.txt" quite
# happily, so while the JSON route was declared first every request for
# the rendered document came back 404 "design <uuid>.txt not found". The
# more specific path must be registered first. Do not reorder these.
@router.get("/bom/{design_id}.txt")
def bom_text(design_id: str, budget_amount: float | None = None,
             budget_currency: str = "ETB",
             budget_fx_date: str | None = None) -> Response:
    """The rendered document — the thing handed to a client."""
    bundle, bom, params = _bom_for(design_id)
    check = None
    budget = _budget_for(params, budget_amount, budget_currency,
                         budget_fx_date)
    if budget is not None:
        try:
            check = check_budget(bom, budget, bundle.costing)
        except BudgetViolation as exc:
            source = (f"  ceiling from: {budget.get('source')} — "
                      f"{budget.get('source_detail')}\n")
            return Response(
                render_bom(bom) + "\n" + "=" * 78
                + f"\nBUDGET CONSTRAINT: FAIL\n{'=' * 78}\n"
                + source + f"  {exc.message}\n",
                media_type="text/plain", status_code=422)
    return Response(render_bom(bom, check), media_type="text/plain")


@router.get("/bom/{design_id}")
def bom_json(design_id: str, budget_amount: float | None = None,
             budget_currency: str = "ETB",
             budget_fx_date: str | None = None) -> dict:
    bundle, bom, params = _bom_for(design_id)
    payload = bom.as_dict()
    budget = _budget_for(params, budget_amount, budget_currency,
                         budget_fx_date)
    if budget is not None:
        try:
            payload["budget"] = check_budget(bom, budget,
                                             bundle.costing).as_dict()
        except BudgetViolation as exc:
            # Binding, not advisory: an over-budget design is REFUSED, with
            # the real numbers, exactly like a geometry hard constraint.
            raise HTTPException(422, {
                "error": "budget_exceeded", "message": exc.message,
                "total_usd": exc.total_usd, "ceiling_usd": exc.ceiling_usd,
                "over_usd": exc.over_usd, "over_pct": exc.over_pct,
                "source": budget.get("source"),
                "source_detail": budget.get("source_detail"),
            }) from exc
    return payload
