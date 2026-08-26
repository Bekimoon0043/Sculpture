# LIMITATIONS.md — What is NOT real yet, and what can never be

This list is honest on purpose (Rule 2: no fabricated capability). If
something here matters to a project, tell the technical lead before relying
on it.

---

## 1. DWG and SketchUp (.skp) export are not possible natively (ruling 5a)

- **DWG** is Autodesk's closed format. Our tooling writes **DXF** (which
  every CAD program opens). Real DWG requires a converter.

**Update 2026-08-21 (Phase 9A):** both now appear in every export manifest
with status `impossible` and this workaround text ships INSIDE the
LUXEXCHANGE package as `README_DWG_SKP.txt` — a fabricator reading the zip
offline no longer needs this file.
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

- **Phase 5** — the loop is BUILT, auto-gated, and has now been RUN LIVE
  (2026-08-24, ADR-045): three rounds against Claude Sonnet 4.5 and GPT-4o for
  $0.042916 measured, 5 agreed deltas applied, geometry rebuilt each round and
  measurably changed. `scripts/run_vision_critique.py` reproduces it.
  Enforcement of `max_vision_iterations` is wired to the budget.yaml value and
  the script refuses to exceed it.

  What is NOT yet established is how the loop behaves over MANY designs. One
  live run on one design proves the machinery converges; it does not prove the
  critique reliably improves a design, and the objective score is currently a
  thin composite (mass against handling limit). Treat the loop as working, not
  as validated design judgement.
- **Phase 6** — the primitive library (PHASE_6_PLAN.md). Slice A1 (assembly
  core + basin_round/plinth/sculptural_column, gate PASS 2026-08-20, ADR-032)
  is BUILT; slices A2 (AI + surfaces), B (rim treatments + fixtures),
  C (extrusion/array masses), D (free-form) are not. See §11 for what A1
  does not do. (DesignDNA and the full export suite, once listed under this
  phase, are re-homed by the 2026-08-19 completion plan: export suite after
  Phase 5, DesignDNA in Phase 7.)
- **Phase 7** — resumable job runner with kill-and-resume checkpoints;
  DesignDNA memory store and retrieval.

The missing L5-L8 work now starts in `PHASE_7_COMPLETION_PLAN.md` and is
split into follow-on plans through `PHASE_13_RECOVERY_HARDENING_PLAN.md`.
Phase 7 starts with assembly-manifest persistence because validation,
rendering, critique, export, and DesignDNA all need one shared design
artifact.

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

## 11. Phase 6 slice A1/A2 scope limits (2026-08-20, updated 2026-08-26)

**Update 2026-08-26 (slice A2, ADR-052):** the fabrication → design bridge
is BUILT and auto-gated. A passing assembly fabrication now persists a real
design record through the SAME helper the operator API uses (byte-identical
STEP and spec_hash across both paths, proven in `gate_phase6a2_auto.py`
§4), with lineage in both directions (`designs.generated_program_id`,
`generated_programs.manifest_json`) and the two-tier prompt surface
(measured: 11,267 → 8,144 chars for a 3-primitive spec). The 2026-08-21
"still missing" list is fully discharged: the primitive-agnostic API +
manifest persistence landed with Phase 7A, the frontend with Phases 14–15,
the bridge and two-tier surface with A2.

**Update 2026-08-21:** the Phase 4-to-6 bridge is now partial instead of
absent: the GEOMETRIST prompt exposes `registry.assemble`, the slice-A1
primitives, the assembly plan shape and the manifest return contract, and
the fabrication loop validates returned `assembly_manifest_v1` data with
`validate_assembly`. The Designer prompt now carries the live primitive
index and Design Specs are re-asked when `massing.elements[].primitive`
names a primitive outside the registry (2026-08-21). A trusted Slice A1
spec-to-assembly-plan mapper now converts `massing.elements` into
`registry.assemble` input with unit conversion and parent_id-derived joints.

What Phase 6 still deliberately does NOT do:

- **No live multi-primitive fabrication has happened yet.** The machinery
  is complete and gated at $0; the operator's live gate
  (`gate_phase6_visual.md` — brief → Council → fabrication → viewable,
  exportable assembly) has not been run. Until it passes, first-attempt
  success for assemblies is unmeasured.
- ~~Four primitives~~ — **TEN as of 2026-08-26**: slice B (ADR-054)
  added the rim treatments + nozzle fixture on `basin_round`; slice C1
  (ADR-055, `gate_phase6c_auto.py` PASS) added `basin_rect`,
  `stepped_monolith`, `water_wall`, `torus_ring`, `blade_fin_array`,
  `lotus_petal_array`. Free-form (`basin_elliptical`, `basin_spline`,
  `spline_loft_mass`) remains slice D.
