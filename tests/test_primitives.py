"""Phase 6 slice A1 — the three new primitives + the signed envelope values.

Validation tests run without the geometry kernel; build tests construct real
solids and prove watertightness through the REAL validate_mesh path (ADR-029
method note: never judge watertightness from a raw GLB load).
"""

from __future__ import annotations

import math

import pytest

from app.core.config import load_config_bundle
from app.geometry.primitives import PRIMITIVES, basin_round, plinth, sculptural_column
from app.geometry.primitives.base import ConstraintViolation


def _materials():
    return load_config_bundle().materials.materials


# ---------------------------------------------------------------------------
# The registry dict
# ---------------------------------------------------------------------------

def test_registry_carries_the_slice_a_primitives():
    assert set(PRIMITIVES) == {
        "tiered_cascade", "basin_round", "plinth", "sculptural_column",
    }
    for pid, module in PRIMITIVES.items():
        assert module.PRIMITIVE_ID == pid
        for attr in ("PURPOSE", "CAN_PARENT_STACK", "CAN_PARENT_INSERT",
                     "validate", "build", "anchors", "height_mm",
                     "max_outer_diameter_mm", "inner_diameter_mm"):
            assert hasattr(module, attr), f"{pid} lacks {attr}"


# ---------------------------------------------------------------------------
# Signed envelope sheet Part 2 — the material values (ADR-032)
# ---------------------------------------------------------------------------

def test_joint_overlap_floors_match_signed_sheet():
    mats = _materials()
    assert mats["basalt_slab"].joint_overlap_mm == 10
    assert mats["cast_concrete_c35_45"].joint_overlap_mm == 15
    assert mats["bronze_cast"].joint_overlap_mm == 5
    assert mats["stainless_316l_sheet"].joint_overlap_mm == 3


def test_feature_and_radius_floors_match_signed_sheet():
    mats = _materials()
    assert mats["basalt_slab"].min_feature_mm == 15
    assert mats["cast_concrete_c35_45"].min_feature_mm == 25
    assert mats["bronze_cast"].min_feature_mm == 2
    assert mats["basalt_slab"].min_internal_radius_mm == 10
    assert mats["cast_concrete_c35_45"].min_internal_radius_mm == 10
    assert mats["bronze_cast"].min_internal_radius_mm == 3
    # 316L: both floors are FORMULAS — the wall thickness itself.
    s = mats["stainless_316l_sheet"]
    assert s.min_feature_mm == "wall"
    assert s.min_internal_radius_mm == "wall"
    assert s.min_feature_floor_mm(5.0) == 5.0
    assert s.min_internal_radius_floor_mm(8.0) == 8.0
    # constants pass through the same accessors
    assert mats["basalt_slab"].min_feature_floor_mm(100.0) == 15.0


# ---------------------------------------------------------------------------
# basin_round validation
# ---------------------------------------------------------------------------

def test_basin_round_defaults_validate_and_floor_follows_wall():
    p = basin_round.validate({})
    assert p.floor_mm == p.wall_mm == 20
    assert basin_round.anchors(p)["seat"] == 20
    assert basin_round.inner_diameter_mm(p) == 2600 - 40


def test_basin_round_floor_thinner_than_wall_refused():
    with pytest.raises(ConstraintViolation) as exc:
        basin_round.validate({"wall_mm": 30, "floor_mm": 20})
    assert "floor_mm=20 < wall_mm=30" in str(exc.value)


def test_basin_round_wall_envelope_enforced():
    with pytest.raises(ConstraintViolation) as exc:
        basin_round.validate({"wall_mm": 10, "material_id": "basalt_slab"})
    assert "material minimum 20" in str(exc.value)


def test_basin_round_clearance_floor_enforced():
    with pytest.raises(ConstraintViolation) as exc:
        basin_round.validate({"min_clearance_mm": 30, "material_id": "basalt_slab"})
    assert "material minimum 40" in str(exc.value)


def test_basin_round_floor_filling_basin_refused():
    with pytest.raises(ConstraintViolation) as exc:
        basin_round.validate({"height_mm": 200, "floor_mm": 200, "wall_mm": 20})
    assert "the floor would fill the basin" in str(exc.value)


# ---------------------------------------------------------------------------
# plinth validation
# ---------------------------------------------------------------------------

def test_plinth_solid_default_validates():
    p = plinth.validate({})
    assert p.wall_mm == 0 and p.taper_deg == 0
    assert plinth.base_diameter_mm(p) == p.top_diameter_mm


def test_plinth_taper_widens_base():
    p = plinth.validate({"top_diameter_mm": 900, "height_mm": 1000, "taper_deg": 10})
    expected = 900 + 2 * 1000 * math.tan(math.radians(10))
    assert plinth.base_diameter_mm(p) == pytest.approx(expected)
    assert plinth.max_outer_diameter_mm(p) == pytest.approx(expected)


def test_plinth_wall_zero_or_envelope():
    with pytest.raises(ConstraintViolation) as exc:
        plinth.validate({"wall_mm": 1.5})
    assert "0 (solid) or >= 3 mm" in str(exc.value)
    with pytest.raises(ConstraintViolation) as exc:
        plinth.validate({"wall_mm": 10, "material_id": "basalt_slab"})
    assert "material minimum 20" in str(exc.value)


