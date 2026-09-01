"""Cache-class pricing tests (ADR-022, 2026-08-07).

Operator order after the live_verify run: kimi usage returns cached_tokens
(cache-hit input at $0.30 vs cache-miss $3.00 — 10x) and anthropic usage
returns cache_creation_input_tokens / cache_read_input_tokens — read them
and price the input classes separately. These tests prove:

  1. kimi splits usage.cached_tokens OUT of prompt_tokens (uncached billed
     at $3.00, cached at $0.30), with hand-computed costs;
  2. anthropic bills input_tokens (already uncached) + cache-read ($0.30) +
     5m cache-write ($3.75) as three classes;
  3. a usage shape anomaly (cached > prompt) fails loudly, never guesses;
  4. a cache class with NO configured price fails loudly (never guesses),
     and the billed call is STILL persisted to ai_calls (Rule 8 audit);
  5. openai deliberately does NOT split (cached rate not first-party
     verified) — conservative full-price billing;
  6. cache token counts persist on the ai_calls row.
"""

from __future__ import annotations

import pytest

from app.ai.provider import ProviderError
from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.kimi_provider import KimiProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.budget import BudgetEnforcer
from app.core.config import PricingConfig, PricingLookupError
from app.db.models import AICallRow


def _build(cls, name, db, config, client):
    models = config.council.model_defaults[name]
    budget = BudgetEnforcer(f"cache-{name}", 5.0, 25.0, db)
    return cls(
        "test-key-not-real",
        client=client,
        text_model=models.text,
        vision_model=models.vision_or_text(),
        default_temperature=models.temperature,
        db=db,
        pricing=config.pricing,
        budget=budget,
    )


def test_kimi_cache_hit_split_lowers_cost(db, config, openai_transport):
    # 1000 total input, 400 cache-hit, 10 output.
    # cost = (600*3.00 + 400*0.30 + 10*15.00)/1e6 = 0.00207
    client = openai_transport("OK", 1000, 10, cached_tokens=400)
    provider = _build(KimiProvider, "kimi", db, config, client)

    resp = provider.complete("brief", purpose="test", session_id="cache-kimi")

    assert resp.tokens_in == 600            # uncached only — normalised
    assert resp.cached_input_tokens == 400
    assert resp.tokens_out == 10
    assert resp.cost_usd == round((600 * 3.00 + 400 * 0.30 + 10 * 15.00) / 1e6, 6)
    assert resp.cost_usd == 0.00207
    # and materially below the all-cache-miss billing: (1000*3 + 10*15)/1e6
    assert resp.cost_usd < round((1000 * 3.00 + 10 * 15.00) / 1e6, 6)


def test_anthropic_three_input_classes(db, config, anthropic_transport):
    # 1000 uncached + 500 cache-read + 200 cache-write, 10 output.
    # cost = (1000*3.00 + 500*0.30 + 200*3.75 + 10*15.00)/1e6 = 0.00405
    client = anthropic_transport(
        "OK", 1000, 10,
        cache_read_input_tokens=500, cache_creation_input_tokens=200,
    )
    provider = _build(AnthropicProvider, "anthropic", db, config, client)

    resp = provider.complete("brief", purpose="test", session_id="cache-ant")

    assert resp.tokens_in == 1000  # anthropic input_tokens excludes caches
    assert resp.cached_input_tokens == 500
    assert resp.cache_write_input_tokens == 200
    assert resp.cost_usd == round(
        (1000 * 3.00 + 500 * 0.30 + 200 * 3.75 + 10 * 15.00) / 1e6, 6
    )
    assert resp.cost_usd == 0.00405


def test_kimi_cached_greater_than_prompt_fails_loudly(db, config, openai_transport):
    client = openai_transport("OK", 100, 10, cached_tokens=150)  # impossible
    provider = _build(KimiProvider, "kimi", db, config, client)

    with pytest.raises(ProviderError, match="cached_tokens=150"):
        provider.complete("brief", purpose="test", session_id="cache-anomaly")

    with db.get_session() as s:
        rows = s.query(AICallRow).all()
    assert len(rows) == 1
    assert rows[0].status == "error"
    assert "cached_tokens=150" in rows[0].error


def test_unpriced_cache_class_fails_but_call_is_audited(db, config, openai_transport):
    # pricing WITHOUT the kimi cache-read price: the class is unpriced.
    pricing = PricingConfig(
        pricing_version="test-no-cache",
        providers={
            "kimi": {
                "kimi-k3": {
                    "usd_per_1m_input_tokens": 3.00,
                    "usd_per_1m_output_tokens": 15.00,
                    "effective_date": "2026-08-01",
                    # ADR-061: the reservation bound needs the context
                    # window; without it the dispatch would refuse BEFORE
                    # spending, and this test is about failing AFTER.
                    "context_window_tokens": 1048576,
                    "context_window_source": "test fixture",
                }
            }
        },
    )
    with pytest.raises(PricingLookupError, match="cache-READ"):
        pricing.cost_usd("kimi", "kimi-k3", 600, 10, cached_input_tokens=400)

    # And through the full dispatch path: the call SUCCEEDED (money was
    # spent), so the audit row must still exist with the failure recorded.
    models = config.council.model_defaults["kimi"]
    budget = BudgetEnforcer("cache-unpriced", 5.0, 25.0, db)
    client = openai_transport("OK", 1000, 10, cached_tokens=400)
    provider = KimiProvider(
        "test-key-not-real",
        client=client,
        text_model=models.text,
        vision_model=models.vision_or_text(),
        default_temperature=models.temperature,
        db=db,
        pricing=pricing,
        budget=budget,
    )
    with pytest.raises(ProviderError, match="cache-READ"):
        provider.complete("brief", purpose="test", session_id="cache-unpriced")

    with db.get_session() as s:
        rows = s.query(AICallRow).all()
    assert len(rows) == 1
    assert rows[0].status == "error"
    assert rows[0].tokens_in == 600           # the real billed tokens are kept
    assert rows[0].cached_input_tokens == 400
    assert "pricing failure after successful call" in rows[0].error