- **Slice C1 scope limits (2026-08-26, ADR-055):** the rect and
  sculptural masses are NOT stack parents (their seats don't fit the
  circular bearing model — a child cannot stack ON a rect basin rim or a
  torus); rect footprints bear on their conservative INSCRIBED circle
  (may refuse a geometrically viable overhang — loud, never silent);
  arrays are one uniform ring (no mixed blade lengths, no spiral
  phyllotaxis); the lens petal is circular arcs, not a sculpted spline;
  `water_wall` has no notch weir (the ruling was asked twice and not
  given) and its 3x thickness floor is judgement pending a real
  cantilever check. **Segmentation against `max_module_m` is NOT built**
  — an oversized element is still refused, never split; that work moved
  to its own C2 slice beside the costing tie-off (W-7).
- **Slice B scope limits (2026-08-26, ADR-054):** weir crests are
  full-perimeter (360°) only — a partial-arc NOTCH weir breaks
  axisymmetry and needs a cut, deferred to slice C/D with its own proof;
  one nozzle bore size per basin (mixed bores refused naming the
  values); treatments and fixtures live on `basin_round` only; the
  weir/nozzle-to-network binding is enforced on the SPEC path (the
  mapper) — a Designer/API build may set them directly as the operator's
  explicit act. The drip-edge floor is derived as max(3,
  joint_overlap/3) because per-face tolerance is not stored in
  materials.yaml — a judgement stand-in the operator can correct.
- **Joints are a tree, and inserts are coaxial.** One root, `stack_on`
  (with lateral offset) and `concentric_insert` (axis-locked to the
  parent). Only `basin_round` accepts inserts. No side-by-side joints, no
  multi-parent bridging.
- **`min_feature_mm` and `min_internal_radius_mm` are recorded and
  config-validated but nothing consumes them yet** — the parameters they
  floor (rim profile radii, blade/petal thicknesses) arrive with slices B
  and C. Recorded now because the operator signed them now (ADR-032).
- **The mapper speaks the slice A1 vocabulary.** Its alias table covers
  the four primitives; a Council spec using parameter names outside it
  fails loudly at fabrication (a repair digest naming the keys), and
  widening the table is a $0 edit. Slices B–D grow it with each primitive.
- **Mixed-material assemblies validate but cannot be costed correctly
  yet:** costing keys on a single material_id (`build_bom`). Per-element
  masses ARE now persisted with every design record; the costing
  restructure that consumes them moved to the costing tie-off (W-7 in
  NEXT.md) — deliberately NOT built in A2 while the rate card (B-3) is
  all nulls, because every mixed-material total it produced would be
  untestable against reality.
- **A fabricated design lands in Ungrouped.** The bridge sets no
  project_id (Phase 15E projects are operator-scoped); grouping a
  fabrication into a project is a later, deliberate act.
- **Designs persisted before ADR-053 may hide a knife-edge seat.** The
  stack_on bearing floor (2026-08-26) refuses new builds whose seat is
  narrower than the material joint floor, but nothing retro-flags stored
  designs: `a3006a42` (basin ⌀2000 on hollow plinth ⌀2200/102 — a 2 mm
  lip under 1,550 kg) shows PASS badges in its stored validation and
  will only be refused, with the numbers and the fix, when it is next
  rebuilt. **Before quoting or fabricating any pre-2026-08-26 assembly,
  rebuild it once.**
- **A hollow plinth is an open tube, top and bottom** (A1 design,
  unchanged by ADR-053). Whether it should carry a closed top face — the
  pedestal a basin actually sits on — is an open operator ruling; adding
  one changes STEP bytes for hollow-plinth designs and so is not done as
  a quiet fix.

## 12. Phase 8 validation gate scope limits (2026-08-21)

The four gates are real, measured and provenanced (ADR-036). What they do
NOT do:

- **This is not finite-element analysis.** The structural gate is rigid-body
  statics: overturning about the footprint edge, ground bearing pressure,
  wall floors, load-path connectivity. It tells you whether a piece **tips**
  or overloads the ground. It does **not** tell you whether it cracks,
  buckles, fatigues, or how stress concentrates at a joint. A monumental
  piece still needs a structural engineer. The gate is named
  `structure_static_v1` so nobody reads it as more than it is.

