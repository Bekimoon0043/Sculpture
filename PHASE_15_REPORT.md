# Phase 15 report - Designer UX correction

**Status: IN PROGRESS. Slice A auto gate PASS 2026-08-24; visual gate pending.**

Plan: `PHASE_15_DESIGNER_UX_PLAN.md`. Decision: ADR-047.

## Slice A - workspace hierarchy

The first slice changes presentation only. It introduces no geometry, API or
database behavior.

- Viewport allocation increases from fixed 248/380 px rails to 220/330 px;
  Recent Builds starts collapsed at 34 px rather than permanently consuming
  118 px.
- Library cards move into an Add palette. Scene becomes the persistent left
  rail because selection and organization are continuous tasks.
- The right rail is one contextual surface with Design, Checks and Output
  tabs. Inspector, validation and export no longer form a stacked card column.
- Build is the sole primary workspace command. Render and export live under
  Output. Viewport commands use a consistent Lucide icon set.
- The bottom surface is honestly called Recent Builds until Slice E records
  real project and parent lineage.
- T/N shortcuts remain, with visible rail buttons so discoverability does not
  depend on memorizing a keymap.

Gate evidence:

```text
python scripts/gate_phase14_auto.py --frontend-only
PASS - typecheck and production build pass

npm audit --omit=dev
found 0 vulnerabilities
```

The Vite bundle-size warning remains: the three.js application chunk exceeds
500 kB. It is a performance optimization item, not a failed build.

