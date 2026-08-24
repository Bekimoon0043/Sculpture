# Phase 15 report - Designer UX correction

**Status: IN PROGRESS. Slices A-C auto gate PASS 2026-08-24; visual gate pending.**

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

## Slice B - designer-oriented controls

- Registry parameters are presented through a fallback-safe semantic layer:
  Form, Water & services, Material, Construction and Advanced. Registry values
  remain the sole source of ranges, units, defaults and constraint notes.
- Form, water/service and material controls are visible first. Construction
  and unknown future parameters remain available under Advanced rather than
  disappearing from the interface.
- Labels describe design intent (`Top diameter`, `Service bore`, `Tier
  spacing`) instead of exposing storage keys. Optional numeric fields can now
  be cleared back to their derived default.
- Checks lead with `Ready to progress`, `Review before fabrication`, `Changes
  required` or `Project input required`. Non-pass rows are summarized first;
  messages that name an element offer a direct selection action. Every raw
  measurement remains under All measured checks.
- Output leads with the LUXEXCHANGE fabrication package. Individual CAD/mesh
  files remain downloadable under a secondary disclosure.

Gate: `python scripts/gate_phase14_auto.py --frontend-only` PASS (typecheck +
production build, $0, offline).

## Slice C - isolated CAD draft preview

- `POST /api/geometry/assembly/preview.glb` executes the same assembly request
  through the real OpenCASCADE assembler and returns a named-node GLB.
- The route deliberately skips STEP export, layered validation and all database
  writes. It reports a stable request hash and measured kernel duration in
  response headers, but makes no validation or persistence claim.
- The workspace debounces edits by 550 ms, aborts the superseded request and
  rejects late responses by sequence number. Object URLs are revoked when
  replaced or on unmount.
- Draft geometry is displayed only when its request JSON still equals the
  current document. The viewport identifies it as `DRAFT / CAD preview /
  unvalidated`; Render and Output continue to require a canonical full build.

Gate evidence:

```text
docker compose exec backend python scripts/gate_phase15_auto.py
preview: 74460 bytes, nodes=['basin_01', 'column_01', 'plinth_01']
kernel time: 4745 ms
rows before=(0, 0), after two previews=(0, 0)
STEP sha256: 7e5d3adccbe871f5ea07...
persisted designs=2, validation rows=8
PASS - Phase 15 sections: backend ($0, offline)

python scripts\gate_phase15_auto.py --frontend-only
PASS - Phase 15 sections: frontend ($0, offline)

docker compose exec backend pytest tests/test_assembly_api.py -q
27 passed in 390.91s
```

The gate assembly measured about 4.7 seconds on this machine. Debouncing makes
editing coherent but does not make OpenCASCADE interactive; this remains a
documented performance limit rather than a hidden spinner.
