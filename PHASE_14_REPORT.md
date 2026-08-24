# PHASE 14 REPORT — Designer Workspace

**Status: BUILT — auto gate PASS 2026-08-24 (both sections). Awaiting the
operator's visual gate (`gate_phase14_visual.md`).**

Directive (operator, via /goal 2026-08-24): library with thumbnails /
selectable viewport / contextual inspector / variant strip / contextual
actions, plus undo-redo, duplicate, hide-solo, swatches, saved views,
measurement, section plane, and side-by-side variants — "from *the system
can build a design* to *a designer can shape, judge, compare, and refine a
design with confidence*."

Plan: `PHASE_14_DESIGNER_WORKSPACE_PLAN.md`. Decision record: ADR-044.
New limits: LIMITATIONS.md §18.

## What was built

Backend (small, all proven by the gate):

- `assemble(..., return_solids=True)` — exposes the placed per-element
  solids it already computed; default return unchanged (Phase 6 callers
  safe, asserted).
- `app/geometry/scene_glb.py` — `scene.glb`: same geometry and
  tessellation constants as the preview GLB, one glTF node per element,
  node name == element_id, composed via trimesh (existing dependency).
  Written at build time next to `assembly.glb`; STEP and the fused GLB are
  byte-for-byte untouched.
- Routes: `GET /latest/scene.glb`, `GET /{id}/scene.glb` (lazy backfill —
  a pre-Phase-14 design regenerates its scene from the stored request on
  first read, 409 with real violations if config drift broke it),
  `GET /{id}.glb`, `GET /{id}/manifest`, `GET /designs?limit=`.

Frontend (React + three.js already pinned — zero new dependencies):

- `workspace/document.ts` — the design document (exact build-request
  shape) + undo/redo snapshot stack (cap 100).
- `workspace/WorkspaceViewport.tsx` — raycast selection via scene-GLB node
  names, per-element hide/solo, material tints, two-click measurement in
  mm, X/Y/Z section plane (clip planes also filter picking), camera pose
  capture/apply, PNG snapshot of the live frame.
- `workspace/PrimitiveLibrary.tsx` (registry-driven, schematic SVG
  thumbnails), `ScenePanel.tsx` (select/hide/solo),
  `InspectorPanel.tsx` (generated parameter forms with ranges + units,
  material swatches, joint editor with cycle-safe parent list),
  `HistoryStrip.tsx` + `CompareView.tsx` (variants, restore, 2-up
  compare), `DesignerWorkspace.tsx` (toolbar: Add · Duplicate · Build &
  validate · Render · Export · measure/section/frame/views; keyboard
  Ctrl+Z/Y, Delete, Esc), `appearance.ts` (identification colours,
  labelled as such).
- `App.tsx` — the Designer view replaces the Assembly view; stepper and
  status bar unchanged and still derived; the workspace stays mounted
  across view switches so document + undo history survive a detour to
  Brief/Council. AssemblyPanel retired; Cascade tool kept.

The honest contract, kept visible: the viewport shows the last BUILT
geometry; edits mark the workspace "UNBUILT CHANGES"; *Build & validate*
is the only bridge (ADR-044 §2). Render is disabled while dirty — it must
never render something other than what is on screen.

## Gate evidence (real output)

Geometry/API sections, run in the backend container
(`docker compose exec backend python scripts/gate_phase14_auto.py`):

