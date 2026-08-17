# PHASE_6_PLAN.md — The Primitive Library (2026-08-17)

**STATUS: APPROVED by the operator 2026-08-17.** Reclassification approved;
assembly-in-slice-A approved; count settled at SIXTEEN (§1);
`fabrication.max_lift_kg` / `max_module_m` confirmed as real workshop limits
and correct to make binding. Slice A is SPLIT into A1/A2 (§2.0) on the
operator's question about its size. Envelope sheet for slice A is out for
correction: `PHASE_6_SLICE_A_ENVELOPES.md`. **No code is written until that
sheet is signed off.**

Scope: the platform stops being a single-shape configurator and becomes a
design platform — a library of primitives that COMPOSE into one fabricable
assembly.

**GATE (operator, verbatim):** a brief that needs three different primitives
composed together produces one watertight assembly that passes validation
and exports cleanly.

---

## 0. Two findings that shape everything below

### 0.1 The Design Spec already models composition — since Phase 1

`schemas/design_spec_v1.json` `$defs/element` (required by `massing.elements`):

```
element_id      required
primitive       required — "Must exist in geometry/registry.py — e.g.
                basin_round, tiered_cascade, nozzle_ring, lotus_array, spline_loft"
parameters      required — "Validated against the primitive's own parameter
                schema in registry.py"
material_id     required
position        required — x_m, y_m, z_m, rot_z_deg
parent_id       optional — "Stacking: this element sits on parent"
service_voids   optional — plumbing | lighting | access_hatch
```

That is an assembly graph: typed nodes, parameters, placement, a parent
relationship, and declared penetrations. It has been in the contract since
Phase 1 and **Phase 4 discards it.** The passing live program read a
five-element massing (`outer_drum`, `ring_outer`, `ring_middle`,
`ring_inner`, `central_column`) and collapsed all five into ONE
`cascade_fountain` call, because that is the only vocabulary it has.

**So Phase 6 is not "invent composition". It is "honour the contract that
already exists".** That reframing matters: the schema, the Council prompts
and the Arbiter all already speak in elements. Only the registry and the
fabrication vocabulary are single-shaped.

### 0.2 The tangency rule generalises to every joint

ADR-029 measured it: two surfaces that TOUCH fuse into a solid that is not
watertight, and any positive separation is sound — a knife edge, not a
slope. The mirror of that result is the construction rule for all of Phase
6: **every mating joint must be a deliberate INTERFERENCE (a real overlap),
never a contact.** An assembly is a machine for producing coincident faces;
without this rule Phase 6 reproduces the ADR-029 defect once per joint.

---

## 1. The list, reclassified — and three of them are not primitives

**COUNT SETTLED (operator, 2026-08-17): SIXTEEN entries** — 13 registry
masses including `tiered_cascade`, 3 rim treatments, plus the nozzle fixture
family. That count is used everywhere from here. They are not all the same
KIND of thing:

**MASSES (13, including the existing `tiered_cascade`)** — solids that fuse into the assembly:
`basin_round`, `basin_elliptical`, `basin_rect`, `basin_spline`, `plinth`,
`sculptural_column`, `torus_ring`, `stepped_monolith`, `water_wall`,
`blade_fin_array`, `lotus_petal_array`, `spline_loft_mass`, `tiered_cascade`.

**RIM TREATMENTS (3)** — 2D profiles applied to a host mass's rim
(operator-approved reclassification, 2026-08-17):
`weir_edge`, `coping_profile`, `pool_edge_detail`

**FIXTURE FAMILY (1)** — features cut into or added onto a host:
`nozzle_ring`, plus the existing plumbing bore and lighting mounts.

**13 + 3 = 16 entries, plus the fixture family.**

