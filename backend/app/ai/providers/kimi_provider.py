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
  2026-08-01). Re-fetched 2026-09-14 (D-28, ADR-070): "The maximum number
  of tokens to generate for the chat completion" — the output ceiling the
  reservation bound relies on. Whether K3's always-on reasoning is inside
  that ceiling is NOT documented; the operator's ledger shows completion
  tokens capped at exactly the requested maximum and never above.

Amendment 5: if the vision call fails with a model/endpoint error, the raw
message is surfaced verbatim in the ProviderError (and the gate instructs the
operator to record it in LIMITATIONS.md) — honest failure, never a silent
fallback.

D-28 (ADR-070): the request is built as a plain dict (`_build_*_request`)
and sent unchanged (`_send`); call_log prices the reservation from that
same dict.
"""

from __future__ import annotations

import base64
from pathlib import Path

import openai

from app.ai.provider import AIProvider, RawResult, provider_timeout_s


def _split_cached(usage) -> tuple[int, int]:
    """Normalise Moonshot usage -> (uncached_input, cached_input).

    Live-verified shape (operator run 2026-08-07, kimi-k3): usage carries
    top-level cached_tokens alongside prompt_tokens/completion_tokens.
    cached_tokens is the cache-HIT SUBSET of prompt_tokens, billed at a lower
    class ($0.30 vs $3.00 per MTok — platform.kimi.ai/docs/pricing,
    fetched 2026-08-07). Falls back to prompt_tokens_details.cached_tokens
    (OpenAI-compatible spelling) if the top-level field is absent.
    """

    prompt_total = usage.prompt_tokens
    cached = getattr(usage, "cached_tokens", None)
    if cached is None:
        details = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", 0) if details is not None else 0
    cached = int(cached or 0)
    if cached > prompt_total:  # shape anomaly — fail loudly, never guess
        raise ValueError(
            f"kimi usage reports cached_tokens={cached} > "
            f"prompt_tokens={prompt_total}; cannot split input classes"
        )
    return prompt_total - cached, cached

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
            openai.OpenAI(api_key=api_key, base_url=self.base_url, timeout=provider_timeout_s(),
                # max_retries=0: the SDK's internal retry loop is invisible
                # to ai_calls and multiplied attempts silently (the
                # operator's 220 s "timeout" was 3 hidden internal attempts).
                # call_log owns retries, with every attempt audited.
                max_retries=0,
            )
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

    def _build_text_request(
        self, prompt: str, model: str, max_tokens: int, temperature: float | None
    ) -> dict:
        kwargs: dict = dict(
            model=model,
            # Live docs (chat.md, fetched 2026-08-01): max_tokens is
            # deprecated on this API — max_completion_tokens is the parameter.
            max_completion_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        # Live K3 docs (kimi-k3-quickstart.md, fetched 2026-08-01):
        # "temperature=1.0, top_p=0.95, n=1, presence_penalty=0, and
        # frequency_penalty=0 are fixed; omit them from requests."
        # council.yaml therefore sets kimi temperature: null — the parameter
        # is only sent if the operator explicitly configures one.
        if temperature is not None:
            kwargs["temperature"] = temperature
        return kwargs

    def _build_vision_request(
        self, prompt: str, image_path: Path, model: str, max_tokens: int
    ) -> dict:
        media_type = _MEDIA_TYPES.get(image_path.suffix.lower())
        if media_type is None:
            raise ValueError(
                f"unsupported image type {image_path.suffix!r} for vision call"
            )
        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return dict(
            model=model,
            max_completion_tokens=max_tokens,  # see _build_text_request note
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

    def _send(self, request: dict, *, kind: str) -> RawResult:
        if kind == "vision":
            try:
                resp = self._client.chat.completions.create(**request)
            except Exception as exc:
                # Amendment 5: surface the raw model/endpoint error verbatim.
                raise RuntimeError(
                    f"kimi vision call failed (model={request.get('model')}): "
                    f"{exc}"
                ) from exc
        else:
            resp = self._client.chat.completions.create(**request)
        uncached, cached = _split_cached(resp.usage)
        return RawResult(
            text=resp.choices[0].message.content or "",
            tokens_in=uncached,
            tokens_out=resp.usage.completion_tokens,
            cached_input_tokens=cached,
        )
