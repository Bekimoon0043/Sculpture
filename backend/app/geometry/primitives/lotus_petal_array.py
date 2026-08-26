"""lotus_petal_array — tilted lens petals around a hub disc
(Phase 6 slice C1, ADR-055).

Each petal is a closed LENS profile (two circular arcs — sagitta
arithmetic, no free-form splines: those are slice D) extruded to the
petal thickness, tilted outward, and engaged into the hub by the material
joint floor. Petals fuse in INDEX order. Adjacent petals may cleanly gap
or cleanly overlap at the hub circle (real lotus petals overlap); the
near-tangent band between is refused (base.check_array_spacing).

Coordinate system: Z up, origin at the centre of the hub base; petal 0
points +X.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Material
from app.geometry.primitives.base import (
    ConstraintViolation,
    check_array_spacing,
    check_material,
    collect_model_errors,
    extrude_closed_profile,
    load_materials,
    make_params_model,
    merge_raw,
)

PRIMITIVE_ID = "lotus_petal_array"
PURPOSE = "ring of tilted lens petals on a hub disc (lotus sculpture)"
CAN_PARENT_STACK = False
CAN_PARENT_INSERT = False

PARAMETERS: dict[str, dict[str, Any]] = {
    "hub_diameter_mm": {
        "unit": "mm", "default": 500, "min": 150, "max": 1500,
        "type": "float", "notes": "hub disc the petals engage into",
    },
    "hub_height_mm": {
        "unit": "mm", "default": 200, "min": 100, "max": 800,
        "type": "float", "notes": "hub disc height",
    },
    "petal_count": {
        "unit": "count", "default": 8, "min": 6, "max": 24, "type": "int",
        "notes": "petals in the ring; the hub-circle spacing arithmetic is "
        "the real ceiling (ADR-055)",
    },
    "petal_length_mm": {
        "unit": "mm", "default": 500, "min": 200, "max": 1500,
        "type": "float", "notes": "petal length tip-to-base (the lens chord)",
    },
    "petal_width_mm": {
        "unit": "mm", "default": 250, "min": 100, "max": 800,
        "type": "float", "notes": "petal width at its widest (2x the lens "
        "sagitta); must stay under half the length or the lens degenerates",
    },
    "petal_thickness_mm": {
        "unit": "mm", "default": None, "min": 3, "max": 120, "type": "float",
        "optional": True,
        "notes": "floor = material min_feature; omit for max(25, floor)",
    },
    "tilt_deg": {
        "unit": "deg", "default": 35, "min": 0, "max": 60, "type": "float",
        "notes": "petal tilt up from horizontal; 0 = flat rosette, above "
        "60 it reads as a cup (taxonomy, ADR-055)",
    },
    "material_id": {
        "unit": "materials.yaml key", "default": "bronze_cast",
        "min": None, "max": None, "type": "str",
        "notes": "drives mass calc + feature/joint floors",
    },
}

LotusPetalArrayParams = make_params_model("LotusPetalArrayParams", PARAMETERS)


def validate(raw: dict[str, Any], materials: dict[str, Material] | None = None):
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []
    merged = merge_raw(PRIMITIVE_ID, PARAMETERS, raw, violations)
    try:
        params = LotusPetalArrayParams.model_validate(merged)
    except Exception as exc:
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    material = check_material(PRIMITIVE_ID, params.material_id, materials, violations)
    if material is not None:
        t = params.petal_thickness_mm
        if t is None:
            t = max(25.0, float(material.min_feature_floor_mm(25.0)))
            params = params.model_copy(update={"petal_thickness_mm": t})
        feat_floor = float(material.min_feature_floor_mm(t))
        if t < feat_floor:
            violations.append(
                f"petal_thickness_mm={t:g} < the {params.material_id} "
                f"feature floor {feat_floor:g} mm (signed sheet §2.2)"
            )
        check_array_spacing(
            "petals", params.hub_diameter_mm, params.petal_count,
            params.petal_width_mm, material, params.material_id, violations,
        )
    if params.petal_width_mm >= params.petal_length_mm:
        violations.append(
            f"petal_width_mm={params.petal_width_mm:g} >= petal_length_mm="
            f"{params.petal_length_mm:g} — at width = length the two lens "
            "arcs close into a circle (sagitta = chord/2); a petal is "
            "always longer than it is wide (ADR-055 arithmetic)"
        )
    if violations:
        raise ConstraintViolation(violations)
    return params


def _lens_radius(length: float, width: float) -> float:
    """Circular-segment radius for chord `length` and sagitta `width/2`."""
    s = width / 2.0
    return (length ** 2) / (8.0 * s) + s / 2.0


def build(p):
    from build123d import Cylinder, Polyline, Pos, RadiusArc, Rot

    mat = load_materials()[p.material_id]
    engage = float(mat.joint_overlap_mm)
    hub_r = p.hub_diameter_mm / 2.0
    solid = Pos(0, 0, p.hub_height_mm / 2) * Cylinder(hub_r, p.hub_height_mm)

    L, W, t = p.petal_length_mm, p.petal_width_mm, p.petal_thickness_mm
    R = _lens_radius(L, W)

    def draw() -> None:
        # Lens along +X from the origin: two opposite circular arcs.
        RadiusArc((0, 0), (L, 0), R)
        RadiusArc((L, 0), (0, 0), R)

    petal_flat = extrude_closed_profile(draw, t)
    for i in range(int(p.petal_count)):
        angle = 360.0 * i / int(p.petal_count)
        petal = (
            Rot(0, 0, angle)
            * Pos(hub_r - engage, 0, p.hub_height_mm - engage)
            * Rot(0, -p.tilt_deg, 0)
            * petal_flat
        )
        solid = solid + petal  # index order — deterministic fuse sequence
    solids = solid.solids()
    if len(solids) != 1:
        raise RuntimeError(
            f"lotus_petal_array construction produced {len(solids)} solids, "
            "expected 1"
        )
    return solids[0]


def height_mm(p) -> float:
    import math

    tip = p.hub_height_mm + p.petal_length_mm * math.sin(
        math.radians(p.tilt_deg))
    return float(max(p.hub_height_mm, tip))


def anchors(p) -> dict[str, float | None]:
    return {"base": 0.0, "top": height_mm(p), "seat": None}


def max_outer_diameter_mm(p) -> float:
    import math

    reach = p.hub_diameter_mm / 2.0 + p.petal_length_mm * math.cos(
        math.radians(p.tilt_deg))
    return float(2 * reach)


def inner_diameter_mm(p) -> float | None:
    return None


def stack_top_annulus_mm(p) -> None:
    return None


def base_annulus_mm(p) -> tuple[float, float]:
    """The hub disc only (conservative, ADR-055)."""
    return float(p.hub_diameter_mm), 0.0