**Why the treatments must not be primitives.** A weir edge, a coping and a
pool-edge detail are not objects that sit next to a basin; they are the
shape of the basin's rim. Building them as separate solids and fusing them
onto a rim is a post-hoc boolean on the most delicate feature of the part —
exactly the move ADR-010 already rejected for lip fillets ("drawn INTO the
dish profile as true circular arcs... no post-hoc 3D fillet() that could
fail at parameter extremes"). They belong in the host's profile, where the
existing proof holds.

The same argument makes `nozzle_ring` a fixture: the spec already calls
these `service_voids`, and `hydraulic_network.nodes[].nozzle_bore_mm`
already carries the dimension.

---

## 2. Question 1 — the build order, and why

Ordering principle: **by kernel-operation risk, and by what unlocks the
gate.** Not by the operator's list order, which mixes trivial and hardest.

The operator's gate needs three primitives COMPOSED. So the assembly
machinery must land in the FIRST slice with the cheapest primitives — not
after fourteen primitives exist. Everything after slice A is widening a
mechanism that is already gated.

### 2.0 Slice A is SPLIT — A1 (offline core) and A2 (AI + surfaces)

The operator asked whether slice A is too large for one slice. It is — see
the chat answer of 2026-08-17. Combined it would be the largest single slice
in the project's history, and it mixes deterministic offline geometry with
live AI integration and a frontend refactor. Split on that exact fault line:

**A1 — the assembly core, provable entirely offline at $0.** Registry
restructure, the 3 primitives, per-member walls, `assemble()`, assembly
validation, assembly determinism, AST narrowing. No AI, no API, no frontend.
*Gate A1 (auto, $0): three primitives composed into ONE watertight body;
`body_count == 1` at B-rep AND mesh level; every declared joint verified to
interfere; byte-identical STEP across two processes; the Phase 2 canonical
hash e1a59fa6… unchanged.*

**A2 — the AI and the surfaces.** Two-tier prompt surface, spec→assembly
mapping, designer index + spec validation, primitive-agnostic API, frontend
refactor. *Gate A2 = THE OPERATOR'S GATE: a brief needing three primitives
produces one watertight assembly, viewable and exportable.*

All the geometric risk lives in A1 and costs $0 to iterate on. A2 becomes an
integration slice over a proven core.

### Slice A1/A2 content — assembly machinery + 3 revolved masses

`basin_round`, `plinth`, `sculptural_column` + `registry.assemble()` +
assembly validation + the spec→primitive mapping.

Why these three: all are solids of revolution, the one construction proven
watertight across a full parameter sweep (Phase 2 + ADR-029); they are the
three parts of the commonest LuxuryCon object; and they exercise the two
joint types that matter (stack-on, concentric-insert). The riskiest thing
in slice A is the assembler, not the geometry — which is the correct place
to put the risk when the machinery is new.

**Gate A = the operator's gate**, achieved at the end of the first slice.

### Slice B — edge treatments + fixtures

`weir_edge`, `coping_profile`, `pool_edge_detail` as profile modifiers;
`nozzle_ring` as a fixture set driven by `service_voids` and
`hydraulic_network`.

Why second: this is what makes a fountain a fountain rather than a stack of
masses, it binds geometry to the spec's water and hydraulic sections for the
first time, and it adds **zero new boolean risk** — treatments are drawn
into host profiles, fixtures are bores and bosses of the kind already proven.

*Gate B: a basin with a weir edge and a nozzle ring, where the weir depth
and nozzle bores come from `hydraulic_network`, not from the model's
invention.*

### Slice C — extrusion and array masses

`basin_rect`, `stepped_monolith`, `water_wall` (extrude/prism);
`torus_ring` (revolve, trivial); `blade_fin_array`, `lotus_petal_array`
(`PolarLocations` + fuse — confirmed present in build123d 0.11.1).

Why third: arrays are where the fuse count explodes — a 24-petal array is 24
booleans in one element — so they need slice A's assembly validation already
proven, and they are where **determinism of fuse ORDER** first bites.

*Gate C: a 24-element polar array inside a 3-primitive assembly, byte-
identical STEP across two processes.*

### Slice D — free-form

`basin_elliptical` (non-uniform `scale(by=(sx,sy,sz))` — the signature
exists in 0.11.1 and needs a spike, not an assumption), `basin_spline`,
`spline_loft_mass` (`loft` over `Spline` sections).

Why last, and a warning I would rather give now: **watertight-by-
construction may not be achievable for the spline masses.** A loft can
self-intersect at parameter extremes in ways no per-parameter range check
catches. If the spike shows that, these ship with a narrower guarantee —
validated per build rather than guaranteed by envelope — and that limit goes
in LIMITATIONS.md rather than being quietly papered over. Doing them last
means the assembly and validation machinery is mature before the least
constrainable geometry arrives.

*Gate D: a free-form mass composed with two library primitives, or an
honest limitation entry saying which part of the guarantee does not hold.*

---

## 3. Question 2 — how the registry surface scales

**Measured today: `registry_surface()` is 3,773 chars ≈ 943 tokens for ONE
primitive.** Seventeen registry entries at that density is ≈14k tokens of
surface in every fabrication call, re-sent on every repair attempt. At
anthropic's $3/MTok input that is ≈$0.042 per call in surface alone,
≈$0.13 per 3-attempt fabrication — against $0.046777 for an entire
successful fabrication today. Cost is the smaller problem; 14k tokens of
undifferentiated API reference in front of the actual task is the larger one.

Three changes, none of which give up ADR-026's anti-drift property (every
line below is still GENERATED from the live registry):

