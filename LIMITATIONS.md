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

  **Owner ruling 2026-08-28 (ADR-060): slice-D-class free-form capability
  is RELEASE-BLOCKING for Production v1.** Complicated amorphous, organic,
  mesh-like sculpture design is a primary product requirement. The live
  demo proved the workflow on the existing ten-primitive library only;
  amorphous design GENERATION is unproven — what exists today is
  polygon-mesh EXPORT (GLB/STL/OBJ) of solids the kernel already built,
  which is not the same capability. Discovery is slice PR-2.5 (NEXT.md
  §2), blocked on operator input B-11 (3–5 reference designs, intended
  materials/fabrication processes, sculpting-controls ruling). No
  construction approach — BREP, procedural/implicit, mesh-native, or
  reference-mesh fitting — is preselected before that evidence exists.
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

**Update 2026-08-27 (slice C2, ADR-056):** segmentation is BUILT, so two
of the three driverless lines now have real drivers. `costing.yaml` is at
`2026-08-v2` and the rate card is **39 null entries, up from 33** — a
per-material `seam` rate (4) plus `install.truck_payload_kg` and
`install.modules_per_trip`. That growth is the price of two lines moving
from "ours to build" to "yours to supply".

- **The rate card is empty.** 39 null entries in `config/costing.yaml`. Every
  one is named by `GET /api/costing/rate-card` and by the BOM itself. No cost
  is computed from a null rate and none is defaulted to zero, so **no real
  design can produce a total today** — the gate proves the machinery is
  honest about that, not that a client-ready quote exists.
