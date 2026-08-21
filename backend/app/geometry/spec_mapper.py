"""Design Spec -> Phase 6 Slice A1 assembly plan.

This is trusted code: AI-written fabrication programs may ask the registry to
map a Design Spec, but the model does not decide booleans, placement math or
which primitive parameters are legal. The mapper is deliberately narrow for
Slice A1 and refuses ambiguous shapes with ConstraintViolation instead of
guessing.
"""

from __future__ import annotations

from typing import Any

from app.geometry.primitives import PRIMITIVES
from app.geometry.primitives.base import ConstraintViolation

_UNIT_TO_MM = {"mm": 1.0, "m": 1000.0}

_ALIASES: dict[str, dict[str, str]] = {
    "basin_round": {
        "diameter": "diameter_mm",
        "outer_diameter": "diameter_mm",
        "depth": "height_mm",
        "height": "height_mm",
        "wall": "wall_mm",
        "wall_thickness": "wall_mm",
        "floor": "floor_mm",
        "floor_thickness": "floor_mm",
        "clearance": "min_clearance_mm",
        "min_clearance": "min_clearance_mm",
    },
    "plinth": {
        "diameter": "top_diameter_mm",
        "top_diameter": "top_diameter_mm",
        "height": "height_mm",
        "wall": "wall_mm",
        "wall_thickness": "wall_mm",
        "taper": "taper_deg",
    },
    "sculptural_column": {
        "diameter": "diameter_mm",
        "base_diameter": "diameter_mm",
        "height": "height_mm",
        "wall": "wall_mm",
        "wall_thickness": "wall_mm",
        "bore": "bore_mm",
        "bore_diameter": "bore_mm",
        "taper": "taper_deg",
    },
    "tiered_cascade": {
        "tiers": "tiers",
        "tier_top_diameter": "tier_top_diameter_mm",
        "tier_diameter_step": "tier_diameter_step_mm",
        "dish_depth": "dish_depth_mm",
        "tier_spacing": "tier_spacing_mm",
        "lip_fillet": "lip_fillet_mm",
        "column_diameter": "column_diameter_mm",
        "basin_diameter": "basin_diameter_mm",
        "basin_height": "basin_height_mm",
        "basin_wall": "basin_wall_mm",
        "column_wall": "column_wall_mm",
        "bore_diameter": "bore_diameter_mm",
        "min_clearance": "min_clearance_mm",
    },
}

_CAN_INSERT = {("sculptural_column", "basin_round")}


def _dimension_to_number(value: Any, target_key: str, path: str) -> float | int | str:
    """Convert Design Spec dimension objects to primitive parameter values."""
    if not isinstance(value, dict):
        return value
    if "value" not in value or "unit" not in value:
        raise ConstraintViolation([
            f"{path}: dimension object must carry value and unit"
        ])
    raw_value = value["value"]
    unit = value["unit"]
    if target_key.endswith("_mm"):
        if unit not in _UNIT_TO_MM:
            raise ConstraintViolation([
                f"{path}: unit {unit!r} cannot map to {target_key}; use mm or m"
            ])
        return float(raw_value) * _UNIT_TO_MM[unit]
    if target_key.endswith("_deg"):
        if unit != "deg":
            raise ConstraintViolation([
                f"{path}: unit {unit!r} cannot map to {target_key}; use deg"
            ])
        return float(raw_value)
    if unit in _UNIT_TO_MM:
        return float(raw_value) * _UNIT_TO_MM[unit]
    return raw_value


def _map_parameters(primitive: str, raw: dict[str, Any], material_id: str) -> dict[str, Any]:
    aliases = _ALIASES.get(primitive, {})
    primitive_params = PRIMITIVES[primitive].PARAMETERS
    mapped: dict[str, Any] = {}
    violations: list[str] = []

    for key, value in sorted((raw or {}).items()):
        target = aliases.get(key, key)
        if target not in primitive_params:
            violations.append(
                f"{primitive}: parameter {key!r} is not supported by the "
                f"Slice A1 mapper (known: {', '.join(sorted(primitive_params))}; "
                f"aliases: {', '.join(sorted(aliases))})"
            )
            continue
        try:
            mapped[target] = _dimension_to_number(
                value, target, f"{primitive}.{key}"
            )
        except ConstraintViolation as exc:
            violations.extend(exc.violations)

    if violations:
        raise ConstraintViolation(violations)
    mapped["material_id"] = material_id
    return mapped


def _joint_type(child_primitive: str, parent_primitive: str) -> str:
    if (child_primitive, parent_primitive) in _CAN_INSERT:
        return "concentric_insert"
    return "stack_on"


def fabrication_limits_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    fabrication = spec.get("fabrication") or {}
    limits: dict[str, Any] = {}
    if "max_lift_kg" in fabrication:
        limits["max_lift_kg"] = fabrication["max_lift_kg"]
    max_module = fabrication.get("max_module_m")
    if isinstance(max_module, dict):
        values = [float(v) for v in max_module.values()]
        if values:
            limits["max_module_m"] = max(values)
    elif max_module is not None:
        limits["max_module_m"] = max_module
    return limits


def assembly_plan_from_spec(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Map Design Spec massing.elements to registry.assemble input.

    Slice A1 supports a tree using parent_id. Root is the one element without
    parent_id. parent_id becomes stack_on except sculptural_column into
    basin_round, which becomes concentric_insert.
    """
    elements = spec.get("massing", {}).get("elements", [])
    by_id: dict[str, dict[str, Any]] = {}
    violations: list[str] = []

    for i, element in enumerate(elements):
        eid = element.get("element_id")
        primitive = element.get("primitive")
        if not eid:
            violations.append(f"massing.elements[{i}] has no element_id")
            continue
        if eid in by_id:
            violations.append(f"element_id {eid!r} is duplicated")
            continue
        if primitive not in PRIMITIVES:
            violations.append(
                f"{eid}: primitive {primitive!r} is not in the live registry "
                f"(available: {', '.join(sorted(PRIMITIVES))})"
            )
            continue
        by_id[eid] = element

    if violations:
        raise ConstraintViolation(violations)

    plan: list[dict[str, Any]] = []
    for eid in sorted(by_id):
        element = by_id[eid]
        primitive = element["primitive"]
        try:
            parameters = _map_parameters(
                primitive,
                element.get("parameters") or {},
                element["material_id"],
            )
        except ConstraintViolation as exc:
            violations.extend(f"{eid}: {v}" for v in exc.violations)
            continue

        plan_element: dict[str, Any] = {
            "element_id": eid,
            "primitive": primitive,
            "parameters": parameters,
        }
        parent_id = element.get("parent_id")
        if parent_id:
            parent = by_id.get(parent_id)
            if parent is None:
                violations.append(f"{eid}: parent_id {parent_id!r} not found")
            else:
                plan_element["joint"] = {
                    "type": _joint_type(primitive, parent["primitive"]),
                    "parent": parent_id,
                }
        plan.append(plan_element)

    if violations:
        raise ConstraintViolation(violations)
    return plan

