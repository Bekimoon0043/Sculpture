# FF-A2 visual gate — freeform_loop, the ref-08 hollow-lens sculpture (ADR-066)

**Precondition:** `gate_ffa2_auto.py` PASSES in the backend container
with zero skipped sections. If it does not, this walk is locked — do
not sign anything below.

You are judging the first real free-form sculpture the platform can
build: a hollow 316L lens with a walled window bore, standing on a thin
interface plate. It is **PRE-FABRICATION only** — nothing here is
fabrication-ready, the wall is a nominal gauge (never verified), the
armature does not exist, and every mass-dependent decision reports
*needs input*. Your eye rules fidelity; the auto gate only bounds what
can reach you (owner condition 6, ADR-064).

Rebuild first so the walk sees the final tree:

```powershell
docker compose up --build -d
```

---

## Step 1 — The three-way comparison (the fidelity verdict)

The comparison baseline is **pinned by identity** — the ref-08 render
you rejected on 2026-09-03, preserved at
`data\render_scratch\pr25_brep__ref08_loop_from_halves\` and hashed
**2026-09-04, before any FF-A2 build edit**:

```
ortho_front.png      488884 bytes  a278a98de4b58bcec3d453bc60cbc58cf29a389152af2d32b8505c557c6354ac
ortho_side.png       469413 bytes  1b99c3f3c74175d7e2871e3f971916f96b78e699ad49e480018ce055eaa9b6e4
perspective_3q.png   504202 bytes  5c5e69c99b644a1dc7ada3a9c0259ec87866580b5bacc45c7c7cabea21e69a9a
(annotated: cb6c81ee… / 96030fa9… / d2873055…)
```

(Regenerable as an *equivalent* render — not byte-identical, PNG bytes
are non-determinism-gated per ADR-045 — with the recorded discovery
command `python scripts\run_pr25_discovery.py`.)

1. Open the Designer (http://127.0.0.1:5173), create a new design, and
   add a **freeform_loop** from the palette. Build it with its default
   parameters.
2. Render the three canonical views (front, side, perspective) through
   the normal render path, or judge the viewport from those three
   angles if you prefer not to wait for renders.
3. Place side by side: **(a)** the rejected baseline PNGs above,
   **(b)** the new freeform_loop views, **(c)** your local reference
   photograph `briefs\freeform_references\
   08_organic_void_sculpture_water_court.jpg`.

**Question 1: does (b) materially improve on (a) toward (c)?** Look
for: the almond/lens silhouette (not a tube annulus), the roundish
window sitting right of centre at mid-height, the thin sharp tips, the
broad lower body. A NO is a recordable verdict — write it below
exactly as you see it; nothing will be argued with.

- [x] YES / NO: **YES** (operator visual ruling, 2026-09-07)
- Notes: The freeform_loop appearance is correct and acceptable. The
  apparent left/right opening difference is accepted as
  viewing-orientation dependent (owner ruling, recorded verbatim).
  Comparison performed by viewport inspection from the three canonical
  angles, which this gate explicitly permits: a **570-second render
  timeout** occurred and is preserved as a SEPARATE OPERATIONAL
  FINDING — it does not invalidate this visual verdict.

**Question 1b — the 3-D apex scoop and rim shaping (mandatory,
separate).** Your reference's upper body carries a deep concave
surface SCOOP and sculpted rim shaping — 3-D surface features that NO
automatic projection metric measures (the auto gate's
`projected_side_to_apex_band_ratio` passing claims nothing about
them; the original 110 px/55 px rim landmark measured exactly this
scoop and is preserved as history in `ref08_landmarks.json`). Compare
the upper body of (b) against (c) specifically for surface character:
does the built form's upper surface read as acceptably sculpted
against the reference's scoop and rims, or is this a recorded gap?

- [x] Acceptable / Recorded gap: **ACCEPTABLE** (operator visual
  ruling, 2026-09-07)
- Notes: —

## Step 2 — The measurement record countersignature

Open `briefs\freeform_references\ref08_landmarks.json` beside your
local reference image. It records the pixel landmarks measured from
your photograph on 2026-09-04 (sha256 `bfe1662b…` — verify it matches
`reference_manifest.json`).

**Question 2: do the recorded pixel landmarks look right against your
image?** (Apex ≈ (690, 258), bottom tip ≈ (668, 668), void spanning
x 690–798 / y 405–530, widest lower-left rim ≈ 110 px.) These numbers
are what the fidelity bands derive from — if any looks wrong, say
which.

- [x] YES / NO: **YES** (operator visual ruling, 2026-09-07)
- Notes: —

## Step 3 — Honesty spot-checks in the product

With the freeform_loop design open:

1. **Inspector**: the mass reads as a known-geometry figure marked
   **(incomplete)** — never a plain total. Hover/read the missing
   inputs: armature mass, armature centroid, per-module allocation.
2. **Checks tab**: structural and fabrication gates show *needs input*
   rows naming the armature; `fabrication_wall_approval` and
   `forming_radius` are unresolved; nothing mass-dependent shows PASS.
3. **Output tab**: export the package. The zip name carries
   **PRE-FABRICATION**; inside, `ENGINEERING_WARRANT.txt` lists ONLY
   unresolved professional inputs, and
   `validation/freeform_integrity_v1.json` holds the passing geometry
   verdict.
4. **Determinism witness**: the auto-gate transcript section [3] shows
   two different PIDs producing byte-identical STEP sha256 digests —
   confirm the two hashes printed there are equal.

- [x] All four honest: YES / NO: **YES** (operator visual ruling,
  2026-09-07)
- Notes: —

---

## Sign-off

| Step | Verdict (YES/NO) | Date |
|---|---|---|
| 1 — fidelity vs baseline and reference (incl. 1b: 3-D scoop ACCEPTABLE) | **YES** | 2026-09-07 |
| 2 — measurement record countersigned | **YES** | 2026-09-07 |
| 3 — product honesty spot-checks | **YES** | 2026-09-07 |

Signed (operator): **Owner visual ruling recorded 2026-09-07** —
"the freeform_loop appearance is correct and acceptable"; the
left/right opening difference accepted as viewing-orientation
dependent; the 570-second render timeout preserved below as a
separate operational finding.

### Separate operational finding (preserved, does not affect the verdict)

During this walk a render attempt hit a **570-second timeout**. The
operator completed the comparison by viewport inspection from the
three canonical angles, which this gate explicitly permits, so the
visual verdict stands on its own evidence. The timeout itself is an
OPERATIONAL finding about rendering the freeform_loop's dense
free-form mesh on this hardware (i7-8550U, Cycles CPU, no GPU) — to
be carried into the loop docs at close, not resolved here and not
silently dropped.

**What signing means:** the platform now has ONE free-form primitive,
earned under the changed acceptance gate — not five references, not
mesh capability (B-11b stays open and release-blocking), not GRC, not
fabrication readiness. Ref-11 and ref-14 remain blocked by their
recorded findings; ref-16 must carry its recorded two-void topology
when its slice comes.
