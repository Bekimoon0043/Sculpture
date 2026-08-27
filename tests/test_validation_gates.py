"""Phase 8 layered validation gates.

These prove the four properties the Phase 8 rewrite exists for:

1. `needs_input` is a distinct status — a check that could not run is never
   reported as a pass or as a warning.
2. The structural gate DISCRIMINATES. The old centre-of-mass check weighted
   placement origins, so it computed 0.0 for every design ever built and
   could not fail. These tests move mass and watch the verdict change.
3. Every limit carries a `basis`. A threshold with no provenance is a Rule 11
   violation, so an empty basis fails the suite.
4. No non-finite value reaches JSON.
"""

from __future__ import annotations

import json
import math

import pytest
import yaml

from app.core.config import CONFIG_DIR, GateProfilesConfig
from app.geometry.gates import (
    FABRICATION_GATE,
    HYDRAULICS_GATE,
    STRUCTURE_GATE,
    WaterContext,
    validate_fabrication_gate,
    validate_hydraulic_gate,
    validate_layered_gates,
    validate_structural_gate,
    worst_status,
)


def _profiles() -> GateProfilesConfig:
    data = yaml.safe_load((CONFIG_DIR / "gate_profiles.yaml").read_text(encoding="utf-8"))
    return GateProfilesConfig.model_validate(data)


@pytest.fixture()
def profiles() -> GateProfilesConfig:
    return _profiles()


@pytest.fixture()
def unsigned(profiles):
    """The shipped public_plaza profile: real values, not signed off."""
    return profiles.profile("public_plaza")


@pytest.fixture()
def signed(profiles):
    """A fully specified, signed-off profile.

    The shipped profiles deliberately leave site and policy thresholds unset,
    because inventing a design wind speed or an allowable bearing pressure
    would be exactly the fabrication Rule 2 forbids. Tests supply their own
    so the fail paths are exercised.
    """
    profile = profiles.profile("public_plaza").model_copy(update={
        "signed_off": True,
        "design_wind_speed_m_s": 30.0,
        "overturning_safety_factor": 1.5,
        "allowable_bearing_kpa": 150.0,
    })
    return profile


def _manifest(**overrides) -> dict:
    manifest = {
        "schema": "assembly_manifest_v1",
        "body_count_brep": 1,
        "total_mass_kg": 125.0,
        "fabrication_limits": {"max_lift_kg": 300, "max_module_m": 2.0},
        "fabrication_limit_violations": [],
        "joints": [{"child": "basin_01", "parent": "plinth_01", "type": "stack_on"}],
        "assembly_bbox_min_mm": [-500, -500, 0],
        "assembly_bbox_max_mm": [500, 500, 440],
        "elements": [
            {
                "element_id": "plinth_01",
                "primitive": "plinth",
                "material_id": "basalt_slab",
                "parameters": {"top_diameter_mm": 1000, "height_mm": 200, "wall_mm": 80},
                "placement_mm": {"x": 0, "y": 0, "z": 0},
                "bbox_mm": [1000, 1000, 200],
                "bbox_min_mm": [-500, -500, 0],
                "bbox_max_mm": [500, 500, 200],
                "centroid_mm": {"x": 0, "y": 0, "z": 100},
                "mass_kg": 80,
            },
            {
                "element_id": "basin_01",
                "primitive": "basin_round",
                "material_id": "basalt_slab",
                "parameters": {
                    "diameter_mm": 800, "height_mm": 250,
                    "wall_mm": 40, "floor_mm": 60,
                },
                "placement_mm": {"x": 0, "y": 0, "z": 190},
                "bbox_mm": [800, 800, 250],
                "bbox_min_mm": [-400, -400, 190],
                "bbox_max_mm": [400, 400, 440],
                "centroid_mm": {"x": 0, "y": 0, "z": 260},
                "mass_kg": 45,
            },
        ],
    }
    manifest.update(overrides)
    return manifest


def _kwargs(profile, profiles, profile_id="public_plaza"):
    return {
        "profile": profile,
        "profile_id": profile_id,
        "version": profiles.version,
    }


