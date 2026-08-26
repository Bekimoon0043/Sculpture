---
description: Run the gates and report verbatim output — PASS or FAIL, no interpretation
argument-hint: [optional: gate name, e.g. gate_phase4_auto]
---

Run the gates for the current slice and report the **verbatim** output.

Gate to run: $ARGUMENTS — if empty, run every auto gate that this slice could
have affected, plus the full test suite.

```
docker compose exec backend python -m pytest -q
docker compose exec backend python scripts/gate_phase1.py        # costs $0.01-0.05, only when asked
docker compose exec backend python scripts/gate_phase2_auto.py   # $0
docker compose exec backend python scripts/gate_phase3_auto.py   # $0
docker compose exec backend python scripts/gate_phase4_auto.py   # $0
docker compose exec backend python scripts/gate_costing_auto.py  # $0
```

Rules for this command:

- **Paste the real output.** Not a summary of it, not "all green". The numbers
  in the transcript are the evidence; a claim without them is not evidence.
- **A FAIL is a result, not a setback.** Report it immediately, in full, with
  the failing assertion and the real values on both sides.
- **Never adjust a gate so that it passes.** If the gate is wrong, say why it is
  wrong and what the correct check is, and get that agreed before changing it.
  A gate edited to accommodate the code it tests is worthless from then on.
- **Do not run anything that costs money without saying the projected cost
  first** and getting a yes. Caps: $5/session, $25/day. The Phase 1 gate and the
  `--live` halves of the Phase 3 and 4 gates spend real money; everything else
  in the list above is $0 forever.
- If a determinism check is in scope, print both sha256 hashes and the two
  process IDs that produced them. Same hash from one process proves nothing.

Then tell the operator which parts of the **visual** gate they must check by
eye, quoting the steps from `docs/operator/gate_*_visual.md`. The auto gate is
half the gate; you cannot pass the other half for them.
