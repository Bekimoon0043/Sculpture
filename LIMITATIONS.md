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

## 5. Everything from Phases 2–7 is not built yet

Not present in this repository, by design (later-phase code is not created
early):

- **Phase 2** — geometry engine (build123d/OpenCASCADE), primitive registry,
  STEP/STL/GLB export, determinism hash gate.
- **Phase 3** — the AI council orchestrator (Researcher, Designer,
  Geometrist, Engineer, Critic, Arbiter roles from `config/council.yaml`),
  parallel dual-provider runs, Arbiter decision records.
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

## 7. Offline test transports mirror an ASSUMED SDK response shape

The offline test suite (`tests/conftest.py`: `InjectedAnthropicTransport`,
`InjectedOpenAITransport`) uses **hand-constructed** response objects — mocks
that pretend to be a provider's SDK client. They mirror the anthropic/openai
SDK response shape (content blocks / choices / usage) **as assumed, not as
verified against a real API response**.

Consequence: if a real SDK response shape differs from the assumption, the
offline suite **passes while production fails**. This limitation is retired
only by a fully green live Phase 1 gate — the gate exercises the real SDKs
against the real endpoints. Until that run passes, treat the
offline suite as proof of the dispatch path *around* the SDK call, never as
proof of the SDK call itself.

**Progress 2026-08-01 (operator's live gate):** anthropic and openai passed
BOTH text and vision live; kimi passed vision live. These live calls validate
the assumed SDK shapes for those paths. Remaining unverified path: kimi text
(a 400 parameter-validation response already proves the request/response
plumbing reaches the API correctly — the failure was a fixed-temperature
constraint, not an SDK shape mismatch).

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
