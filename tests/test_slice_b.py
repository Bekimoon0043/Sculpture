"""Phase 6 slice B — rim treatments + the nozzle fixture (ADR-054).

Everything here is real geometry ($0, no AI): treatments are drawn INTO the
basin's revolved profile (ADR-010 pattern), nozzle bores are cut by trusted
assembler code, and every hydraulic number comes from the spec's
hydraulic_network — the mapper refuses invention rather than defaulting.
"""

from __future__ import annotations

import pytest

from app.geometry.primitives.base import ConstraintViolation

pytest.importorskip("build123d")

from app.geometry.assembly import assemble  # noqa: E402
from app.geometry.primitives import basin_round  # noqa: E402
from app.geometry.spec_mapper import assembly_plan_from_spec  # noqa: E402

#: Pinned 2026-08-26 BEFORE any slice-B profile edit: the default basin
#: (⌀2600 x 450, wall 20, floor 20, basalt) at the seed-42 STEP timestamp.
#: An untreated basin must keep exporting these exact bytes forever.
DEFAULT_BASIN_STEP_SHA256 = (
    "6038d26f28cd61b0c01ae9fde00ff2841b34ad0d6228cc7c4bbdbdd1eeacf0f0"
)


def _basin(params: dict):
    p = basin_round.validate(params, None)
    return basin_round.build(p), p


# --- byte-guard --------------------------------------------------------------


def test_untreated_basin_bytes_unchanged(tmp_path):
    from app.geometry.exporters import export_step
    from app.geometry.kernel import step_timestamp_for

    solid, _ = _basin({})
    sha = export_step(solid, tmp_path / "b.step", step_timestamp_for(42))
    assert sha == DEFAULT_BASIN_STEP_SHA256


# --- treatments: real solids, watertight, honest refusals -------------------


def test_weir_edge_builds_watertight_and_taller_outer_radius():
    solid, p = _basin({
        "diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
        "floor_mm": 60, "rim_treatment": "weir_edge",
        "material_id": "basalt_slab",
    })
    assert len(solid.solids()) == 1
    # The drip lip overhangs the outer face by drip_edge_mm.
    out_d = basin_round.max_outer_diameter_mm(p)
    assert out_d == pytest.approx(2000 + 2 * p.drip_edge_mm)
    # Crest land >= the basalt feature floor (15), printed arithmetic:
    land = p.wall_mm + p.drip_edge_mm - p.crest_radius_mm
    assert land >= 15


def test_weir_edge_land_under_feature_floor_refused():
    # basalt wall 20: land = 20 + drip(4) - crest(10) = 14 < the 15 floor.
    # (drip 4 clears its own floor max(3, overlap 10/3) = 3.33.)
    with pytest.raises(ConstraintViolation) as exc:
        basin_round.validate({
            "diameter_mm": 2000, "height_mm": 450, "wall_mm": 20,
            "rim_treatment": "weir_edge", "drip_edge_mm": 4,
            "crest_radius_mm": 10, "material_id": "basalt_slab",
        }, None)
    text = str(exc.value)
    assert "crest land" in text and "15" in text


def test_weir_edge_316l_formula_floor_applies():
    # 316L: internal radius floor == wall. crest_radius below wall refused.
    with pytest.raises(ConstraintViolation) as exc:
        basin_round.validate({
            "diameter_mm": 800, "height_mm": 300, "wall_mm": 6,
            "rim_treatment": "weir_edge", "crest_radius_mm": 4,
            "material_id": "stainless_316l_sheet",
        }, None)
    assert "crest_radius" in str(exc.value)


def test_coping_builds_and_raises_height_and_annulus():
    solid, p = _basin({
        "diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
        "rim_treatment": "coping", "coping_overhang_mm": 60,
        "coping_thickness_mm": 50, "material_id": "basalt_slab",
    })
    assert len(solid.solids()) == 1
    assert basin_round.height_mm(p) == 500  # 450 + thickness
    out, inner = basin_round.stack_top_annulus_mm(p)
    assert out == pytest.approx(2000 + 2 * 60)
    assert inner == pytest.approx(2000 - 2 * 40)


def test_coping_overhang_bound_refused():
    with pytest.raises(ConstraintViolation) as exc:
        basin_round.validate({
            "diameter_mm": 2000, "wall_mm": 40, "rim_treatment": "coping",
            "coping_overhang_mm": 150, "material_id": "basalt_slab",
        }, None)
    assert "coping_overhang_mm" in str(exc.value)


def test_pool_edge_builds_and_radius_over_half_wall_refused():
    solid, p = _basin({
        "diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
        "rim_treatment": "pool_edge", "pool_edge_radius_mm": 15,
        "material_id": "basalt_slab",
    })
    assert len(solid.solids()) == 1
    with pytest.raises(ConstraintViolation) as exc:
        basin_round.validate({
            "diameter_mm": 2000, "wall_mm": 40, "rim_treatment": "pool_edge",
            "pool_edge_radius_mm": 25, "material_id": "basalt_slab",
        }, None)
    assert "wall_mm/2" in str(exc.value)


