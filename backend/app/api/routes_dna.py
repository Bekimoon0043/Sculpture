"""DesignDNA API — Phase 11 (L8).

  POST   /api/dna/accept           accept the deliverable as a precedent
  GET    /api/dna                  list (active; ?include_archived=true)
  GET    /api/dna/search           explainable retrieval with match reasons
  GET    /api/dna/{id}             one precedent (?full=true for the record)
  POST   /api/dna/{id}/archive     hide from retrieval, keep the record
  DELETE /api/dna/{id}             wipe payload, keep a tombstone
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.database import get_default_db
from app.dna import (
    AcceptError,
    accept_design,
    archive_precedent,
    delete_precedent,
    get_precedent,
    list_precedents,
    search_precedents,
)

log = logging.getLogger("luxuryform.api.dna")

router = APIRouter(prefix="/dna", tags=["designdna"])


class AcceptRequest(BaseModel):
    design_id: str
    accepted_by: str
    acceptance_note: str
    brief_summary: str | None = None


@router.post("/accept", status_code=201)
def post_accept(req: AcceptRequest) -> dict[str, Any]:
    """Accept a design's DELIVERABLE as precedent.

    Pulls the export package digest, validation rollup and BOM through the
    same code paths the export and validation APIs use — the precedent
    records exactly what those surfaces reported, not a retelling.
    """
    from app.api.routes_assembly import (
        _costing_for,
        _design_or_404,
        _export_rows,
        _validation_statuses,
    )
    from app.geometry.gates import worst_status

    design = _design_or_404(req.design_id)
    statuses = _validation_statuses(design.id)
    overall = worst_status(statuses.values()) if statuses else "needs_input"

    package = next(
        (r for r in _export_rows(design.id) if r["format"] == "LUXEXCHANGE"
         and r["status"] == "included"),
        None,
    )
    # The digest identifies the package; the LUXEXCHANGE row's sha256 is the
    # zip hash. content_digest lives in the job state — read via exports
    # status. Simplest reliable source: the sealed package's stored sha256
    # doubles as identity ONLY if reproducible, which ADR-035/037 guarantee —
    # but the declared identity key is content_digest (plan R1), so fetch it.
    from app.api.routes_assembly import _exports_status

    status = _exports_status(design)
    digest = status.get("content_digest") or (package or {}).get("sha256")

    costing, costing_reason = _costing_for(design.id)

    db = get_default_db()
    try:
        with db.get_session() as session:
            row = accept_design(
                session,
                design_id=design.id,
                accepted_by=req.accepted_by,
                acceptance_note=req.acceptance_note,
                content_digest=digest or "",
                validation_statuses=statuses,
                overall_status=overall,
                costing=costing,
                costing_unavailable_reason=costing_reason,
                brief_summary=req.brief_summary,
            )
            session.flush()
            precedent_id = row.id
    except AcceptError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    with db.get_session() as session:
        return get_precedent(session, precedent_id) or {}


@router.get("")
def get_list(include_archived: bool = False) -> dict[str, Any]:
    db = get_default_db()
    with db.get_session() as session:
        rows = list_precedents(session, include_archived=include_archived)
    return {"precedents": rows, "count": len(rows)}


@router.get("/search")
def get_search(
    material: str | None = None,
    primitive: str | None = None,
    has_water: bool | None = None,
    gate_profile_id: str | None = None,
    height_m: float | None = None,
    text: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    db = get_default_db()
    with db.get_session() as session:
        rows = search_precedents(
            session, material=material, primitive=primitive,
            has_water=has_water, gate_profile_id=gate_profile_id,
            height_m=height_m, text=text, limit=limit,
        )
    return {
        "precedents": rows,
        "count": len(rows),
        "criteria": {
            k: v for k, v in {
                "material": material, "primitive": primitive,
                "has_water": has_water, "gate_profile_id": gate_profile_id,
                "height_m": height_m, "text": text,
            }.items() if v is not None
        },
    }


@router.get("/{precedent_id}")
def get_one(precedent_id: str, full: bool = False) -> dict[str, Any]:
    db = get_default_db()
    with db.get_session() as session:
        row = get_precedent(session, precedent_id, full=full)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no precedent {precedent_id}")
    return row


@router.post("/{precedent_id}/archive")
def post_archive(precedent_id: str) -> dict[str, Any]:
    db = get_default_db()
    with db.get_session() as session:
        row = archive_precedent(session, precedent_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"no living precedent {precedent_id} (deleted ones cannot "
                   f"be archived)",
        )
    return row


@router.delete("/{precedent_id}")
def delete_one(precedent_id: str) -> dict[str, Any]:
    db = get_default_db()
    with db.get_session() as session:
        row = delete_precedent(session, precedent_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no precedent {precedent_id}")
    return row
