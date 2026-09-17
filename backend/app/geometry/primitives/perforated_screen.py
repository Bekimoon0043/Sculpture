"""perforated_screen — a flat or single-curved perforated 316L sheet screen
(MS-A1, the first mesh-class primitive: the perforated-skin class of
mesh-look sculpture — a continuous sheet pierced by a hole grid, NOT an
open wire lattice).

316L-only, like freeform_loop (owner ruling pattern): the screen is cut and
press-formed from stainless_316l_sheet stock; every other process refuses
by name. Mass is COMPLETE — volume x 8000 kg/m3, no armature, no hidden
inputs (the sheet is self-supporting as a formed skin bounded by the
curvature floors below).

Coordinate system (base.py convention): origin at the centre of the base
face, axis Z — the panel stands vertically, height along Z, developed
width along X, sheet thickness along Y. For the curved panel the "centre
of the base face" reads as the midpoint of the base chord: the arc bulges
toward +Y, symmetric about the YZ plane, so the flat panel (curvature
None) is exactly the R -> infinity limit of the same convention.

Floors and their provenance:
  * sheet_thickness_mm — the 316L wall envelope via check_wall_envelope
    (3..20 mm, materials.yaml / ADR-027).
  * ligament = hole_pitch_mm - hole_size_mm >= sheet_thickness_mm —
    the materials.yaml min_feature = wall formula rule: a cut feature
    cannot be thinner than the sheet. Same rule as hole_size_mm >= t.
  * edge_margin_mm >= sheet_thickness_mm — the border strip is a formed
    edge, not a cut feature, but a margin thinner than the sheet cannot
    be held flat in the press (judgement, recorded).
  * curvature_radius_mm >= 5 x sheet_thickness_mm — rolled-sheet forming
    judgement, recorded: 316L springback on a roll tighter than about
    five gauges no longer settles to a stable cylinder.
  * arc_width_mm <= 2π x curvature_radius_mm x 0.75 — at most a 270°
    wrap; beyond that the "screen" closes on itself and is no longer a
    screen (definition, not an engineering limit).
  * stock: arc_width_mm <= stock length, height_mm <= stock width, read
    from the material's stock_size_mm (never hardcoded).
  * total holes <= MAX_TOTAL_HOLES — a MEASURED build-time/render-load
    bound, not a design preference (D-25 context: dense free-form
    tessellation already times out renders on this hardware).

Build: all hole cutters are fused into ONE compound tool and subtracted
in a SINGLE boolean (bounded build time — one BOP operation, not one per
hole). Returns ONE watertight solid; deterministic (the protocol's seed
is accepted by the registry but this construction is pure arithmetic —
the seed is unused).
"""

from __future__ import annotations

import math
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
)

PRIMITIVE_ID = "perforated_screen"
PURPOSE = ("flat or single-curved perforated 316L sheet screen — the "
           "perforated-skin class of mesh-look sculpture, not an open "
           "wire lattice")
CAN_PARENT_STACK = True       # the top edge strip is a thin but real seat
CAN_PARENT_INSERT = False

SEGMENTATION_MODE = "planar_grid"   # a continuous mass: saw planes
                                    # cut real, fabricable modules

SUPPORTED_MATERIAL = "stainless_316l_sheet"

#: Total-hole build cap: a MEASURED build-time/render-load bound (one fused
#: tool + one boolean stays well under the sandbox timeout at this density;
#: the tessellation/render path is the real limit — D-25 context: dense
#: free-form tessellation already times out renders on this hardware).
MAX_TOTAL_HOLES = 1500

#: Rolled-sheet forming judgement (recorded): 316L rolled tighter than
#: about five gauges springs back without settling to a stable cylinder.
MIN_CURVATURE_TIMES_THICKNESS = 5.0

#: At most a 270° wrap — beyond that the screen closes on itself.
MAX_ARC_WRAP_FRACTION = 0.75

HOLE_SHAPES = ("circle", "hexagon")

