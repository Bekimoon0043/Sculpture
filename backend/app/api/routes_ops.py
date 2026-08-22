"""Operations API — Phase 13 slice A (jobs, costs, reconciliation).

  GET /api/ops/jobs      every job with status, type, checkpoint state,
                         halt reason and failure class
  GET /api/ops/costs     spend summed from ai_calls, RECONCILED against the
                         sessions ledger — two independent records that must
                         agree (Rule 8: auditable means two books, not one)

The cost endpoint does arithmetic, never estimates: every number is a sum
over logged rows, and a mismatch between the two ledgers is surfaced as a
finding, not smoothed over.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.db.database import get_default_db
from app.db.models import AICallRow, BudgetEventRow, JobRow, SessionRow

log = logging.getLogger("luxuryform.api.ops")

router = APIRouter(prefix="/ops", tags=["ops"])

#: Reconciliation tolerance: cost_usd is rounded to 6 dp per call, so the
#: two ledgers may differ by rounding, never by a missing call.
RECONCILE_TOLERANCE_USD = 0.001


@router.get("/jobs")
def get_jobs(limit: int = 50) -> dict[str, Any]:
    db = get_default_db()
    with db.get_session() as session:
        rows = session.execute(
            select(JobRow).order_by(JobRow.ts.desc()).limit(max(1, min(limit, 500)))
        ).scalars().all()
    jobs = []
    for row in rows:
        try:
            state = json.loads(row.state_json)
        except (ValueError, TypeError):
            state = {"raw": row.state_json}
        failure_class = None
        if row.halt_reason:
            # Phase 13 R3: the class is the first token when the writer
            # recorded one ("input: ...", "defect: ..."), else unclassified.
            head = row.halt_reason.split(":", 1)[0].strip().lower()
            failure_class = head if head in {
                "transient", "resource", "input", "defect"
            } else "unclassified"
        jobs.append({
            "id": row.id,
            "ts": row.ts,
            "job_type": row.job_type,
            "status": row.status,
            "session_id": row.session_id,
            "state": state,
            "halt_reason": row.halt_reason,
            "failure_class": failure_class,
        })
    return {"jobs": jobs, "count": len(jobs)}


@router.get("/costs")
def get_costs() -> dict[str, Any]:
    """Spend, summed from the per-call ledger and reconciled.

    ai_calls is the per-call book (every provider call, Rule 8); sessions is
    the running-total book the budget enforcer maintains. They are written
    by different code at different times — agreement is evidence, and
    disagreement is a finding this endpoint reports with the session ids.
    """
    db = get_default_db()
    with db.get_session() as session:
        calls = session.execute(select(AICallRow)).scalars().all()
        sessions = session.execute(select(SessionRow)).scalars().all()
        events = session.execute(
            select(BudgetEventRow).order_by(BudgetEventRow.ts.desc()).limit(50)
        ).scalars().all()

    by_purpose: dict[str, dict[str, Any]] = {}
    by_provider: dict[str, dict[str, Any]] = {}
    by_day: dict[str, float] = {}
    per_session_calls: dict[str, float] = {}
    error_cost = 0.0
    error_count = 0
    total = 0.0

    for call in calls:
        total += call.cost_usd
        per_session_calls[call.session_id] = (
            per_session_calls.get(call.session_id, 0.0) + call.cost_usd
        )
        slot = by_purpose.setdefault(
            call.purpose, {"cost_usd": 0.0, "calls": 0, "errors": 0}
        )
        slot["cost_usd"] += call.cost_usd
        slot["calls"] += 1
        pslot = by_provider.setdefault(
            call.provider, {"cost_usd": 0.0, "calls": 0, "errors": 0}
        )
        pslot["cost_usd"] += call.cost_usd
        pslot["calls"] += 1
        day = call.ts[:10]
        by_day[day] = by_day.get(day, 0.0) + call.cost_usd
        if call.status != "ok":
            slot["errors"] += 1
            pslot["errors"] += 1
            error_cost += call.cost_usd
            error_count += 1

    # --- reconciliation: the per-call book vs the session ledger ----------
    mismatches: list[dict[str, Any]] = []
    session_totals = {s.id: s.total_cost_usd for s in sessions}
    for session_id, call_sum in per_session_calls.items():
        ledger = session_totals.get(session_id)
        if ledger is None:
            mismatches.append({
                "session_id": session_id,
                "calls_usd": round(call_sum, 6),
                "ledger_usd": None,
                "finding": "calls exist but no session ledger row",
            })
        elif abs(ledger - call_sum) > RECONCILE_TOLERANCE_USD:
            mismatches.append({
                "session_id": session_id,
                "calls_usd": round(call_sum, 6),
                "ledger_usd": round(ledger, 6),
                "finding": "the two ledgers disagree beyond rounding",
            })

    def _round(d: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {
            k: {**v, "cost_usd": round(v["cost_usd"], 6)}
            for k, v in sorted(d.items(), key=lambda kv: -kv[1]["cost_usd"])
        }

    return {
        "total_usd": round(total, 6),
        "call_count": len(calls),
        "by_purpose": _round(by_purpose),
        "by_provider": _round(by_provider),
        "by_day": {k: round(v, 6) for k, v in sorted(by_day.items(), reverse=True)},
        # Failed calls still cost money when the provider billed the attempt;
        # a separate line stops a flaky connection masquerading as work.
        "error_calls": {"count": error_count, "cost_usd": round(error_cost, 6)},
        "reconciliation": {
            "checked_sessions": len(per_session_calls),
            "tolerance_usd": RECONCILE_TOLERANCE_USD,
            "mismatches": mismatches,
            "clean": not mismatches,
        },
        "budget_events": [
            {"ts": e.ts, "session_id": e.session_id,
             "event_type": e.event_type, "detail": e.detail}
            for e in events
        ],
    }