# ---------------------------------------------------------------------------
# Contract properties that hold for EVERY gate
# ---------------------------------------------------------------------------

def test_every_check_records_the_provenance_of_its_limit(unsigned, profiles):
    """Rule 11: a threshold with no recorded basis is a defect, not a style nit."""
    reports = [
        validate_structural_gate(
            _manifest(), constants=profiles.constants, **_kwargs(unsigned, profiles)
        ),
        validate_hydraulic_gate(
            _manifest(), water=WaterContext(has_water=True, flow_l_per_min=60),
            constants=profiles.constants, **_kwargs(unsigned, profiles)
        ),
        validate_fabrication_gate(_manifest(), **_kwargs(unsigned, profiles)),
    ]
    for report in reports:
        assert report.checks, f"{report.gate_name} produced no checks at all"
        for check in report.checks:
            assert check.basis.strip(), (
                f"{report.gate_name}.{check.check} has no basis — where did its "
                f"limit come from?"
            )


def test_reports_never_serialize_a_non_finite_number(unsigned, profiles):
    """json.dumps emits bare `Infinity`, which is not valid JSON."""
    broken = _manifest(total_mass_kg=0.0)
    broken["elements"] = [
        {**e, "mass_kg": 0.0} for e in broken["elements"]
    ]
    reports = validate_layered_gates(broken)
    blob = json.dumps(
        {name: r.model_dump_wire() for name, r in reports.items()},
        allow_nan=False,  # raises on inf/nan rather than emitting them
    )
    assert "Infinity" not in blob and "NaN" not in blob


def test_status_rollup_orders_fail_above_needs_input_above_warn():
    assert worst_status(["pass", "warn"]) == "warn"
    assert worst_status(["warn", "needs_input"]) == "needs_input"
    assert worst_status(["needs_input", "fail"]) == "fail"
    assert worst_status(["pass", "pass"]) == "pass"


# ---------------------------------------------------------------------------
# Structural gate
# ---------------------------------------------------------------------------

def test_structural_gate_passes_a_stable_assembly(signed, profiles):
    report = validate_structural_gate(
        _manifest(), constants=profiles.constants, **_kwargs(signed, profiles)
    )
    assert report.gate_name == STRUCTURE_GATE
    assert report.status == "pass"
    rows = {r["check"]: r for r in report.check_rows()}
    assert rows["total_mass_kg"]["value"] == 125.0
    # The centre of mass is on the axis, so the lever is the full half-width.
    assert rows["center_of_mass_lever_mm"]["value"] == pytest.approx(500.0)
    assert rows["ground_bearing_pressure_kpa"]["status"] == "pass"
    assert rows["overturning_safety_factor"]["status"] == "pass"


def test_overturning_check_actually_discriminates(signed, profiles):
    """A tall, light, top-heavy piece must fail where a squat one passes.

    This is the test the old gate could not have: it weighted placement
    origins, which were 0,0 for every element the system produced, so the
    stability check computed exactly 0.0 forever.
    """
    squat = validate_structural_gate(
        _manifest(), constants=profiles.constants, **_kwargs(signed, profiles)
    )
    assert squat.status == "pass"

    # Same mass, same footprint — but 6 m tall instead of 0.44 m.
    tall = _manifest(assembly_bbox_max_mm=[500, 500, 6000])
    tall["elements"][1]["centroid_mm"] = {"x": 0, "y": 0, "z": 4000}
    tall["elements"][1]["bbox_max_mm"] = [400, 400, 6000]
    report = validate_structural_gate(
        tall, constants=profiles.constants, **_kwargs(signed, profiles)
    )
    row = next(r for r in report.check_rows() if r["check"] == "overturning_safety_factor")
    assert row["status"] == "fail", "a 6 m mast on a 1 m base must not pass"
    assert row["value"] < 1.5
    assert report.status == "fail"


def test_center_of_mass_outside_the_footprint_fails(signed, profiles):
    """Move the mass off the base and the lever must go negative."""
    leaning = _manifest()
    leaning["elements"][1]["centroid_mm"] = {"x": 900, "y": 0, "z": 260}
    leaning["elements"][1]["mass_kg"] = 400  # heavier than the base
    leaning["total_mass_kg"] = 480
    report = validate_structural_gate(
        leaning, constants=profiles.constants, **_kwargs(signed, profiles)
    )
    row = next(r for r in report.check_rows() if r["check"] == "center_of_mass_lever_mm")
    assert row["value"] < 0
    assert row["status"] == "fail"