- **Three thresholds ship empty and will report `needs_input` until you fill
  them in** — `design_wind_speed_m_s`, `allowable_bearing_kpa`,
  `overturning_safety_factor`. This is deliberate. No honest default exists
  for a site's wind map or its ground bearing capacity, and inventing one
  would be worse than reporting that we cannot check. See
  `docs/operator/07_validation_gates.md`.

- **No profile ships signed off.** Until `signed_off: true`, a breach of a
  profile threshold reports `warn`, not `fail`. Nothing is blocked on a
  number nobody has approved. Material limits from `materials.yaml` and
  workshop limits from the Design Spec are always binding.

- **~~The hydraulic gate depends on Phase 12~~ — RESOLVED 2026-08-22.**
  Phase 12 brief intake now supplies `water_context_v1` and the site facts,
  and the Phase 8b re-gate (`scripts/gate_phase8b_auto.py`) proves the
  hydraulic gate reaches a real pass/warn/fail verdict from a confirmed
  intake with no hand-injected context. One threshold still reports
  `needs_input` by design: `overturning_safety_factor` is a policy value a
  structural engineer signs, deliberately not intake-overridable (ADR-039).

- **Wind is a single static case.** One design wind speed, one drag
  coefficient, one silhouette from the bounding box. No gust dynamics, no
  vortex shedding, no directional wind rose, no shielding from surrounding
  buildings.

- **The silhouette is a bounding box.** Projected area for the wind
  calculation is the overall bbox width x height. For an open or lattice
  form this overstates the load — conservative, but not accurate.

- **Seismic loading is not checked at all.** Not modelled, not reported, not
  claimed.

- **Rigging is declared, never derived.** The gate names which elements
  exceed the manual handling limit and reports `needs_input` for their lift
  points. Geometry cannot invent where a rigger should attach.

- **Split-line feasibility is a count, not a plan.** An oversized element
  reports how many modules it would need and how many joints it carries. It
  does not compute where the split planes go — segmentation is Phase 6
  slice C.

## 13. Phase 9A export package scope limits (2026-08-21)

Ten formats are produced, hashed and reproducible (ADR-035, ADR-037). What
is NOT there:

- **Renders are available as of 2026-08-24** (Phase 9B, ADR-043): the
  Blender/Cycles render worker builds and produces four canonical views.
  Export formats that need Blender are still not wired to it — see the USD
  entry below. Historical note, kept because it dates the entries around it:
  the Blender/Cycles render worker was Phase 9B. Thumbnails
  are absent from the package and the manifest says so rather than shipping
  an empty `renders/` folder.

- **USD, USDZ, FBX and Alembic are produced, but are NOT inside the
  LUXEXCHANGE package** (2026-08-24, ADR-045). The render worker converts them
  (`docker compose --profile render up -d render-worker`); with the worker
  down they report `unavailable` naming that command.

  They are downloadable individually and deliberately not sealed into the ZIP.
  Measured: two conversions of the same design differ by 2 bytes (USDZ), 27
  (FBX) and 1 (ABC) — embedded creation timestamps. The package's promise is
  that the same design yields the same bytes, so a file that cannot honour it
  stays out. The manifest lists them under `omitted_non_reproducible` with a
  per-format `excluded_reason`, so nothing is silently missing.

- **DAE and 3MF report `unavailable`** naming the missing optional Python
  package (`pycollada`, `networkx`). Both are small, but adding them means a
  download on a connection that has cost this project more time than any
  code defect, so it is the operator's call — not something done behind his
  back. Add the name to `pyproject.toml` and rebuild if you want them.

- **DWG and SKP remain impossible** (see §1). Now reported as `impossible`
  with `README_DWG_SKP.txt` travelling **inside** the package.

- **The 2D drawing is two views, with no annotation.** A plan section at
  mid-height and a hidden-line front elevation, on PLAN / ELEVATION / HIDDEN
  layers. There are **no dimensions, no title block, no section marks, no
  weld or finish callouts, no tolerances**. It is a true drawing of the
  geometry, not an issued fabrication drawing. A draughtsman still adds the
  annotation.

- **One section plane, one viewpoint.** Mid-height plan, front elevation.
  No side elevation, no detail views, no additional sections.

- **Mesh-tier files are triangulated approximations.** OBJ, PLY and GLB
  carry `derived_from: assembly.glb`. Never machine or measure from them.

- **The BOM is included only when it can be computed.** Costing keys on a
  single `material_id`; a mixed-material assembly still cannot be costed
  correctly (§11), so the package records `costing_included: false` with the
  reason rather than shipping a wrong number.

