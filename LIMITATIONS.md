# LIMITATIONS.md — What is NOT real yet, and what can never be

This list is honest on purpose (Rule 2: no fabricated capability). If
something here matters to a project, tell the technical lead before relying
on it.

---

## 1. DWG and SketchUp (.skp) export are not possible natively (ruling 5a)

- **DWG** is Autodesk's closed format. Our tooling writes **DXF** (which
  every CAD program opens). Real DWG requires a converter.
- **.skp** (SketchUp) has no working open-source writer anywhere. We cannot
  produce .skp files. SketchUp Pro opens our STEP/DXF/OBJ files directly.

**Operator workaround for DWG (one-time setup, ~10 minutes):**

1. Download the free **ODA File Converter** from
   https://www.opendesign.com/guestfiles/oda_file_converter and install it
   with the default options.
2. When a fabricator asks for DWG: export the design as **DXF** from
   LuxuryForm, then open ODA File Converter, choose the DXF file, set the
   output type to the DWG version the fabricator asked for, and press
   Convert. Send the resulting .dwg.

**Operator workaround for SketchUp:** send the fabricator the **STEP** (or
DXF/OBJ) file and this instruction: *SketchUp Pro → File → Import → choose
the STEP/DXF/OBJ file.* Tested import path; no .skp needed.

## 2. Renders are not byte-identical (ruling 5b / Amendment 1)

The determinism guarantee covers **canonical geometry (STEP + parameter
set)** only: same Design Spec + same seed + same pinned Docker image =
byte-identical geometry. Renders (Blender/Cycles images, GLB files with
embedded metadata, GPU denoisers) are reproducible within visual tolerance,
never byte-for-byte. Every exported artifact records the tool versions that
produced it.

## 3. A GPU is optional, never required (ruling 5c)

Rendering (Phase 5) auto-detects hardware. With no supported GPU, critique
images render on the CPU at reduced samples (slower but identical in
content), and final renders run as explicitly long jobs. The Phase 5 gate
passes on a machine with no GPU.

## 4. Token prices must be verified by the operator (ruling 5d)

`config/pricing.yaml` ships with published list prices as of 2026-07
(`pricing_version: "2026-07-v1"`). Providers change prices without notice.
**Before trusting any cost number**, check the three providers' price pages
and update the file (bump `pricing_version` when you do). Every logged call
records which pricing version computed its cost, so stale numbers can always
be identified — but they are still stale until you update them.

## 5. Phases 5–7 are not fully built yet

**CLOSED phases (no longer limitations):** Phase 1 (gate PASS 2026-08-01),
Phase 2 (gate PASS 2026-08-04 — cascade primitive, STEP/GLB export,
determinism PROVEN cross-machine, viewport framing; see PHASE_2_REPORT.md),
and Phase 3 (gate PASS 2026-08-07 — the AI Council: schema v3, $0 fixture
replay, the orchestrator with strict-JSON validation and re-ask, audited
retries and degraded-session resilience (ADR-023), cache-aware pricing
(ADR-022), cache-break prompts (ADR-024), transcript UI, live machinery,
split gate; first live session measured $0.843842 against a $1.15 estimate;
see PHASE_3_REPORT.md), and Phase 4 (gate PASS 2026-08-17 — the fabrication
loop: the GEOMETRIST writes parametric build123d code executed only in the
ADR-005 sandbox, AST gate, bounded repair, full spec→program→artifact
lineage; the operator's own brief produced a watertight 2.6 m basalt
cascade passing the Phase 2 validation gate on the FIRST attempt for
$0.046777; see PHASE_4_REPORT.md). Phases 3 and 4 scope limits are in their
own reports and in §9 below, not here.

Not present in this repository, by design (later-phase code is not created
early):

- **Phase 5** — validation gates (mesh, hydraulics, structure, fabrication)
  and the render → vision-critique → bounded-delta loop (ADR-007), including
  enforcement of `max_vision_iterations`.
- **Phase 6** — the primitive library (PHASE_6_PLAN.md). Slice A1 (assembly
  core + basin_round/plinth/sculptural_column, gate PASS 2026-08-20, ADR-032)
  is BUILT; slices A2 (AI + surfaces), B (rim treatments + fixtures),
  C (extrusion/array masses), D (free-form) are not. See §11 for what A1
  does not do. (DesignDNA and the full export suite, once listed under this
  phase, are re-homed by the 2026-08-19 completion plan: export suite after
  Phase 5, DesignDNA in Phase 7.)
- **Phase 7** — resumable job runner with kill-and-resume checkpoints;
  DesignDNA memory store and retrieval.