def test_wind_pressure_uses_site_altitude_not_sea_level(signed, profiles):
    """Addis Ababa is at ~2355 m; sea-level density would overstate the load."""
    report = validate_structural_gate(
        _manifest(), constants=profiles.constants, **_kwargs(signed, profiles)
    )
    row = next(r for r in report.check_rows() if r["check"] == "design_wind_pressure_pa")
    rho = profiles.constants.air_density_at_m(signed.site_altitude_m)
    assert rho < profiles.constants.air_density_sea_level_kg_per_m3
    # The reported pressure is rounded to 2 dp.
    assert row["value"] == pytest.approx(0.5 * rho * 30.0**2, abs=0.01)
    assert "ISA" in row["basis"]


def test_unsupplied_thresholds_report_needs_input_not_warn(unsigned, profiles):
    """The shipped profile leaves wind and bearing unset on purpose."""
    report = validate_structural_gate(
        _manifest(), constants=profiles.constants, **_kwargs(unsigned, profiles)
    )
    rows = {r["check"]: r for r in report.check_rows()}
    assert rows["overturning_safety_factor"]["status"] == "needs_input"
    assert rows["ground_bearing_pressure_kpa"]["status"] == "needs_input"
    # The row must name the field to supply, not just shrug.
    assert "design_wind_speed_m_s" in rows["overturning_safety_factor"]["message"]
    assert report.status == "needs_input"
    assert report.passed is False


def test_unsigned_profile_downgrades_a_failure_to_a_warning(unsigned, profiles):
    """Nothing is blocked on a threshold nobody has approved."""
    profile = unsigned.model_copy(update={
        "design_wind_speed_m_s": 30.0,
        "overturning_safety_factor": 1.5,
        "signed_off": False,
    })
    tall = _manifest(assembly_bbox_max_mm=[500, 500, 6000])
    tall["elements"][1]["centroid_mm"] = {"x": 0, "y": 0, "z": 4000}
    report = validate_structural_gate(
        tall, constants=profiles.constants, **_kwargs(profile, profiles)
    )
    row = next(r for r in report.check_rows() if r["check"] == "overturning_safety_factor")
    assert row["status"] == "warn"
    assert "not signed off" in row["message"]


# ---------------------------------------------------------------------------
# Hydraulic gate
# ---------------------------------------------------------------------------

def test_hydraulic_gate_needs_input_when_water_is_unstated(unsigned, profiles):
    report = validate_hydraulic_gate(
        _manifest(), constants=profiles.constants, **_kwargs(unsigned, profiles)
    )
    assert report.gate_name == HYDRAULICS_GATE
    assert report.status == "needs_input"
    assert report.passed is False
    check = report.checks[0]
    assert check.check == "water_designed"
    assert "has_water" in check.message


def test_hydraulic_gate_passes_a_dry_design(unsigned, profiles):
    report = validate_hydraulic_gate(
        _manifest(), water=WaterContext(has_water=False),
        constants=profiles.constants, **_kwargs(unsigned, profiles)
    )
    assert report.status == "pass"


def test_nozzle_bore_is_derived_from_flow_not_a_magic_range(signed, profiles):
    """d = sqrt(4Q / (pi*v)) — the old gate hardcoded 3..150 mm."""
    flow_l_per_min = 120.0
    water = WaterContext(
        has_water=True, flow_l_per_min=flow_l_per_min,
        operating_depth_mm=100, nozzle_bore_mm=20.0,
    )
    report = validate_hydraulic_gate(
        _manifest(), water=water, constants=profiles.constants,
        **_kwargs(signed, profiles)
    )
    row = next(r for r in report.check_rows() if r["check"] == "nozzle_bore_mm")
    q = flow_l_per_min / 60_000.0
    expected = math.sqrt(4 * q / (math.pi * signed.jet_velocity_m_s)) * 1000.0
    low, high = row["limit"]
    # The gate rounds the reported band to 2 dp for readability.
    assert low == pytest.approx(expected * 0.75, abs=0.01)
    assert high == pytest.approx(expected * 1.25, abs=0.01)
    assert row["status"] == "pass"
    assert "sqrt(4Q/(pi*v))" in row["basis"]


