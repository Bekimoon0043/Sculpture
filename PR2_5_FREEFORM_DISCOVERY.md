# PR-2.5 — Free-form amorphous sculpture: discovery report

Date: 2026-09-02 · ADR-064 · Status: **discovery evidence, not product
capability.** Nothing here is reachable from a brief, the Council, the
Designer or the export pipeline; the ten-primitive registry is
unchanged; the Master Scope audit score (31.6/100 at `bfa5a77`) does
not move on anything in this report. LIMITATIONS §22 is the standing
truth: kernel feasibility probed; no user-facing free-form capability
implemented. **The owner's independent visual review (2026-09-03) ruled
the probe forms NOT reference-faithful — the probes prove
operation/kernel feasibility, not reference-faithful geometry; see
"Operator visual verdict" below.**

Ground truth: the operator-supplied B-11 reference set
(`briefs/freeform_references/`, 16 images, hashes and roles in the
committed `reference_manifest.json`; the JPGs themselves are
operator-local and uncommitted by owner ruling). Primary acceptance
family: **08, 11, 13, 14, 16**. None of the 16 images shows a
mesh/lattice structure — see Open items.

## Owner rulings

Recorded 2026-09-02 (full context in ADR-064):

1. **Materials**: welded 316L plate over an internal armature AND cast
   GRC / white concrete. (owner-ruling)
2. **Scale**: primary references validate at monumental **3.5–5.0 m**.
   (owner-ruling — NOT measured from any image)
3. **Controls**: brief-driven generation plus parameter/control-point
   editing; no full manual sculpting in v1. (owner-ruling)
4. **Fidelity**: silhouette + topology — void count, crossings, twist
   direction, proportions. (owner-ruling)
5. Reference images stay local and unpublished. (owner-ruling)
6. **B-11b** — mesh/lattice ground truth — stays OPEN and
   **release-blocking** for any mesh-capability claim and for
   Production v1. (owner-ruling)

Provenance vocabulary used throughout (the ruled six):
`owner-ruling`, `measured-from-dimensioned-reference`,
`image-derived-estimate`, `materials.yaml`, `probe-only-judgement`,
`FABRICATOR-INPUT-REQUIRED`. Every image-derived proportion below is an
estimate read off an uncontrolled photograph and carries real
uncertainty — treat ±20 % as the honest working band until a
dimensioned drawing exists (probe-only-judgement).

## Method

One documented host command runs the whole evidence chain and reruns
cleanly from a fresh checkout (owner clarification 2):

```powershell
python scripts\run_pr25_discovery.py
```

- All geometry-constructing probes (AI-authored) execute ONLY in the
  geo-worker sandbox: network none, user 1000:1000, read-only fs except
  `/scratch`, cpus 1.0, mem 2 GB, hard host-side timeout. Each probe
  runs TWICE in separate sandbox processes (passA/passB).
- Contractual determinism bytes: STEP (Phase 2 exporter, fixed seed
  20260902 timestamp) and canonical OBJ (`%.6f`, fixed order, LF).
  GLB is viewing-only — build123d exports it in metres as unwelded
  per-face primitives, so it is non-contractual (ADR-064).
- Independent validation (backend, analysis-only): OCC
  BRepCheck_Analyzer; OCC `BRepAlgoAPI_Check(shape, True, True)`
  self-interference testing (call pattern discovered at runtime, not
  recalled); kernel-vs-own-tessellation volume cross-check (1.0 mm
  deflection, exact-merge weld, 2 % tolerance — probe-only-judgement);
  trimesh watertight/winding; boundary/non-manifold edge count
  (networkx-free); duplicate-face detection; Euler-characteristic
  genus. Minimum-thickness sampling is UNAVAILABLE on the pinned image
  (`trimesh.proximity.thickness` needs the absent `rtree`) and degrades
  to a recorded error — see Open items.
- Renders: the untouched Phase 9B protocol (ortho_front / ortho_side /
  perspective_3q, 768 px, 24 samples — probe-only-judgement), captions
  stamped under each PNG with fixture, approach and GLB hash.
- Artifacts live only in `data/geo_scratch/pr25_discovery/` and
  `data/render_scratch/pr25_*`; the real DB and `data/exports` are
  never touched; evidence is preserved until the operator signs
  `gate_pr25_discovery_visual.md`.

## Capability matrix

