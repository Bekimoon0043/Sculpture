# SCULPTURE_1_ENTOTO_HALO.md — the first sculpture built on LuxuryForm Studio

**Date:** 2026-09-30 · **Cost:** **$0.00** (no provider call was made)
**Verdict:** built, fused, exported and packaged — **`overall_status: needs_input`**,
**NOT** a fabrication-ready pass. Read §8 before showing this to anyone.

This is a record of one design taken end to end through the real platform, using
the real endpoints and the real kernel. It is not a gate and it does not close a
phase. No file under `backend/`, `config/` or `schemas/` was changed to make it
work: the sculpture either satisfied the existing rules or was refused by them.

---

## 1. The design

**Entoto Halo** — a wet plaza fountain. Four elements, three materials, one
fused body. The reading: a basalt cue — the Entoto ridge above Addis — carrying
a bronze shaft, crowned by a mirror-polished 316L ring whose aperture is the
water's exit.

| # | element | primitive | material | mass | z (mm) | extents (mm) |
|---|---|---|---|---|---|---|
| 1 | `p1` | `plinth` | basalt_slab | 1,001.97 kg | 0 | 2400 × 2400 × 350 (hollow, 150 wall) |
| 2 | `b1` | `basin_round` | basalt_slab | 1,906.55 kg | 340 | 2400 × 2400 × 400 (80 wall, 120 floor) |
| 3 | `c1` | `sculptural_column` | bronze_cast | 1,923.61 kg | 450 | 600 × 600 × 800 (solid, ⌀110 service bore) |
| 4 | `t1` | `torus_ring` | stainless_316l_cast | 239.87 kg | 1220 | 760 × 760 × 140 |

- **Total 5,072.00 kg.** Overall envelope 2,400 × 2,400 × **1,360 mm**.
- **Heaviest single pick: 1,923.61 kg** — a module, not the assembled piece.
- Stored water at the operating depth: **786.7 kg** in the pool.
- The plinth is hollow: that is the mass lever (2,000 kg of stone moved
  off the pick), not decoration.

### Joints — each with real interference and a real seat

| child → parent | type | overlap | floor | intersection |
|---|---|---|---|---|
| `b1` → `p1` | `stack_on` | 10.0 mm | 10.0 mm | 10,602,875 mm³ |
| `c1` → `b1` | `concentric_insert` | 10.0 mm | 10.0 mm | 2,732,400 mm³ |
| `t1` → `c1` | `stack_on` | 30.0 mm | 5.0 mm | 1,615,513 mm³ |

The `t1` overlap is deliberate and load-bearing for the design: a torus is line
contact when it is merely placed, so it is sunk 30 mm into the bronze column to
open a real chord (ADR-055). **This is where the first attempt was refused**, and
the refusal was correct (§5).

---

## 2. The design IS the file

`sculptures/entoto_halo/request.json` holds the whole design — elements,
parameters, joints, water context and the declared pipe network. Nothing about
it lives only in a chat log. Rebuild it with one command:

```bat
python scripts/build_sculpture.py sculptures/entoto_halo/request.json --twice --exports --bom
```

`scripts/build_sculpture.py` drives the platform's own endpoints; it contains no
geometry of its own. It accepts any request file, so this is the same path a
second sculpture would take.

---

## 3. Measured evidence (design `098f640e-6894-43b2-a698-452f432435e3`)

```
spec_hash     f328b46d983e68cf7889b4cee543b6b432ec2f548a90a5735892d4dac018df41
step_sha256   9537b6ae058d1868eb0f764848d46cc6211dd28a704153fe739fbef4d601d250
glb_sha256    b36e4046836a3315ec21afd1aee5549bdc8941fbe80f0052d89762dd083d5ed0
build_ms      1095
fused bodies  1     segmentation: 4 modules, 0 limit violations
```

Mesh validation: **watertight, winding consistent, 1 body, 30,236 faces,
0 degenerate faces**, and a B-rep vs mesh volume cross-check of **0.0423 %
against a 2 % tolerance** (the two independent volume calculations agree).

### The gate verdicts, verbatim

