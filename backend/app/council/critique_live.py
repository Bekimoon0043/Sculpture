"""Live dispatcher for the vision critique loop (Phase 5).

`LiveDispatcher` in dispatch.py serves the text Council; it has no image
parameter. This is its vision counterpart: it satisfies the
`CritiqueDispatcher` protocol in critique.py and routes each call through
`AIProvider.vision()`, which means the whole Phase 1 machinery applies per
call — the pre-dispatch budget check that raises BudgetHalt BEFORE any
network traffic, real cost from real tokens against pricing.yaml, and the
`ai_calls` audit row. Rule 8 is not something this module implements; it is
something this module refuses to bypass.

THE FOUR VIEWS BECOME ONE IMAGE
-------------------------------
The critique protocol passes `image_paths` (four canonical views).
`AIProvider.vision()` takes one image. Rather than widen the audited provider
path, this composes the views into a single labelled contact sheet — which is
also what a person reviewing a design is handed, and what lets the model
compare the plan against the elevation instead of recalling it.
See app.render.contact_sheet for the full reasoning.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.ai.provider import AIProvider, ProviderError
from app.council.critique import CritiqueOutcome
from app.render.contact_sheet import build_contact_sheet

log = logging.getLogger("luxuryform.council.critique_live")


class LiveCritiqueDispatcher:
    """Production vision dispatcher: real SDKs, real money (budget-capped)."""

    def __init__(self, providers: dict[str, AIProvider],
                 sheet_dir: Path | None = None) -> None:
        self._providers = providers
        # Where composed sheets are kept. A real directory rather than a
        # temp file when the caller gives one, because the sheet is the
        # actual evidence of what the model was shown -- a critique that
        # cannot be traced back to its image is not auditable.
        self._sheet_dir = sheet_dir

    def dispatch(
        self,
        *,
        role: str,
        side: str,
        provider: str,
        prompt: str,
        session_id: str,
        max_tokens: int,
        image_paths: list[Path] | None = None,
    ) -> CritiqueOutcome:
        p = self._providers.get(provider)
        if p is None:
            return CritiqueOutcome(
                provider=provider, model="", text="", tokens_in=0, tokens_out=0,
                latency_ms=0.0, cost_usd=0.0, pricing_version="",
                status="error",
                error=f"provider {provider!r} is not configured",
            )

        if not image_paths:
            return CritiqueOutcome(
                provider=provider, model="", text="", tokens_in=0, tokens_out=0,
                latency_ms=0.0, cost_usd=0.0, pricing_version="",
                status="error",
                error="vision critique dispatched with no images",
            )

        sheet = self._compose(image_paths, session_id, provider)

        try:
            resp = p.vision(
                prompt,
                sheet,
                purpose=f"council_{role}",
                max_tokens=max_tokens,
                session_id=session_id,
            )
        except ProviderError as exc:
            # A provider failing is a normal outcome the loop handles: the
            # round proceeds with one critique and consensus reports that it
            # could not be reached. It is NOT an exception to the caller.
            log.warning("vision critique via %s failed: %s", provider, exc)
            return CritiqueOutcome(
                provider=provider, model="", text="", tokens_in=0, tokens_out=0,
                latency_ms=0.0, cost_usd=0.0, pricing_version="",
                status="error", error=str(exc),
            )

        return CritiqueOutcome(
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

    def _compose(self, image_paths: list[Path], session_id: str,
                 provider: str) -> Path:
        """Build the contact sheet both providers see.

        Both providers are shown the SAME sheet. Composing per provider would
        introduce a difference between them that has nothing to do with the
        design, and consensus between two models looking at two different
        pictures is not consensus.
        """
        views = {p.stem: p for p in image_paths}
        if self._sheet_dir is not None:
            self._sheet_dir.mkdir(parents=True, exist_ok=True)
            out = self._sheet_dir / "contact_sheet.png"
        else:
            out = Path(tempfile.gettempdir()) / f"critique_{session_id}.png"
        if out.exists():
            return out          # same round, second provider: reuse it
        return build_contact_sheet(views, out)


__all__ = ["LiveCritiqueDispatcher"]
