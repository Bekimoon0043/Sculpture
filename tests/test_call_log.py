"""Call-log tests (Rule 8): the full logged dispatch round-trip.

Uses the injected SDK transports from conftest.py — hand-constructed mocks
that pretend to be a provider's SDK client (see the plain-language conftest
comment). They let the REAL production dispatch path run offline; the assumed
SDK response shape they mirror is verified only by the live gate run.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.ai.provider import ProviderError
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.budget import BudgetEnforcer
from app.db.models import AICallRow


def _provider(db, config, client, api_key="test-key"):
    return OpenAIProvider(
        api_key,
        client=client,
        text_model="gpt-4o",
        vision_model="gpt-4o",
        db=db,
        pricing=config.pricing,
        budget=BudgetEnforcer("sess-1", 5.0, 25.0, db),
    )


def test_full_logging_round_trip(db, config, openai_transport):
    transport = openai_transport("LUXURYFORM", input_tokens=12, output_tokens=3)
    provider = _provider(db, config, transport)

    resp = provider.complete(
        "Reply with the word LUXURYFORM and nothing else.",
        purpose="test_round_trip",
        session_id="sess-1",
    )

    assert resp.provider == "openai"
    assert resp.model == "gpt-4o"
    assert resp.text == "LUXURYFORM"
    assert resp.tokens_in == 12
    assert resp.tokens_out == 3
    # gpt-4o: $2.50 / $10.00 per 1M tokens -> (12*2.5 + 3*10)/1e6
    assert resp.cost_usd == 0.00006
    assert resp.pricing_version == "2026-08-v2"
    assert resp.latency_ms >= 0

    # The SDK was called with the real parameters.
    assert len(transport.calls) == 1
    assert transport.calls[0]["model"] == "gpt-4o"

    # The ai_calls row persisted the full prompt and response (Rule 8).
    with db.get_session() as s:
        rows = s.execute(
            select(AICallRow).where(AICallRow.session_id == "sess-1")
        ).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.provider == "openai"
    assert row.prompt == "Reply with the word LUXURYFORM and nothing else."
    assert row.response == "LUXURYFORM"
    assert row.tokens_in == 12 and row.tokens_out == 3
    assert row.cost_usd == 0.00006
    assert row.status == "ok"
    assert row.error is None


def test_api_error_logs_error_row_and_raises(db, config, openai_transport):
    transport = openai_transport(
        "", 0, 0, error=RuntimeError("503: service unavailable")
    )
    provider = _provider(db, config, transport)

    with pytest.raises(ProviderError) as excinfo:
        provider.complete("hello", purpose="test_error", session_id="sess-1")
    assert excinfo.value.provider == "openai"
    assert "503" in excinfo.value.raw_message

    with db.get_session() as s:
        rows = s.execute(
            select(AICallRow).where(AICallRow.session_id == "sess-1")
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "error"
    assert "503" in rows[0].error
    assert rows[0].cost_usd == 0.0


def test_missing_key_raises_before_any_network(db, config, openai_transport):
    transport = openai_transport(
        "should never be returned", 1, 1,
        error=AssertionError("NETWORK WAS TOUCHED"),
    )
    provider = _provider(db, config, transport, api_key=None)

    with pytest.raises(ProviderError, match="not configured"):
        provider.complete("hello", purpose="test_no_key", session_id="sess-1")
    assert transport.calls == []  # proof: dispatch never happened


def test_unknown_model_pricing_raises_and_never_guesses(
    db, config, openai_transport
):
    transport = openai_transport(
        "should never be returned", 1, 1,
        error=AssertionError("NETWORK WAS TOUCHED"),
    )
    provider = _provider(db, config, transport)

    with pytest.raises(ProviderError, match="no price entry"):
        provider.complete(
            "hello", purpose="test_unknown_model", model="gpt-99-ultra",
            session_id="sess-1",
        )
    assert transport.calls == []
