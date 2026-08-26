"""basin_round — a round tub basin (Phase 6 slice A1, ADR-032).

The first standalone basin: outer cylinder wall + floor in ONE closed
revolved profile (the cascade basin's proven construction, Rule 6 —
watertight by construction), with the floor thickness split from the wall:
the floor carries the water load and may be THICKER than the wall, never
thinner (hard constraint 8, signed envelope sheet §3.1).

Coordinate system: Z up, origin at the centre of the base face.

Hard constraints (every violation carries the real numbers):
  2. wall_mm inside the material's wall envelope (ADR-027)
  7. min_clearance_mm >= the material's fall-gap floor (ADR-029) — this is
     the clearance the basin PROMISES to anything inserted into it; the
     assembler enforces it against the actual inserted child.
  8. floor_mm >= wall_mm (floor carries the water load)
  geometric integrity: wall must leave an interior (2*wall < diameter),
     floor must leave a basin (floor < height).
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
)

PRIMITIVE_ID = "basin_round"
PURPOSE = "round tub basin: cylindrical wall + load-bearing floor, one revolved solid"
CAN_PARENT_STACK = True      # the rim is a real annular face
CAN_PARENT_INSERT = True     # the interior seats columns/sculpture

PARAMETERS: dict[str, dict[str, Any]] = {
    "diameter_mm": {
        "unit": "mm",
        "default": 2600,
        "min": 400,
        "max": 6000,
        "type": "float",
        "notes": "outer diameter (inherits the cascade basin range)",
    },
    "height_mm": {
        "unit": "mm",
        "default": 450,
        "min": 200,
        "max": 900,
        "type": "float",
        "notes": "outer height (inherits the cascade basin range)",
    },
    "wall_mm": {
        "unit": "mm",
        "default": 20,
        "min": 3,
        "max": 300,
        "type": "float",
        "notes": "wall thickness; material envelope applies (ADR-027, "
        "hard constraint 2)",
    },
    "floor_mm": {
        "unit": "mm",
        "default": None,
        "min": 3,
        "max": 400,
        "type": "float",
        "optional": True,
        "notes": "floor thickness; omit to use wall_mm. May be thicker than "
        "the wall (it carries the water load), never thinner — hard "
        "constraint 8: floor_mm >= wall_mm",
    },
    "min_clearance_mm": {
        "unit": "mm",
        "default": 100,
        "min": 20,
        "max": 1000,
        "type": "float",
        "notes": "DIAMETRAL clearance this basin promises around anything "
        "inserted into it (radial gap is half); per-material floor applies "
        "(ADR-029, hard constraint 7)",
    },
    "material_id": {
        "unit": "materials.yaml key",
        "default": "basalt_slab",
        "min": None,
        "max": None,
        "type": "str",
        "notes": "drives mass calc + wall envelope + clearance floor",
    },
}

BasinRoundParams = make_params_model("BasinRoundParams", PARAMETERS)


def validate(
    raw: dict[str, Any],
    materials: dict[str, Material] | None = None,
):
    """Ranges + hard constraints; floor_mm's derived default resolved here."""
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []
    merged = merge_raw(PRIMITIVE_ID, PARAMETERS, raw, violations)

    try:
        params = BasinRoundParams.model_validate(merged)
    except Exception as exc:
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    if params.floor_mm is None:
        params = params.model_copy(update={"floor_mm": params.wall_mm})

    material = check_material(PRIMITIVE_ID, params.material_id, materials, violations)
    if material is not None:
        # --- hard constraint 2 ------------------------------------------------
        check_wall_envelope(
            "wall_mm", params.wall_mm, params.material_id, material, violations
        )
        # --- hard constraint 7 (the promise this basin makes to inserts) -----
        if params.min_clearance_mm < material.min_clearance_mm:
            violations.append(
                f"min_clearance_mm={params.min_clearance_mm:g} < material "
                f"minimum {material.min_clearance_mm:g} mm for "
                f"{params.material_id} ({material.name}) — "
                f"{params.min_clearance_mm / 2:g} mm radial is below the "
                f"{material.min_clearance_mm / 2:g} mm this material is "
                "built to (materials.yaml, ADR-029)"
            )

    # --- hard constraint 8: the floor carries the water load -----------------
    if params.floor_mm < params.wall_mm:
        violations.append(
            f"floor_mm={params.floor_mm:g} < wall_mm={params.wall_mm:g} — "
            "the floor carries the water load and must never be thinner "
            "than the wall (hard constraint 8, signed envelope sheet §3.1)"
        )

    # --- geometric integrity: a basin must have an interior ------------------
    inner = params.diameter_mm - 2 * params.wall_mm
    if inner <= 0:
        violations.append(
            f"wall_mm={params.wall_mm:g} leaves no interior: inner diameter "
            f"= {params.diameter_mm:g} - 2x{params.wall_mm:g} = {inner:g} mm"
        )
    if params.floor_mm >= params.height_mm:
        violations.append(
            f"floor_mm={params.floor_mm:g} >= height_mm={params.height_mm:g} "
            "— the floor would fill the basin (no interior depth left)"
        )

    if violations:
        raise ConstraintViolation(violations)
    return params


def build(p):
    """Tub: outer cylinder wall + floor, one closed revolved profile."""
    from build123d import Polyline

    R = p.diameter_mm / 2
    H = p.height_mm
    w = p.wall_mm
    f = p.floor_mm

    def draw() -> None:
        Polyline(
            (0, 0),
            (R, 0),
            (R, H),
            (R - w, H),
            (R - w, f),
            (0, f),
            close=True,
        )

    solid = revolve_closed_profile(draw)
    solids = solid.solids()
    if len(solids) != 1:
        raise RuntimeError(
            f"basin_round construction produced {len(solids)} solids, expected 1"
        )
    return solids[0]


def height_mm(p) -> float:
    return float(p.height_mm)


def anchors(p) -> dict[str, float | None]:
    """seat = top of the floor: where an inserted child stands."""
    return {"base": 0.0, "top": float(p.height_mm), "seat": float(p.floor_mm)}


def max_outer_diameter_mm(p) -> float:
    return float(p.diameter_mm)


def inner_diameter_mm(p) -> float | None:
    return float(p.diameter_mm - 2 * p.wall_mm)


def stack_top_annulus_mm(p) -> tuple[float, float]:
    """(outer, inner) diameter of the rim face a child stands on (ADR-053)."""
    return float(p.diameter_mm), float(p.diameter_mm - 2 * p.wall_mm)


def base_annulus_mm(p) -> tuple[float, float]:
    """The floor spans the whole base: a full disc (ADR-053)."""
    return float(p.diameter_mm), 0.0
