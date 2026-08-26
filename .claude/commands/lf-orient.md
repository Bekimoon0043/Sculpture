---
description: Start of session — read the repo, report exactly where the build stands, change nothing
---

You are the sole author of LuxuryForm Studio, resuming work. Orient yourself
before touching anything.

Read, in this order:
1. `CLAUDE.md` — the standing rules. They override your defaults.
2. `NEXT.md` — the loop state file. This is the source of truth for what is left.
3. `LIMITATIONS.md` — what is honestly not real yet.
4. `DECISIONS.md` — skim the ADR index (`grep -n "^## ADR" DECISIONS.md`), then
   read in full any ADR that touches the work `NEXT.md` says is next.
5. The `PHASE_*_PLAN.md` / `PHASE_*_REPORT.md` for the next item in the queue.

Then run and read the real output of:
```
git log --oneline -15
git status
git branch --show-current
```

Report back, in this order and nothing more:

1. **Where the build stands** — phase, slice, what is closed, in one short table.
2. **The next item in the queue** and whether it is blocked. If blocked, name
   the blocker and exactly what you need from the operator to clear it.
3. **Drift** — anything in the repo that contradicts `NEXT.md`, `LIMITATIONS.md`
   or a phase report. Quote both sides. Drift is a finding, not a fix.
4. **Anything that looks half-finished, inconsistent or wrong** that is not
   already written down.

**Do not change any code, any doc, or any config in this command.** Orientation
only. The operator decides what happens next.