PARAMETERS: dict[str, dict[str, Any]] = {
    "height_mm": {
        "unit": "mm", "default": 900, "min": 400, "max": 1500,
        "type": "float",
        "notes": "panel height along Z; binds the 316L stock sheet "
                 "WIDTH 1500 (materials.yaml stock_size_mm, checked "
                 "against the material, not hardcoded)",
    },
    "arc_width_mm": {
        "unit": "mm", "default": 1400, "min": 400, "max": 3000,
        "type": "float",
        "notes": "DEVELOPED (arc) length of the panel along X — the "
                 "flat-pattern width; binds the 316L stock sheet "
                 "LENGTH 3000 (stock_size_mm, read from the material)",
    },
    "sheet_thickness_mm": {
        "unit": "mm", "default": 6, "min": 3, "max": 20,
        "type": "float",
        "notes": "the 316L wall envelope (check_wall_envelope, ADR-027); "
                 "also the ligament and hole floors below (min_feature "
                 "= wall, materials.yaml)",
    },
    "curvature_radius_mm": {
        "unit": "mm", "default": None, "min": 100, "max": 50000,
        "type": "float", "optional": True,
        "notes": "None (default) = FLAT panel; else the cylinder radius "
                 "the panel wraps around, inner face at R, bulge +Y. "
                 "Floor 5 x sheet_thickness_mm (rolled-sheet forming "
                 "judgement, recorded); arc must stay <= 270° wrap",
    },
    "hole_shape": {
        "unit": "circle | hexagon", "default": "circle",
        "min": None, "max": None, "type": "str",
        "notes": "circle: hole_size_mm is the DIAMETER; hexagon: "
                 "hole_size_mm is the ACROSS-FLATS width",
    },
    "hole_pitch_mm": {
        "unit": "mm", "default": 40, "min": 10, "max": 200,
        "type": "float",
        "notes": "centre-to-centre grid pitch, both axes; the ligament "
                 "pitch - size must stay >= sheet_thickness_mm",
    },
    "hole_size_mm": {
        "unit": "mm", "default": 20, "min": 4, "max": 150,
        "type": "float",
        "notes": "circle: diameter; hexagon: across-flats. Floor = "
                 "sheet_thickness_mm (a cut feature cannot be thinner "
                 "than the sheet — materials.yaml min_feature = wall)",
    },
    "edge_margin_mm": {
        "unit": "mm", "default": 25, "min": 3, "max": 100,
        "type": "float",
        "notes": "border strip without holes, all four edges; floor = "
                 "sheet_thickness_mm (a margin thinner than the sheet "
                 "cannot be held flat in the press — judgement, "
                 "recorded)",
    },
    "material_id": {
        "unit": "materials.yaml key", "default": "stainless_316l_sheet",
        "min": None, "max": None, "type": "str",
        "notes": "ONLY stainless_316l_sheet — the screen is cut and "
                 "press-formed from 316L stock; every other process "
                 "refuses by name",
    },
}

PerforatedScreenParams = make_params_model(
    "PerforatedScreenParams", PARAMETERS)


# ---------------------------------------------------------------------------
# grid arithmetic (pure functions — validate and build read the same counts)
# ---------------------------------------------------------------------------

def grid_count(span_mm: float, margin_mm: float, pitch_mm: float) -> int:
    """Holes along one axis: the count whose extreme holes still clear the
    margins — max(1, floor((span - 2·margin + pitch)/pitch))."""
    return max(1, math.floor(
        (span_mm - 2.0 * margin_mm + pitch_mm) / pitch_mm))


def grid_counts(p) -> tuple[int, int]:
    return (grid_count(p.arc_width_mm, p.edge_margin_mm, p.hole_pitch_mm),
            grid_count(p.height_mm, p.edge_margin_mm, p.hole_pitch_mm))


def _arc_angle_rad(p) -> float:
    """Plan-view subtense of the curved panel (radians)."""
    return float(p.arc_width_mm) / float(p.curvature_radius_mm)


def hole_area_mm2(p) -> float:
    if p.hole_shape == "hexagon":
        # across-flats f: area = (√3/2)·f²
        return math.sqrt(3.0) / 2.0 * float(p.hole_size_mm) ** 2
    return math.pi * (float(p.hole_size_mm) / 2.0) ** 2


# ---------------------------------------------------------------------------
# cross-parameter constraints (one message per rule, real numbers)
# ---------------------------------------------------------------------------

def _margin_fit_violations(p) -> list[str]:
    """Constraint 3a: the grid must fit with margins in BOTH directions —
    the full hole must clear both edge margins on each axis."""
    violations: list[str] = []
    axes = (("arc width (X)", float(p.arc_width_mm)),
            ("height (Z)", float(p.height_mm)))
    for label, span in axes:
        usable = span - 2.0 * p.edge_margin_mm
        if usable < p.hole_size_mm:
            violations.append(
                f"perforation grid does not fit on the {label} axis: "
                f"{span:g} - 2 x edge_margin_mm {p.edge_margin_mm:g} = "
                f"{usable:g} mm < hole_size_mm {p.hole_size_mm:g} — the "
                "hole would break the border strip")
    return violations


