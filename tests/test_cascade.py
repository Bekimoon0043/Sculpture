"""Tests for the cascade parameter registry + geometry construction.

Constraint tests need only pydantic + the real materials.yaml — they run
everywhere. Build/watertight tests need build123d + trimesh (importorskip:
on any machine with the pinned deps installed they run for real).
"""

from __future__ import annotations

import re

import pytest

from app.geometry.registry import (
    CASCADE_PARAMETERS,
    ConstraintViolation,
    validate_params,
)


def _build123d():
    return pytest.importorskip("build123d", reason="build123d not installed")


def _trimesh():
    return pytest.importorskip("trimesh", reason="trimesh not installed")


# ---------------------------------------------------------------------------
# Registry shape (PHASE2_PLAN §3 table + min_clearance_mm)
# ---------------------------------------------------------------------------

def test_registry_has_exactly_the_plan_parameters():
    expected = {
        "tiers", "tier_top_diameter_mm", "tier_diameter_step_mm",
        "dish_depth_mm", "tier_spacing_mm", "lip_fillet_mm",
        "column_diameter_mm", "basin_diameter_mm", "basin_height_mm",
        "basin_wall_mm", "bore_diameter_mm", "material_id", "min_clearance_mm",
        # slice A1 (ADR-032): per-member walls — the column's own wall,
        # derived default basin_wall_mm (closes LIMITATIONS §9 first bullet)
        "column_wall_mm",
    }
    assert set(CASCADE_PARAMETERS) == expected
    for name, spec in CASCADE_PARAMETERS.items():
        assert {"unit", "default", "min", "max", "type"} <= set(spec), name


def test_registry_defaults_match_plan_table():
    assert CASCADE_PARAMETERS["tiers"]["default"] == 3
    assert CASCADE_PARAMETERS["tiers"]["min"] == 1
    assert CASCADE_PARAMETERS["tiers"]["max"] == 5
    assert CASCADE_PARAMETERS["tier_top_diameter_mm"]["default"] == 600
    assert CASCADE_PARAMETERS["tier_diameter_step_mm"]["default"] == 400
    assert CASCADE_PARAMETERS["dish_depth_mm"]["default"] == 90
    assert CASCADE_PARAMETERS["tier_spacing_mm"]["default"] == 350
    assert CASCADE_PARAMETERS["lip_fillet_mm"]["default"] == 8
    assert CASCADE_PARAMETERS["column_diameter_mm"]["default"] == 200
    assert CASCADE_PARAMETERS["basin_diameter_mm"]["default"] == 2600
    assert CASCADE_PARAMETERS["basin_height_mm"]["default"] == 450
    assert CASCADE_PARAMETERS["basin_wall_mm"]["default"] == 20
    assert CASCADE_PARAMETERS["bore_diameter_mm"]["default"] == 50
    assert CASCADE_PARAMETERS["material_id"]["default"] == "basalt_slab"
    assert CASCADE_PARAMETERS["min_clearance_mm"]["default"] == 100


# ---------------------------------------------------------------------------
# Parameter math
# ---------------------------------------------------------------------------

def test_widest_dish_and_required_basin_math():
    params = validate_params({})  # defaults: 3 tiers, 600 top, 400 step
    assert params.widest_dish_diameter_mm() == 600 + 2 * 400 == 1400
    assert params.required_basin_diameter_mm() == 1400 + 2 * 20 + 100 == 1540
    five = validate_params({"tiers": 5})
    assert five.widest_dish_diameter_mm() == 600 + 4 * 400 == 2200


def test_defaults_are_valid():
    params = validate_params({})
    assert params.tiers == 3
    assert params.material_id == "basalt_slab"


# ---------------------------------------------------------------------------
# Hard constraints — every error carries the REAL numbers [ADD-4]
# ---------------------------------------------------------------------------

