"""OpenAI provider — official `openai` SDK, chat.completions API (ADR-002).

Vision attaches the image as an image_url data-URI block. Token counts come
from response.usage (prompt_tokens / completion_tokens) — real numbers from
the API.
"""

from __future__ import annotations

import base64
from pathlib import Path

import openai

from app.ai.provider import AIProvider, RawResult

_MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp"}


class OpenAIProvider(AIProvider):
    name = "openai"
    env_var = "OPENAI_API_KEY"

    def __init__(self, api_key, *, client=None, **kwargs) -> None:
        super().__init__(api_key, **kwargs)
        # client= is dependency injection for the offline test transport;
        # production always builds the real SDK client below.
        self._client = client or (
            openai.OpenAI(api_key=api_key, timeout=60.0) if api_key else None
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
            max_tokens=max_tokens,
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
        resp = self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
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
        return RawResult(
            text=resp.choices[0].message.content or "",
            tokens_in=resp.usage.prompt_tokens,
            tokens_out=resp.usage.completion_tokens,
        )
