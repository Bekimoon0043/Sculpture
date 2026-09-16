"""D-28 (ADR-070): the reservation bound is derived from the REAL serialized
request envelope, never from the model's whole context window.

    input_token_bound = min(context_window, utf8_bytes(request) + 256)
    bound_usd         = input_token_bound x highest input rate
                      + max_tokens        x output rate        (ceiling µUSD)

Everything here is offline and $0: injected SDK transports (conftest),
temp databases, keys scrubbed, no network. Covered, per the owner's
approval of 2026-09-14:

  * the bound for each provider is bytes + 256 (framing margin, recorded
    as a JUDGEMENT value, not first-party proof for anthropic or kimi),
    strictly below the retained ADR-061 context-window CEILING;
  * the priced envelope IS the sent envelope (field-for-field, all three
    providers) and its non-content headroom is at least 64 bytes;
  * multibyte prompts bound by UTF-8 BYTES, never characters;
  * the context window is an absolute ceiling (never exceeded);
  * vision requests stay on the ADR-061 window bound;
  * the FF-A3 halt replayed offline: the retry now fits; under the
    ceiling function the same sequence is refused;
  * retries, exhaustion and startup recovery keep every uncertain hold at
    the envelope bound with its basis persisted;
  * UNDERFLOW fails closed: billed input above the token bound, or output
    above max_tokens, engages `ceiling_violated`, halts the scope and
    refuses the next dispatch even when the DOLLAR bound still covered
    it; money above the bound still engages `bound_exceeded` first;
  * the startup census re-checks every settled text call in history and
    engages a GLOBAL lock on the first falsification;
  * the additive `bound_basis` column is patched into a pre-D-28 file and
    reaches both operator surfaces.
"""

from __future__ import annotations

