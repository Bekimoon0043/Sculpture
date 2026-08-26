---
description: Plan the next slice and stop for approval — no code
argument-hint: [optional: work item id, e.g. W-1, or a description]
---

Plan the next slice. **Write no code in this command.** `CLAUDE.md` requires the
plan to be reported and approved first; this is that report.

The slice to plan: $ARGUMENTS
If that is empty, take the first unblocked item from the work queue in `NEXT.md`.

First confirm the ground truth — do not plan from memory:
- Re-read the relevant section of `NEXT.md` and the phase plan it points to.
- Re-read every ADR the slice touches, and `LIMITATIONS.md` for the entries this
  slice would close or widen.
- Read the actual code you would be changing. Quote the current signatures.
- If the slice is **blocked** in `NEXT.md`, stop and say so. Do not plan around
  a blocker; ask for the ruling the blocker names.

Then report a plan with exactly these parts:

1. **What this slice makes true** — one paragraph, in the operator's language,
   not in API names.
2. **Files** — every file created, changed or deleted, with one line each on why.
3. **Schema, config and registry changes** — the before and after, explicitly.
   State whether the Phase 2 canonical STEP hash `e1a59fa6…` is affected. If it
   is, that needs its own ruling.
4. **The gate** — the exact `scripts/gate_*_auto.py` checks (each must be $0,
   non-interactive, and fail loudly with real numbers) and the
   `docs/operator/gate_*_visual.md` steps the operator checks by eye.
5. **Parameter ranges and envelopes** — per material, with the arithmetic that
   derives each bound. Never a number that "looked reasonable". Mark judgement
   values as judgement so the operator knows which need correction most.
6. **Projected cost in dollars**, split into $0 offline work and any live API
   spend, against the $5/session and $25/day caps. If it is $0, say $0.
7. **What could go wrong**, and which failure would be silent. Name the most
   dangerous silent failure explicitly.
8. **Anything in the order or in the brief you believe is wrong**, and what you
   would do instead. Say it now, not after building it.

End with: **"Approve this plan and I build it."** Then stop and wait.
