#!/usr/bin/env python3
"""PR-4 AUTO GATE — honest module transport costing (ADR-067). $0 forever.

Run inside Docker:
    docker compose exec backend python scripts/gate_pr4_auto.py

Non-interactive, offline, no AI call, no network, no database opened, and
the REAL rate card (config/costing.yaml) is proven byte-identical before
and after — every transport number in here is an injected in-memory TEST
value with no engineering meaning.

What it proves, with real numbers on both sides of every check:

  1. DETERMINISM — the same module set allocates identically twice, and
     identically again with the input order shuffled.
  2. THE REFUSAL — a module over the payload stops the line, naming the
     module and both numbers (operator amendment 3).
  3. THE DISPROOF — four 6 t modules at a 10 t payload: the retired
     lower-bound arithmetic said 3 trips, the loaded trucks say 4. Both
     numbers printed side by side; the old formula never returns.
  4. BOTH LIMITS BIND — a bed-bound case and a weight-bound case, each
     with the spare capacity that proves which limit stopped it.
  5. PER-TRIP TRUTH — through the full BOM: every trip prints its module
     IDs, masses, load and remaining capacity, and the invariants are
     re-verified INDEPENDENTLY of the allocator (ID partition, mass
     conservation by fsum, both capacities, unrounded).
  6. WORDING — the line says "a deterministic conservative feasible
     allocation" and the banned claims (assembled at runtime so this file
     never contains them) are absent from the line and the document.
  7. GUARDS — disagreeing module masses refuse with both sums; null rates
     stay MISSING_RATE on the same path as before PR-4; an unsegmented
     design stays NOT_COMPUTABLE; an incomplete mass raises
     IncompleteMassError BEFORE any allocation; malformed module records
     are rejected.
  8. THE DOCUMENT — the rendered BOM carries the trips table.
  9. HERMETICITY — config/costing.yaml byte-identical, $0, offline.
"""

from __future__ import annotations

import hashlib
import math
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

TOTAL = 9

#: assembled at runtime so THIS FILE never carries the banned claims
BANNED_TOKENS = ("mini" + "mal", "mini" + "mum", "opti" + "mal",
                 "max(" + "ceil(")


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/{TOTAL}] {title}")
    _hline()


def _check(failures: list[str], label: str, ok: bool,
           detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}"
          + (f" -- {detail}" if detail else ""))
    if not ok:
        failures.append(f"{label} -- {detail}")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assembly_report(**over):
    from app.geometry.validate import AssemblyValidationReport, VolumeCrossCheck
    data = {
        "glb_path": "/tmp/gate_pr4.glb",
        "element_count": 2, "joint_count": 1,
        "watertight": True, "winding_consistent": True, "body_count": 1,
        "volume_mm3": 5.067251e9, "surface_area_mm2": 67.0381e6,
        "degenerate_face_count": 0, "face_count": 4000,
        "element_masses_kg": {"p1": 2375.044, "b1": 11346.137},
        "total_mass_kg": 13721.181,
        "volume_crosscheck": VolumeCrossCheck(
            trimesh_volume_mm3=5.067251e9, build123d_volume_mm3=5.067251e9,
            delta_pct=0.0, tolerance_pct=2.0, within_tolerance=True),
        "passed": True,
    }
    data.update(over)
    return AssemblyValidationReport(**data)


def _manifest(module_records: dict, module_count: int, heaviest: float):
    return {"schema": "assembly_manifest_v1", "segmentation": {
        "schema": "assembly_segmentation_v1",
        "module_count": module_count,
        "heaviest_module_kg": heaviest,
        "not_segmentable": [],
        "elements": module_records,
        "seams": {
            "split": {"count": 12, "length_mm": 50112.0,
                      "area_mm2": 3531278.0},
            "joint": {"count": 1, "length_mm": 12566.371,
                      "area_mm2": 1256637.0},
            "total_length_mm": 62678.371,
        },
    }}


def _ten_module_manifest():
    return _manifest(
        {"p1": {"module_count": 1,
                "modules": [{"index": 0, "mass_kg": 2375.044}]},
         "b1": {"module_count": 9,
                "modules": [{"index": i, "mass_kg": 1300.0}
                            for i in range(8)]
                + [{"index": 8, "mass_kg": 946.137}]}},
        module_count=10, heaviest=2375.044)