def test_openai_does_not_split_conservative_full_price(db, config, openai_transport):
    # gpt-4o cached rate is tracker-only, not first-party verified: the
    # provider ignores cached_tokens and bills all input at the full rate.
    client = openai_transport("OK", 1000, 10, cached_tokens=400)
    provider = _build(OpenAIProvider, "openai", db, config, client)

    resp = provider.complete("brief", purpose="test", session_id="cache-oai")

    assert resp.tokens_in == 1000
    assert resp.cached_input_tokens == 0
    assert resp.cost_usd == round((1000 * 2.50 + 10 * 10.00) / 1e6, 6)


def test_cache_tokens_persist_on_ai_calls_row(db, config, anthropic_transport):
    client = anthropic_transport(
        "OK", 800, 5,
        cache_read_input_tokens=300, cache_creation_input_tokens=100,
    )
    provider = _build(AnthropicProvider, "anthropic", db, config, client)
    provider.complete("brief", purpose="test", session_id="cache-persist")

    with db.get_session() as s:
        row = s.query(AICallRow).one()
    assert row.tokens_in == 800
    assert row.cached_input_tokens == 300
    assert row.cache_write_input_tokens == 100
    assert row.cost_usd == round(
        (800 * 3.00 + 300 * 0.30 + 100 * 3.75 + 5 * 15.00) / 1e6, 6
    )
    assert row.pricing_version == "2026-08-v4"


def test_pricing_yaml_v3_has_first_party_cache_prices(config):
    kimi = config.pricing.price_for("kimi", "kimi-k3")
    assert kimi.usd_per_1m_cached_input_tokens == 0.30
    ant = config.pricing.price_for("anthropic", "claude-sonnet-4-5")
    assert ant.usd_per_1m_cached_input_tokens == 0.30
    assert ant.usd_per_1m_cache_write_input_tokens == 3.75
    # openai: deliberately unpriced for cache (see pricing.yaml note)
    oai = config.pricing.price_for("openai", "gpt-4o")
    assert oai.usd_per_1m_cached_input_tokens is None


# --- ADR-024: cache-break prompt structure + anthropic cache_control --------

def test_designer_prompt_static_prefix_then_variant_after_break(config):
    from app.ai.provider import CACHE_BREAK
    from app.council import prompts

    p1 = prompts.designer_prompt("BRIEF", "RESEARCH", 1, "SCHEMA")
    p2 = prompts.designer_prompt("BRIEF", "RESEARCH", 2, "SCHEMA")
    assert CACHE_BREAK in p1 and CACHE_BREAK in p2
    # identical static prefixes — the cacheable part
    assert p1.split(CACHE_BREAK)[0] == p2.split(CACHE_BREAK)[0]
    # the alternative number varies ONLY after the break
    assert "ALTERNATIVE 1" in p1.split(CACHE_BREAK)[1]
    assert "ALTERNATIVE 2" in p2.split(CACHE_BREAK)[1]
    assert "ALTERNATIVE" not in p1.split(CACHE_BREAK)[0]


def test_post_designer_roles_share_context_prefix():
    from app.ai.provider import CACHE_BREAK
    from app.council import prompts

    brief, summary = "BRIEF", "SUMMARY"
    prefixes = [
        prompts.geometrist_prompt(brief, summary),
        prompts.engineer_prompt(brief, summary, "GEO"),
        prompts.critic_prompt(brief, summary, "ENG"),
        prompts.arbiter_prompt(brief, summary, "ENG", "DEFECTS"),
    ]
    split = [p.split(CACHE_BREAK) for p in prefixes]
    assert all(len(s) == 2 for s in split)
    first = split[0][0]
    assert all(s[0] == first for s in split)  # one shared cache prefix
    # role-specific content lives after the break
    assert "GEOMETRIST" in split[0][1] and "ARBITER" in split[3][1]
    assert "GEO" in split[1][1] and "DEFECTS" in split[3][1]


def test_anthropic_sends_cache_control_on_break(db, config, anthropic_transport):
    from app.ai.provider import CACHE_BREAK

    client = anthropic_transport("OK", 10, 5)
    models = config.council.model_defaults["anthropic"]
    budget = BudgetEnforcer("cache-break", 5.0, 25.0, db)
    provider = AnthropicProvider(
        "test-key-not-real", client=client, text_model=models.text,
        vision_model=models.vision_or_text(),
        default_temperature=models.temperature, db=db,
        pricing=config.pricing, budget=budget,
    )
    provider.complete(f"STATIC PREFIX{CACHE_BREAK}varying part",
                      purpose="test", session_id="cache-break")

    content = client.calls[0]["messages"][0]["content"]
    assert isinstance(content, list) and len(content) == 2
    assert content[0]["text"] == "STATIC PREFIX"
    assert content[0]["cache_control"] == {"type": "ephemeral"}
    assert content[1]["text"] == "varying part"

    # no sentinel -> plain string content, unchanged behavior
    client2 = anthropic_transport("OK", 10, 5)
    provider._client = client2
    provider.complete("ordinary prompt", purpose="test", session_id="cache-break")
    assert client2.calls[0]["messages"][0]["content"] == "ordinary prompt"