import io
import json
import sqlite3
from contextlib import redirect_stdout
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.ai.call_log import envelope_bound_usd_micro, reserve_bound_usd_micro
from app.ai.provider import ProviderError, request_envelope_bytes
from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.kimi_provider import KimiProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.budget import (
    ENVELOPE_FORMULA,
    FRAMING_MARGIN_TOKENS,
    PRE_D28_FORMULA,
    VISION_FORMULA,
    BudgetEnforcer,
    BudgetHalt,
    SafetyLockHalt,
    ScopeHaltedHalt,
    envelope_census,
    micro_to_usd,
    reconcile_spend_books,
    recover_stale_spend_holds,
)
from app.db.models import (
    AICallRow,
    BudgetEventRow,
    SpendReservationRow,
    SpendSafetyLockRow,
    SpendScopeRow,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "council_session_ffa3_v1.json"

MODELS = {"anthropic": "claude-sonnet-4-5", "openai": "gpt-4o", "kimi": "kimi-k3"}
CLASSES = {"anthropic": AnthropicProvider, "openai": OpenAIProvider,
           "kimi": KimiProvider}
TEMPERATURE = {"anthropic": 0.0, "openai": 0.0, "kimi": None}
PROVIDERS = sorted(MODELS)

MICRO = Decimal("0.000001")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enforcer(db, run_cap=5.0, day_cap=25.0, session="sess-1", **kw):
    return BudgetEnforcer(session, run_cap, day_cap, db, **kw)


def _provider(name, db, config, transport, budget, pricing=None):
    model = MODELS[name]
    return CLASSES[name](
        "test-key", client=transport, text_model=model, vision_model=model,
        db=db, pricing=pricing or config.pricing, budget=budget,
        default_temperature=TEMPERATURE[name],
    )


def _transport(name, openai_transport, anthropic_transport, text="OK",
               tin=12, tout=3, **kw):
    if name == "anthropic":
        return anthropic_transport(text, tin, tout, **kw)
    return openai_transport(text, tin, tout, **kw)


def _expected_micro(entry, input_tokens: int, max_tokens: int) -> int:
    """Independent re-derivation of the bound (Decimal, ceiling)."""
    rate_in = Decimal(str(entry.usd_per_1m_input_tokens))
    if entry.usd_per_1m_cache_write_input_tokens is not None:
        rate_in = max(rate_in,
                      Decimal(str(entry.usd_per_1m_cache_write_input_tokens)))
    rate_out = Decimal(str(entry.usd_per_1m_output_tokens))
    usd = (Decimal(input_tokens) * rate_in
           + Decimal(max_tokens) * rate_out) / Decimal(1_000_000)
    return int(usd.quantize(MICRO, rounding=ROUND_CEILING) / MICRO)


def _ffa3_kimi_prompt() -> str:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return next(c["prompt"] for c in fx["calls"]
                if c["provider"] == "kimi" and c["role"] == "researcher")


class _Flaky:
    """openai-shaped transport that fails the first N calls transiently."""

    def __init__(self, inner, failures: int) -> None:
        from types import SimpleNamespace

        self._inner = inner
        self._failures = failures
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= self._failures:
            raise ConnectionError("Connection error.")
        return self._inner._create(**kwargs)


# ---------------------------------------------------------------------------
# the derivation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", PROVIDERS)
def test_envelope_bound_is_request_bytes_plus_margin_below_the_ceiling(
    name, db, config, openai_transport, anthropic_transport
):
    p = _provider(name, db, config,
                  _transport(name, openai_transport, anthropic_transport),
                  _enforcer(db))
    model = MODELS[name]
    request = p._build_text_request("hello", model, 8192, TEMPERATURE[name])
    nbytes = request_envelope_bytes(request)
    micro, basis = envelope_bound_usd_micro(
        config.pricing, name, model, "text", request, 8192)
    entry = config.pricing.price_for(name, model)

    assert basis["formula"] == ENVELOPE_FORMULA
    assert basis["kind"] == "text"
    assert basis["envelope_utf8_bytes"] == nbytes
    assert basis["framing_margin_tokens"] == FRAMING_MARGIN_TOKENS == 256
    assert "judgement" in basis["framing_margin_status"]
    assert "not first-party proof for anthropic or kimi" in basis[
        "framing_margin_status"]
    assert basis["context_window_tokens"] == entry.context_window_tokens
    assert basis["input_tokens_bound"] == nbytes + 256
    assert basis["ceiling_applied"] is False
    assert basis["max_tokens"] == 8192
    assert micro == _expected_micro(entry, nbytes + 256, 8192)
    ceiling = reserve_bound_usd_micro(config.pricing, name, model, 8192)
    assert micro < ceiling
    # the ceiling function is unchanged (ADR-061 values retained exactly)
    assert ceiling == {"anthropic": 872_880, "openai": 401_920,
                       "kimi": 3_268_608}[name]


def test_the_ffa3_kimi_hold_would_have_been_cents_not_dollars(db, config,
                                                             openai_transport):
    """The reservation that halted the live session (2026-09-14) was taken
    for a 2,05x-byte prompt at the $3.268608 window bound. Under the
    envelope bound the same request holds under $0.20 and a retry fits."""
    prompt = _ffa3_kimi_prompt()
    p = _provider("kimi", db, config, openai_transport("OK", 1, 1),
                  _enforcer(db))
    request = p._build_text_request(prompt, "kimi-k3", 8192, None)
    micro, basis = envelope_bound_usd_micro(
        config.pricing, "kimi", "kimi-k3", "text", request, 8192)
    entry = config.pricing.price_for("kimi", "kimi-k3")
    assert 2000 < len(prompt.encode("utf-8")) < 2200
    assert micro == _expected_micro(entry, basis["input_tokens_bound"], 8192)
    assert micro < 200_000                       # under $0.20
    assert reserve_bound_usd_micro(config.pricing, "kimi", "kimi-k3",
                                   8192) == 3_268_608
    # an uncertain hold at this bound plus a retry's hold fit under $5
    assert 2 * micro < 5_000_000


def test_multibyte_prompts_bound_by_utf8_bytes_not_characters(db, config,
                                                              openai_transport):
    p = _provider("openai", db, config, openai_transport("OK", 1, 1),
                  _enforcer(db))
    cjk = "警告" * 4000          # 8,000 characters, 24,000 UTF-8 bytes
    ascii_ = "ab" * 4000         # 8,000 characters, 8,000 bytes
    emoji = "😀" * 1000          # 1,000 characters, 4,000 bytes
    bounds = {}
    for label, text in (("cjk", cjk), ("ascii", ascii_), ("emoji", emoji)):
        req = p._build_text_request(text, "gpt-4o", 256, 0.0)
        _, basis = envelope_bound_usd_micro(
            config.pricing, "openai", "gpt-4o", "text", req, 256)
        bounds[label] = basis["input_tokens_bound"]
    assert len(cjk) == len(ascii_) == 8000
    assert bounds["cjk"] >= 24_000 + 256
    assert bounds["ascii"] >= 8_000 + 256
    assert bounds["ascii"] < bounds["cjk"]        # a char bound would tie
    assert bounds["emoji"] >= 4_000 + 256


def test_context_window_is_an_absolute_ceiling(db, config, openai_transport):
    p = _provider("openai", db, config, openai_transport("OK", 1, 1),
                  _enforcer(db))
    req = p._build_text_request("x" * 130_000, "gpt-4o", 8192, 0.0)
    micro, basis = envelope_bound_usd_micro(
        config.pricing, "openai", "gpt-4o", "text", req, 8192)
    assert basis["envelope_utf8_bytes"] > 128_000
    assert basis["input_tokens_bound"] == 128_000
    assert basis["ceiling_applied"] is True
    assert micro == reserve_bound_usd_micro(config.pricing, "openai",
                                            "gpt-4o", 8192) == 401_920


def test_vision_requests_stay_on_the_window_ceiling(db, config,
                                                     anthropic_transport,
                                                     test_image):
    p = _provider("anthropic", db, config, anthropic_transport("OK", 1, 1),
                  _enforcer(db))
    req = p._build_vision_request("describe", test_image,
                                  "claude-sonnet-4-5", 256)
    micro, basis = envelope_bound_usd_micro(
        config.pricing, "anthropic", "claude-sonnet-4-5", "vision", req, 256)
    assert micro == reserve_bound_usd_micro(config.pricing, "anthropic",
                                            "claude-sonnet-4-5", 256)
    assert basis["formula"] == VISION_FORMULA
    assert basis["kind"] == "vision"
    assert basis["input_tokens_bound"] == 200_000
    assert basis["ceiling_applied"] is True
    assert basis["envelope_utf8_bytes"] > 0     # still recorded, never used


def test_bound_needs_a_first_party_context_window_still(db, config,
                                                        openai_transport):
    from app.core.config import PricingLookupError

    pricing = config.pricing.model_copy(deep=True)
    entry = pricing.providers["openai"]["gpt-4o"]
    pricing.providers["openai"]["gpt-4o"] = entry.model_copy(
        update={"context_window_tokens": None})
    with pytest.raises(PricingLookupError, match="context_window_tokens"):
        envelope_bound_usd_micro(pricing, "openai", "gpt-4o", "text",
                                 {"model": "gpt-4o"}, 10)


# ---------------------------------------------------------------------------
# the priced envelope IS the sent envelope
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", PROVIDERS)
def test_the_priced_envelope_is_the_sent_envelope(
    name, db, config, openai_transport, anthropic_transport
):
    transport = _transport(name, openai_transport, anthropic_transport)
    p = _provider(name, db, config, transport, _enforcer(db))
    prompt = "hello ✓ — envelope"
    p.complete(prompt, purpose="t", session_id="sess-1", max_tokens=300)
    assert len(transport.calls) == 1
    sent = transport.calls[0]
    built = p._build_text_request(prompt, MODELS[name], 300, TEMPERATURE[name])
    assert sent == built                                   # field for field
    with db.get_session() as s:
        row = s.execute(select(SpendReservationRow)).scalars().one()
    basis = json.loads(row.bound_basis)
    assert basis["envelope_utf8_bytes"] == request_envelope_bytes(sent)
    expected, _ = envelope_bound_usd_micro(
        config.pricing, name, MODELS[name], "text", sent, 300)
    assert row.reserved_usd_micro == expected
    assert row.status == "settled"


@pytest.mark.parametrize("name", PROVIDERS)
def test_non_content_headroom_is_at_least_64_bytes(
    name, db, config, openai_transport, anthropic_transport
):
    p = _provider(name, db, config,
                  _transport(name, openai_transport, anthropic_transport),
                  _enforcer(db))
    prompt = "Reply with exactly: OK"
    req = p._build_text_request(prompt, MODELS[name], 8192, TEMPERATURE[name])
    headroom = request_envelope_bytes(req) - len(prompt.encode("utf-8"))
    assert headroom >= 64, headroom


# ---------------------------------------------------------------------------
# retries, uncertain holds, the FF-A3 halt replayed
# ---------------------------------------------------------------------------


def test_the_ffa3_halt_replays_offline_and_now_survives(
    db, config, openai_transport, monkeypatch
):
    """Run cap $5.00, one transient kimi failure, then success. The
    uncertain hold stays counted at ITS bound and the ADR-023 retry FITS.
    The identical sequence under the ADR-061 ceiling is REFUSED — the
    measured 2026-09-14 halt."""
    monkeypatch.setenv("LUXURYFORM_PROVIDER_BACKOFF_BASE_S", "0")
    prompt = _ffa3_kimi_prompt()
    flaky = _Flaky(openai_transport("OK", 512, 104), failures=1)
    budget = _enforcer(db, scope_id="council-replay", scope_kind="council")
    p = _provider("kimi", db, config, flaky, budget)
    resp = p.complete(prompt, purpose="council_researcher",
                      session_id="sess-1", max_tokens=8192)
    assert resp.text == "OK"
    with db.get_session() as s:
        res = s.execute(select(SpendReservationRow).order_by(
            SpendReservationRow.attempt_no)).scalars().all()
    assert [r.status for r in res] == ["uncertain", "settled"]
    assert res[0].reserved_usd_micro == res[1].reserved_usd_micro < 200_000
    assert json.loads(res[0].bound_basis)["formula"] == ENVELOPE_FORMULA
    assert budget.spent_run_usd() == pytest.approx(
        micro_to_usd(res[0].reserved_usd_micro) + resp.cost_usd)
    assert budget.spent_run_usd() < 0.5

    # counterfactual: the same two holds at the ADR-061 ceiling
    ceiling = reserve_bound_usd_micro(config.pricing, "kimi", "kimi-k3", 8192)
    old = _enforcer(db, session="sess-old", scope_id="council-old")
    rid = old.reserve(ceiling, provider="kimi", model="kimi-k3", kind="text",
                      attempt_no=1)
    old.record_failed_attempt(
        rid, ts=_now(), provider="kimi", model="kimi-k3",
        purpose="council_researcher", prompt=prompt, response="",
        tokens_in=0, tokens_out=0, cached_input_tokens=0,
        cache_write_input_tokens=0, latency_ms=1.0,
        pricing_version=config.pricing.pricing_version,
        error="Connection error.")
    with pytest.raises(BudgetHalt) as halt:
        old.reserve(ceiling, provider="kimi", model="kimi-k3", kind="text",
                    attempt_no=2)
    assert halt.value.cap_kind == "run"
    assert halt.value.spent_usd == pytest.approx(3.268608)


def test_exhausted_attempts_hold_three_envelope_bounds(
    db, config, openai_transport, monkeypatch
):
    monkeypatch.setenv("LUXURYFORM_PROVIDER_BACKOFF_BASE_S", "0")
    flaky = _Flaky(openai_transport("never", 1, 1), failures=99)
    budget = _enforcer(db)
    p = _provider("kimi", db, config, flaky, budget)
    with pytest.raises(ProviderError, match="Connection error"):
        p.complete("hello", purpose="t", session_id="sess-1", max_tokens=8192)
    with db.get_session() as s:
        res = s.execute(select(SpendReservationRow)).scalars().all()
    assert len(res) == 3 and all(r.status == "uncertain" for r in res)
    expected, _ = envelope_bound_usd_micro(
        config.pricing, "kimi", "kimi-k3", "text", flaky.calls[0], 8192)
    assert all(r.reserved_usd_micro == expected for r in res)
    assert all(r.bound_basis for r in res)
    assert budget.spent_run_usd() == pytest.approx(3 * micro_to_usd(expected))


def test_startup_recovery_keeps_the_envelope_bound_and_its_basis(db, config):
    budget = _enforcer(db, scope_id="sc-dead")
    basis = {"formula": ENVELOPE_FORMULA, "input_tokens_bound": 400,
             "max_tokens": 256, "kind": "text",
             "framing_margin_tokens": FRAMING_MARGIN_TOKENS}
    rid = budget.reserve(3_560, provider="openai", model="gpt-4o",
                         kind="text", attempt_no=1, bound_basis=basis)
    assert recover_stale_spend_holds(db) == [rid]
    with db.get_session() as s:
        row = s.get(SpendReservationRow, rid)
    assert row.status == "uncertain"
    assert row.reserved_usd_micro == 3_560
    assert json.loads(row.bound_basis) == basis
    assert budget.spent_today_usd() == pytest.approx(0.00356)
    assert reconcile_spend_books(db) == []


# ---------------------------------------------------------------------------
# underflow fails closed
# ---------------------------------------------------------------------------


def test_billed_input_above_the_token_bound_locks_the_provider(
    db, config, openai_transport
):
    """Tokens over the bound while the DOLLARS still fit (output unused):
    the derivation is falsified, so the provider/model locks and the scope
    halts at settlement — never a silent absorb."""
    probe = _provider("openai", db, config, openai_transport("x", 1, 1),
                      _enforcer(db, session="probe"))
    req = probe._build_text_request("hello", "gpt-4o", 256, 0.0)
    bound_tokens = request_envelope_bytes(req) + FRAMING_MARGIN_TOKENS
    transport = openai_transport("OK", bound_tokens + 1, 0)
    budget = _enforcer(db, scope_id="viol-in")
    p = _provider("openai", db, config, transport, budget)
    resp = p.complete("hello", purpose="t", session_id="sess-1",
                      max_tokens=256)
    with db.get_session() as s:
        res = s.execute(select(SpendReservationRow)).scalars().one()
        locks = s.execute(select(SpendSafetyLockRow)).scalars().all()
        events = s.execute(select(BudgetEventRow)).scalars().all()
        scope = s.get(SpendScopeRow, "viol-in")
    assert res.status == "settled"
    assert res.settled_usd_micro < res.reserved_usd_micro      # money fit
    assert resp.cost_usd == micro_to_usd(res.settled_usd_micro)
    assert len(locks) == 1 and locks[0].reason == "ceiling_violated"
    assert locks[0].provider == "openai" and locks[0].model == "gpt-4o"
    detail = json.loads(locks[0].detail)
    assert detail["billed_input_tokens"] == bound_tokens + 1
    assert detail["input_tokens_bound"] == bound_tokens
    assert any(e.event_type == "ceiling_violated" for e in events)
    assert scope.status == "halted"
    with pytest.raises(ScopeHaltedHalt):
        budget.reserve(1, provider="openai", model="gpt-4o", kind="text",
                       attempt_no=1)
    with pytest.raises(SafetyLockHalt):
        _enforcer(db, session="elsewhere").reserve(
            1, provider="openai", model="gpt-4o", kind="text", attempt_no=1)


def test_output_above_max_tokens_locks_the_provider(db, config,
                                                    openai_transport):
    transport = openai_transport("OK", 1, 257)
    budget = _enforcer(db, scope_id="viol-out")
    p = _provider("openai", db, config, transport, budget)
    p.complete("hello", purpose="t", session_id="sess-1", max_tokens=256)
    with db.get_session() as s:
        res = s.execute(select(SpendReservationRow)).scalars().one()
        locks = s.execute(select(SpendSafetyLockRow)).scalars().all()
        scope = s.get(SpendScopeRow, "viol-out")
    assert res.settled_usd_micro < res.reserved_usd_micro      # money fit
    assert len(locks) == 1 and locks[0].reason == "ceiling_violated"
    detail = json.loads(locks[0].detail)
    assert detail["tokens_out"] == 257 and detail["max_tokens"] == 256
    assert scope.status == "halted"


def test_money_above_the_bound_still_wins_with_one_bound_exceeded_lock(
    db, config, openai_transport
):
    pricing = config.pricing.model_copy(deep=True)
    entry = pricing.providers["openai"]["gpt-4o"]
    pricing.providers["openai"]["gpt-4o"] = entry.model_copy(
        update={"context_window_tokens": 1})
    budget = _enforcer(db, scope_id="bx")
    p = _provider("openai", db, config, openai_transport("BIG", 100, 50),
                  budget, pricing=pricing)
    p.complete("hello", purpose="t", session_id="sess-1", max_tokens=1)
    with db.get_session() as s:
        res = s.execute(select(SpendReservationRow)).scalars().one()
        locks = s.execute(select(SpendSafetyLockRow)).scalars().all()
    assert json.loads(res.bound_basis)["input_tokens_bound"] == 1
    assert res.settled_usd_micro > res.reserved_usd_micro
    assert [lk.reason for lk in locks] == ["bound_exceeded"]


# ---------------------------------------------------------------------------
# the census: history re-checked at every startup
# ---------------------------------------------------------------------------


def _insert_ok_call(db, *, call_id, purpose, prompt, tokens_in,
                    reservation_id=None, provider="openai", model="gpt-4o"):
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, started_at, status, "
            "total_cost_usd) VALUES ('sess-1', ?, 'active', 0)", (_now(),))
        conn.execute(
            "INSERT INTO ai_calls (id, session_id, ts, provider, model, "
            "purpose, prompt, response, tokens_in, tokens_out, "
            "cached_input_tokens, cache_write_input_tokens, latency_ms, "
            "cost_usd, pricing_version, status, error, reservation_id) "
            "VALUES (?, 'sess-1', ?, ?, ?, ?, ?, 'r', ?, 1, 0, 0, 1.0, "
            "0.0001, 'v', 'ok', NULL, ?)",
            (call_id, _now(), provider, model, purpose, prompt, tokens_in,
             reservation_id))
        conn.commit()