def test_constraint_basin_too_small_lists_real_numbers():
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params({"basin_diameter_mm": 1000})
    (message,) = excinfo.value.violations
    # widest dish 1400 + 2*wall 2x20 + clearance 100 = 1540 required
    assert "basin_diameter_mm=1000" in message
    assert "1540" in message
    assert "1400" in message
    assert "2x20" in message
    assert "100" in message


def test_constraint_wall_below_material_minimum_lists_real_numbers():
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params({"basin_wall_mm": 10, "basin_diameter_mm": 4000})
    messages = excinfo.value.violations
    wall_msgs = [m for m in messages if "basin_wall_mm=10" in m]
    assert wall_msgs, messages
    # basalt_slab min_wall_mm is 20 in materials.yaml
    assert any("material minimum 20" in m for m in wall_msgs)
    assert any("basalt_slab" in m for m in wall_msgs)


def test_constraint_lip_fillet_vs_dish_depth_lists_real_numbers():
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params(
            {"dish_depth_mm": 40, "lip_fillet_mm": 25, "basin_wall_mm": 30}
        )
    messages = excinfo.value.violations
    assert any(
        "lip_fillet_mm=25" in m and "dish_depth_mm/2" in m and "20" in m
        for m in messages
    ), messages


def test_all_violations_are_listed_not_just_the_first():
    # basin too small AND wall too thin AND lip fillet too big
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params(
            {"basin_diameter_mm": 1000, "basin_wall_mm": 5, "lip_fillet_mm": 25}
        )
    violations = excinfo.value.violations
    assert len(violations) >= 3, violations
    for v in violations:
        assert re.search(r"\d", v), f"violation lacks real numbers: {v}"


def test_extra_construction_constraints_have_real_numbers():
    # bore nearly as wide as the column; spacing tighter than dish depth
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params(
            {
                "column_diameter_mm": 80,
                "bore_diameter_mm": 75,   # needs 75 + 2*20 = 115
                "tier_spacing_mm": 150,
                "dish_depth_mm": 300,
                "basin_diameter_mm": 6000,
            }
        )
    violations = excinfo.value.violations
    assert any("column_diameter_mm=80" in v and "115" in v for v in violations)
    assert any("tier_spacing_mm=150" in v and "300" in v for v in violations)


def test_range_violation_names_parameter_and_bound():
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params({"tiers": 9})
    assert any("tiers" in v and "5" in v for v in excinfo.value.violations)


def test_unknown_parameter_is_rejected():
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params({"tier_hieght_mm": 100})  # typo
    assert any("unknown parameter" in v for v in excinfo.value.violations)


def test_unknown_material_is_rejected():
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params({"material_id": "unobtainium"})
    assert any("unobtainium" in v for v in excinfo.value.violations)


def test_concrete_material_forces_thicker_wall():
    # cast_concrete_c35_45 requires min_wall_mm 75
    params = validate_params(
        {
            "material_id": "cast_concrete_c35_45",
            "basin_wall_mm": 80,
            "lip_fillet_mm": 8,
            "column_diameter_mm": 300,  # 50 bore + 2x80 wall = 210 minimum
        }
    )
    assert params.basin_wall_mm == 80
    with pytest.raises(ConstraintViolation):
        validate_params({"material_id": "cast_concrete_c35_45"})  # default wall 20 < 75


def test_material_wall_envelope_ceiling_adr027():
    """ADR-027: per-material max wall (materials.yaml) is enforced with
    real numbers; monumental basalt walls that the live Phase 4 run needed
    are now INSIDE the envelope."""
    # the live-run value that the old demo ceiling (100) rejected
    # (column widened so constraint 4 — bore + 2*wall — stays satisfied)
    params = validate_params(
        {"basin_wall_mm": 180, "lip_fillet_mm": 8, "column_diameter_mm": 450}
    )
    assert params.basin_wall_mm == 180
    # basalt ceiling is 250 — beyond it raises with the real numbers
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params(
            {"basin_wall_mm": 260, "column_diameter_mm": 600}
        )
    msgs = excinfo.value.violations
    assert any(
        "basin_wall_mm=260" in m and "material maximum 250" in m
        and "basalt_slab" in m for m in msgs
    ), msgs
    # 316L sheet caps at 20 — 25 mm plate is not sheet work
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params(
            {"material_id": "stainless_316l_sheet", "basin_wall_mm": 25}
        )
    assert any(
        "material maximum 20" in m and "stainless_316l_sheet" in m
        for m in excinfo.value.violations
    )
    # bronze cast caps at 40
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params({"material_id": "bronze_cast", "basin_wall_mm": 45})
    assert any(
        "material maximum 40" in m for m in excinfo.value.violations
    )


