"""plinth — a solid or hollow pedestal frustum (Phase 6 slice A1, ADR-032).

The base a basin, sculpture or column stands on. Solid by default; hollow
(wall_mm > 0) is the real mass lever — the signed envelope sheet's worked
example: a 1.0 m dia x 1.0 m basalt plinth is 2,121 kg solid but 1,252 kg
hollow at a 180 mm wall (41% less), which is the difference between failing
and passing a 2,000 kg max_lift_kg. The constraint message names hollowing,
so the design conversation is about hollowing rather than shrinking.

Taper widens the plinth DOWNWARD (the top diameter is the stated parameter;
the base grows by height*tan(taper)) — a pedestal spreads toward the ground.
Wall thickness is measured horizontally; at the 15° taper ceiling that is
within 3.5% of the true normal thickness, inside every material envelope's
granularity.

Taxonomy bounds (signed sheet §3.2, definitions rather than engineering
limits): taller than 1.5 m it is a column, not a plinth; steeper than 15°
it reads as a cone/monolith (a slice-C primitive).

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
    load_materials,
    make_params_model,
    merge_raw,
    revolve_closed_profile,
    taper_radius_delta_mm,
)

PRIMITIVE_ID = "plinth"
PURPOSE = "solid or hollow pedestal frustum; the base other elements stack on"
CAN_PARENT_STACK = True
CAN_PARENT_INSERT = False    # no floor to seat an insert on (hollow = open tube)

SEGMENTATION_MODE = "planar_grid"   # a continuous mass: saw planes
                                    # cut real, fabricable modules
PARAMETERS: dict[str, dict[str, Any]] = {
    "top_diameter_mm": {
        "unit": "mm",
        "default": 900,
        "min": 200,
        "max": 3000,
        "type": "float",
        "notes": "top face diameter — below 200 it is a boss, above 3000 "
        "it is a basin (signed sheet §3.2)",
    },
    "height_mm": {
        "unit": "mm",
        "default": 600,
        "min": 100,
        "max": 1500,
        "type": "float",
        "notes": "taxonomy bound: taller than 1.5 m it is a column, not a "
        "plinth (definition, not an engineering limit)",
    },
    "wall_mm": {
        "unit": "mm",
        "default": 0,
        "min": 0,
        "max": 300,
        "type": "float",
        "notes": "0 = solid; otherwise a hollow shell inside the material's "
        "wall envelope (ADR-027). Hollowing is the real mass lever against "
        "max_lift_kg (signed sheet §4.2)",
    },
    "taper_deg": {
        "unit": "deg",
        "default": 0,
        "min": 0,
        "max": 15,
        "type": "float",
        "notes": "sides lean outward toward the BASE by this angle from "
        "vertical; beyond 15° it reads as a cone/monolith (slice C)",
    },
    "material_id": {
        "unit": "materials.yaml key",
        "default": "basalt_slab",
        "min": None,
        "max": None,
        "type": "str",
        "notes": "drives mass calc + wall envelope",
    },
}

PlinthParams = make_params_model("PlinthParams", PARAMETERS)


def base_diameter_mm(p) -> float:
    """Base diameter grows from the top by the taper over the height."""
    return float(p.top_diameter_mm + 2 * taper_radius_delta_mm(p.height_mm, p.taper_deg))


def validate(
    raw: dict[str, Any],
    materials: dict[str, Material] | None = None,
):
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []
    merged = merge_raw(PRIMITIVE_ID, PARAMETERS, raw, violations)

    try:
        params = PlinthParams.model_validate(merged)
    except Exception as exc:
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    material = check_material(PRIMITIVE_ID, params.material_id, materials, violations)

    # wall: 0 = solid, else the material envelope (hard constraint 2).
    if params.wall_mm != 0:
        if params.wall_mm < 3:
            violations.append(
                f"wall_mm={params.wall_mm:g} — a hollow plinth wall must be "
                "0 (solid) or >= 3 mm (the platform wall floor); values "
                "between are not fabricable shells"
            )
        elif material is not None:
            check_wall_envelope(
                "wall_mm", params.wall_mm, params.material_id, material, violations
            )
        # a hollow shell must leave a hole: the TOP is the narrowest section
        inner_top = params.top_diameter_mm - 2 * params.wall_mm
        if inner_top <= 0:
            violations.append(
                f"wall_mm={params.wall_mm:g} leaves no interior at the top: "
                f"inner diameter = {params.top_diameter_mm:g} - "
                f"2x{params.wall_mm:g} = {inner_top:g} mm — use wall_mm=0 "
                "for a solid plinth"
            )

    if violations:
        raise ConstraintViolation(violations)
    return params


def build(p):
    """Frustum (solid) or annular shell (hollow), one revolved profile."""
    from build123d import Polyline

    Rt = p.top_diameter_mm / 2
    Rb = base_diameter_mm(p) / 2
    H = p.height_mm
    w = p.wall_mm

    def draw_solid() -> None:
        Polyline((0, 0), (Rb, 0), (Rt, H), (0, H), close=True)

    def draw_hollow() -> None:
        Polyline((Rb, 0), (Rt, H), (Rt - w, H), (Rb - w, 0), close=True)

    solid = revolve_closed_profile(draw_solid if w == 0 else draw_hollow)
    solids = solid.solids()
    if len(solids) != 1:
        raise RuntimeError(
            f"plinth construction produced {len(solids)} solids, expected 1"
        )
    return solids[0]


def height_mm(p) -> float:
    return float(p.height_mm)


def anchors(p) -> dict[str, float | None]:
    return {"base": 0.0, "top": float(p.height_mm), "seat": None}


def max_outer_diameter_mm(p) -> float:
    return base_diameter_mm(p)


def inner_diameter_mm(p) -> float | None:
    return None


def stack_top_annulus_mm(p) -> tuple[float, float]:
    """(outer, inner) diameter of the stackable top face (ADR-053).

    Solid: a full disc. Hollow: the open tube's annular rim — which is why
    a child's seat width must be checked, not assumed."""
    if p.wall_mm == 0:
        return float(p.top_diameter_mm), 0.0
    return float(p.top_diameter_mm), float(p.top_diameter_mm - 2 * p.wall_mm)


def base_annulus_mm(p) -> tuple[float, float]:
    """(outer, inner) diameter of the base footprint (ADR-053)."""
    outer = base_diameter_mm(p)
    if p.wall_mm == 0:
        return outer, 0.0
    return outer, outer - 2 * float(p.wall_mm)
