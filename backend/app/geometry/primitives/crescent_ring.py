"""crescent_ring — a vertical partial-torus crescent (slice SC-A1).

The outer form of a mirror-polished "moon crescent" sculpture: a circular
arc SWEPT with a circular (or elliptically squashed) tube section, standing
upright — a partial torus. Construction: revolve the tube section about the
torus axis by exactly arc_span_deg, which IS the sweep (revolving an offset
closed section about an axis by a partial angle produces the identical
B-rep a section-along-arc sweep would; the analytic check below is the
swept-volume theory). Watertight BY CONSTRUCTION (base.py Rule 6 argument):
a closed section revolved about an axis it never touches is always a valid
closed solid. This mirrors torus_ring, which builds the full ring from the
native Torus solid rather than an explicit sweep.

Coordinate system (base.py convention): origin at the centre of the base
footprint, axis Z. The ring's centreline circle lies in the XZ vertical
plane, centred at (0, 0, centerline_radius + tube/2), so the tube's LOWEST
point (azimuth 270°) rests exactly at z = 0. Azimuths are measured from +X
toward +Z (CCW seen from +Y). The opening gap occupies azimuths
[gap_azimuth, gap_azimuth + (360 - arc_span)] CCW; the swept arc is the
complement, [gap_azimuth + (360 - arc_span), gap_azimuth + 360]. The tube's
axial direction is Y (depth): the depth extent is tube_diameter_mm.

The photo replica (the client reference piece, read at photo precision):
0.4 m deep x 1.9 m tall x 2.0 m long. Defaults R=800, tube=350, span=300,
gap=0 reproduce it: depth 350 mm (~0.4 m), height = 2R + tube = 1950 mm
(~1.9 m), length = 2R + tube = 1950 mm (the photo's "2.0 m" is the same
extent read to two figures — both axes span the full diameter when the
swept arc includes azimuths 90/180/270/360).

Materials — allowed set, everything else refuses by name (the owner-ruling
pattern of freeform_loop / perforated_screen):
  * stainless_316l_cast (materials.yaml, SC-A1) — cast or rolled-plate
    welded & mirror-polished 316L; the crescent's chunky tube is NOT formed
    sheet. PROVISIONAL fabricator-set envelope, tunable, not a standard
    citation (FABRICATOR-INPUT, flagged in materials.yaml).
  * stainless_316l_sheet — the formed-sheet envelope (3..20 mm): a slim
    crescent bent/rolled from heavy 316L plate within the sheet process.
tube_diameter_mm (and tube_depth_oval_mm when set) must sit inside the
CHOSEN material's wall envelope via check_wall_envelope, real numbers in
every message.

Derived quantities, never parameters:
  * height = top of the swept solid. For spans reaching the zenith
    (90° swept) it is exactly 2 x centerline_radius + tube_diameter;
    otherwise it is the top of the end-cap ellipse at whichever end face
    is higher (top_mm below computes it from the arc, never assumed).
  * length = 2R + tube_diameter when the swept arc includes both side
    azimuths (0° and 180°); the bounding box is the truth.

Mass is COMPLETE — volume x 8000 kg/m3, no armature, no hidden inputs (a
cast/welded stainless tube is self-supporting at these gauges; same
complete-mass declaration as torus_ring / perforated_screen).

Floors and their provenance:
  * the nadir rule: the swept arc MUST include azimuth 270° (inclusive) —
    otherwise the crescent floats above the base plane and the base-face
    origin convention (lowest tube point at z = 0) is a lie. Refused with
    the swept-arc numbers.
  * tube_depth_oval_mm < tube_diameter_mm — a "squash" at or above the
    tube diameter is not a squash (definition), and the vertical gauge
    must still clear the material wall envelope.
  * 2R + tube <= 5000 mm monumental scale: GUARANTEED by the static
    ranges (R max 1500, tube max 500 -> 2x1500 + 500 = 3500 < 5000), the
    same range-pinning convention as perforated_screen — pinned in the
    tests, no runtime check that can never fire.

Build-stage loud refusals (ADR-064 class, the perforated_screen pattern):
exactly one solid, positive volume, and swept volume vs analytic
torus-segment theory (V = section_area x 2πR x span/360) within 2% — a
silent empty boolean or a boolean defect is refused, never shipped.

The protocol's ``seed`` is accepted by the registry but unused: this
construction is pure arithmetic, deterministic by inspection.
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

PRIMITIVE_ID = "crescent_ring"
PURPOSE = ("vertical partial-torus crescent — the mirror-polished "
           "\"moon crescent\" sculpture class (arc swept with a tube "
           "section, standing on its lowest tube point)")
CAN_PARENT_STACK = False    # the top is a curved tube, not a face
CAN_PARENT_INSERT = False

SEGMENTATION_MODE = "planar_grid"   # a continuous mass: saw planes
                                    # cut real, fabricable modules

#: The allowed material set (owner-ruling pattern). Everything else is
#: refused by name with the two implemented processes listed.
SUPPORTED_MATERIALS = ("stainless_316l_cast", "stainless_316l_sheet")

#: Swept-volume theory tolerance (build-stage cross-check, ADR-064 class
#: refusal — identical role to the 2% perforation-removed check of
#: perforated_screen).
VOLUME_THEORY_TOLERANCE = 0.02

#: The nadir azimuth: the tube's lowest point sits here; the base-face
#: origin convention requires the swept arc to include it.
NADIR_AZIMUTH_DEG = 270.0

PARAMETERS: dict[str, dict[str, Any]] = {
    "centerline_radius_mm": {
        "unit": "mm", "default": 800, "min": 400, "max": 1500,
        "type": "float",
        "notes": "radius of the arc the tube sweeps along (the XZ "
                 "vertical plane). Range binds overall height "
                 "2R + tube <= 5000 mm monumental scale: the static "
                 "maxima give 2x1500 + 500 = 3500 < 5000 (guaranteed "
                 "by the ranges, pinned in the tests)",
    },
    "tube_diameter_mm": {
        "unit": "mm", "default": 350, "min": 80, "max": 500,
        "type": "float",
        "notes": "tube section gauge: the axial (Y, depth) diameter AND "
                 "the vertical diameter unless tube_depth_oval_mm is "
                 "set. This is the formed/cast WALL measure — must sit "
                 "inside the CHOSEN material's wall envelope "
                 "(check_wall_envelope, ADR-027): 3..500 cast, 3..20 "
                 "sheet. Depth extent of the sculpture = this number "
                 "(photo replica: 350 mm ~ 0.4 m deep)",
    },
    "arc_span_deg": {
        "unit": "deg", "default": 300, "min": 90, "max": 330,
        "type": "float",
        "notes": "the swept arc; the opening gap is its complement "
                 "(360 - span). 330 ~ the photo piece. The swept arc "
                 "must include the nadir azimuth 270 deg or the "
                 "crescent floats (the nadir rule, validated with real "
                 "numbers)",
    },
    "gap_azimuth_deg": {
        "unit": "deg", "default": 0, "min": 0, "max": 360,
        "type": "float",
        "notes": "azimuth where the opening gap STARTS, measured from "
                 "+X toward +Z (CCW seen from +Y); the gap occupies "
                 "[gap_azimuth, gap_azimuth + 360 - arc_span]. "
                 "Deterministic placement: gap 0 and gap 360 are the "
                 "same solid (pinned in the tests)",
    },
    "tube_depth_oval_mm": {
        "unit": "mm", "default": None, "min": 50, "max": 500,
        "type": "float", "optional": True,
        "notes": "None (default) = CIRCULAR section; else the vertical "
                 "squash: elliptical section with vertical axis = oval "
                 "and axial (depth) axis = tube_diameter_mm. Must stay "
                 "< tube_diameter_mm and inside the material wall "
                 "envelope (min wall included)",
    },
    "material_id": {
        "unit": "materials.yaml key", "default": "stainless_316l_cast",
        "min": None, "max": None, "type": "str",
        "notes": "ONLY stainless_316l_cast (cast/welded & polished) or "
                 "stainless_316l_sheet (formed heavy plate); every "
                 "other material refuses by name. Drives the wall "
                 "envelope the tube gauge is held to",
    },
}

CrescentRingParams = make_params_model("CrescentRingParams", PARAMETERS)


# ---------------------------------------------------------------------------
# derived geometry (pure functions — validate() and build() read the same
# numbers, and the tests pin these relationships)
# ---------------------------------------------------------------------------

def _semi_axes(p) -> tuple[float, float]:
    """(radial, axial) semi-axes of the tube section. The RADIAL axis
    (local torus-radial; vertical at the nadir and the zenith) takes the
    oval when set; the AXIAL axis (the Y depth direction everywhere) is
    always tube_diameter_mm / 2 — the depth extent is tube_diameter_mm."""
    radial = (p.tube_depth_oval_mm or p.tube_diameter_mm) / 2.0
    return radial, float(p.tube_diameter_mm) / 2.0


def _center_height_mm(p) -> float:
    """Z of the centreline circle's centre: R + radial semi-axis, so the
    tube's lowest point (nadir azimuth 270 deg) sits exactly at z = 0."""
    radial, _ = _semi_axes(p)
    return float(p.centerline_radius_mm) + radial