def test_material_clearance_floor_adr029():
    """ADR-029: hard constraint 7 — min_clearance_mm has a per-material
    floor, enforced with real numbers in BOTH the diametral and the radial
    figure. Constraint 1 alone cannot catch this: it is satisfied exactly
    AT tangency."""
    # basalt floor is 40 mm diametral (20 mm radial)
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params({"min_clearance_mm": 30})
    msgs = excinfo.value.violations
    assert any(
        "min_clearance_mm=30" in m and "material minimum 40" in m
        and "basalt_slab" in m and "15 mm radial" in m for m in msgs
    ), msgs
    # concrete is the coarsest: 50 mm diametral
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params({
            "material_id": "cast_concrete_c35_45", "basin_wall_mm": 75,
            "column_diameter_mm": 200, "min_clearance_mm": 40,
        })
    assert any(
        "material minimum 50" in m and "cast_concrete_c35_45" in m
        for m in excinfo.value.violations
    ), excinfo.value.violations
    # at the floor exactly, it passes
    assert validate_params({"min_clearance_mm": 40}).min_clearance_mm == 40


def test_zero_clearance_is_rejected_by_the_range_adr029():
    """The registry floor (20 = smallest material floor) kills clearance 0
    before the per-material constraint even runs — 0 is the value the live
    geometrist chose, and it is now unreachable through any material."""
    with pytest.raises(ConstraintViolation) as excinfo:
        validate_params({"min_clearance_mm": 0})
    assert any("min_clearance_mm" in m for m in excinfo.value.violations)
    assert CASCADE_PARAMETERS["min_clearance_mm"]["min"] == 20


def test_live_gate_failure_parameters_are_now_rejected_adr029():
    """REGRESSION, verbatim from the failed live run of 2026-08-09: these
    exact parameters built a solid that trimesh reported watertight=False,
    because widest dish 2240 + 2x180 wall == basin 2600 exactly. The
    registry must now refuse them BEFORE the sandbox burns an attempt."""
    live = {
        "tiers": 3, "tier_top_diameter_mm": 1120.0,
        "tier_diameter_step_mm": 560.0, "dish_depth_mm": 420.0,
        "tier_spacing_mm": 420.0, "lip_fillet_mm": 8.0,
        "column_diameter_mm": 420.0, "basin_diameter_mm": 2600.0,
        "basin_height_mm": 350.0, "basin_wall_mm": 180.0,
        "bore_diameter_mm": 50.0, "material_id": "basalt_slab",
        "min_clearance_mm": 0.0,
    }
    with pytest.raises(ConstraintViolation):
        validate_params(live)
    # and the fix the geometrist should reach for — shrink the DISHES, keep
    # the brief's 2.6 m basin — validates cleanly
    fixed = dict(live, min_clearance_mm=40.0,
                 tier_top_diameter_mm=1080.0, tier_diameter_step_mm=560.0)
    assert validate_params(fixed).min_clearance_mm == 40.0


def _monumental(**overrides):
    """The live brief's monumental basalt massing, parameterised.

    basin 2.6 m, 180 mm wall, 420 mm dishes — the configuration the Council
    actually produced on 2026-08-09 and the one the tangency defect hid in.
    """
    params = {
        "tiers": 3, "tier_diameter_step_mm": 560.0, "dish_depth_mm": 420.0,
        "tier_spacing_mm": 420.0, "lip_fillet_mm": 8.0,
        "column_diameter_mm": 420.0, "basin_diameter_mm": 2600.0,
        "basin_height_mm": 350.0, "basin_wall_mm": 180.0,
        "bore_diameter_mm": 50.0, "material_id": "basalt_slab",
    }
    params.update(overrides)
    return params


