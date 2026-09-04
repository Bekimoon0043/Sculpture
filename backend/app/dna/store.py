"""DesignDNA precedent store — Phase 11 (L8).

Every accepted design becomes a searchable precedent: what it was, how it
validated, what it cost, and one number that identifies it. Four design
rules, from the reviewed plan:

IDENTITY IS THE PACKAGE DIGEST (R1). A precedent keys on the LUXEXCHANGE
`content_digest`, which covers geometry + spec + validation + BOM together.
Two designs with identical STEP but different materials or validation
profiles are different precedents, and the digest separates them where a
geometry hash would not. Consequence: **a design must have an export package
before it can be accepted** — the deliverable defines the precedent, and
this enforces the pipeline order (build → validate → export → accept)
instead of letting half-finished work into memory.

ACCEPTANCE IS AN EVENT WITH AN AUTHOR (R3). `accepted_by` and
`acceptance_note` are required. A precedent that cannot say who accepted it
and why is not auditable, and it will be injected into paid Council prompts
for years (Rule 12).

RETRIEVAL IS EXPLAINABLE BEFORE IT IS CLEVER (R4). Deterministic structured
matching over tags, returning a per-field match reason. No embeddings: an
operator with no coding background must be able to see WHY a precedent
surfaced, and an unexplainable similarity score cannot be debugged when it
retrieves the wrong thing.

ARCHIVE AND DELETE ARE DIFFERENT (R6). Archive hides from retrieval and
keeps the record, so old sessions that cite it stay coherent. Delete wipes
the payload but leaves a tombstone with the id, so a session that cited it
reports "precedent deleted" rather than a dangling reference.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import DesignDnaRow, DesignRow, ValidationReportRow

log = logging.getLogger("luxuryform.dna")

#: Precedents injected into one Council prompt, at most. More would drown
#: the brief and cost real money per session.
MAX_INJECTED_PRECEDENTS = 3


class AcceptError(RuntimeError):
    """Raised when a design cannot become a precedent, with the reason."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Tags — the queryable surface of a precedent
# ---------------------------------------------------------------------------

def derive_tags(
    stored: dict[str, Any],
    validation_statuses: dict[str, str],
    overall_status: str,
    costing: dict[str, Any] | None,
) -> dict[str, Any]:
    """Extract the retrieval keys from a persisted assembly design record.

    Everything here is measured or declared — nothing is inferred by a
    model. That is what makes a match reason like "material basalt_slab"
    trustworthy enough to show the operator.
    """
    manifest = stored.get("manifest") or {}
    request = stored.get("request") or {}
    elements = list(manifest.get("elements") or [])

    bb_min = manifest.get("assembly_bbox_min_mm") or [0, 0, 0]
    bb_max = manifest.get("assembly_bbox_max_mm") or [0, 0, 0]
    height_m = (float(bb_max[2]) - float(bb_min[2])) / 1000.0
    footprint_m = max(
        float(bb_max[0]) - float(bb_min[0]),
        float(bb_max[1]) - float(bb_min[1]),
    ) / 1000.0

    water = request.get("water") or {}
    return {
        "materials": sorted({str(e.get("material_id")) for e in elements}),
        "primitives": sorted({str(e.get("primitive")) for e in elements}),
        "element_count": len(elements),
        "height_m": round(height_m, 3),
        "footprint_m": round(footprint_m, 3),
        # FF-A1 (ADR-065): None — never zero, never a partial sum — when
        # the manifest's mass truth is incomplete; the flag says which.
        "total_mass_kg": (
            round(float(manifest["total_mass_kg"]), 1)
            if manifest.get("total_mass_kg") is not None else None),
        "mass_complete": manifest.get("total_mass_kg") is not None,
        "has_water": bool(water.get("has_water")),
        "gate_profile_id": request.get("gate_profile_id"),
        "overall_status": overall_status,
        "gate_statuses": validation_statuses,
        "total_cost_usd": (
            round(float(costing.get("total_usd")), 2)
            if costing and isinstance(costing.get("total_usd"), (int, float))
            else None
        ),
        "seed": request.get("seed"),
    }


# ---------------------------------------------------------------------------
# Accept
# ---------------------------------------------------------------------------

