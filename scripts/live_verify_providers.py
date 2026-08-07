"""Live provider verification (ADR-009 / ADR-021) — OPERATOR RUNS THIS.

The build sandbox holds no provider keys, so the account-specific checks run
here, on your machine, against your keys in .env:

  1. models.list() per provider — which model strings YOUR account serves
     (availability is account-specific; the 2026-07-31 kimi list proved it).
  2. A minimal kimi-k3 TEXT call — dumps the raw response shape so the
     offline test transports can be checked against reality, not assumption
     (LIMITATIONS §7). Cost: a few cents at most.
  3. Minimal anthropic + openai text calls — same shape dump (both were
     live-verified by the Phase 1 gate; this re-confirms nothing broke).

Run from the repo root (backend environment active, .env filled):

    python scripts/live_verify_providers.py

It prints a report and writes scripts/live_verify_report.json. Paste the
console output back to the technical lead. API keys are never printed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.config import get_settings, load_config_bundle  # noqa: E402


def main() -> int:
    settings = get_settings()
    bundle = load_config_bundle()
    report: dict = {"models_list": {}, "text_calls": {}}

    # --- 1. models.list() per provider ------------------------------------
    import openai
    import anthropic

    if settings.openai_api_key:
        client = openai.OpenAI(api_key=settings.openai_api_key, timeout=60.0)
        ids = sorted(m.id for m in client.models.list().data)
        report["models_list"]["openai"] = ids
        print(f"[openai] models.list(): {len(ids)} models; "
              f"gpt-4o present: {'gpt-4o' in ids}")
    else:
        print("[openai] SKIPPED — OPENAI_API_KEY not set in .env")

    if settings.moonshot_api_key:
        base = bundle.council.endpoints.get("kimi") or "https://api.moonshot.ai/v1"
        client = openai.OpenAI(
            api_key=settings.moonshot_api_key, base_url=base, timeout=60.0
        )
        ids = sorted(m.id for m in client.models.list().data)
        report["models_list"]["kimi"] = ids
        print(f"[kimi] models.list(): {ids}")
    else:
        print("[kimi] SKIPPED — MOONSHOT_API_KEY not set in .env")

    if settings.anthropic_api_key:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=60.0)
        page = client.models.list(limit=100)
        ids = sorted(m.id for m in page.data)
        report["models_list"]["anthropic"] = ids
        print(f"[anthropic] models.list(): {len(ids)} models; "
              f"claude-sonnet-4-5 present: "
              f"{any('claude-sonnet-4-5' in i for i in ids)}")
    else:
        print("[anthropic] SKIPPED — ANTHROPIC_API_KEY not set in .env")

    # --- 2/3. minimal text calls, raw shape dump ---------------------------
    def dump_kimi() -> None:
        base = bundle.council.endpoints.get("kimi") or "https://api.moonshot.ai/v1"
        client = openai.OpenAI(
            api_key=settings.moonshot_api_key, base_url=base, timeout=60.0
        )
        resp = client.chat.completions.create(
            model="kimi-k3",
            max_completion_tokens=32,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        )
        dump = resp.model_dump()
        report["text_calls"]["kimi"] = dump
        choice0 = dump["choices"][0]
        print("[kimi] text call shape: top-level keys =", sorted(dump))
        print("[kimi] choices[0].message keys =", sorted(choice0["message"]))
        print("[kimi] usage keys =", sorted(dump.get("usage") or {}))
        print("[kimi] content[:60] =", repr((choice0["message"].get("content") or "")[:60]))

    def dump_openai() -> None:
        client = openai.OpenAI(api_key=settings.openai_api_key, timeout=60.0)
        resp = client.chat.completions.create(
            model="gpt-4o",
            max_completion_tokens=32,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        )
        dump = resp.model_dump()
        report["text_calls"]["openai"] = dump
        print("[openai] choices[0].message keys =", sorted(dump["choices"][0]["message"]))
        print("[openai] usage keys =", sorted(dump.get("usage") or {}))

    def dump_anthropic() -> None:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=60.0)
        resp = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=32,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        )
        dump = resp.model_dump()
        report["text_calls"]["anthropic"] = dump
        print("[anthropic] content block types =",
              [b.get("type") for b in dump["content"]])
        print("[anthropic] usage keys =", sorted(dump.get("usage") or {}))

    for name, configured, fn in [
        ("kimi", settings.moonshot_api_key, dump_kimi),
        ("openai", settings.openai_api_key, dump_openai),
        ("anthropic", settings.anthropic_api_key, dump_anthropic),
    ]:
        if not configured:
            print(f"[{name}] text call SKIPPED — key not set")
            continue
        try:
            fn()
        except Exception as exc:  # surface verbatim, never swallow (Rule 8)
            report["text_calls"][name] = {"error": str(exc)}
            print(f"[{name}] text call FAILED (verbatim): {exc}")

    out = REPO_ROOT / "scripts" / "live_verify_report.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nFull dump written to {out} — paste the console output back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