def _watertight_at(tmp_path, name, params):
    """Build + export + measure through the REAL Phase 2 validator.

    Must go through validate_mesh, not a raw trimesh.load: the GLB exporter
    writes one patch per B-rep face with duplicated seam vertices, so a raw
    load reports EVERY build — including the Phase 2 canonical one — as not
    watertight. validate_mesh merge_vertices() first (see its docstring).
    """
    from app.core.config import load_config_bundle
    from app.geometry.primitives.cascade import build_cascade
    from app.geometry.exporters import export_glb
    from app.geometry.validate import validate_mesh

    solid = build_cascade(params)
    out = tmp_path / f"{name}.glb"
    export_glb(solid, out)
    material = load_config_bundle().materials.materials[params.material_id]
    return validate_mesh(out, material, material_id=params.material_id,
                         reference_volume_mm3=solid.volume)


def test_build_at_the_material_clearance_floor_is_watertight_adr029(tmp_path):
    """The floor is only worth having if geometry AT the floor is sound.
    Builds the corrected live massing at basalt's exact floor and proves the
    fused solid meshes watertight — the check that failed live."""
    _build123d()
    _trimesh()
    # widest dish sized to sit exactly at the floor: 2600 - 2*180 - 40
    params = validate_params(_monumental(
        tier_top_diameter_mm=2200.0 - 1120.0, min_clearance_mm=40.0))
    report = _watertight_at(tmp_path, "floor", params)
    assert report.watertight, report.model_dump()
    assert report.passed, report.model_dump()


def test_zero_clearance_really_does_break_the_mesh_adr029(tmp_path):
    """The evidence the floor rests on, re-measured rather than asserted.

    model_construct BYPASSES the new range deliberately: this reproduces the
    exact geometry of the failed live run (2026-08-09, volume 3169987070
    mm3, watertight False) and shows that the smallest positive clearance
    already fixes it. Zero is a knife-edge tangency singularity, not a
    gradual degradation — which is why the FABRICATION floors in
    materials.yaml (20-50 mm) are set by workshop reality and carry an
    enormous margin over the CAD threshold, rather than being tuned to it.
    """
    _build123d()
    _trimesh()
    from app.geometry.registry import CascadeParams

    tangent = CascadeParams.model_construct(
        **_monumental(tier_top_diameter_mm=1120.0, min_clearance_mm=0.0))
    report = _watertight_at(tmp_path, "tangent", tangent)
    assert not report.watertight, (
        "the tangency case must still reproduce as NOT watertight — if this "
        "starts passing, the kernel changed and ADR-029's basis needs review"
    )
    assert round(report.volume_mm3) == 3169987070, report.volume_mm3

    clear = CascadeParams.model_construct(
        **_monumental(tier_top_diameter_mm=1119.5, min_clearance_mm=0.5))
    assert _watertight_at(tmp_path, "clear", clear).watertight


def test_monumental_dish_depth_adr027():
    """ADR-027 widened dish_depth_mm to 600 for monumental stonework;
    hard constraint 6 (spacing >= depth) still binds."""
    params = validate_params({"dish_depth_mm": 420, "tier_spacing_mm": 500})
    assert params.dish_depth_mm == 420
    with pytest.raises(ConstraintViolation):
        validate_params({"dish_depth_mm": 420, "tier_spacing_mm": 300})