def accept_design(
    session,
    *,
    design_id: str,
    accepted_by: str,
    acceptance_note: str,
    content_digest: str,
    validation_statuses: dict[str, str],
    overall_status: str,
    costing: dict[str, Any] | None,
    costing_unavailable_reason: str | None = None,
    brief_summary: str | None = None,
) -> DesignDnaRow:
    """Write one precedent. Raises AcceptError with the honest reason.

    The caller (the API route) supplies the digest and validation rollup it
    already computed — this function owns the precedent invariants:
    non-empty authorship, digest-deduplication, and a complete payload.
    """
    if not accepted_by.strip():
        raise AcceptError("accepted_by is required — a precedent needs an author")
    if not acceptance_note.strip():
        raise AcceptError(
            "acceptance_note is required — future sessions will read this to "
            "know why the design was considered good"
        )
    if not content_digest:
        raise AcceptError(
            "this design has no export package yet — a precedent is the "
            "accepted DELIVERABLE, so build the LUXEXCHANGE package first "
            "(POST /api/geometry/assembly/{design_id}/exports)"
        )
    if overall_status == "fail":
        raise AcceptError(
            "a failing design cannot become a precedent — its validation "
            "rollup is 'fail'; fix the design or accept a different one"
        )

    design = session.get(DesignRow, design_id)
    if design is None:
        raise AcceptError(f"design {design_id} does not exist")
    stored = json.loads(design.parameter_json)

    # Dedupe on the package digest among living precedents (R1).
    existing = session.execute(
        select(DesignDnaRow)
        .where(DesignDnaRow.content_digest == content_digest)
        .where(DesignDnaRow.status != "deleted")
    ).scalars().first()
    if existing is not None:
        raise AcceptError(
            f"this exact deliverable is already precedent {existing.id} "
            f"(same content_digest {content_digest[:16]}…); accept is "
            f"idempotent per package, not per click"
        )

    tags = derive_tags(stored, validation_statuses, overall_status, costing)
    summary = {
        "schema": "designdna_record_v1",
        "design_id": design_id,
        "spec_hash": design.spec_hash,
        "geometry_hash": design.geometry_hash,
        "brief_summary": brief_summary,
        "request": stored.get("request"),
        "manifest": stored.get("manifest"),
        "artifacts": stored.get("artifacts"),
        "validation": {
            "overall_status": overall_status,
            "gate_statuses": validation_statuses,
        },
        "costing": costing,
        "costing_unavailable_reason": (
            None if costing is not None else
            (costing_unavailable_reason or "no BOM was available at acceptance")
        ),
    }

    row = DesignDnaRow(
        id=str(uuid.uuid4()),
        created_at=_utc_now(),
        design_id=design_id,
        embedding_ref=None,  # local vector search is a later, additive slice
        summary_json=json.dumps(summary, sort_keys=True),
        status="active",
        accepted_by=accepted_by.strip(),
        acceptance_note=acceptance_note.strip(),
        content_digest=content_digest,
        tags_json=json.dumps(tags, sort_keys=True),
        archived_at=None,
    )
    session.add(row)
    log.info(
        "designdna accept: precedent=%s design=%s digest=%s by=%s",
        row.id, design_id, content_digest[:16], accepted_by,
    )
    return row


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def _public(row: DesignDnaRow, match_reasons: list[str] | None = None) -> dict[str, Any]:
    if row.status == "deleted":
        # Tombstone: the id resolves, the payload is gone, and we say so.
        return {
            "id": row.id,
            "created_at": row.created_at,
            "design_id": row.design_id,
            "status": "deleted",
            "detail": "this precedent was deleted; only its identity remains",
        }
    tags = json.loads(row.tags_json) if row.tags_json else {}
    out: dict[str, Any] = {
        "id": row.id,
        "created_at": row.created_at,
        "design_id": row.design_id,
        "status": row.status or "active",
        "accepted_by": row.accepted_by,
        "acceptance_note": row.acceptance_note,
        "content_digest": row.content_digest,
        "tags": tags,
        "archived_at": row.archived_at,
    }
    if match_reasons is not None:
        out["match_reasons"] = match_reasons
    return out


def get_precedent(session, precedent_id: str, *, full: bool = False) -> dict[str, Any] | None:
    row = session.get(DesignDnaRow, precedent_id)
    if row is None:
        return None
    out = _public(row)
    if full and row.status != "deleted":
        out["record"] = json.loads(row.summary_json)
    return out


def list_precedents(session, *, include_archived: bool = False) -> list[dict[str, Any]]:
    query = select(DesignDnaRow).where(DesignDnaRow.status != "deleted")
    if not include_archived:
        query = query.where(DesignDnaRow.status == "active")
    rows = session.execute(query.order_by(DesignDnaRow.created_at.desc())).scalars().all()
    return [_public(r) for r in rows]