def test_nozzle_bore_far_from_the_derived_value_fails(signed, profiles):
    water = WaterContext(
        has_water=True, flow_l_per_min=120.0,
        operating_depth_mm=100, nozzle_bore_mm=140.0,
    )
    report = validate_hydraulic_gate(
        _manifest(), water=water, constants=profiles.constants,
        **_kwargs(signed, profiles)
    )
    row = next(r for r in report.check_rows() if r["check"] == "nozzle_bore_mm")
    assert row["status"] == "fail"
    assert report.status == "fail"


def test_freeboard_fails_when_the_water_is_too_close_to_the_rim(signed, profiles):
    # basin usable depth is height 250 - floor 60 = 190 mm.
    water = WaterContext(has_water=True, flow_l_per_min=10.0, operating_depth_mm=185)
    report = validate_hydraulic_gate(
        _manifest(), water=water, constants=profiles.constants,
        **_kwargs(signed, profiles)
    )
    row = next(r for r in report.check_rows() if r["check"] == "basin_01.freeboard_mm")
    assert row["value"] == pytest.approx(5.0)
    assert row["status"] == "fail"


def test_turnover_uses_real_capacity(signed, profiles):
    water = WaterContext(has_water=True, flow_l_per_min=1000.0, operating_depth_mm=100)
    report = validate_hydraulic_gate(
        _manifest(), water=water, constants=profiles.constants,
        **_kwargs(signed, profiles)
    )
    row = next(r for r in report.check_rows() if r["check"] == "reservoir_turnover_min")
    # A 1000 L/min pump empties this small basin far faster than the minimum.
    assert row["value"] < signed.min_reservoir_turnover_min
    assert row["status"] == "fail"


# ---------------------------------------------------------------------------
# Fabrication gate
# ---------------------------------------------------------------------------

def test_fabrication_gate_flags_an_overweight_element(unsigned, profiles):
    heavy = _manifest()
    heavy["elements"][1]["mass_kg"] = 900  # limit is 300
    report = validate_fabrication_gate(heavy, **_kwargs(unsigned, profiles))
    row = next(r for r in report.check_rows() if r["check"] == "basin_01.mass_kg")
    assert row["value"] == 900
    assert row["limit"] == 300.0
    assert row["status"] == "fail"
    assert report.status == "fail"


def test_an_oversized_element_in_a_pre_segmentation_manifest_asks_for_a_rebuild(
        unsigned, profiles):
    """A manifest written before slice C2 has no segmentation block.

    The gate must not answer "3 modules" from ceil(5000/2000) — that is
    exactly the predicted number segmentation replaced with a measured
    one, and a hollow shape makes it wrong. It asks for the rebuild.
    """
    big = _manifest()
    big["elements"][1]["bbox_mm"] = [5000, 800, 250]  # limit is 2.0 m
    assert "segmentation" not in big
    report = validate_fabrication_gate(big, **_kwargs(unsigned, profiles))
    rows = {r["check"]: r for r in report.check_rows()}
    assert rows["basin_01.module_bbox_mm"]["status"] == "fail"
    split = rows["basin_01.module_split_count"]
    assert split["status"] == "needs_input"
    assert "rebuild" in split["message"]
    assert report.status == "fail"


