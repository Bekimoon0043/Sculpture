"""Anthropic provider — official `anthropic` SDK, messages API (ADR-002).

Text and vision both go through client.messages.create; vision attaches the
image as a base64 image block. Token counts are read from response.usage —
real numbers from the API, never estimates.

D-28 (ADR-070): the request is built as a plain dict (`_build_*_request`)
and sent unchanged (`_send`); call_log prices the reservation from that
same dict. `max_tokens` is "the absolute maximum number of tokens to
generate" (platform.claude.com/docs/en/api/messages, fetched 2026-09-14)
— the output ceiling the bound relies on. Anthropic also states "You are
not billed for system-added tokens. Billing reflects only your content"
(token-counting guide, fetched 2026-09-14), so no framing is billed on
top of the content bytes.
"""

from __future__ import annotations

import base64
from pathlib import Path

import anthropic

from app.ai.provider import (
    AIProvider,
    CACHE_BREAK,
    RawResult,
    provider_timeout_s,
)


def _cacheable_content(prompt: str):
    """Split a prompt at CACHE_BREAK into a cached prefix block + the rest.

    ADR-024 (first-party docs fetched 2026-08-07): anthropic only caches
    prefixes a request explicitly marks with cache_control=ephemeral; the
    prefix must be byte-identical across calls and over the model minimum
    (~1024 tokens). No sentinel -> the plain string passes through
    unchanged.
    """
    if CACHE_BREAK not in prompt:
        return prompt
    prefix, rest = prompt.split(CACHE_BREAK, 1)
    return [
        {"type": "text", "text": prefix,
         "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": rest},
    ]


def _cache_fields(usage) -> tuple[int, int]:
    """Anthropic cache classes -> (cache_read, cache_write) input tokens.

    Live-verified shape (operator run 2026-08-07, claude-sonnet-4-5): usage
    carries cache_creation_input_tokens and cache_read_input_tokens.
    Anthropic's input_tokens ALREADY EXCLUDES both cache classes, so no
    subtraction here (unlike kimi) — the classes price separately
    ($0.30 read / $3.75 5m-write per MTok — platform.claude.com/docs,
    fetched 2026-08-07). getattr defaults keep older SDK responses working.
    """

    return (
        int(getattr(usage, "cache_read_input_tokens", 0) or 0),
        int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
    )

_MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp"}


class AnthropicProvider(AIProvider):
    name = "anthropic"
    env_var = "ANTHROPIC_API_KEY"

    def __init__(self, api_key, *, client=None, **kwargs) -> None:
        super().__init__(api_key, **kwargs)
        # client= is dependency injection for the offline test transport;
        # production always builds the real SDK client below.
        self._client = client or (
            anthropic.Anthropic(api_key=api_key, timeout=provider_timeout_s(),
                # max_retries=0: the SDK's internal retry loop is invisible
                # to ai_calls and multiplied attempts silently (the
                # operator's 220 s "timeout" was 3 hidden internal attempts).
                # call_log owns retries, with every attempt audited.
                max_retries=0,
            ) if api_key else None
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
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": _cacheable_content(prompt)}],
        )
        if temperature is not None:  # None = omit the parameter entirely
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
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

    def _send(self, request: dict, *, kind: str) -> RawResult:
        resp = self._client.messages.create(**request)
        text = "".join(
            block.text for block in resp.content
            if getattr(block, "type", None) == "text"
        )
        cache_read, cache_write = _cache_fields(resp.usage)
        return RawResult(
            text=text,
            tokens_in=resp.usage.input_tokens,
            tokens_out=resp.usage.output_tokens,
            cached_input_tokens=cache_read,
            cache_write_input_tokens=cache_write,
        )