def test_census_reports_history_and_locks_on_a_falsified_assumption(
    db, config, openai_transport
):
    budget = _enforcer(db, scope_id="sc-c")
    p = _provider("openai", db, config, openai_transport("OK", 12, 3), budget)
    # 19 prompt bytes for 12 billed tokens — real tokenizers bill well under
    # one token per byte, so the ratio must be strictly below 1.
    p.complete("hello census census", purpose="t", session_id="sess-1")
    report = envelope_census(db)
    assert report["framing_margin_tokens"] == 256
    assert report["text_calls"] == 1 and report["violations"] == []
    stats = report["per_model"]["openai/gpt-4o"]
    assert stats["calls"] == 1
    assert 0 < stats["worst_tokens_per_prompt_byte"] < 1
    assert stats["worst_headroom_tokens"] > 0

    # a vision row with absurd input tokens is out of scope (skipped)
    _insert_ok_call(db, call_id="c-vision", purpose="council_vision_critique",
                    prompt="look", tokens_in=999_999)
    report = envelope_census(db)
    assert report["vision_skipped"] == 1 and report["violations"] == []
    assert reconcile_spend_books(db) == []

    # a text row billed above prompt bytes + margin falsifies the assumption
    prompt = "short"
    _insert_ok_call(db, call_id="c-bad", purpose="council_engineer",
                    prompt=prompt,
                    tokens_in=len(prompt.encode()) + FRAMING_MARGIN_TOKENS + 1)
    report = envelope_census(db)
    assert len(report["violations"]) == 1
    v = report["violations"][0]
    assert v["ai_call_id"] == "c-bad" and v["basis"] == PRE_D28_FORMULA
    assert v["billed_input_tokens"] == v["input_tokens_bound"] + 1
    problems = reconcile_spend_books(db)
    assert any("ceiling violated" in pr and "c-bad" in pr for pr in problems)
    with db.get_session() as s:
        locks = s.execute(select(SpendSafetyLockRow).where(
            SpendSafetyLockRow.status == "active")).scalars().all()
    assert [lk.reason for lk in locks] == ["ceiling_violated"]
    assert locks[0].provider is None                       # GLOBAL
    with pytest.raises(SafetyLockHalt):
        _enforcer(db, session="s2").reserve(
            1, provider="kimi", model="kimi-k3", kind="text", attempt_no=1)


