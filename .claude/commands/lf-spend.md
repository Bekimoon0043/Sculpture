---
description: Cost a live run before any money is spent
argument-hint: [what you want to run]
---

Before spending anything: $ARGUMENTS

Report, in this order:

1. **The projected cost in dollars**, computed — not estimated from feel. Show
   the arithmetic: token counts per call × the rate in `config/pricing.yaml`,
   naming its `pricing_version`. Cache reads and cache writes price differently
   (ADR-022); if the prompt has a cached prefix, price both classes separately.
2. **What that buys** — the concrete outcome, and what remains unproven after it.
3. **The caps and the headroom**: $5 per session, $25 per day. Read today's
   actual spend from `http://localhost:8000/api/logs/budget` — do not assume it
   is zero. Say how much room is left after this run.
4. **Whether the same evidence is available at $0.** Fixture replay, the offline
   auto gates and the recorded Council sessions exist precisely so that logic can
   be developed without spending. If a $0 path proves the same thing, say so and
   recommend it.
5. **A warning if the number in `config/pricing.yaml` may be stale.** Providers
   change prices without notice (LIMITATIONS §4). Every logged call records which
   `pricing_version` computed its cost, so a stale number is identifiable — but
   it is still stale until the operator checks the price pages.

Then stop and wait for an explicit yes. The platform checks the cap before every
API call and halts on breach — but the operator's approval comes first, and the
cap is a backstop, not a budget.