- **Reproducibility is per (design, seed, image).** It holds across
  processes and across export runs on this machine and this image. Two
  different build123d or ezdxf versions may still differ — that is why
  `provenance.json` records tool versions, and why the Phase 9A gate
  re-checks reproducibility on every run.

- **Renders will never be byte-identical** (§2 still stands). The package
  determinism guarantee covers geometry, drawings and metadata.

## 14. Phase 11 DesignDNA scope limits (2026-08-22)

Accepted designs become searchable, explainable precedent (ADR-038). What it
does NOT do:

- **Retrieval is structured matching, not semantic search.** Filters are
  material, primitive, water, gate profile, height band and note text, all
  AND-ed. A brief phrased differently but describing the same thing will not
  match on meaning. Local embedding search is a possible later slice; it was
  deliberately not built first, because an operator must be able to see WHY
  a precedent surfaced.

- **The height band is a fixed ±50%.** Not tuned, not learned. A blunt
  instrument that is at least legible.

- **No precedent influences geometry automatically.** Precedents enter
  Council PROMPTS as context only. Nothing in the geometry engine reads
  DesignDNA, and no dimension is ever copied from a precedent by machine.

- **Injection is capped at three precedents** with no relevance threshold
  beyond the filters. A session with many similar precedents gets the three
  most specific matches, newest first — not necessarily the three best.

- **Precedent quality is not judged.** If the operator accepts a mediocre
  design with a glowing note, the Council reads that note as written. The
  library is memory, not taste.

- **Deleting frees the digest.** After a delete, the same deliverable can be
  accepted again deliberately. That is intended, but it means "delete" is
  not a permanent ban on a design.

## 15. Phase 12 brief intake scope limits (2026-08-22)

Typed contexts with per-field provenance (ADR-039), feeding the Phase 8
gates. What it does NOT do:

- **The parser is one call, not a conversation.** It fills what it can find
  and stops. It does not ask the client follow-up questions, and it does not
  re-read the brief after you edit the form.

- **The parser can misread.** It carries the quote it took each value from
  precisely because it can be wrong — check parsed fields against the quote
  before confirming. Nothing downstream distinguishes a correct parse from a
  plausible wrong one.

- **Climate normalization is partial.** Freeze risk, dust exposure and water
  availability are captured, but nothing CONSUMES them yet. No gate reads
  them; they are recorded for the Council and for later phases. Recorded
  honestly, not claimed as validated inputs.

- **Budget fields are captured but not bound to costing.** The costing layer
  still takes its budget separately; wiring the intake budget into the
  binding budget check is not done.

- **Only three site facts reach the gates** — altitude, design wind speed,
  allowable bearing. Everything else in the site section is context for the
  Council, not a gate input.

- **Intakes are not attached to projects.** Phase 15E projects now group
  assembly designs and preserve their parent lineage, but brief intakes remain
  a flat list and the newest is still the default. Project-level client/site
  context therefore has to be selected separately during validation.

- **The Council prompt uses the AUGMENTED brief.** The intake block and any
  precedent block are prepended and stored as the session's brief text, so
  the transcript shows exactly what the Council saw. Session brief text is
  therefore longer than what the operator typed.

## 16. Phase 13 slice A scope limits (2026-08-22)

Jobs, cost reconciliation and proven backup/restore (ADR-040). What is NOT
built — most of the original Phase 13 plan remains open:

- **There is no resumable job runner.** Export jobs record a checkpoint and
  a failure class, and re-running an export is byte-equivalent to the first
  run (proven in the gate), but nothing RESUMES a killed job from its last
  checkpoint. The kill-and-resume gate the Phase 13 plan describes is not
  built. Long Council and fabrication runs are still all-or-nothing.

- **Failure classes are assigned at one call site.** Only the export job
  classifies its failures. Council, fabrication and validation failures are
  still unclassified.

- **Nothing retries automatically.** The classes tell the operator what to
  do; no code acts on them.

- **The cost dashboard is read-only and unpaginated.** It sums every logged
  call every request. Fine for thousands of rows; it will need pagination
  long before it needs anything cleverer.

- **Backup is manual.** No schedule, no rotation, no off-machine copy. The
  operator runs the command.

- **Restore verification checks the NEWEST package only.** Table counts
  cover every table, but only one export package is re-verified. A corrupt
  older package would not be caught.

- **Restore does not swap the live store.** It unpacks and verifies into a
  fresh directory; moving it into place is the operator's deliberate step.

## 17. UI scope limits (2026-08-22)

The shell is a pipeline (ADR-041). What it does NOT do:

