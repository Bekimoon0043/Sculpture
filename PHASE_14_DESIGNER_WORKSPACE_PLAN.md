# Phase 14 — Designer Workspace

**Directive** (operator, 2026-08-24, via /goal): move the UI from "the
system can build a design" to "a designer can shape, judge, compare and
refine a design with confidence."

## The layout

```
┌──────────────────────────────────────────────────────────────────┐
│ topbar: brand · pipeline stepper (unchanged) · tools             │
├──────────────────────────────────────────────────────────────────┤
│ toolbar: Add · Duplicate · Build & validate · Render · Export    │
│          undo/redo · measure · section · saved views · frame     │
├───────────┬────────────────────────────────────┬─────────────────┤
│ LIBRARY   │            3D VIEWPORT             │ INSPECTOR       │
│ primitive │  selectable elements (click),      │ selected element│
│ catalog   │  hide/solo respected, section      │ parameters with │
│ with      │  plane, measurement overlay        │ ranges + units, │
│ thumbnails│                                    │ material        │
│ ───────── │                                    │ swatches, joint │
│ SCENE     │                                    │ ─────────────── │
│ element   │                                    │ Checks (gates)  │
│ list,     │                                    │ Export panel    │
│ hide/solo │                                    │                 │
├───────────┴────────────────────────────────────┴─────────────────┤
│ HISTORY STRIP: every build this session + persisted designs,     │
│ thumbnail · status · mass · click-to-restore · compare (2-up)    │
├──────────────────────────────────────────────────────────────────┤
│ statusbar (unchanged)                                            │
└──────────────────────────────────────────────────────────────────┘
```

## The honest contract the workspace keeps

The viewport shows the **last built geometry**, never a client-side
approximation of unbuilt edits. Editing the document marks the workspace
*dirty*; "Build & validate" is the only way pixels change. This is Rule 5
kept visible: the deterministic kernel draws, the UI only edits the
document the kernel will receive.

## Backend additions (small, all real)

The GLB today is one fused solid — nothing in it can be picked. Selection
needs per-element nodes, and the history strip needs to read past designs.

1. `assemble(..., return_solids=True)` also returns the placed per-element
   solids it already computes (assembly.py:319-324). Non-breaking keyword.
2. `app/geometry/scene_glb.py` — `export_scene_glb(solids, path)`: each
   element exported at the standard GLB deflections, composed into ONE GLB
   whose node names are the element_ids (via trimesh, already a
   dependency). Written at build time next to `assembly.glb`. The fused
   `assembly.glb` remains the package artifact; `scene.glb` is the
   workspace's pickable view of the same geometry.
3. New routes (routes_assembly.py):
   - `GET /latest/scene.glb`, `GET /{design_id}/scene.glb` — lazily
     regenerated from the stored request if missing (pre-Phase-14 builds).
   - `GET /{design_id}.glb`, `GET /{design_id}/manifest` — per-design
     reads (compare + restore need them; only `/latest/*` existed).
   - `GET /designs?limit=` — newest-first design list for the history
     strip: id, created_at, seed, primitives, element count, mass,
     overall validation status.

No geometry semantics change. STEP stays canonical and byte-identical.

## Frontend (React + three.js already pinned — zero new dependencies)

- `workspace/document.ts` — the editable design document (exact build
  request shape) + undo/redo as a past/present/future snapshot stack.
- `workspace/WorkspaceViewport.tsx` — the ADR-020 viewport grown up:
  raycast selection via scene.glb node names, per-element hide/solo,
  material tints, two-click measurement (reported in mm — scene units are
  metres per ADR-020), X/Y/Z section plane (renderer clipping), camera
  pose capture/apply (saved views), PNG snapshot (history thumbnails).
- `workspace/appearance.ts` — material_id -> display colour. Materials
  have NO appearance data in the backend (materials.yaml is engineering
  numbers), so this is an explicit, labelled visual-identification map,
  not a render claim.
- `workspace/PrimitiveLibrary.tsx` — registry-driven catalog; schematic
  SVG thumbnails per primitive (drawn, not rendered — labelled as such).
- `workspace/ScenePanel.tsx` — element list: select, hide, solo.
- `workspace/InspectorPanel.tsx` — parameters with min/max/unit from the
  registry, material swatches, joint editor (type, parent, offsets),
  duplicate/delete. Below it the existing Validation and Export panels.
- `workspace/HistoryStrip.tsx` + `CompareView.tsx` — every build becomes
  a variant card (snapshot, status, mass); click restores its document;
  two checked cards render side-by-side viewports.
- `workspace/DesignerWorkspace.tsx` — owns the document history, build
  calls, selection/visibility state, measure/section/saved-view state,
  the contextual toolbar, and keyboard (Ctrl+Z/Y, Delete).
- App.tsx — the `assembly` view is replaced by `designer`; stepper and
  status bar unchanged. AssemblyPanel retires (the workspace subsumes it).

Duplicate placement: a stack_on duplicate is offset sideways by the
source's built bbox (from the manifest) so it does not land inside its
source; a concentric_insert duplicate cannot be offset (the joint model
has no slot for it) — the UI says so instead of letting the build fail
mysteriously.

## Gates

- `scripts/gate_phase14_auto.py` ($0, offline, non-interactive):
  1. build a 3-element assembly in-process; assert `scene.glb` exists and
     its GLB node names equal the element_ids (parsed from the binary);
  2. per-design routes (`/{id}.glb`, `/{id}/manifest`, `/{id}/scene.glb`,
     `/designs`) return the design;
  3. lazy backfill: delete scene.glb, GET regenerates it identically
     (same node set);
  4. fused assembly.glb byte-unchanged by this phase (STEP sha asserted);
  5. frontend typecheck+build (`npm run build`) passes offline.
- `gate_phase14_visual.md` — operator checks: select/hide/solo, measure a
  known dimension, section plane, undo/redo, duplicate, swatches, saved
  views, history restore, 2-up compare, render action.

## Out of scope (LIMITATIONS.md entries)

- No element rotation — the placement model is joints + translation only.
- No live preview while dragging parameters — every build is a full OCCT
  fuse + gate run (seconds); the workspace is explicit-build by design.
- Library thumbnails are schematic SVG, not rendered geometry.
- Material swatch colours are UI identification only.