def _holes_cap_violation(p) -> str | None:
    """Constraint 3b: the measured build-time/render-load bound."""
    nx, ny = grid_counts(p)
    total = nx * ny
    if total > MAX_TOTAL_HOLES:
        return (
            f"hole grid too dense: nx {nx} x ny {ny} = {total} holes > "
            f"the {MAX_TOTAL_HOLES} cap (a measured build-time/"
            "render-load bound — dense free-form tessellation already "
            "times out renders on this hardware, D-25 context) — "
            "enlarge hole_pitch_mm or shrink the panel")
    return None


def _curvature_violations(p) -> list[str]:
    violations: list[str] = []
    if p.curvature_radius_mm is None:
        return violations
    r = float(p.curvature_radius_mm)
    t = float(p.sheet_thickness_mm)
    r_floor = MIN_CURVATURE_TIMES_THICKNESS * t
    if r < r_floor:
        violations.append(
            f"curvature_radius_mm {r:g} < {MIN_CURVATURE_TIMES_THICKNESS:g} "
            f"x sheet_thickness_mm {t:g} = {r_floor:g} mm — rolled-sheet "
            "forming judgement (recorded): 316L rolled tighter than "
            "about five gauges springs back without settling to a "
            "stable cylinder")
    wrap_limit = 2.0 * math.pi * r * MAX_ARC_WRAP_FRACTION
    if p.arc_width_mm > wrap_limit:
        violations.append(
            f"arc_width_mm {p.arc_width_mm:g} > 2π x curvature_radius_mm "
            f"{r:g} x {MAX_ARC_WRAP_FRACTION:g} = {wrap_limit:.0f} mm — "
            f"the panel would wrap more than "
            f"{MAX_ARC_WRAP_FRACTION * 360:g}° "
            f"({MAX_ARC_WRAP_FRACTION:g} of a full turn), closing on "
            "itself; it is no longer a screen")
    return violations


def _stock_violation(p, material: Material | None) -> str | None:
    if material is None:
        return None
    stock = material.stock_size_mm
    if stock is None:
        return (f"{p.material_id} declares no stock sheet "
                "(stock_size_mm null) — a screen must be cut from "
                "declared stock")
    problems = []
    if p.arc_width_mm > stock.length:
        problems.append(
            f"arc_width_mm {p.arc_width_mm:g} exceeds the stock sheet "
            f"LENGTH {stock.length:g} mm")
    if p.height_mm > stock.width:
        problems.append(
            f"height_mm {p.height_mm:g} exceeds the stock sheet WIDTH "
            f"{stock.width:g} mm")
    if problems:
        return (f"{p.material_id} stock_size_mm "
                f"{stock.length:g} x {stock.width:g} mm: "
                + "; ".join(problems)
                + " (materials.yaml stock, read from the material — "
                  "a larger screen needs a seam, which is not this "
                  "primitive)")
    return None


