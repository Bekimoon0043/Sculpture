"""The single dispatch path for every AI call (SPEC section F, Rule 8).

``execute()`` is the ONLY way a prompt reaches a provider. PR-2 (ADR-061)
made the cap enforcement RESERVATION-based, per PHYSICAL attempt:

1. refuses outright when the provider carries no BudgetEnforcer — an
   uncapped paid dispatch is structurally impossible, not a convention,
2. computes the cap-safe reservation bound (context-window fallback — see
   ``reserve_bound_usd_micro`` below; the old chars/4 estimate is gone),
3. ensures the sessions row exists (the reservation FKs it),
4. for EACH physical attempt: atomically RESERVES the bound (BudgetHalt
   raises here, with its evidence committed, before any network traffic),
   dispatches, then settles in ONE transaction — the ai_calls row insert,
   the reservation settlement and the sessions ledger update commit
   together, so a crash can never leave a partial state,
5. a failed attempt writes its own error ai_calls row and its reservation
   goes UNCERTAIN — counted at the full bound forever (fail closed: no
   first-party documentation proves any provider error class non-billing;
   silence is not proof). Transient failures retry under a NEW reservation
   with audited linkage (ADR-023 semantics preserved, now one row per
   attempt so no attempt is ever invisible),
6. a pricing failure after a billed call settles UNCERTAIN at the full
   bound AND engages a provider/model safety lock (the pricing machinery
   may be wrong for every run using that model); an actual cost above the
   reserved bound does the same at settlement. Both halt the spend scope.

Missing API key -> ProviderError("... not configured ...") BEFORE any
reservation or network. Pricing/bound lookup failure -> ProviderError; a
price or a context window is never guessed.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from app.core.budget import usd_to_micro
from app.core.config import PricingLookupError
from app.db.models import SessionRow

if TYPE_CHECKING:
    from app.ai.provider import AIProvider, ProviderResponse, RawResult


def reserve_bound_usd_micro(
    pricing, provider_name: str, model: str, max_tokens: int
) -> int:
    """Cap-safe reservation upper bound in micro-USD (ADR-061, Amendment 4).

    No provider's first-party documentation proves every component of a
    prompt-based token formula (message framing overhead is documented by
    none of the three; fetched 2026-08-28 — see pricing.yaml), so ALL
    providers use the mandated conservative fallback:

        bound = context_window_tokens x highest applicable input rate
              + max_tokens          x output rate

    * context_window_tokens is the model's FIRST-PARTY documented context
      window (pricing.yaml, per model, with source + fetch date). Billed
      input tokens — text AND images — are context tokens by definition,
      so the window ceilings both.
    * The input rate is max(base input, cache-write): anthropic 5-minute
      cache writes bill 1.25x and our dispatch path can request ephemeral
      caching; the 1h class ($6) is unreachable — no code path sends a ttl.
      Cache READS are cheaper than base, so assuming zero reads is safe.
    * max_tokens is the request's own output ceiling, enforced server-side
      (first-party model pages list max output; the request cannot exceed
      what it asked for).
    * Rounding is CEILING to the next micro-USD — a bound never rounds down.
    """
    entry = pricing.price_for(provider_name, model)  # raises if absent
    if entry.context_window_tokens is None:
        raise PricingLookupError(
            f"no context_window_tokens for {provider_name}/{model} in "
            f"config/pricing.yaml — the ADR-061 reservation bound needs the "
            "model's first-party documented context window (with source and "
            "fetch date); add it rather than guessing"
        )
    if max_tokens < 1:
        raise ValueError("max_tokens must be at least 1")
    input_rate = Decimal(str(entry.usd_per_1m_input_tokens))
    if entry.usd_per_1m_cache_write_input_tokens is not None:
        input_rate = max(
            input_rate, Decimal(str(entry.usd_per_1m_cache_write_input_tokens))
        )
    output_rate = Decimal(str(entry.usd_per_1m_output_tokens))
    bound = (
        Decimal(entry.context_window_tokens) * input_rate
        + Decimal(max_tokens) * output_rate
    ) / Decimal(1_000_000)
    return usd_to_micro(bound, rounding=ROUND_CEILING)


def _is_transient(exc: Exception) -> bool:
    """Timeout / connection failures are transient and worth retrying; 4xx,
    validation and shape errors are not. Class-name matching covers both
    SDKs (openai.* / anthropic.* Timeout+Connection errors) and httpx.
    (Retry POLICY only — spend classification is uniformly 'uncertain'.)
    """
    name = type(exc).__name__.lower()
    return "timeout" in name or "connection" in name or "connect" in name


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_session(provider: "AIProvider", session_id: str) -> None:
    """ai_calls.session_id and spend_reservations.session_id are FKs; the
    sessions row must exist BEFORE the first reservation (ADR-061)."""
    with provider._db.get_session() as s:
        if s.get(SessionRow, session_id) is None:
            s.add(
                SessionRow(
                    id=session_id,
                    started_at=_utc_now_iso(),
                    ended_at=None,
                    status="active",
                    total_cost_usd=0.0,
                )
            )


def execute(
    provider: "AIProvider",
    *,
    kind: Literal["text", "vision"],
    prompt: str,
    image_path: Path | None,
    purpose: str,
    model: str,
    max_tokens: int,
    temperature: float | None,
    session_id: str,
) -> "ProviderResponse":
    from app.ai.provider import ProviderError, ProviderResponse  # avoid cycle

    # Missing key -> honest failure BEFORE any reservation or network.
    if not provider.api_key:
        raise ProviderError(
            provider.name,
            f"provider not configured (set {provider.env_var} in .env)",
        )

    # ADR-061: an uncapped paid dispatch is impossible, not discouraged.
    if provider._budget is None:
        raise ProviderError(
            provider.name,
            "no BudgetEnforcer attached — uncapped paid dispatch is "
            "forbidden (ADR-061); construct providers via build_providers "
            "with an enforcer",
        )
    budget = provider._budget

    # Bound lookup failure -> ProviderError; never guess.
    try:
        bound_micro = reserve_bound_usd_micro(
            provider._pricing, provider.name, model, max_tokens
        )
    except PricingLookupError as exc:
        raise ProviderError(provider.name, str(exc)) from exc

    _ensure_session(provider, session_id)

    from app.ai.provider import (  # local import: config-free env helpers
        provider_backoff_base_s,
        provider_max_attempts,
    )

    max_attempts = provider_max_attempts()
    backoff_base = provider_backoff_base_s()
    started = time.perf_counter()
    retry_notes: list[str] = []

    for attempt in range(1, max_attempts + 1):
        # Atomic hold for THIS physical attempt. BudgetHalt (with its
        # evidence rows committed) propagates from here — including when a
        # retry no longer fits under a cap: money may already be gone.
        reservation_id = budget.reserve(
            bound_micro,
            provider=provider.name,
            model=model,
            kind=kind,
            attempt_no=attempt,
        )
        ts = _utc_now_iso()
        attempt_started = time.perf_counter()
        try:
            if kind == "text":
                raw: "RawResult" = provider._raw_complete(
                    prompt, model, max_tokens, temperature
                )
            else:
                assert image_path is not None
                raw = provider._raw_vision(
                    prompt, Path(image_path), model, max_tokens
                )
        except Exception as exc:
            latency_ms = round((time.perf_counter() - attempt_started) * 1000, 3)
            error_text = str(exc)
            if retry_notes:
                error_text += " | retry history: " + " ; ".join(retry_notes)
            budget.record_failed_attempt(
                reservation_id,
                ts=ts, provider=provider.name, model=model, purpose=purpose,
                prompt=prompt, response="", tokens_in=0, tokens_out=0,
                cached_input_tokens=0, cache_write_input_tokens=0,
                latency_ms=latency_ms,
                pricing_version=provider._pricing.pricing_version,
                error=error_text,
            )
            if attempt < max_attempts and _is_transient(exc):
                retry_notes.append(
                    f"attempt {attempt}/{max_attempts} transient: {exc} "
                    f"(reservation {reservation_id} held uncertain)"
                )
                time.sleep(backoff_base * (3 ** (attempt - 1)))
                continue
            raise ProviderError(provider.name, error_text) from exc

        latency_ms = round((time.perf_counter() - started) * 1000, 3)

        # Real cost from real tokens. If a cache-class price is missing the
        # call ALREADY succeeded (money was spent): the audit row persists
        # with the pricing failure recorded, the reservation stays counted
        # at its FULL bound (fail closed — never 0), and a provider/model
        # safety lock engages before the honest raise (Amendment 5).
        try:
            cost_usd = provider._pricing.cost_usd(
                provider.name,
                model,
                raw.tokens_in,
                raw.tokens_out,
                cached_input_tokens=raw.cached_input_tokens,
                cache_write_input_tokens=raw.cache_write_input_tokens,
            )
        except PricingLookupError as exc:
            budget.record_failed_attempt(
                reservation_id,
                ts=ts, provider=provider.name, model=model, purpose=purpose,
                prompt=prompt, response=raw.text, tokens_in=raw.tokens_in,
                tokens_out=raw.tokens_out,
                cached_input_tokens=raw.cached_input_tokens,
                cache_write_input_tokens=raw.cache_write_input_tokens,
                latency_ms=latency_ms,
                pricing_version=provider._pricing.pricing_version,
                error=f"pricing failure after successful call: {exc}",
                pricing_failure=True,
            )
            raise ProviderError(provider.name, str(exc)) from exc

        budget.settle_success(
            reservation_id,
            ts=ts, provider=provider.name, model=model, purpose=purpose,
            prompt=prompt, response=raw.text, tokens_in=raw.tokens_in,
            tokens_out=raw.tokens_out,
            cached_input_tokens=raw.cached_input_tokens,
            cache_write_input_tokens=raw.cache_write_input_tokens,
            latency_ms=latency_ms, cost_usd=cost_usd,
            pricing_version=provider._pricing.pricing_version,
        )

        return ProviderResponse(
            provider=provider.name,
            model=model,
            text=raw.text,
            tokens_in=raw.tokens_in,
            tokens_out=raw.tokens_out,
            cached_input_tokens=raw.cached_input_tokens,
            cache_write_input_tokens=raw.cache_write_input_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            pricing_version=provider._pricing.pricing_version,
        )

    raise AssertionError("unreachable: the attempt loop returns or raises")
