"""Kimi (Moonshot AI) provider (ADR-002, ADR-009).

Moonshot's API is OpenAI-compatible, so this provider uses the official
`openai` SDK. All platform facts below come from LIVE sources, not recall:

* base_url — config/council.yaml -> endpoints.kimi, overridable via env
  MOONSHOT_BASE_URL, defaulting to https://api.moonshot.ai/v1 (operator's key
  verified live 2026-07-31; platform.kimi.ai/docs/api/overview, fetched
  2026-08-01). The previous hardcoded .cn endpoint caused a live 401.
* model — kimi-k3 for BOTH text and vision: the account's live models.list()
  has no vision-specific model, and kimi-k3 has native image input
  (platform.kimi.ai/docs/guide/use-kimi-vision-model.md, fetched 2026-08-01).
* parameter — max_completion_tokens, NOT max_tokens: the live chat-completion
  reference marks max_tokens "Deprecated, please refer to
  max_completion_tokens" (platform.kimi.ai/docs/api/chat.md, fetched
  2026-08-01).

Amendment 5: if the vision call fails with a model/endpoint error, the raw
message is surfaced verbatim in the ProviderError (and the gate instructs the
operator to record it in LIMITATIONS.md) — honest failure, never a silent
fallback.
"""

from __future__ import annotations

import base64
from pathlib import Path

import openai

from app.ai.provider import AIProvider, RawResult

# Default only — config/council.yaml endpoints.kimi and env MOONSHOT_BASE_URL
# take precedence (ADR-009: endpoints live in config, not code).
DEFAULT_KIMI_BASE_URL = "https://api.moonshot.ai/v1"

_MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp"}


class KimiProvider(AIProvider):
    name = "kimi"
    env_var = "MOONSHOT_API_KEY"

    def __init__(self, api_key, *, base_url: str | None = None, client=None,
                 **kwargs) -> None:
        super().__init__(api_key, **kwargs)
        self.base_url = base_url or DEFAULT_KIMI_BASE_URL
        # client= is dependency injection for the offline test transport;
        # production always builds the real SDK client below.
        self._client = client or (
            openai.OpenAI(api_key=api_key, base_url=self.base_url, timeout=60.0)
            if api_key
            else None
        )

    def health(self) -> dict:
        if self.api_key:
            return {"configured": True, "reason": "API key present"}
        return {
            "configured": False,
            "reason": f"missing API key (set {self.env_var} in .env)",
        }

    def _raw_complete(
        self, prompt: str, model: str, max_tokens: int, temperature: float
    ) -> RawResult:
        resp = self._client.chat.completions.create(
            model=model,
            # Live docs (chat.md, fetched 2026-08-01): max_tokens is
            # deprecated on this API — max_completion_tokens is the parameter.
            max_completion_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return RawResult(
            text=resp.choices[0].message.content or "",
            tokens_in=resp.usage.prompt_tokens,
            tokens_out=resp.usage.completion_tokens,
        )

    def _raw_vision(
        self, prompt: str, image_path: Path, model: str, max_tokens: int
    ) -> RawResult:
        media_type = _MEDIA_TYPES.get(image_path.suffix.lower())
        if media_type is None:
            raise ValueError(
                f"unsupported image type {image_path.suffix!r} for vision call"
            )
        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        try:
            resp = self._client.chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,  # see _raw_complete note
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{b64}"
                                },
                            },
                        ],
                    }
                ],
            )
        except Exception as exc:
            # Amendment 5: surface the raw model/endpoint error verbatim.
            raise RuntimeError(
                f"kimi vision call failed (model={model}): {exc}"
            ) from exc
        return RawResult(
            text=resp.choices[0].message.content or "",
            tokens_in=resp.usage.prompt_tokens,
            tokens_out=resp.usage.completion_tokens,
        )
