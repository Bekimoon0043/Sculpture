# PHASE_8_REPORT.md — L5 Layered Validation Gate

**Auto gate: PASS, 2026-08-21.** `scripts/gate_phase8_auto.py`, exit 0, $0,
no network, no provider keys.
**Visual gate: pending operator** — `gate_phase8_visual.md`.

ADRs: **ADR-034** (diagnostic build mode), **ADR-036** (four statuses).

---

## What this phase actually changed

The Phase 8 foundation slice shipped working code with passing tests. A
review on 2026-08-21 found that it did not meet its own gate. Eight defects,
each reproduced before being fixed.

### The worst one: a warning was displayed as a pass

`LayeredGateReport.passed` was `status != "fail"`. That flowed to
`ValidationReportRow.passed`, to the API, to `ValidationPanel`, which
rendered `validation.passed ? "PASS" : "FAIL"`.

Nothing populated the water context in a live run, so the hydraulic gate
*always* returned "no water choreography supplied" as a warning. **Every
design ever built displayed a green PASS for hydraulics that had never been
evaluated.**

Fixed by four statuses (ADR-036). `needs_input` — "we could not check" — is
now structurally distinct from `warn` — "we checked and it is marginal".
`passed` means `pass`, everywhere.

### The structural gate could not fail

The centre-of-mass check weighted `placement_mm`, the element's placement
origin — not its mass centroid. Every element this system produces sits at
x=0, y=0, so the check computed exactly `0.0` for every design ever built.
It had never once discriminated.

It also compared that against `max(root_bbox[:2]) / 2`, which assumes the
root is centred on the world origin, and its `math.inf` branch serialised as
bare `Infinity` — not valid JSON, and it would have broken any strict parser
downstream, including a fabricator's.

Now: `assemble()` records a real `centroid_mm` per element (from
`Solid.center(CenterOf.MASS)`) plus world-space `bbox_min_mm` / `bbox_max_mm`.
The gate weights real centroids by real mass against a real footprint.

Evidence from gate section 5:

```
ok    the built fountain passes overturning  — safety factor 24.888
ok    an 8 m mast on the same base FAILS overturning  — safety factor 0.698 < 1.5 required
ok    the two cases give different answers  — the old gate returned 0.0 for every design ever built
ok    ground bearing pressure is measured  — 4.84 kPa against 150.0 kPa allowable
```

### The fabrication gate re-checked what had already passed

`assemble()` raised on `max_lift_kg` / `max_module_m` **before** returning a
manifest, so the gate only ever saw manifests that had passed those checks
by construction. It could not fail in the live path; it only "failed"
against hand-built dicts in tests.

ADR-034 adds `strict=False` for the operator-facing route: a limit breach
now **builds the geometry** and reports the breach as a failing gate row.
The operator sees the 1550 kg basin *and* the number that disqualifies it.
The AI fabrication loop keeps `strict=True` — generated code that produces
an unbuildable part must be refused, not discussed.

### Two checks were tautologies

`min_feature_floor_mm` and `min_internal_radius_floor_mm` set
`value == limit` and `passed = True` unconditionally. Nothing was compared.
Rule 1 forbids placeholders; these were removed and replaced with checks
that measure something — module split count, bore aspect ratio, wall floors.

### Limits had no provenance

Every check now carries `basis`, naming its source. A check with an empty
basis fails the suite (`test_every_check_records_the_provenance_of_its_limit`).
Rule 11 became structural rather than aspirational.

Nineteen checks across three gates, every one provenanced.

---

## New engineering the gate performs

**Overturning.** Restoring moment `m·g·b` against wind moment `q·Cd·A·z`,
where `q = 0.5·ρ·v²`. Rigid-body statics — it says whether the piece tips,
not whether it cracks. The gate name `structure_static_v1` says so.

**Ground bearing pressure.** `m·g / A_footprint`, including stored water
mass when a water context is supplied. Tells the operator what foundation the
piece needs.

**Air density from site altitude.** Addis Ababa sits at ~2355 m:

```
ok  site air density is below sea level — 0.9711 kg/m3 at 2355 m vs 1.225 at sea level
```

Using the sea-level figure would overstate every wind moment LuxuryCon
produces in its own city by about 26%.

**Derived hydraulics.** The nozzle bore now comes from continuity,
`d = sqrt(4Q/(pi·v))`, replacing a hardcoded `3..150 mm` range that violated
Rule 11:

```
ok  the required bore is derived from flow and jet velocity
    — d = sqrt(4Q/(pi*v)) = 20.60 mm, band [15.45, 25.75]
ok  reservoir capacity is computed from the geometry — 839.63 L
```

Plus freeboard, reservoir turnover and service void.

---

## `config/gate_profiles.yaml`

New, versioned. Splits **physical constants** (gravity, ISA air density,
water density) from **site and policy thresholds** (operator-set, following
the `materials.yaml` precedent — tunable, not standard citations).

Three thresholds ship **empty on purpose**: `design_wind_speed_m_s`,
`allowable_bearing_kpa`, `overturning_safety_factor`. No honest default
exists for a site's wind map or its ground bearing capacity — presumed
bearing varies by more than ten times between soft clay and rock. Inventing
one would be exactly the fabrication Rule 2 forbids. They report
`needs_input` naming the field and who supplies it.

`signed_off: false` means a breach of a profile threshold reports `warn`,
not `fail`. Nothing is blocked on a number nobody has approved. Material and
Design Spec limits are always binding.

---

## Live defect found after the gate passed

The operator reported the Assembly tab rendering **fully black**. Two real
bugs, both reproduced against his own database:

1. **A crash.** `gates` includes the mesh report, which has neither `rows`
   nor `checks`. `(gate.rows ?? gate.checks).map(...)` threw, React
   unmounted the tree, and a blank page on a dark theme reads as black. This
   was a pre-existing bug, newly triggered because a stored design now
   existed to load on mount.

2. **The lie surviving in legacy rows.** Rows written before the `status`
   column have `status = NULL` and `passed = 1` under the old "did not fail"
   definition. The fallback `"pass" if row.passed else "fail"` resurrected
   the exact defect this phase exists to kill — a stored `warn` reported as
   `pass`.

Both fixed. `_row_status` now reads the stored JSON before falling back, and
returns `needs_input` when the status genuinely cannot be determined. The
panel never assumes a payload shape, and `ErrorBoundary` ensures a crash can
never again present as a black screen with no message.

Four regression tests cover it.

---

## PHASE 8 GATE: PASS (auto, offline, $0 - 2026-08-21)

## Gate evidence

```
[1/7] CONFIG — gate_profiles.yaml loads and validates          ok
[2/7] BUILD — a real three-primitive assembly with real centroids  ok
[3/7] PROVENANCE — 19 checks across 3 gates, all with provenance   ok
[4/7] HONESTY — needs_input is not a pass, warn is not a pass      ok
[5/7] DISCRIMINATION — 24.888 passes, 0.698 fails                  ok
[6/7] DERIVATION — bore from sqrt(4Q/(pi*v)), capacity 839.63 L    ok
[7/7] DIAGNOSTIC BUILD + JSON SAFETY                               ok

PASS — Phase 8 auto gate: all sections passed at $0.
```

Full suite: **309 passed**. Every other gate re-run and still passing —
phase 2, 3, 4, 6a1, costing.

---

## What is NOT closed

Phase 8 **cannot fully close until Phase 12**. Nothing in the brief → Design
Spec → assemble path populates `water_context_v1`, so a live run reports
`needs_input` for hydraulics. The gate evaluates real numbers the moment
context is supplied, proven in tests and gate section 6, but that supply
arrives with brief intake.

Resolution: `needs_input` is accepted as a legitimate terminal hydraulic
status for Phase 8, with a **Phase 8b re-gate** after Phase 12.

Full scope limits: `LIMITATIONS.md` §12. This is not FEA, wind is a single
static case, the silhouette is a bounding box, and seismic is not checked at
all.