`validation_gates` holds exactly **three** gates:

| gate | status | what it actually measured |
|---|---|---|
| `hydraulics` | **pass** | capacity 1,103.43 L; freeboard 80.0 mm ≥ 60 required; turnover 15.33 min ≥ 15; service void 820 mm ≥ 80; **nozzle bore 16.0 mm inside the derived band [11.97, 19.95]** |
| `structure_static_v1` | **needs_input** | 1 fused body · mass > 0 · 1 root · 3 of 3 joints on the load path · centre-of-mass lever 1,200 mm — then **2 checks cannot evaluate** (§8) |
| `fabrication` | **needs_input** | 12 checks pass, incl. per-element mass vs 2,000 kg, module bbox 2,400 mm vs 2,400 mm limit, **bore aspect 7.27 ≤ 8.0** — then rigging cannot be certified (§8) |

The mesh result is a **separate report** (`validation`), not a fourth gate: it
carries no `gate_name` and no `status`, and reports `passed: true` — watertight,
winding consistent, 1 body, 0 degenerate faces, volume cross-check inside
tolerance.

`overall_status` rolls these up worst-first: **`needs_input`**, `passed: false`.
**A `needs_input` is not a warning and it is not a pass** — it is the platform
saying it cannot check something, and naming what it needs. That is the whole
point of the layered gate design (ADR-036) and it is why this report does not
end with the word "approved".

---

## 4. Rule 5 — determinism, proven twice on the live stack

```
run 1 STEP 9537b6ae058d1868eb0f764848d46cc6211dd28a704153fe739fbef4d601d250
run 2 STEP 9537b6ae058d1868eb0f764848d46cc6211dd28a704153fe739fbef4d601d250
STEP byte-identical: YES
GLB  byte-identical: YES
```

Two independent builds of the identical request, minutes apart, produced the
same canonical STEP *and* the same preview GLB. The same digest then reappears
inside the sealed package's checksums. That is the platform's central promise
(the LLM proposes, the kernel decides) holding on a design an LLM never touched.

---

## 5. The refusal that shaped the design (evidence the gate works)

The first attempt used a ⌀280 mm bronze column with a ⌀1100 mm ring on top.
The kernel refused it with real numbers:

> `t1: stack_on c1 lands on a -282.6 mm radial seat, below the 5 mm floor for
> stainless_316l_cast on bronze_cast (child base annulus ⌀845.109..1074.89 on
> parent top annulus ⌀100..280 mm) — a seat narrower than the fabrication
> tolerance stack can vanish in the workshop (signed sheet §2.1).`

A negative seat is the algebra being blunt: the ring's contact band sat at
radii 422–537 mm while the post's top face only reached 140 mm, so the ring was
floating **outside its parent entirely**. I resized the column to ⌀600 mm and
the ring to ⌀760 mm; the seat became +18.7 mm and the build passed. The design
changed because the arithmetic refused to lie, not because anyone eyeballed it.

---

## 6. Exports — what a fabricator actually receives

Eight formats were written; six were declared `unavailable` and two
`impossible` — nothing is faked into a format the toolchain cannot write:
`DAE`, `3MF`, `USD`, `USDZ`, `FBX`, `ABC` unavailable; `DWG`, `SKP` impossible
(both ship with the workaround text inside the package).

```
STEP   26884 B  cad   9537b6ae…   ← the canonical contract artifact
BREP    8320 B  cad   957b51b7…   ← lossless OCCT solid, for CAD rework
STL  1511884 B  cad   562ee0fc…   ← watertight triangulation for CAM/print
DXF    63541 B  cad   f16914e2…   ← 2D drawing
SVG    17205 B  cad   19f2d328…   ← plan + elevation sheet in mm
GLB   589332 B  mesh  b36e4046…   ← the viewport / render mesh
OBJ  1152257 B  mesh  12409928…
PLY   594335 B  mesh  35b424e7…
```

The `SVG` is a real drawing (a `PLAN` group of arcs in a 5400 × 2400 mm
viewBox), so a workshop can look at the piece without a CAD seat.

