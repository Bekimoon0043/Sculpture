#!/usr/bin/env python3
"""Phase 8 auto gate — L5 layered validation. Runs at $0, forever.

Non-interactive, no network, no provider keys. Exit 0 = PASS, 1 = FAIL.

    docker compose exec backend python scripts/gate_phase8_auto.py

What it proves, in the operator's terms:

  1. Four statuses exist and `needs_input` is not a pass.
  2. Every threshold says where it came from (Rule 11).
  3. The structural gate DISCRIMINATES — the old one computed 0.0 forever.
  4. Wind load uses the site's real air density, not sea level.
  5. Hydraulic limits are DERIVED from flow, not hardcoded.
  6. A workshop-limit breach still produces geometry, and fails the gate.
  7. Nothing non-finite ever reaches JSON.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

PASS, FAIL = "PASS", "FAIL"


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/7] {title}")
    _hline()


def _check(failures: list[str], label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{('  — ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def main() -> int:
    from app.core.config import GateProfilesConfig, load_config_bundle
    from app.geometry import assemble
    from app.geometry.gates import (
        FABRICATION_GATE,
        HYDRAULICS_GATE,
        STRUCTURE_GATE,
        WaterContext,
        validate_hydraulic_gate,
        validate_layered_gates,
        validate_structural_gate,
        worst_status,
    )

    failures: list[str] = []
    bundle = load_config_bundle()
    profiles: GateProfilesConfig = bundle.gate_profiles

    elements = [
        {"element_id": "plinth_01", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 2200, "height_mm": 300, "wall_mm": 120}},
        {"element_id": "basin_01", "primitive": "basin_round",
         "parameters": {"diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
                        "floor_mm": 160, "min_clearance_mm": 220},
         "joint": {"type": "stack_on", "parent": "plinth_01"}},
        {"element_id": "column_01", "primitive": "sculptural_column",
         "parameters": {"diameter_mm": 360, "height_mm": 900, "bore_mm": 150},
         "joint": {"type": "concentric_insert", "parent": "basin_01"}},
    ]
    fabrication = {"max_lift_kg": 3000, "max_module_m": 4.0}

    # -----------------------------------------------------------------
    _section(1, "CONFIG — gate_profiles.yaml loads and validates")
    _check(failures, "gate_profiles.yaml version >= 1", profiles.version >= 1,
           f"version {profiles.version}")
    _check(failures, "the default profile exists", "public_plaza" in profiles.profiles,
           f"profiles: {sorted(profiles.profiles)}")
    rho_sea = profiles.constants.air_density_sea_level_kg_per_m3
    plaza = profiles.profile("public_plaza")
    rho_site = profiles.constants.air_density_at_m(plaza.site_altitude_m)
    _check(failures, "site air density is below sea level", rho_site < rho_sea,
           f"{rho_site:.4f} kg/m3 at {plaza.site_altitude_m:g} m vs {rho_sea} at sea level")
    unset = [f for f in ("design_wind_speed_m_s", "overturning_safety_factor",
                         "allowable_bearing_kpa") if getattr(plaza, f) is None]
    print(f"  note  thresholds still awaiting operator sign-off: {unset or 'none'}")

    # -----------------------------------------------------------------
    _section(2, "BUILD — a real three-primitive assembly with real centroids")
    solid, manifest = assemble(elements, seed=7, fabrication=fabrication, strict=False)
    _check(failures, "one fused B-rep body", manifest["body_count_brep"] == 1)
    _check(failures, "every element carries a mass centroid",
           all("centroid_mm" in e for e in manifest["elements"]))
    _check(failures, "every element carries world-space extents",
           all("bbox_min_mm" in e and "bbox_max_mm" in e for e in manifest["elements"]))
    print(f"  note  total mass {manifest['total_mass_kg']:.1f} kg, "
          f"{len(manifest['elements'])} elements")

    # -----------------------------------------------------------------
    _section(3, "PROVENANCE — every limit records where it came from (Rule 11)")
    reports = validate_layered_gates(manifest)
    missing = [
        f"{name}.{c.check}"
        for name, report in reports.items()
        for c in report.checks
        if not c.basis.strip()
    ]
    _check(failures, "no check has an empty basis", not missing, str(missing[:3]))
    total_checks = sum(len(r.checks) for r in reports.values())
    print(f"  note  {total_checks} checks across {len(reports)} gates, all with provenance")

    # -----------------------------------------------------------------
    _section(4, "HONESTY — needs_input is not a pass, and warn is not a pass")
    structure = reports[STRUCTURE_GATE]
    hydraulics = reports[HYDRAULICS_GATE]
    _check(failures, "no water context -> hydraulics needs_input",
           hydraulics.status == "needs_input", f"status {hydraulics.status}")
    _check(failures, "a needs_input gate does not report passed",
           hydraulics.passed is False)
    _check(failures, "unset wind speed -> overturning needs_input",
           any(c.check == "overturning_safety_factor" and c.status == "needs_input"
               for c in structure.checks))
    _check(failures, "rollup puts fail above needs_input above warn",
           worst_status(["pass", "warn", "needs_input"]) == "needs_input"
           and worst_status(["needs_input", "fail"]) == "fail")

    # -----------------------------------------------------------------
    _section(5, "DISCRIMINATION — the structural gate can actually fail")
    signed = plaza.model_copy(update={
        "signed_off": True, "design_wind_speed_m_s": 30.0,
        "overturning_safety_factor": 1.5, "allowable_bearing_kpa": 150.0,
    })
    kwargs = {"profile": signed, "profile_id": "public_plaza",
              "constants": profiles.constants, "version": profiles.version}

    squat = validate_structural_gate(manifest, **kwargs)
    squat_sf = next(c.value for c in squat.checks
                    if c.check == "overturning_safety_factor")

    tall = json.loads(json.dumps(manifest))
    tall["assembly_bbox_max_mm"] = [1100.0, 1100.0, 8000.0]
    tall["elements"][0]["centroid_mm"]["z"] = 5000.0
    tower = validate_structural_gate(tall, **kwargs)
    tall_sf = next(c.value for c in tower.checks
                   if c.check == "overturning_safety_factor")

    _check(failures, "the built fountain passes overturning", squat.status == "pass",
           f"safety factor {squat_sf}")
    _check(failures, "an 8 m mast on the same base FAILS overturning",
           tower.status == "fail", f"safety factor {tall_sf} < 1.5 required")
    _check(failures, "the two cases give different answers", squat_sf != tall_sf,
           "the old gate returned 0.0 for every design ever built")

    bearing = next(c for c in squat.checks if c.check == "ground_bearing_pressure_kpa")
    _check(failures, "ground bearing pressure is measured", bearing.value > 0,
           f"{bearing.value} kPa against {bearing.limit} kPa allowable")

    # -----------------------------------------------------------------
    _section(6, "DERIVATION — hydraulic limits come from arithmetic, not literals")
    flow = 120.0
    water = WaterContext(has_water=True, flow_l_per_min=flow,
                         operating_depth_mm=200, nozzle_bore_mm=20.0)
    hydro = validate_hydraulic_gate(manifest, water=water, **kwargs)
    bore = next(c for c in hydro.checks if c.check == "nozzle_bore_mm")
    q = flow / 60_000.0
    expected = math.sqrt(4 * q / (math.pi * signed.jet_velocity_m_s)) * 1000.0
    _check(failures, "the required bore is derived from flow and jet velocity",
           abs((bore.limit[0] + bore.limit[1]) / 2 - expected) < 0.05,
           f"d = sqrt(4Q/(pi*v)) = {expected:.2f} mm, band {bore.limit}")
    _check(failures, "the basis records the formula", "sqrt(4Q/(pi*v))" in bore.basis)
    capacity = next(c for c in hydro.checks
                    if c.check.endswith("reservoir_capacity_l"))
    _check(failures, "reservoir capacity is computed from the geometry",
           capacity.value > 0, f"{capacity.value} L")

    # -----------------------------------------------------------------
    _section(7, "DIAGNOSTIC BUILD + JSON SAFETY")
    heavy_solid, heavy_manifest = assemble(
        elements, seed=7,
        fabrication={"max_lift_kg": 50, "max_module_m": 4.0}, strict=False,
    )
    _check(failures, "a limit breach still produces geometry",
           heavy_solid is not None and heavy_manifest["body_count_brep"] == 1)
    _check(failures, "the breach is recorded on the manifest",
           bool(heavy_manifest["fabrication_limit_violations"]))
    heavy_reports = validate_layered_gates(heavy_manifest)
    _check(failures, "the fabrication gate FAILS on the breach",
           heavy_reports[FABRICATION_GATE].status == "fail")

    try:
        assemble(elements, seed=7,
                 fabrication={"max_lift_kg": 50, "max_module_m": 4.0}, strict=True)
        _check(failures, "strict mode still refuses the same design", False,
               "no ConstraintViolation was raised")
    except Exception as exc:
        _check(failures, "strict mode still refuses the same design",
               type(exc).__name__ == "ConstraintViolation", type(exc).__name__)

    try:
        json.dumps(
            {n: r.model_dump_wire() for n, r in heavy_reports.items()},
            allow_nan=False,
        )
        _check(failures, "reports serialize as strict JSON (no Infinity/NaN)", True)
    except ValueError as exc:
        _check(failures, "reports serialize as strict JSON (no Infinity/NaN)",
               False, str(exc))

    # -----------------------------------------------------------------
    print()
    _hline()
    print("VERDICT")
    _hline()
    if failures:
        print(f"{FAIL} — Phase 8 auto gate: {len(failures)} check(s) failed:")
        for item in failures:
            print(f"    - {item}")
        return 1
    print(f"{PASS} — Phase 8 auto gate: all sections passed at $0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