def validate(raw: dict[str, Any], materials: dict[str, Material] | None = None):
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []
    merged = merge_raw(PRIMITIVE_ID, PARAMETERS, raw, violations)
    try:
        params = PerforatedScreenParams.model_validate(merged)
    except Exception as exc:
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    material = check_material(
        PRIMITIVE_ID, params.material_id, materials, violations)

    # 316L-only: the screen is cut and press-formed from 316L stock.
    # Everything else refuses by name (the floors below are 316L
    # formulas, so there is nothing honest to check against another
    # material — same pattern as freeform_loop).
    if params.material_id != SUPPORTED_MATERIAL:
        violations.append(
            f"material_id={params.material_id!r} is not supported by "
            f"{PRIMITIVE_ID}: only {SUPPORTED_MATERIAL!r} (cut and "
            "press-formed 316L sheet) is implemented — perforated "
            f"screens in any other material are UNBUILT "
            "(FABRICATOR-INPUT-REQUIRED)")
        raise ConstraintViolation(violations)

    if material is not None:
        check_wall_envelope(
            "sheet_thickness_mm", params.sheet_thickness_mm,
            params.material_id, material, violations)

    if params.hole_shape not in HOLE_SHAPES:
        violations.append(
            f"hole_shape={params.hole_shape!r} is not a supported "
            f"perforation: only {', '.join(HOLE_SHAPES)}")

    t = float(params.sheet_thickness_mm)
    if params.edge_margin_mm < t:
        violations.append(
            f"edge_margin_mm={params.edge_margin_mm:g} < "
            f"sheet_thickness_mm {t:g} — the border strip is formed, "
            "not cut, and a margin thinner than the sheet cannot be "
            "held flat in the press (judgement, recorded)")

    ligament = float(params.hole_pitch_mm) - float(params.hole_size_mm)
    if ligament < t:
        violations.append(
            f"ligament = hole_pitch_mm {params.hole_pitch_mm:g} - "
            f"hole_size_mm {params.hole_size_mm:g} = {ligament:g} mm < "
            f"sheet_thickness_mm {t:g} mm — a cut feature cannot be "
            "thinner than the sheet (materials.yaml min_feature = wall "
            f"for {params.material_id})")
    if params.hole_size_mm < t:
        violations.append(
            f"hole_size_mm={params.hole_size_mm:g} < sheet_thickness_mm "
            f"{t:g} — the perforation must be at least one sheet "
            "thickness (materials.yaml min_feature = wall: a cut "
            "feature cannot be thinner than the sheet)")

    violations.extend(_margin_fit_violations(params))
    cap = _holes_cap_violation(params)
    if cap:
        violations.append(cap)
    violations.extend(_curvature_violations(params))
    stock = _stock_violation(params, material)
    if stock:
        violations.append(stock)

    if violations:
        raise ConstraintViolation(violations)
    return params


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def _refuse(detail: str) -> None:
    """A failed construction stage is a DETERMINISTIC, LOUD refusal (the
    normal ConstraintViolation path), never a silent no-op boolean (the
    ADR-064 empty-boolean class) and never a bare 500."""
    raise ConstraintViolation(
        [f"perforated_screen construction refused: {detail}"])


def _panel_solid(p):
    """The un-perforated sheet: flat rectangular prism, or a vertical
    annular sector (inner face at R, thickness outward, arc length =
    arc_width_mm, bulge +Y, base-chord midpoint at the origin).

    Both are watertight BY CONSTRUCTION (base.py Rule 6 argument): the
    flat panel is a closed box; the curved panel is a closed XZ profile
    revolved about Z by exactly the arc subtense."""
    from build123d import Box, Pos, Polyline, BuildSketch, BuildLine, Plane, \
        make_face, revolve, Axis, Rot

    h = float(p.height_mm)
    t = float(p.sheet_thickness_mm)
    if p.curvature_radius_mm is None:
        return Pos(0, 0, h / 2.0) * Box(
            float(p.arc_width_mm), t, h)

    r = float(p.curvature_radius_mm)
    theta_deg = math.degrees(_arc_angle_rad(p))
    with BuildSketch(Plane.XZ) as sketch:
        with BuildLine():
            Polyline((r, 0), (r + t, 0), (r + t, h), (r, h), close=True)
        make_face()
    sector = revolve(sketch.sketch, Axis.Z, revolution_arc=theta_deg)
    # The revolve starts at +X and runs CCW; centre the sector on +Y so
    # the base chord midpoint lands at the origin (the flat panel is the
    # R -> infinity limit of the same convention).
    return Rot(0, 0, 90.0 - theta_deg / 2.0) * sector


def _cutter(p, origin, normal):
    """One through-hole cutter: a prism along the local sheet normal,
    longer than the sheet, centred on the hole position. Circle holes
    are cylinders (hole_size = diameter); hexagon holes are hexagonal
    prisms built on the across-flats width (circumradius = f/√3)."""
    from build123d import Circle, Plane, RegularPolygon, extrude

    t = float(p.sheet_thickness_mm)
    overshoot = max(2.0, 0.5 * t)   # [J] each side: clears both faces
    length = t + 2.0 * overshoot
    nx, ny, nz = normal
    ox, oy, oz = origin
    plane = Plane(
        origin=(ox - nx * length / 2.0, oy - ny * length / 2.0,
                oz - nz * length / 2.0),
        z_dir=normal,
        x_dir=(0.0, 0.0, 1.0),   # plane x-axis vertical: deterministic
                                 # hole orientation on flat and curved
    )
    if p.hole_shape == "hexagon":
        across_flats = float(p.hole_size_mm)
        face = plane * RegularPolygon(
            across_flats / math.sqrt(3.0), side_count=6)
    else:
        face = plane * Circle(float(p.hole_size_mm) / 2.0)
    return extrude(face, amount=length)


