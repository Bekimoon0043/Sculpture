# PHASE_6_SLICE_A_ENVELOPES.md — DRAFT for operator correction (2026-08-17)

**STATUS: DRAFT. Nothing is built to these numbers.** Every value in Part 2
and Part 3 is my proposal with the arithmetic shown, for you to correct.
Cross out, overwrite, or tell me the driver is wrong — then I build to the
corrected sheet, and it becomes `materials.yaml` + the primitive registries
with the reasoning recorded in the ADR (the ADR-027 / ADR-029 pattern).

**Basis honesty (ADR-009, standing):** these are WORKSHOP envelopes set by
the fabricator — you. They are not citations of an external standard and no
standard was fetched to set them. Where a number comes from computed
arithmetic, the arithmetic is shown and is mine; where it comes from
judgement about what your workshop will actually build, it is marked
*judgement* and needs your correction most.

---

## Part 1 — Inherited unchanged. Nothing to sign off here.

Already derived, already in force, already gated. Slice A reuses them and
does **not** re-derive them.

| value | basalt_slab | cast_concrete_c35_45 | bronze_cast | stainless_316l_sheet | source |
|---|---|---|---|---|---|
| wall envelope (mm) | 20–250 | 75–300 | 6–40 | 3–20 | ADR-027 |
| fall-gap floor `min_clearance_mm` (mm, diametral) | 40 | 50 | 20 | 20 | ADR-029 |
| density (kg/m³) | 2700 | 2400 | 8800 | 8000 | materials.yaml |

---

## Part 2 — NEW per-material values. **These need your sign-off.**

### 2.1 `joint_overlap_mm` — the interference at every mating joint

The rule this implements: **every joint is a real overlap, never a contact**
(ADR-029 generalised, which you accepted). ADR-029 measured that zero is a
knife-edge singularity and any positive value is geometrically sound — so
the floor is **not** set by the CAD. It is set by fabrication tolerance:
*if the CAD overlap is smaller than the real tolerance stack of the two
mating faces, the model says the parts interfere and the stone says there is
a gap.*

Arithmetic: `joint_overlap_floor = 2 × (per-face tolerance) + margin`,
rounded up to a round number.

| material | per-face tolerance (*judgement*) | 2 × tol | **proposed floor** | margin over CAD threshold |
|---|---|---|---|---|
| basalt_slab | ±3 mm (carved/CNC monumental stone) | 6 mm | **10 mm** | 10× the 1.0 mm tessellation deflection |
| cast_concrete_c35_45 | ±5 mm (formwork deflection + aggregate bulge) | 10 mm | **15 mm** | 15× |
| bronze_cast | ±1.5 mm (cast then chased) | 3 mm | **5 mm** | 5× |
| stainless_316l_sheet | ±0.5 mm (laser cut, press formed) | 1 mm | **3 mm** | 3× |

**Cross-material joints take the MAX of the two floors** — a bronze column
on a basalt plinth uses 10 mm, not 5 mm. That is a rule, not a number, and
it needs no table.

*The number I am least sure of is concrete's ±5 mm. If your formwork is
better than that, this floor should come down.*

### 2.2 `min_feature_mm` — the smallest projecting detail that survives

The smallest rib, fin, step or petal thickness the process will actually
reproduce. Below this the feature chips off, fails to fill, or disappears
into the surface finish. This is what stops slice C's blade and petal arrays
being specified into fiction.

| material | **proposed** | basis (*judgement*) |
|---|---|---|
| basalt_slab | **15 mm** | monumental carving chips out below this on a projecting edge |
| cast_concrete_c35_45 | **25 mm** | governed by aggregate: C35/45 with 20 mm aggregate cannot reproduce finer detail |
| bronze_cast | **2 mm** | casting reproduces fine detail well; chasing recovers the rest |
| stainless_316l_sheet | **= wall thickness** (min 3 mm) | a formed sheet feature cannot be thinner than the sheet |

### 2.3 `min_internal_radius_mm` — the tooling radius at internal corners

A sharp internal corner is not manufacturable in any of these materials;
this is the radius the tool actually leaves. It also protects the kernel: it
is the value the rim treatments in slice B will be floored against.

| material | **proposed** | basis (*judgement*) |
|---|---|---|
| basalt_slab | **10 mm** | diamond cup wheel / ball-nose CNC practical minimum |
| cast_concrete_c35_45 | **10 mm** | standard formwork corner fillet |
| bronze_cast | **3 mm** | pattern-maker's fillet |
| stainless_316l_sheet | **= wall thickness** (min 3 mm) | press-brake inside radius ≈ one material thickness |

Note two of these are **formulas, not constants** — 316L scales with sheet
thickness. That is deliberate: a constant would be wrong across the 3–20 mm
envelope.

---

## Part 3 — The three slice-A primitives

Ranges are the PLATFORM envelope (union across materials, the ADR-027
pattern); per-material constraints then narrow them. Values marked
*inherit* are taken from the existing cascade registry unchanged so the two
vocabularies cannot drift apart.

### 3.1 `basin_round`

