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
from app.costing.bom import build_bom
from app.costing.budget import BudgetViolation, check_budget
from app.costing.drivers import (
    IncompleteMassError,
    drivers_for_assembly,
    drivers_from_validation,
)
from app.costing.report import render_bom
from app.db.database import get_default_db
from app.db.models import DesignRow, ValidationReportRow
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


def _material_of(params: dict, report) -> str:
    """The one material this BOM is priced in.

    An assembly may carry several. Costing keys on a single material_id
    (build_bom), so a mixed-material design is REFUSED by name rather than
    quoted at whichever material happened to reach the report first — a
    bronze sculpture priced as basalt is a wrong number that looks right.
    Per-element costing is the costing tie-off (NEXT.md W-7).
    """
    manifest = params.get("manifest") or {}
    elements = manifest.get("elements") or []
    if elements:
        by_material: dict[str, list[str]] = {}
        for element in elements:
            by_material.setdefault(
                str(element.get("material_id")), []
            ).append(str(element.get("element_id")))
        if len(by_material) > 1:
            detail = "; ".join(
                f"{mid}: {', '.join(sorted(eids))}"
                for mid, eids in sorted(by_material.items())
            )
            raise HTTPException(409, {
                "error": "mixed_material_assembly",
                "message": (
                    f"design {params.get('schema', 'assembly')} uses "
                    f"{len(by_material)} materials and the BOM prices one. "
                    f"Refusing rather than quoting every element at one "
                    f"material's rate ({detail}). Per-element costing is the "
                    f"costing tie-off, NEXT.md W-7"),
                "materials": sorted(by_material),
                "elements_by_material": {k: sorted(v)
                                         for k, v in by_material.items()},
            })
        return next(iter(by_material))
    return getattr(report, "material_id", "") or params.get("material_id", "")


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
    material_id = _material_of(params, report)
    material = bundle.materials.materials.get(material_id)
    if material is None:
        raise HTTPException(
            409, f"design material {material_id!r} is not in materials.yaml")
    try:
        drivers = (
            drivers_for_assembly(report, params.get("manifest"))
            if isinstance(report, AssemblyValidationReport)
            else drivers_from_validation(report)
        )
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
    bom = build_bom(bundle.costing, drivers,
                    material_id, material, design_id=design_id,
                    spec_hash=spec_hash,
                    now_iso=created_at if reproducible else None)
    return bundle, bom, params


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
    bundle, bom, _ = _bom_for(design_id)
    check = None
    if budget_amount is not None:
        try:
            check = check_budget(
                bom, {"amount": budget_amount, "currency": budget_currency,
                      "fx_date": budget_fx_date}, bundle.costing)
        except BudgetViolation as exc:
            return Response(
                render_bom(bom) + "\n" + "=" * 78
                + f"\nBUDGET CONSTRAINT: FAIL\n{'=' * 78}\n  {exc.message}\n",
                media_type="text/plain", status_code=422)
    return Response(render_bom(bom, check), media_type="text/plain")


@router.get("/bom/{design_id}")
def bom_json(design_id: str, budget_amount: float | None = None,
             budget_currency: str = "ETB",
             budget_fx_date: str | None = None) -> dict:
    bundle, bom, _ = _bom_for(design_id)
    payload = bom.as_dict()
    if budget_amount is not None:
        budget = {"amount": budget_amount, "currency": budget_currency,
                  "fx_date": budget_fx_date}
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
            }) from exc
    return payload
