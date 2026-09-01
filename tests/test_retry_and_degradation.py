"""Retry + degraded-session tests (ADR-023, 2026-08-07).

Defects from the operator's first live session: a single kimi timeout
(220 s — actually 3 hidden SDK-internal attempts) killed a whole 15-call
session on a slow line. Fixes proven here:

  1. TRANSIENT failures (timeout/connection) are retried with backoff —
     every attempt audited, SDK-internal retries disabled;
  2. non-transient errors are NEVER retried;
  3. a failed NON-CRITICAL Council call degrades the session (degraded=1,
     error row persisted) instead of aborting it; BudgetHalt is never
     degraded — it always halts.

Backoff base is set to 0 in every retry test so the suite stays fast.
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.ai.provider import ProviderError
from app.ai.providers.kimi_provider import KimiProvider
from app.core.budget import BudgetEnforcer, BudgetHalt
from app.council.orchestrator import CouncilOrchestrator
from app.db.models import (
    CouncilCallRow,
    CouncilSessionRow,
    EngineeringReviewRow,
    AICallRow,
)
from tests.test_council_orchestrator import (
    MODELS,
    ScriptedDispatcher,
    _arbiter_decision_json,
)


# --- 1-2. provider-layer retry ----------------------------------------------

class FlakyTimeoutTransport:
    """OpenAI-shape transport that raises TimeoutError `fail_times` times,
    then succeeds. TimeoutError is the built-in — transient by class name."""

    def __init__(self, text: str, fail_times: int) -> None:
        from types import SimpleNamespace

        self.calls: list[dict] = []
        self._fail_left = fail_times
        self._response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
            usage=SimpleNamespace(
                prompt_tokens=100, completion_tokens=10, total_tokens=110,
                cached_tokens=0,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0),
                completion_tokens_details=SimpleNamespace(),
            ),
        )
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._fail_left > 0:
            self._fail_left -= 1
            raise TimeoutError("Request timed out.")
        return self._response


def _kimi(db, config, client):
    models = config.council.model_defaults["kimi"]
    # ADR-061: every physical attempt reserves kimi's context-window bound
    # ($3.149568 at 256 output tokens) and a FAILED attempt stays counted
    # (uncertain, fail closed) — so three attempts need ~$9.45 of headroom.
    # These tests exercise RETRY mechanics; the cap mechanics have their
    # own suite (test_spend_reservations.py), so the run cap here is 25.
    budget = BudgetEnforcer("retry-test", 25.0, 25.0, db)
    return KimiProvider(
        "test-key-not-real",
        client=client,
        text_model=models.text,
        vision_model=models.vision_or_text(),
        default_temperature=models.temperature,
        db=db,
        pricing=config.pricing,
        budget=budget,
    )


def test_transient_timeout_retried_then_succeeds(db, config, monkeypatch):
    monkeypatch.setenv("LUXURYFORM_PROVIDER_BACKOFF_BASE_S", "0")
    client = FlakyTimeoutTransport("OK", fail_times=2)
    provider = _kimi(db, config, client)

    resp = provider.complete("brief", purpose="test", session_id="retry-1")

    assert resp.text == "OK"
    assert len(client.calls) == 3  # two timeouts, third succeeds
    with db.get_session() as s:
        rows = s.query(AICallRow).all()
    # ADR-061: EVERY physical attempt is audited with its own row (the old
    # contract discarded the transient history on success) — two error
    # rows for the timeouts, one ok row for the success.
    assert len(rows) == 3
    assert sorted(r.status for r in rows) == ["error", "error", "ok"]
    assert all(r.reservation_id for r in rows)


def test_persistent_timeout_exhausts_attempts_with_audit(db, config, monkeypatch):
    monkeypatch.setenv("LUXURYFORM_PROVIDER_BACKOFF_BASE_S", "0")
    client = FlakyTimeoutTransport("OK", fail_times=99)
    provider = _kimi(db, config, client)

    with pytest.raises(ProviderError, match="Request timed out"):
        provider.complete("brief", purpose="test", session_id="retry-2")

    assert len(client.calls) == 3  # default max attempts
    with db.get_session() as s:
        rows = s.query(AICallRow).all()
    # One audited row PER attempt (ADR-061). Later attempts carry the
    # history accumulated so far, so exactly ONE row (the last) names
    # attempt 2/3, and it names attempt 1/3 too — the full trail survives.
    assert len(rows) == 3
    assert all(r.status == "error" for r in rows)
    final = [r for r in rows if "attempt 2/3" in (r.error or "")]
    assert len(final) == 1
    assert "retry history" in final[0].error
    assert "attempt 1/3" in final[0].error


def test_non_transient_error_never_retried(db, config, monkeypatch):
    monkeypatch.setenv("LUXURYFORM_PROVIDER_BACKOFF_BASE_S", "0")
    client = FlakyTimeoutTransport("OK", fail_times=0)
    # swap in a non-transient permanent failure
    def boom(**kwargs):
        client.calls.append(kwargs)
        raise RuntimeError("400: invalid request")
    client.chat.completions.create = boom
    provider = _kimi(db, config, client)

    with pytest.raises(ProviderError, match="400"):
        provider.complete("brief", purpose="test", session_id="retry-3")

    assert len(client.calls) == 1  # no retry on a 4xx-class error
    with db.get_session() as s:
        row = s.query(AICallRow).one()
    assert "retry history" not in (row.error or "")


def test_attempts_configurable_via_env(db, config, monkeypatch):
    monkeypatch.setenv("LUXURYFORM_PROVIDER_BACKOFF_BASE_S", "0")
    monkeypatch.setenv("LUXURYFORM_PROVIDER_MAX_ATTEMPTS", "1")
    client = FlakyTimeoutTransport("OK", fail_times=1)
    provider = _kimi(db, config, client)

    with pytest.raises(ProviderError):
        provider.complete("brief", purpose="test", session_id="retry-4")
    assert len(client.calls) == 1  # retries disabled by config


# --- 3. orchestrator degraded-continue --------------------------------------

class OutageDispatcher(ScriptedDispatcher):
    """Fails every call whose (role, side) is in fail_on."""

    def __init__(self, pricing, base_spec, fail_on: set, db=None):
        super().__init__(pricing, base_spec)
        self._fail_on = fail_on
        self._db = db

    def dispatch(self, *, role, side, provider, prompt, session_id, max_tokens):
        if (role, side) in self._fail_on:
            self.calls.append({"role": role, "side": side, "provider": provider})
            raise RuntimeError(f"scripted outage at {role}/{side}")
        if role == "arbiter" and side == "primary":
            from app.db.models import DesignSpecRow
            from app.council.orchestrator import DispatchOutcome
            with self._db.get_session() as s:
                ids = [r.id for r in s.query(DesignSpecRow).all()]
            return DispatchOutcome(
                provider=provider, model=MODELS[provider],
                text=_arbiter_decision_json(ids), tokens_in=2000, tokens_out=900,
                latency_ms=100.0,
                cost_usd=self._pricing.cost_usd(provider, MODELS[provider],
                                                2000, 900),
                pricing_version=self._pricing.pricing_version)
        return super().dispatch(role=role, side=side, provider=provider,
                                prompt=prompt, session_id=session_id,
                                max_tokens=max_tokens)


@pytest.fixture()
def base_spec(repo_root):
    from tests.test_design_spec_schema import valid_example_spec
    return valid_example_spec()


def test_full_researcher_outage_degrades_not_aborts(db, config, base_spec):
    d = OutageDispatcher(config.pricing, base_spec,
                         {("researcher", "primary"), ("researcher", "parallel")},
                         db=db)
    orch = CouncilOrchestrator(db, config.pricing, d, config.council)
    sid = orch.run_session("brief with a dead researcher (scripted)")

    with db.get_session() as s:
        sess = s.get(CouncilSessionRow, sid)
        assert sess.status == "completed"   # degraded, not aborted
        assert sess.degraded == 1
        errors = [c for c in s.query(CouncilCallRow).filter_by(session_id=sid)
                  if c.status == "error"]
        assert len(errors) == 2             # both researcher calls audited
        assert {c.role for c in errors} == {"researcher"}
        # designers were told, honestly, that research was unavailable
        designer_call = [c for c in s.query(CouncilCallRow)
                         .filter_by(session_id=sid) if c.role == "designer"][0]
        assert "researcher unavailable" in designer_call.prompt


def test_engineer_parallel_outage_degrades_keeps_primary(db, config, base_spec):
    d = OutageDispatcher(config.pricing, base_spec,
                         {("engineer", "parallel")}, db=db)
    orch = CouncilOrchestrator(db, config.pricing, d, config.council)
    sid = orch.run_session("brief with a flaky parallel engineer (scripted)")

    with db.get_session() as s:
        sess = s.get(CouncilSessionRow, sid)
        assert sess.status == "completed"
        assert sess.degraded == 1
        reviews = s.query(EngineeringReviewRow).filter_by(session_id=sid).all()
        assert len(reviews) == 1            # only the primary review persisted
        assert reviews[0].side == "primary"
        errors = [c for c in s.query(CouncilCallRow).filter_by(session_id=sid)
                  if c.status == "error"]
        assert len(errors) == 1
        assert errors[0].role == "engineer" and errors[0].side == "parallel"


def test_budget_halt_on_optional_call_still_halts(db, config, base_spec):
    d = OutageDispatcher(config.pricing, base_spec, set(), db=db)
    d.halt_on_call = 2  # researcher parallel — an OPTIONAL call
    orch = CouncilOrchestrator(db, config.pricing, d, config.council)

    with pytest.raises(BudgetHalt):
        orch.run_session("brief that hits the cap on call 2 (scripted)")

    with db.get_session() as s:
        sess = s.query(CouncilSessionRow).one()
        assert sess.status == "halted_budget"