The authoritative machine-readable matrix — the auto gate cross-checks
every row against the orchestrator's `summary.json` and re-hashes every
artifact:

```json capability-matrix
[
  {"fixture": "import_fixture_blob", "approach": "import", "status": "constructed"},
  {"fixture": "ref11_twist_ribbon", "approach": "brep", "status": "constructed"},
  {"fixture": "ref08_void_loop", "approach": "brep", "status": "constructed"},
  {"fixture": "ref08_varying_loop", "approach": "brep", "status": "failed"},
  {"fixture": "ref08_loop_from_halves", "approach": "brep", "status": "constructed"},
  {"fixture": "bad_tangent_overlap_fuse", "approach": "brep", "status": "constructed"},
  {"fixture": "ref13_double_loop", "approach": "brep", "status": "constructed"},
  {"fixture": "ref14_interwoven", "approach": "brep", "status": "constructed"},
  {"fixture": "ref16_split_rejoin", "approach": "brep", "status": "constructed"},
  {"fixture": "bad_self_crossing", "approach": "brep", "status": "constructed"},
  {"fixture": "ref16_fillet_seams", "approach": "brep", "status": "failed"},
  {"fixture": "import_fitted_blob", "approach": "import", "status": "constructed"},
  {"fixture": "ref11_twist_tube", "approach": "mesh", "status": "constructed"},
  {"fixture": "ref08_varying_loop", "approach": "mesh", "status": "constructed"},
  {"fixture": "ref14_three_rings", "approach": "mesh", "status": "constructed"},
  {"fixture": "ref13_double_loop", "approach": "mesh", "status": "failed"},
  {"fixture": "ref16_split_rejoin", "approach": "mesh", "status": "failed"}
]
```

Key measured results (mm, mm³; all at the owner-ruled 3.5–5.0 m band;
proportions image-derived-estimate):

| Fixture | Result | Independent verdict |
|---|---|---|
| `ref11_twist_ribbon` (brep) | 1 solid, kernel-valid, vol 0.549 m³, bbox 939×1110×4196 | tessellation clean, volume agrees to 0.023 % — but the OCC self-interference check returns `IsValid=False` with `HasErrors=False`: an **indeterminate verdict that fails closed**; the checks disagree, and resolving that disagreement is an implementation-slice task |
| `ref08_void_loop` (brep, periodic sweep) | constructed but **kernel-invalid** | kept deliberately as evidence: closed-path `sweep()` seals a defective seam — not watertight, 507 boundary/non-manifold edges, 168 duplicate face pairs |
| `ref08_varying_loop` (brep, periodic multisection sweep) | **refused by OCC**: `OCP.OCP.Standard.Standard_ConstructionError: PipeShell : uncompatible wires` | — |
| `ref08_loop_from_halves` (brep) | **the working closed-loop construction**: two butt-joined open lofts with bitwise-identical boundary sections, fused → 1 valid solid, genus 1, vol 1.672 m³, volume agreement 0.27 % | clean |
| `ref13_double_loop` (brep) | 1 valid solid, **genus 2** (both through-voids), vol 1.707 m³, full 4600 mm height, volume agreement 0.49 % | clean |
| `ref14_interwoven` (brep) | 1 kernel-valid solid, vol 3.069 m³, full 4200 mm height | **flagged**: OCC self-interference check objects and the tessellation shows 2 boundary/non-manifold edges — interweaving is the hardest BREP case; "kernel says valid" is not enough |
| `ref16_split_rejoin` (brep) | 1 valid solid, genus 1 (split/rejoin void), vol 0.573 m³ | clean |
| `ref16_fillet_seams` (brep) | **failed at 25 mm AND 8 mm**: `Failed creating a fillet ... use max_fillet()` — seam blending on fused free-form bodies is unproven | — |
| `bad_self_crossing` (brep, DELIBERATE) | constructed by the kernel without complaint | **refused by the stack** — OCC self-interference errors + non-watertight tessellation. The refusal machinery works |
| `bad_tangent_overlap_fuse` (brep, DELIBERATE) | near-tangent overlap fuse | **refused** — corrupt geometry caught (86 boundary/non-manifold edges). In an earlier probe iteration the same fuse SILENTLY returned an empty Compound claiming `is_valid=True`; the probe now carries an empty-result guard because of it |
| `ref11_twist_tube` / `ref08_varying_loop` (mesh) | watertight parametric tubes, genus 0/1, canonical OBJ | clean — the varying-section CLOSED loop is trivial here where BREP needed the two-half workaround |
| `ref14_three_rings` (mesh) | 3 interlocked tubes, watertight, genus 3 — but **3 disjoint bodies** | no boolean/fusion machinery exists on this route |
| `ref13`/`ref16` (mesh) | **not constructible**: need booleans or an implicit/SDF route; no CGAL/libigl/OpenVDB, no scikit-image | — |
| `import_fixture_blob` → `import_fitted_blob` | deterministic generated blob imported, validated, uniform-scaled to 4200 mm, canonically re-exported | clean; proves transform/validate/re-serialize ONLY — not artist-mesh trust, and NOT a B-11b lattice |