## 6. ~~Provider vision failures found by the gate~~ — RETIRED 2026-08-01

All three providers (anthropic, openai, kimi) PASSED the live vision section
of the Phase 1 gate on the operator's machine. Amendment 5 is fully
satisfied; this entry is retired. (Section numbers are preserved so existing
references to §7 stay valid.)

## 7. ~~Offline test transports mirror an ASSUMED SDK response shape~~ — RETIRED 2026-08-07

**RETIRED (live-verified, operator run 2026-08-07).** The operator ran
`scripts/live_verify_providers.py` against their real account. Verbatim
results, matching the offline transports exactly:

- `[kimi]` top-level keys = choices, created, id, model, object,
  service_tier, system_fingerprint, usage
- `[kimi]` choices[0].message keys include `content`; content returned `'OK'`
- `[kimi]` usage keys = cached_tokens, completion_tokens,
  completion_tokens_details, prompt_tokens, prompt_tokens_details,
  total_tokens
- `[openai]` message keys include `content` (gpt-4o present in
  models.list(): TRUE, 124 models)
- `[anthropic]` content block types = ['text']; usage includes
  cache_creation_input_tokens and cache_read_input_tokens
  (claude-sonnet-4-5 present: TRUE, 10 models)

All six paths (3 providers x text/vision) are now verified against live
responses rather than assumed. The transports in `tests/conftest.py` were
updated to include the live-verified cache usage fields (ADR-022), and the
kimi/anthropic providers now SPLIT cache-token classes for pricing (see
DECISIONS.md ADR-022). The historical text of this limitation is preserved
in git history (section numbers are never reused).

---

## 8. Phase 2 scope limits (what the geometry engine does NOT do yet)

- **Single primitive only.** The tiered-cascade fountain is the ONLY
  registered primitive. No sculpture lofting, no custom profiles (Phase 4+).
- **Mesh preview, not photoreal.** The viewport shows the tessellated GLB
  with simple lighting. Renders (Blender/Cycles) are Phase 5.
- **No ray-based wall-thickness check yet.** The wall guarantee comes
  from the HARD CONSTRAINTS in `registry.py` (wall inside the selected
  material's min/max envelope from materials.yaml, ADR-027, enforced
  before any build), not from a measured ray-cast thickness
  analysis of the mesh. That check arrives with the validation-gate phase.
- **STEP determinism is proven for the canonical STEP export only.** GLB
  bytes, render outputs and any file with embedded metadata are NOT part of
  the byte-identity guarantee (see §2) — only STEP + parameter set are, and
  that is what the gate hashes.
- ~~The rebuild-time number [ADD-5] is pending operator hardware~~ —
  **CLOSED 2026-08-04**, measured by the operator on their machine: 1400 ms
  viewport / 1170 ms server, recorded in PHASE_2_REPORT.md. (This entry
  stayed open in error until 2026-08-17.)
- **GLB tessellation is 1 mm deflection.** The preview mesh deviates from the
  exact B-rep by up to ~1 mm on curved surfaces; the volume cross-check
  (2% tolerance, both numbers printed) quantifies the effect. Fabrication
  always uses the STEP, never the GLB.
- **Watertightness is only meaningful after `merge_vertices()`.** The GLB
  exporter writes one mesh patch per B-rep face with duplicated seam
  vertices, so a raw `trimesh.load()` reports EVERY build — including the
  Phase 2 canonical one — as not watertight. `validate_mesh` dedupes
  coincident vertices first (no vertex moves, no face changes) and is the
  only honest place to read this number from (ADR-029 method note).

---

## 9. Phase 4 scope limits (what the fabrication loop does NOT do yet)

- ~~One wall parameter serves the basin, the dishes AND the column~~ —
  **COLUMN HALF RETIRED 2026-08-20 (slice A1, ADR-032):** `column_wall_mm`
  now exists, defaults to `basin_wall_mm`, and hard constraint 4 reads it —
  the geometrist no longer has to thin the Council's basin wall to satisfy
  a column constraint. STILL TRUE: the basin and the DISHES share
  `basin_wall_mm` (they are drawn from the same profile family). Until a
  live fabrication demonstrates the model using the split parameter, keep
  checking fabricated wall values against the Design Spec before quoting.
- **The repair loop is so far diagnostic, not corrective.** Across four
  live runs, rounds 2 and 3 have never produced a pass; every success came
  at attempt 1. The failure digests have been valuable — they found three
  real defects — but no repair round has yet rescued a run.