def _sweep_start_deg(p) -> float:
    """Azimuth where the swept arc begins (the gap's far edge)."""
    return (float(p.gap_azimuth_deg)
            + (360.0 - float(p.arc_span_deg))) % 360.0


def _arc_includes_deg(p, azimuth_deg: float) -> bool:
    """True when azimuth lies within the swept arc [start, start+span]
    (endpoints inclusive — an end exactly at the nadir still rests on the
    base plane, a point contact the joint floor refuses to seat on)."""
    start = _sweep_start_deg(p)
    return ((azimuth_deg - start) % 360.0) <= float(p.arc_span_deg) + 1e-9


def top_mm(p) -> float:
    """Top of the swept solid, computed from the arc — never assumed.

    At azimuth phi the surface reaches z = z_c + (R + radial) x sin(phi);
    the maximum over the swept arc is at the zenith (90 deg) when the arc
    includes it (height = 2R + tube_diameter for a circular section), else
    at whichever end face is higher — the top of that end-cap ellipse."""
    r = float(p.centerline_radius_mm)
    radial, _ = _semi_axes(p)
    start = _sweep_start_deg(p)
    end = (start + float(p.arc_span_deg)) % 360.0
    if _arc_includes_deg(p, 90.0):
        peak = 1.0
    else:
        peak = max(math.sin(math.radians(start)), math.sin(math.radians(end)))
    return _center_height_mm(p) + (r + radial) * peak