def test_plinth_hollow_needs_interior():
    with pytest.raises(ConstraintViolation) as exc:
        plinth.validate({"top_diameter_mm": 300, "wall_mm": 150,
                         "material_id": "cast_concrete_c35_45"})
    assert "leaves no interior at the top" in str(exc.value)


# ---------------------------------------------------------------------------
# sculptural_column validation
# ---------------------------------------------------------------------------

def test_column_wall_and_bore_mutually_exclusive():
    with pytest.raises(ConstraintViolation) as exc:
        sculptural_column.validate({"wall_mm": 20, "bore_mm": 50})
    assert "mutually exclusive" in str(exc.value)


def test_column_taper_consuming_section_refused():
    # base 80 mm, 6 m tall, 15°: the taper eats the whole section long
    # before the top.
    with pytest.raises(ConstraintViolation) as exc:
        sculptural_column.validate({"diameter_mm": 80, "height_mm": 6000,
                                    "taper_deg": 15})
    assert "consumes the whole section" in str(exc.value)


def test_column_bore_keeps_material_wall_at_the_top():
    # 200 mm base, 2° taper over 1200: top = 200 - 2*1200*tan(2°) ≈ 116.2;
    # a 90 mm bore leaves ~13.1 mm < basalt's 20 mm minimum.
    with pytest.raises(ConstraintViolation) as exc:
        sculptural_column.validate({"diameter_mm": 200, "height_mm": 1200,
                                    "taper_deg": 2, "bore_mm": 90,
                                    "material_id": "basalt_slab"})
    assert "full wall around the plumbing bore" in str(exc.value)


def test_column_bore_range_inherited():
    with pytest.raises(ConstraintViolation) as exc:
        sculptural_column.validate({"bore_mm": 10, "material_id": "bronze_cast"})
    assert "25..150" in str(exc.value)


# ---------------------------------------------------------------------------
# Builds — real solids through the real validator
# ---------------------------------------------------------------------------

def _build_and_validate(module, raw: dict, tmp_path, name: str):
    from app.geometry.exporters import export_glb
    from app.geometry.validate import validate_mesh

    params = module.validate(raw)
    solid = module.build(params)
    out = tmp_path / f"{name}.glb"
    export_glb(solid, out)
    material = _materials()[params.material_id]
    return validate_mesh(out, material, params.material_id,
                         reference_volume_mm3=float(solid.volume))


@pytest.mark.parametrize("raw", [
    {"diameter_mm": 800, "height_mm": 300, "wall_mm": 25,
     "material_id": "basalt_slab"},
    {"diameter_mm": 800, "height_mm": 300, "wall_mm": 25, "floor_mm": 80,
     "material_id": "basalt_slab"},
])
def test_basin_round_builds_watertight(raw, tmp_path):
    report = _build_and_validate(basin_round, raw, tmp_path, "basin")
    assert report.watertight and report.body_count == 1 and report.passed


@pytest.mark.parametrize("raw", [
    {"top_diameter_mm": 500, "height_mm": 400, "material_id": "basalt_slab"},
    {"top_diameter_mm": 500, "height_mm": 400, "taper_deg": 10,
     "material_id": "basalt_slab"},
    {"top_diameter_mm": 500, "height_mm": 400, "wall_mm": 100,
     "taper_deg": 5, "material_id": "cast_concrete_c35_45"},
])
def test_plinth_builds_watertight(raw, tmp_path):
    report = _build_and_validate(plinth, raw, tmp_path, "plinth")
    assert report.watertight and report.body_count == 1 and report.passed


@pytest.mark.parametrize("raw", [
    {"diameter_mm": 200, "height_mm": 600, "material_id": "basalt_slab"},
    {"diameter_mm": 300, "height_mm": 800, "bore_mm": 60, "taper_deg": 3,
     "material_id": "basalt_slab"},
    {"diameter_mm": 300, "height_mm": 800, "wall_mm": 10,
     "material_id": "bronze_cast"},
])
def test_column_builds_watertight(raw, tmp_path):
    report = _build_and_validate(sculptural_column, raw, tmp_path, "column")
    assert report.watertight and report.body_count == 1 and report.passed


def test_plinth_hollowing_is_the_mass_lever_worked_example(tmp_path):
    """Signed sheet §4.2 arithmetic, proven on real geometry: 1.0 m dia x
    1.0 m basalt plinth — 2,121 kg solid, 1,252 kg at a 180 mm wall."""
    solid_p = plinth.validate({"top_diameter_mm": 1000, "height_mm": 1000,
                               "material_id": "basalt_slab"})
    hollow_p = plinth.validate({"top_diameter_mm": 1000, "height_mm": 1000,
                                "wall_mm": 180, "material_id": "basalt_slab"})
    v_solid = float(plinth.build(solid_p).volume)
    v_hollow = float(plinth.build(hollow_p).volume)
    rho = _materials()["basalt_slab"].density_kg_per_m3
    assert v_solid * 1e-9 * rho == pytest.approx(2121, abs=2)
    assert v_hollow * 1e-9 * rho == pytest.approx(1252, abs=2)
