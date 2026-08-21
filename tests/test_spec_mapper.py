"""Phase 6 A2: Design Spec -> assembly plan mapping."""

from __future__ import annotations

import pytest

from app.geometry.primitives.base import ConstraintViolation
from app.geometry.spec_mapper import (
    assembly_plan_from_spec,
    fabrication_limits_from_spec,
)
from tests.test_design_spec_schema import valid_example_spec


def _slice_a_spec():
    spec = valid_example_spec()
    spec["massing"]["elements"] = [
        {
            "element_id": "p1",
            "primitive": "plinth",
            "parameters": {
                "top_diameter": {"value": 0.7, "unit": "m"},
                "height": {"value": 300, "unit": "mm"},
            },
            "material_id": "basalt_slab",
            "position": {"x_m": 0, "y_m": 0, "z_m": 0},
        },
        {
            "element_id": "b1",
            "primitive": "basin_round",
            "parameters": {
                "diameter": {"value": 600, "unit": "mm"},
                "height": {"value": 300, "unit": "mm"},
                "wall": {"value": 25, "unit": "mm"},
                "floor": {"value": 60, "unit": "mm"},
            },
            "material_id": "basalt_slab",
            "position": {"x_m": 0, "y_m": 0, "z_m": 0.29},
            "parent_id": "p1",
        },
        {
            "element_id": "c1",
            "primitive": "sculptural_column",
            "parameters": {
                "diameter": {"value": 100, "unit": "mm"},
                "height": {"value": 400, "unit": "mm"},
            },
            "material_id": "basalt_slab",
            "position": {"x_m": 0, "y_m": 0, "z_m": 0.35},
            "parent_id": "b1",
        },
    ]
    spec["fabrication"]["max_lift_kg"] = 2000
    spec["fabrication"]["max_module_m"] = {"x": 1.0, "y": 1.2, "z": 0.8}
    return spec


def test_assembly_plan_from_spec_maps_slice_a_tree():
    plan = assembly_plan_from_spec(_slice_a_spec())

    assert [e["element_id"] for e in plan] == ["b1", "c1", "p1"]
    by_id = {e["element_id"]: e for e in plan}
    assert by_id["p1"]["primitive"] == "plinth"
    assert by_id["p1"]["parameters"]["top_diameter_mm"] == 700
    assert by_id["p1"]["parameters"]["height_mm"] == 300
    assert "joint" not in by_id["p1"]

    assert by_id["b1"]["joint"] == {"type": "stack_on", "parent": "p1"}
    assert by_id["b1"]["parameters"]["diameter_mm"] == 600
    assert by_id["b1"]["parameters"]["floor_mm"] == 60

    assert by_id["c1"]["joint"] == {
        "type": "concentric_insert",
        "parent": "b1",
    }
    assert by_id["c1"]["parameters"]["diameter_mm"] == 100


def test_fabrication_limits_from_spec_scalarizes_module_box():
    assert fabrication_limits_from_spec(_slice_a_spec()) == {
        "max_lift_kg": 2000,
        "max_module_m": 1.2,
    }


def test_assembly_plan_from_spec_refuses_unknown_parameter():
    spec = _slice_a_spec()
    spec["massing"]["elements"][0]["parameters"]["petal_count"] = {
        "value": 8,
        "unit": "deg",
    }
    with pytest.raises(ConstraintViolation) as exc:
        assembly_plan_from_spec(spec)
    assert "petal_count" in str(exc.value)
    assert "plinth" in str(exc.value)


def test_assembly_plan_from_spec_refuses_unknown_parent():
    spec = _slice_a_spec()
    spec["massing"]["elements"][1]["parent_id"] = "ghost"
    with pytest.raises(ConstraintViolation) as exc:
        assembly_plan_from_spec(spec)
    assert "parent_id 'ghost' not found" in str(exc.value)


def test_assembly_plan_from_spec_refuses_bad_unit_for_mm():
    spec = _slice_a_spec()
    spec["massing"]["elements"][1]["parameters"]["diameter"]["unit"] = "deg"
    with pytest.raises(ConstraintViolation) as exc:
        assembly_plan_from_spec(spec)
    assert "unit 'deg' cannot map to diameter_mm" in str(exc.value)
