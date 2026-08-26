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
    # --- slice B rim treatments (ADR-054): drawn INTO the revolved profile
    # --- as Polyline+RadiusArc segments (ADR-010), never a post-hoc boolean.
    "rim_treatment": {
        "unit": "enum",
        "default": "none",
        "min": None,
        "max": None,
        "type": "str",
        "notes": "rim cross-section: none | weir_edge (360° spill crest with "
        "drip lip — requires a hydraulic_network weir node at the crest "
        "elevation) | coping (overhanging cap) | pool_edge (bullnose)",
    },
    "crest_radius_mm": {
        "unit": "mm",
        "default": None,
        "min": 3,
        "max": 300,
        "type": "float",
        "optional": True,
        "notes": "weir_edge only: internal arc pulling the sheet onto the "
        "crest; floor = material min_internal_radius (316L: = wall). Omit "
        "to use that floor",
    },
    "drip_edge_mm": {
        "unit": "mm",
        "default": None,
        "min": 3,
        "max": 20,
        "type": "float",
        "optional": True,
        "notes": "weir_edge only: square drip lip (overhang + groove) so the "
        "sheet detaches cleanly; floor = max(3, joint_overlap/3) per "
        "material, ceiling wall_mm/3",
    },
    "coping_overhang_mm": {
        "unit": "mm",
        "default": None,
        "min": 10,
        "max": 100,
        "type": "float",
        "optional": True,
        "notes": "coping only: outward overhang of the cap; 100 mm ceiling "
        "until a cantilever check exists (ADR-054, judgement). Omit for 40",
    },
    "coping_thickness_mm": {
        "unit": "mm",
        "default": None,
        "min": 20,
        "max": 150,
        "type": "float",
        "optional": True,
        "notes": "coping only: cap thickness, floor max(min_feature, 20); "
        "adds to the element's overall height. Omit to use the floor",
    },
    "pool_edge_radius_mm": {
        "unit": "mm",
        "default": None,
        "min": 3,
        "max": 150,
        "type": "float",
        "optional": True,
        "notes": "pool_edge only: bullnose radius on BOTH rim edges; must "
        "stay inside wall_mm/2 and at or above min_feature/2. Omit for the "
        "largest legal radius",
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

    # --- slice B rim treatments (ADR-054) ------------------------------------
    treatment = params.rim_treatment
    if treatment not in ("none", "weir_edge", "coping", "pool_edge"):
        violations.append(
            f"rim_treatment={treatment!r} — must be one of none, weir_edge, "
            "coping, pool_edge"
        )
        treatment = "none"
    _OWNER = {
        "crest_radius_mm": "weir_edge",
        "drip_edge_mm": "weir_edge",
        "coping_overhang_mm": "coping",
        "coping_thickness_mm": "coping",
        "pool_edge_radius_mm": "pool_edge",
    }
    for pname, owner in _OWNER.items():
        if getattr(params, pname) is not None and treatment != owner:
            violations.append(
                f"{pname} is set but rim_treatment={treatment!r} — treatment "
                f"parameters belong to their treatment; set "
                f"rim_treatment={owner!r} or drop the parameter"
            )

    if material is not None and treatment == "weir_edge":
        w, mid = params.wall_mm, params.material_id
        rad_floor = material.min_internal_radius_floor_mm(w)
        feat_floor = material.min_feature_floor_mm(w)
        cr = params.crest_radius_mm
        if cr is None:
            cr = float(rad_floor)
        dv_floor = max(3.0, material.joint_overlap_mm / 3.0)
        dv_ceiling = min(20.0, w / 3.0)
        dv = params.drip_edge_mm
        if dv is None:
            dv = max(5.0, dv_floor)
        params = params.model_copy(
            update={"crest_radius_mm": cr, "drip_edge_mm": dv}
        )
        if cr < rad_floor:
            violations.append(
                f"crest_radius_mm={cr:g} < the {mid} internal-radius floor "
                f"{rad_floor:g} mm (signed sheet §2.3; 316L floor = wall)"
            )
        if cr > w:
            violations.append(
                f"crest_radius_mm={cr:g} > wall_mm={w:g} — the crest arc "
                "must fit inside the wall"
            )
        if dv < dv_floor or dv > dv_ceiling:
            violations.append(
                f"drip_edge_mm={dv:g} outside [{dv_floor:g}..{dv_ceiling:g}] "
                f"for {mid} (floor max(3, joint_overlap/3); ceiling "
                "wall_mm/3 — a drip lip is a projecting feature)"
            )
        land = w + dv - cr
        if land < feat_floor:
            violations.append(
                f"weir crest land = wall {w:g} + drip {dv:g} - crest radius "
                f"{cr:g} = {land:g} mm < the {mid} feature floor "
                f"{feat_floor:g} mm — widen the wall, shrink the crest "
                "radius, or grow the drip edge"
            )
    elif material is not None and treatment == "coping":
        feat_floor = material.min_feature_floor_mm(params.wall_mm)
        ov = params.coping_overhang_mm
        if ov is None:
            ov = 40.0
        tcap = params.coping_thickness_mm
        if tcap is None:
            tcap = max(float(feat_floor), 20.0)
        params = params.model_copy(
            update={"coping_overhang_mm": ov, "coping_thickness_mm": tcap}
        )
        if not (10.0 <= ov <= 100.0):
            violations.append(
                f"coping_overhang_mm={ov:g} outside [10..100] — below 10 the "
                "overhang is inside fabrication tolerance; above 100 an "
                "unreinforced stone cantilever needs the structural check "
                "that does not exist yet (ADR-054)"
            )
        floor_t = max(float(feat_floor), 20.0)
        if not (floor_t <= tcap <= 150.0):
            violations.append(
                f"coping_thickness_mm={tcap:g} outside [{floor_t:g}..150] "
                f"for {params.material_id} (floor max(min_feature, 20))"
            )
    elif material is not None and treatment == "pool_edge":
        w = params.wall_mm
        feat_floor = material.min_feature_floor_mm(w)
        r_floor = max(3.0, float(feat_floor) / 2.0)
        r = params.pool_edge_radius_mm
        if r is None:
            r = min(w / 2.0, max(3.0, r_floor))
        params = params.model_copy(update={"pool_edge_radius_mm": r})
        if r > w / 2.0:
            violations.append(
                f"pool_edge_radius_mm={r:g} > wall_mm/2 = {w / 2:g} — the "
                "bullnose must live inside the wall's half-thickness"
            )
        if r < r_floor:
            violations.append(
                f"pool_edge_radius_mm={r:g} < {r_floor:g} mm (max(3, "
                f"min_feature/2) for {params.material_id}) — smaller is "
                "grinding noise, not a profile"
            )

    if violations:
        raise ConstraintViolation(violations)
    return params


def build(p):
    """Tub: outer cylinder wall + floor, one closed revolved profile.

    Slice B (ADR-054): the rim treatments are alternative rim cross-sections
    of the SAME closed profile — Polyline + RadiusArc, revolved (ADR-010).
    ``rim_treatment == "none"`` draws the identical six-point profile the
    slice inherited, byte-for-byte (pinned in tests and the gate).
    """
    from build123d import Polyline, RadiusArc

    R = p.diameter_mm / 2
    H = p.height_mm
    w = p.wall_mm
    f = p.floor_mm
    t = p.rim_treatment

    if t == "weir_edge":
        cr = p.crest_radius_mm
        dv = p.drip_edge_mm

        def draw() -> None:
            # Up the outer face to the drip groove, out onto the lip, over
            # the crest land, then the internal crest arc onto the inner
            # face. The internal corner at (R, H-dv) is a DELIBERATE sharp
            # arris — a drip needs one to shed the sheet (ADR-054).
            Polyline(
                (0, 0),
                (R, 0),
                (R, H - dv),
                (R + dv, H - dv),
                (R + dv, H),
                (R - w + cr, H),
            )
            RadiusArc((R - w + cr, H), (R - w, H - cr), cr)
            Polyline((R - w, H - cr), (R - w, f), (0, f), (0, 0))

    elif t == "coping":
        ov = p.coping_overhang_mm
        tc = p.coping_thickness_mm

        def draw() -> None:
            # Cap overhanging outward; its underside at H is the drip gap.
            Polyline(
                (0, 0),
                (R, 0),
                (R, H),
                (R + ov, H),
                (R + ov, H + tc),
                (R - w, H + tc),
                (R - w, f),
                (0, f),
                close=True,
            )

    elif t == "pool_edge":
        r = p.pool_edge_radius_mm

        def draw() -> None:
            # Bullnose: quarter arcs on BOTH rim edges, flat land between.
            Polyline((0, 0), (R, 0), (R, H - r))
            RadiusArc((R, H - r), (R - r, H), r)
            Polyline((R - r, H), (R - w + r, H))
            RadiusArc((R - w + r, H), (R - w, H - r), r)
            Polyline((R - w, H - r), (R - w, f), (0, f), (0, 0))

    else:

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
    """Overall height; coping adds its cap thickness (ADR-054)."""
    if p.rim_treatment == "coping":
        return float(p.height_mm + p.coping_thickness_mm)
    return float(p.height_mm)


def anchors(p) -> dict[str, float | None]:
    """seat = top of the floor: where an inserted child stands."""
    return {"base": 0.0, "top": height_mm(p), "seat": float(p.floor_mm)}


def max_outer_diameter_mm(p) -> float:
    if p.rim_treatment == "weir_edge":
        return float(p.diameter_mm + 2 * p.drip_edge_mm)
    if p.rim_treatment == "coping":
        return float(p.diameter_mm + 2 * p.coping_overhang_mm)
    return float(p.diameter_mm)


def inner_diameter_mm(p) -> float | None:
    return float(p.diameter_mm - 2 * p.wall_mm)


def stack_top_annulus_mm(p) -> tuple[float, float]:
    """(outer, inner) diameter of the rim face a child stands on (ADR-053).

    Treatments reshape the rim, so the honest seat changes with them
    (ADR-054): the weir lip and crest arc, the coping's wider cap, the
    bullnose's shrunken flat land."""
    d, w = float(p.diameter_mm), float(p.wall_mm)
    if p.rim_treatment == "weir_edge":
        return d + 2 * p.drip_edge_mm, d - 2 * w + 2 * p.crest_radius_mm
    if p.rim_treatment == "coping":
        return d + 2 * p.coping_overhang_mm, d - 2 * w
    if p.rim_treatment == "pool_edge":
        return d - 2 * p.pool_edge_radius_mm, d - 2 * w + 2 * p.pool_edge_radius_mm
    return d, d - 2 * w


def base_annulus_mm(p) -> tuple[float, float]:
    """The floor spans the whole base: a full disc (ADR-053)."""
    return float(p.diameter_mm), 0.0