def _hole_grid(p) -> list[tuple[float, float, tuple[float, float, float]]]:
    """(surface coordinate s along the developed width, z, outward normal)
    per hole, grid centred in the panel."""
    nx, ny = grid_counts(p)
    pitch = float(p.hole_pitch_mm)
    h = float(p.height_mm)
    points = []
    for i in range(nx):
        s = (i - (nx - 1) / 2.0) * pitch
        for j in range(ny):
            z = h / 2.0 + (j - (ny - 1) / 2.0) * pitch
            if p.curvature_radius_mm is None:
                points.append((s, z, (0.0, 1.0, 0.0)))
            else:
                phi = s / float(p.curvature_radius_mm)
                normal = (math.sin(phi), math.cos(phi), 0.0)
                points.append((s, z, normal))
    return points


def build(p):
    from build123d import Compound, Pos

    panel = _panel_solid(p)
    if len(panel.solids()) != 1 or float(panel.volume) <= 0.0:
        _refuse(
            f"panel produced {len(panel.solids())} solids, volume "
            f"{float(panel.volume):.1f} mm3 — expected one positive "
            "solid")

    t = float(p.sheet_thickness_mm)
    if p.curvature_radius_mm is None:
        mid_radius = 0.0
    else:
        mid_radius = float(p.curvature_radius_mm) + t / 2.0

    cutters = []
    for s, z, normal in _hole_grid(p):
        if mid_radius == 0.0:
            origin = (s, 0.0, z)
        else:
            origin = (mid_radius * normal[0], mid_radius * normal[1], z)
        cutters.append(_cutter(p, origin, normal))

    # ONE boolean: every cutter in a single compound tool, subtracted in
    # a single BOP operation — bounded build time however many holes the
    # grid carries (a per-hole boolean loop is the unbounded version).
    tool = Compound(children=cutters)
    pierced = panel - tool

    parts = pierced.solids()
    if len(parts) != 1 or float(pierced.volume) <= 0.0:
        _refuse(
            f"perforation left {len(parts)} solids, volume "
            f"{float(pierced.volume):.1f} mm3 — expected one pierced "
            "sheet (a silent empty boolean is the ADR-064 class)")
    v_panel = float(panel.volume)
    v_pierced = float(pierced.volume)
    removed = v_panel - v_pierced
    nx, ny = grid_counts(p)
    expected = nx * ny * hole_area_mm2(p) * t
    if removed <= 0.0 or abs(removed - expected) / expected > 0.02:
        _refuse(
            f"perforation removed {removed:.0f} mm3 vs the grid's "
            f"theoretical {expected:.0f} mm3 ({nx} x {ny} holes, dev "
            "> 2%) — a boolean defect, not geometry")
    return parts[0]


# ---------------------------------------------------------------------------
# protocol surface
# ---------------------------------------------------------------------------

def height_mm(p) -> float:
    return float(p.height_mm)


def anchors(p) -> dict[str, float | None]:
    return {"base": 0.0, "top": float(p.height_mm), "seat": None}


def max_outer_diameter_mm(p) -> float:
    """Widest footprint extent — the pattern of the flat primitives
    (water_wall, ADR-055): the diagonal of the footprint rectangle, the
    maximum distance between any two points of the plan outline. Flat:
    the footprint is arc_width x thickness. Curved: the plan outline is
    an annular sector whose extreme points are 2·(R + t) apart at the
    outer radius."""
    t = float(p.sheet_thickness_mm)
    if p.curvature_radius_mm is None:
        return float((p.arc_width_mm ** 2 + t ** 2) ** 0.5)
    return 2.0 * (float(p.curvature_radius_mm) + t)


def inner_diameter_mm(p) -> float | None:
    return None


def _base_inscribed_diameter_mm(p) -> float:
    """Inscribed circle of the plan footprint (conservative, ADR-055).
    Flat: min(arc_width, thickness). Curved: the narrowest corridor of
    the annular sector — the radial thickness and the inner-arc chord.
    This is why the screen stacks on a thin seat: a sheet's footprint
    IS its thickness."""
    t = float(p.sheet_thickness_mm)
    if p.curvature_radius_mm is None:
        return min(float(p.arc_width_mm), t)
    chord = 2.0 * float(p.curvature_radius_mm) * math.sin(
        _arc_angle_rad(p) / 2.0)
    return min(chord, t)


def base_annulus_mm(p) -> tuple[float, float]:
    return _base_inscribed_diameter_mm(p), 0.0


def stack_top_annulus_mm(p) -> tuple[float, float]:
    """The top edge strip is congruent with the base footprint."""
    return _base_inscribed_diameter_mm(p), 0.0
