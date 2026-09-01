"""Offline provider tests: all three providers through the real dispatch path.

Stated plainly: the injected SDK clients (InjectedAnthropicTransport /
InjectedOpenAITransport from conftest.py) are MOCKS that pretend to be a
provider. They are hand-constructed, not recorded, but their shapes are
LIVE-VERIFIED against the operator's account (live_verify_providers.py run
2026-08-07 — DECISIONS.md ADR-021/ADR-022; LIMITATIONS.md §7 retired). What
these tests prove is the real production code path AROUND the SDK call:
bound -> BudgetEnforcer.reserve (ADR-061) -> dispatch -> real token/cost
math from pricing.yaml -> ai_calls persistence. Production always builds real
SDK clients and requires real API calls; nothing here bypasses that.
"""

from __future__ import annotations

import pytest

from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.kimi_provider import KimiProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.budget import BudgetEnforcer

# (provider class, injected input tokens, injected output tokens, expected cost)
# Costs are hand-computed from config/pricing.yaml (2026-08-v3):
#   anthropic claude-sonnet-4-5 $3.00/$15.00 per 1M: (12*3 + 3*15)/1e6 = 0.000081
#   openai    gpt-4o           $2.50/$10.00 per 1M: (12*2.5 + 3*10)/1e6 = 0.00006
#   kimi      kimi-k3 $3.00/$15.00 per 1M (live docs 2026-08-01):
#             (20*3 + 4*15)/1e6 = 0.00012
TEXT_CASES = [
    ("anthropic", 12, 3, 0.000081),
    ("openai", 12, 3, 0.00006),
    ("kimi", 20, 4, 0.00012),
]

# Vision: 1000 in / 10 out for all three ->
#   anthropic: (1000*3 + 10*15)/1e6 = 0.00315
#   openai:    (1000*2.5 + 10*10)/1e6 = 0.0026
#   kimi (same kimi-k3 model, native image input): (1000*3 + 10*15)/1e6 = 0.00315
VISION_CASES = [
    ("anthropic", 1000, 10, 0.00315),
    ("openai", 1000, 10, 0.0026),
    ("kimi", 1000, 10, 0.00315),
]


def _build(name, db, config, client):
    models = config.council.model_defaults[name]
    budget = BudgetEnforcer(f"offline-{name}", 5.0, 25.0, db)
    kwargs = dict(
        text_model=models.text,
        vision_model=models.vision_or_text(),
        # Mirrors the factory: per-model temperature from council.yaml
        # (None for kimi-k3 = omit the parameter from requests).
        default_temperature=models.temperature,
        db=db,
        pricing=config.pricing,
        budget=budget,
    )
    cls = {"anthropic": AnthropicProvider, "openai": OpenAIProvider,
           "kimi": KimiProvider}[name]
    return cls("test-key-not-real", client=client, **kwargs)


def _transport(name, factory_anthropic, factory_openai, text, tin, tout):
    if name == "anthropic":
        return factory_anthropic(text, tin, tout)
    return factory_openai(text, tin, tout)  # kimi speaks the OpenAI protocol


@pytest.mark.parametrize("name,tin,tout,expected_cost", TEXT_CASES)
def test_complete_offline_correct_response_and_cost(
    name, tin, tout, expected_cost, db, config,
    anthropic_transport, openai_transport,
):
    client = _transport(name, anthropic_transport, openai_transport,
                        "LUXURYFORM", tin, tout)
    provider = _build(name, db, config, client)

    resp = provider.complete(
        "Reply with the word LUXURYFORM and nothing else.",
        purpose="test_offline",
        session_id=f"offline-{name}",
    )

    assert resp.provider == name
    assert resp.model == config.council.model_defaults[name].text
    assert resp.text == "LUXURYFORM"
    assert resp.tokens_in == tin
    assert resp.tokens_out == tout
    assert resp.cost_usd == expected_cost
    assert resp.pricing_version == "2026-08-v4"
    assert resp.latency_ms >= 0
    assert len(client.calls) == 1
    # Kimi live docs (chat.md + kimi-k3-quickstart.md, fetched 2026-08-01):
    # max_tokens is DEPRECATED (use max_completion_tokens), and K3 fixes
    # temperature=1.0 — "omit them from requests". council.yaml sets kimi
    # temperature: null, so the parameter must be ABSENT from the dispatch.
    if name == "kimi":
        assert "max_completion_tokens" in client.calls[0]
        assert "max_tokens" not in client.calls[0]
        assert "temperature" not in client.calls[0]
    else:
        # anthropic/openai are configured with temperature: 0.0 and must send it.
        assert client.calls[0].get("temperature") == 0.0


@pytest.mark.parametrize("name,tin,tout,expected_cost", VISION_CASES)
def test_vision_offline_correct_response_and_cost(
    name, tin, tout, expected_cost, db, config,
    anthropic_transport, openai_transport, test_image,
):
    description = "A deep blue field with a gold ring around a white square."
    client = _transport(name, anthropic_transport, openai_transport,
                        description, tin, tout)
    provider = _build(name, db, config, client)

    resp = provider.vision(
        "Describe this image in one sentence. Include the dominant color.",
        test_image,
        purpose="test_offline_vision",
        session_id=f"offline-{name}",
    )

    assert resp.provider == name
    assert resp.model == config.council.model_defaults[name].vision_or_text()
    assert resp.text == description
    assert resp.tokens_in == tin
    assert resp.tokens_out == tout
    assert resp.cost_usd == expected_cost
    assert len(client.calls) == 1
    # The image was really read and embedded in the request payload.
    payload = str(client.calls[0])
    assert "image" in payload
