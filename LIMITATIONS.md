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

## 6. Provider vision failures found by the gate

The Phase 1 gate sends a real test image to each provider's vision endpoint.
If a provider's vision call fails, the gate prints the raw error and an
ACTION line telling you to record it here.

**Operator: if the gate reports a vision failure, replace the line below with
what the gate printed (provider, model, and the exact error), and date it.**

- _(no vision failures recorded yet — fill in from gate output if one appears)_
