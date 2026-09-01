"""PR-2 (ADR-061): atomic spend reservations — the full contract.

Everything here is offline and $0: injected SDK transports (conftest),
throwaway temp databases, no keys, no network. Covered:

  * the cap-safe bound formula (context-window fallback), exact in µUSD;
  * barrier-based concurrency — two callers, one slot, exactly one passes;
  * per-physical-attempt reservations: settle / uncertain / retry linkage;
  * atomic settlement (ai_calls + reservation + sessions in one txn) and
    the 1:1 link in both directions;
  * fail-closed: uncertain attempts stay counted; pricing failure and
    bound-exceeded engage safety locks and halt the scope;
  * atomic cap-refusal evidence (budget_events + jobs committed with the
    refusal);
  * UTC-day rollover (the day a hold was TAKEN binds);
  * startup recovery + two-book reconciliation (exact id, no timestamps);
  * spend-scope lifecycle: uuid5 fabrication/intake identity, critique
    open-reuse/closed-new, sticky halted, audited resolutions;
  * integer micro-USD arithmetic at half-micro boundaries and over
    many-row sums where binary floats drift;
  * an enforcer-less provider cannot dispatch at all.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.ai.call_log import reserve_bound_usd_micro
from app.ai.provider import ProviderError
from app.ai.providers.kimi_provider import KimiProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.budget import (
    BudgetEnforcer,
    BudgetHalt,
    SafetyLockHalt,
    ScopeHaltedHalt,
    fabrication_scope_id,
    intake_scope_id,
    latest_open_scope,
    micro_to_usd,
    recover_stale_spend_holds,
    reconcile_spend_books,
    resolve_halted_scope,
    resolve_safety_lock,
    resolve_uncertain_hold,
    usd_to_micro,
)
from app.db.models import (
    AICallRow,
    BudgetEventRow,
    JobRow,
    SpendReservationRow,
    SpendSafetyLockRow,
    SpendScopeRow,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enforcer(db, run_cap=5.0, day_cap=25.0, session="sess-1", **kw):
    return BudgetEnforcer(session, run_cap, day_cap, db, **kw)


def _openai(db, config, transport, budget, api_key="test-key"):
    return OpenAIProvider(
        api_key, client=transport, text_model="gpt-4o", vision_model="gpt-4o",
        db=db, pricing=config.pricing, budget=budget,
    )


# ---------------------------------------------------------------------------
# micro-USD arithmetic (Amendment: Decimal from the stored decimal text,
# explicit rounding, adversarial half-micro boundaries)
# ---------------------------------------------------------------------------


def test_micro_conversion_at_half_micro_boundaries():
    from decimal import ROUND_CEILING

    assert usd_to_micro("0.0000005") == 1          # half-up rounds UP
    assert usd_to_micro("0.0000004") == 0
    assert usd_to_micro("0.0000015") == 2          # half-UP, not banker's
    assert usd_to_micro(0.000001) == 1
    assert usd_to_micro("0.0000001", rounding=ROUND_CEILING) == 1  # bounds ceil
    assert usd_to_micro(0.0, rounding=ROUND_CEILING) == 0
    # The float 0.1 has no exact binary form; str() gives its decimal face
    # and the conversion must be exactly 100000µ, never 99999 or 100001.
    assert usd_to_micro(0.1) == 100_000
    assert micro_to_usd(872_880) == 0.87288
    with pytest.raises(ValueError):
        usd_to_micro(-0.01)


def test_many_row_sum_is_exact_where_float_sum_drifts(db):
    """1000 x $0.000001 must total EXACTLY 1000µ in the ledger: a reserve
    of 1µ more against a $0.001001 day cap fits, against $0.001 refuses."""
    ts = _now()
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, started_at, status, "
            "total_cost_usd) VALUES ('s-many', ?, 'active', 0)", (ts,))
        for i in range(1000):
            conn.execute(
                "INSERT INTO ai_calls (id, session_id, ts, provider, model, "
                "purpose, prompt, response, tokens_in, tokens_out, "
                "latency_ms, cost_usd, pricing_version, status) VALUES "
                "(?, 's-many', ?, 'openai', 'gpt-4o', 'micro-sum', 'p', 'r', "
                "0, 0, 0.0, 0.000001, 'test', 'ok')",
                (f"c{i}", ts),
            )
        conn.commit()
    # float arithmetic would say sum(1000 * 1e-6) = 0.0009999999999999731
    assert abs(sum([1e-6] * 1000) - 0.001) > 0  # the drift is real
    fits = _enforcer(db, run_cap=5.0, day_cap=0.001001, session="s-fits")
    fits.reserve(1, provider="openai", model="gpt-4o", kind="text",
                 attempt_no=1)  # 1000µ + 1µ <= 1001µ — exact integers
    refuses = _enforcer(db, run_cap=5.0, day_cap=0.001, session="s-refuses")
    with pytest.raises(BudgetHalt):
        refuses.reserve(1, provider="openai", model="gpt-4o", kind="text",
                        attempt_no=1)  # 1000µ + 1µ + 1µ(held above) > 1000µ


# ---------------------------------------------------------------------------
# the bound formula (context-window fallback) — exact µUSD values
# ---------------------------------------------------------------------------


def test_reserve_bounds_are_the_documented_context_window_fallback(config):
    p = config.pricing
    # anthropic: 200000 x $3.75 (cache-write is the highest input class)
    # + 8192 x $15 output = $0.75 + $0.12288 = $0.872880 exactly.
    assert reserve_bound_usd_micro(p, "anthropic", "claude-sonnet-4-5",
                                   8192) == 872_880
    # openai: 128000 x $2.50 + 8192 x $10 = $0.32 + $0.08192 = $0.401920.
    assert reserve_bound_usd_micro(p, "openai", "gpt-4o", 8192) == 401_920
    # kimi: 1048576 x $3.00 + 8192 x $15 = $3.145728 + $0.12288 = $3.268608.
    assert reserve_bound_usd_micro(p, "kimi", "kimi-k3", 8192) == 3_268_608


def test_bound_needs_a_first_party_context_window(config):
    from app.core.config import PricingLookupError

    entry = config.pricing.providers["openai"]["gpt-4o"]
    stripped = entry.model_copy(update={"context_window_tokens": None})
    pricing = config.pricing.model_copy(deep=True)
    pricing.providers["openai"]["gpt-4o"] = stripped
    with pytest.raises(PricingLookupError, match="context_window_tokens"):
        reserve_bound_usd_micro(pricing, "openai", "gpt-4o", 100)


def test_bound_dwarfs_the_old_chars4_estimate(config):
    """The retired chars/4 estimate for an adversarial dense prompt vs the
    reservation bound: the bound must dominate by construction."""
    prompt = "警告" * 4000  # unicode-dense: far more tokens than chars/4
    old_estimate = ((len(prompt) // 4 + 1) * 2.50 + 256 * 10.0) / 1_000_000
    bound = micro_to_usd(
        reserve_bound_usd_micro(config.pricing, "openai", "gpt-4o", 256)
    )
    assert bound > old_estimate


# ---------------------------------------------------------------------------
# reserve/settle happy path through the REAL dispatch chokepoint
# ---------------------------------------------------------------------------


def test_settlement_is_atomic_and_one_to_one(db, config, openai_transport):
    budget = _enforcer(db, scope_kind="council")
    provider = _openai(db, config, openai_transport("OK", 12, 3), budget)
    resp = provider.complete("hello", purpose="t", session_id="sess-1")
    assert resp.cost_usd == 0.00006

    with db.get_session() as s:
        res = s.execute(select(SpendReservationRow)).scalars().all()
        calls = s.execute(select(AICallRow)).scalars().all()
    assert len(res) == 1 and len(calls) == 1
    r, c = res[0], calls[0]
    assert r.status == "settled"
    assert r.settled_usd_micro == 60  # $0.000060 exactly
    assert r.reserved_usd_micro == reserve_bound_usd_micro(
        config.pricing, "openai", "gpt-4o", 256)
    assert r.ai_call_id == c.id and c.reservation_id == r.id  # both directions
    assert r.attempt_no == 1 and r.day_utc == r.created_at[:10]
    assert reconcile_spend_books(db) == []
    # the sessions ledger was reconciled in the same transaction
    with sqlite3.connect(str(db.path)) as conn:
        total = conn.execute(
            "SELECT total_cost_usd FROM sessions WHERE id='sess-1'"
        ).fetchone()[0]
    assert total == 0.00006


def test_unique_partial_indexes_enforce_one_to_one(db):
    """Amendment 6: the 1:1 guarantee is SCHEMA-level, not just code."""
    ts = _now()
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute("INSERT INTO sessions (id, started_at, status, "
                     "total_cost_usd) VALUES ('s', ?, 'active', 0)", (ts,))
        conn.execute("INSERT INTO spend_scopes (id, kind, created_at, "
                     "status) VALUES ('sc', 'adhoc', ?, 'open')", (ts,))
        for rid in ("r1", "r2"):
            conn.execute(
                "INSERT INTO spend_reservations (id, created_at, day_utc, "
                "scope_id, session_id, attempt_no, provider, model, kind, "
                "reserved_usd_micro, status) VALUES (?, ?, ?, 'sc', 's', 1, "
                "'openai', 'gpt-4o', 'text', 100, 'held')",
                (rid, ts, ts[:10]),
            )
        conn.execute(
            "INSERT INTO ai_calls (id, session_id, ts, provider, model, "
            "purpose, prompt, response, tokens_in, tokens_out, latency_ms, "
            "cost_usd, pricing_version, status, reservation_id) VALUES "
            "('a1', 's', ?, 'openai', 'gpt-4o', 'p', '', '', 0, 0, 0, 0, "
            "'t', 'ok', 'r1')", (ts,))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO ai_calls (id, session_id, ts, provider, model, "
                "purpose, prompt, response, tokens_in, tokens_out, "
                "latency_ms, cost_usd, pricing_version, status, "
                "reservation_id) VALUES ('a2', 's', ?, 'openai', 'gpt-4o', "
                "'p', '', '', 0, 0, 0, 0, 't', 'ok', 'r1')", (ts,))
        conn.execute("UPDATE spend_reservations SET ai_call_id='a1' "
                     "WHERE id='r1'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE spend_reservations SET ai_call_id='a1' "
                         "WHERE id='r2'")


# ---------------------------------------------------------------------------
# barrier concurrency — two callers, one slot
# ---------------------------------------------------------------------------


def test_two_concurrent_reservers_cannot_both_pass(db):
    """threading.Barrier releases both reservers at once against a run cap
    that fits exactly ONE bound: exactly one holds, one BudgetHalt."""
    bound = usd_to_micro(2.0)
    barrier = threading.Barrier(2)
    results: list[str] = []
    halts: list[BudgetHalt] = []

    def contend(name: str) -> None:
        enforcer = _enforcer(db, run_cap=3.0, day_cap=25.0,
                             session="race", scope_id="race-scope")
        barrier.wait(timeout=10)
        try:
            results.append(
                enforcer.reserve(bound, provider="openai", model="gpt-4o",
                                 kind="text", attempt_no=1))
        except BudgetHalt as halt:
            halts.append(halt)

    threads = [threading.Thread(target=contend, args=(n,)) for n in "ab"]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert len(results) == 1, f"{len(results)} holds, {len(halts)} halts"
    assert len(halts) == 1
    assert halts[0].cap_kind == "run"
    with db.get_session() as s:
        held = s.execute(select(SpendReservationRow)).scalars().all()
    assert len(held) == 1 and held[0].status == "held"
    assert held[0].reserved_usd_micro + bound > usd_to_micro(3.0)


def test_cap_refusal_commits_its_evidence_atomically(db):
    enforcer = _enforcer(db, run_cap=0.01, day_cap=25.0, session="ref-1")
    with pytest.raises(BudgetHalt) as excinfo:
        enforcer.reserve(usd_to_micro(0.02), provider="openai",
                         model="gpt-4o", kind="text", attempt_no=1)
    assert excinfo.value.cap_kind == "run"
    with db.get_session() as s:
        events = s.execute(select(BudgetEventRow).where(
            BudgetEventRow.session_id == "ref-1")).scalars().all()
        jobs = s.execute(select(JobRow).where(
            JobRow.session_id == "ref-1")).scalars().all()
        held = s.execute(select(SpendReservationRow)).scalars().all()
    assert len(events) == 1 and events[0].event_type == "cap_breach"
    assert len(jobs) == 1 and jobs[0].status == "halted_budget"
    assert held == []  # a refusal never leaves a hold behind


# ---------------------------------------------------------------------------
# per-attempt reservations: retries, exhaustion, fail-closed uncertainty
# ---------------------------------------------------------------------------


class _FlakyTransport:
    """Times out N times, then answers — openai-compatible shape."""

    def __init__(self, inner, failures: int) -> None:
        self._inner = inner
        self._failures = failures
        self.calls: list[dict] = []
        from types import SimpleNamespace

        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= self._failures:
            raise TimeoutError("simulated network timeout")
        return self._inner._create(**kwargs)


def test_transient_retry_uses_a_new_reservation_per_attempt(
    db, config, openai_transport, monkeypatch
):
    monkeypatch.setenv("LUXURYFORM_PROVIDER_BACKOFF_BASE_S", "0")
    flaky = _FlakyTransport(openai_transport("OK", 12, 3), failures=1)
    budget = _enforcer(db)
    provider = _openai(db, config, flaky, budget)
    resp = provider.complete("hello", purpose="t", session_id="sess-1")
    assert resp.text == "OK"

    with db.get_session() as s:
        res = s.execute(select(SpendReservationRow).order_by(
            SpendReservationRow.attempt_no)).scalars().all()
        calls = s.execute(select(AICallRow)).scalars().all()
    assert [r.status for r in res] == ["uncertain", "settled"]
    assert [r.attempt_no for r in res] == [1, 2]
    # EVERY physical attempt has its own audited ai_calls row (ADR-023,
    # honest per-attempt form) with exact reservation correlation.
    assert len(calls) == 2
    by_res = {c.reservation_id: c for c in calls}
    assert by_res[res[0].id].status == "error"
    assert "timeout" in by_res[res[0].id].error
    assert by_res[res[1].id].status == "ok"
    # fail closed: the uncertain attempt still consumes its FULL bound.
    spent = budget.spent_run_usd()
    assert spent == pytest.approx(
        micro_to_usd(res[0].reserved_usd_micro) + 0.00006)
    assert reconcile_spend_books(db) == []


def test_exhausted_attempts_leave_every_hold_uncertain(
    db, config, openai_transport, monkeypatch
):
    monkeypatch.setenv("LUXURYFORM_PROVIDER_BACKOFF_BASE_S", "0")
    flaky = _FlakyTransport(openai_transport("never", 1, 1), failures=99)
    budget = _enforcer(db)
    provider = _openai(db, config, flaky, budget)
    with pytest.raises(ProviderError, match="timeout"):
        provider.complete("hello", purpose="t", session_id="sess-1")
    with db.get_session() as s:
        res = s.execute(select(SpendReservationRow)).scalars().all()
    assert len(res) == 3  # LUXURYFORM_PROVIDER_MAX_ATTEMPTS default
    assert all(r.status == "uncertain" for r in res)
    assert budget.spent_run_usd() == pytest.approx(
        3 * micro_to_usd(res[0].reserved_usd_micro))


def test_a_retry_that_no_longer_fits_halts_mid_sequence(
    db, config, openai_transport, monkeypatch
):
    """Money may already be gone: attempt 1's uncertain hold + attempt 2's
    bound exceed the run cap, so the RETRY refuses — honestly, pre-network."""
    monkeypatch.setenv("LUXURYFORM_PROVIDER_BACKOFF_BASE_S", "0")
    bound = micro_to_usd(reserve_bound_usd_micro(
        config.pricing, "openai", "gpt-4o", 256))
    flaky = _FlakyTransport(openai_transport("never", 1, 1), failures=99)
    budget = _enforcer(db, run_cap=round(bound * 1.5, 6))
    provider = _openai(db, config, flaky, budget)
    with pytest.raises(BudgetHalt) as excinfo:
        provider.complete("hello", purpose="t", session_id="sess-1")
    assert excinfo.value.cap_kind == "run"
    assert len(flaky.calls) == 1  # the second attempt never reached the SDK


def test_non_transient_error_fails_after_one_uncertain_attempt(
    db, config, openai_transport
):
    transport = openai_transport("", 0, 0,
                                 error=RuntimeError("503: service unavailable"))
    budget = _enforcer(db)
    provider = _openai(db, config, transport, budget)
    with pytest.raises(ProviderError, match="503"):
        provider.complete("hello", purpose="t", session_id="sess-1")
    with db.get_session() as s:
        res = s.execute(select(SpendReservationRow)).scalars().all()
        calls = s.execute(select(AICallRow)).scalars().all()
    assert len(res) == 1 and res[0].status == "uncertain"
    assert len(calls) == 1 and calls[0].status == "error"
    assert calls[0].reservation_id == res[0].id


def test_dispatch_without_an_enforcer_is_refused(db, config, openai_transport):
    transport = openai_transport("never", 1, 1,
                                 error=AssertionError("NETWORK WAS TOUCHED"))
    provider = _openai(db, config, transport, budget=None)
    with pytest.raises(ProviderError, match="no BudgetEnforcer"):
        provider.complete("hello", purpose="t", session_id="sess-1")
    assert transport.calls == []


def test_build_providers_requires_an_enforcer(db, config, settings):
    from app.ai.providers import build_providers

    with pytest.raises(TypeError):
        build_providers(settings, config, db)  # no budget argument at all
    with pytest.raises(ValueError, match="ADR-061"):
        build_providers(settings, config, db, None)


# ---------------------------------------------------------------------------
# safety locks: pricing failure, bound exceeded, sticky halted scopes
# ---------------------------------------------------------------------------


def test_pricing_failure_after_a_billed_call_fails_closed(
    db, config, openai_transport
):
    """kimi reports cache-hit tokens; with the cached price stripped the
    cost computation fails AFTER the money was spent. The hold must stay
    UNCERTAIN at its FULL bound (never $0), the audit row must keep the
    response (Rule 8), and a kimi/kimi-k3 safety lock must refuse the next
    dispatch until audited resolution."""
    pricing = config.pricing.model_copy(deep=True)
    entry = pricing.providers["kimi"]["kimi-k3"]
    pricing.providers["kimi"]["kimi-k3"] = entry.model_copy(
        update={"usd_per_1m_cached_input_tokens": None})
    budget = _enforcer(db, scope_id="critique-x", scope_kind="critique")
    provider = KimiProvider(
        "test-key", client=openai_transport("BILLED", 100, 10,
                                            cached_tokens=40),
        text_model="kimi-k3", vision_model="kimi-k3",
        db=db, pricing=pricing, budget=budget,
    )
    with pytest.raises(ProviderError, match="cache-READ"):
        provider.complete("hello", purpose="t", session_id="sess-1")

    with db.get_session() as s:
        res = s.execute(select(SpendReservationRow)).scalars().one()
        call = s.execute(select(AICallRow)).scalars().one()
        locks = s.execute(select(SpendSafetyLockRow)).scalars().all()
        scope = s.get(SpendScopeRow, "critique-x")
    assert res.status == "uncertain"
    assert res.settled_usd_micro is None  # counted at reserved bound
    assert call.status == "error" and call.response == "BILLED"
    assert "pricing failure" in call.error
    assert len(locks) == 1 and locks[0].status == "active"
    assert locks[0].provider == "kimi" and locks[0].model == "kimi-k3"
    assert locks[0].reason == "pricing_failure"
    assert scope.status == "halted"

    # The lock refuses the NEXT matching dispatch — from any scope.
    other = _enforcer(db, session="sess-2", scope_id="other-scope")
    with pytest.raises(SafetyLockHalt):
        other.reserve(100, provider="kimi", model="kimi-k3", kind="text",
                      attempt_no=1)
    # ...but an unlocked provider still dispatches.
    other.reserve(100, provider="openai", model="gpt-4o", kind="text",
                  attempt_no=1)

    # Audited resolution clears the lock; the scope needs ITS OWN resolution.
    lock_id = locks[0].id
    with pytest.raises(ValueError):
        resolve_safety_lock(db, lock_id, "   ")  # a reason is required
    resolve_safety_lock(db, lock_id, "prices re-verified against the console")
    other.reserve(100, provider="kimi", model="kimi-k3", kind="text",
                  attempt_no=2)
    halted = _enforcer(db, session="sess-3", scope_id="critique-x",
                       scope_kind="critique")
    with pytest.raises(ScopeHaltedHalt):
        halted.reserve(100, provider="openai", model="gpt-4o", kind="text",
                       attempt_no=1)
    resolve_halted_scope(db, "critique-x", "reviewed; ledger reconciled")
    halted.reserve(100, provider="openai", model="gpt-4o", kind="text",
                   attempt_no=1)  # closed scopes reopen; halted never did


def test_actual_above_reserved_bound_engages_the_lock(
    db, config, openai_transport
):
    """A bound-derivation defect (forced here by a doctored 1-token context
    window) must settle at the TRUE cost, record bound_exceeded, lock the
    provider/model and halt the scope — never a silent pass."""
    pricing = config.pricing.model_copy(deep=True)
    entry = pricing.providers["openai"]["gpt-4o"]
    pricing.providers["openai"]["gpt-4o"] = entry.model_copy(
        update={"context_window_tokens": 1})
    budget = _enforcer(db, scope_id="bx-scope")
    provider = OpenAIProvider(
        "test-key", client=openai_transport("BIG", 100, 50),
        text_model="gpt-4o", vision_model="gpt-4o",
        db=db, pricing=pricing, budget=budget,
    )
    resp = provider.complete("hello", purpose="t", session_id="sess-1",
                             max_tokens=1)
    assert resp.cost_usd == 0.00075  # the response still returns honestly

    with db.get_session() as s:
        res = s.execute(select(SpendReservationRow)).scalars().one()
        locks = s.execute(select(SpendSafetyLockRow)).scalars().all()
        events = s.execute(select(BudgetEventRow)).scalars().all()
        scope = s.get(SpendScopeRow, "bx-scope")
    assert res.status == "settled" and res.settled_usd_micro == 750
    assert res.settled_usd_micro > res.reserved_usd_micro
    assert len(locks) == 1 and locks[0].reason == "bound_exceeded"
    assert any(e.event_type == "bound_exceeded" for e in events)
    assert scope.status == "halted"
    # The halted scope refuses first; the lock refuses any OTHER scope too.
    with pytest.raises(ScopeHaltedHalt):
        budget.reserve(100, provider="openai", model="gpt-4o", kind="text",
                       attempt_no=1)
    with pytest.raises(SafetyLockHalt):
        _enforcer(db, session="elsewhere").reserve(
            100, provider="openai", model="gpt-4o", kind="text", attempt_no=1)


# ---------------------------------------------------------------------------
# day rollover + recovery + reconciliation
# ---------------------------------------------------------------------------


def test_the_day_a_hold_was_taken_binds(db):
    """A $20 uncertain hold from YESTERDAY consumes yesterday's budget, not
    today's; the same hold dated today refuses today's reserve."""
    ts_yesterday = "2026-08-27T23:59:00+00:00"
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute("INSERT INTO sessions (id, started_at, status, "
                     "total_cost_usd) VALUES ('s', ?, 'active', 0)",
                     (ts_yesterday,))
        conn.execute("INSERT INTO spend_scopes (id, kind, created_at, "
                     "status) VALUES ('sc-y', 'adhoc', ?, 'open')",
                     (ts_yesterday,))
        conn.execute(
            "INSERT INTO spend_reservations (id, created_at, day_utc, "
            "scope_id, session_id, attempt_no, provider, model, kind, "
            "reserved_usd_micro, status) VALUES ('r-y', ?, '2026-08-27', "
            "'sc-y', 's', 1, 'kimi', 'kimi-k3', 'text', ?, 'uncertain')",
            (ts_yesterday, usd_to_micro(20.0)),
        )
        conn.commit()
    today = _enforcer(db, run_cap=15.0, day_cap=25.0, session="s-t")
    today.reserve(usd_to_micro(10.0), provider="openai", model="gpt-4o",
                  kind="text", attempt_no=1)  # yesterday's $20 is not today's
    day = datetime.now(timezone.utc).date().isoformat()
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "UPDATE spend_reservations SET day_utc=?, created_at=? "
            "WHERE id='r-y'", (day, _now()))
        conn.commit()
    with pytest.raises(BudgetHalt) as excinfo:
        today.reserve(usd_to_micro(10.0), provider="openai", model="gpt-4o",
                      kind="text", attempt_no=2)  # now 20+10 held +10 > 25
    assert excinfo.value.cap_kind == "day"


def test_startup_recovery_classifies_dead_holds_uncertain(db):
    ts = _now()
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute("INSERT INTO sessions (id, started_at, status, "
                     "total_cost_usd) VALUES ('s', ?, 'active', 0)", (ts,))
        conn.execute("INSERT INTO spend_scopes (id, kind, created_at, "
                     "status) VALUES ('sc', 'council', ?, 'open')", (ts,))
        conn.execute(
            "INSERT INTO spend_reservations (id, created_at, day_utc, "
            "scope_id, session_id, attempt_no, provider, model, kind, "
            "reserved_usd_micro, status) VALUES ('r-dead', ?, ?, 'sc', 's', "
            "1, 'anthropic', 'claude-sonnet-4-5', 'text', 872880, 'held')",
            (ts, ts[:10]),
        )
        conn.commit()
    recovered = recover_stale_spend_holds(db)
    assert recovered == ["r-dead"]
    with db.get_session() as s:
        row = s.get(SpendReservationRow, "r-dead")
    assert row.status == "uncertain"
    assert row.ai_call_id is None  # exact-id: nothing to correlate with
    assert "may have billed" in row.note
    # still counted at the full bound — fail closed
    probe = _enforcer(db, run_cap=5.0, day_cap=25.0, session="probe")
    assert probe.spent_today_usd() == pytest.approx(0.87288)
    assert reconcile_spend_books(db) == []
    # ...and an audited operator reconciliation to the console-verified $0
    # releases the headroom without deleting anything.
    resolve_uncertain_hold(db, "r-dead", 0.0,
                           "all three consoles checked for the window")
    with db.get_session() as s:
        row = s.get(SpendReservationRow, "r-dead")
    assert row.status == "reconciled" and row.settled_usd_micro == 0
    assert "operator reconciliation" in row.note
    assert probe.spent_today_usd() == 0.0
    # An operator reconciliation is NOT a two-book mismatch: it must never
    # engage the global lock at the next startup (defect caught by the
    # gate's own §5 detail line on 2026-08-28 and fixed in-slice).
    assert reconcile_spend_books(db) == []


def test_a_nonzero_reconciliation_still_counts_against_both_caps(db):
    """A dead hold the console shows WAS billed ($0.30) must keep counting
    at $0.30 — in the day sum AND the run sum — after reconciliation, even
    though no 'ok' ai_calls row exists for it."""
    ts = _now()
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute("INSERT INTO sessions (id, started_at, status, "
                     "total_cost_usd) VALUES ('s', ?, 'active', 0)", (ts,))
        conn.execute("INSERT INTO spend_scopes (id, kind, created_at, "
                     "status) VALUES ('sc', 'council', ?, 'open')", (ts,))
        conn.execute(
            "INSERT INTO spend_reservations (id, created_at, day_utc, "
            "scope_id, session_id, attempt_no, provider, model, kind, "
            "reserved_usd_micro, status) VALUES ('r-billed', ?, ?, 'sc', "
            "'s', 1, 'openai', 'gpt-4o', 'text', 401920, 'held')",
            (ts, ts[:10]))
        conn.commit()
    recover_stale_spend_holds(db)
    resolve_uncertain_hold(db, "r-billed", 0.30, "console shows $0.30")
    probe = _enforcer(db, run_cap=5.0, day_cap=25.0, session="s",
                      scope_id="sc")
    assert probe.spent_today_usd() == pytest.approx(0.30)
    assert probe.spent_run_usd() == pytest.approx(0.30)
    assert reconcile_spend_books(db) == []
    # and it is no longer an OPEN hold: the budget page must not list it
    with db.get_session() as s:
        row = s.get(SpendReservationRow, "r-billed")
    assert row.status == "reconciled" and row.settled_usd_micro == 300_000


def test_a_tampered_ledger_engages_a_global_lock(db):
    ts = _now()
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute("INSERT INTO sessions (id, started_at, status, "
                     "total_cost_usd) VALUES ('s', ?, 'active', 0)", (ts,))
        conn.execute("INSERT INTO spend_scopes (id, kind, created_at, "
                     "status) VALUES ('sc', 'adhoc', ?, 'open')", (ts,))
        conn.execute(
            "INSERT INTO spend_reservations (id, created_at, day_utc, "
            "scope_id, session_id, attempt_no, provider, model, kind, "
            "reserved_usd_micro, settled_usd_micro, status, ai_call_id) "
            "VALUES ('r-bad', ?, ?, 'sc', 's', 1, 'openai', 'gpt-4o', "
            "'text', 100, 60, 'settled', 'no-such-call')",
            (ts, ts[:10]),
        )
        conn.commit()
    problems = reconcile_spend_books(db)
    assert problems and "no ai_call" in problems[0]
    blocked = _enforcer(db, session="s2")
    with pytest.raises(SafetyLockHalt):
        blocked.reserve(1, provider="openai", model="gpt-4o", kind="text",
                        attempt_no=1)


# ---------------------------------------------------------------------------
# spend-scope identity + lifecycle
# ---------------------------------------------------------------------------


def test_scope_ids_are_full_uuid5_never_truncated():
    sess, spec = str(uuid.uuid4()), str(uuid.uuid4())
    a = fabrication_scope_id(sess, spec)
    assert a == fabrication_scope_id(sess, spec)  # deterministic
    assert a != fabrication_scope_id(sess, str(uuid.uuid4()))
    assert len(a) == 36 and str(uuid.UUID(a)) == a
    # No truncated-prefix construction: two identities sharing 8-char
    # prefixes must still get different scopes.
    s1 = "aaaaaaaa-1111-1111-1111-111111111111"
    s2 = "aaaaaaaa-2222-2222-2222-222222222222"
    assert fabrication_scope_id(s1, spec) != fabrication_scope_id(s2, spec)
    i1 = intake_scope_id("intake-aaaaaaaa-x")
    assert i1 == intake_scope_id("intake-aaaaaaaa-x")
    assert i1 != intake_scope_id("intake-aaaaaaaa-y")


def test_fabrication_scope_accumulates_across_reposts(db):
    """Operator ruling 2026-08-28: every re-POST of the same (session,
    spec) reopens the SAME scope; the $5 pot continues."""
    scope = fabrication_scope_id("sess-A", "spec-B")
    first = _enforcer(db, run_cap=1.0, session="sess-A", scope_id=scope,
                      scope_kind="fabrication")
    first.reserve(usd_to_micro(0.6), provider="openai", model="gpt-4o",
                  kind="text", attempt_no=1)
    first.close_scope()
    with db.get_session() as s:
        assert s.get(SpendScopeRow, scope).status == "closed"
    second = _enforcer(db, run_cap=1.0, session="sess-A", scope_id=scope,
                       scope_kind="fabrication")
    with pytest.raises(BudgetHalt):  # 0.6 held + 0.6 > 1.0 — it accumulated
        second.reserve(usd_to_micro(0.6), provider="openai", model="gpt-4o",
                       kind="text", attempt_no=1)
    with db.get_session() as s:
        scope_row = s.get(SpendScopeRow, scope)
    assert scope_row.status == "open" and "reopened" in scope_row.note


def test_critique_scopes_resume_open_then_start_fresh(db):
    digest = "d" * 64
    assert latest_open_scope(db, "critique", digest) is None
    first = _enforcer(db, session="c1", scope_id=str(uuid.uuid4()),
                      scope_kind="critique", design_ref=digest)
    first.reserve(100, provider="openai", model="gpt-4o", kind="vision",
                  attempt_no=1)
    # a restart finds the OPEN scope and resumes it
    assert latest_open_scope(db, "critique", digest) == first.scope_id
    first.close_scope()
    # once closed, a new invocation gets a fresh scope — no lifetime cap
    assert latest_open_scope(db, "critique", digest) is None


def test_a_reconciled_orphan_reaches_every_operator_surface(
    db, config, openai_transport, monkeypatch
):
    """Truth model (ADR-061): total = ai_calls settled spend + reconciled
    orphan spend, non-overlapping. A $0.30 reconciled orphan must show in
    /api/ops/costs total AND /api/logs/budget, explicitly as reconciled
    unmatched spend with its ids/day/amount/note, while the normal
    ai_calls<->sessions reconciliation stays clean and nothing is counted
    twice."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api import routes_logs, routes_ops
    from app.db.database import get_default_db, reset_default_db

    monkeypatch.setenv("LUXURYFORM_DB", str(db.path))
    reset_default_db()
    try:
        # one ordinary settled call: $0.000060 in ai_calls + sessions ledger
        budget = _enforcer(db, session="sess-1", scope_id="sc-1")
        _openai(db, config, openai_transport("OK", 12, 3), budget).complete(
            "hello", purpose="t", session_id="sess-1")
        # one dead hold, recovered and reconciled to $0.30 by the operator
        ts = _now()
        with sqlite3.connect(str(db.path)) as conn:
            conn.execute(
                "INSERT INTO spend_reservations (id, created_at, day_utc, "
                "scope_id, session_id, attempt_no, provider, model, kind, "
                "reserved_usd_micro, status) VALUES ('r-orphan', ?, ?, "
                "'sc-1', 'sess-1', 2, 'openai', 'gpt-4o', 'text', 401920, "
                "'held')", (ts, ts[:10]))
            conn.commit()
        recover_stale_spend_holds(db)
        resolve_uncertain_hold(db, "r-orphan", 0.30, "console shows $0.30")

        app = FastAPI()
        app.include_router(routes_ops.router, prefix="/api")
        app.include_router(routes_logs.router, prefix="/api")
        with TestClient(app) as client:
            costs = client.get("/api/ops/costs").json()
            budget_page = client.get("/api/logs/budget").json()
    finally:
        reset_default_db()

    assert costs["ai_calls_usd"] == 0.00006
    assert costs["reconciled_usd"] == 0.3
    assert costs["total_usd"] == pytest.approx(0.30006)      # the union
    assert costs["by_day"][ts[:10]] == pytest.approx(0.30006)
    rec = costs["reconciled_unmatched_spend"]
    assert rec["count"] == 1 and rec["cost_usd"] == 0.3
    row = rec["rows"][0]
    assert row["reservation_id"] == "r-orphan"
    assert row["scope_id"] == "sc-1" and row["day_utc"] == ts[:10]
    assert row["reconciled_usd"] == 0.3 and row["reserved_usd"] == 0.40192
    assert "console shows $0.30" in row["note"]
    assert row["ai_call_id"] is None                         # no fabricated call
    # the ordinary book still reconciles: ledger 0.00006 == calls 0.00006
    assert costs["reconciliation"]["clean"] is True
    assert costs["reconciliation"]["mismatches"] == []
    assert costs["reconciliation"]["reconciled_double_counts"] == []
    assert "truth_model" in costs
    # the budget page shows it explicitly AND counts it for today's cap
    page_rows = budget_page["reconciled_unmatched_spend"]
    assert [r["reservation_id"] for r in page_rows] == ["r-orphan"]
    assert page_rows[0]["reconciled_usd"] == 0.3
    assert budget_page["spent_today_usd"] == pytest.approx(0.30006)
    assert all(h["reservation_id"] != "r-orphan"
               for h in budget_page["open_holds"])       # no longer open

    # the non-overlap guard: force the orphan onto the 'ok' call
    with db.get_session() as s:
        ok_call = s.execute(select(AICallRow).where(
            AICallRow.status == "ok")).scalars().one()
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute("UPDATE spend_reservations SET ai_call_id=NULL "
                     "WHERE ai_call_id=?", (ok_call.id,))
        conn.execute("UPDATE spend_reservations SET ai_call_id=? "
                     "WHERE id='r-orphan'", (ok_call.id,))
        conn.commit()
    problems = reconcile_spend_books(db)
    assert any("double count" in p for p in problems)


def test_max_attempts_ceiling_is_a_structural_422():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api import routes_council

    app = FastAPI()
    app.include_router(routes_council.router, prefix="/api")
    with TestClient(app) as client:
        r = client.post("/api/council/sessions/whatever/fabricate",
                        json={"max_attempts": 99})
        assert r.status_code == 422
        r = client.post("/api/council/sessions/whatever/fabricate",
                        json={"max_attempts": 0})
        assert r.status_code == 422
