"""basin_rect — a rectangular tub, extruded (Phase 6 slice C1, ADR-055).

Outer rounded-rectangle block minus an inner rounded-rectangle cavity —
both closed profiles, both extruded (watertight by construction), the
cavity cut with overshoot exactly like the column bore (the proven
internal-boolean pattern). `corner_radius_mm` is the INNER corner radius:
that is the corner a tool must reach, so the signed §2.3
min_internal_radius floor binds on it (316L: = wall). The outer corner
radius is corner + wall, keeping the wall thickness constant around the
corner.

Coordinate system: Z up, origin at the centre of the base face.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Material
from app.geometry.primitives.base import (
    ConstraintViolation,
    check_material,
    check_wall_envelope,
    collect_model_errors,
    extrude_closed_profile,
    load_materials,
    make_params_model,
    merge_raw,
)

PRIMITIVE_ID = "basin_rect"
PURPOSE = "rectangular water basin (extruded tub with rounded inner corners)"
CAN_PARENT_STACK = False   # the rim is a rectangular ring: the circular
                           # seat model would misstate it (LIMITATIONS §11)
CAN_PARENT_INSERT = False  # concentric_insert assumes a circular interior

PARAMETERS: dict[str, dict[str, Any]] = {
    "length_mm": {
        "unit": "mm", "default": 2000, "min": 500, "max": 4000,
        "type": "float",
        "notes": "outer length; above 4000 it is a pool needing expansion "
        "joints, below 500 a bowl (ADR-055, taxonomy)",
    },
    "width_mm": {
        "unit": "mm", "default": 1200, "min": 500, "max": 4000,
        "type": "float", "notes": "outer width; same taxonomy bounds",
    },
    "height_mm": {
        "unit": "mm", "default": 450, "min": 200, "max": 1200,
        "type": "float", "notes": "outer height (rim above base)",
    },
    "wall_mm": {
        "unit": "mm", "default": 20, "min": 3, "max": 300, "type": "float",
        "notes": "wall thickness; material envelope applies (ADR-027)",
    },
    "floor_mm": {
        "unit": "mm", "default": None, "min": 3, "max": 400, "type": "float",
        "optional": True,
        "notes": "floor thickness; omit to use wall_mm; never thinner than "
        "the wall (it carries the water load)",
    },
    "corner_radius_mm": {
        "unit": "mm", "default": None, "min": 3, "max": 500, "type": "float",
        "optional": True,
        "notes": "INNER corner radius — the corner a tool must reach; floor "
        "= material min_internal_radius (316L: = wall); ceiling = a quarter "
        "of the smaller inner side. Omit to use the floor",
    },
    "material_id": {
        "unit": "materials.yaml key", "default": "basalt_slab",
        "min": None, "max": None, "type": "str",
        "notes": "drives mass calc + wall envelope + radius floor",
    },
}

BasinRectParams = make_params_model("BasinRectParams", PARAMETERS)


def validate(raw: dict[str, Any], materials: dict[str, Material] | None = None):
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []
    merged = merge_raw(PRIMITIVE_ID, PARAMETERS, raw, violations)
    try:
        params = BasinRectParams.model_validate(merged)
    except Exception as exc:
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    if params.floor_mm is None:
        params = params.model_copy(update={"floor_mm": params.wall_mm})
    material = check_material(PRIMITIVE_ID, params.material_id, materials, violations)
    if material is not None:
        check_wall_envelope("wall_mm", params.wall_mm, params.material_id,
                            material, violations)
        rad_floor = material.min_internal_radius_floor_mm(params.wall_mm)
        r = params.corner_radius_mm
        if r is None:
            r = float(rad_floor)
            params = params.model_copy(update={"corner_radius_mm": r})
        if r < rad_floor:
            violations.append(
                f"corner_radius_mm={r:g} < the {params.material_id} "
                f"internal-radius floor {rad_floor:g} mm (signed sheet "
                "§2.3; 316L floor = wall)"
            )
    inner_l = params.length_mm - 2 * params.wall_mm
    inner_w = params.width_mm - 2 * params.wall_mm
    if inner_l <= 0 or inner_w <= 0:
        violations.append(
            f"wall_mm={params.wall_mm:g} leaves no interior: inner = "
            f"{inner_l:g} x {inner_w:g} mm"
        )
    elif params.corner_radius_mm is not None:
        ceiling = min(inner_l, inner_w) / 4.0
        if params.corner_radius_mm > ceiling:
            violations.append(
                f"corner_radius_mm={params.corner_radius_mm:g} > a quarter "
                f"of the smaller inner side ({ceiling:g} mm) — the corners "
                "would consume the sides"
            )
    if params.floor_mm < params.wall_mm:
        violations.append(
            f"floor_mm={params.floor_mm:g} < wall_mm={params.wall_mm:g} — "
            "the floor carries the water load and must never be thinner "
            "than the wall"
        )
    if params.floor_mm >= params.height_mm:
        violations.append(
            f"floor_mm={params.floor_mm:g} >= height_mm="
            f"{params.height_mm:g} — no interior depth left"
        )
    if violations:
        raise ConstraintViolation(violations)
    return params


def _rounded_rect(half_l: float, half_w: float, r: float):
    """A closed rounded-rectangle profile, centred at the origin."""
    from build123d import Polyline, RadiusArc

    Polyline((-half_l + r, -half_w), (half_l - r, -half_w))
    RadiusArc((half_l - r, -half_w), (half_l, -half_w + r), r)
    Polyline((half_l, -half_w + r), (half_l, half_w - r))
    RadiusArc((half_l, half_w - r), (half_l - r, half_w), r)
    Polyline((half_l - r, half_w), (-half_l + r, half_w))
    RadiusArc((-half_l + r, half_w), (-half_l, half_w - r), r)
    Polyline((-half_l, half_w - r), (-half_l, -half_w + r))
    RadiusArc((-half_l, -half_w + r), (-half_l + r, -half_w), r)


def build(p):
    from build123d import Pos

    L2, W2 = p.length_mm / 2, p.width_mm / 2
    w, f, H = p.wall_mm, p.floor_mm, p.height_mm
    r_in = p.corner_radius_mm
    r_out = r_in + w

    outer = extrude_closed_profile(lambda: _rounded_rect(L2, W2, r_out), H)
    # Cavity cut with 1 mm overshoot above the rim (the bore pattern):
    cavity = extrude_closed_profile(
        lambda: _rounded_rect(L2 - w, W2 - w, r_in), H - f + 1.0
    )
    solid = outer - Pos(0, 0, f) * cavity
    solids = solid.solids()
    if len(solids) != 1:
        raise RuntimeError(
            f"basin_rect construction produced {len(solids)} solids, expected 1"
        )
    return solids[0]


def height_mm(p) -> float:
    return float(p.height_mm)


def anchors(p) -> dict[str, float | None]:
    return {"base": 0.0, "top": float(p.height_mm), "seat": float(p.floor_mm)}


def max_outer_diameter_mm(p) -> float:
    """Circumscribed diagonal — honest for fit checks (never understates)."""
    return float((p.length_mm ** 2 + p.width_mm ** 2) ** 0.5)


def inner_diameter_mm(p) -> float | None:
    return None


def stack_top_annulus_mm(p) -> None:
    return None  # not a stack parent in C1 (rect rim vs circular seat model)


def base_annulus_mm(p) -> tuple[float, float]:
    """Inscribed circle of the rect footprint (ADR-055): the conservative
    seat — a false refusal is loud, an overstated seat would be silent."""
    return float(min(p.length_mm, p.width_mm)), 0.0
