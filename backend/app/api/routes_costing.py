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
from app.costing.drivers import drivers_from_validation
from app.costing.report import render_bom
from app.db.database import get_default_db
from app.db.models import DesignRow, ValidationReportRow
from app.geometry.validate import ValidationReport

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


def _load(design_id: str):
    db = get_default_db()
    with db.get_session() as s:
        design = s.get(DesignRow, design_id)
        if design is None:
            raise HTTPException(404, f"design {design_id} not found")
        row = (s.query(ValidationReportRow)
               .filter_by(design_id=design_id)
               .order_by(ValidationReportRow.created_at.desc())
               .first())
        if row is None:
            raise HTTPException(
                409,
                f"design {design_id} has no validation report — costs derive "
                "from validation numbers, so there is nothing to cost yet")
        report = ValidationReport(**json.loads(row.numbers_json))
        params = json.loads(design.parameter_json)
        return design.spec_hash or "", params, report


def _bom_for(design_id: str):
    bundle = load_config_bundle()
    spec_hash, params, report = _load(design_id)
    material_id = report.material_id or params.get("material_id", "")
    material = bundle.materials.materials.get(material_id)
    if material is None:
        raise HTTPException(
            409, f"design material {material_id!r} is not in materials.yaml")
    bom = build_bom(bundle.costing, drivers_from_validation(report),
                    material_id, material, design_id=design_id,
                    spec_hash=spec_hash)
    return bundle, bom, params


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