**(a) Two-tier surface.** An always-present INDEX — one line per primitive
(id, one-line purpose, joint types it accepts, parameter count) ≈250 tokens
for all seventeen. Then the FULL signature, parameter table and envelopes
for **only the primitives this spec uses**. A 3-primitive assembly carries
≈250 + ~2.8k ≈ 3k tokens instead of 14k.

**(b) Selection is computed in code, never chosen by the model.** The
primitives to expand come from `massing.elements[].primitive` — the spec
already names them. The model never picks its own reference material.

**(c) The DESIGNER gets the index, and the spec is validated against it.**
`element.primitive` already says "must exist in registry.py" and nothing
enforces it. Phase 6 puts the index in the designer prompt and validates
`primitive` against the live registry during spec validation, so an unknown
primitive becomes a bounded re-ask on Phase 3's existing machinery instead
of a fabrication failure three stages later. **This moves the failure left,
where it is cheap.**

**Cache structure — the first place ADR-024 pays measurably.** Order the
prompt `[index + selected detail + spec] → CACHE_BREAK → [failure history]`.
Every attempt within one fabrication run shares that prefix, so repair
attempts 2 and 3 read ~3k tokens at $0.30/MTok instead of $3.00 — 10×
cheaper. The cache token fields already persist per call (ADR-022), so
engagement is MEASURED, not assumed.

---

## 4. Question 3 — how primitives compose

### The GEOMETRIST does not fuse. It declares.

The generated program returns an **assembly plan** — placed primitives with
parameters and declared joints — and trusted registry code performs every
boolean. `registry.assemble(elements)` computes transforms, enforces the
joint rules, fuses in a canonical order, and cuts service voids last.

**Why not let the model assemble:** booleans are where OCCT fails, and we
have already watched the model reason itself into a tangency singularity on
a SINGLE primitive with one clearance parameter. Free-form boolean
authorship multiplies that failure class by every joint, and no constraint
system can catch a degeneracy the model constructs directly.

**Consequence — narrow the AST whitelist to `{registry, math}`, dropping
`build123d`** — recorded as a deliberate TRADE, at the operator's explicit
instruction (2026-08-17), not as a security footnote:

> **ADR-030 (draft) — the registry becomes the ceiling on geometric
> capability.** Dropping `build123d` from the AST whitelist means AI-written
> code can only reach geometry the registry exposes. The model can never
> reach for a kernel operation we have not deliberately published. **What we
> buy:** every constraint becomes enforceable rather than advisory, every
> boolean is performed by trusted code, and the failure class we measured in
> ADR-029 — the model reasoning itself into a geometric singularity — cannot
> be constructed directly. **What we give up:** novel form is gated on a
> registry edit. If a brief needs a shape the library does not have, the
> platform cannot improvise it, and the answer is a new primitive with its
> own envelopes and tests — a deliberate act with a gate, not an emergent
> one. **The operator accepts this ceiling knowingly (2026-08-17).** A future
> decision to widen it should be made against this record: the question to
> ask then is not "is build123d safe?" but "are we willing to make the
> constraint system advisory again?" — because that, and not sandbox escape,
> is what widening costs. The sandbox (ADR-005) remains the real security
> boundary either way; this trade is about correctness.

### Joint model — three kinds, matching the schema

| joint | meaning | from the spec |
|---|---|---|
| `stack_on(parent)` | child's base meets parent's top face | `parent_id` + `position.z_m` |
| `concentric_insert(parent)` | shared axis, inserted to a depth | `parent_id` + concentric position |
| `rim_treatment(host)` | profile applied to a host's rim | slice B treatments |

### The interference rule (the ADR-029 lesson, generalised)

Every mating joint overlaps by a real amount — `joint_overlap_mm`, floored
per material exactly as ADR-029 floors the fall gap. The assembler computes
placements to GUARANTEE the overlap and refuses any plan that would produce
a coincident-face contact. Zero overlap is the knife edge; positive overlap
is sound.

### Validating an assembly is not validating a solid