- **No visual verification was possible in this environment.** Markup is
  checked by server-rendering every component state and reading the HTML,
  and by a production build plus typecheck. Nobody has looked at the pixels.
  The visual gates exist for exactly this reason.

- **The layout is desktop-first.** Phase 15A reduced the Designer rails to
  220/330 px, made both collapsible and collapsed Recent Builds by default,
  but the other pipeline views remain unverified below about 1100 px.

- **No command palette.** (Phase 14 added undo/redo and Ctrl+Z / Ctrl+Y /
  Delete / Esc in the Designer Workspace; other views still have no
  shortcuts.)

- **The pipeline stepper does not enforce order.** It reports state and
  navigates; every view remains reachable at any time. Nothing stops the
  operator building before confirming an intake — the gates simply report
  needs_input, which is the honest consequence.

- **Precedent search has no pagination.** Every match renders.

- **The Council view still has no precedent toggle in the UI.** The API
  supports `use_precedents`, and the Library shows what would be injected,
  but the Council panel does not yet expose the switch.

## 18. Phase 14 Designer Workspace scope limits (2026-08-24)

- **No element rotation.** The placement model is joints plus translation;
  there is no rotation or scale anywhere in the request, manifest, or
  assembler. The inspector therefore offers none. Free-form placement
  beyond stack_on x/y offsets does not exist.

- **Draft geometry is not real-time.** Phase 15C now runs the real
  OpenCASCADE assembler after a 550 ms debounce and shows its named-node GLB
  without persistence or validation. The three-element gate model took about
  4.7 seconds on this machine. Superseded responses are ignored, but an OCCT
  calculation already running in the backend is not interrupted by the
  browser's aborted HTTP request. Render and export still require a matching
  full build.

- **The primitive library previews one item at a time.** The highlighted item
  is real kernel geometry built from live registry defaults, not a cached
  thumbnail. Moving focus starts another CPU-bound preview, so opening the
  palette does not pre-render every primitive concurrently.

- **Material swatch colours are identification only.** materials.yaml has
  no appearance data (colour/roughness/texture); the mapping lives in
  `frontend/src/workspace/appearance.ts` and says so in its tooltip. The
  only honest appearance output is the Phase 9B render.

- **The scene GLB doubles mesh storage per design** (fused assembly.glb +
  per-element scene.glb, ~70 kB each at current sizes). Accepted for
  pickability; both are outside the determinism contract (STEP is
  canonical).

- **Variant thumbnails, saved camera views and the remembered active
  design are per-browser** (localStorage), not server state. Clearing
  site data loses them; the design list itself always comes back from the
  server. Thumbnails exist only for builds whose geometry was actually on
  screen in that browser; a cleared or different browser falls back to
  opening the newest design in scope (2026-08-26).

- **Variants lists the newest 50 builds in one project**, un-paginated.
  Restoring and rebuilding records a real parent branch, but the compact tray
  is not a node graph and does not visualize grandchildren as a tree. Legacy
  records remain in a separate Ungrouped scope with NULL project and parent.

- **Measurement snaps to the tessellated surface** (the 1 mm-deflection
  preview mesh), not the exact B-rep — good to about a millimetre at
  fountain scale, which the tool's own numbers make visible. Fabrication
  measurements come from STEP in CAD, never from the viewport.

- **Section plane is a visual cut only** — it clips rendering and picking;
  it does not produce a drawing (DXF/SVG sections remain the export
  package's job).

- **Compare is two builds, not N.** Phase 15D synchronizes their cameras and
  lists changed stored request values, but it does not perform geometric
  deviation analysis, overlay meshes, or calculate surface-to-surface deltas.

- **Undo history is in-memory** (capped at 100 steps) and lost on reload;
  the durable history is the builds themselves in the strip.

**Phase 14b addendum (Blender-familiar controls, 2026-08-24):**

- **No grab/rotate/scale keys (G/R/S), by design, and stated in the keymap
  card:** elements are placed by joints and parameters — there is nothing
  free-form for a transform gizmo to move. This repeats the "no rotation"
  limit above from the interaction side.
- **Single selection only.** No box select, no multi-select, no A
  select-all; operations act on one element.
- **No command palette (F3).** The keymap overlay (`?`) is the
  discoverability surface for now.
- **Saved views do not store orthographic zoom** — a view saved while
  zoomed in ortho restores at the equivalent perspective distance instead.
- **View shortcuts use top-row digits** (1/3/7/5 with Shift variants), not
  only the numpad — the operator's laptop has none. Ctrl+digit is left to
  the browser (tab switching), which is why opposites are on Shift, unlike
  Blender's Ctrl.
