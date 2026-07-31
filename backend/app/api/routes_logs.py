"""Audit-log API (Rule 8): every AI call and every budget event is queryable.

GET /api/logs/calls?limit=&provider=  -> ai_calls rows (full prompt/response)
GET /api/logs/budget                  -> spend today, session spend, caps, events
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.budget import BudgetEnforcer
from app.core.config import load_config_bundle
from app.db.database import get_default_db
from app.db.models import AICallRow, BudgetEventRow, SessionRow

router = APIRouter(tags=["logs"])


@router.get("/logs/calls")
def list_calls(
    limit: int = Query(default=50, ge=1, le=1000),
    provider: str | None = Query(default=None),
) -> dict:
    db = get_default_db()
    stmt = select(AICallRow).order_by(AICallRow.ts.desc()).limit(limit)
    if provider:
        stmt = select(AICallRow).where(AICallRow.provider == provider).order_by(
            AICallRow.ts.desc()
        ).limit(limit)
    with db.get_session() as s:
        rows = s.execute(stmt).scalars().all()
    return {
        "count": len(rows),
        "calls": [
            {
                "id": r.id,
                "session_id": r.session_id,
                "ts": r.ts,
                "provider": r.provider,
                "model": r.model,
                "purpose": r.purpose,
                "prompt": r.prompt,
                "response": r.response,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "latency_ms": r.latency_ms,
                "cost_usd": r.cost_usd,
                "pricing_version": r.pricing_version,
                "status": r.status,
                "error": r.error,
            }
            for r in rows
        ],
    }


@router.get("/logs/budget")
def budget_status() -> dict:
    db = get_default_db()
    bundle = load_config_bundle()
    caps = bundle.budget

    # Session/day spend derive from ai_calls — the single source of truth.
    probe = BudgetEnforcer("__budget_view__", caps.session_cap_usd,
                           caps.day_cap_usd, db)
    with db.get_session() as s:
        per_session = s.execute(
            select(SessionRow.id, SessionRow.total_cost_usd).order_by(
                SessionRow.started_at.desc()
            ).limit(50)
        ).all()
        events = s.execute(
            select(BudgetEventRow).order_by(BudgetEventRow.ts.desc()).limit(100)
        ).scalars().all()

    return {
        "spent_today_usd": probe.spent_today(),
        "caps": {
            "session_cap_usd": caps.session_cap_usd,
            "day_cap_usd": caps.day_cap_usd,
            "max_vision_iterations": caps.max_vision_iterations,
            "on_breach": caps.on_breach,
        },
        "sessions": [
            {"session_id": sid, "total_cost_usd": total}
            for sid, total in per_session
        ],
        "budget_events": [
            {
                "id": e.id,
                "session_id": e.session_id,
                "ts": e.ts,
                "event_type": e.event_type,
                "detail": e.detail,
            }
            for e in events
        ],
    }
