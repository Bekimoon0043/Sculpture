# gate_pr25_discovery_visual.md — PR-2.5 discovery, the operator's eye gate

**Cost: $0.** Nothing here spends money or touches the network.

**Rebuild: already satisfied — do NOT rebuild again.** The slice's
tests and gate are baked into backend image `ec459ff14a9f` (built
2026-09-03, both PR-2.5 test files 26/26 green on it). Only rebuild if
`docker compose images backend` shows a DIFFERENT image id, and
coordinate with any live session first if so.

**What you are signing:** that the discovery evidence is real and
sufficient, and that the report's acceptance plan and representation
recommendation are approved as the basis for the free-form
IMPLEMENTATION slice. You are NOT signing that any free-form capability
exists — LIMITATIONS §22 records that none does.

**This gate requires your local reference images** in
`briefs\freeform_references\` (they are private and uncommitted; on a
machine without them, stop — only you can walk this gate).

## 1. Verify the evidence chain is intact

```powershell
docker compose exec -T backend python scripts/gate_pr25_discovery_auto.py
python scripts\gate_pr25_discovery_auto.py --host-drift
```

- [ ] Both end **PASS**. The two runs split the coverage — the
      recorded 2026-09-03 results, which yours should reproduce:
      * **In-container: PASS 198/198**, with exactly one section
        skipped BY DESIGN — the operator-local reference images
        (section 10) — because the JPGs are dockerignored and never
        enter the image, so the container cannot see them.
      * **Host `--host-drift`: PASS 217/217, zero sections skipped** —
        THIS run is the one that verifies all 16 local image hashes
        against the committed manifest (section 10), proves
        `backend/app`, `config` and `schemas` untouched, and proves no
        JPG is tracked by git (section 12).

## 2. Compare the probe forms against your references

For each row below, open the reference image and the three annotated
renders side by side. Per the fidelity ruling you made, judge
**silhouette + topology** — void count, crossings, twist direction,
proportions — not surface detail. Renders are in
`data\render_scratch\<job>\` as `ortho_front.annotated.png`,
`ortho_side.annotated.png`, `perspective_3q.annotated.png`; each
carries its fixture name, approach and GLB hash in the caption strip.
The matching GLB (inspectable 3D artifact) sits in
`data\geo_scratch\pr25_discovery\passA\`; Windows' built-in 3D Viewer
opens GLB files if installed — otherwise judge from the three views
plus the reported bounding envelope.

| Reference image | Probe job(s) to open |
|---|---|
| `08_organic_void_sculpture_water_court.jpg` | `pr25_brep__ref08_loop_from_halves` (the valid closed-loop construction — closest result; omitted from this table before the 2026-09-03 review, now fixed), `pr25_brep__ref08_void_loop` (defective-seam evidence), `pr25_mesh__ref08_varying_loop` |
| `11_twisted_ribbon_fountain_sculpture.jpg` | `pr25_brep__ref11_twist_ribbon`, `pr25_mesh__ref11_twist_tube` |
| `13_double_loop_garden_sculpture.jpg` | `pr25_brep__ref13_double_loop` |
| `14_interwoven_ribbon_garden_sculpture.jpg` | `pr25_brep__ref14_interwoven`, `pr25_mesh__ref14_three_rings` |
| `16_split_ribbon_garden_sculpture.jpg` | `pr25_brep__ref16_split_rejoin` |

- [ ] Each rendered form speaks the same geometric language as its
      reference (loops, voids, twist, weave, split) at a stated
      3.5–5 m envelope.
- [ ] The failures the report records (the varying-section closed sweep,
      the seam fillet, the mesh route's missing booleans, the flagged
      periodic-sweep seams) are stated as failures — nothing failed is
      dressed up as working.

## 3. Check the honesty guards

Open `PR2_5_FREEFORM_DISCOVERY.md` and confirm by eye:

- [ ] Every number carries one of your six provenance tags, and every
      GRC fabrication fact is FABRICATOR-INPUT-REQUIRED (no invented
      density/wall/reinforcement values anywhere).
- [ ] 316L masses are skin-only, labeled non-engineering discovery
      estimates, with the sentence that total assembly mass is not
      computable until the armature is designed.
- [ ] B-11b (mesh/lattice) is recorded as OPEN and release-blocking —
      the generated import blob is explicitly NOT a stand-in.
- [ ] The audit score (31.6/100) is unchanged anywhere it appears.

## 4. Rule on the report's recommendations

The report ends with a representation recommendation and an acceptance
gate design for the implementation slice. Your ruling on each:

- [ ] Representation recommendation: APPROVED / CHANGED (state below)
- [ ] Acceptance gate design: APPROVED / CHANGED (state below)
- [ ] STEP stays the canonical artifact for the 316L family (any change
      requires your explicit architectural ruling): CONFIRMED / RULED
      OTHERWISE (state below)

## Sign-off

```
Date: 2026-09-03
Step 1 — auto gate PASS in both modes:                  YES
Step 2 — silhouette+topology comparison satisfied:      NO
Step 3 — honesty guards verified:                       YES
Step 4 — rulings recorded:                              YES

Rulings / notes:

The complete visual gate was independently reviewed against references
08, 11, 13, 14 and 16, including every required front/side/perspective
render. The honest visual result is NOT PASS:

- Ref08: the valid ref08_loop_from_halves BREP is the closest result
  but was omitted from the gate table. The listed ref08_void_loop has
  a visible defective seam. The mesh result is presented horizontally
  and does not satisfy the reference proportions.
- Ref11: BREP demonstrates a vertical twist but misses the broad
  flowing silhouette and lower opening; its OCC result is
  indeterminate. Mesh does not resemble the reference.
- Ref13: two holes exist, but they are small circular cutouts rather
  than the two large organic loops and twisted waist.
- Ref14: BREP looks like hoops around a column and is independently
  flagged; mesh is three disconnected rings. Neither matches the tall
  interwoven ribbon reference.
- Ref16: the probe is a simple one-void pointed loop, not the flowing
  split/rejoin form and two-void topology recorded in
  REFERENCE_ANALYSIS.md.

Representation recommendation:  BREP-first APPROVED WITH CONDITIONS
Acceptance gate design:         CHANGED (the owner's eight conditions
                                are integrated into the report's
                                "Acceptance gate design" section:
                                canonical upright orientation;
                                reference-specific envelope + landmark
                                proportions; correct body/void/genus
                                counts; required twist / split-rejoin /
                                over-under crossing behavior; owner
                                visual comparison of all three views;
                                ref11 OCC disagreement resolved before
                                acceptance; ref14 self-interference/
                                non-manifold findings resolved before
                                acceptance; ref16 topology matching the
                                recorded reference requirement)
STEP canonical (316L family):   CONFIRMED

The probes prove operation/kernel feasibility, NOT reference-faithful
geometry. Reference-faithful geometry remains unproven and is the
implementation slice's burden under the changed acceptance gate.
```

After signing, the discovery artifacts under
`data\geo_scratch\pr25_discovery\` and `data\render_scratch\pr25_*` may
be deleted (controlled cleanup, ADR-064); the committed report, manifest
and summary evidence remain the permanent record.
