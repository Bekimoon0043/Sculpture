# Phase 15 report - Designer UX correction

**Status: IMPLEMENTED. Slices A-E auto gate PASS 2026-08-24; visual gate pending.**

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

## Slice D - visual judgement

- Studio and Technical are explicit viewport modes. Studio adds a neutral
  ground, soft filmic lighting, model-derived shadows and a literal 1.7 m scale
  staff. Technical keeps the dark adaptive grid used for selection, measuring
  and section work.
- All lighting positions, ground dimensions and shadow bounds derive from the
  loaded model bounds. The scale staff is the sole fixed world measurement.
- The Add palette no longer presents hand-drawn primitive thumbnails. It runs
  one focused registry primitive through the preview route and shows the real
  CAD GLB with measured build time. Hover or keyboard focus changes the
  preview; only one kernel request is active.
- A/B comparison now synchronizes both cameras and reads both persisted build
  manifests. A scrollable table shows only changed seed, fabrication, primitive,
  joint and parameter values under the paired CAD views.

Gate evidence:

```text
docker compose exec backend python scripts/gate_phase15_auto.py
kernel previews: ['basin_round', 'plinth', 'sculptural_column', 'tiered_cascade']
all registry previews named; still no database writes
PASS - Phase 15 sections: backend ($0, offline)

npm run build
PASS - TypeScript and Vite production build
```

The visual acceptance checklist is `gate_phase15_visual.md`; operator pixel
review remains pending because no inspectable browser is connected to this
agent environment.

## Slice E - project and variant lineage

- The existing dormant `projects` table is now active through create, list,
  rename and archive-capable API routes. No replacement project model was
  introduced.
- `designs.project_id` and `designs.parent_design_id` are nullable foreign-key
  columns applied idempotently at startup. Every existing design remains NULL
  and appears under Ungrouped; no migration guesses ownership or ancestry.
- A build validates that its project exists and is open and that its parent is
  an assembly design in the same project before starting OpenCASCADE work.
  Project and parent metadata do not enter the canonical geometry payload, so
  identical geometry still produces identical STEP bytes.
- The workspace opens one project scope at a time. A new project begins with a
  root document; each subsequent build records the currently opened design as
  its parent. Reopening an earlier variant and building creates a real branch.
- The lower tray is named Variants inside a project and Ungrouped builds for
  legacy records. Root and branch records carry explicit lineage indicators.

Gate evidence:

```text
docker compose exec backend pytest tests/test_schema_patches.py \
  tests/test_assembly_api.py::test_projects_can_be_created_renamed_and_listed \
  tests/test_assembly_api.py::test_assembly_build_persists_manifest_artifacts_and_gate_statuses -q
5 passed in 25.30s

docker compose exec backend python scripts/gate_phase15_auto.py
project root -> branch recorded; cross-project parent rejected
PASS - Phase 15 sections: backend ($0, offline)

python scripts\gate_phase15_auto.py --frontend-only
PASS - Phase 15 sections: frontend ($0, offline)
```