```
[1/5] SCENE GLB WRITER — one named node per element, proven
scene.glb written: 74460 bytes, sha256 aad45df1564e494a…
named mesh nodes: ['basin_01', 'column_01', 'plinth_01']
  basin_01: 1012 vertices
  column_01: 1012 vertices
  plinth_01: 1012 vertices
ok — 3 elements, each a named node with geometry

[2/5] API ROUND-TRIP — build, then read the design back by id
built design efef6467-6dc8-4534-a19b-f91d8002e7ec (overall needs_input)
  GET …/scene.glb -> 200 model/gltf-binary
  GET …​.glb -> 200 model/gltf-binary
  GET …/manifest -> 200 application/json
  GET /api/geometry/assembly/latest/scene.glb -> 200 model/gltf-binary
  GET /api/geometry/assembly/designs -> 200 application/json
  listed: 3 elements, ['basin_round', 'sculptural_column', 'plinth'],
  status needs_input, 2420.3 kg

[3/5] LAZY BACKFILL — scene.glb deleted, GET regenerates it
regenerated nodes: ['basin_01', 'column_01', 'plinth_01']
ok — regenerated scene has the identical node set

[4/5] FUSED ARTIFACTS UNTOUCHED — determinism + back-compat
STEP sha256 build 1: 7e5d3adccbe871f5…
STEP sha256 build 2: 7e5d3adccbe871f5…
ok — byte-identical STEP across rebuilds (Rule 5 intact)
ok — assemble() default return shape unchanged (Phase 6 callers safe)

PASS — all sections that ran passed at $0 with no network
```

(The `needs_input` overall status is correct: the gate build supplies no
intake, so hydraulics/overturning honestly report missing site facts —
exactly the Phase 8 behaviour.)

Frontend section, run on the host
(`python scripts\gate_phase14_auto.py --frontend-only`):

```
[5/5] FRONTEND BUILD — tsc strict + vite, offline
  ✓ built in 980ms
ok — typecheck and production build pass
PASS — all sections that ran passed at $0 with no network
```

The gate states in its verdict which sections a given run covered; full
coverage is the two commands above (documented in the gate header and
CLAUDE.md).

## PHASE 14 GATE: PASS (auto, 2026-08-24)

Auto gate: **PASS** (2026-08-24, both environments, $0, offline).
Visual gate: **AWAITING OPERATOR** — `gate_phase14_visual.md`, ten
sections with expected observations, including the measurement
sanity-check against the basin's declared 2000 mm diameter.

## For the operator

```powershell
cd C:\Users\buroo\luxuryform
docker compose up --build -d          # backend AND frontend images changed
# optional, for the Render button:
docker compose --profile render up -d render-worker
```

Then open http://localhost:5173 and walk `gate_phase14_visual.md`.

---

## Amendment — Phase 14b: window audit + Blender-familiar controls (2026-08-24)

Directive: "check every window design, then make them easy to use for
designers, like Blender." Audit table and keymap rationale:
`PHASE_14B_BLENDER_UX_PLAN.md`; decisions: ADR-046; new limits:
LIMITATIONS.md §18 addendum.

Added, all frontend-only (no backend files touched, container suite
unaffected):

- **Viewport:** MMB orbit + Shift+MMB pan alongside LMB; 1/3/7 view keys
  with Shift opposites; `5` orthographic ⇄ perspective (two cameras, the
  perspective pose is the single truth); `.` frame-selected keeping the
  current angle, `Home` frame all; a clickable axis gizmo positioned per
  frame from the camera quaternion; a Blender-status-bar-style mouse-hint
  line.
- **Outliner:** double-click / F2 inline rename with joints re-pointed
  atomically and UI state remapped only on a valid rename.
- **Keys:** Shift+D duplicate, H hide, Alt+H unhide all, `/` solo, X
  delete, T/N rail collapse (persisted), `?` keymap card. The map is
  active only while the Designer view is shown.
- **Discoverability:** every toolbar tooltip names its shortcut; the `?`
  card is the reference; the keymap card states why G/R/S do not exist
  (joints + parameters are the only honest editing path, ADR-044).

## PHASE 14B GATE: PASS (auto frontend section, 2026-08-24)

`python scripts\gate_phase14_auto.py --frontend-only` (tsc strict + vite):

```
[5/5] FRONTEND BUILD — tsc strict + vite, offline
  ✓ built in 749ms
ok — typecheck and production build pass
PASS — all sections that ran passed at $0 with no network
```

Visual gate awaiting the operator: `gate_phase14b_visual.md` (four
sections: discoverability, navigation, outliner editing, panels).