def test_pre_d28_rows_are_measured_against_prompt_bytes_plus_margin(db):
    ts = _now()
    prompt = "an old prompt"
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute("INSERT INTO sessions (id, started_at, status, "
                     "total_cost_usd) VALUES ('sess-1', ?, 'active', 0)", (ts,))
        conn.execute("INSERT INTO spend_scopes (id, kind, created_at, "
                     "status) VALUES ('sc', 'council', ?, 'open')", (ts,))
        conn.execute(
            "INSERT INTO spend_reservations (id, created_at, day_utc, "
            "scope_id, session_id, attempt_no, provider, model, kind, "
            "reserved_usd_micro, settled_usd_micro, status, ai_call_id) "
            "VALUES ('r-old', ?, ?, 'sc', 'sess-1', 1, 'kimi', 'kimi-k3', "
            "'text', 3268608, 100, 'settled', 'c-old')", (ts, ts[:10]))
        conn.commit()
    _insert_ok_call(db, call_id="c-old", purpose="council_critic",
                    prompt=prompt, tokens_in=len(prompt.encode()) + 256,
                    reservation_id="r-old", provider="kimi", model="kimi-k3")
    with sqlite3.connect(str(db.path)) as conn:   # settled == cost (100µ)
        conn.execute("UPDATE ai_calls SET cost_usd=0.0001 WHERE id='c-old'")
        conn.commit()
    report = envelope_census(db)
    assert report["violations"] == []
    assert report["per_model"]["kimi/kimi-k3"]["pre_d28_rows"] == 1
    assert reconcile_spend_books(db) == []