`validate_mesh` today measures one closed mesh. That is necessary and not
sufficient. Additions:

1. **`body_count == 1`.** The fatal silent failure is a floating element: a
   mesh can be perfectly watertight and still be two disjoint closed bodies.
   `build_cascade` already asserts `len(solids) == 1` at the B-rep level —
   extend that pattern to the assembly AND to the mesh.
2. **Per-joint overlap verified after placement**: for each declared joint,
   assert the two members actually intersect (intersection volume > 0)
   BEFORE the fuse. Exact, cheap, B-rep level, and it catches a mis-placed
   element that still happens to mesh watertight.
3. **Volume conservation**: Σ member volumes − Σ joint intersections ≈
   assembly volume, within tolerance. A large discrepancy means unintended
   interference — two elements occupying the same space. This is the
   assembly analogue of the existing 2% B-rep-vs-mesh cross-check.
4. **Per-element mass breakdown**, checked against `fabrication.max_lift_kg`
   and `fabrication.max_module_m` — see §5, this is what makes those dead
   schema fields load-bearing.
5. **Void check**: internal voids only where a `service_void` declared one.
6. Everything already measured: watertight, winding, degenerate faces,
   volume cross-check, bounds.

### Determinism must survive Phase 6

Fuse order is canonical — elements sorted by `element_id`, never dict or
insertion order. **The Phase 6 gate must prove byte-identical STEP for a
multi-element assembly across two processes**, exactly as Phase 2 does for
one solid. Amendment 1 is the platform's crown jewel; an assembly that
hashes differently on Tuesday ends the guarantee.

---

## 5. Question 4 — per-material envelopes and their arithmetic

**Position first, honestly.** Sixteen primitives × four materials is 60+
envelope tables, and those numbers are workshop judgement — the operator's,
not mine. ADR-027 and ADR-029 both record their bounds as workshop values
set by the fabricator, tunable, explicitly NOT citations of a standard. I
will not invent sixty numbers in a plan and present them as engineering.

What I propose instead is a **split that shrinks the invented surface to
almost nothing**, because most of these bounds should not be static tables
at all.

### Every bound comes from one of four drivers, and the ADR records which