**Determinism: 13/13 contractual artifacts (7 STEP + 6 canonical OBJ)
byte-identical across two separate sandbox processes.** Validation
verdicts agree between passes. 12/12 render jobs produced all three
views; 36 captioned PNGs. Render worker running at start AND end;
backend image `9fe4c4328116` throughout; zero orchestration failures;
$0 spent.

Fixture-development history, recorded rather than hidden: the first
probe iteration's ref13 voids (image-guessed radii) were wider than the
hourglass waist and bisected the body into two solids — the fixture was
re-sized to express the intended genus-2 capability claim; the first
closed-ring attempt swept one periodic spline and produced the seam
defect now preserved as `ref08_void_loop`; the overlap-fuse silent
empty result was promoted into the permanent `bad_tangent_overlap_fuse`
specimen plus a probe-level guard.

## Approach comparison

**(a) Controlled BREP loft/sweep/spline — the strongest route.** All
five primary geometric languages were constructed as single kernel
solids at real scale with byte-deterministic STEP: twist with varying
sections (ref11), closed varying-section loop (ref08, via butt-joined
half-lofts — never via periodic sweep), two-void genus-2 body (ref13),
interwoven fused body (ref14, flagged), split/rejoin (ref16). It slots
directly into the existing STEP-canonical pipeline (validation,
segmentation, LUXEXCHANGE, Phase 2 determinism). Its real costs,
measured: periodic-path constructions are defective or refused; seam
blending (fillet) is unproven; interweaving survives construction but
not independent scrutiny; and one OCC verdict (ref11) is indeterminate.

**(b) Deterministic procedural mesh — powerful but boxed in.**
Watertight-by-construction, trivially handles what BREP found hardest
(closed varying-section loops), byte-deterministic canonical OBJ. But
with no boolean machinery in the installed stack it cannot join, split
or subtract — so ref13/ref16 are out of reach and ref14 stays three
disjoint bodies — and it lives outside the STEP-canonical pipeline:
**any change to STEP as the canonical artifact requires an explicit
architectural ruling** (ADR-060), which this report does not propose.

**(c) Reference-mesh import — proven narrow.** Import, validation,
deterministic fitting and canonical re-serialization all work. What it
does not solve is where a trustworthy artist mesh comes from (LLMs may
never emit unchecked vertices — the rule survives; a human-authored
mesh needs provenance, license and engineering review), and it must not
be mistaken for B-11b evidence.

### Operator visual verdict (2026-09-03) — Step 2: NOT PASS

The owner had the complete visual-gate package independently reviewed
against references 08, 11, 13, 14 and 16, including every required
front/side/perspective render. The honest result: **the visual
comparison is NOT PASS. The probes prove operation/kernel feasibility,
not reference-faithful geometry.** Per-reference findings, recorded:

- **Ref 08**: the valid `ref08_loop_from_halves` BREP is the closest
  result but was omitted from the gate's comparison table (now fixed);
  the listed `ref08_void_loop` has a visible defective seam; the mesh
  result is presented horizontally and does not satisfy the reference
  proportions.
- **Ref 11**: the BREP demonstrates a vertical twist but misses the
  broad flowing silhouette and lower opening, and its OCC verdict is
  indeterminate; the mesh does not resemble the reference.
- **Ref 13**: two holes exist, but they are small circular cutouts
  rather than the two large organic loops and twisted waist.
- **Ref 14**: the BREP looks like hoops around a column and is
  independently flagged; the mesh is three disconnected rings; neither
  matches the tall interwoven ribbon reference.
