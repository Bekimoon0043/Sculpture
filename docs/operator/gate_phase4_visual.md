# Phase 4 Visual Gate — the operator half (about 10 minutes)

Run AFTER `gate_phase4_auto.py` printed `VERDICT: PASS` and AFTER one live
fabrication (doc 05). Everything below is an eye-check in the browser; no
command output to interpret.

## 1. The fabricated geometry renders

1. Open the viewport UI: http://localhost:5173
2. Switch to the **Cascade** view. The fabricated artifact lives at
   `data/fabrications/<session-id>/<program-id>/artifact.glb`.
   - [ ] The GLB loads in the viewport (use the path from the fabrication
     response or the transcript's Fabrication panel).
   - [ ] It looks like the cascade: one basin, a central column, stacked
     dishes — one fused solid, not floating parts.
   - [ ] The proportions follow the Arbiter's chosen spec (tier count and
     relative dish sizes match what the spec says).

## 2. The transcript shows the lineage

1. Switch to the **Council** view and open session `32e1c68f` (your live
   Phase 3 session).
2. Scroll to the **Fabrication** panel (between Design specs and
   Transcript).
   - [ ] Every attempt is a card: attempt number, provider, status badge.
   - [ ] A `passed` card shows a validation payload with REAL numbers
     (volume, watertight, mass) — not bare "ok".
   - [ ] If any attempt was rejected or failed, its card shows the reason
     verbatim (AST rejection reason, sandbox error, or the failed
     validation checks with numbers).
3. In the cost panel:
   - [ ] `geometrist_code` is its OWN line in the by-role rollup — you can
     see exactly what the code generation + repair loop cost.

## 3. Badge sanity (ADR-025)

- [ ] The session badge situation is honest: `degraded` only if a provider
  call failed, `corrected` if a re-ask succeeded, neither if clean.
  (Your restated session 32e1c68f should show `corrected`.)

## 4. Rates endpoint

Open http://localhost:8000/api/council/fabrication-rates in the browser.

- [ ] `first_attempt_pass_rate` and `per_round` are reported SEPARATELY.
- [ ] `ast_rejection_catalogue` lists any rejection reasons seen.

If every box checks: Phase 4 gate is PASSED. Note the date in your records.
