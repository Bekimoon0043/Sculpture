"""Phase 6 slice C1 — extrusion and array masses (ADR-055).

Real geometry throughout, $0, no AI. What this file proves: six new
primitives build ONE watertight solid each; every signed floor binds
(feature, internal radius, joint/tolerance); the torus can no longer sit
on a knife-line; and a 24-blade array fuses deterministically into one
body inside an assembly (the two-process byte-identity lives in the gate).
"""

from __future__ import annotations

import math

import pytest

from app.geometry.primitives.base import ConstraintViolation

pytest.importorskip("build123d")

from app.geometry.assembly import assemble  # noqa: E402
from app.geometry.primitives import (  # noqa: E402
    PRIMITIVES,
    basin_rect,
    blade_fin_array,
    lotus_petal_array,
    stepped_monolith,
    torus_ring,
    water_wall,
)


def test_registry_lists_ten_primitives():
    # FF-A2 (ADR-066, operator-approved conversion): the C1 ten are a
    # SUBSET — the exact-set assertion lives in the newest slice's gate
    # (gate_ffa2_auto asserts the eleven), per the recorded 2026-08-26
    # convention in gate_phase6a1_auto.py.
    assert {
        "tiered_cascade", "basin_round", "plinth", "sculptural_column",
        "basin_rect", "stepped_monolith", "water_wall", "torus_ring",
        "blade_fin_array", "lotus_petal_array",
    } <= set(PRIMITIVES)


def _build(module, params):
    p = module.validate(params, None)
    solid = module.build(p)
    assert len(solid.solids()) == 1, module.PRIMITIVE_ID
    return solid, p


# --- each primitive builds ONE watertight solid ------------------------------


def test_basin_rect_builds_and_volume_is_a_tub():
    solid, p = _build(basin_rect, {
        "length_mm": 2000, "width_mm": 1200, "height_mm": 450,
        "wall_mm": 40, "floor_mm": 60, "corner_radius_mm": 60,
        "material_id": "basalt_slab",
    })
    # A tub holds water: its volume is far below the bounding block's.
    assert float(solid.volume) < 0.5 * (2000 * 1200 * 450)
    assert float(solid.volume) > 0


def test_stepped_monolith_builds_with_shrinking_steps():
    solid, p = _build(stepped_monolith, {
        "base_length_mm": 1200, "base_width_mm": 1200, "steps": 3,
        "step_height_mm": 300, "step_inset_mm": 100,
        "material_id": "basalt_slab",
    })
    bb = solid.bounding_box()
    assert (bb.max.Z - bb.min.Z) == pytest.approx(900, abs=1)


def test_water_wall_builds_with_weir_crest():
    solid, p = _build(water_wall, {
        "length_mm": 2400, "height_mm": 1800, "thickness_mm": 100,
        "material_id": "basalt_slab",
    })
    bb = solid.bounding_box()
    # The drip lip overhangs one face: depth = thickness + drip_edge.
    assert (bb.max.X - bb.min.X) == pytest.approx(
        100 + p.drip_edge_mm, abs=0.5)
    assert (bb.max.Y - bb.min.Y) == pytest.approx(2400, abs=1)


def test_torus_ring_builds():
    solid, p = _build(torus_ring, {
        "major_diameter_mm": 1200, "minor_diameter_mm": 200,
        "material_id": "bronze_cast",
    })
    # Convention (ADR-055): major_diameter_mm is the OUTER diameter, so the
    # centreline radius R = (major − minor)/2. Exact volume V = 2·π²·R·r².
    R = (1200 - 200) / 2
    r = 200 / 2
    assert float(solid.volume) == pytest.approx(
        2 * math.pi**2 * R * r**2, rel=0.01)


def test_blade_fin_array_24_blades_one_body():
    # 316L formula floors: feature floor = blade thickness (30), so the
    # hub gap π·500/24 − 30 = 35.4 mm must clear 30 — it does.
    solid, p = _build(blade_fin_array, {
        "hub_diameter_mm": 500, "hub_height_mm": 600, "blade_count": 24,
        "blade_length_mm": 300, "blade_height_mm": 500,
        "blade_thickness_mm": 30, "material_id": "stainless_316l_sheet",
    })
    bb = solid.bounding_box()
    assert (bb.max.X - bb.min.X) == pytest.approx(500 + 2 * 300, abs=1)


def test_lotus_petal_array_builds_one_body():
    solid, p = _build(lotus_petal_array, {
        "hub_diameter_mm": 500, "hub_height_mm": 200, "petal_count": 8,
        "petal_length_mm": 500, "petal_width_mm": 250,
        "petal_thickness_mm": 30, "tilt_deg": 35,
        "material_id": "bronze_cast",
    })
    assert float(solid.volume) > 0


# --- the signed floors bind on the new shapes --------------------------------


def test_basin_rect_corner_radius_under_internal_floor_refused():
    with pytest.raises(ConstraintViolation) as exc:
        basin_rect.validate({
            "length_mm": 2000, "width_mm": 1200, "wall_mm": 40,
            "corner_radius_mm": 5, "material_id": "basalt_slab",
        }, None)
    text = str(exc.value)
    assert "corner_radius_mm" in text and "10" in text  # basalt radius floor


