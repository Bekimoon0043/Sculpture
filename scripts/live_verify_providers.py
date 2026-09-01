"""Live provider verification (ADR-009 / ADR-021) — OPERATOR RUNS THIS.

The build sandbox holds no provider keys, so the account-specific checks run
here, on your machine, against your keys in .env:

  1. models.list() per provider — which model strings YOUR account serves
     (availability is account-specific; the 2026-07-31 kimi list proved it).
     Listing models is an unmetered GET — no reservation needed.
  2. A minimal kimi-k3 TEXT call — dumps the raw response shape so the
     offline test transports can be checked against reality, not assumption
     (LIMITATIONS §7). Cost: a few cents at most.
  3. Minimal anthropic + openai text calls — same shape dump (both were
     live-verified by the Phase 1 gate; this re-confirms nothing broke).

PR-2 (ADR-061): this script was the repo's ONLY paid path outside the
capped, logged dispatch fence. The raw SDK calls stay (their PURPOSE is
the raw response shape, which the provider abstraction hides), but every
metered call is now wrapped by the real spend ledger: an atomic
reservation before, a settlement (ai_calls row + reservation + session
ledger, one transaction) after, a failed call recorded 'uncertain' at its
full bound. Input is billed conservatively at the full uncached rate in
the audit row (a 12-token prompt has no meaningful cache split).

Run from the repo root (backend environment active, .env filled):

    python scripts/live_verify_providers.py

It prints a report and writes scripts/live_verify_report.json. Paste the
console output back to the technical lead. API keys are never printed.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.ai.call_log import reserve_bound_usd_micro  # noqa: E402
from app.core.budget import BudgetEnforcer, BudgetHalt  # noqa: E402
from app.core.config import get_settings, load_config_bundle  # noqa: E402
from app.db.database import Database  # noqa: E402


def main() -> int:
    settings = get_settings()
    bundle = load_config_bundle()
    report: dict = {"models_list": {}, "text_calls": {}}

    # The OPERATOR's real database: verification spend is real spend and
    # lands in the same ledger and audit log as everything else (ADR-061).
    data_root = Path("/app/data") if Path("/app/data").exists() else REPO_ROOT / "data"
    db = Database(data_root / "luxuryform.db")
    db.init_db()
    verify_session = f"verify-{uuid.uuid4()}"
    budget = BudgetEnforcer(
        verify_session,
        bundle.budget.run_cap_usd,
        bundle.budget.day_cap_usd,
        db,
        scope_id=str(uuid.uuid4()),
        scope_kind="verify",
    )

    def metered(provider_name: str, model: str, max_tokens: int, fn):
        """Reserve -> raw call -> settle/record, through the real ledger."""
        bound = reserve_bound_usd_micro(bundle.pricing, provider_name, model,
                                        max_tokens)
        rid = budget.reserve(bound, provider=provider_name, model=model,
                             kind="text", attempt_no=1)
        ts = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()
        try:
            dump = fn()
        except Exception as exc:
            budget.record_failed_attempt(
                rid, ts=ts, provider=provider_name, model=model,
                purpose="live_verify_text", prompt="Reply with exactly: OK",
                response="", tokens_in=0, tokens_out=0,
                cached_input_tokens=0, cache_write_input_tokens=0,
                latency_ms=round((time.perf_counter() - t0) * 1000, 3),
                pricing_version=bundle.pricing.pricing_version,
                error=str(exc),
            )
            raise
        usage = dump.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens")
                         or usage.get("output_tokens") or 0)
        cost = bundle.pricing.cost_usd(provider_name, model, tokens_in,
                                       tokens_out)
        budget.settle_success(
            rid, ts=ts, provider=provider_name, model=model,
            purpose="live_verify_text", prompt="Reply with exactly: OK",
            response=json.dumps(dump, default=str)[:4000],
            tokens_in=tokens_in, tokens_out=tokens_out,
            cached_input_tokens=0, cache_write_input_tokens=0,
            latency_ms=round((time.perf_counter() - t0) * 1000, 3),
            cost_usd=cost, pricing_version=bundle.pricing.pricing_version,
        )
        print(f"[{provider_name}] settled ${cost:.6f} "
              f"(reserved bound ${bound / 1_000_000:.6f}) — logged in ai_calls")
        return dump

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

    # --- 2/3. minimal text calls, raw shape dump (metered via the ledger) --
    def dump_kimi() -> None:
        def raw() -> dict:
            base = bundle.council.endpoints.get("kimi") or "https://api.moonshot.ai/v1"
            client = openai.OpenAI(
                api_key=settings.moonshot_api_key, base_url=base, timeout=60.0
            )
            resp = client.chat.completions.create(
                model="kimi-k3",
                max_completion_tokens=32,
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            )
            return resp.model_dump()

        dump = metered("kimi", "kimi-k3", 32, raw)
        report["text_calls"]["kimi"] = dump
        choice0 = dump["choices"][0]
        print("[kimi] text call shape: top-level keys =", sorted(dump))
        print("[kimi] choices[0].message keys =", sorted(choice0["message"]))
        print("[kimi] usage keys =", sorted(dump.get("usage") or {}))
        print("[kimi] content[:60] =", repr((choice0["message"].get("content") or "")[:60]))

    def dump_openai() -> None:
        def raw() -> dict:
            client = openai.OpenAI(api_key=settings.openai_api_key, timeout=60.0)
            resp = client.chat.completions.create(
                model="gpt-4o",
                max_completion_tokens=32,
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            )
            return resp.model_dump()

        dump = metered("openai", "gpt-4o", 32, raw)
        report["text_calls"]["openai"] = dump
        print("[openai] choices[0].message keys =", sorted(dump["choices"][0]["message"]))
        print("[openai] usage keys =", sorted(dump.get("usage") or {}))

    def dump_anthropic() -> None:
        def raw() -> dict:
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key,
                                         timeout=60.0)
            resp = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=32,
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            )
            return resp.model_dump()

        dump = metered("anthropic", "claude-sonnet-4-5", 32, raw)
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
        except BudgetHalt as halt:
            report["text_calls"][name] = {"budget_halt": halt.reason}
            print(f"[{name}] REFUSED by the spend ledger (this is the cap "
                  f"working): {halt.reason}")
        except Exception as exc:  # surface verbatim, never swallow (Rule 8)
            report["text_calls"][name] = {"error": str(exc)}
            print(f"[{name}] text call FAILED (verbatim): {exc}")

    budget.close_scope()

    out = REPO_ROOT / "scripts" / "live_verify_report.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nFull dump written to {out} — paste the console output back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