- **ONE cost line still has no DRIVER — and segmentation is not what it is
  waiting for.** `material_purchase` when `buy_price` is quoted per slab or
  sheet needs two things neither of which segmentation provides:
  `materials.yaml` records `stock_size_mm` as a length and a width with **no
  thickness**, so a stock volume cannot be formed; and nesting a formed
  shell onto flat sheet needs the surface UNROLLED, which the kernel does
  not do for a doubly-curved revolve. The BOM's blocker text names both.
  (`seam_welding` and `install_transport` were on this list until slice C2
  and are now `missing_rate` — the operator's number, not our code.)
- **Consequence for filling in the rate card**: basalt is quoted `per: slab`
  and 316L `per: sheet` in the template, and neither unit is computable.
  **Quoting basalt per m3 or per kg makes the largest line on the BOM work
  immediately** — this is unchanged by slice C2 and is still the single
  biggest win available.
- **The seam rate exists as of `costing.yaml` 2026-08-v2**, per material,
  quoted `per: m` (the seam RUN) or `per: m2` (the bedded FACE). Both
  drivers are measured off the real cut faces; the unit decides which one
  bills, so the platform never guesses which the workshop means.
- **The budget constraint binds at the BOM boundary**, not inside
  `registry.validate_params` (ADR-031 records why: the sandbox has no rate
  card and the geometrist has no rates in its prompt). An over-budget design
  is refused with real numbers and cannot be exported as a quote; it is not
  refused at geometry-build time.
- ~~**Crane pick weight equals total mass**~~ — **DISCHARGED 2026-08-27
  (slice C2).** On the assembly path the pick weight is the heaviest
  MODULE, measured. A 13.7-tonne stacked fountain now quotes a 2,375 kg
  pick. On the single-solid Phase 2 path it is still the whole mass, which
  is correct — one fused solid is lifted as one piece — and the driver
  still records `monolithic` so which case you are in stays visible.
- **Costing keys on ONE material.** A mixed-material assembly is refused
  with HTTP 409 naming every material and its elements, rather than priced
  at whichever material reached the report first. Per-element costing is
  the costing tie-off (NEXT.md W-7).
- **Two latent defects were found by making the assembly path work, both
  now fixed and regression-tested** (ADR-056): `GET /api/costing/bom/{id}`
  returned HTTP 500 for every assembly ever built, because an assembly
  stores an `AssemblyValidationReport` (no `material_id`, no single
  `mass_kg`) and the route parsed every stored report as a
  `ValidationReport`; and `GET /api/costing/bom/{id}.txt` — the rendered
  document handed to a client — returned 404 for every design, because it
  was registered AFTER `/bom/{design_id}` and the greedy path parameter
  swallowed the `.txt`.

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
  cantilever check. ~~Segmentation against `max_module_m` is NOT built~~
  — **BUILT 2026-08-27, slice C2 (ADR-056); see the block below.**

- **Slice C2 scope limits (2026-08-27, ADR-056).** An element over
  `fabrication.max_module_m` is now CUT into modules by the kernel, and
  both workshop limits bind on the modules rather than the element. What
  it deliberately does NOT do:
  - **Only axis-aligned planar grids.** A round basin split three ways
    becomes a 3x3 waffle. A stone mason might cut RADIAL pie segments
    instead, and for axisymmetric vessels that is probably the better
    answer — it needs the operator's ruling on how the yard actually
    cuts, and is proposed as its own slice. Flagged as the slice's
    weakest decision in ADR-056 and in `gate_phase6c2_visual.md` §2.
  - **Planes are evenly spaced**, which minimises the heaviest module.
    A workshop buying fixed stock may prefer full slabs plus a remnant.
  - **`blade_fin_array` and `lotus_petal_array` are NOT segmentable** and
    are refused by name. They are already rings of discrete pieces on a
    hub, so saw planes fragment them: measured, a 24-blade array at a
    0.8 m limit yields 25 solids whose lightest is 0.9 kg against a
    heaviest of 2,685.7 kg. Their real decomposition — hub plus N
    separately-made blades — is not built; the count would be exact from
    `blade_count`, but the blade-root seam needs its own measurement and
    its own proof.
  - **No minimum-module (sliver) floor exists**, deliberately: every
    `planar_grid` shape measured produced sane masses, and inventing a
    threshold nobody derived would hide the case it was meant to catch.
    A too-small module is VISIBLE in the printed module masses.
  - **A grid over 256 predicted cells is refused** with the arithmetic
    rather than attempted. A guard against a runaway limit (a 6 m basin
    at 0.1 m predicts 17,500 cells), not an engineering bound.
  - **Segmentation is driven by `max_module_m` only.** With no module
    limit declared nothing is cut, each element is its own module, and an
    over-mass element is refused exactly as before — the platform will
    not invent the limit it would have cut to. `max_lift_kg` alone does
    not trigger a split.
  - **Per-axis limits are CONSERVATIVE (PR-1, ADR-059).** Since
    2026-08-28 each bbox axis binds on its own limit (the spec's
    `{x,y,z}`; a Designer scalar means a cubic envelope). Module
    ROTATION for transport is not modelled — a module that could legally
    lie on its side to fit the truck may be refused. Loud, never silent,
    and the safe direction; a rotation-aware packing check would be its
    own slice.
  - **Trip allocation is FEASIBLE, not the fewest possible (PR-4,
    ADR-067).** Since 2026-09-07 the transport line LOADS the trucks
    (first-fit-decreasing over the measured module masses, both limits
    checked unrounded, every trip printed with its modules, load and
    remaining capacity) instead of printing the old
    `max(ceil(mass/payload), ceil(modules/per_trip))` lower bound —
    which four 6 t modules at a 10 t payload disprove (4 real trips vs
    the bound's 3). What it still cannot do: the count is conservative,
    never proven lowest (a cleverer packing may save a truck — the BOM
    says "a deterministic conservative feasible allocation" and nothing
    more); the fleet is uniform (ONE `truck_payload_kg`, ONE
    `modules_per_trip` for the whole job — no mixed trucks, no partial
    hires); module DIMENSIONS are not packed (bed space is a slot
    count, not an area/length fit — the per-axis size limit above is
    what keeps a module truck-shaped); and designs whose manifests
    predate per-module mass records refuse the line with a rebuild
    instruction rather than allocating a partial load.
  - **Designs whose spec-declared `{x,y,z}` was collapsed to one number
    (built before 2026-08-28 through the fabrication loop) are flagged,
    never re-judged.** Their manifest read carries a live
    `module_limit_provenance: needs_input` naming the spec's true axes,
    and geometry-rebuilding operations (re-export, scene regeneration)
    refuse with the exact rebuild command. Designer-built scalar designs
    are deliberate cubic envelopes and are untouched.
  - **Plane order is not bit-exact.** The connected components and every
    engineering number are order-independent to better than 1e-9
    relative, but OCCT's split is not bit-identical under reordering
    (measured: 1666.6666666666677 vs 1666.6666666666667 mm). Production
    always cuts x-y-z; byte-identity is claimed and gated only for the
    same code path across processes. The STEP hash is untouched —
    segmentation cuts COPIES and never touches the fused solid.
  - **Designs built before 2026-08-27 carry no segmentation block.** They
    are not treated as monolithic (that would price a 9-module basin as
    one 11-tonne lift); the fabrication gate returns `needs_input` asking
    for a rebuild, and the BOM says the same. **Rebuild any older
    assembly once before quoting it.**
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
- ~~**The mapper speaks the slice A1 vocabulary.** Its alias table covers
  the four primitives; a Council spec using parameter names outside it
  fails loudly at fabrication (a repair digest naming the keys), and
  widening the table is a $0 edit. Slices B–D grow it with each primitive.~~
  **CORRECTED 2026-09-08 (PR-5, ADR-068):** `spec_mapper._ALIASES` covers
  TEN primitives (basin_round, plinth, sculptural_column, basin_rect,
  stepped_monolith, water_wall, torus_ring, blade_fin_array,
  lotus_petal_array, tiered_cascade — slices A1, B, C1). ~~The one it does
  NOT cover is `freeform_loop`: a Council spec cannot request the
  free-form primitive at all — no vocabulary, no alias, no mapping. That
  gap is FF-A3's, not a mapper defect; unknown parameter names still fail
  loudly at fabrication naming the keys.~~ **CORRECTED 2026-09-09 (FF-A3,
  ADR-069):** the mapper covers all ELEVEN primitives; `freeform_loop`'s
  13 registry keys (12 scalars + `material_id`) are each reachable by a
  spec-level name, the Designer index prints every primitive's vocabulary
  generated from the registry, and the Designer boundary now runs the
  mapper plus each primitive's own `validate()` before a spec is
  persisted — so unknown names, wrong units and out-of-range numbers are
  re-asked at design time instead of failing at a paid fabrication call.
  A ratio/fraction target takes a PLAIN number: a `{value, unit}` object
  on a ratio is refused (before FF-A3 a ratio in metres was silently
  multiplied by 1000 and a wrong unit passed through untouched). Count
  and enumeration targets (`tiers`, `steps`, `blade_count`,
  `petal_count`, `rim_treatment`) still accept a `{value, unit}` object
  and pass the unit through unchecked — recorded as D-27, not fixed here.
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

- ~~**Split-line feasibility is a count, not a plan.** An oversized element
  reports how many modules it would need and how many joints it carries. It
  does not compute where the split planes go — segmentation is Phase 6
  slice C.~~ **RETIRED 2026-09-08 (PR-5, ADR-068; the capability landed
  2026-08-27, slice C2, ADR-056):** the kernel CUTS an oversized element
  into numbered modules on an axis-aligned planar grid, measures every
  module's volume, mass and bbox, counts seams once per interface, and the
  lift and envelope checks bind on the MODULES (per axis since PR-1,
  ADR-059). What is still not modelled is in §10 (radial segmentation
  D-11, rotation for transport, trip packing by dimension).

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

  **Update 2026-08-27 (PR-0, ADR-057):** their SEALED manifest entries are
  now the constant status `excluded` whatever the render worker was doing at
  export time — the live `included`/`unavailable` status lives on the
  exports API only. This is what makes the package content digest
  independent of worker state; before it, two exports of one design during
  a worker-up run could seal different digests (D-9b).

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

## 19. The API has no authentication; loopback binding is the only lock (2026-08-27, PR-3, ADR-058)

- **There is no login, no token, no session, no user model.** Every API
  route — including the ones that read full Council transcripts and the
  ones that dispatch PAID provider calls — answers to anyone who can
  reach the port. This was true from Phase 1 and is recorded here now.
- **The only access control is that the ports answer on `127.0.0.1`
  alone** (PR-3): Docker publishes 8000 and 5173 loopback-only, so only
  processes on the operator's own machine can connect. `gate_pr3_auto.py`
  asserts the compose file AND the live sockets on every roster run,
  because a regression here is perfectly silent — localhost keeps working
  identically while the LAN quietly regains access.
- **LAN and remote access are unsupported, deliberately, with no
  documented enable path.** No override file or command ships. Access
  from another device may return only as part of a future slice that
  builds real authentication first, and that slice would rewrite this
  entry (docs/operator/11_network_privacy.md says the same in the
  operator's language).
- **Out of the gate's sight:** a manual `docker run -p` outside compose,
  and any reverse proxy or tunnel the operator runs themselves. Do not
  put one in front of the platform while this entry exists.

## 20. Spend-cap scope limits (2026-08-28, PR-2, ADR-061)

- **The $25/UTC-day cap is per DATABASE FILE, not per machine.** Every
  reservation, settlement and cap sum lives in one SQLite file; a process
  pointed at a different file (a test temp DB, a second data directory)
  gets full headroom — exactly the ADR-033 incident mechanics. The
  standing guards are the hermetic-env test rule (keys forced to empty
  strings) and the fact that every production path shares
  `data/luxuryform.db`. A machine-global cap would need a second shared
  store and is deliberately out of scope.
- **Reservation bounds are the conservative context-window fallback for
  ALL THREE providers** — none documents per-message framing overhead
  (checked first-party 2026-08-28), so no tighter prompt-based formula
  ships. The stated cost: a kimi-k3 call holds $3.268608 while in
  flight and refuses once its run has less headroom than that, even
  though its real cost would be cents. Over-reservation can refuse
  early; it can never overspend.
- **Uncertain holds require the operator.** A failed or dead attempt
  counts at its full bound FOREVER until
  `scripts/spend_admin.py resolve-hold` reconciles it to the
  console-verified amount (status `reconciled`; it keeps counting at
  that amount) — the provider consoles are the only truth for a dead
  call (ADR-033). Nothing expires or auto-clears; a day with several
  uncertain kimi holds can be legitimately, honestly exhausted.
- **Safety locks and halted scopes are sticky by design.** Only the
  audited `spend_admin.py` commands clear them; there is no API route
  and no UI button, deliberately — clearing a spend lock is an
  operator-only act.
- **The per-database cap also means the critique script's `--max-spend`
  layers via `min()` with the run cap, as before** — it narrows, never
  widens.

## 21. ~~Validation gates are ADVISORY at the export boundary~~ — CLOSED by LF-103A (2026-09-01, ADR-063), with stated residuals

The 2026-09-01 audit found that a FAILED design sealed the same
clean-looking LUXEXCHANGE package as a passing one, and that
`LayeredGateReport.blocking` was dead code. **LF-103A closed the export
boundary** (evidence: `gate_lf103a_auto.py` PASS, `tests/
test_export_boundary.py`, `tests/test_package_class.py`; operator
visual gate personally walked and signed PASS 2026-09-02, verbatim in
`gate_lf103a_visual.md`):

- **FAILED never packages.** The export POST refuses with HTTP 409
  naming the failing checks with real numbers, BEFORE any geometry work;
  the package builder itself raises `PackageRefused` (bypass closed);
  fabrication-capable downloads (STEP/BREP/STL/DXF/SVG — raw STEP is
  fabrication-capable, never "just viewing") refuse too. The viewport
  stream stays untouched (ADR-034), and mesh downloads stay served with
  a `DIAGNOSTIC-NOT-FOR-FABRICATION` filename.
- **Everything not proven clean seals as PRE-FABRICATION**: the download
  is named `…_PRE-FABRICATION.zip`, every `exports/` entry is marked in
  its own filename, the DXF/SVG drawings carry a printed
  NOT-FOR-CONSTRUCTION notice (the only formats where a visual in-format
  mark genuinely exists), and `ENGINEERING_WARRANT.txt` names every
  unresolved check and the professional input it requires. Marking is
  filename/entry-only — canonical bytes and the Phase 2 hash are
  untouched, and the package stays byte-reproducible.
- **CLEAN is currently unreachable in production, by design** (ADR-063):
  it requires all gates pass + `profile_signed_off` at validation time +
  one coherent profile/version basis + a shared `validation_basis` run
  identity that no persisted row carries yet + a geometry-hash match.
  The branch exists and is proven with signed fixtures; LF-102 must not
  make it reachable until the validation-run identity debt (D-24) closes.
- **Old packages fail closed as LEGACY_UNCLASSIFIED**: a zip sealed
  without a `package_class` never downloads as if clean — it refuses
  with the exact re-export action; the file on disk is never rewritten.

**What this deliberately does NOT close:**

- Validation rows still carry no cryptographic run identity (D-24) —
  the reason CLEAN stays builder-only.
- The budget check still binds only on the BOM route with
  `?budget_amount=`, and the sealed BOM is not budget-gated (D-19's
  remaining half; PR-6).
- The Phase 2 cascade path and build-time GLB/scene streams remain
  reachable without a package — cascade designs classify
  PRE-FABRICATION and their downloads are marked, but no gate refuses
  the viewport, deliberately.
- DesignDNA accept still refuses only `fail`, not `needs_input` — a
  separate ruling, out of LF-103A's scope.

## 22. Free-form amorphous sculpture: kernel feasibility probed; no user-facing free-form capability implemented

PR-2.5 discovery (2026-09-02/03, ADR-064; closed 2026-09-03 on
definitive image `52209e4a6eea` — 540 tests both worker states, full
roster green, discovery host gate 217/217) ran sandboxed probes against
the owner's B-11 references. **Discovery probes are evidence, not
product capability**: nothing free-form is reachable from a brief, the
Council, the Designer or the export pipeline, the ten-primitive
registry is unchanged, and the Master Scope audit score (31.6/100 at
`bfa5a77`) does not move on probe results.

What the probes established is recorded with verbatim numbers in
`PR2_5_FREEFORM_DISCOVERY.md`. The owner's independent visual review
(2026-09-03) ruled the probe forms **NOT reference-faithful** — the
probes prove operation/kernel feasibility, not reference-faithful
geometry; the fidelity gap is the implementation slice's burden under
the changed acceptance gate. What remains missing, honestly:

- ~~**No free-form primitive, spec vocabulary, API surface or Designer
  control exists.**~~ **PARTIALLY CLOSED by FF-A2 (2026-09-04,
  ADR-066): ONE free-form primitive exists** — `freeform_loop`, the
  ref-08 hollow-lens class, reachable from the Designer with scalar
  controls, built by the deterministic kernel, integrity-gated and
  **PRE-FABRICATION only**. What FF-A2 deliberately does NOT deliver:
  control-point editing (scalar parameters only — recorded unbuilt);
  ~~any brief/Council claim (the claim is Designer/spec → kernel);~~
  **FF-A3 (2026-09-09, ADR-069) widened this to: a typed brief through
  the Brief tab → a Council Design Spec naming `freeform_loop` with all
  12 scalars + `material_id` stated explicitly → the trusted mapper →
  the deterministic kernel — proven at $0 by fixture replay of a
  SYNTHETIC hand-authored Council session, which proves replay and
  pipeline compatibility only, NOT that an AI selected the primitive
  from prose. The claim "typed brief → Council selection → sculpture"
  is NOT made until one real live Council + fabrication demonstration
  (gate_ffa3_visual.md Step 6, separately cost-approved) has been run
  and recorded. **Attempted 2026-09-14 and NOT achieved:** the one
  authorized live session halted 46 seconds in — the openai researcher
  call succeeded ($0.007725), the parallel kimi call failed with a
  transient "Connection error.", its reservation went UNCERTAIN at the
  full $3.268608 cap-safe bound, and the retry's reservation was refused
  by the $5.00 run cap. Session `2a7d3e5b…` persisted ZERO Design Specs
  and zero arbiter decisions, so the Council never reached the Designer
  stage: it neither selected nor declined `freeform_loop`, and the
  demonstration did not reach the question. The fabrication attempt was
  not run. **No AI has yet chosen this primitive from prose, and the
  platform does not claim it has.** See D-28 for why the retry could not
  proceed within the cap. **Update 2026-09-15: D-28 is CLOSED (ADR-070) —
  the same retry now holds under $0.20 and fits under the $5 run cap —
  but Step 6 has STILL not been run; "no AI has chosen this primitive
  from prose" remains true until a cost-approved retry is executed and
  recorded.** **Owner ruling 2026-09-14: Step 6 remains NOT
  ACHIEVED, is never marked PASS, and real Council selection of
  `freeform_loop` remains UNPROVEN. FF-A3 closes only as "typed-brief/
  Council contract implemented and fixture-gated; live end-to-end
  selection blocked by D-28 and not claimed."** The kernel's measured robustness cliff (ADR-066
  decision 10) also bites parameter sets the primitive's validate()
  accepts: three of the six hand-authored alternatives first written for
  the fixture were REFUSED at build (negative inner-lens volume; a
  collapsed or split cavity corridor) and were replaced by sets that
  build — every refusal is loud and deterministic, never a corrupt
  solid, and the refused sets are recorded in ADR-069;**
  ref-11/ref-13/ref-14/ref-15/ref-16 classes (blocked or unstarted per
  their recorded findings); a verified wall (the modeled shell's
  measured minimum sits at the truncated tips and
  `geometric_wall_measurement` reports needs_input; the nominal 6 mm
  gauge is a prototype value, and `fabrication_wall_approval` +
  `forming_radius` are permanently unresolved professional inputs
  until given); per-module CAD export (segmentation is measured
  ANALYSIS, never a transportable-modules claim). The originally
  approved tube-annulus construction FAILED development and is
  preserved as evidence in ADR-066 — it is not capability. The original
  `rim_ratio` landmark (110 px/55 px = 2.0) was RETIRED as an automatic
  check by owner ruling 2026-09-05 and preserved as history in
  `ref08_landmarks.json`: its 55 px apex reading measured the
  reference's 3-D surface scoop, invisible to any front projection.
  The replacement `projected_side_to_apex_band_ratio` is derived
  exactly from the reference under the recorded instrument (122/139 =
  0.877698, band [0.7022, 1.0532]); the 3-D scoop/rim shaping remains
  a separate MANDATORY visual-gate comparison that no projection-metric
  pass claims to satisfy. Additionally,
  the kernel has a MEASURED robustness cliff on large twisted thin
  shells (ADR-066 decision 10): some in-range extreme combinations
  (measured: 5.0 m envelope with twist −90° at bow 600–900 mm; waist
  fraction 0.25) cannot be hollowed by the installed OCC booleans —
  they refuse loudly and deterministically at build (HTTP 422 with the
  real stage numbers), never build corrupt, and the measured cliff
  combinations are pinned as refusal tests. And rendering a
  freeform_loop hit a **570-second timeout** on this hardware during
  the FF-A2 visual walk (D-25): the dense free-form tessellation is
  heavy for CPU Cycles on the i7; visual gates permit viewport
  inspection, so nothing was invalidated, but free-form renders need a
  budget/mesh decision before Phase 10 or PR-9 rely on them.
- **B-11b — mesh/lattice ground truth — is OPEN and release-blocking**
  for any mesh-capability claim and for Production v1 (owner ruling,
  2026-09-02): none of the 16 supplied references shows an open mesh,
  wire lattice, perforated skin or cellular structure, and the import
  probe's generated blob deliberately does not stand in for one.
  Nothing mesh/lattice is specified, promised or scored until the owner
  supplies a real reference. **Update 2026-09-16 (MS-A1, ADR-071): the
  PERFORATED-SKIN class is now built and gated — `perforated_screen`
  (316L only, flat or single-curved, circle/hex through-hole grid) is
  a real, deterministic, integrity-gated primitive. B-11b stays OPEN
  for the OPEN-LATTICE class (wire cages, cellular structures): the
  owner reference is still required before that class is specified —
  procedural meshes still have no boolean machinery (PR-2.5 probes).**
- **GRC fabrication data is entirely FABRICATOR-INPUT-REQUIRED** —
  density, minimum shell thickness, reinforcement, panel size,
  connection details, mold limits. `config/materials.yaml` carries no
  GRC entry on purpose; probes used clearly-labeled non-engineering
  sample parameters for topology only and produced no mass, lifting,
  structural or fabrication claims for GRC.
- **316L total assembly mass is not computable until the armature is
  designed**; only skin-only figures exist, labeled non-engineering
  discovery estimates.
- **The 16 reference JPGs are operator-local and uncommitted** (owner
  amendment 1): git and docker both ignore them; the committed record
  is `briefs/freeform_references/reference_manifest.json` (hashes,
  roles) plus `REFERENCE_ANALYSIS.md`. The permanent roster gate stays
  reproducible without them; the operator's visual gate requires them.
- **Approach-(b) procedural meshes have no boolean/fusion machinery**
  in the installed stack (no CGAL/libigl/OpenVDB; scikit-image is not
  installed), and **approach-(c) imports prove transform/validate/
  re-serialize only** — where trustworthy artist meshes would come from
  is an open trust problem for the implementation ruling.
- **FF-A1 (2026-09-03, ADR-065) built the incomplete-mass truth model
  and the production `freeform_integrity_v1` stack — ACTIVE since
  FF-A2 (2026-09-04, ADR-066):** a `freeform_loop` design is the first
  real incomplete-mass, integrity-gated design. Every mass-dependent
  check (centroid, overturning, bearing, lift, crane, rigging
  ruled-out, costing, BOM, quote) refuses or reports needs_input on it
  BY CONSTRUCTION; there is deliberately no input contract that makes
  them pass — the complete armature contract (mass + centroid +
  per-module allocation, or a documented conservative worst case)
  remains FUTURE design work, owner-gated.
- **Minimum-thickness sampling is unavailable on the pinned image**:
  `trimesh.proximity.thickness` requires `rtree`, which is not
  installed (a download, so the operator's call — same class as D-7).
  The validator records the error honestly instead of a number; a
  free-form implementation slice needs either `rtree` or an
  alternative thickness check before thin-wall limits can bind.
