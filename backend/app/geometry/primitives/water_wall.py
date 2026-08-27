"""water_wall — a freestanding spill wall (Phase 6 slice C1, ADR-055).

The thickness x height cross-section — including the ADR-054 weir crest
(internal crest arc, land, square drip lip) — is drawn as ONE closed
profile and extruded along the wall's length. Linear, not revolved, so
the slice-B axisymmetry limit does not apply here; the crest still obeys
the same signed floors.

The thickness floor is 3x the material's minimum VESSEL wall (ADR-055,
judgement): a freestanding cantilevered slab is not a supported vessel
wall, and no structural check exists yet to say otherwise. The operator
flagged nothing at sign-off; the number stands until corrected.

Coordinate system: Z up; the wall runs along Y, centred; the drip lip
overhangs the +X face; origin at the centre of the base face.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Material
from app.geometry.primitives.base import (
    ConstraintViolation,
    check_material,
    collect_model_errors,
    extrude_closed_profile,
    load_materials,
    make_params_model,
    merge_raw,
)

PRIMITIVE_ID = "water_wall"
PURPOSE = "freestanding spill wall with a weir crest along its length"
CAN_PARENT_STACK = False   # the top is a spill crest, not a seat
CAN_PARENT_INSERT = False

SEGMENTATION_MODE = "planar_grid"   # a continuous mass: saw planes
                                    # cut real, fabricable modules
#: 3x the ADR-027 vessel-wall floor (ADR-055 §5, judgement — the weakest
#: number in the slice, explicitly flagged for the operator's correction).
_THICKNESS_FLOOR_FACTOR = 3.0

PARAMETERS: dict[str, dict[str, Any]] = {
    "length_mm": {
        "unit": "mm", "default": 2400, "min": 500, "max": 6000,
        "type": "float", "notes": "run of the wall (extrusion length)",
    },
    "height_mm": {
        "unit": "mm", "default": 1800, "min": 600, "max": 3000,
        "type": "float",
        "notes": "crest height; above 3000 an unreinforced wall demands "
        "the structural review the platform does not do (ADR-055)",
    },
    "thickness_mm": {
        "unit": "mm", "default": None, "min": 9, "max": 600, "type": "float",
        "optional": True,
        "notes": "slab thickness; floor = 3x the material wall floor "
        "(basalt 60 / concrete 225 / bronze 18 / 316L 9 — ADR-055 "
        "judgement). Omit for max(floor, 100)",
    },
    "crest_radius_mm": {
        "unit": "mm", "default": None, "min": 3, "max": 300, "type": "float",
        "optional": True,
        "notes": "internal crest arc; floor = material min_internal_radius "
        "(ADR-054 pattern). Omit to use the floor",
    },
    "drip_edge_mm": {
        "unit": "mm", "default": None, "min": 3, "max": 20, "type": "float",
        "optional": True,
        "notes": "square drip lip on the spill face; floor max(3, "
        "joint_overlap/3), ceiling thickness/3 (ADR-054 pattern)",
    },
    "material_id": {
        "unit": "materials.yaml key", "default": "basalt_slab",
        "min": None, "max": None, "type": "str",
        "notes": "drives mass calc + every floor above",
    },
}

WaterWallParams = make_params_model("WaterWallParams", PARAMETERS)


def validate(raw: dict[str, Any], materials: dict[str, Material] | None = None):
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []
    merged = merge_raw(PRIMITIVE_ID, PARAMETERS, raw, violations)
    try:
        params = WaterWallParams.model_validate(merged)
    except Exception as exc:
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    material = check_material(PRIMITIVE_ID, params.material_id, materials, violations)
    if material is not None:
        t_floor = _THICKNESS_FLOOR_FACTOR * float(material.min_wall_mm)
        t = params.thickness_mm
        if t is None:
            t = max(t_floor, 100.0)
            params = params.model_copy(update={"thickness_mm": t})
        if t < t_floor:
            violations.append(
                f"thickness_mm={t:g} < {t_floor:g} mm (3x the "
                f"{params.material_id} vessel-wall floor "
                f"{material.min_wall_mm:g} — a freestanding slab, ADR-055 "
                "judgement)"
            )
        rad_floor = material.min_internal_radius_floor_mm(t)
        cr = params.crest_radius_mm
        if cr is None:
            cr = float(rad_floor)
        dv_floor = max(3.0, material.joint_overlap_mm / 3.0)
        dv_ceiling = min(20.0, t / 3.0)
        dv = params.drip_edge_mm
        if dv is None:
            dv = max(5.0, dv_floor)
        params = params.model_copy(
            update={"crest_radius_mm": cr, "drip_edge_mm": dv}
        )
        if cr < rad_floor:
            violations.append(
                f"crest_radius_mm={cr:g} < the {params.material_id} "
                f"internal-radius floor {rad_floor:g} mm (signed sheet §2.3)"
            )
        if cr > t:
            violations.append(
                f"crest_radius_mm={cr:g} > thickness_mm={t:g} — the crest "
                "arc must fit the slab"
            )
        if dv < dv_floor or dv > dv_ceiling:
            violations.append(
                f"drip_edge_mm={dv:g} outside [{dv_floor:g}..{dv_ceiling:g}]"
                f" for {params.material_id} (ADR-054 floors)"
            )
        feat = material.min_feature_floor_mm(t)
        land = t + dv - cr
        if land < feat:
            violations.append(
                f"crest land = thickness {t:g} + drip {dv:g} - crest radius "
                f"{cr:g} = {land:g} mm < the {params.material_id} feature "
                f"floor {feat:g} mm"
            )
    if violations:
        raise ConstraintViolation(violations)
    return params


def build(p):
    from build123d import Polyline, RadiusArc, Pos

    T, H, L = p.thickness_mm, p.height_mm, p.length_mm
    cr, dv = p.crest_radius_mm, p.drip_edge_mm

    def draw() -> None:
        # XZ section; the drip lip overhangs the +X (spill) face.
        Polyline((0, 0), (T, 0), (T, H - dv), (T + dv, H - dv),
                 (T + dv, H), (cr, H))
        RadiusArc((cr, H), (0, H - cr), cr)
        Polyline((0, H - cr), (0, 0))

    solid = extrude_closed_profile(draw, L, plane_name="XZ")
    solids = solid.solids()
    if len(solids) != 1:
        raise RuntimeError(
            f"water_wall construction produced {len(solids)} solids, expected 1"
        )
    # Centre the run on the origin whatever the extrude direction was.
    bb = solids[0].bounding_box()
    return Pos(-bb.min.X, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * solids[0]


def height_mm(p) -> float:
    return float(p.height_mm)


def anchors(p) -> dict[str, float | None]:
    return {"base": 0.0, "top": float(p.height_mm), "seat": None}


def max_outer_diameter_mm(p) -> float:
    return float((p.length_mm ** 2 + (p.thickness_mm + p.drip_edge_mm) ** 2) ** 0.5)


def inner_diameter_mm(p) -> float | None:
    return None


def stack_top_annulus_mm(p) -> None:
    return None  # never a stack parent: the top is a spill crest


def base_annulus_mm(p) -> tuple[float, float]:
    """Inscribed circle — the slab's thickness (conservative, ADR-055)."""
    return float(min(p.length_mm, p.thickness_mm)), 0.0
