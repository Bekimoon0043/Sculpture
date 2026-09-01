"""Brief intake API — Phase 12 (L1).

The intake is the honest channel between a client's prose and the platform's
typed contexts. The flow the routes support:

  POST /api/intake                    create a draft (brief text + any fields)
  POST /api/intake/{id}/parse         ONE paid parser call fills gaps ($, logged)
  PUT  /api/intake/{id}               operator edits fields (source=operator)
  GET  /api/intake/{id} · /latest     read, always with readiness attached
  POST /api/intake/{id}/confirm       freeze for use by Council / validation

Editing costs nothing: the parse result is stored, and the operator can
correct fields and re-confirm without a second provider call (plan R4).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.budget import BudgetEnforcer
from app.core.config import get_settings, load_config_bundle
from app.db.database import get_default_db
from app.db.models import IntakeRow
from app.intake.models import (
    IntakeV1,
    Sourced,
    readiness,
    summary_block,
    to_site_overrides,
)

log = logging.getLogger("luxuryform.api.intake")

router = APIRouter(prefix="/intake", tags=["intake"])


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IntakeCreateRequest(BaseModel):
    brief_text: str = ""
    #: {"site.city": "Addis Ababa", ...} — dotted fields the operator typed.
    fields: dict[str, Any] = {}


class IntakeUpdateRequest(BaseModel):
    fields: dict[str, Any]
    #: A field set to null clears it back to unknown.


def _apply_operator_fields(intake: IntakeV1, fields: dict[str, Any]) -> list[str]:
    """Set dotted fields with source=operator. Returns rejected field names."""
    rejected: list[str] = []
    for dotted, value in fields.items():
        parts = dotted.split(".")
        if len(parts) != 2 or not hasattr(intake, parts[0]):
            rejected.append(dotted)
            continue
        section = getattr(intake, parts[0])
        if not hasattr(section, parts[1]):
            rejected.append(dotted)
            continue
        if value is None:
            setattr(section, parts[1], Sourced.unknown())
        else:
            setattr(section, parts[1], Sourced(value=value, source="operator"))
    return rejected


def _payload(row: IntakeRow) -> dict[str, Any]:
    intake = IntakeV1.model_validate(json.loads(row.normalized_json))
    overrides = to_site_overrides(intake)
    return {
        "id": row.id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "status": row.status,
        "brief_text": row.brief_text,
        "council_session_id": row.council_session_id,
        "intake": intake.dump_wire(),
        "readiness": readiness(intake),
        "summary_block": summary_block(intake, row.id),
        # Which gate-profile thresholds THIS intake supplies. Derived by the
        # same function the build path uses, so the UI can never disagree
        # with what the gates actually receive — the panel used to warn that
        # a threshold was unset while the intake was already supplying it.
        "site_overrides": {k: v for k, v in overrides.items() if k != "_source"},
    }


def _get_or_404(session, intake_id: str) -> IntakeRow:
    row = session.get(IntakeRow, intake_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no intake {intake_id}")
    return row


@router.post("", status_code=201)
def create_intake(req: IntakeCreateRequest) -> dict[str, Any]:
    intake = IntakeV1()
    rejected = _apply_operator_fields(intake, req.fields)
    if rejected:
        raise HTTPException(
            status_code=422,
            detail=f"unknown intake fields: {rejected}",
        )
    now = _utc_now()
    row = IntakeRow(
        id=str(uuid.uuid4()), created_at=now, updated_at=now,
        brief_text=req.brief_text.strip(),
        normalized_json=json.dumps(intake.dump_wire(), sort_keys=True),
        status="draft", council_session_id=None,
    )
    db = get_default_db()
    with db.get_session() as session:
        session.add(row)
    return _payload(row)


@router.get("/latest")
def get_latest_intake() -> dict[str, Any]:
    db = get_default_db()
    with db.get_session() as session:
        row = session.execute(
            select(IntakeRow).order_by(IntakeRow.created_at.desc()).limit(1)
        ).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="no intake yet")
    return _payload(row)


@router.get("/{intake_id}")
def get_intake(intake_id: str) -> dict[str, Any]:
    db = get_default_db()
    with db.get_session() as session:
        row = _get_or_404(session, intake_id)
    return _payload(row)


@router.put("/{intake_id}")
def update_intake(intake_id: str, req: IntakeUpdateRequest) -> dict[str, Any]:
    """Operator edits. Free — no provider call, no token spent (plan R4)."""
    db = get_default_db()
    with db.get_session() as session:
        row = _get_or_404(session, intake_id)
        intake = IntakeV1.model_validate(json.loads(row.normalized_json))
        rejected = _apply_operator_fields(intake, req.fields)
        if rejected:
            raise HTTPException(status_code=422, detail=f"unknown intake fields: {rejected}")
        row.normalized_json = json.dumps(intake.dump_wire(), sort_keys=True)
        row.updated_at = _utc_now()
        # Editing a confirmed intake reopens it: the confirmation covered the
        # OLD content, and downstream consumers must see that it changed.
        row.status = "draft"
    return _payload(row)


@router.post("/{intake_id}/parse")
def parse_intake(intake_id: str) -> dict[str, Any]:
    """ONE paid provider call to fill the gaps the operator left.

    Operator-sourced fields are never overwritten. Without API keys this
    fails with an honest 503 and the form keeps working by hand.
    """
    from app.ai.provider import ProviderError
    from app.ai.providers import build_providers
    from app.intake.parser import PARSER_ROLE, run_parse

    db = get_default_db()
    bundle = load_config_bundle()
    settings = get_settings()

    role = bundle.council.roles.get(PARSER_ROLE)
    provider_name = (role.primary if role else None) or "openai"

    with db.get_session() as session:
        row = _get_or_404(session, intake_id)
        if not row.brief_text.strip():
            raise HTTPException(
                status_code=422,
                detail="this intake has no brief text to parse — add the "
                       "client's brief first",
            )
        intake = IntakeV1.model_validate(json.loads(row.normalized_json))

    # ADR-061: the SESSION id stays per-parse (each parse is one audited
    # dispatch group), but the SPEND SCOPE is deterministic over the FULL
    # intake id — repeated parses of one intake accumulate under one run
    # cap; the cap never resets by accident (Amendment 3).
    from app.core.budget import intake_scope_id

    session_id = f"intake-{intake_id[:8]}-{uuid.uuid4().hex[:8]}"
    budget = BudgetEnforcer(
        session_id, bundle.budget.run_cap_usd, bundle.budget.day_cap_usd, db,
        scope_id=intake_scope_id(intake_id),
        scope_kind="intake",
        design_ref=intake_id,
    )
    providers = build_providers(settings, bundle, db, budget)
    material_ids = sorted(bundle.materials.materials)
    try:
        merged, accounting = run_parse(
            providers[provider_name],
            brief=row.brief_text, intake=intake,
            material_ids=material_ids, session_id=session_id,
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"parser provider {provider_name} unavailable: {exc}. "
                   f"The form still works — fill the fields by hand.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"the parser reply was not valid JSON: {exc}. The call is "
                   f"logged under session {session_id}; retry or fill by hand.",
        ) from exc

    with db.get_session() as session:
        fresh = _get_or_404(session, intake_id)
        fresh.normalized_json = json.dumps(merged.dump_wire(), sort_keys=True)
        fresh.updated_at = _utc_now()
        fresh.status = "draft"
    out = _payload(fresh)
    out["parse"] = {**accounting, "session_id": session_id}
    return out


@router.post("/{intake_id}/confirm")
def confirm_intake(intake_id: str) -> dict[str, Any]:
    """Freeze the intake for downstream use.

    Confirmation requires tiers 1 and 2 answered (plan R5) — the fields
    whose absence blocks geometry or a validation gate. Tiers 3 and 4 may
    stay unknown; the affected layer reports it honestly.
    """
    db = get_default_db()
    with db.get_session() as session:
        row = _get_or_404(session, intake_id)
        intake = IntakeV1.model_validate(json.loads(row.normalized_json))
        ready = readiness(intake)
        if not ready["ready_for_council"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "intake is not ready — tier 1/2 fields are "
                               "missing; answer them before paid Council calls",
                    "missing_by_tier": ready["missing_by_tier"],
                },
            )
        row.status = "confirmed"
        row.updated_at = _utc_now()
    return _payload(row)
