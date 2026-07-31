"""Spend-cap enforcement (Amendment 2 — the heart of Phase 1).

Hard ceilings on AI spend, checked BEFORE any API call is dispatched:

* per-session cap (budget.yaml: session_cap_usd)
* per-UTC-day cap   (budget.yaml: day_cap_usd)

On breach: halt, persist state, report — never silently continue. The halt
writes a ``budget_events`` row AND a ``jobs`` row (status='halted_budget')
carrying the persisted state so a run can be inspected and resumed later.

Spend is derived from the ``ai_calls`` table — the single source of truth —
never from a side counter. All money math is rounded to 6 decimal places.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.db.database import Database
from app.db.models import AICallRow, BudgetEventRow, JobRow, SessionRow


def _round6(value: float) -> float:
    return round(float(value), 6)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BudgetHalt(Exception):
    """Raised when a spend cap would be breached. Carries the full context."""

    def __init__(self, session_id: str, reason: str, spent: float, cap: float) -> None:
        super().__init__(reason)
        self.session_id = session_id
        self.reason = reason
        self.spent_usd = _round6(spent)
        self.cap_usd = _round6(cap)


class BudgetEnforcer:
    """Pre-dispatch cap check + post-dispatch accounting for one session."""

    def __init__(
        self,
        session_id: str,
        session_cap_usd: float,
        day_cap_usd: float,
        db: Database,
    ) -> None:
        if session_cap_usd <= 0 or day_cap_usd <= 0:
            raise ValueError("caps must be positive USD amounts")
        self.session_id = session_id
        self.session_cap_usd = _round6(session_cap_usd)
        self.day_cap_usd = _round6(day_cap_usd)
        self.db = db

    # -- spend queries (ai_calls is the single source of truth) -------------

    def spent_session(self) -> float:
        """Total recorded cost of AI calls in this session."""
        with self.db.get_session() as s:
            total = s.execute(
                select(func.coalesce(func.sum(AICallRow.cost_usd), 0.0)).where(
                    AICallRow.session_id == self.session_id
                )
            ).scalar_one()
        return _round6(total)

    def spent_today(self) -> float:
        """Total recorded cost of AI calls across ALL sessions on the current
        UTC calendar day (ts is UTC ISO-8601 text; first 10 chars = the date)."""
        today = datetime.now(timezone.utc).date().isoformat()
        with self.db.get_session() as s:
            total = s.execute(
                select(func.coalesce(func.sum(AICallRow.cost_usd), 0.0)).where(
                    func.substr(AICallRow.ts, 1, 10) == today
                )
            ).scalar_one()
        return _round6(total)

    # -- enforcement ----------------------------------------------------------

    def pre_dispatch_check(self, estimated_cost_usd: float) -> None:
        """Raise BudgetHalt if dispatching a call with this estimated cost
        would breach the session cap or the UTC-day cap. On raise, the breach
        is persisted (budget_events + halted jobs row) before the exception
        leaves this method."""
        est = _round6(estimated_cost_usd)
        if est < 0:
            raise ValueError("estimated cost cannot be negative")

        spent_session = self.spent_session()
        if _round6(spent_session + est) > self.session_cap_usd:
            self._halt(
                cap_kind="session",
                spent=spent_session,
                cap=self.session_cap_usd,
                attempted_estimate_usd=est,
            )

        spent_today = self.spent_today()
        if _round6(spent_today + est) > self.day_cap_usd:
            self._halt(
                cap_kind="day",
                spent=spent_today,
                cap=self.day_cap_usd,
                attempted_estimate_usd=est,
            )

    def record_actual(self, cost_usd: float) -> None:
        """Post-dispatch accounting: fold the real cost into the session
        aggregate. (Per-call truth stays in ai_calls; this is the running
        total shown to the operator.)"""
        cost = _round6(cost_usd)
        if cost < 0:
            raise ValueError("cost cannot be negative")
        with self.db.get_session() as s:
            row = s.get(SessionRow, self.session_id)
            if row is None:
                row = SessionRow(
                    id=self.session_id,
                    started_at=_utc_now_iso(),
                    ended_at=None,
                    status="active",
                    total_cost_usd=0.0,
                )
                s.add(row)
            row.total_cost_usd = _round6(row.total_cost_usd + cost)

    # -- internals ------------------------------------------------------------

    def _halt(
        self,
        *,
        cap_kind: str,
        spent: float,
        cap: float,
        attempted_estimate_usd: float,
    ) -> None:
        reason = (
            f"{cap_kind} spend cap would be breached: "
            f"spent ${spent:.6f} + estimated ${attempted_estimate_usd:.6f} "
            f"> {cap_kind} cap ${cap:.6f} — halting, state persisted "
            f"(Amendment 2: halt_and_report)"
        )
        now = _utc_now_iso()
        detail = json.dumps(
            {
                "cap_kind": cap_kind,
                "spent_usd": _round6(spent),
                "cap_usd": _round6(cap),
                "attempted_estimate_usd": attempted_estimate_usd,
            },
            sort_keys=True,
        )
        state = json.dumps(
            {
                "session_id": self.session_id,
                "halted_at": now,
                "cap_kind": cap_kind,
                "spent_session_usd": self.spent_session(),
                "spent_today_usd": self.spent_today(),
                "session_cap_usd": self.session_cap_usd,
                "day_cap_usd": self.day_cap_usd,
                "attempted_estimate_usd": attempted_estimate_usd,
            },
            sort_keys=True,
        )
        with self.db.get_session() as s:
            s.add(
                BudgetEventRow(
                    id=str(uuid.uuid4()),
                    session_id=self.session_id,
                    ts=now,
                    event_type="cap_breach",
                    detail=detail,
                )
            )
            s.add(
                JobRow(
                    id=str(uuid.uuid4()),
                    session_id=self.session_id,
                    ts=now,
                    job_type="ai_dispatch",
                    status="halted_budget",
                    state_json=state,
                    halt_reason=reason,
                )
            )
        raise BudgetHalt(self.session_id, reason, spent, cap)