def length_mm(p) -> float:
    """Overall X extent when both side azimuths (0 deg and 180 deg) are
    swept: exactly 2R + tube_diameter for a circular section (2R + oval
    when squashed — the horizontal tube projection is the RADIAL
    semi-axis). Otherwise the wider of the end-cap positions. The
    bounding box in build() is the authoritative truth; this helper
    exists so the mapper/tests can pin the relationship."""
    r = float(p.centerline_radius_mm)
    radial, _ = _semi_axes(p)
    extent = 0.0
    for azimuth in (0.0, 180.0):
        if _arc_includes_deg(p, azimuth):
            extent = max(extent, r + radial)
    start = _sweep_start_deg(p)
    end = (start + float(p.arc_span_deg)) % 360.0
    for azimuth in (start, end):
        extent = max(extent, (r + radial)
                     * abs(math.cos(math.radians(azimuth))))
    return 2.0 * extent


def swept_volume_mm3(p) -> float:
    """Analytic torus-segment volume: section area x centreline arc
    length. Circular: pi x (tube/2)^2 x 2πR x span/360; elliptical:
    pi x (oval/2) x (tube/2) x 2πR x span/360."""
    r = float(p.centerline_radius_mm)
    radial, axial = _semi_axes(p)
    arc = 2.0 * math.pi * r * float(p.arc_span_deg) / 360.0
    return math.pi * radial * axial * arc


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def validate(raw: dict[str, Any], materials: dict[str, Material] | None = None):
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []

    # height is DERIVED, never a parameter — refuse it by name with the
    # relationship, before merge_raw's generic unknown-key message (which
    # still fires for any other unknown key).
    for key in ("height", "height_mm"):
        if key in raw:
            violations.append(
                f"{key!r} is DERIVED, never a parameter of {PRIMITIVE_ID}: "
                "height = 2 x centerline_radius_mm + tube_diameter_mm for "
                "spans reaching the zenith (the swept arc includes 90 deg); "
                "otherwise it is the top of the higher end-cap ellipse, "
                "computed from centerline_radius_mm, tube_diameter_mm and "
                "arc_span_deg — state those parameters, not height")

    merged = merge_raw(PRIMITIVE_ID, PARAMETERS, raw, violations)
    try:
        params = CrescentRingParams.model_validate(merged)
    except Exception as exc:
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    material = check_material(
        PRIMITIVE_ID, params.material_id, materials, violations)

    if params.material_id not in SUPPORTED_MATERIALS:
        violations.append(
            f"material_id={params.material_id!r} is not supported by "
            f"{PRIMITIVE_ID}: only {SUPPORTED_MATERIALS[0]!r} (cast/welded "
            f"& mirror-polished) and {SUPPORTED_MATERIALS[1]!r} (formed "
            "heavy plate) are implemented — crescent rings in any other "
            "material are UNBUILT (FABRICATOR-INPUT-REQUIRED)")

    if material is not None:
        check_wall_envelope(
            "tube_diameter_mm", params.tube_diameter_mm,
            params.material_id, material, violations)

    if params.tube_depth_oval_mm is not None:
        if params.tube_depth_oval_mm >= params.tube_diameter_mm:
            violations.append(
                f"tube_depth_oval_mm={params.tube_depth_oval_mm:g} must "
                f"stay < tube_diameter_mm {params.tube_diameter_mm:g} — "
                "the oval is a vertical SQUASH of the tube section; at or "
                "above the tube diameter it is not a squash")
        if material is not None:
            check_wall_envelope(
                "tube_depth_oval_mm", params.tube_depth_oval_mm,
                params.material_id, material, violations)

    # the nadir rule: the swept arc must include azimuth 270 deg or the
    # crescent floats and the base-face origin convention is false.
    if not _arc_includes_deg(params, NADIR_AZIMUTH_DEG):
        start = _sweep_start_deg(params)
        end = (start + float(params.arc_span_deg)) % 360.0
        violations.append(
            f"the opening gap covers the nadir azimuth "
            f"{NADIR_AZIMUTH_DEG:g} deg (swept arc runs "
            f"{start:g} deg -> {end:g} deg) — the crescent would float "
            "above the base plane: the base-face origin convention "
            "(lowest tube point at z = 0) requires the swept arc to "
            "include the nadir; move gap_azimuth_deg or widen "
            "arc_span_deg")

    if violations:
        raise ConstraintViolation(violations)
    return params


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def _refuse(detail: str) -> None:
    """A failed construction stage is a DETERMINISTIC, LOUD refusal (the
    normal ConstraintViolation path), never a silent no-op boolean (the
    ADR-064 empty-boolean class) and never a bare 500 — the
    perforated_screen pattern."""
    raise ConstraintViolation(
        [f"crescent_ring construction refused: {detail}"])