# ---------------------------------------------------------------------------
# schema patch + operator surfaces + the read-only admin command
# ---------------------------------------------------------------------------


def test_bound_basis_is_patched_into_a_pre_d28_file(tmp_path):
    from app.db.database import Database

    if sqlite3.sqlite_version_info < (3, 35, 0):
        pytest.skip("DROP COLUMN needs SQLite >= 3.35")
    path = tmp_path / "old.db"
    Database(path).init_db()
    with sqlite3.connect(str(path)) as conn:
        conn.execute("ALTER TABLE spend_reservations DROP COLUMN bound_basis")
        conn.commit()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(spend_reservations)")}
    assert "bound_basis" not in cols
    Database(path).init_db()                   # the startup patch
    with sqlite3.connect(str(path)) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(spend_reservations)")}
        patched = conn.execute(
            "SELECT 1 FROM schema_patches WHERE table_name='spend_reservations' "
            "AND column_name='bound_basis'").fetchone()
    assert "bound_basis" in cols and patched is not None


def test_both_operator_surfaces_expose_the_basis(
    db, config, openai_transport, monkeypatch
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api import routes_logs, routes_ops
    from app.db.database import get_default_db, reset_default_db

    monkeypatch.setenv("LUXURYFORM_PROVIDER_BACKOFF_BASE_S", "0")
    monkeypatch.setenv("LUXURYFORM_DB", str(db.path))
    reset_default_db()
    try:
        # an exhausted call leaves an UNCERTAIN hold with a real basis
        flaky = _Flaky(openai_transport("never", 1, 1), failures=99)
        p = _provider("kimi", db, config, flaky,
                      _enforcer(db, scope_id="sc-1"))
        with pytest.raises(ProviderError):
            p.complete("hello", purpose="t", session_id="sess-1")
        # a pre-D-28 style hold (no basis), recovered and reconciled
        ts = _now()
        with sqlite3.connect(str(db.path)) as conn:
            conn.execute(
                "INSERT INTO spend_reservations (id, created_at, day_utc, "
                "scope_id, session_id, attempt_no, provider, model, kind, "
                "reserved_usd_micro, status) VALUES ('r-orphan', ?, ?, "
                "'sc-1', 'sess-1', 9, 'kimi', 'kimi-k3', 'text', 3268608, "
                "'held')", (ts, ts[:10]))
            conn.commit()
        from app.core.budget import resolve_uncertain_hold

        recover_stale_spend_holds(db)
        resolve_uncertain_hold(db, "r-orphan", 0.0, "console: not billed")

        app = FastAPI()
        app.include_router(routes_ops.router, prefix="/api")
        app.include_router(routes_logs.router, prefix="/api")
        with TestClient(app) as client:
            page = client.get("/api/logs/budget").json()
            costs = client.get("/api/ops/costs").json()
    finally:
        reset_default_db()

    holds = page["open_holds"]
    assert len(holds) == 3 and all(h["status"] == "uncertain" for h in holds)
    for h in holds:
        assert h["bound_basis"]["formula"] == ENVELOPE_FORMULA
        assert h["bound_basis"]["framing_margin_tokens"] == 256
        assert h["reserved_usd"] < 0.2
    rec = page["reconciled_unmatched_spend"][0]
    assert rec["reservation_id"] == "r-orphan"
    assert rec["bound_basis"]["formula"] == PRE_D28_FORMULA
    assert rec["reserved_usd"] == 3.268608
    rows = costs["reconciled_unmatched_spend"]["rows"]
    assert rows[0]["bound_basis"]["formula"] == PRE_D28_FORMULA


def test_spend_admin_census_is_read_only(db, config, openai_transport):
    import hashlib
    import sys

    sys.path.insert(0, str(REPO / "scripts"))
    from spend_admin import cmd_census

    p = _provider("anthropic", db, config,
                  openai_transport("OK", 1, 1), _enforcer(db))  # unused
    q = _provider("openai", db, config, openai_transport("OK", 12, 3),
                  _enforcer(db, scope_id="sc-a"))
    q.complete("hello", purpose="t", session_id="sess-1")
    del p
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = hashlib.sha256(db.path.read_bytes()).hexdigest()
    out = io.StringIO()
    with redirect_stdout(out):
        rc = cmd_census(db)
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    after = hashlib.sha256(db.path.read_bytes()).hexdigest()
    text = out.getvalue()
    assert rc == 0 and before == after
    assert "openai/gpt-4o" in text and "violations: 0" in text
    assert "framing margin 256" in text
