# PHASE_8_VALIDATION_GATE_PLAN.md — L5 Validation Gate

Original draft 2026-08-21. **Design review and rewrite 2026-08-21** after
reading the shipped slice (`backend/app/geometry/gates.py`,
`backend/app/api/routes_assembly.py`, `tests/test_validation_gates.py`) and
probing the running containers.

Phase 8 turns validation from "watertight mesh exists" into a layered design
gate for geometry, structure, hydraulics and fabrication.

---

## Part 1 — Review of the shipped slice

The slice is real code with passing tests (`12 passed` in
`luxuryform-backend-1`). It is not fake. But eight design defects mean it
does not yet meet its own gate, and two of them touch Rule 1 (no
placeholders) and Rule 12 (honest failure).

### D1 — The fabrication gate cannot fail in the real API path

`assemble()` already raises `ConstraintViolation` for `mass > max_lift_kg`
and `bbox > max_module_m` (`assembly.py:423-443`) **before** it returns a
manifest. `validate_fabrication_gate` re-checks exactly those two numbers on
a manifest that, by construction, already passed them. In the live `/build`
path the request 422s and no fabrication report is ever written for a
failing design. The only way the gate fails is a hand-built dict in
`tests/test_validation_gates.py::test_fabrication_gate_fails_oversized_module`.

Phase 8 is currently duplicating a Phase 6 constraint rather than adding a
layer.

### D2 — Two fabrication checks are tautologies

```python
checks.append(GateCheck(check=f"{eid}.min_feature_floor_mm",
                        severity="info", passed=True,
                        value=feature_floor, limit=feature_floor, ...))
```

`value == limit`, `passed` hardcoded `True`. Nothing is compared. This is a
placeholder wearing a check's clothes, which Rule 1 forbids. The plan's
stated fabrication scope — tool access, split-line feasibility, minimum tool
radius, per-module rows — is otherwise unbuilt.

### D3 — `severity` conflates check policy with check outcome

`severity` is assigned `"fail"` when the check fails and `"info"` when it
passes. So severity is a *restatement of the outcome*, not a property of the
check. There is no way to express "this is a warn-level check and it was
violated". Consequence: every implemented check is hard binary, and the only
`warn` in the whole system is a hardcoded missing-context note.

### D4 — The centre-of-mass check cannot fail, and can emit invalid JSON

```python
x = float(placement.get("x") or 0.0)   # placement ORIGIN, not centroid
...
cog_offset = math.hypot(mx/total, my/total) if total > 0 else math.inf
support_radius = max(root_bbox[:2]) / 2.0   # assumes root centred on origin
```

Three separate faults:

- It weights the **placement origin**, not the element centroid. A hollow
  basin's mass is in its walls, not at its axis point. Every element the
  system currently produces sits at `x=0, y=0`, so `cog_offset` is always
  exactly `0.0` and the check has never once discriminated.
- `support_radius` assumes the root footprint is centred on the world
  origin. Any root with a lateral offset makes the comparison meaningless.
- The `math.inf` branch is persisted through `json.dumps`, which emits bare
  `Infinity`. Verified in the container: `json.dumps({"v": math.inf})` →
  `{"v": Infinity}`. That is not valid JSON; it breaks any strict parser
  reading `validation_reports.numbers_json`, including the export package.

The plan promised support span, load path and unsupported-span warnings.
None of the checks a monumental fountain actually needs — overturning under
wind, ground bearing pressure — are present.

### D5 — The hydraulic gate is inert by construction

`water` and `hydraulic_network` are free-form `dict | None` fields on
`AssemblyBuildRequest` with no schema, and **nothing in the Design Spec →
`spec_mapper` → assemble path populates them**. In every real run the gate
returns the single "no active water choreography" warning. It is honest, but
it has never evaluated a fountain.

`3.0 <= bore <= 150.0` is a hardcoded magic range. Rule 11 requires ranges
to derive from material and engineering arithmetic with the reasoning
recorded. A nozzle bore follows from flow and jet velocity
(`d = sqrt(4Q / (pi·v))`), not from a literal in a Python file.

### D6 — `warn` is persisted and reported as `pass`

`LayeredGateReport.passed = status != "fail"`, then
`ValidationReportRow.passed = 1 if report.passed else 0`, then
`/latest/validation` returns `passed: all(bool(row.passed))`, then
`ValidationPanel.tsx` renders `validation.passed ? "PASS" : "FAIL"` in the
header.

A design with a warning on every layer displays a green PASS badge. The
plan's own gate criteria say "The frontend shows pass/warn/fail status for
every validation layer" and "the UI shows validation status without implying
warnings are passes". The current code does exactly what the plan forbids.

Worse, `warn` is doing two incompatible jobs: *"we checked and it is
marginal"* and *"we could not check at all"*. Those must never share a
status.

### D7 — Reports are not self-describing