- **First-attempt success rests on one post-fix data point.** One run
  passing at attempt 1 is not a rate. PHASE_4_REPORT.md states this
  plainly; the table extends with the next live fabrications.
- **Material fall-gap floors and wall envelopes are WORKSHOP values**, set
  by the fabricator and tunable in materials.yaml (ADR-027, ADR-029). They
  are not citations of an external standard, and no standard was fetched to
  set them.
- **The scratch mount is never reaped.** `data/geo_scratch/` accumulates one
  directory per sandbox job, holding the generated program and its result.
  Nothing deletes them. Harmless today (kilobytes), and useful for
  forensics, but it is not a cleanup story yet.
- **The synthetic demo Council session is indistinguishable from a real
  one** in the session list: `54e12d62` shows `completed` with
  `total_cost_usd $1.2624` although no API call was ever made (it has zero
  `ai_calls` rows — which is why budget enforcement is unaffected, ADR-003).
  Any spend figure read from `council_sessions` rather than `ai_calls`
  overstates by that amount.

---

## 10. Costing layer scope limits (2026-08-17)

The engine is built, gated and honest. What it cannot yet do splits into two
piles, and the BOM says on every line which pile a gap belongs to.

- **The rate card is empty.** 33 null entries in `config/costing.yaml`. Every
  one is named by `GET /api/costing/rate-card` and by the BOM itself. No cost
  is computed from a null rate and none is defaulted to zero, so **no real
  design can produce a total today** — the gate proves the machinery is
  honest about that, not that a client-ready quote exists.
- **Three cost lines have no DRIVER yet — ours to build, not a missing
  rate**: `material_purchase` when `buy_price` is quoted per slab or sheet
  (needs nesting into `stock_size_mm`), `seam_welding` (no seams until there
  are modules) and `install_transport` (a trip count needs a module count).
  All three need segmentation against `fabrication.max_module_m` — Phase 6.
- **Consequence for filling in the rate card**: basalt is quoted `per: slab`
  and 316L `per: sheet` in the template, and neither unit is computable
  today. **Quoting basalt per m3 or per kg makes the largest line on the BOM
  work immediately**; quoting per slab defers it to segmentation.
- **There is no seam rate in costing.yaml v1.** One is needed when
  segmentation lands.
- **The budget constraint binds at the BOM boundary**, not inside
  `registry.validate_params` (ADR-031 records why: the sandbox has no rate
  card and the geometrist has no rates in its prompt). An over-budget design
  is refused with real numbers and cannot be exported as a quote; it is not
  refused at geometry-build time.
- **Crane pick weight equals total mass** because every design today is one
  fused solid. It becomes the heaviest ELEMENT once assemblies exist
  (Phase 6); the driver records `monolithic: true` so the change is visible.

---

## 11. Phase 6 slice A1 scope limits (2026-08-20)

The assembly core is built and gated offline. What A1 deliberately does
NOT do:

- **The AI cannot use any of it yet.** Slice A2 wires the spec→plan
  mapping, the two-tier prompt surface, the designer index and spec
  validation. Today `registry.assemble` is reachable by generated code in
  principle, but the GEOMETRIST's prompt still documents only
  `cascade_fountain` — a live fabrication still produces a single cascade.
- **Four primitives.** `tiered_cascade`, `basin_round`, `plinth`,
  `sculptural_column`. Rim treatments and nozzle fixtures are slice B;
  extrusion/array masses slice C; free-form slice D.
- **Joints are a tree, and inserts are coaxial.** One root, `stack_on`
  (with lateral offset) and `concentric_insert` (axis-locked to the
  parent). Only `basin_round` accepts inserts. No side-by-side joints, no
  multi-parent bridging.
- **`min_feature_mm` and `min_internal_radius_mm` are recorded and
  config-validated but nothing consumes them yet** — the parameters they
  floor (rim profile radii, blade/petal thicknesses) arrive with slices B
  and C. Recorded now because the operator signed them now (ADR-032).
- **The API and frontend are still cascade-shaped.**
  `/api/geometry/cascade/*` and the viewport panel know nothing of
  assemblies; the primitive-agnostic surfaces are budgeted into A2.
- **The assembly manifest is not yet persisted** — designs/
  generated_programs gain manifest columns with A2, when fabrication can
  actually produce one.
- **Mixed-material assemblies validate but cannot be costed correctly
  yet:** the persisted ValidationReport carries one material_id; per-
  element mass exists only in the (unpersisted) manifest. Reconciled in A2
  alongside persistence.
- **The operator's visual gate arrives with A2**, when there is something
  to look at in the viewport; A1's gate is the $0 auto script only.
