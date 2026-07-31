"""Pricing config tests (ADR-006): versioned pricing, real math, no guessing."""

from __future__ import annotations

import pytest

from app.core.config import PricingLookupError


def test_pricing_yaml_loads_with_version(config):
    assert config.pricing.pricing_version == "2026-07-v1"


def test_every_council_default_model_has_a_price(config):
    """Every text+vision model named in council.yaml must be priced — the
    provider layer refuses to guess, so a missing entry would halt calls."""
    for provider, models in config.council.model_defaults.items():
        for kind in ("text", "vision"):
            model = getattr(models, kind)
            entry = config.pricing.price_for(provider, model)  # raises if absent
            assert entry.usd_per_1m_input_tokens > 0
            assert entry.usd_per_1m_output_tokens > 0


def test_effective_date_present_on_every_entry(config):
    for provider, models in config.pricing.providers.items():
        for model, entry in models.items():
            assert entry.effective_date, f"{provider}/{model} missing effective_date"


def test_cost_math_is_exact(config):
    # claude-sonnet-4-5: $3.00 / $15.00 per 1M tokens.
    cost = config.pricing.cost_usd(
        "anthropic", "claude-sonnet-4-5", tokens_in=1000, tokens_out=500
    )
    assert cost == pytest.approx((1000 * 3.00 + 500 * 15.00) / 1_000_000)
    assert cost == 0.0105


def test_unknown_model_raises_never_guesses(config):
    with pytest.raises(PricingLookupError):
        config.pricing.price_for("openai", "gpt-99-ultra")
