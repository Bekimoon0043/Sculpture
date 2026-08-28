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


def test_fabrication_limits_from_spec_preserves_the_axes():
    """PR-1 (ADR-059): the spec's {x,y,z} survives, never collapsed.

    Until PR-1 this function returned max(x,y,z) = 1.2 — the LOOSEST axis
    became the limit for all three, silently under-enforcing y and z. The
    old test (test_fabrication_limits_from_spec_scalarizes_module_box)
    pinned that defect as the contract; it was reported red before this
    rewrite.
    """
    assert fabrication_limits_from_spec(_slice_a_spec()) == {
        "max_lift_kg": 2000,
        "max_module_m": {"x": 1.0, "y": 1.2, "z": 0.8},
    }


def test_fabrication_limits_from_spec_refuses_a_scalar():
    """Amendment 3: this function reads Design Specs ONLY. A scalar here
    is a malformed spec, not a Designer cubic envelope — that
    compatibility lives at assemble() alone."""
    spec = _slice_a_spec()
    spec["fabrication"]["max_module_m"] = 2.4
    with pytest.raises(ConstraintViolation) as exc:
        fabrication_limits_from_spec(spec)
    assert "max_module_m" in str(exc.value)


def test_fabrication_limits_from_spec_refuses_bad_axes():
    """Amendment 4: exactly x, y, z; no booleans, non-numerics,
    non-finite values, zeros or negatives — each named loudly."""
    bad_values = [
        {"x": 1.0, "y": 1.2},                        # missing axis
        {"x": 1.0, "y": 1.2, "z": 0.8, "w": 1.0},    # extra axis
        {"x": True, "y": 1.2, "z": 0.8},             # boolean
        {"x": "1.0", "y": 1.2, "z": 0.8},            # non-numeric
        {"x": float("inf"), "y": 1.2, "z": 0.8},     # non-finite
        {"x": 0, "y": 1.2, "z": 0.8},                # zero
        {"x": -1.0, "y": 1.2, "z": 0.8},             # negative
    ]
    for bad in bad_values:
        spec = _slice_a_spec()
        spec["fabrication"]["max_module_m"] = bad
        with pytest.raises(ConstraintViolation):
            fabrication_limits_from_spec(spec)


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
