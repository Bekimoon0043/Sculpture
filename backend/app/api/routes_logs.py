"""Audit-log API (Rule 8): every AI call and every budget event is queryable.

GET /api/logs/calls?limit=&provider=  -> ai_calls rows (full prompt/response)
GET /api/logs/budget                  -> spend today, session spend, caps, events
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.budget import BudgetEnforcer, bound_basis_for_display
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

    # Day spend derives from ai_calls settled truth + open holds at their
    # bounds (ADR-061); the probe enforcer only reads, never reserves.
    probe = BudgetEnforcer("__budget_view__", caps.run_cap_usd,
                           caps.day_cap_usd, db)
    from app.db.models import SpendReservationRow, SpendSafetyLockRow

    with db.get_session() as s:
        per_session = s.execute(
            select(SessionRow.id, SessionRow.total_cost_usd).order_by(
                SessionRow.started_at.desc()
            ).limit(50)
        ).all()
        events = s.execute(
            select(BudgetEventRow).order_by(BudgetEventRow.ts.desc()).limit(100)
        ).scalars().all()
        open_holds = s.execute(
            select(SpendReservationRow)
            .where(SpendReservationRow.status.in_(("held", "uncertain")))
            .order_by(SpendReservationRow.created_at.desc())
            .limit(100)
        ).scalars().all()
        active_locks = s.execute(
            select(SpendSafetyLockRow)
            .where(SpendSafetyLockRow.status == "active")
            .order_by(SpendSafetyLockRow.created_at.desc())
        ).scalars().all()
        reconciled = s.execute(
            select(SpendReservationRow)
            .where(SpendReservationRow.status == "reconciled")
            .order_by(SpendReservationRow.created_at.desc())
            .limit(100)
        ).scalars().all()

    return {
        "spent_today_usd": probe.spent_today_usd(),
        "caps": {
            "run_cap_usd": caps.run_cap_usd,
            "day_cap_usd": caps.day_cap_usd,
            "max_vision_iterations": caps.max_vision_iterations,
            "on_breach": caps.on_breach,
        },
        # ADR-061 operator visibility: money currently held or uncertain
        # (each row still consuming headroom at reserved_usd), and any
        # active safety locks (these REFUSE matching paid dispatch until
        # resolved via scripts/spend_admin.py).
        "open_holds": [
            {
                "reservation_id": r.id,
                "created_at": r.created_at,
                "scope_id": r.scope_id,
                "provider": r.provider,
                "model": r.model,
                "status": r.status,
                "reserved_usd": r.reserved_usd_micro / 1_000_000,
                "note": r.note,
                # D-28 (ADR-070): why the hold is the size it is.
                "bound_basis": bound_basis_for_display(r.bound_basis),
            }
            for r in open_holds
        ],
        "active_safety_locks": [
            {
                "lock_id": lk.id,
                "created_at": lk.created_at,
                "provider": lk.provider,
                "model": lk.model,
                "reason": lk.reason,
                "detail": lk.detail,
            }
            for lk in active_locks
        ],
        # Operator-reconciled ORPHAN spend (ADR-061): dead/unpriced attempts
        # the operator verified in the provider console. Already included in
        # spent_today_usd for its dispatch day; shown here explicitly as
        # "reconciled unmatched spend", never as a fabricated ai_calls row.
        "reconciled_unmatched_spend": [
            {
                "reservation_id": r.id,
                "scope_id": r.scope_id,
                "session_id": r.session_id,
                "day_utc": r.day_utc,
                "created_at": r.created_at,
                "provider": r.provider,
                "model": r.model,
                "reserved_usd": r.reserved_usd_micro / 1_000_000,
                "reconciled_usd": (r.settled_usd_micro or 0) / 1_000_000,
                "ai_call_id": r.ai_call_id,
                "note": r.note,
                "bound_basis": bound_basis_for_display(r.bound_basis),
            }
            for r in reconciled
        ],
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
