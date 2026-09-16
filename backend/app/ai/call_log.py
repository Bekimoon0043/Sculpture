"""The single dispatch path for every AI call (SPEC section F, Rule 8).

``execute()`` is the ONLY way a prompt reaches a provider. PR-2 (ADR-061)
made the cap enforcement RESERVATION-based, per PHYSICAL attempt; D-28
(ADR-070) made the reserved bound HONEST — derived from the real request:

1. refuses outright when the provider carries no BudgetEnforcer — an
   uncapped paid dispatch is structurally impossible, not a convention,
2. BUILDS the exact request dict the SDK will receive, and computes the
   cap-safe reservation bound from THAT object (``envelope_bound_usd_micro``
   below): min(context window, UTF-8 bytes of the serialized envelope + a
   256-token framing margin) x highest input rate + max_tokens x output
   rate. The context window is an absolute ceiling, never an assumed
   billable request. Vision requests stay on the ADR-061 window ceiling,
3. ensures the sessions row exists (the reservation FKs it),
4. for EACH physical attempt: atomically RESERVES the bound with its basis
   record (BudgetHalt raises here, with its evidence committed, before any
   network traffic), SENDS the same request object, then settles in ONE
   transaction — the ai_calls row insert, the reservation settlement and
   the sessions ledger update commit together, so a crash can never leave
   a partial state,
5. a failed attempt writes its own error ai_calls row and its reservation
   goes UNCERTAIN — counted at the full bound forever (fail closed: no
   first-party documentation proves any provider error class non-billing;
   silence is not proof). Transient failures retry under a NEW reservation
   with audited linkage (ADR-023 semantics preserved, now one row per
   attempt so no attempt is ever invisible),
6. a pricing failure after a billed call settles UNCERTAIN at the full
   bound AND engages a provider/model safety lock (the pricing machinery
   may be wrong for every run using that model); an actual cost above the
   reserved bound does the same at settlement (``bound_exceeded``); billed
   input tokens above the token bound, or output tokens above max_tokens,
   engage ``ceiling_violated`` even when the dollars still fit. All halt
   the spend scope.

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

from app.ai.provider import request_envelope_bytes
from app.core.budget import (
    ENVELOPE_FORMULA,
    FRAMING_MARGIN_STATUS,
    FRAMING_MARGIN_TOKENS,
    VISION_FORMULA,
    usd_to_micro,
)
from app.core.config import PricingLookupError
from app.db.models import SessionRow

if TYPE_CHECKING:
    from app.ai.provider import AIProvider, ProviderResponse, RawResult


def _rates(pricing, provider_name: str, model: str):
    """(entry, input rate, output rate) — the highest applicable input
    class and the output class, as Decimals from the stored decimal text.
    Raises PricingLookupError when the price or the first-party context
    window is absent: never guessed."""
    entry = pricing.price_for(provider_name, model)  # raises if absent
    if entry.context_window_tokens is None:
        raise PricingLookupError(
            f"no context_window_tokens for {provider_name}/{model} in "
            f"config/pricing.yaml — the reservation bound needs the model's "
            "first-party documented context window (with source and fetch "
            "date); add it rather than guessing"
        )
    input_rate = Decimal(str(entry.usd_per_1m_input_tokens))
    if entry.usd_per_1m_cache_write_input_tokens is not None:
        input_rate = max(
            input_rate, Decimal(str(entry.usd_per_1m_cache_write_input_tokens))
        )
    output_rate = Decimal(str(entry.usd_per_1m_output_tokens))
    return entry, input_rate, output_rate


def _bound_micro(input_tokens: int, input_rate: Decimal, max_tokens: int,
                 output_rate: Decimal) -> int:
    bound = (
        Decimal(input_tokens) * input_rate + Decimal(max_tokens) * output_rate
    ) / Decimal(1_000_000)
    return usd_to_micro(bound, rounding=ROUND_CEILING)


def reserve_bound_usd_micro(
    pricing, provider_name: str, model: str, max_tokens: int
) -> int:
    """The context-window CEILING in micro-USD (ADR-061, Amendment 4).

    Since D-28 (ADR-070) this is the CEILING the envelope bound can never
    exceed, not the reservation itself:

        ceiling = context_window_tokens x highest applicable input rate
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
      (first-party: anthropic "the absolute maximum number of tokens to
      generate"; openai "the maximum number of tokens that can be
      generated"; moonshot "the maximum number of tokens to generate" —
      all fetched 2026-09-14).
    * Rounding is CEILING to the next micro-USD — a bound never rounds down.
    """
    entry, input_rate, output_rate = _rates(pricing, provider_name, model)
    if max_tokens < 1:
        raise ValueError("max_tokens must be at least 1")
    return _bound_micro(entry.context_window_tokens, input_rate, max_tokens,
                        output_rate)


def envelope_bound_usd_micro(
    pricing, provider_name: str, model: str, kind: str, request: dict,
    max_tokens: int,
) -> tuple[int, dict]:
    """The honest reservation bound (D-28, ADR-070) and its basis record.

    TEXT:   input_tokens_bound = min(context_window,
                                     utf8_bytes(serialized request) + 256)
    VISION: input_tokens_bound = context_window (ADR-061 unchanged — image
            token formulas are not fetched; the window remains the ceiling)

        bound = input_tokens_bound x highest input rate
              + max_tokens         x output rate         (ceiling µUSD)

    The byte term: a lossless, reversible tokenizer over arbitrary text
    maps every byte into some token and emits no empty token, so tokens
    never exceed bytes (tiktoken README, fetched 2026-09-14, for openai).
    Anthropic and Moonshot publish neither a tokenizer nor a worst case:
    on the operator's real ledger the worst observed is 0.36 billed input
    tokens per prompt byte. The 256-token framing margin is the owner's
    amendment (2026-09-14): a conservative JUDGEMENT value, not first-party
    proof for anthropic or kimi (openai documents 3 per message + 3 reply
    priming as an estimate; anthropic bills no system-added tokens;
    moonshot documents nothing). The assumption is self-policed: billed
    input above input_tokens_bound engages ``ceiling_violated`` at
    settlement and the startup census re-checks every settled text call.

    Returns (micro-USD bound, basis dict persisted on the reservation).
    """
    entry, input_rate, output_rate = _rates(pricing, provider_name, model)
    if max_tokens < 1:
        raise ValueError("max_tokens must be at least 1")
    if kind not in ("text", "vision"):
        raise ValueError(f"unknown call kind {kind!r}")
    window = int(entry.context_window_tokens)
    nbytes = request_envelope_bytes(request)
    if kind == "vision":
        input_tokens = window
        formula = VISION_FORMULA
    else:
        input_tokens = min(window, nbytes + FRAMING_MARGIN_TOKENS)
        formula = ENVELOPE_FORMULA
    micro = _bound_micro(input_tokens, input_rate, max_tokens, output_rate)
    basis = {
        "formula": formula,
        "kind": kind,
        "envelope_utf8_bytes": nbytes,
        "framing_margin_tokens": FRAMING_MARGIN_TOKENS,
        "framing_margin_status": FRAMING_MARGIN_STATUS,
        "context_window_tokens": window,
        "input_tokens_bound": input_tokens,
        "ceiling_applied": input_tokens == window,
        "max_tokens": max_tokens,
        "input_rate_usd_per_1m": str(input_rate),
        "output_rate_usd_per_1m": str(output_rate),
        "bound_usd_micro": micro,
    }
    return micro, basis


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

    # D-28: build the EXACT request first; the bound is priced from it and
    # the same object is what gets sent.
    if kind == "text":
        request = provider._build_text_request(
            prompt, model, max_tokens, temperature
        )
    else:
        assert image_path is not None
        request = provider._build_vision_request(
            prompt, Path(image_path), model, max_tokens
        )

    # Bound lookup failure -> ProviderError; never guess.
    try:
        bound_micro, basis = envelope_bound_usd_micro(
            provider._pricing, provider.name, model, kind, request, max_tokens
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
            bound_basis=basis,
        )
        ts = _utc_now_iso()
        attempt_started = time.perf_counter()
        try:
            raw: "RawResult" = provider._send(request, kind=kind)
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
