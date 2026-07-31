"""Budget enforcer tests (Amendment 2).

Real DB, real rows: caps derive from the ai_calls table, breaches persist
budget_events + halted jobs rows, and UTC-day logic is exercised with real
timestamps.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.budget import BudgetEnforcer, BudgetHalt
from app.db.models import AICallRow, BudgetEventRow, JobRow, SessionRow


def _insert_call(db, session_id: str, cost_usd: float, ts: datetime | None = None) -> None:
    """Write an ai_calls row exactly as the production log path would."""
    when = ts or datetime.now(timezone.utc)
    with db.get_session() as s:
        if s.get(SessionRow, session_id) is None:
            s.add(
                SessionRow(
                    id=session_id,
                    started_at=when.isoformat(),
                    ended_at=None,
                    status="active",
                    total_cost_usd=0.0,
                )
            )
            s.flush()  # parent row must hit the DB before the FK'd child row
        s.add(
            AICallRow(
                id=str(uuid.uuid4()),
                session_id=session_id,
                ts=when.isoformat(),
                provider="test",
                model="test-model",
                purpose="test",
                prompt="p",
                response="r",
                tokens_in=1,
                tokens_out=1,
                latency_ms=1.0,
                cost_usd=cost_usd,
                pricing_version="test-v1",
                status="ok",
                error=None,
            )
        )


def test_pre_dispatch_check_passes_under_cap(db):
    enforcer = BudgetEnforcer("s1", session_cap_usd=5.0, day_cap_usd=25.0, db=db)
    _insert_call(db, "s1", 1.0)
    enforcer.pre_dispatch_check(2.0)  # 1.0 + 2.0 = 3.0 < 5.0 — must not raise


def test_raises_over_session_cap_and_persists_state(db):
    enforcer = BudgetEnforcer("s2", session_cap_usd=1.0, day_cap_usd=25.0, db=db)
    _insert_call(db, "s2", 0.8)
    with pytest.raises(BudgetHalt) as excinfo:
        enforcer.pre_dispatch_check(0.5)  # 0.8 + 0.5 > 1.0
    halt = excinfo.value
    assert halt.session_id == "s2"
    assert halt.spent_usd == pytest.approx(0.8)
    assert halt.cap_usd == pytest.approx(1.0)
    assert "session" in halt.reason

    with db.get_session() as s:
        events = s.execute(
            select(BudgetEventRow).where(BudgetEventRow.session_id == "s2")
        ).scalars().all()
        jobs = s.execute(
            select(JobRow).where(JobRow.session_id == "s2")
        ).scalars().all()
    assert len(events) == 1
    assert events[0].event_type == "cap_breach"
    assert "session" in events[0].detail
    assert len(jobs) == 1
    assert jobs[0].status == "halted_budget"
    assert jobs[0].halt_reason == halt.reason
    assert "s2" in jobs[0].state_json


def test_raises_over_day_cap(db):
    enforcer = BudgetEnforcer("s3", session_cap_usd=100.0, day_cap_usd=2.0, db=db)
    _insert_call(db, "s3", 1.6)  # today by default
    with pytest.raises(BudgetHalt) as excinfo:
        enforcer.pre_dispatch_check(0.5)  # day: 1.6 + 0.5 > 2.0
    assert "day" in excinfo.value.reason


def test_record_actual_accumulates(db):
    enforcer = BudgetEnforcer("s4", session_cap_usd=5.0, day_cap_usd=25.0, db=db)
    enforcer.record_actual(0.123456)
    enforcer.record_actual(0.1)
    enforcer.record_actual(0.2)
    with db.get_session() as s:
        row = s.get(SessionRow, "s4")
    assert row is not None
    assert row.total_cost_usd == pytest.approx(0.423456)


def test_spent_session_and_today_derive_from_ai_calls(db):
    enforcer = BudgetEnforcer("s5", session_cap_usd=50.0, day_cap_usd=50.0, db=db)
    _insert_call(db, "s5", 1.0)
    _insert_call(db, "s5", 2.0)
    _insert_call(db, "other-session", 4.0)
    assert enforcer.spent_session() == pytest.approx(3.0)
    assert enforcer.spent_today() == pytest.approx(7.0)  # all sessions, UTC today


def test_utc_day_logic_excludes_yesterday(db):
    enforcer = BudgetEnforcer("s6", session_cap_usd=50.0, day_cap_usd=50.0, db=db)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    _insert_call(db, "s6", 9.0, ts=yesterday)
    _insert_call(db, "s6", 1.5)  # today
    assert enforcer.spent_session() == pytest.approx(10.5)  # session = all time
    assert enforcer.spent_today() == pytest.approx(1.5)     # day = UTC today only