### The package is sealed, and it verifies itself

```
content_digest 3ccee796b63f5f0e49a71cdd73e6cdae68475d5e78140a8af71b2809eba13ace
package_sha256 6df5d52cd132a8013ebf863da9c58d361bb23b198a1638cc807030473173cc9b
```

20 entries, every geometry file prefixed `PRE-FABRICATION.` in its filename.
The served download's sha256 **matches the seal** (checked). Extracting it and
running the verifier it ships (`verify_luxexchange.py`) inside the backend
container returned:

```
LUXEXCHANGE VERIFICATION PASSED
  files checked  : 18
  content digest : 3ccee796b63f5f0e49a71cdd73e6cdae68475d5e78140a8af71b2809eba13ace
```

That digest is the `content_digest` printed above: the package's own verifier
reaches the same number as the API that sealed it.

**Re-exporting the same design twice gives an identical `content_digest` and an
identical `package_sha256`** — verified, not assumed.

### The class is `pre_fabrication`, and it says why

The package will not call itself fabrication-capable:

```
ENGINEERING WARRANT — PRE-FABRICATION PACKAGE
class: PRE_FABRICATION
This package is PRE-FABRICATION. It is NOT fabrication-ready and must not be
built from. Every geometry file in it is marked PRE-FABRICATION in its filename.
WHY THIS PACKAGE IS NOT CLEAN
* fabrication: needs_input
* structure_static_v1: needs_input
```

That warrant is generated, not written by hand, and it names the professional
who must resolve each open check.

---

## 7. The BOM: every driver measured, no money invented

`complete: false`, **all seven totals `null`**. The rate card (`2026-09-v3`) is
the operator's to fill and this design needs **15 paths**, every one of them
named by the BOM:

```
install.days_per_tonne            materials.basalt_slab.fabrication.hours_per_m3
install.truck_payload_kg          materials.basalt_slab.finishing
joints.cross_material_owner       materials.basalt_slab.seam
contingency_pct                   materials.bronze_cast.fabrication.hours_per_m3
markup_pct                        materials.bronze_cast.finishing
workshop.overhead_pct             materials.bronze_cast.waste_factor_pct
                                  materials.stainless_316l_cast.fabrication.hours_per_m3
                                  materials.stainless_316l_cast.finishing
                                  materials.stainless_316l_cast.waste_factor_pct
```

What the BOM *does* deliver, measured rather than estimated:

- per-element masses and **exposed skin** (element area minus the joint contact
  area it does not finish) — `b1` 12.7006 m², `c1` 1.9753 m², `p1` 6.0083 m²,
  `t1` 0.7743 m²;
- **`crane_pick_kg` = 1,923.61** — the heaviest module, which is the only number
  a lift decision may use;
- 19.839 m of joint seam run and 1.4159 m² of bedded seam face;
- two lines are `NOT COMPUTABLE` rather than guessed (`b1`, `p1` material
  purchase): a slab count cannot be derived from mass,
  `basalt_slab.stock_size_mm` carries no thickness, and nesting a doubly-curved
  revolve onto flat stock needs an unroll the kernel does not do (ADR-056). The
  BOM says so in full sentences and suggests the fix (`buy_price` per kg or m³).

This is the honest shape of the money question: **the geometry is measured to
the gram and the price is missing, and the two are never confused.**

---

## 8. What is NOT certified — three checks, three named professionals

| check | why it cannot evaluate | what is required |
|---|---|---|
| `structure_static_v1.overturning_safety_factor` | `public_plaza.design_wind_speed_m_s` is **null** — no wind speed has been supplied | the local wind map, or the project's structural engineer |
| `structure_static_v1.ground_bearing_pressure_kpa` | `public_plaza.allowable_bearing_kpa` is **null** — the piece applies 10.0 kPa over 5.760 m² (incl. 786.7 kg water) but there is nothing to compare against | a geotechnical survey for the actual site |
| `fabrication.rigging_declared` | all 4 elements exceed the 50 kg manual-handling limit, so lift points must be declared — geometry cannot derive them | a rigging reviewer |

