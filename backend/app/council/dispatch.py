"""Live dispatcher: wires the Council orchestrator to the real provider
layer (Phase 3, build step 2).

Every dispatch goes through provider.complete() -> call_log.execute, which
means the full Phase 1 machinery applies per call: pre-dispatch budget
check (BudgetHalt before any network), real cost from real tokens x
pricing.yaml, ai_calls audit row. The orchestrator additionally records the
council_calls row (role + side) — the per-role cost table is a GROUP BY
over council_calls; ai_calls remains the generic audit log.
"""

from __future__ import annotations

from app.ai.provider import AIProvider
from app.council.orchestrator import DispatchOutcome


class LiveDispatcher:
    """Production dispatcher: real SDKs, real money (budget-capped)."""

    def __init__(self, providers: dict[str, AIProvider]) -> None:
        self._providers = providers

    def dispatch(
        self,
        *,
        role: str,
        side: str,
        provider: str,
        prompt: str,
        session_id: str,
        max_tokens: int,
    ) -> DispatchOutcome:
        p = self._providers[provider]
        resp = p.complete(
            prompt,
            purpose=f"council_{role}",
            max_tokens=max_tokens,
            session_id=session_id,
        )
        return DispatchOutcome(
            provider=resp.provider,
            model=resp.model,
            text=resp.text,
            tokens_in=resp.tokens_in,
            tokens_out=resp.tokens_out,
            latency_ms=resp.latency_ms,
            cost_usd=resp.cost_usd,
            pricing_version=resp.pricing_version,
            status="ok",
            error=None,
        )