def _test_card(bundle):
    """The injected TEST rate card — in memory only, arbitrary values,
    NEVER copied into config/costing.yaml."""
    from app.core.config import CostingConfig
    raw = bundle.costing.model_dump()
    raw["install"]["transport"] = {"amount": 8000.0, "currency": "ETB",
                                   "per": "trip"}
    raw["install"]["truck_payload_kg"] = 12000.0
    raw["install"]["modules_per_trip"] = 4
    raw["fx_rates"]["ETB"] = {"rate": 140.0, "as_of": "2026-08-01"}
    return CostingConfig(**raw)


def main() -> int:
    from app.core.config import load_config_bundle
    from app.costing.bom import (
        COMPUTED,
        MISSING_RATE,
        NOT_COMPUTABLE,
        build_bom,
    )
    from app.costing.drivers import IncompleteMassError, drivers_for_assembly
    from app.costing.report import render_bom
    from app.costing.transport import (
        AllocationInputError,
        NoFeasibleAllocation,
        allocate_trips,
        verify_allocation,
    )

    failures: list[str] = []
    yaml_path = REPO_ROOT / "config" / "costing.yaml"
    yaml_sha_before = _sha(yaml_path)
    print("PR-4 AUTO GATE — honest module transport costing (ADR-067)")
    print(f"config/costing.yaml sha256 (before): {yaml_sha_before}")

    bundle = load_config_bundle()
    basalt = bundle.materials.materials["basalt_slab"]

    # ------------------------------------------------------------------
    _section(1, "DETERMINISM — a pure function of the module set")
    mixed = ([(f"b1#{i}", 1300.0) for i in range(8)]
             + [("b1#8", 946.137), ("p1#0", 2375.044)])
    a1 = allocate_trips(list(mixed), 12000.0, 4)
    a2 = allocate_trips(list(mixed), 12000.0, 4)
    shuffled = list(mixed)
    random.Random(0).shuffle(shuffled)
    a3 = allocate_trips(shuffled, 12000.0, 4)
    for t in a1.trips:
        print(f"  trip {t.index}: {', '.join(t.module_ids)}  "
              f"load {t.load_kg:,.3f} kg")
    _check(failures, "identical input twice -> identical allocation",
           a1 == a2)
    _check(failures, "shuffled input -> identical allocation",
           a1 == a3, f"shuffle moved the order: {shuffled != mixed}")
    _check(failures, "the 10-module set loads onto 3 trips",
           a1.trip_count == 3, f"got {a1.trip_count}")

    # ------------------------------------------------------------------
    _section(2, "THE REFUSAL — a module no truck can carry")
    try:
        allocate_trips([("m_small", 1000.0), ("m_big", 6000.0)],
                       5000.0, 4)
        _check(failures, "over-payload module refused", False,
               "allocate_trips returned instead of refusing")
    except NoFeasibleAllocation as exc:
        print(f"  refusal: {exc}")
        _check(failures, "the refusal names the module",
               "m_big" in str(exc))
        _check(failures, "the refusal carries both numbers",
               "6,000" in str(exc) and "5,000" in str(exc))

    # ------------------------------------------------------------------
    _section(3, "THE DISPROOF — the retired lower bound vs loaded trucks")
    four = [(f"m{i}", 6000.0) for i in range(1, 5)]
    old_bound = max(math.ceil(24000.0 / 10000.0), math.ceil(4 / 4))
    alloc = allocate_trips(four, 10000.0, 4)
    print(f"  4 modules x 6,000 kg, payload 10,000 kg, 4 per bed")
    print(f"  retired lower-bound arithmetic : {old_bound} trips")
    print(f"  loaded trucks (this slice)     : {alloc.trip_count} trips")
    _check(failures, "the loaded count beats the bound",
           alloc.trip_count == 4 and old_bound == 3,
           f"{alloc.trip_count} vs {old_bound}")

    # ------------------------------------------------------------------
    _section(4, "BOTH LIMITS BIND — bed space and weight, separately")
    bed = allocate_trips([(f"m{i}", 1000.0) for i in range(1, 6)],
                         1_000_000.0, 2)
    print(f"  bed-bound: 5 x 1,000 kg, payload 1,000,000 kg, 2 per bed "
          f"-> {bed.trip_count} trips; trip 1 spare payload "
          f"{bed.trips[0].remaining_payload_kg:,.0f} kg, spare slots "
          f"{bed.trips[0].remaining_module_slots}")
    _check(failures, "bed space binds at 3 trips",
           bed.trip_count == 3
           and bed.trips[0].remaining_module_slots == 0
           and bed.trips[0].remaining_payload_kg == 998000.0)
    wt = allocate_trips([(f"m{i}", 1500.0) for i in range(1, 4)],
                        2000.0, 10)
    print(f"  weight-bound: 3 x 1,500 kg, payload 2,000 kg, 10 per bed "
          f"-> {wt.trip_count} trips; trip 1 spare payload "
          f"{wt.trips[0].remaining_payload_kg:,.0f} kg, spare slots "
          f"{wt.trips[0].remaining_module_slots}")
    _check(failures, "weight binds at 3 trips",
           wt.trip_count == 3
           and wt.trips[0].remaining_module_slots == 9
           and wt.trips[0].remaining_payload_kg == 500.0)

    # ------------------------------------------------------------------
    _section(5, "PER-TRIP TRUTH — the full BOM, invariants re-verified")
    card = _test_card(bundle)
    print("  (test rates — arbitrary values, NEVER copy these into "
          "costing.yaml)")
    drivers = drivers_for_assembly(_assembly_report(),
                                   _ten_module_manifest())
    bom = build_bom(card, drivers, "basalt_slab", basalt)
    line = {ln.line_id: ln for ln in bom.lines}["install_transport"]
    _check(failures, "install_transport is COMPUTED on the test card",
           line.status == COMPUTED, line.status)
    used = line.drivers_used
    print(f"  formula: {line.formula}")
    payload_kg = float(used["payload_kg"])
    per_trip = int(used["modules_per_trip"])
    seen_ids: list[str] = []
    loads = []
    for t in used["allocation"]:
        mods = " + ".join(f"{m['id']} ({m['mass_kg']:,.3f} kg)"
                          for m in t["modules"])
        print(f"    trip {t['trip']}: {mods}")
        print(f"      load {t['load_kg']:,.3f} kg; spare "
              f"{t['remaining_payload_kg']:,.3f} kg payload, "
              f"{t['remaining_module_slots']} module slot(s)")
        seen_ids.extend(m["id"] for m in t["modules"])
        loads.append(float(t["load_kg"]))
        _check(failures,
               f"trip {t['trip']} obeys the payload (unrounded record)",
               float(t["load_kg"]) <= payload_kg + 0.0005,
               f"{t['load_kg']} vs {payload_kg}")
        _check(failures, f"trip {t['trip']} obeys the bed count",
               len(t["modules"]) <= per_trip)
    module_ids = [mid for mid, _ in drivers.module_masses_kg]
    _check(failures, "every module id appears exactly once across trips",
           sorted(seen_ids) == sorted(module_ids),
           f"{len(seen_ids)} placed of {len(module_ids)}")
    total = math.fsum(m for _, m in drivers.module_masses_kg)
    _check(failures, "mass is conserved across the printed loads",
           abs(math.fsum(loads) - total) < 0.01,
           f"{math.fsum(loads):,.3f} vs {total:,.3f} kg")
    # and once more through the allocator's own independent gate, on a
    # fresh allocation of the same set
    verify_allocation(list(drivers.module_masses_kg), payload_kg, per_trip,
                      allocate_trips(list(drivers.module_masses_kg),
                                     payload_kg, per_trip))
    _check(failures, "verify_allocation confirms the same set", True)
    _check(failures, "trips priced: 3 x 8,000 ETB",
           used["trips"] == 3 and line.amount_native == 24000.0,
           f"{used['trips']} trips, {line.amount_native} native")

    # ------------------------------------------------------------------
    _section(6, "WORDING — feasible and conservative, nothing more")
    doc = render_bom(bom)
    _check(failures, "the line says what amendment 3 orders",
           "deterministic conservative feasible allocation" in line.formula)
    for token in BANNED_TOKENS:
        _check(failures,
               f"banned claim {token!r} absent from the line",
               token not in line.formula.lower())
        _check(failures,
               f"banned claim {token!r} absent from the document",
               token not in doc.lower())

    # ------------------------------------------------------------------
    _section(7, "GUARDS — every dishonest path refuses")
    # 7a. module masses that disagree with the validation report
    bad = _manifest(
        {"p1": {"module_count": 1,
                "modules": [{"index": 0, "mass_kg": 2375.044}]},
         "b1": {"module_count": 9,
                "modules": [{"index": i, "mass_kg": 1300.0}
                            for i in range(8)]
                + [{"index": 8, "mass_kg": 2000.0}]}},
        module_count=10, heaviest=2375.044)
    d_bad = drivers_for_assembly(_assembly_report(), bad)
    ln = {l.line_id: l for l in
          build_bom(card, d_bad, "basalt_slab", basalt).lines
          }["install_transport"]
    print(f"  disagreement blocker: {ln.blocker[:120]}...")
    _check(failures, "disagreeing masses refuse with both sums",
           ln.status == NOT_COMPUTABLE and "14,775.044" in ln.blocker
           and "13,721.181" in ln.blocker, ln.status)
    # 7b. a module over the payload, through the full BOM
    over = _manifest(
        {"b1": {"module_count": 2,
                "modules": [{"index": 0, "mass_kg": 13000.0},
                            {"index": 1, "mass_kg": 1000.0}]}},
        module_count=2, heaviest=13000.0)
    d_over = drivers_for_assembly(
        _assembly_report(element_masses_kg={"b1": 14000.0},
                         total_mass_kg=14000.0), over)
    ln = {l.line_id: l for l in
          build_bom(card, d_over, "basalt_slab", basalt).lines
          }["install_transport"]
    _check(failures, "an unliftable module refuses the BOM line too",
           ln.status == NOT_COMPUTABLE and "b1#0" in ln.blocker
           and "13,000" in ln.blocker and "12,000" in ln.blocker)
    # 7c. the REAL card's nulls keep the pre-PR-4 status and path
    d_ok = drivers_for_assembly(_assembly_report(), _ten_module_manifest())
    ln = {l.line_id: l for l in
          build_bom(bundle.costing, d_ok, "basalt_slab", basalt).lines
          }["install_transport"]
    print(f"  real card: {ln.status} on {ln.rate_path}")
    _check(failures, "null capacities stay MISSING_RATE (his to supply)",
           ln.status == MISSING_RATE
           and ln.rate_path == "install.truck_payload_kg")
    # 7d. an unsegmented design stays NOT_COMPUTABLE (ours to build)
    d_mono = drivers_for_assembly(_assembly_report(),
                                  {"schema": "assembly_manifest_v1"})
    ln = {l.line_id: l for l in
          build_bom(card, d_mono, "basalt_slab", basalt).lines
          }["install_transport"]
    _check(failures, "no segmentation record -> NOT_COMPUTABLE, unchanged",
           ln.status == NOT_COMPUTABLE)
    # 7e. an INCOMPLETE mass never reaches allocation (FF-A1, ADR-065)
    try:
        drivers_for_assembly(_assembly_report(total_mass_kg=None),
                             _ten_module_manifest())
        _check(failures, "incomplete mass raises before allocation", False,
               "drivers_for_assembly returned")
    except IncompleteMassError as exc:
        _check(failures, "incomplete mass raises before allocation", True,
               str(exc)[:80])
    # 7f. malformed module records are rejected loudly
    for label, mods, payload, per in (
            ("duplicate id", [("m1", 100.0), ("m1", 200.0)], 1000.0, 4),
            ("negative mass", [("m1", -5.0)], 1000.0, 4),
            ("non-finite mass", [("m1", float("nan"))], 1000.0, 4),
            ("fractional bed count", [("m1", 100.0)], 1000.0, 2.5),
            ("zero payload", [("m1", 100.0)], 0.0, 4)):
        try:
            allocate_trips(mods, payload, per)
            _check(failures, f"{label} rejected", False, "was accepted")
        except AllocationInputError:
            _check(failures, f"{label} rejected", True)

    # ------------------------------------------------------------------
    _section(8, "THE DOCUMENT — the trips table on the rendered BOM")
    has_table = ("trip 1:" in doc and "trip 3:" in doc and "p1#0" in doc
                 and "spare" in doc
                 and "deterministic conservative feasible allocation" in doc)
    for row in doc.splitlines():
        if "trip " in row or "loading" in row or "spare" in row:
            print(f"  |{row}")
    _check(failures, "the document prints every trip with its capacity",
           has_table)

    # ------------------------------------------------------------------
    _section(9, "HERMETICITY — nothing real was touched")
    yaml_sha_after = _sha(yaml_path)
    print(f"  config/costing.yaml sha256 (after) : {yaml_sha_after}")
    _check(failures, "config/costing.yaml is byte-identical",
           yaml_sha_after == yaml_sha_before)
    print("  no database opened, no network, no AI call, $0 — every "
          "transport number above is an in-memory TEST value")

    # ------------------------------------------------------------------
    print()
    _hline()
    if failures:
        print(f"FAIL — {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — all checks in every section passed at $0, offline, with "
          "no AI call, no database and the real rate card untouched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
