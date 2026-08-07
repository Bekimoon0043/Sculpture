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

## 5. Phases 3–7 are not fully built yet

**CLOSED phases (no longer limitations):** Phase 1 (gate PASS 2026-08-01)
and Phase 2 (gate PASS 2026-08-04 — cascade primitive, STEP/GLB export,
determinism PROVEN cross-machine, viewport framing; see PHASE_2_REPORT.md).
Phase 2's scope limits are documented in §8 below, not here.

Not present in this repository, by design (later-phase code is not created
early):

- **Phase 3 — IN PROGRESS.** Built (steps 1–3 of 5): schema v3
  (council_sessions / council_calls / design_specs / engineering_reviews /
  defect_lists / arbiter_decisions), the $0 fixture replay pipeline, the
  costing rates schema (`config/costing.yaml` template, operator fills the
  nulls), the Council orchestrator (offline-proven against a scripted
  dispatcher; live run is step 4), and cache-aware pricing (ADR-022:
  kimi/anthropic cache token classes priced separately at first-party
  rates), and the transcript UI (step 3: session list, per-call role cards,
  Arbiter decision card, cost rollup vs caps with cache-savings display;
  demo session replays the synthetic fixture at $0). NOT built yet:
  live session capture (step 4), split gate (step 5).
- **Phase 4** — the sandbox for AI-written geometry code (isolation level
  already fixed in ADR-005), Blender workers.
- **Phase 5** — validation gates (mesh, hydraulics, structure, fabrication)
  and the render → vision-critique → bounded-delta loop (ADR-007), including
  enforcement of `max_vision_iterations`.
- **Phase 6** — DesignDNA memory store and retrieval; full export suite.
- **Phase 7** — resumable job runner with kill-and-resume checkpoints.

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
- **No ray-based wall-thickness check yet.** The minimum-wall guarantee comes
  from the HARD CONSTRAINTS in `registry.py` (wall >= material minimum,
  enforced before any build), not from a measured ray-cast thickness
  analysis of the mesh. That check arrives with the validation-gate phase.
- **STEP determinism is proven for the canonical STEP export only.** GLB
  bytes, render outputs and any file with embedded metadata are NOT part of
  the byte-identity guarantee (see §2) — only STEP + parameter set are, and
  that is what the gate hashes.
- **The rebuild-time number [ADD-5] is pending operator hardware.** The
  frontend measures it live; the value in PHASE_2_REPORT.md is filled in by
  the operator from the viewport readout, on their machine — never estimated
  by us.
- **GLB tessellation is 1 mm deflection.** The preview mesh deviates from the
  exact B-rep by up to ~1 mm on curved surfaces; the volume cross-check
  (2% tolerance, both numbers printed) quantifies the effect. Fabrication
  always uses the STEP, never the GLB.
