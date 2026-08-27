"""stepped_monolith — a solid stack of shrinking rectangular steps
(Phase 6 slice C1, ADR-055).

Each step above the first is EMBEDDED into the one below by the material
joint floor — the internal analogue of the assembly interference rule
(ADR-029/032): stacked boxes that merely touch are a face-tangency the
fuse cannot be trusted with; sunk boxes fuse robustly. Solid throughout —
the monolith IS the mass; the computed max_lift_kg driver is its check.

Coordinate system: Z up, origin at the centre of the base face.
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

PRIMITIVE_ID = "stepped_monolith"
PURPOSE = "solid stack of shrinking rectangular steps (ziggurat mass)"
CAN_PARENT_STACK = True    # the top step is a real flat face
CAN_PARENT_INSERT = False

SEGMENTATION_MODE = "planar_grid"   # a continuous mass: saw planes
                                    # cut real, fabricable modules
PARAMETERS: dict[str, dict[str, Any]] = {
    "base_length_mm": {
        "unit": "mm", "default": 1200, "min": 300, "max": 3000,
        "type": "float", "notes": "bottom step length",
    },
    "base_width_mm": {
        "unit": "mm", "default": 1200, "min": 300, "max": 3000,
        "type": "float", "notes": "bottom step width",
    },
    "steps": {
        "unit": "count", "default": 3, "min": 2, "max": 7, "type": "int",
        "notes": "one step is a plinth, eight reads as stairs (ADR-055 "
        "taxonomy)",
    },
    "step_height_mm": {
        "unit": "mm", "default": 300, "min": 100, "max": 800,
        "type": "float", "notes": "uniform height per step",
    },
    "step_inset_mm": {
        "unit": "mm", "default": None, "min": 3, "max": 750, "type": "float",
        "optional": True,
        "notes": "each side steps in by this; floor = the material joint "
        "floor (an inset below the §2.1 tolerance stack disappears in "
        "fabrication); ceiling keeps a real top face. Omit for "
        "max(50, floor)",
    },
    "material_id": {
        "unit": "materials.yaml key", "default": "basalt_slab",
        "min": None, "max": None, "type": "str",
        "notes": "drives mass calc + the inset/embed floors",
    },
}

SteppedMonolithParams = make_params_model("SteppedMonolithParams", PARAMETERS)


def validate(raw: dict[str, Any], materials: dict[str, Material] | None = None):
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []
    merged = merge_raw(PRIMITIVE_ID, PARAMETERS, raw, violations)
    try:
        params = SteppedMonolithParams.model_validate(merged)
    except Exception as exc:
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    material = check_material(PRIMITIVE_ID, params.material_id, materials, violations)
    if material is not None:
        floor = float(material.joint_overlap_mm)
        inset = params.step_inset_mm
        if inset is None:
            inset = max(50.0, floor)
            params = params.model_copy(update={"step_inset_mm": inset})
        if inset < floor:
            violations.append(
                f"step_inset_mm={inset:g} < the {params.material_id} joint "
                f"floor {floor:g} mm (signed sheet §2.1) — a step edge "
                "inside the tolerance stack disappears in fabrication"
            )
        shorter = min(params.base_length_mm, params.base_width_mm)
        top = shorter - 2 * (params.steps - 1) * inset
        if top < 100.0:
            violations.append(
                f"top face = {shorter:g} - 2x{params.steps - 1}x{inset:g} = "
                f"{top:g} mm < 100 mm — fewer steps, a smaller inset, or a "
                "bigger base"
            )
    if violations:
        raise ConstraintViolation(violations)
    return params


def build(p):
    from build123d import Box, Pos

    embed = 0.0
    solid = None
    mat = load_materials()[p.material_id]
    embed_mm = float(mat.joint_overlap_mm)
    for i in range(int(p.steps)):
        length = p.base_length_mm - 2 * i * p.step_inset_mm
        width = p.base_width_mm - 2 * i * p.step_inset_mm
        z_lo = i * p.step_height_mm - (embed_mm if i > 0 else 0.0)
        z_hi = (i + 1) * p.step_height_mm
        h = z_hi - z_lo
        box = Pos(0, 0, z_lo + h / 2) * Box(length, width, h)
        solid = box if solid is None else solid + box
    solids = solid.solids()
    if len(solids) != 1:
        raise RuntimeError(
            f"stepped_monolith construction produced {len(solids)} solids, "
            "expected 1"
        )
    return solids[0]


def height_mm(p) -> float:
    return float(p.steps * p.step_height_mm)


def anchors(p) -> dict[str, float | None]:
    return {"base": 0.0, "top": height_mm(p), "seat": None}


def max_outer_diameter_mm(p) -> float:
    return float((p.base_length_mm ** 2 + p.base_width_mm ** 2) ** 0.5)


def inner_diameter_mm(p) -> float | None:
    return None


def _top_dims(p) -> tuple[float, float]:
    k = 2 * (p.steps - 1) * p.step_inset_mm
    return float(p.base_length_mm - k), float(p.base_width_mm - k)


def stack_top_annulus_mm(p) -> tuple[float, float]:
    """Inscribed circle of the TOP step (conservative, ADR-055)."""
    tl, tw = _top_dims(p)
    return min(tl, tw), 0.0


def base_annulus_mm(p) -> tuple[float, float]:
    """Inscribed circle of the base footprint (conservative, ADR-055)."""
    return float(min(p.base_length_mm, p.base_width_mm)), 0.0
