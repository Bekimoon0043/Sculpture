"""sculptural_column — a standalone monumental column (Phase 6 slice A1,
ADR-032).

Solid or hollow cylinder/frustum. Unlike the cascade's central column (a
core inside a basin, capped at 600 mm) this is a standalone monumental
element — the diameter ceiling is 1200 mm (signed sheet §3.3).

Taper narrows the column UPWARD (the stated diameter is at the BASE; the
top shrinks by height*tan(taper)) — a column tapers toward its capital,
the mirror of the plinth's spread toward the ground.

Exactly one of two hollowing routes, never both:
  * wall_mm > 0  — a hollow SHELL (open tube), the mass lever;
  * bore_mm > 0  — a plumbing service void DRILLED through a solid column,
    which must keep a full material-minimum wall around the bore at the
    column's NARROWEST point (the top, under taper) — the cascade's hard
    constraint 4 generalised.

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

PRIMITIVE_ID = "sculptural_column"
PURPOSE = "standalone solid/hollow column or tapered shaft, optional plumbing bore"
CAN_PARENT_STACK = True      # the capital face carries stacked elements
CAN_PARENT_INSERT = False

PARAMETERS: dict[str, dict[str, Any]] = {
    "diameter_mm": {
        "unit": "mm",
        "default": 200,
        "min": 80,
        "max": 1200,
        "type": "float",
        "notes": "BASE diameter; min inherits the cascade column floor, max "
        "raised 600 -> 1200 for monumental standalone use (signed sheet §3.3)",
    },
    "height_mm": {
        "unit": "mm",
        "default": 1200,
        "min": 300,
        "max": 6000,
        "type": "float",
        "notes": "monumental range (signed sheet §3.3)",
    },
    "wall_mm": {
        "unit": "mm",
        "default": 0,
        "min": 0,
        "max": 300,
        "type": "float",
        "notes": "0 = solid; otherwise a hollow shell inside the material's "
        "wall envelope (ADR-027). Mutually exclusive with bore_mm",
    },
    "bore_mm": {
        "unit": "mm",
        "default": 0,
        "min": 0,
        "max": 150,
        "type": "float",
        "notes": "0 = none; otherwise a plumbing service void (25..150 mm) "
        "drilled through a SOLID column. Mutually exclusive with wall_mm",
    },
    "taper_deg": {
        "unit": "deg",
        "default": 0,
        "min": 0,
        "max": 15,
        "type": "float",
        "notes": "sides lean inward toward the TOP by this angle from "
        "vertical; the column must keep a real section at the top",
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

SculpturalColumnParams = make_params_model("SculpturalColumnParams", PARAMETERS)


def top_diameter_mm(p) -> float:
    """Top diameter shrinks from the base by the taper over the height."""
    return float(p.diameter_mm - 2 * taper_radius_delta_mm(p.height_mm, p.taper_deg))


def validate(
    raw: dict[str, Any],
    materials: dict[str, Material] | None = None,
):
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []
    merged = merge_raw(PRIMITIVE_ID, PARAMETERS, raw, violations)

    try:
        params = SculpturalColumnParams.model_validate(merged)
    except Exception as exc:
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    material = check_material(PRIMITIVE_ID, params.material_id, materials, violations)

    d_top = top_diameter_mm(params)
    if d_top <= 0:
        violations.append(
            f"taper_deg={params.taper_deg:g} over height_mm="
            f"{params.height_mm:g} consumes the whole section: top diameter "
            f"= {params.diameter_mm:g} - 2x"
            f"{taper_radius_delta_mm(params.height_mm, params.taper_deg):g} "
            f"= {d_top:g} mm"
        )

    if params.wall_mm != 0 and params.bore_mm != 0:
        violations.append(
            f"wall_mm={params.wall_mm:g} and bore_mm={params.bore_mm:g} are "
            "mutually exclusive: a hollow shell (wall_mm) IS the void — "
            "drill a bore only through a solid column"
        )

    if params.wall_mm != 0:
        if params.wall_mm < 3:
            violations.append(
                f"wall_mm={params.wall_mm:g} — a hollow column wall must be "
                "0 (solid) or >= 3 mm (the platform wall floor)"
            )
        elif material is not None:
            check_wall_envelope(
                "wall_mm", params.wall_mm, params.material_id, material, violations
            )
        inner_top = d_top - 2 * params.wall_mm
        if d_top > 0 and inner_top <= 0:
            violations.append(
                f"wall_mm={params.wall_mm:g} leaves no interior at the top: "
                f"inner diameter = {d_top:g} - 2x{params.wall_mm:g} = "
                f"{inner_top:g} mm — use wall_mm=0 for a solid column"
            )

    if params.bore_mm != 0:
        if params.bore_mm < 25:
            violations.append(
                f"bore_mm={params.bore_mm:g} — a plumbing bore must be 0 "
                "(none) or 25..150 mm (inherits the cascade bore range)"
            )
        # hard constraint 4 generalised: a full material-minimum wall must
        # survive around the bore at the NARROWEST point (the top).
        if material is not None and d_top > 0:
            remaining = (d_top - params.bore_mm) / 2
            if remaining < material.min_wall_mm:
                violations.append(
                    f"bore_mm={params.bore_mm:g} leaves a "
                    f"{remaining:g} mm wall at the column top (top diameter "
                    f"{d_top:g}), below the {material.min_wall_mm:g} mm "
                    f"material minimum for {params.material_id} "
                    f"({material.name}) — the column must keep a full wall "
                    "around the plumbing bore (hard constraint 4)"
                )

    if violations:
        raise ConstraintViolation(violations)
    return params


def build(p):
    """Frustum (solid) or annular shell; bore cut through with overshoot."""
    from build123d import Cylinder, Polyline, Pos

    Rb = p.diameter_mm / 2
    Rt = top_diameter_mm(p) / 2
    H = p.height_mm
    w = p.wall_mm

    def draw_solid() -> None:
        Polyline((0, 0), (Rb, 0), (Rt, H), (0, H), close=True)

    def draw_hollow() -> None:
        Polyline((Rb, 0), (Rt, H), (Rt - w, H), (Rb - w, 0), close=True)

    solid = revolve_closed_profile(draw_solid if w == 0 else draw_hollow)
    if p.bore_mm != 0:
        # 1 mm overshoot both ends so the cut never leaves a skin face.
        solid -= Pos(0, 0, H / 2) * Cylinder(p.bore_mm / 2, H + 2.0)

    solids = solid.solids()
    if len(solids) != 1:
        raise RuntimeError(
            f"sculptural_column construction produced {len(solids)} solids, "
            "expected 1"
        )
    return solids[0]


def height_mm(p) -> float:
    return float(p.height_mm)


def anchors(p) -> dict[str, float | None]:
    return {"base": 0.0, "top": float(p.height_mm), "seat": None}


def max_outer_diameter_mm(p) -> float:
    return float(p.diameter_mm)   # widest at the base (taper narrows upward)


def inner_diameter_mm(p) -> float | None:
    return None


def stack_top_annulus_mm(p) -> tuple[float, float]:
    """(outer, inner) diameter of the capital face (ADR-053)."""
    top = top_diameter_mm(p)
    if p.wall_mm != 0:
        return top, top - 2 * float(p.wall_mm)
    if p.bore_mm != 0:
        return top, float(p.bore_mm)
    return top, 0.0


def base_annulus_mm(p) -> tuple[float, float]:
    """(outer, inner) diameter of the base footprint (ADR-053)."""
    if p.wall_mm != 0:
        return float(p.diameter_mm), float(p.diameter_mm - 2 * p.wall_mm)
    if p.bore_mm != 0:
        return float(p.diameter_mm), float(p.bore_mm)
    return float(p.diameter_mm), 0.0