def search_precedents(
    session,
    *,
    material: str | None = None,
    primitive: str | None = None,
    has_water: bool | None = None,
    gate_profile_id: str | None = None,
    height_m: float | None = None,
    height_band_pct: float = 50.0,
    text: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Deterministic AND-matching with a named reason per matched field.

    Every supplied criterion must match; every match names itself. Ordered
    by number of reasons (more specific first), then recency. The dataset is
    accepted designs — tens, not millions — so loading active rows and
    filtering in code is both fast and fully explainable.
    """
    rows = session.execute(
        select(DesignDnaRow)
        .where(DesignDnaRow.status == "active")
        .order_by(DesignDnaRow.created_at.desc())
    ).scalars().all()

    results: list[dict[str, Any]] = []
    for row in rows:
        tags = json.loads(row.tags_json) if row.tags_json else {}
        reasons: list[str] = []

        if material is not None:
            if material not in (tags.get("materials") or []):
                continue
            reasons.append(f"material {material}")
        if primitive is not None:
            if primitive not in (tags.get("primitives") or []):
                continue
            reasons.append(f"uses primitive {primitive}")
        if has_water is not None:
            if bool(tags.get("has_water")) != has_water:
                continue
            reasons.append("water design" if has_water else "dry design")
        if gate_profile_id is not None:
            if tags.get("gate_profile_id") != gate_profile_id:
                continue
            reasons.append(f"validated under profile {gate_profile_id}")
        if height_m is not None:
            got = tags.get("height_m")
            if not isinstance(got, (int, float)):
                continue
            low = height_m * (1 - height_band_pct / 100.0)
            high = height_m * (1 + height_band_pct / 100.0)
            if not (low <= float(got) <= high):
                continue
            reasons.append(
                f"height {got:g} m within {low:.2f}–{high:.2f} m of requested "
                f"{height_m:g} m"
            )
        if text:
            haystack = " ".join(
                filter(None, [row.acceptance_note, row.accepted_by])
            ).lower()
            if text.lower() not in haystack:
                continue
            reasons.append(f"note mentions {text!r}")

        results.append(_public(row, reasons))

    # Newest first, then (stable sort) most-specific first: a precedent that
    # matched three criteria outranks one that matched one.
    results.sort(key=lambda r: r["created_at"], reverse=True)
    results.sort(key=lambda r: -len(r["match_reasons"]))
    return results[: max(1, limit)]


# ---------------------------------------------------------------------------
# Injection into Council prompts
# ---------------------------------------------------------------------------

def precedent_block(precedents: list[dict[str, Any]]) -> str:
    """Render precedents as a quarantined, provenance-marked prompt block (R5).

    The framing sentence is load-bearing: without it, the Council copies a
    precedent's 2.4 m basin into a brief that asked for 1.2 m because the
    precedent said so. Numbers here describe PRIOR work, never requirements.
    """
    if not precedents:
        return ""
    lines = [
        "=== BEGIN PRECEDENTS (prior accepted work — context only) ===",
        "These are designs LuxuryCon previously accepted and delivered. Their",
        "numbers describe PRIOR projects, NOT requirements for this brief.",
        "Use them for house style, proven proportions and material pairings.",
        "Never copy a dimension from a precedent over one stated in the brief.",
        "",
    ]
    for p in precedents[:MAX_INJECTED_PRECEDENTS]:
        tags = p.get("tags") or {}
        reasons = p.get("match_reasons") or []
        lines.append(f"PRECEDENT {p['id']} (accepted {p['created_at'][:10]}):")
        lines.append(f"  why accepted: {p.get('acceptance_note')}")
        lines.append(
            f"  materials: {', '.join(tags.get('materials') or []) or 'unknown'}"
            f" | primitives: {', '.join(tags.get('primitives') or []) or 'unknown'}"
        )
        mass_text = (f"{tags.get('total_mass_kg')} kg"
                     if tags.get("total_mass_kg") is not None
                     else "incomplete (ADR-065)")
        lines.append(
            f"  height {tags.get('height_m')} m, footprint {tags.get('footprint_m')} m,"
            f" mass {mass_text},"
            f" water: {'yes' if tags.get('has_water') else 'no'}"
        )
        lines.append(
            f"  validation: {tags.get('overall_status')} under profile "
            f"{tags.get('gate_profile_id')}"
        )
        if reasons:
            lines.append(f"  matched this brief because: {'; '.join(reasons)}")
        lines.append("")
    lines.append("=== END PRECEDENTS ===")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Archive / delete
# ---------------------------------------------------------------------------

def archive_precedent(session, precedent_id: str) -> dict[str, Any] | None:
    row = session.get(DesignDnaRow, precedent_id)
    if row is None or row.status == "deleted":
        return None
    row.status = "archived"
    row.archived_at = _utc_now()
    log.info("designdna archive: %s", precedent_id)
    return _public(row)


def delete_precedent(session, precedent_id: str) -> dict[str, Any] | None:
    """Wipe the payload, keep the tombstone (R6).

    An old Council session that cited this id must resolve to "deleted",
    never to a dangling reference or — worse — to stale content.
    """
    row = session.get(DesignDnaRow, precedent_id)
    if row is None:
        return None
    row.status = "deleted"
    row.summary_json = "{}"
    row.tags_json = None
    row.accepted_by = None
    row.acceptance_note = None
    row.content_digest = None
    row.archived_at = _utc_now()
    log.info("designdna delete (tombstoned): %s", precedent_id)
    return _public(row)