def build(p):
    from build123d import (
        Axis, BuildPart, BuildSketch, Circle, Ellipse, Locations, Plane,
        Pos, Rot, revolve,
    )

    r = float(p.centerline_radius_mm)
    radial, axial = _semi_axes(p)
    # The tube section in the plane containing the torus axis (local XZ;
    # local X radial, local Z axial), centred at (R, 0) — offset from the
    # axis so the revolve is a torus segment, never a sphere. Revolving
    # this closed section about the axis by arc_span_deg IS the sweep of
    # the section along the circular arc: identical B-rep, watertight by
    # construction (base.py Rule 6).
    with BuildSketch(Plane.XZ) as sketch:
        with Locations(Pos(r, 0)):
            if p.tube_depth_oval_mm is None:
                Circle(axial)
            else:
                Ellipse(radial, axial)
    with BuildPart() as part:
        revolve(sketch.sketch, Axis.Z, revolution_arc=float(p.arc_span_deg))
    seg = part.solids()[0]

    # Local -> world: local X (radial) -> world X; local Y (along the
    # arc) -> world Z; local Z (axial) -> world -Y (the depth axis). The
    # revolve sweeps the arc from local azimuth 0 CCW, which lands at
    # world azimuth 0 -> shift the start to gap + (360 - span).
    solid = Pos(0, 0, _center_height_mm(p)) * Rot(
        0, -_sweep_start_deg(p), 0) * Rot(90, 0, 0) * seg

    parts = solid.solids()
    if len(parts) != 1 or float(solid.volume) <= 0.0:
        _refuse(
            f"construction produced {len(parts)} solids, volume "
            f"{float(solid.volume):.1f} mm3 — expected one positive "
            "swept solid (a silent empty boolean is the ADR-064 class)")
    volume = float(solid.volume)
    theory = swept_volume_mm3(p)
    if abs(volume - theory) / theory > VOLUME_THEORY_TOLERANCE:
        _refuse(
            f"swept volume {volume:.0f} mm3 vs analytic torus-segment "
            f"theory {theory:.0f} mm3 (section area x 2πR x span/360, "
            f"dev > {VOLUME_THEORY_TOLERANCE:.0%}) — a boolean defect, "
            "not geometry")
    return parts[0]


