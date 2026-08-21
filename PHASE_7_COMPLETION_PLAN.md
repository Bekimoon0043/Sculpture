# PHASE_7_COMPLETION_PLAN.md - Missing L5-L8 Completion Phase (2026-08-21)

This phase exists to finish the capabilities that are still missing from the
L1-L8 target architecture without pretending they already exist.

It starts from the current repository state:

- L1 Brief Intake: partial, enough for Council sessions, but not a polished
  plain-language intake product with site, climate, culture, and budget
  normalization.
- L2 AI Council: built.
- L3 Design Spec: built around strict JSON validation.
- L4 Geometry Engine: built, with Phase 6 Slice A1 assembly primitives and a
  trusted spec-to-assembly mapper now started.
- L5 Validation Gate: partial. Mesh/watertight validation exists; structural,
  hydraulic, and fabrication gates are not complete.
- L6 Vision Critique: not built as a render-to-critique-to-delta-to-resolve
  loop.
- L7 Render + Export: partial. STEP/GLB exist; Cycles, LUXEXCHANGE v1, and the
  full practical export package are not complete.
- L8 DesignDNA: not built.

## Phase Goal

Turn a client brief into a retrievable, validated, render-reviewed, exportable
design package:

brief -> Council spec -> assembly geometry -> validation gates -> render ->
vision critique -> bounded parameter deltas -> re-solve -> export package ->
DesignDNA precedent.

## Hard Rule

Every new capability must be truthful in the UI and API. If a layer is still a
stub, the response must say so with an actionable reason.

## Slice 7A - Finish The Assembly Surface

Purpose: close the remaining Phase 6 Slice A2 gap so generated geometry is not
locked to one cascade function.

Status: implemented as the first Phase 7A slice on 2026-08-21.

Build:

- Primitive-agnostic backend endpoint for assembly defaults, previews, and
  validation.
- Manifest persistence on `generated_programs` or the nearest existing
  artifact table.
- Frontend controls driven by the live primitive registry, not hardcoded
  cascade-only fields.
- Operator docs for building an assembly from Design Spec massing elements.

Implementation:

- Backend route: `/api/geometry/assembly/*`.
- Persistence: `designs.parameter_json` stores
  `assembly_design_record_v1`, including request, manifest, and artifacts.
- Artifacts: deterministic STEP plus GLB preview under
  `data/designs/<spec_hash>/`.
- Validation: `validation_reports.gate_name = assembly_mesh`.
- Frontend: Assembly tab builds from `/api/geometry/assembly/defaults` and
  displays `/api/geometry/assembly/latest.glb`.
- Operator doc: `docs/operator/06_assembly_manifest.md`.

Gate:

- A spec with at least three supported primitives maps to one
  `assembly_manifest_v1`.
- The manifest is persisted, reloaded, validated, and previewed in the browser.
- Unknown primitives or unsupported parameters fail before fabrication with
  clear errors.

## Slice 7B - Validation Gate Expansion

Purpose: make L5 real beyond watertight mesh checks.

Build:

- Structural checks: mass, center of gravity, support span, minimum wall
  thickness, and load-bearing warnings.
- Hydraulic checks: reservoir capacity, nozzle bore sanity, pump-flow range,
  slope/drain direction, and service void clearance.
- Fabrication checks: maximum lift mass, maximum module envelope, minimum tool
  radius, split-line feasibility, and per-module report rows.
- Validation report schema with pass/warn/fail severity and source values.

Gate:

- A valid assembly produces mesh, structural, hydraulic, and fabrication
  reports.
- A deliberately invalid assembly fails for the correct layer and includes the
  measured offending values.
- The UI shows validation status without implying warnings are passes.

## Slice 7C - Render And Export Foundation

Purpose: make L7 exportable packages real while respecting known limits.

Build:

- Headless Blender/Cycles CPU render worker with deterministic camera presets
  and reduced-sample critique renders.
