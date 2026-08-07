"""Anthropic provider — official `anthropic` SDK, messages API (ADR-002).

Text and vision both go through client.messages.create; vision attaches the
image as a base64 image block. Token counts are read from response.usage —
real numbers from the API, never estimates.
"""

from __future__ import annotations

import base64
from pathlib import Path

import anthropic

from app.ai.provider import AIProvider, RawResult


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
            anthropic.Anthropic(api_key=api_key, timeout=60.0) if api_key else None
        )

    def health(self) -> dict:
        if self.api_key:
            return {"configured": True, "reason": "API key present"}
        return {
            "configured": False,
            "reason": f"missing API key (set {self.env_var} in .env)",
        }

    def _raw_complete(
        self, prompt: str, model: str, max_tokens: int, temperature: float | None
    ) -> RawResult:
        kwargs: dict = dict(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if temperature is not None:  # None = omit the parameter entirely
            kwargs["temperature"] = temperature
        resp = self._client.messages.create(**kwargs)
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

    def _raw_vision(
        self, prompt: str, image_path: Path, model: str, max_tokens: int
    ) -> RawResult:
        media_type = _MEDIA_TYPES.get(image_path.suffix.lower())
        if media_type is None:
            raise ValueError(
                f"unsupported image type {image_path.suffix!r} for vision call"
            )
        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        resp = self._client.messages.create(
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
