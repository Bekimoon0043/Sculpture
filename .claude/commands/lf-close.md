---
description: Close the slice — update the docs, commit as one unit, push, advance NEXT.md
argument-hint: [slice id and one-line summary]
---

Close out the slice: $ARGUMENTS

**Precondition:** the auto gate PASSES and the operator has confirmed the visual
gate. If either is untrue, stop and say which one. A slice that has not gated
does not close.

Update all of these in the SAME commit, so the commit can be rolled back as one
coherent unit:

1. **`NEXT.md`** — tick the item, move the queue forward, and rewrite section 0
   so the table matches reality. Add any new debt this slice created to §2
   Debts. Add any new blocker to §1. This file going stale is how the loop dies.
2. **`LIMITATIONS.md`** — retire what is now real (strike it through, keep the
   section number, note the date and the evidence); add what this slice could
   not do. Never silently drop an entry.
3. **`DECISIONS.md`** — a new ADR for any decision with a real trade-off, in the
   existing format: the decision, what it buys, what it gives up, and the
   evidence or fetch date behind it.
4. **The phase report** — `PHASE_N_REPORT.md` with the gate evidence: the actual
   transcript, the measured numbers, the real cost including retries.
5. **`README.md`** — only if what the platform can do has changed.

Then commit and push:
```
git add -A
git commit -m "<clear message: what became true, and the gate that proves it>"
git push -u origin claude/project-review-ai-loop-5jn2to
```
If the push fails on a network error, retry up to 4 times with backoff
(2s, 4s, 8s, 16s) — the operator's connection drops constantly. Do not open a
pull request unless the operator asks for one.

Finally, print a short handover for the next session:
- what is now true that was not before, in the operator's language
- the exact command the operator runs to see it for themselves
- what `/lf-next` will pick up, and whether it is blocked
