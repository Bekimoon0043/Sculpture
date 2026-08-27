"""blade_fin_array — radial blades on a cylindrical hub
(Phase 6 slice C1, ADR-055).

The array risk this slice exists to retire: N boolean fuses in one
element. Blades fuse in INDEX order (never set order — determinism), each
engaged into the hub by the material joint floor (a blade that merely
touches the hub is the ADR-029 tangency), and the spacing at the hub must
clear the tangency band (base.check_array_spacing).

Coordinate system: Z up, origin at the centre of the hub base; blade 0
points +X, the rest follow counter-clockwise at 2π/N.
"""

from __future__ import annotations

import math
from typing import Any

from app.core.config import Material
from app.geometry.primitives.base import (
    ConstraintViolation,
    check_array_spacing,
    check_material,
    collect_model_errors,
    load_materials,
    make_params_model,
    merge_raw,
)

PRIMITIVE_ID = "blade_fin_array"
PURPOSE = "radial blade/fin ring on a cylindrical hub (kinetic silhouette)"
CAN_PARENT_STACK = False
CAN_PARENT_INSERT = False

SEGMENTATION_MODE = "discrete_array"  # a saw plane through a blade ring
                                      # makes fragments, not modules: at a
                                      # 0.8 m limit a 24-blade array gives
                                      # 25 solids, smallest 0.9 kg against
                                      # a largest of 2,685.7 kg. Refused by
                                      # name; the real decomposition is hub
                                      # + N blades (LIMITATIONS.md 11).
PARAMETERS: dict[str, dict[str, Any]] = {
    "hub_diameter_mm": {
        "unit": "mm", "default": 400, "min": 150, "max": 1500,
        "type": "float", "notes": "cylindrical hub the blades engage into",
    },
    "hub_height_mm": {
        "unit": "mm", "default": 600, "min": 100, "max": 1500,
        "type": "float", "notes": "hub height; blades never exceed it",
    },
    "blade_count": {
        "unit": "count", "default": 12, "min": 3, "max": 36, "type": "int",
        "notes": "number of blades; the hub-circle spacing arithmetic is "
        "the real ceiling (ADR-055)",
    },
    "blade_length_mm": {
        "unit": "mm", "default": 400, "min": 100, "max": 1500,
        "type": "float", "notes": "radial reach beyond the hub surface",
    },
    "blade_height_mm": {
        "unit": "mm", "default": 500, "min": 100, "max": 1500,
        "type": "float", "notes": "blade height; must be <= hub height so "
        "every blade fully engages the hub face",
    },
    "blade_thickness_mm": {
        "unit": "mm", "default": None, "min": 3, "max": 150, "type": "float",
        "optional": True,
        "notes": "floor = material min_feature (316L: = thickness formula); "
        "omit for max(30, floor)",
    },
    "material_id": {
        "unit": "materials.yaml key", "default": "stainless_316l_sheet",
        "min": None, "max": None, "type": "str",
        "notes": "drives mass calc + feature/joint floors",
    },
}

BladeFinArrayParams = make_params_model("BladeFinArrayParams", PARAMETERS)


def validate(raw: dict[str, Any], materials: dict[str, Material] | None = None):
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []
    merged = merge_raw(PRIMITIVE_ID, PARAMETERS, raw, violations)
    try:
        params = BladeFinArrayParams.model_validate(merged)
    except Exception as exc:
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    material = check_material(PRIMITIVE_ID, params.material_id, materials, violations)
    if material is not None:
        t = params.blade_thickness_mm
        feat_floor_default = float(material.min_feature_floor_mm(
            t if t is not None else 30.0))
        if t is None:
            t = max(30.0, feat_floor_default)
            params = params.model_copy(update={"blade_thickness_mm": t})
        feat_floor = float(material.min_feature_floor_mm(t))
        if t < feat_floor:
            violations.append(
                f"blade_thickness_mm={t:g} < the {params.material_id} "
                f"feature floor {feat_floor:g} mm (signed sheet §2.2)"
            )
        check_array_spacing(
            "blades", params.hub_diameter_mm, params.blade_count, t,
            material, params.material_id, violations,
        )
    if params.blade_height_mm > params.hub_height_mm:
        violations.append(
            f"blade_height_mm={params.blade_height_mm:g} > hub_height_mm="
            f"{params.hub_height_mm:g} — a blade taller than its hub is "
            "not engaged along its full height"
        )
    if violations:
        raise ConstraintViolation(violations)
    return params


def build(p):
    from build123d import Box, Cylinder, Pos, Rot

    mat = load_materials()[p.material_id]
    engage = float(mat.joint_overlap_mm)
    hub_r = p.hub_diameter_mm / 2.0
    solid = Pos(0, 0, p.hub_height_mm / 2) * Cylinder(hub_r, p.hub_height_mm)
    radial = engage + p.blade_length_mm
    # centre of the blade box along +X: from (hub_r - engage) outward
    cx = hub_r - engage + radial / 2.0
    for i in range(int(p.blade_count)):
        angle = 360.0 * i / int(p.blade_count)
        blade = (
            Rot(0, 0, angle)
            * Pos(cx, 0, p.blade_height_mm / 2)
            * Box(radial, p.blade_thickness_mm, p.blade_height_mm)
        )
        solid = solid + blade  # index order — deterministic fuse sequence
    solids = solid.solids()
    if len(solids) != 1:
        raise RuntimeError(
            f"blade_fin_array construction produced {len(solids)} solids, "
            "expected 1"
        )
    return solids[0]


def height_mm(p) -> float:
    return float(p.hub_height_mm)


def anchors(p) -> dict[str, float | None]:
    return {"base": 0.0, "top": float(p.hub_height_mm), "seat": None}


def max_outer_diameter_mm(p) -> float:
    return float(p.hub_diameter_mm + 2 * p.blade_length_mm)


def inner_diameter_mm(p) -> float | None:
    return None


def stack_top_annulus_mm(p) -> None:
    return None


def base_annulus_mm(p) -> tuple[float, float]:
    """The hub disc — blades' feet are ignored (conservative, ADR-055)."""
    return float(p.hub_diameter_mm), 0.0
