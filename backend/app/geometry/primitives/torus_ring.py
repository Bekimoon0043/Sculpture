"""torus_ring — a solid torus resting on its base circle
(Phase 6 slice C1, ADR-055).

`major_diameter_mm` is the OUTER diameter (what a fabricator measures);
the centreline radius is (major − minor)/2. Self-intersection is refused
by arithmetic (major >= 2 x minor). A torus meets a flat seat on a
mathematically perfect LINE — the ADR-029 knife edge in the round — so it
exposes `base_annulus_at_overlap_mm`: the assembler computes the real
chord bearing 2·sqrt(overlap·(minor − overlap)) at the sunk depth and
holds it to the joint floor like any other seat.

Coordinate system: Z up, origin on the seat plane under the centre.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Material
from app.geometry.primitives.base import (
    ConstraintViolation,
    check_material,
    collect_model_errors,
    load_materials,
    make_params_model,
    merge_raw,
)

PRIMITIVE_ID = "torus_ring"
PURPOSE = "solid torus ring (halo/ring sculpture, overflow trough core)"
CAN_PARENT_STACK = False   # the top is a curve, not a face
CAN_PARENT_INSERT = False

SEGMENTATION_MODE = "planar_grid"   # a continuous mass: saw planes
                                    # cut real, fabricable modules
PARAMETERS: dict[str, dict[str, Any]] = {
    "major_diameter_mm": {
        "unit": "mm", "default": 1200, "min": 300, "max": 3000,
        "type": "float",
        "notes": "OUTER diameter; must be >= 2x the minor diameter or the "
        "torus self-intersects (arithmetic, ADR-055)",
    },
    "minor_diameter_mm": {
        "unit": "mm", "default": 200, "min": 60, "max": 600,
        "type": "float",
        "notes": "section diameter; 60 floor = a handleable cast/carved "
        "section (ADR-055, judgement)",
    },
    "material_id": {
        "unit": "materials.yaml key", "default": "basalt_slab",
        "min": None, "max": None, "type": "str",
        "notes": "drives mass calc + the seat's joint floor",
    },
}

TorusRingParams = make_params_model("TorusRingParams", PARAMETERS)


def validate(raw: dict[str, Any], materials: dict[str, Material] | None = None):
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []
    merged = merge_raw(PRIMITIVE_ID, PARAMETERS, raw, violations)
    try:
        params = TorusRingParams.model_validate(merged)
    except Exception as exc:
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    check_material(PRIMITIVE_ID, params.material_id, materials, violations)
    if params.major_diameter_mm < 2 * params.minor_diameter_mm:
        violations.append(
            f"major_diameter_mm={params.major_diameter_mm:g} < 2x "
            f"minor_diameter_mm ({2 * params.minor_diameter_mm:g}) — the "
            "torus would self-intersect at the axis"
        )
    if violations:
        raise ConstraintViolation(violations)
    return params


def _radii(p) -> tuple[float, float]:
    r = p.minor_diameter_mm / 2.0
    return (p.major_diameter_mm - p.minor_diameter_mm) / 2.0, r


def build(p):
    from build123d import Pos, Torus

    R, r = _radii(p)
    solid = Pos(0, 0, r) * Torus(R, r)
    solids = solid.solids()
    if len(solids) != 1:
        raise RuntimeError(
            f"torus_ring construction produced {len(solids)} solids, expected 1"
        )
    return solids[0]


def height_mm(p) -> float:
    return float(p.minor_diameter_mm)


def anchors(p) -> dict[str, float | None]:
    return {"base": 0.0, "top": float(p.minor_diameter_mm), "seat": None}


def max_outer_diameter_mm(p) -> float:
    return float(p.major_diameter_mm)


def inner_diameter_mm(p) -> float | None:
    return float(p.major_diameter_mm - 2 * p.minor_diameter_mm)


def stack_top_annulus_mm(p) -> None:
    return None


def base_annulus_mm(p) -> tuple[float, float]:
    """The un-sunk contact is a LINE: zero-width annulus on the centreline.
    Any stack_on that does not sink the torus is refused by the bearing
    floor — which is the point (ADR-055)."""
    R, _ = _radii(p)
    return 2 * R, 2 * R


def base_annulus_at_overlap_mm(p, overlap_mm: float) -> tuple[float, float]:
    """Chord bearing at the sunk depth: half-width sqrt(d·(minor − d))."""
    R, r = _radii(p)
    d = max(0.0, min(float(overlap_mm), 2 * r))
    half_chord = (d * (2 * r - d)) ** 0.5
    return 2 * R + 2 * half_chord, max(0.0, 2 * R - 2 * half_chord)