The report records `value` and `limit` but never **where the limit came
from**, and never which threshold set was in force. An archived report
cannot be re-read a year later, and Phase 11 already assumes a "validation
profile" retrieval key that does not exist.

### D8 — `schema` as a Pydantic field name

Confirmed live on pydantic 2.10.4 — this fires on the real class, on every
import, not only in a synthetic test:

```
pydantic/_internal/_fields.py:192: UserWarning: Field name "schema" in
"LayeredGateReport" shadows an attribute in parent "BaseModel"
```

It works today and warns; it is a latent break on upgrade.

---

## Part 2 — Corrected design

### C1 — Status vocabulary: four values, never three

| status | meaning |
| --- | --- |
| `pass` | checked, inside limits |
| `warn` | checked, inside limits but marginal, or a non-blocking policy breach |
| `fail` | checked, outside limits — blocks acceptance |
| `needs_input` | **not checkable** — a required input was absent |

`needs_input` is the fix for D6. "We could not check the hydraulics" stops
masquerading as "the hydraulics are fine". A gate is `needs_input` if any of
its checks is, and no `needs_input` gate may be reported as passing.

Rollup order: `fail` > `needs_input` > `warn` > `pass`.

### C2 — `GateCheck` carries policy and provenance

```python
class GateCheck(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    check: str
    status: Literal["pass", "warn", "fail", "needs_input"]   # OUTCOME
    on_violation: Literal["warn", "fail"]                    # POLICY, declared up front
    value: float | int | str | list | None                   # never non-finite
    limit: float | int | str | list | None
    units: str | None
    basis: str            # provenance of the limit — REQUIRED
    message: str
```

`basis` is the Rule 11 enforcement point. Every limit names its source:
`"materials.yaml:basalt_slab.min_wall_mm"`,
`"spec.fabrication.max_lift_kg"`,
`"gate_profiles.yaml:public_plaza.design_wind_pressure_pa"`,
`"derived: d = sqrt(4Q/(pi·v)); v from gate_profiles.yaml:jet_velocity_m_s"`.
A check with an empty `basis` is a build error, not a review comment. This
retires D7 and makes D5's magic constants structurally impossible.

`value` is sanitised on construction: non-finite becomes `None` with status
`fail`. Retires the `Infinity` half of D4.

Rename the model field `schema` → `schema_id` with
`Field(serialization_alias="schema")`, so the JSON wire shape is unchanged.
Retires D8.

### C3 — `config/gate_profiles.yaml`, versioned and reasoned

Thresholds that are not material-derived belong in config with their
engineering rationale recorded beside them, exactly as `materials.yaml`
already does:

```yaml
version: 1
profiles:
  public_plaza:
    design_wind_pressure_pa: <value>      # rationale: <basis, source, fetch date>
    allowable_bearing_kpa: <value>
    min_freeboard_mm: <value>
    min_reservoir_turnover_min: <value>
    jet_velocity_m_s: <value>
    overturning_safety_factor: <value>
  indoor_lobby: {...}
  private_garden: {...}
```

The profile id is stored on the report; Phase 11 gets its "validation
profile" retrieval key for free. **Values are deliberately left blank in
this plan** — they are an operator/engineering decision recorded in the ADR
at approval time, never a Python literal chosen by the author.

### C4 — Fabrication becomes a real layer, not a Phase 6 echo

Two changes.

**Diagnostic build mode.** `assemble(..., strict=True)` keeps today's hard
`ConstraintViolation` — the AI fabrication loop needs a hard refusal. The
operator-facing API calls `strict=False`: geometry is still produced, and
mass/module overruns arrive as `fail` rows in the fabrication report instead
of a 422 with nothing to look at.

This is the product fix behind D1. The operator should *see* the 4-tonne
plinth in the viewport and be told it is 4 tonnes, not get an error page.
The AI path is unaffected.

*This changes signed Phase 6 behaviour and needs an ADR plus approval before
implementation.*

