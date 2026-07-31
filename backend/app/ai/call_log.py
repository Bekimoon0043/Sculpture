"""The single dispatch path for every AI call (SPEC section F, Rule 8).

``execute()`` is the ONLY way a prompt reaches a provider. In order, it:

1. computes a pre-call cost estimate from pricing.yaml,
2. runs ``BudgetEnforcer.pre_dispatch_check`` (Amendment 2 — raises BudgetHalt
   before any network traffic if a cap would be breached),
3. executes the real API call (SDK clients are built with a 60 s timeout),
4. computes the actual cost from the returned token counts x pricing.yaml,
5. records the actual spend and INSERTs the full ai_calls row — full prompt,
   full response, tokens, latency, cost, pricing version (Rule 8 audit),
6. on API error: INSERTs an ai_calls row with status='error' + the raw error
   text, then raises ProviderError.

Missing API key -> ProviderError("... not configured ...") BEFORE any network.
Pricing lookup failure (model not in pricing.yaml) -> ProviderError; a price
is never guessed.
"""

from __future__ import annotations

import math
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from app.core.budget import BudgetEnforcer
from app.core.config import PricingLookupError
from app.db.models import AICallRow, SessionRow

if TYPE_CHECKING:
    from app.ai.provider import AIProvider, ProviderResponse, RawResult

# Pre-call estimate assumptions (documented, conservative):
#  - text tokens are approximated at ~4 characters per token,
#  - a vision call additionally carries a fixed image-token allowance.
_CHARS_PER_TOKEN = 4
_VISION_IMAGE_TOKEN_ALLOWANCE = 1100


def estimate_cost_usd(
    provider: "AIProvider", model: str, prompt: str, max_tokens: int, kind: str
) -> float:
    """Pre-dispatch upper-ish estimate from pricing.yaml (never guessed)."""
    entry = provider._pricing.price_for(provider.name, model)  # raises if absent
    est_in = max(1, math.ceil(len(prompt) / _CHARS_PER_TOKEN))
    if kind == "vision":
        est_in += _VISION_IMAGE_TOKEN_ALLOWANCE
    est = (
        est_in * entry.usd_per_1m_input_tokens
        + max_tokens * entry.usd_per_1m_output_tokens
    ) / 1_000_000
    return round(est, 6)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_session(provider: "AIProvider", session_id: str) -> None:
    """ai_calls.session_id is a FK; make sure the sessions row exists."""
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
    temperature: float,
    session_id: str,
) -> "ProviderResponse":
    from app.ai.provider import ProviderError, ProviderResponse  # avoid cycle

    # Missing key -> honest failure BEFORE any network traffic.
    if not provider.api_key:
        raise ProviderError(
            provider.name,
            f"provider not configured (set {provider.env_var} in .env)",
        )

    # Pricing lookup failure -> ProviderError; never guess a price.
    try:
        estimate = estimate_cost_usd(provider, model, prompt, max_tokens, kind)
    except PricingLookupError as exc:
        raise ProviderError(provider.name, str(exc)) from exc

    # Amendment 2: hard cap check before the call exists.
    if provider._budget is not None:
        provider._budget.pre_dispatch_check(estimate)

    _ensure_session(provider, session_id)

    # Step 3: the real dispatch (SDK client carries the 60 s timeout).
    started = time.perf_counter()
    ts = _utc_now_iso()
    try:
        if kind == "text":
            raw: "RawResult" = provider._raw_complete(
                prompt, model, max_tokens, temperature
            )
        else:
            assert image_path is not None
            raw = provider._raw_vision(prompt, Path(image_path), model, max_tokens)
    except Exception as exc:  # step 6: log the error row, then raise honestly
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        _insert_call(
            provider,
            session_id=session_id,
            ts=ts,
            model=model,
            purpose=purpose,
            prompt=prompt,
            response="",
            tokens_in=0,
            tokens_out=0,
            latency_ms=latency_ms,
            cost_usd=0.0,
            status="error",
            error=str(exc),
        )
        raise ProviderError(provider.name, str(exc)) from exc

    latency_ms = round((time.perf_counter() - started) * 1000, 3)

    # Steps 4-5: real cost from real tokens, then persist the full row.
    cost_usd = provider._pricing.cost_usd(
        provider.name, model, raw.tokens_in, raw.tokens_out
    )
    _insert_call(
        provider,
        session_id=session_id,
        ts=ts,
        model=model,
        purpose=purpose,
        prompt=prompt,
        response=raw.text,
        tokens_in=raw.tokens_in,
        tokens_out=raw.tokens_out,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        status="ok",
        error=None,
    )
    if provider._budget is not None:
        provider._budget.record_actual(cost_usd)

    return ProviderResponse(
        provider=provider.name,
        model=model,
        text=raw.text,
        tokens_in=raw.tokens_in,
        tokens_out=raw.tokens_out,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        pricing_version=provider._pricing.pricing_version,
    )


def _insert_call(
    provider: "AIProvider",
    *,
    session_id: str,
    ts: str,
    model: str,
    purpose: str,
    prompt: str,
    response: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: float,
    cost_usd: float,
    status: str,
    error: str | None,
) -> str:
    call_id = str(uuid.uuid4())
    with provider._db.get_session() as s:
        s.add(
            AICallRow(
                id=call_id,
                session_id=session_id,
                ts=ts,
                provider=provider.name,
                model=model,
                purpose=purpose,
                prompt=prompt,
                response=response,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                pricing_version=provider._pricing.pricing_version,
                status=status,
                error=error,
            )
        )
    return call_id