def test_blade_under_feature_floor_refused():
    with pytest.raises(ConstraintViolation) as exc:
        blade_fin_array.validate({
            "hub_diameter_mm": 400, "blade_count": 12,
            "blade_thickness_mm": 10, "material_id": "basalt_slab",
        }, None)
    text = str(exc.value)
    assert "blade_thickness_mm" in text and "15" in text


def test_petal_tangency_band_refused():
    # Lotus petals may GAP (>= feature floor, tool access) or OVERLAP
    # (>= joint floor, a real fuse) — the near-tangent band between is the
    # ADR-029 knife edge. 6 petals of width 260 on a ⌀500 hub:
    # π·500/6 − 260 = 1.8 mm — inside the band for bronze (2 / 5).
    with pytest.raises(ConstraintViolation) as exc:
        lotus_petal_array.validate({
            "hub_diameter_mm": 500, "petal_count": 6,
            "petal_width_mm": 260, "petal_thickness_mm": 30,
            "material_id": "bronze_cast",
        }, None)
    text = str(exc.value)
    assert "1.8" in text and "tangency" in text


def test_torus_self_intersection_refused():
    with pytest.raises(ConstraintViolation) as exc:
        torus_ring.validate({
            "major_diameter_mm": 300, "minor_diameter_mm": 200,
            "material_id": "bronze_cast",
        }, None)
    assert "major" in str(exc.value)


def test_step_inset_under_tolerance_floor_refused():
    with pytest.raises(ConstraintViolation) as exc:
        stepped_monolith.validate({
            "base_length_mm": 1200, "base_width_mm": 1200, "steps": 3,
            "step_inset_mm": 5, "material_id": "basalt_slab",
        }, None)
    text = str(exc.value)
    assert "step_inset_mm" in text and "10" in text  # basalt joint floor


def test_water_wall_thickness_floor_refused():
    # basalt: floor = 3 x 20 = 60 mm (judgement stand-in, ADR-055).
    with pytest.raises(ConstraintViolation) as exc:
        water_wall.validate({
            "length_mm": 2400, "height_mm": 1800, "thickness_mm": 40,
            "material_id": "basalt_slab",
        }, None)
    text = str(exc.value)
    assert "thickness_mm" in text and "60" in text


# --- bearing honesty (ADR-053 extended) --------------------------------------


def test_torus_knife_line_contact_refused_and_sunk_torus_passes():
    plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 1600, "height_mm": 300,
                        "material_id": "basalt_slab"}},
        {"element_id": "t1", "primitive": "torus_ring",
         "parameters": {"major_diameter_mm": 1200, "minor_diameter_mm": 200,
                        "material_id": "basalt_slab"},
         # basalt joint floor 10: chord = 2·sqrt(10·(200−10)) ≈ 87 mm ≥ 10 ✓
         "joint": {"type": "stack_on", "parent": "p1"}},
    ]
    solid, manifest = assemble(plan, seed=7)
    assert manifest["body_count_brep"] == 1
    # Force a shallower overlap than the floor: refused with the chord.
    plan[1]["joint"]["overlap_mm"] = 2
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan, seed=7)
    assert "overlap_mm=2" in str(exc.value)


def test_rect_on_round_uses_inscribed_circle_seat():
    # basin_rect 2000x1200 on a plinth ⌀1000: inscribed circle ⌀1200 —
    # conservative seat = min(1200, 1000)/2 = 500 ≥ 10 floor → passes.
    plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 1000, "height_mm": 300,
                        "material_id": "basalt_slab"}},
        {"element_id": "b1", "primitive": "basin_rect",
         "parameters": {"length_mm": 2000, "width_mm": 1200,
                        "height_mm": 450, "wall_mm": 40, "floor_mm": 60,
                        "material_id": "basalt_slab"},
         "joint": {"type": "stack_on", "parent": "p1"}},
    ]
    solid, manifest = assemble(plan, seed=7)
    assert manifest["body_count_brep"] == 1


# --- the gate composition, single-process (two-process is the gate's job) ---


def test_24_blade_array_inside_three_primitive_assembly():
    plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 1400, "height_mm": 400,
                        "material_id": "basalt_slab"}},
        {"element_id": "b1", "primitive": "basin_round",
         "parameters": {"diameter_mm": 1200, "height_mm": 350,
                        "wall_mm": 40, "floor_mm": 80,
                        "material_id": "basalt_slab"},
         "joint": {"type": "stack_on", "parent": "p1"}},
        {"element_id": "a1", "primitive": "blade_fin_array",
         "parameters": {"hub_diameter_mm": 320, "hub_height_mm": 500,
                        "blade_count": 24, "blade_length_mm": 250,
                        "blade_height_mm": 400, "blade_thickness_mm": 20,
                        "material_id": "stainless_316l_sheet"},
         "joint": {"type": "concentric_insert", "parent": "b1"}},
    ]
    solid, manifest = assemble(plan, seed=7)
    assert manifest["body_count_brep"] == 1
    assert len(manifest["elements"]) == 3
    vc = manifest["volume_conservation"]
    assert vc["delta_pct"] <= vc["tolerance_pct"]