**Checks that actually compare something** (replacing D2's tautologies):

- `{eid}.wall_mm` vs `materials.yaml` min wall — moved here from structure,
  where it does not belong.
- `{eid}.module_split_count` — for an element over `max_module_m`, the module
  count along the worst axis, and whether any required split plane lands
  inside a declared joint interface. Real arithmetic on manifest numbers.
- `{eid}.bore_aspect_ratio` — `depth / bore_mm` for every internal cavity
  against the material's internal-radius floor. This is what "tool access"
  means numerically.
- `{eid}.lift_points` — `needs_input` until the spec carries rigging data.
  Honestly absent beats falsely present.

### C5 — Structure becomes `structure_static_v1` and gains the two checks that matter

Rename so nobody reads it as FEA. Then:

- **Centroids.** `assemble()` already holds every element solid; it adds
  `centroid_mm: {x, y, z}` to each manifest element — one line at
  `assembly.py:413`. The gate then weights real centroids instead of
  placement origins.
- **World-space footprint.** Root footprint from the root's world bbox
  min/max, not `max(dim)/2` assumed centred on the origin.
- **Overturning** (new): restoring moment `m·g·b` versus wind moment
  `p·A_projected·z_centroid`, against `overturning_safety_factor`.
  Rigid-body statics, computable from the manifest today, and it is the
  check that decides whether a 3 m outdoor monument is safe.
- **Ground bearing pressure** (new): `m·g / A_footprint` versus
  `allowable_bearing_kpa`. Tells the operator what foundation the piece
  needs — direct commercial value.
- Both are labelled in `message` as rigid-body approximations, not FEA.

### C6 — Hydraulics gets a typed context and real arithmetic

Define `water_context_v1` as a Pydantic model on the request, populated by
`spec_mapper` from the Design Spec. Until Phase 12 supplies those fields the
gate returns **`needs_input`**, not `warn`.

Checks, each with a derived `basis`:

- `reservoir_turnover_min` = `capacity_l / flow_l_per_min` versus profile
  minimum.
- `freeboard_mm` = `height − floor − operating_depth` versus profile
  minimum — the splash-out check.
- `nozzle_bore_mm` — declared bore versus the bore the declared flow
  requires at profile jet velocity, `d = sqrt(4Q/(pi·v))`, tolerance banded.
  Replaces the `3..150` literal.
- `drain_slope` — floor slope sign toward the declared drain node.
- `service_void_mm` — clear annulus between column bore and basin inner wall
  for pipe runs, versus the material internal-radius floor.

### C7 — Persistence and API stop collapsing status

- `validation_reports` gains a `status TEXT` column via the existing startup
  schema-patch mechanism (ADR-023). `passed INTEGER` stays for back
  compatibility, redefined as `status == "pass"` — **not** `!= "fail"`.
- `/latest/validation` returns `overall_status` using the C1 rollup, plus
  per-gate `status`, plus `gate_profile_id` and `gates_version`.
- `ValidationPanel.tsx` header renders the worst status across gates with
  four badge states. A `needs_input` gate renders amber with the missing
  field named, never as PASS.

---

## Part 3 — Ordering defect this review exposes

**Phase 8 cannot fully close before Phase 12.** The hydraulic gate is only
reachable once brief intake normalises water, site and climate context (C6).
The current plan set has Phase 12 last.

Resolution — do not reorder, redefine closure:

- Phase 8 closes with `needs_input` accepted as a legitimate terminal
  hydraulic status, provided the gate demonstrably evaluates real numbers
  when context is injected by hand in a test.
- A short **Phase 8b re-gate** runs after Phase 12, asserting the hydraulic
  layer reaches `pass`/`warn`/`fail` from a real brief with no hand-injected
  context.

---

## Part 4 — Revised gate

Phase 8 closes when:

1. A valid multi-primitive assembly returns `structure_static_v1`,
   `hydraulics`, `fabrication` and `assembly_mesh` reports, each with a
   four-value status and a non-empty `basis` on every check.
2. A deliberately overweight element **builds geometry** and returns
   `fabrication: fail` with the measured mass and limit — not a 422.
3. A laterally offset mass **fails** the overturning check with a real safety
   factor, proving C5 discriminates where D4 could not.
4. A design with water context injected returns hydraulic `pass`/`warn`/
   `fail` with derived nozzle bore and turnover values; without it, returns
   `needs_input` naming the missing fields.
5. Every persisted `numbers_json` parses under
   `json.loads(..., parse_constant=<raise>)` — no `Infinity`, no `NaN`.
6. `/latest/validation` reports `overall_status: warn` for a warned design,
   and the UI header shows WARN, not PASS.
7. `gate_profiles.yaml` loads, validates at startup, and its profile id and
   version appear on every persisted report.
8. Tests cover pass, warn, needs_input and fail per layer, plus the
   non-finite guard and the warn-is-not-pass regression.
9. `scripts/gate_phase8_auto.py` runs at $0, non-interactive, clear exit
   code; `gate_phase8_visual.md` covers the four badge states by eye.

## Part 5 — Build order

1. C2 + C1 (status vocabulary, `basis`, non-finite guard, `schema_id`) — pure
   refactor of `gates.py`, no new behaviour, tests updated in the same commit.
2. C3 `gate_profiles.yaml` + startup validation.
3. C5 structure: manifest `centroid_mm`, world footprint, overturning,
   bearing.
4. C7 persistence + API + UI honesty.
5. C4 fabrication: ADR for diagnostic build mode → approval → implement.
6. C6 hydraulics: typed `water_context_v1`, derived checks, `needs_input`
   path.

Steps 1–4 correct shipped code and carry no new dependencies. Steps 5–6
change signed behaviour or depend on Phase 12, and are gated on operator
approval.