1. **Material process envelope** — what the workshop can form, cast or carve
   in that material. *(ADR-027's wall envelopes are this.)* Static, per
   material, operator-set, small.
2. **Geometric integrity** — floors that keep the CAD out of a singularity,
   with measured margin. *(ADR-029's clearance floor is this; Phase 6 adds
   the joint-overlap floor.)* Static, small, derived from a measured sweep.
3. **Mass and handling** — **computed, not tabulated.** See below.
4. **Hydraulic function** — weir depths, nozzle bores, fall gaps. **Computed
   from `hydraulic_network`**, which the Council already fills.

### The important move: drivers 3 and 4 need no tables

ADR-027 set basalt's 250 mm wall ceiling from a mass calculation against
"the edge of handling". But the spec **already carries the real limits**:
`fabrication.max_lift_kg` and `fabrication.max_module_m` are REQUIRED
fields, filled per project by the Council, and currently **completely
unused by the geometry layer**.

So the handling bound should not be a static number per material at all. It
should be a computed constraint: *this element's mass, from its own volume ×
its material's density, against THIS project's declared `max_lift_kg`* —
with the arithmetic printed in the violation exactly like every other hard
constraint. Same for module size against `max_module_m`, and for hydraulic
dimensions against `hydraulic_network`.

That is strictly better than a table: it is traceable, it is per-project
rather than one-size-fits-all, it needs no invented numbers, and it turns
three dead required schema fields into working engineering.

**Net operator input required:** process envelope + geometric floors, per
PRIMITIVE CLASS rather than per primitive (basin variants share basin
numbers), per material. Realistically ~5 short tables — one per slice —
which I would bring for sign-off BEFORE building that slice, exactly the way
ADR-027 and ADR-029 were done.

### Worked example — `plinth`, to show the method end to end

| bound | driver | arithmetic |
|---|---|---|
| `plinth_wall_mm` | 1 process | inherits the ADR-027 material wall envelope unchanged (basalt 20–250, concrete 75–300, bronze 6–40, 316L 3–20) |
| `joint_overlap_mm` floor | 2 integrity | ≥ the material's ADR-029 class; measured margin over the tangency knife edge, same sweep method |
| `plinth_height_mm` max | 3 handling | **computed**: π·(d/2)²·h·ρ ≤ `max_lift_kg`. Basalt (ρ=2700), 1.0 m dia solid: 1.0 m tall = π·0.25·1.0·2700 = **2,121 kg**; at a declared `max_lift_kg` of 2,000 the constraint binds at h = 0.94 m and says so with both numbers. Same primitive, same material, a 5 t crane → a different legal height. No table can express that; the computation can. |
| `plinth_top_width` | 3 module | **computed** against `fabrication.max_module_m`, driving the segmentation count when it is exceeded |
| min feature / tool radius | 1 process | operator table, per material, per slice — carving tooling for basalt, forming radius for 316L |

---

## 6. Repo structure and schema changes

- `backend/app/geometry/primitives/` — one module per primitive, each
  exposing `PARAMETERS`, `validate(params, material)` and `build(params)`.
  `registry.py` becomes a REGISTRY (id → module) plus `assemble()`, and
  keeps its security note: everything importable is reachable by sandboxed
  code.
- `cascade.py` moves under `primitives/` unchanged — `tiered_cascade` stays
  a registered primitive, so Phase 4's proven path keeps working and the
  Phase 2 canonical STEP hash stays provable.
- `validate.py` gains `validate_assembly()` alongside `validate_mesh()`.
- **No Design Spec schema change** — `$defs/element` already carries what is
  needed. (`schema_version` bookkeeping only.)
- **DB**: `designs`/`generated_programs` gain an assembly manifest (elements,
  joints, per-element mass) via the ADR-023 additive-patch registry — no v5
  rebuild, operator's live database ALTERed at startup, data preserved.
- **API + frontend, easy to forget and real work**: `/api/geometry/cascade/*`
  and `CascadePanel.tsx` are single-primitive-shaped (the panel renders
  straight from `cascade/defaults`). They become primitive-agnostic —
  `/api/geometry/primitives`, `/api/geometry/{primitive}/defaults` — or the
  viewport stops matching the platform. Budgeted into slice A.

## 7. Cost

Per fabrication call, prompt surface ≈3k tokens instead of today's ~1.2k, so
≈$0.055–0.065 per call at anthropic rates, with repair attempts reading the
cached prefix at 10× less. A 3-primitive assembly plausibly needs more
attempts than a single primitive until first-attempt success is measured, so
budget ≈**$0.15–0.20 per assembly fabrication**, against $0.046777 for
today's single primitive. Still small beside a $0.84 Council session and far
inside the $5 session cap. I will report measured figures per slice the way
PHASE_4_REPORT.md does, and the per-round rates will say whether the repair
loop becomes corrective rather than merely diagnostic.

## 8. Risks and things I believe are wrong in the brief as written

1. **Three list items are not primitives** (§1) — building them as fusable
   solids would repeat the defect ADR-010 already fixed.
2. **The gate needs composition, so assembly must be slice 1, not slice 4.**
   The brief's "a few primitives, gated, then more" reads as primitives
   first, machinery later; that ordering cannot reach the stated gate until
   the very end.
3. **`basin_spline` / `spline_loft_mass` may not achieve watertight-by-
   construction.** Flagged now rather than discovered at gate D.
4. **The AST whitelist must narrow** (drop `build123d`) or every registry
   constraint becomes advisory the moment the model can fuse.
5. **`validate_mesh` assumes one solid**; a watertight two-body assembly
   would pass today. This is the most dangerous silent failure in the phase.
6. **Determinism must be re-proven for assemblies** or Amendment 1 quietly
   stops being true.
7. **The designer prompt must carry the primitive index**, or specs will
   keep naming primitives that do not exist.
8. **Count discrepancy** — fourteen / fifteen / sixteen (§1). Worth settling
   before we build to it.
9. **Phase 4's open limit lands here**: one wall parameter still serves
   basin, dishes and column (LIMITATIONS §9). Per-member walls are a
   slice-A registry decision, not a later cleanup.

## 9. What I need from the operator before slice A

1. Approval of the reclassification (§1) and of assembly-in-slice-A (§2).
2. A ruling on the count (§8.8).
3. The slice-A envelope table (§5): process envelope + min feature size +
   tool radius, per material, for basin / plinth / column. I will bring a
   filled draft with the arithmetic shown, for correction — not a blank form.
4. Confirmation that `fabrication.max_lift_kg` and `max_module_m` in the
   spec are the real handling limits for the workshop, since §5 makes them
   binding constraints rather than documentation.