def test_registry_surface_states_ranges_and_envelopes():
    """The geometrist prompt must state per-parameter [min..max] AND the
    per-material wall envelopes (live-run issue 4: prove the surface
    carries the bounds, generated from live config)."""
    from app.council.prompts import registry_surface

    surface = registry_surface()
    assert "basin_wall_mm (float, mm, default 20 [3..300])" in surface
    assert "dish_depth_mm (float, mm, default 90 [40..600])" in surface
    assert "MATERIAL ENVELOPES" in surface
    assert (
        "basalt_slab (Basalt slab): basin_wall_mm 20..250 mm | "
        "min_clearance_mm >= 40 mm (20 mm radial)"
    ) in surface
    assert (
        "stainless_316l_sheet (316L stainless steel sheet): "
        "basin_wall_mm 3..20 mm | min_clearance_mm >= 20 mm (10 mm radial)"
    ) in surface


def test_registry_surface_teaches_the_clearance_trap_adr029():
    """ADR-029: the live gate failed because the geometrist drove
    min_clearance_mm to 0 to satisfy constraint 1 against a brief-fixed
    basin diameter. The surface must state the DIAMETRAL convention, name
    the tangency consequence, and give the solving order that avoids it —
    otherwise the same reasoning recurs on every monumental brief."""
    from app.council.prompts import registry_surface

    surface = registry_surface()
    assert "7. min_clearance_mm >= the material's CLEARANCE FLOOR" in surface
    assert "DIAMETRAL" in surface
    assert "HALF" in surface
    # the exact failure mode, named in the prompt
    assert "TOUCHES the basin wall" in surface
    assert "not watertight" in surface
    # and the way out: solve for the dishes, not the clearance
    assert (
        "widest_dish <= basin_diameter_mm - 2*basin_wall_mm - min_clearance_mm"
    ) in surface


# ---------------------------------------------------------------------------
# Geometry construction — watertight at tier extremes (needs build123d+trimesh)
# ---------------------------------------------------------------------------

def _build_and_check_watertight(tmp_path, tiers: int):
    _build123d()
    _trimesh()
    from app.core.config import load_config_bundle
    from app.geometry import GeometryBuild, export_glb, validate_mesh

    params = validate_params({"tiers": tiers})
    build = GeometryBuild(seed=7, params=params)
    solid = build.build()
    assert len(solid.solids()) == 1
    assert solid.is_valid  # property in build123d 0.11.x (verified installed)
    glb = tmp_path / f"cascade_t{tiers}.glb"
    export_glb(solid, glb)
    material = load_config_bundle().materials.materials[params.material_id]
    report = validate_mesh(
        glb, material, material_id=params.material_id,
        reference_volume_mm3=float(solid.volume),
    )
    assert report.watertight, f"tiers={tiers}: exported mesh not watertight"
    assert report.winding_consistent
    assert report.volume_mm3 > 0
    assert report.passed
    return solid, report


def test_build_one_tier_watertight(tmp_path):
    _build_and_check_watertight(tmp_path, 1)


def test_build_five_tiers_watertight(tmp_path):
    solid, report = _build_and_check_watertight(tmp_path, 5)
    # bounds sanity (CAD frame, mm): 5-tier default cascade spans the basin
    xmin, ymin, zmin, xmax, ymax, zmax = report.bounds_mm
    assert abs((xmax - xmin) - 2600) < 2.0  # basin diameter
    assert abs((ymax - ymin) - 2600) < 2.0
    # height: basin 450 + 4*350 spacing + 90 top-dish depth
    assert abs((zmax - zmin) - 1940) < 2.0


def test_bore_actually_pierces_the_stack(tmp_path):
    _build123d()
    from app.geometry import GeometryBuild

    # Same everything, wider bore -> strictly less material (the void grows).
    narrow = GeometryBuild(seed=1, params=validate_params({})).build()
    wide = GeometryBuild(
        seed=1, params=validate_params({"bore_diameter_mm": 150})
    ).build()
    assert wide.volume < narrow.volume
    # and the difference matches the added cylindrical void: the bore passes
    # through 1170 mm of material (basin floor + full column + dish floors).
    import math

    expected = math.pi * ((150 / 2) ** 2 - (50 / 2) ** 2)
    height = 450 + 2 * 350 + 20  # basin + spacings + wall (column top)
    delta = narrow.volume - wide.volume
    assert abs(delta - expected * height) / (expected * height) < 0.01