| parameter | unit | default | min | max | basis |
|---|---|---|---|---|---|
| `diameter_mm` | mm | 2600 | 400 | 6000 | *inherit* `basin_diameter_mm` |
| `height_mm` | mm | 450 | 200 | 900 | *inherit* `basin_height_mm` |
| `wall_mm` | mm | 20 | 3 | 300 | *inherit* union of ADR-027 envelopes |
| `floor_mm` | mm | = `wall_mm` | 3 | 400 | new: floor may be thicker than the wall (it carries the water load), never thinner — **hard constraint: `floor_mm >= wall_mm`** |
| `min_clearance_mm` | mm | 100 | 20 | 1000 | *inherit* ADR-029 |

### 3.2 `plinth`

| parameter | unit | default | min | max | basis |
|---|---|---|---|---|---|
| `top_diameter_mm` | mm | 900 | 200 | 3000 | judgement: below 200 it is a boss, above 3000 it is a basin |
| `height_mm` | mm | 600 | 100 | 1500 | **taxonomy bound**: taller than 1.5 m it is a column, not a plinth. Stated as a definition, not an engineering limit |
| `wall_mm` | mm | 0 (solid) | 0 or 3 | 300 | 0 = solid; otherwise the ADR-027 envelope. Hollowing is the real mass lever — see 4.2 |
| `taper_deg` | deg | 0 | 0 | 15 | judgement: beyond 15° it reads as a cone/monolith, which is a slice-C primitive |

### 3.3 `sculptural_column`

| parameter | unit | default | min | max | basis |
|---|---|---|---|---|---|
| `diameter_mm` | mm | 200 | 80 | 1200 | min *inherits* `column_diameter_mm`; max raised 600→1200 for monumental standalone use (the cascade's 600 was a core inside a basin) |
| `height_mm` | mm | 1200 | 300 | 6000 | judgement: monumental range |
| `wall_mm` | mm | 0 (solid) | 0 or 3 | 300 | as plinth |
| `bore_mm` | mm | 0 (none) | 0 or 25 | 150 | *inherit* `bore_diameter_mm` range |
| `taper_deg` | deg | 0 | 0 | 15 | as plinth |

**Hard constraints carried across all three:** the existing wall envelope
(2), the clearance floor (7), plus new (8) `floor_mm >= wall_mm`,
(9) `joint_overlap_mm >= material floor`, (10) `min_internal_radius >=
material floor`, (11) any projecting feature `>= min_feature_mm`.

---

## Part 4 — What is deliberately NOT in any table

Per your confirmation that lift and transport limits genuinely vary per
project across Africa, the Gulf and Asia, these are **computed per spec**,
never tabulated:

### 4.1 Mass against `fabrication.max_lift_kg`

`mass = volume(params) × density(material)`, checked per element, violation
printing both numbers. Real reference point from the Phase 4 gate: the
fabricated basalt cascade measured **1.2713 m³ → 3,432.48 kg**.

### 4.2 Worked example — why hollowing, not shrinking, is the lever

A 1.0 m diameter × 1.0 m tall basalt plinth:

- **solid**: π × 0.5² × 1.0 = 0.7854 m³ × 2700 = **2,121 kg**
- **hollow, 180 mm wall**: π × (0.5² − 0.32²) × 1.0 = 0.4637 m³ × 2700 = **1,252 kg**

Same silhouette, 41% less mass. Against a declared `max_lift_kg` of 2,000 the
solid plinth is refused and the hollow one passes — and the constraint
message will say exactly that, so the design conversation is about
hollowing rather than about shrinking the client's plinth.

*(Cross-check that this method agrees with what is already in force: ADR-027
set basalt's 250 mm wall ceiling from π × (3² − 2.75²) × 0.9 × 2700 ≈ 11.0 t
on the largest registry basin. Same arithmetic, same source of truth.)*

### 4.3 Module size against `fabrication.max_module_m`

Any element whose bounding box exceeds the declared module drives
segmentation — which is a slice-C concern, but the CHECK lands in slice A so
an oversized element is never silently produced.

---

## Part 5 — Per-member walls, and how the Phase 2 hash is protected

You approved per-member walls as a slice-A decision. Each primitive gets its
own `wall_mm`, and `tiered_cascade` gains **`column_wall_mm`**, with hard
constraint 4 changing from

```
column_diameter_mm >= bore_diameter_mm + 2 * basin_wall_mm
```
to
```
column_diameter_mm >= bore_diameter_mm + 2 * column_wall_mm
```

**`column_wall_mm` defaults to `basin_wall_mm`.** With defaults unchanged the
computed geometry is bit-for-bit what it is today, so the Phase 2 canonical
STEP `e1a59fa6…` is preserved and Amendment 1 is untouched. The gate will
assert that hash explicitly as part of slice A, not assume it.

This closes LIMITATIONS §9's first bullet: the geometrist will no longer have
to thin your 180 mm basin wall to 60 mm to satisfy a column constraint — it
can set the column wall independently, which is what the Council designed.

---

## Sign-off

| section | needs your correction |
|---|---|
| Part 1 | no — already in force |
| **2.1 joint overlap** | **yes** — least sure: concrete ±5 mm |
| **2.2 min feature** | **yes** — all four are judgement |
| **2.3 min internal radius** | **yes** — all four are judgement |
| **3.1–3.3 ranges** | **yes** — especially the plinth/column taxonomy bounds |
| Part 4 | no numbers to sign — confirm the METHOD only |
| Part 5 | confirm the hash-protection approach |

Correct this sheet and I start slice A1.