- Export job model with artifacts, checksums, versions, and logs.
- LUXEXCHANGE v1 package: JSON manifest, Design Spec, validation reports,
  costs, geometry fingerprints, thumbnails, and exported files.
- Practical export formats: STEP, GLB, STL, OBJ, DXF, USD/USDZ, DAE, FBX, and
  Alembic where the toolchain can produce them.
- Clear DWG/SKP workaround links instead of fake native support.

Gate:

- One design exports a package with checksums and a manifest.
- Re-running the same geometry keeps canonical STEP deterministic.
- Missing external exporters degrade with honest status, not silent omission.

## Slice 7D - Vision Critique Loop

Purpose: make L6 real as a bounded, auditable improvement loop.

Build:

- Render set generation from the current geometry: front, side, plan, and
  perspective.
- Two-provider vision critique consensus using the configured primary pair.
- Strict JSON critique schema: issues, confidence, parameter deltas, and stop
  reason.
- Delta clamp against allowed parameter ranges before re-solving geometry.
- Iteration history stored with cost, images, model outputs, deltas, and
  validation results.

Gate:

- A design runs at least one critique round and either improves by accepted
  deltas or stops with a clear reason.
- The loop respects `max_vision_iterations`.
- Vision output cannot directly execute code and cannot bypass validation.

## Slice 7E - DesignDNA

Purpose: make every accepted design a reusable precedent.

Build:

- Accepted-design event that stores Design Spec, assembly manifest, validation
  report, render thumbnails, export manifest, cost summary, and tags.
- Local retrieval by project type, material, scale, climate, culture cues,
  budget band, validation profile, and geometry fingerprint.
- Precedent injection into future Council prompts with explicit provenance.
- Privacy rule: no rejected or draft design enters DesignDNA unless the
  operator accepts it.

Gate:

- Accepting a design creates one retrievable precedent.
- A later brief can retrieve that precedent and show why it matched.
- The system can delete or archive a precedent without corrupting old sessions.

## Slice 7F - Hardening And Operator Recovery

Purpose: make long render, critique, validation, and export jobs survive real
operator use.

Build:

- Resumable job runner with checkpoints for fabrication, validation, render,
  critique, export, and DesignDNA acceptance.
- Kill-and-resume test scripts.
- Backup/export of local data.
- Cost dashboard for Council, fabrication, render, critique, and export runs.
- Operator docs for phase gates and recovery.

Gate:

- Killing the backend during a long job lets the operator resume without
  losing accepted artifacts.
- Every paid API call remains auditable.
- The status screen identifies the active phase, current job, and last failure.

## Completion Gate

Phase 7 is closed only when all of these are true:

- A plain-language brief produces a strict Design Spec.
- The Design Spec maps to a multi-primitive assembly manifest.
- The geometry validates across mesh, structural, hydraulic, and fabrication
  gates.
- The render worker produces critique images.
- Two vision providers critique the render and return bounded JSON deltas.
- Accepted deltas re-solve geometry and re-run validation.
- The final design exports a LUXEXCHANGE v1 package and practical file
  formats.
- The accepted design becomes searchable DesignDNA precedent.
- The full run survives a backend restart through checkpoints.

## First Build Step

Start with Slice 7A because it unlocks every later layer. Validation, rendering,
vision critique, export, and DesignDNA all need one shared object to point at:
the persisted assembly manifest.

## Follow-On Phase Files

After Phase 7 closes the assembly-manifest foundation, the remaining work is
split into these detailed phase plans:

- `PHASE_8_VALIDATION_GATE_PLAN.md`
- `PHASE_9_RENDER_EXPORT_PLAN.md`
- `PHASE_10_VISION_CRITIQUE_PLAN.md`
- `PHASE_11_DESIGNDNA_PLAN.md`
- `PHASE_12_BRIEF_INTAKE_POLISH_PLAN.md`
- `PHASE_13_RECOVERY_HARDENING_PLAN.md`