def test_treatment_params_without_treatment_refused():
    with pytest.raises(ConstraintViolation) as exc:
        basin_round.validate({
            "diameter_mm": 2000, "coping_overhang_mm": 60,
            "material_id": "basalt_slab",
        }, None)
    assert "rim_treatment" in str(exc.value)


# --- nozzle fixture: bores cut by trusted code, volume arithmetic -----------


def _nozzle_plan(count: int, bore: float, ring_d: float | None = None):
    fixture: dict = {"type": "nozzle_ring", "count": count, "bore_mm": bore}
    if ring_d is not None:
        fixture["ring_diameter_mm"] = ring_d
    return [{
        "element_id": "b1",
        "primitive": "basin_round",
        "parameters": {"diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
                       "floor_mm": 60, "material_id": "basalt_slab"},
        "fixtures": [fixture],
    }]


def test_nozzle_ring_removes_exact_volume():
    import math

    plain, _ = assemble(_nozzle_plan(0, 0)[:0] + [{
        "element_id": "b1", "primitive": "basin_round",
        "parameters": {"diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
                       "floor_mm": 60, "material_id": "basalt_slab"},
    }], seed=7)
    bored, manifest = assemble(_nozzle_plan(3, 20.6), seed=7)
    el = manifest["elements"][0]
    assert el["fixtures"][0]["count"] == 3
    removed = (plain.volume - bored.volume)
    expected = 3 * math.pi * (20.6 / 2) ** 2 * 60
    assert removed == pytest.approx(expected, rel=0.01)
    assert manifest["body_count_brep"] == 1


def test_nozzle_web_under_feature_floor_refused():
    # Ring so tight the stone web between adjacent bores vanishes.
    with pytest.raises(ConstraintViolation) as exc:
        assemble(_nozzle_plan(24, 50, ring_d=200), seed=7)
    text = str(exc.value)
    assert "web" in text and "15" in text  # basalt feature floor named


def test_nozzle_on_primitive_without_floor_refused():
    plan = [{
        "element_id": "p1", "primitive": "plinth",
        "parameters": {"top_diameter_mm": 900, "material_id": "basalt_slab"},
        "fixtures": [{"type": "nozzle_ring", "count": 2, "bore_mm": 20}],
    }]
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan, seed=7)
    assert "basin_round" in str(exc.value)


# --- the mapper: hydraulics from the spec, never invention ------------------


def _spec_with(nodes: list[dict], element_params: dict | None = None):
    return {
        "massing": {"elements": [{
            "element_id": "b1", "primitive": "basin_round",
            "material_id": "basalt_slab",
            "parameters": element_params or {
                "diameter": {"value": 2000, "unit": "mm"},
                "height": {"value": 450, "unit": "mm"},
                "wall": {"value": 40, "unit": "mm"},
                "floor": {"value": 60, "unit": "mm"},
            },
            "position": {"x_m": 0, "y_m": 0, "z_m": 0.8, "rot_z_deg": 0},
        }]},
        "hydraulic_network": {"nodes": nodes, "edges": []},
    }


def test_mapper_wires_weir_node_and_checks_elevation():
    # Basin base at 0.8 m, height 450 -> crest at 1.25 m. Node matches.
    plan = assembly_plan_from_spec(_spec_with([
        {"node_id": "w1", "type": "weir", "elevation_m": 1.25,
         "element_id": "b1"},
    ]))
    assert plan[0]["parameters"]["rim_treatment"] == "weir_edge"


def test_mapper_refuses_weir_elevation_mismatch_with_both_numbers():
    with pytest.raises(ConstraintViolation) as exc:
        assembly_plan_from_spec(_spec_with([
            {"node_id": "w1", "type": "weir", "elevation_m": 1.10,
             "element_id": "b1"},
        ]))
    text = str(exc.value)
    assert "1100" in text and "1250" in text  # both elevations, in mm


def test_mapper_refuses_weir_treatment_without_a_node():
    spec = _spec_with([])
    spec["massing"]["elements"][0]["parameters"]["rim_treatment"] = "weir_edge"
    with pytest.raises(ConstraintViolation) as exc:
        assembly_plan_from_spec(spec)
    assert "weir node" in str(exc.value)


def test_mapper_wires_nozzle_nodes_into_one_fixture():
    plan = assembly_plan_from_spec(_spec_with([
        {"node_id": f"n{i}", "type": "nozzle", "elevation_m": 0.86,
         "element_id": "b1", "nozzle_bore_mm": 20.6}
        for i in range(3)
    ]))
    fixture = plan[0]["fixtures"][0]
    assert fixture == {"type": "nozzle_ring", "count": 3, "bore_mm": 20.6}


def test_mapper_refuses_mixed_bores():
    with pytest.raises(ConstraintViolation) as exc:
        assembly_plan_from_spec(_spec_with([
            {"node_id": "n1", "type": "nozzle", "elevation_m": 0.86,
             "element_id": "b1", "nozzle_bore_mm": 20.6},
            {"node_id": "n2", "type": "nozzle", "elevation_m": 0.86,
             "element_id": "b1", "nozzle_bore_mm": 32.0},
        ]))
    text = str(exc.value)
    assert "20.6" in text and "32" in text
