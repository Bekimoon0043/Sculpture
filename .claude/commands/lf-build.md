---
description: Build the approved slice — real code, real tests, no stubs
argument-hint: [optional: slice id]
---

Build the slice that was just approved: $ARGUMENTS

Non-negotiables while you build. These are `CLAUDE.md` rules, not preferences:

- **No stubs, no mocks, no placeholders, no TODO.** If a module is written, it
  works, and a `pytest` test proves it with real data. A test that asserts a
  mock returns what the mock was told to return proves nothing.
- **No fabricated capability.** If something cannot be done, it goes in
  `LIMITATIONS.md` and you build the real alternative. Never simulate an API
  response to make a demo look complete.
- **ADR-009 — nothing from recall.** Every third-party endpoint, model string,
  SDK shape, parameter name and price is fetched from live provider or library
  docs, and the fetch date is recorded in the ADR. This rule exists because
  breaking it cost three separate multi-hour failures.
- **ADR-005 — AI-written geometry code runs only in the sandbox.** Separate
  container, non-root, no network, read-only filesystem except the one scratch
  mount, CPU and memory limits, hard timeout. Never in a test. Never in a gate.
- **Metric, SI, explicit units.** A unitless number is a bug.
- **Determinism from the Design Spec onward.** Same spec + seed + pinned image =
  byte-identical STEP. Never write a gate that tests brief-level reproducibility.
- **Every AI call logged** — model, prompt, response, tokens, latency, cost.

Work in this order:
1. Write the failing test first where the behaviour is testable offline.
2. Write the code.
3. Run the tests and show the real output. `docker compose exec backend python -m pytest -q`
4. Write or extend the gate script for this slice.
5. Update `LIMITATIONS.md`, `DECISIONS.md` (a new ADR if you made a decision
   with a real trade-off), the phase report, and `NEXT.md`.

Report honestly and immediately if something does not work. A truthful failure
report is worth more than a demo that looks finished. Never claim something
works without showing the command and its real output.

**Do not commit yet.** `/lf-gate` runs next.

When done, remind the operator that anything touching `backend/` needs:
```
docker compose up --build -d
```