**`public_plaza.signed_off` is `false`.** Nothing here is a defect: inventing a
wind speed or a bearing pressure would be fabricating engineering data, which
Rule 2 forbids. The design is complete; the **site** is what is missing. Supply
those three values in `config/gate_profiles.yaml` (or via a confirmed brief
intake, which binds site facts automatically), rebuild, and the same request
re-validates with no geometry change.

---

## 9. Renders: not available on this machine, and the platform says so

A render job was submitted and behaved exactly as the logs predict:

```
POST /api/render/jobs  ->  HTTP 200, job c34701df56a14f10, 4 views queued
GET  /api/render/jobs/c34701df56a14f10
  ->  {"status":"failed",
       "error":"render-worker produced no result within 90s — is the
                render-worker container running? (docker compose ps render-worker)"}
```

The job staged correctly (`data/render_scratch/c34701df56a14f10/input.glb`,
589,332 bytes — the sculpture's own mesh). **Only the `render-worker` (Blender)
image is missing on this machine**: `docker images` lists exactly two images
(backend, frontend) and `docker compose ps` shows backend, frontend and
geo-worker. So renders are unavailable here, for the same reason
`gate_phase9b_auto` reads NOT RUN rather than PASS (see `NEXT.md`). It is not a
failure of the sculpture and it is not a hidden pass.

**What you can look at today, at $0:**

- the viewport UI at **http://localhost:5173** — the design is already listed
  (`GET /api/geometry/assembly/designs` returns it with `scene_glb_url`);
- `data/sculpture_runs/098f640e-.../luxexchange_v1.zip` → its `SVG` plan and
  elevation sheet opens in any browser;
- the `GLB`, in the three.js viewport or any viewer.

---

## 10. One real finding — the bearing footprint is a rough upper bound

Found during this run, **not fixed, deliberately**: the structural gate computes
ground bearing over the **root element's bounding rectangle** (`gates.py:421`,
"footprint, in WORLD coordinates"). This sculpture's root is a **cylindrical**
plinth, so the gate divided by 2400 × 2400 = 5.760 m² when the true plan area is
π × 1.200² = **4.524 m²**:

```
as reported  : 5,858.7 kg x 9.81 / 5.760 m2 = 10.0 kPa
true circular: 5,858.7 kg x 9.81 / 4.524 m2 = 12.7 kPa   (+27 %)
```

For a round base the bounding box **understates** the pressure. Today it is
harmless because `allowable_bearing_kpa` is null, so no verdict is emitted — but
if the operator signs off, say, 12 kPa allowable, the gate would report **PASS at
10.0 kPa while the real pressure is 12.7 kPa**. `DEVELOPMENT_AUDIT.md` row 7
already flags the bbox footprint as unconservative; this run puts exact numbers
on the circular case. **Proposed as a debt for the operator to number and
prioritise** — the fix belongs to whoever owns the structural gate, not to a
sculpture run.

---

## 11. What was and was not touched

**Not changed:** any file under `backend/`, `config/`, `schemas/`, `tests/`,
`docker*`, `pyproject.toml`. No gate script. No phase report. `NEXT.md` is
untouched, because this design is not a slice in the queue.

**Added (new files only):**
`sculptures/entoto_halo/request.json` (the design),
`sculptures/entoto_halo/README.md`,
`scripts/build_sculpture.py` (the reproducible driver),
`docs/operator/13_building_a_sculpture.md` (the guide),
this report.

Because nothing in the backend changed, the standing auto-gate roster and the
pinned-image chain are untouched and no rebuild is required.

**Provider spend: $0.00.** No Council session was run. The AI-Council path to a
Design Spec is a separate, paid step, and — per `NEXT.md` — the last live attempt
HALTED when a provider dropped mid-call and its reservation went UNCERTAIN at a
$3.27 bound against the $5 cap. Run `/lf-spend` before spending on it.

**Side effect to be aware of:** each build inserts a design row. Repeated builds
left several rows for this sculpture (same `spec_hash`, different `design_id`);
they are visible in the UI's design list and can be pruned from the operator's
own database whenever convenient.