# ---------------------------------------------------------------------------
# protocol surface
# ---------------------------------------------------------------------------

def height_mm(p) -> float:
    return top_mm(p)


def anchors(p) -> dict[str, float | None]:
    return {"base": 0.0, "top": top_mm(p), "seat": None}


def max_outer_diameter_mm(p) -> float:
    """Widest footprint extent — the pattern of the flat primitives
    (water_wall, ADR-055): the diagonal of the footprint rectangle, the
    maximum distance between any two points of the plan outline. The
    footprint is length_mm (X extent) x tube_diameter_mm (Y depth)."""
    footprint_depth = float(p.tube_diameter_mm)
    return float((length_mm(p) ** 2 + footprint_depth ** 2) ** 0.5)


def inner_diameter_mm(p) -> float | None:
    return None


def base_annulus_mm(p) -> tuple[float, float]:
    """The un-sunk contact is a POINT (the tube bottom at the nadir):
    zero-width annulus, the torus_ring precedent — any stack_on that
    does not sink the crescent is refused by the bearing floor, which is
    the point (ADR-055)."""
    return 0.0, 0.0


def base_annulus_at_overlap_mm(p, overlap_mm: float) -> tuple[float, float]:
    """Contact patch when the crescent is sunk overlap_mm into the
    parent's top face. The parent plane cuts the tube at depth d =
    overlap above the nadir bottom: a stadium patch whose extent ALONG
    the path is the chord 2 x sqrt(d x (2a - d)) (a = radial semi-axis)
    and across the depth 2 x (b/a) x sqrt(d x (2a - d)) >= the chord
    (b >= a always: oval <= tube). The chord is the patch's minor
    dimension — the honest seat width, conservative at every angle."""
    radial, _ = _semi_axes(p)
    d = max(0.0, min(float(overlap_mm), 2.0 * radial))
    half_chord = (d * (2.0 * radial - d)) ** 0.5
    return 2.0 * half_chord, 0.0