- **Ref 16**: the probe is a simple one-void pointed loop, not the
  flowing split/rejoin form and two-void topology recorded in
  `REFERENCE_ANALYSIS.md`.

Owner rulings issued with this verdict: **BREP-first APPROVED WITH
CONDITIONS**; **acceptance gate design CHANGED** (the changed design is
what now stands in the section below); **STEP canonical for the 316L
family CONFIRMED**.

**Recommendation (ruled 2026-09-03: APPROVED WITH CONDITIONS — see the
verdict above):**
implement the free-form capability **BREP-first** — a constrained
construction vocabulary (bounded guide curves, placed rotated/scaled
sections, lofts, butt-joined loop assembly, subtractive voids) that an
LLM parameterizes as a spec and the deterministic kernel executes, with
the independent validation stack (self-interference + tessellation
cross-check included) as a mandatory post-build gate because kernel
`is_valid` alone is demonstrably insufficient. STEP stays canonical.
The mesh route is held in reserve for the B-11b lattice class, decided
only when its reference arrives. Interweaving (ref14-class) enters the
acceptance set only behind its flagged-questions being resolved.

## Parameter frames

Every number tagged; nothing invented.

**Welded 316L plate + armature** (refs 11/13/14/15/16 class):

- Plate thickness **6 mm** — measured-from-dimensioned-reference
  (reference 01 states it).
- Density **8000 kg/m³** — materials.yaml
  (`stainless_316l_sheet.density_kg_per_m3`).
- Skin-only mass at 6 mm over the probe bodies' measured surface areas
  (areas are geometry of image-derived-estimate forms; each figure is a
  **non-engineering discovery estimate** — not an assembly mass, not a
  lifting value, not a quotation value, not an acceptance limit):
  ref11 7.68 m² → ≈ 369 kg · ref08-loop 15.78 m² → ≈ 757 kg ·
  ref13 11.91 m² → ≈ 572 kg · ref14 24.82 m² → ≈ 1191 kg ·
  ref16 7.99 m² → ≈ 384 kg. **Total assembly mass is not computable
  until the armature is designed** — FABRICATOR-INPUT-REQUIRED.
- Minimum forming radius for 6 mm plate: FABRICATOR-INPUT-REQUIRED
  (a probe input, never a claim).
- Envelope: heights 3.5–5.0 m (owner-ruling); measured probe bboxes sit
  inside it; per-axis module limits bind through the existing PR-1
  machinery once segmentation of curved bodies is implemented.

**Cast GRC / white concrete** (ref 08 class): density, minimum shell
thickness, reinforcement, panel size, connection details and mold
limits are ALL **FABRICATOR-INPUT-REQUIRED**. `config/materials.yaml`
deliberately carries no GRC entry. The probes used clearly-labeled
non-engineering sample parameters to exercise topology only and emit no
mass, lifting, structural or fabrication claims for GRC.

## Acceptance gate design

**As CHANGED by the owner's ruling of 2026-09-03** (issued with the
NOT-PASS visual verdict; this supersedes the pre-verdict draft). For
the implementation slice, to be planned via `/lf-next`:

1. **Chain**: intake fixture (real brief text) → Council alternatives
   via RECORDED FIXTURE REPLAY (Phase 3 pattern; $0 in the auto gate) →
   constrained free-form spec → deterministic watertight geometry →
   L5 validation → segmentation into transportable modules →
   render → LUXEXCHANGE export. One LIVE Council demonstration happens
   only in the implementation slice's visual gate, cost-approved
   beforehand.
2. **Canonical upright orientation** is required of every accepted
   form — a result presented on its side (the ref-08 mesh probe's
   failure mode) cannot pass.
3. **Reference-specific envelope and landmark proportion checks**:
   each acceptance fixture carries its reference's stated envelope and
   a small set of landmark proportions (opening sizes and positions,
   waist widths, lobe spans — image-derived-estimate until dimensioned
   drawings exist), asserted from persisted geometry.
