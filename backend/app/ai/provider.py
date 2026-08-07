"""AI provider abstraction (SPEC section F).

One interface for Anthropic, OpenAI and Kimi. Every concrete provider
implements ``_raw_complete`` / ``_raw_vision`` (the real SDK call); the public
``complete`` / ``vision`` methods live on the ABC and route EVERY call through
``ai/call_log.py`` — estimate, cap check, timed dispatch, real cost, full
logging. There is no code path that talks to a provider unlogged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.budget import BudgetEnforcer
    from app.core.config import PricingConfig
    from app.db.database import Database


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    model: str
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
    pricing_version: str
    # Cache-split input tokens (ADR-022; live-verified shapes 2026-08-07).
    # tokens_in is ALWAYS the UNCACHED input count, normalised per provider.
    cached_input_tokens: int = 0
    cache_write_input_tokens: int = 0


@dataclass(frozen=True)
class RawResult:
    """What a provider SDK call returns before logging/costing.

    Cache-split input tokens (ADR-022). Providers NORMALISE at the boundary:
    tokens_in is always the UNCACHED input count (kimi subtracts
    usage.cached_tokens from usage.prompt_tokens; anthropic's input_tokens
    already excludes cache reads/writes). cached_input_tokens = cache-read
    class (kimi cached_tokens / anthropic cache_read_input_tokens);
    cache_write_input_tokens = anthropic cache_creation_input_tokens (0 for
    OpenAI-compatible APIs, which have no write class).
    """

    text: str
    tokens_in: int
    tokens_out: int
    cached_input_tokens: int = 0
    cache_write_input_tokens: int = 0


class ProviderError(Exception):
    """Honest provider failure. Carries the provider and the raw message."""

    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.raw_message = message


class AIProvider(ABC):
    """Base class wiring every call through the logged, capped dispatch path."""

    name: str
    env_var: str

    def __init__(
        self,
        api_key: str | None,
        *,
        text_model: str,
        vision_model: str,
        db: "Database",
        pricing: "PricingConfig",
        budget: "BudgetEnforcer | None" = None,
        default_temperature: float | None = 0.0,
    ) -> None:
        self.api_key = api_key
        self.text_model = text_model
        self.vision_model = vision_model
        # None = omit temperature from requests (fixed-temperature reasoning
        # models, e.g. kimi-k3 — see council.yaml model_defaults).
        self.default_temperature = default_temperature
        self._db = db
        self._pricing = pricing
        self._budget = budget

    # -- public interface: routes through ai/call_log.py ----------------------

    def complete(
        self,
        prompt: str,
        *,
        purpose: str,
        model: str | None = None,
        max_tokens: int = 256,
        temperature: float | None = None,
        session_id: str,
    ) -> ProviderResponse:
        from app.ai import call_log

        return call_log.execute(
            self,
            kind="text",
            prompt=prompt,
            image_path=None,
            purpose=purpose,
            model=model or self.text_model,
            max_tokens=max_tokens,
            # Explicit argument wins; else the per-model config default
            # (None = omit the parameter entirely — fixed-temperature models).
            temperature=(
                temperature if temperature is not None else self.default_temperature
            ),
            session_id=session_id,
        )

    def vision(
        self,
        prompt: str,
        image_path: Path,
        *,
        purpose: str,
        model: str | None = None,
        max_tokens: int = 256,
        session_id: str,
    ) -> ProviderResponse:
        from app.ai import call_log

        return call_log.execute(
            self,
            kind="vision",
            prompt=prompt,
            image_path=image_path,
            purpose=purpose,
            model=model or self.vision_model,
            max_tokens=max_tokens,
            temperature=0.0,
            session_id=session_id,
        )

    @abstractmethod
    def health(self) -> dict:
        """{configured: bool, reason: str} — never includes key material."""

    # -- implemented by concrete providers: the real SDK call -----------------

    @abstractmethod
    def _raw_complete(
        self, prompt: str, model: str, max_tokens: int, temperature: float | None
    ) -> RawResult:
        """One real text API call via the official SDK.

        ``temperature=None`` means OMIT the parameter from the request —
        never substitute a number for a model that fixes its temperature.
        """

    @abstractmethod
    def _raw_vision(
        self, prompt: str, image_path: Path, model: str, max_tokens: int
    ) -> RawResult:
        """One real vision API call via the official SDK."""
