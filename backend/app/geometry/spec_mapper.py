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
from app.geometry.segmentation import normalize_module_limit_m

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
        # slice B rim treatments (ADR-054)
        "rim": "rim_treatment",
        "crest_radius": "crest_radius_mm",
        "drip_edge": "drip_edge_mm",
        "coping_overhang": "coping_overhang_mm",
        "coping_thickness": "coping_thickness_mm",
        "pool_edge_radius": "pool_edge_radius_mm",
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
    # slice C1 (ADR-055)
    "basin_rect": {
        "length": "length_mm",
        "width": "width_mm",
        "depth": "height_mm",
        "height": "height_mm",
        "wall": "wall_mm",
        "wall_thickness": "wall_mm",
        "floor": "floor_mm",
        "floor_thickness": "floor_mm",
        "corner_radius": "corner_radius_mm",
    },
    "stepped_monolith": {
        "length": "base_length_mm",
        "base_length": "base_length_mm",
        "width": "base_width_mm",
        "base_width": "base_width_mm",
        "step_height": "step_height_mm",
        "step_inset": "step_inset_mm",
        "inset": "step_inset_mm",
    },
    "water_wall": {
        "length": "length_mm",
        "height": "height_mm",
        "thickness": "thickness_mm",
        "wall": "thickness_mm",
        "crest_radius": "crest_radius_mm",
        "drip_edge": "drip_edge_mm",
    },
    "torus_ring": {
        "major_diameter": "major_diameter_mm",
        "outer_diameter": "major_diameter_mm",
        "diameter": "major_diameter_mm",
        "minor_diameter": "minor_diameter_mm",
        "section_diameter": "minor_diameter_mm",
    },
    "blade_fin_array": {
        "hub_diameter": "hub_diameter_mm",
        "hub_height": "hub_height_mm",
        "count": "blade_count",
        "blades": "blade_count",
        "blade_length": "blade_length_mm",
        "blade_height": "blade_height_mm",
        "blade_thickness": "blade_thickness_mm",
        "thickness": "blade_thickness_mm",
    },
    "lotus_petal_array": {
        "hub_diameter": "hub_diameter_mm",
        "hub_height": "hub_height_mm",
        "count": "petal_count",
        "petals": "petal_count",
        "petal_length": "petal_length_mm",
        "petal_width": "petal_width_mm",
        "petal_thickness": "petal_thickness_mm",
        "thickness": "petal_thickness_mm",
        "tilt": "tilt_deg",
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
    """Design-Spec fabrication limits for registry.assemble — PER-AXIS.

    The schema (design_spec_v1.json) has always required max_module_m as
    the object {x, y, z}; until PR-1 (ADR-059) this function collapsed it
    to max(x,y,z), silently gating the two tighter axes against the
    loosest. It now preserves the axes, validated (each finite and > 0),
    and REFUSES a scalar: this function reads Design Specs only, and a
    scalar here is a malformed spec, not a Designer cubic envelope — that
    compatibility lives at assemble() alone (Amendment 3, PR-1 approval).
    """
    fabrication = spec.get("fabrication") or {}
    limits: dict[str, Any] = {}
    if "max_lift_kg" in fabrication:
        limits["max_lift_kg"] = fabrication["max_lift_kg"]
    max_module = fabrication.get("max_module_m")
    if max_module is not None:
        try:
            limits["max_module_m"] = normalize_module_limit_m(
                max_module, allow_scalar=False)
        except ValueError as exc:
            raise ConstraintViolation([
                f"Design Spec fabrication.max_module_m is malformed: {exc}"
            ]) from exc
    return limits


#: A weir node must sit AT the crest it claims (ADR-054): the tolerance is
#: survey noise, not a lever — anything larger means the water plan and the
#: geometry disagree about where the water leaves the basin.
_WEIR_ELEVATION_TOL_MM = 5.0


def _wire_hydraulics(
    spec: dict[str, Any],
    eid: str,
    element: dict[str, Any],
    primitive: str,
    parameters: dict[str, Any],
    plan_element: dict[str, Any],
    violations: list[str],
) -> None:
    """Slice B (ADR-054): hydraulic facts come FROM the network, never from
    invention — and never from silent defaults.

    * a `weir` node bound to this element demands (and supplies) the
      weir_edge treatment, and its elevation must MATCH the element's crest
      elevation within survey tolerance;
    * a weir_edge treatment WITHOUT a weir node is refused — a spillway the
      water plan does not know is invention;
    * `nozzle` nodes become ONE nozzle_ring fixture (count = nodes, bore
      verbatim); mixed bores are refused (slice B limit).
    """
    nodes = (spec.get("hydraulic_network") or {}).get("nodes") or []
    weir_nodes = [
        n for n in nodes
        if n.get("type") == "weir" and n.get("element_id") == eid
    ]
    nozzle_nodes = sorted(
        (n for n in nodes
         if n.get("type") == "nozzle" and n.get("element_id") == eid),
        key=lambda n: str(n.get("node_id")),
    )

    if weir_nodes:
        if primitive != "basin_round":
            violations.append(
                f"{eid}: weir node {weir_nodes[0].get('node_id')!r} targets "
                f"a {primitive!r} — only basin_round carries a weir crest "
                "in slice B"
            )
            return
        if len(weir_nodes) > 1:
            violations.append(
                f"{eid}: {len(weir_nodes)} weir nodes on one element — "
                "slice B builds one 360° crest per basin"
            )
            return
        node = weir_nodes[0]
        stated = parameters.get("rim_treatment")
        if stated not in (None, "weir_edge"):
            violations.append(
                f"{eid}: rim_treatment={stated!r} but weir node "
                f"{node.get('node_id')!r} declares a spill crest — the "
                "water plan and the rim disagree"
            )
            return
        height = parameters.get("height_mm")
        if height is None:
            height = PRIMITIVES[primitive].PARAMETERS["height_mm"]["default"]
        z_m = float((element.get("position") or {}).get("z_m", 0.0))
        rim_mm = z_m * 1000.0 + float(height)
        node_mm = float(node.get("elevation_m", 0.0)) * 1000.0
        if abs(node_mm - rim_mm) > _WEIR_ELEVATION_TOL_MM:
            violations.append(
                f"{eid}: weir node {node.get('node_id')!r} elevation "
                f"{node_mm:g} mm does not match the crest elevation "
                f"{rim_mm:g} mm (base {z_m * 1000:g} + height {height:g}; "
                f"tolerance {_WEIR_ELEVATION_TOL_MM:g} mm) — for a 360° "
                "revolved basin the crest IS the wall top (ADR-054): move "
                "the node or resize/re-seat the basin"
            )
            return
        parameters["rim_treatment"] = "weir_edge"
    elif parameters.get("rim_treatment") == "weir_edge":
        violations.append(
            f"{eid}: rim_treatment=weir_edge but hydraulic_network has no "
            "weir node for this element — a spillway the water plan does "
            "not know is invention; declare the weir node at the crest "
            "elevation"
        )
        return

    if nozzle_nodes:
        if primitive != "basin_round":
            violations.append(
                f"{eid}: nozzle nodes target a {primitive!r} — only "
                "basin_round floors carry nozzle rings in slice B"
            )
            return
        bores = []
        for n in nozzle_nodes:
            bore = n.get("nozzle_bore_mm")
            if bore is None:
                violations.append(
                    f"{eid}: nozzle node {n.get('node_id')!r} carries no "
                    "nozzle_bore_mm — the bore comes from the network, "
                    "never from invention"
                )
                return
            bores.append(float(bore))
        if len(set(bores)) > 1:
            violations.append(
                f"{eid}: nozzle nodes carry MIXED bores "
                f"{sorted(set(bores))} — slice B drills one bore size per "
                "basin (a mixed ring is a slice-C fixture)"
            )
            return
        plan_element["fixtures"] = [{
            "type": "nozzle_ring",
            "count": len(nozzle_nodes),
            "bore_mm": bores[0],
        }]


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
        _wire_hydraulics(
            spec, eid, element, primitive, parameters, plan_element,
            violations,
        )
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

