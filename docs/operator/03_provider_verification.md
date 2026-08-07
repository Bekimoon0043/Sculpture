# 03 — Verifying provider models and SDK shapes (Phase 3, ADR-009/ADR-021)

**When:** once, before the first live Council session (build step 4).
**Why:** model availability is account-specific, and the offline test
transports mirror an ASSUMED response shape. This script settles both with
your real keys. **Cost: a few cents at most.**

## Steps (Windows, from the repo folder)

1. Make sure `.env` has your three keys (same file as the Phase 1 gate):

       ANTHROPIC_API_KEY=...
       OPENAI_API_KEY=...
       MOONSHOT_API_KEY=...

2. Run (with the backend container running, or any shell where the backend
   Python environment is active):

       docker compose exec backend python scripts/live_verify_providers.py

3. The script prints, per provider: the model list your account serves
   (and whether `gpt-4o` / `claude-sonnet-4-5` are on it), then one minimal
   text call each with the RAW response shape (top-level keys, message
   keys, usage keys). It writes the full dump to
   `scripts/live_verify_report.json`.

4. Paste the console output back to the technical lead. Keys are never
   printed.

## What happens with the result

- If a model our config names is missing from your account's list, we
  change `config/council.yaml` to a model you actually have — one line.
- If the kimi text response shape differs from what the offline transports
  assume (`choices[0].message.content`, `usage.prompt_tokens` /
  `usage.completion_tokens`), the transports are updated to match reality
  BEFORE the first live Council session, and LIMITATIONS §7 is closed.