4. **Correct connected-body and void/genus counts** per reference —
   ref13-class must be ONE body of genus 2 with the two voids at the
   recorded stations; disconnected multi-body results (the ref-14 mesh
   probe's failure mode) cannot pass.
5. **Required twist direction, split/rejoin and over/under crossing
   behavior** asserted per reference — including that ref13-class
   voids are large organic loops with a twisted waist (not small
   circular cutouts), and ref16-class carries the flowing split/rejoin
   form with the TWO-void topology `REFERENCE_ANALYSIS.md` records.
6. **Owner visual comparison of front, side and perspective views** is
   a mandatory acceptance step for every fixture — the auto gate's
   topology/proportion checks gate what CAN pass; only the owner's eye
   passes it.
7. **The ref11 OCC disagreement (indeterminate
   `BRepAlgoAPI_Check` verdict vs clean tessellation) must be RESOLVED
   before any ref11-class acceptance** — not worked around.
8. **The ref14 self-interference/non-manifold findings must be
   RESOLVED before any ref14-class acceptance** — interwoven forms
   enter the acceptance set only clean.
9. **Negative fixtures**: the self-crossing sweep and the tangent
   overlap fuse MUST refuse; a thin-wall case joins when a thickness
   check exists (see Open items); an over-envelope body must segment or
   refuse via the PR-1 per-axis limits.
10. **Determinism**: identical spec + seed + pinned image →
    byte-identical STEP, twice in separate processes, plus package
    byte-reproducibility per (design, seed, class) under the LF-103A
    export boundary (all free-form designs classify PRE-FABRICATION
    until D-24 closes).
11. **Both worker states**, $0, offline, hermetic (LF-103A section-9
    pattern); geometry assertions come from persisted
    genus/void/proportion data — pixel comparison is never an auto-gate
    check (the owner's eye in item 6 covers appearance). Separate 316L
    and GRC acceptance families (welded seams vs mold pieces).

## Open items

- **Reference-faithful geometry is UNPROVEN** (owner visual verdict
  2026-09-03, NOT PASS): every probe form fell short of its reference's
  silhouette/topology on independent review. The implementation slice
  must close this gap under the CHANGED acceptance gate above — upright
  orientation, landmark proportions, per-reference body/void/genus and
  crossing behavior, and the owner's eye on all three views.
- **B-11b (mesh/lattice ground truth): OPEN and release-blocking** for
  any mesh-capability claim and for Production v1. Needs at least one
  real reference image of the intended lattice/perforated class from
  the owner. Nothing is specified in its place.
- The ref11 indeterminate OCC self-check verdict and the ref14
  interweave flags — resolve before either enters the acceptance set.
- Seam blending: `max_fillet()` exploration or welded-seam acceptance
  without blend — a fabrication-driven decision, not a cosmetic one.
- Minimum-thickness checking needs `rtree` (a download — operator's
  call) or an alternative; until then thin-wall limits cannot bind.
- GRC fabricator datasheet (six FABRICATOR-INPUT-REQUIRED items) and
  the 316L forming-radius/armature inputs.
- Segmentation of curved free-form bodies (the existing planar-cut
  segmenter has never been proven on them) — an implementation-slice
  work item, not assumed.

## Definitive gate evidence (2026-09-03, close)

**Closed strictly as a DISCOVERY result, not as completed free-form
capability: reference-faithful geometry and user-facing free-form
capability remain UNBUILT.**

On definitive backend image `52209e4a6eea` (start == end of the run),
all at $0 with no providers:

- Stage 1 (render worker REMOVED, listing `[]` before and after):
  `540 passed, 3 warnings in 1013.06s (0:16:53)`; all 21 in-container
  roster scripts exit 0 (17 phase gates + PR-1 + PR-2 + LF-103A +
  PR-2.5 `PASS -- all 198 checks`); PR-3 static via stdin PASS.
- Stage 2 (worker restored, pinned `Up 5 seconds` before, up
  throughout and at the end): `540 passed, 3 warnings in 597.63s
  (0:09:57)`; `gate_phase9b_auto` exit 0 PASS.
- Host: PR-3 `--live` PASS, scope audit PASS, Phase 14
  `--frontend-only` PASS, and PR-2.5 `--host-drift`
  `PASS -- all 217 checks` with `sections skipped: none` (all 16
  operator-local image hashes verified; no JPG tracked; production
  trees untouched).

The operator's visual ruling stands verbatim in
`gate_pr25_discovery_visual.md`: **Step 2 = NO** (the probe forms are
NOT reference-faithful); BREP-first **APPROVED WITH CONDITIONS**;
acceptance gate design **CHANGED** (the eight conditions above); STEP
canonical for the 316L family **CONFIRMED**.