def test_a_segmented_element_reports_its_measured_modules(unsigned, profiles):
    """With a segmentation block the gate reports what was measured, and
    the lift row prices the heaviest MODULE, not the whole element."""
    big = _manifest()
    big["elements"][1]["bbox_mm"] = [5000, 5000, 700]   # limit is 2.0 m
    big["elements"][1]["mass_kg"] = 11346.1
    big["segmentation"] = {
        "schema": "assembly_segmentation_v1",
        "elements": {"basin_01": {
            "mode": "planar_grid",
            "grid": {"x": 3, "y": 3, "z": 1},
            "predicted_cells": 9,
            "module_count": 9,
            "seam_length_mm": 8420.0,
            "modules": [
                {"index": i, "mass_kg": 1472.2, "volume_mm3": 545255768.7,
                 "bbox_mm": [1666.67, 1666.67, 700.0],
                 "bbox_min_mm": [0.0, 0.0, 0.0]}
                for i in range(9)
            ],
        }},
    }
    report = validate_fabrication_gate(big, **_kwargs(unsigned, profiles))
    rows = {r["check"]: r for r in report.check_rows()}
    assert rows["basin_01.module_bbox_mm"]["status"] == "pass"
    assert rows["basin_01.module_bbox_mm"]["value"] == pytest.approx(1666.67)
    split = rows["basin_01.module_split_count"]
    assert split["status"] == "pass"
    assert split["value"] == 9
    assert "8.42 m of seam" in split["message"]
    # the crane picks 1,472 kg, not 11,346 kg
    assert rows["basin_01.mass_kg"]["value"] == pytest.approx(1472.2)


def test_bore_aspect_ratio_is_measured(unsigned, profiles):
    deep = _manifest()
    deep["elements"][1]["parameters"] = {"bore_mm": 50, "height_mm": 900, "wall_mm": 40}
    report = validate_fabrication_gate(deep, **_kwargs(unsigned, profiles))
    row = next(r for r in report.check_rows() if r["check"] == "basin_01.bore_aspect_ratio")
    assert row["value"] == pytest.approx(18.0)
    # public_plaza is unsigned, so a profile-threshold breach warns.
    assert row["status"] == "warn"


def test_rigging_is_one_check_not_one_per_element(unsigned, profiles):
    report = validate_fabrication_gate(_manifest(), **_kwargs(unsigned, profiles))
    rigging = [r for r in report.check_rows() if r["check"] == "rigging_declared"]
    assert len(rigging) == 1
    # Only elements ABOVE the 50 kg manual handling limit are named: the
    # plinth is 80 kg, the basin is 45 kg and can be placed by hand.
    assert "plinth_01" in rigging[0]["message"]
    assert "basin_01" not in rigging[0]["message"]
    assert rigging[0]["status"] == "needs_input"


def test_light_assembly_needs_no_rigging(unsigned, profiles):
    light = _manifest()
    for element in light["elements"]:
        element["mass_kg"] = 5
    report = validate_fabrication_gate(light, **_kwargs(unsigned, profiles))
    row = next(r for r in report.check_rows() if r["check"] == "rigging_declared")
    assert row["status"] == "pass"


def test_wall_below_the_material_floor_fails_regardless_of_profile(unsigned, profiles):
    thin = _manifest()
    thin["elements"][1]["parameters"]["wall_mm"] = 1.0
    report = validate_fabrication_gate(thin, **_kwargs(unsigned, profiles))
    row = next(r for r in report.check_rows() if r["check"] == "basin_01.wall_mm")
    # A material envelope is signed when it is entered — never downgraded.
    assert row["status"] == "fail"
    assert "materials.yaml" in row["basis"]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def test_validate_layered_gates_returns_all_three_gates():
    reports = validate_layered_gates(_manifest())
    assert set(reports) == {STRUCTURE_GATE, HYDRAULICS_GATE, FABRICATION_GATE}
    for report in reports.values():
        assert report.gate_profile_id == "public_plaza"
        assert report.gate_profiles_version >= 1


def test_unknown_gate_profile_is_a_loud_error():
    from app.core.config import ConfigError

    with pytest.raises(ConfigError, match="unknown gate profile"):
        validate_layered_gates(_manifest(), gate_profile_id="atlantis")


def test_wire_format_keeps_the_schema_key():
    """The pydantic field is `schema_id` (it shadowed BaseModel.schema), but
    the JSON a consumer sees must still say `schema`."""
    report = validate_layered_gates(_manifest())[STRUCTURE_GATE]
    wire = report.model_dump_wire()
    assert wire["schema"] == "layered_validation_report_v2"
    assert "schema_id" not in wire
