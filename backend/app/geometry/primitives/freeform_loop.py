"""freeform_loop — the ref-08 class free-form sculpture (FF-A2, ADR-066).

A PRE-FABRICATION parametric free-form implementation: a hollow 316L
lens shell pierced by a walled window bore, standing on a thin 316L
interface plate. The construction is the owner-approved 2026-09-04
delta (hollow lens + walled window bore); the earlier tube-annulus
construction FAILED development and is preserved as evidence in
ADR-066 — it is not registered, not built, not capability.

Construction order (approved delta, verbatim):
  1. OUTER lens — one loft along the STRAIGHT vertical spine:
     [Vertex(base tip), N_STATIONS horizontal ellipse sections,
     Vertex(top tip)]. Width/depth per station from deterministic
     profiles; per-station y-offset = out-of-plane bow (wobble);
     per-station rotation = twist.
  2. CAVITY — the inner lens (sections drawn in by wall_mm, tips pulled
     in to where the profile supports a wall) MINUS the clearance
     cylinder (bore + wall_mm, full-through). Must be exactly one solid.
  3. M = OUTER − CAVITY — sealed hollow lens.
  4. M = M − bore cylinder — cuts the window; the cavity was built to
     stand clear of the bore corridor, and the MEASURED BRepExtrema
     bore-region wall (owner clarification 2, 2026-09-04) is the
     authoritative proof — it must be >= wall_mm − 0.5 mm or the gate
     FAILS. No exact-clearance claim is made from the construction
     alone.
  5. M = M + interface plate (thickness = wall_mm, embedment exactly
     EMBEDMENT_MM, ligament rules unchanged).

Topology contract (unchanged, operator-approved): 1 kernel solid,
1 through-opening, 2 boundary components, 1 sealed cavity, genus [1,1].

316L-only: the SELECTED PROTOTYPE MANUFACTURING HYPOTHESIS (owner
ruling — the reference photograph proves no material); all other
processes refuse by name (LIMITATIONS 22). wall_mm is a prototype
nominal gauge, never a "verified" wall: geometric_wall_measurement is
measured-or-NEEDS_INPUT (v4 rule) and fabrication_wall_approval /
forming_radius stay unresolved professional inputs.

Provenance tags: [owner] owner-ruling · [img] image-derived-estimate
(briefs/freeform_references/ref08_landmarks.json) · [mat]
materials.yaml 316L · [arith] derived arithmetic · [probe]
discovery-proven · [J] judgement.
"""

from __future__ import annotations

import math
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

PRIMITIVE_ID = "freeform_loop"
PURPOSE = ("ref-08 class free-form sculpture: hollow 316L lens with a "
           "walled window bore, PRE-FABRICATION only")
CAN_PARENT_STACK = False    # the top is a curved shell tip, not a face
CAN_PARENT_INSERT = False

SEGMENTATION_MODE = "planar_grid"

# FF-A1 (ADR-065) applicability declarations — these arm the
# incomplete-mass model and the freeform_integrity_v1 export gate.
REQUIRES_FREEFORM_INTEGRITY = True
INCOMPLETE_MASS_INPUTS = (
    "armature mass (FABRICATOR-INPUT-REQUIRED)",
    "armature centroid (FABRICATOR-INPUT-REQUIRED)",
    "per-module armature allocation (FABRICATOR-INPUT-REQUIRED)",
)

#: The explicit topology contract (operator-approved values, unchanged
#: by the lens delta): a sealed hollow lens whose window bore pierces
#: the OUTER component only (one handle), with the donut cavity sealed.
EXPECTED_TOPOLOGY: dict[str, Any] = {
    "kernel_solids": 1,
    "through_openings": 1,
    "boundary_components": 2,
    "closed_internal_cavities": 1,
    "per_component_genus": [1, 1],
    "per_component_euler": [0, 0],
    "accidental_extra_bodies_or_voids": 0,
}

SUPPORTED_MATERIAL = "stainless_316l_sheet"

EMBEDMENT_MM = 3.0          # [mat] 316L joint_overlap_mm — never tangent
MIN_LIGAMENT_MM = 3.0       # [mat] 316L min_wall_mm — real remaining wall
N_STATIONS = 21             # [J] lens loft stations along the vertical
                            # spine (loft's safe case — measured
                            # 2026-09-04: the failure mode was 3-D
                            # paths, not straight-spine stacking)
PROFILE_EXPONENT = 0.8      # [J] sin^p profile shape (p<1 fills the
                            # mid-body, sharpens the tips)
WOBBLE_HEIGHT_FRACTION_MAX = 0.25   # [owner v4] bow amplitude bound
WELD_MARGIN_MM = 20.0       # [mat] 316L min_clearance_mm as weld margin
BORE_CLEARANCE_MARGIN_MM = 0.5      # [J] corridor fit margin
BORE_LINER_EXTRA_MM = 2.0   # [J, measured 2026-09-04] growing an
                            # ellipse's semi-axes by wall_mm is NOT a
                            # parallel offset (owner clarification 2):
                            # the +wall corridor measured a 5.236 mm
                            # liner at the default 555x645 bore vs the
                            # 5.5 mm FAIL threshold; the corridor is
                            # therefore bore + wall + this allowance,
                            # and the MEASURED bore_region_min_mm stays
                            # the authoritative clearance.
WALL_MEASURE_TOL_MM = 0.5   # [mat provenance] the recorded ±0.5 mm/face
                            # 316L cut/form tolerance — also the bore
                            # clearance FAIL threshold (clarification 2)

PARAMETERS: dict[str, dict[str, Any]] = {
    "height_mm": {
        "unit": "mm", "default": 4250, "min": 3500, "max": 5000,
        "type": "float",
        "notes": "[owner] hard scale ruling 3.5-5.0 m, verbatim",
    },
    "width_mm": {
        "unit": "mm", "default": 2569, "min": 1680, "max": 3600,
        "type": "float",
        "notes": "[img x owner, arith] W/H band 0.48-0.72 x height "
                 "ruling; default (249/412) x 4250 = 2568.57",
    },
    "depth_mm": {
        "unit": "mm", "default": 900, "min": 300, "max": 1800,
        "type": "float",
        "notes": "[J] lens max depth (y extent) — NOT measurable from "
                 "the single reference photo (stated in "
                 "ref08_landmarks.json); range J, must stay <= width",
    },
    "wall_mm": {
        "unit": "mm", "default": 6, "min": 6, "max": 20,
        "type": "float",
        "notes": "prototype NOMINAL GAUGE from reference 01 — "
                 "not a verified wall, ever. Floor 6 = embedment 3 + "
                 "ligament 3 [arith, owner ruling]; ceiling 20 [mat]",
    },
    "section_twist_deg": {
        "unit": "deg", "default": 20, "min": -90, "max": 90,
        "type": "float",
        "notes": "[J] relative section rotation top vs bottom along the "
                 "vertical spine; direction landmark positive = CCW "
                 "viewed from above [img, direction only]",
    },
    "wobble_mm": {
        "unit": "mm", "default": 150, "min": -1250, "max": 1250,
        "type": "float",
        "notes": "[J] out-of-plane bow amplitude (y displacement of the "
                 "spine, zero at the tips), NOT twist; |wobble| <= 0.25 "
                 "x height enforced per combination [owner v4]",
    },
    "plan_skew_ratio": {
        "unit": "ratio", "default": 0.15, "min": -0.30, "max": 0.30,
        "type": "float",
        "notes": "[img +0.1466] the window bore's horizontal offset as "
                 "a fraction of width_mm (approved delta: this "
                 "parameter now drives the void-offset landmark "
                 "directly)",
    },
    "bore_width_mm": {
        "unit": "mm", "default": 1110, "min": 200, "max": 2000,
        "type": "float",
        "notes": "[img] window bore width; default 0.4337 x 2569 = "
                 "1114 -> 1110; corridor fit re-derived per "
                 "combination in validate()",
    },
    "bore_height_mm": {
        "unit": "mm", "default": 1290, "min": 200, "max": 2500,
        "type": "float",
        "notes": "[img] window bore height; default from measured void "
                 "aspect 0.864: 1110/0.864 = 1284 -> 1290",
    },
    "bore_center_height_fraction": {
        "unit": "ratio", "default": 0.485, "min": 0.25, "max": 0.75,
        "type": "float",
        "notes": "[img 0.4854] bore CENTER height as a fraction of "
                 "height_mm (renamed per owner clarification 1 — "
                 "bore_height_mm defines the size)",
    },
    "waist_height_fraction": {
        "unit": "ratio", "default": 0.45, "min": 0.25, "max": 0.65,
        "type": "float",
        "notes": "[J] height fraction of the widest lens station "
                 "(reference reads widest slightly below middle)",
    },
    "base_plate_diameter_mm": {
        "unit": "mm", "default": 600, "min": 150, "max": 1500,
        "type": "float",
        "notes": "[img-consistency 0.24 x width; ceiling J] thin "
                 "interface plate; floor = tip landing chord + weld "
                 "margin, derived per combination in validate()",
    },
    "material_id": {
        "unit": "materials.yaml key", "default": "stainless_316l_sheet",
        "min": None, "max": None, "type": "str",
        "notes": "ONLY stainless_316l_sheet — the selected prototype "
                 "manufacturing hypothesis (owner ruling); everything "
                 "else refuses (GRC and other processes are unbuilt)",
    },
}

FreeformLoopParams = make_params_model("FreeformLoopParams", PARAMETERS)

# Hard runtime landmark band (unchanged): every accepted combination
# must stay a ref-08-class envelope. The remaining bands are
# FIXTURE-FIDELITY checks, asserted by gate_ffa2_auto on the acceptance
# fixture only.
WIDTH_HEIGHT_BAND = (0.48, 0.72)    # [img +/-20%]


# ---------------------------------------------------------------------------
# deterministic profile functions (pure functions of z_tilde in [0, 1])
# ---------------------------------------------------------------------------

def _warp(z_tilde: float, waist: float) -> float:
    """Maps the height fraction so the profile peaks at the waist."""
    z_tilde = min(max(z_tilde, 0.0), 1.0)
    k = math.log(0.5) / math.log(waist)
    return z_tilde ** k


def half_width_mm(z_tilde: float, p) -> float:
    u = _warp(z_tilde, p.waist_height_fraction)
    return (p.width_mm / 2.0) * math.sin(math.pi * u) ** PROFILE_EXPONENT


def half_depth_mm(z_tilde: float, p) -> float:
    u = _warp(z_tilde, p.waist_height_fraction)
    return (p.depth_mm / 2.0) * math.sin(math.pi * u) ** PROFILE_EXPONENT


def _bow_mm(z_tilde: float, p) -> float:
    return p.wobble_mm * math.sin(math.pi * min(max(z_tilde, 0.0), 1.0))


def _twist_at(z_tilde: float, p) -> float:
    return p.section_twist_deg * (min(max(z_tilde, 0.0), 1.0) - 0.5)


def _lens_z_range(p) -> tuple[float, float]:
    """The lens spans plate_top − embedment .. height (world z, mm)."""
    return (p.wall_mm - EMBEDMENT_MM, float(p.height_mm))


def _profile_crossing(p, target_hw: float, rising: bool) -> float:
    """z_tilde where half_width crosses target (bisection, 60 iters —
    deterministic). ``rising`` = the lower crossing."""
    lo, hi = (0.0, p.waist_height_fraction) if rising else (
        p.waist_height_fraction, 1.0)
    for _ in range(60):
        mid = (lo + hi) / 2.0
        val = half_width_mm(mid, p)
        if rising:
            if val < target_hw:
                lo = mid
            else:
                hi = mid
        else:
            if val < target_hw:
                hi = mid
            else:
                lo = mid
    return (lo + hi) / 2.0


def bore_center_mm(p) -> tuple[float, float]:
    """(x, z) of the window bore centre in world mm."""
    z_lo, z_hi = _lens_z_range(p)
    return (p.plan_skew_ratio * p.width_mm,
            z_lo + p.bore_center_height_fraction * (z_hi - z_lo))


def landing_footprint_mm(p) -> float:
    """Silhouette chord of the lens tip at the embedment depth."""
    z_lo, z_hi = _lens_z_range(p)
    zt = EMBEDMENT_MM / (z_hi - z_lo)
    return 2.0 * half_width_mm(zt, p)


def plate_diameter_floor_mm(p) -> float:
    return landing_footprint_mm(p) + 2.0 * WELD_MARGIN_MM


def _corridor_fit_violation(p) -> str | None:
    """The bore corridor (bore + wall, at the skew offset) must sit
    inside the INNER lens silhouette with a margin, at every sampled
    corridor height — else the cavity would be split or the window
    would break the silhouette rim. Real numbers in the message."""
    z_lo, z_hi = _lens_z_range(p)
    span = z_hi - z_lo
    bx, zc = bore_center_mm(p)
    grow = p.wall_mm + BORE_LINER_EXTRA_MM
    ch = p.bore_height_mm / 2.0 + grow           # corridor semi-height
    cw = p.bore_width_mm / 2.0 + grow            # corridor semi-width
    worst = None
    for i in range(41):
        z = zc - ch + (2.0 * ch) * i / 40.0
        zt = (z - z_lo) / span
        if zt <= 0.0 or zt >= 1.0:
            return (f"window bore corridor leaves the lens vertically: "
                    f"corridor z {z:.0f} mm outside the lens span "
                    f"{z_lo:.0f}..{z_hi:.0f} mm")
        rel = (z - zc) / ch
        cx = cw * math.sqrt(max(1.0 - rel * rel, 0.0))
        inner_hw = half_width_mm(zt, p) - p.wall_mm
        margin = inner_hw - (abs(bx) + cx) - BORE_CLEARANCE_MARGIN_MM
        if worst is None or margin < worst[0]:
            worst = (margin, z, inner_hw, abs(bx) + cx)
    if worst is not None and worst[0] < 0.0:
        m, z, ihw, need = worst
        return (f"window bore corridor does not fit the lens: at "
                f"z={z:.0f} mm the inner silhouette half-width is "
                f"{ihw:.1f} mm but bore offset + corridor half-width + "
                f"{BORE_CLEARANCE_MARGIN_MM:g} mm margin needs "
                f"{need + BORE_CLEARANCE_MARGIN_MM:.1f} mm — shrink the "
                "bore, reduce plan_skew_ratio, or widen the lens")
    # the corridor also needs real depth material front and back
    zt_c = (zc - z_lo) / span
    inner_hd = half_depth_mm(zt_c, p) - p.wall_mm
    if inner_hd <= p.wall_mm:
        return (f"lens too thin for a walled bore: inner half-depth at "
                f"the bore centre {inner_hd:.1f} mm <= wall "
                f"{p.wall_mm:g} mm")
    return None


def validate(raw: dict[str, Any], materials: dict[str, Material] | None = None):
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []
    merged = merge_raw(PRIMITIVE_ID, PARAMETERS, raw, violations)
    try:
        params = FreeformLoopParams.model_validate(merged)
    except Exception as exc:
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    check_material(PRIMITIVE_ID, params.material_id, materials, violations)

    # 316L-only (owner ruling): the selected prototype manufacturing
    # hypothesis. Everything else refuses by name.
    if params.material_id != SUPPORTED_MATERIAL:
        violations.append(
            f"material_id={params.material_id!r} is not supported by "
            f"{PRIMITIVE_ID}: only {SUPPORTED_MATERIAL!r} (welded 316L "
            "sheet — the selected prototype manufacturing hypothesis, "
            "not an image-derived fact) is implemented. GRC / cast "
            "concrete / stone / bronze processes for free-form shells "
            "remain UNBUILT (LIMITATIONS 22, FABRICATOR-INPUT-REQUIRED)"
        )
        raise ConstraintViolation(violations)

    p = params
    # Hard scale + envelope band (owner ruling, unchanged).
    ratio = p.width_mm / p.height_mm
    lo, hi = WIDTH_HEIGHT_BAND
    if not (lo <= ratio <= hi):
        violations.append(
            f"width_mm/height_mm = {p.width_mm:g}/{p.height_mm:g} = "
            f"{ratio:.3f} outside the ref-08 envelope band "
            f"[{lo:g}, {hi:g}] (image-derived-estimate ±20%, "
            "ref08_landmarks.json) — this combination is not a "
            "ref-08-class form"
        )

    # Wall / embedment / ligament (owner arithmetic, unchanged).
    if p.wall_mm - EMBEDMENT_MM < MIN_LIGAMENT_MM:
        violations.append(
            f"wall_mm={p.wall_mm:g}: embedment {EMBEDMENT_MM:g} mm "
            f"(316L joint floor) + ligament {MIN_LIGAMENT_MM:g} mm "
            f"(316L min wall) require wall_mm >= "
            f"{EMBEDMENT_MM + MIN_LIGAMENT_MM:g} — the plate would "
            "compromise the shell"
        )

    if p.depth_mm > p.width_mm:
        violations.append(
            f"depth_mm={p.depth_mm:g} > width_mm={p.width_mm:g} — the "
            "lens cannot be deeper than it is wide [J bound, recorded]"
        )

    # Bow bound (owner v4, unchanged rule).
    wob_max = WOBBLE_HEIGHT_FRACTION_MAX * p.height_mm
    if abs(p.wobble_mm) > wob_max:
        violations.append(
            f"|wobble_mm|={abs(p.wobble_mm):g} > "
            f"{WOBBLE_HEIGHT_FRACTION_MAX:g} x height_mm = "
            f"{wob_max:g} mm (owner-approved bound)"
        )

    # Hollowability at the waist: the cavity must keep a real core.
    inner_hd_waist = p.depth_mm / 2.0 - p.wall_mm
    if inner_hd_waist < p.wall_mm:
        violations.append(
            f"hollowing impossible: depth {p.depth_mm:g}/2 - wall "
            f"{p.wall_mm:g} = {inner_hd_waist:.1f} mm < wall "
            f"{p.wall_mm:g} mm (min_internal_radius = wall, "
            "materials.yaml 316L formula)"
        )

    fit = _corridor_fit_violation(p)
    if fit:
        violations.append(fit)

    # NOTE (ADR-066, measured 2026-09-05): no predictive "fold guard"
    # exists here on purpose. A section-extent/spine-curvature guard
    # was tried and DISPROVEN by measurement — it refused a
    # proven-buildable combination (ratio 0.85 at 3.5 m) while missing
    # a real kernel failure (ratio 0.57 at 5.0 m). The kernel's
    # robustness cliff on large twisted thin shells is instead caught
    # LOUDLY at build time: every construction stage is checked and a
    # failed stage raises a deterministic ConstraintViolation refusal
    # with the real numbers (never a silent no-op boolean).

    floor = plate_diameter_floor_mm(p)
    if p.base_plate_diameter_mm < floor:
        violations.append(
            f"base_plate_diameter_mm={p.base_plate_diameter_mm:g} < "
            f"tip landing chord {landing_footprint_mm(p):.1f} + 2 x "
            f"{WELD_MARGIN_MM:g} mm weld margin = {floor:.1f} mm — the "
            "plate cannot receive the lens tip"
        )

    if violations:
        raise ConstraintViolation(violations)
    return params


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def _lens_solid(p, inset_mm: float):
    """One lofted lens along the straight vertical spine. ``inset_mm``
    > 0 builds the cavity lens: sections drawn in by the inset and the
    tips pulled to where the width profile still supports a wall.

    The loft-to-vertex apex tessellates as a DEGENERATE fan (measured
    2026-09-04: 4 boundary/non-manifold edges at the tips, zero-length
    and multiplicity-4), and fusing a blunting sphere onto the
    degenerate cone fails silently (measured: 2 solids, ~sphere-only
    volume — the ADR-064 silent-boolean class). Both tips are therefore
    TRUNCATED by a boolean cut wall_mm short of the point — [arith]: a
    formed 316L tip cannot be sharper than min_internal_radius = wall
    (materials.yaml formula), so the truncation is the material's own
    floor, not a cosmetic choice; the base truncation also gives the
    plate a real flat landing instead of a knife point."""
    from build123d import Box, Ellipse, Plane, Pos, Rot, Vertex, loft

    z_lo, z_hi = _lens_z_range(p)
    span = z_hi - z_lo
    if inset_mm > 0.0:
        # tips where the half-width profile crosses 2 x inset
        zt0 = _profile_crossing(p, 2.0 * inset_mm, rising=True)
        zt1 = _profile_crossing(p, 2.0 * inset_mm, rising=False)
    else:
        zt0, zt1 = 0.0, 1.0

    def station(zt: float):
        hw = half_width_mm(zt, p) - inset_mm
        hd = half_depth_mm(zt, p) - inset_mm
        return hw, hd

    sections = []
    tip_lo = (0.0, _bow_mm(zt0, p), z_lo + zt0 * span)
    tip_hi = (0.0, _bow_mm(zt1, p), z_lo + zt1 * span)
    n = N_STATIONS
    for i in range(1, n + 1):
        zt = zt0 + (zt1 - zt0) * i / (n + 1)
        hw, hd = station(zt)
        if hw <= 0.5 or hd <= 0.5:
            continue
        plane = Plane(origin=(0.0, _bow_mm(zt, p), z_lo + zt * span),
                      z_dir=(0, 0, 1), x_dir=(1, 0, 0))
        sections.append(
            plane * (Rot(0, 0, _twist_at(zt, p)) * Ellipse(hw, hd)))
    lens = loft([Vertex(*tip_lo)] + sections + [Vertex(*tip_hi)],
                ruled=False)
    r = float(p.wall_mm)
    big = 2.0 * (p.width_mm + p.depth_mm + abs(p.wobble_mm))
    lens = lens - Pos(0, 0, tip_hi[2] - r + big / 2.0) * Box(big, big, big)
    lens = lens - Pos(0, 0, tip_lo[2] + r - big / 2.0) * Box(big, big, big)
    return lens


def _bore_cylinder(p, grow_mm: float):
    """Elliptical cylinder along Y through the full lens depth (and
    then some), centred on the bore centre. ``grow_mm`` widens it into
    the clearance corridor."""
    from build123d import Ellipse, Plane, extrude

    bx, zc = bore_center_mm(p)
    length = 2.0 * (p.depth_mm + abs(p.wobble_mm)) + 100.0
    plane = Plane(origin=(bx, -length / 2.0, zc), z_dir=(0, 1, 0),
                  x_dir=(1, 0, 0))
    face = plane * Ellipse(p.bore_width_mm / 2.0 + grow_mm,
                           p.bore_height_mm / 2.0 + grow_mm)
    return extrude(face, amount=length)


def _refuse(detail: str) -> None:
    """A failed construction stage is a DETERMINISTIC, LOUD refusal
    (HTTP 422 through the normal ConstraintViolation path), never a
    silent no-op boolean (the ADR-064 class) and never a bare 500.
    Measured 2026-09-05: some extreme large/twisted combinations sit
    on a kernel robustness cliff — recorded in LIMITATIONS 22; the
    pinned refusal tests keep the boundary honest."""
    raise ConstraintViolation(
        [f"freeform_loop construction refused: {detail}"])


def build(p):
    from build123d import Cylinder, Pos

    outer = _lens_solid(p, 0.0)
    if len(outer.solids()) != 1 or float(outer.volume) <= 0.0:
        _refuse(
            f"freeform_loop outer lens produced {len(outer.solids())} "
            f"solids, volume {float(outer.volume):.1f} mm3 — expected "
            "one positive solid"
        )

    inner = _lens_solid(p, float(p.wall_mm))
    if len(inner.solids()) != 1 or float(inner.volume) <= 0.0:
        _refuse(
            f"freeform_loop inner lens produced {len(inner.solids())} "
            f"solids, volume {float(inner.volume):.1f} mm3 — expected "
            "one positive solid"
        )

    cavity = inner - _bore_cylinder(p, float(p.wall_mm)
                                    + BORE_LINER_EXTRA_MM)
    cav_solids = cavity.solids()
    if len(cav_solids) != 1 or float(cavity.volume) <= 0.0:
        _refuse(
            f"freeform_loop cavity collapsed or split: clearance "
            f"corridor left {len(cav_solids)} solids, volume "
            f"{float(cavity.volume):.1f} mm3 — expected one donut void "
            "(red-first failure condition: cavity collapse)"
        )

    hollow = outer - cavity
    if len(hollow.solids()) != 1:
        _refuse(
            f"freeform_loop hollowing produced "
            f"{len(hollow.solids())} solids, expected 1"
        )
    v_out, v_cav, v_hollow = (float(outer.volume), float(cavity.volume),
                              float(hollow.volume))
    if not (0.0 < v_hollow < v_out):
        _refuse(
            f"freeform_loop shell volume {v_hollow:.1f} mm3 outside "
            f"(0, outer {v_out:.1f}) — the cavity subtraction failed "
            "silently (the ADR-064 empty-boolean class)"
        )
    if abs((v_out - v_cav) - v_hollow) / v_hollow > 0.01:
        _refuse(
            f"freeform_loop shell volume {v_hollow:.1f} != outer "
            f"{v_out:.1f} - cavity {v_cav:.1f} (delta > 1%) — boolean "
            "defect"
        )

    pierced = hollow - _bore_cylinder(p, 0.0)
    pierced_solids = pierced.solids()
    if len(pierced_solids) != 1 or float(pierced.volume) <= 0.0:
        _refuse(
            f"freeform_loop window bore left {len(pierced_solids)} "
            f"solids, volume {float(pierced.volume):.1f} mm3 — "
            "expected one pierced shell (red-first failure condition: "
            "bore/topology defect)"
        )
    pierced = pierced_solids[0]

    # The bore must NOT have opened the cavity: exactly two
    # face-connected boundary components (outer skin + sealed cavity).
    # The authoritative clearance proof is the MEASURED bore-region
    # wall (measure_wall/gate) — this census is the loud early tripwire.
    comps = _face_components(pierced)
    if len(comps) != 2:
        _refuse(
            f"freeform_loop bore opened the internal cavity: face "
            f"partition found {len(comps)} boundary components, "
            "expected 2 (red-first failure condition: bore-to-cavity "
            "communication)"
        )

    # Seat exactly: lens tip at plate_top − embedment.
    bb = pierced.bounding_box()
    target_low = float(p.wall_mm) - EMBEDMENT_MM
    pierced = Pos(0, 0, target_low - float(bb.min.Z)) * pierced

    plate = Pos(0, 0, float(p.wall_mm) / 2.0) * Cylinder(
        float(p.base_plate_diameter_mm) / 2.0, float(p.wall_mm))

    try:
        embed = pierced & plate
        embed_vol = float(embed.volume) if embed is not None else 0.0
    except Exception:
        embed_vol = 0.0
    if embed_vol <= 0.0:
        _refuse(
            f"freeform_loop tip does not embed into the interface "
            f"plate (intersection {embed_vol:.3f} mm3) — a tangent or "
            "floating contact is the ADR-029 knife edge and is refused"
        )

    solid = pierced + plate
    parts = solid.solids()
    if len(parts) != 1:
        _refuse(
            f"freeform_loop union produced {len(parts)} solids, "
            "expected 1"
        )
    return parts[0]


# ---------------------------------------------------------------------------
# protocol surface
# ---------------------------------------------------------------------------

def height_mm(p) -> float:
    return float(p.height_mm)


def anchors(p) -> dict[str, float | None]:
    return {"base": 0.0, "top": float(p.height_mm), "seat": None}


def max_outer_diameter_mm(p) -> float:
    return float(max(p.width_mm, p.base_plate_diameter_mm))


def inner_diameter_mm(p) -> float | None:
    return None


def base_annulus_mm(p) -> tuple[float, float]:
    """The interface plate is a solid disk footprint."""
    return float(p.base_plate_diameter_mm), 0.0


def stack_top_annulus_mm(p) -> None:
    return None


# ---------------------------------------------------------------------------
# geometric wall measurement (v4 rule — measured or honest needs_input)
# ---------------------------------------------------------------------------

def _face_components(solid) -> list[list[Any]]:
    """Partition the solid's faces into edge-connected components —
    networkx/scipy-free (neither is on the pinned image, ADR-064)."""
    faces = list(solid.faces())

    def edge_key(edge) -> tuple:
        c = edge.center()
        return (round(float(c.X), 3), round(float(c.Y), 3),
                round(float(c.Z), 3), round(float(edge.length), 3))

    parent = list(range(len(faces)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    seen: dict[tuple, int] = {}
    for idx, face in enumerate(faces):
        for edge in face.edges():
            k = edge_key(edge)
            if k in seen:
                union(seen[k], idx)
            else:
                seen[k] = idx
    groups: dict[int, list[Any]] = {}
    for idx, face in enumerate(faces):
        groups.setdefault(find(idx), []).append(face)
    return sorted(groups.values(), key=len, reverse=True)


def _compound_of(faces):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    comp = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(comp)
    for f in faces:
        builder.Add(comp, f.wrapped)
    return comp


def measure_wall(p, solid) -> dict[str, Any]:
    """brepextrema_v1: calibrated red-first against known hollow
    controls (tests/test_wall_measurement.py). Returns the manifest
    block the fabrication gate holds to the v4 rule — PASS only when
    calibrated AND in tolerance, else needs_input. NEVER a claim that
    the nominal gauge is a measured or approved wall.

    Owner clarification 2 (2026-09-04): the MEASURED bore-region wall
    (`bore_region_min_mm` — cavity samples inside the bore corridor
    footprint) is the authoritative bore-to-cavity clearance; the gate
    FAILS if it is < wall_mm − 0.5 mm. Junction rule: cavity samples in
    the plate zone are excluded from the max (their nearest outer
    surface is the plate)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt

    components = _face_components(solid)
    if len(components) != 2:
        return {
            "method": "brepextrema_v1", "status": "unavailable",
            "reason": (f"face partition found {len(components)} "
                       "boundary components, expected 2 (outer + "
                       "cavity) — measurement basis absent"),
        }
    outer_comp = _compound_of(components[0])
    cavity_comp = _compound_of(components[1])

    d = BRepExtrema_DistShapeShape(outer_comp, cavity_comp)
    if not d.IsDone():
        return {"method": "brepextrema_v1", "status": "unavailable",
                "reason": "outer-to-cavity distance did not converge"}
    min_mm = float(d.Value())
    if min_mm <= 1e-6:
        return {
            "method": "brepextrema_v1", "status": "unavailable",
            "reason": (f"zero-distance artifact ({min_mm:.9f} mm) "
                       "between boundary components — seam/end-face "
                       "contact, measurement untrustworthy"),
        }

    from build123d import Compound
    cav = Compound(cavity_comp)
    verts, _tris = cav.tessellate(tolerance=1.0, angular_tolerance=0.1)
    pts = sorted({(round(v.X, 3), round(v.Y, 3), round(v.Z, 3))
                  for v in verts})
    step = max(1, len(pts) // 200)
    samples = pts[::step][:200]

    # Owner clarification 2: the MEASURED bore-to-cavity distance is
    # authoritative. Measured DIRECTLY: the window-tube faces (outer-
    # component faces whose centre lies inside the bore footprint) to
    # the whole cavity component — one BRepExtrema call, no sampling.
    wall = float(getattr(p, "wall_mm", 0.0) or 0.0)
    bore_to_cavity_mm = None
    bore_face_count = 0
    bw_pre = float(getattr(p, "bore_width_mm", 0.0) or 0.0)
    bh_pre = float(getattr(p, "bore_height_mm", 0.0) or 0.0)
    if bw_pre > 0 and bh_pre > 0:
        bx_pre, bzc_pre = bore_center_mm(p)
        cw_pre = bw_pre / 2.0 * 1.05
        chh_pre = bh_pre / 2.0 * 1.05
        bore_faces = []
        for face in components[0]:
            c = face.center()
            if (((float(c.X) - bx_pre) / cw_pre) ** 2
                    + ((float(c.Z) - bzc_pre) / chh_pre) ** 2 <= 1.0):
                bore_faces.append(face)
        bore_face_count = len(bore_faces)
        if bore_faces:
            db = BRepExtrema_DistShapeShape(_compound_of(bore_faces),
                                            cavity_comp)
            if db.IsDone():
                bore_to_cavity_mm = float(db.Value())

    plate_d = float(getattr(p, "base_plate_diameter_mm", 0.0) or 0.0)
    junction_r = plate_d / 2.0 + wall
    junction_z = wall * 2.0
    bw = float(getattr(p, "bore_width_mm", 0.0) or 0.0)
    bh = float(getattr(p, "bore_height_mm", 0.0) or 0.0)
    max_mm = 0.0
    max_junction_mm = 0.0
    n_junction = 0
    for (x, y, z) in samples:
        v = BRepBuilderAPI_MakeVertex(gp_Pnt(x, y, z)).Vertex()
        dv = BRepExtrema_DistShapeShape(v, outer_comp)
        if not dv.IsDone():
            continue
        val = float(dv.Value())
        if val <= 1e-6:
            return {
                "method": "brepextrema_v1", "status": "unavailable",
                "reason": (f"zero-distance artifact at cavity sample "
                           f"({x:.1f}, {y:.1f}, {z:.1f}) — "
                           "measurement untrustworthy"),
            }
        in_junction = (math.hypot(x, y) <= junction_r
                       and z <= junction_z)
        if in_junction:
            n_junction += 1
            max_junction_mm = max(max_junction_mm, val)
        else:
            max_mm = max(max_mm, val)
    return {
        "method": "brepextrema_v1", "status": "measured",
        "min_mm": round(min_mm, 3), "max_mm": round(max_mm, 3),
        "samples": len(samples), "junction_excluded": n_junction,
        "junction_max_mm": round(max_junction_mm, 3),
        "junction_basis": (f"cavity samples within plate radius + wall "
                           f"({junction_r:.1f} mm) and z <= 2 x wall "
                           f"({junction_z:.1f} mm): nearest outer "
                           "surface is the interface plate, not the "
                           "shell wall"),
        "bore_to_cavity_mm": (round(bore_to_cavity_mm, 3)
                              if bore_to_cavity_mm is not None else None),
        "bore_face_count": bore_face_count,
        "bore_basis": ("BRepExtrema distance from the window-tube faces "
                       "(outer-component faces centred inside the bore "
                       "footprint x1.05) to the entire cavity component "
                       "— the AUTHORITATIVE bore-to-cavity clearance "
                       "(owner clarification 2); FAIL below wall − "
                       f"{WALL_MEASURE_TOL_MM:g} mm"),
    }


# ---------------------------------------------------------------------------
# projection metrics (fixture-fidelity landmarks, gate_ffa2_auto)
# ---------------------------------------------------------------------------

def projection_metrics(solid, grid_mm: float = 10.0) -> dict[str, Any]:
    """Front-view (X-Z, looking along +Y) silhouette metrics measured
    from the built geometry — deterministic rasterization of the
    tessellation. These are what the gate holds against the committed
    ref08_landmarks.json bands; pixel comparison is never an auto-gate
    check (owner condition 11, ADR-064)."""
    import numpy as np

    verts, tris = solid.tessellate(tolerance=1.0, angular_tolerance=0.1)
    pts = np.array([[v.X, v.Z] for v in verts], dtype=float)
    tris = np.asarray(tris, dtype=int)

    lo = pts.min(axis=0) - grid_mm
    hi = pts.max(axis=0) + grid_mm
    nx = int(math.ceil((hi[0] - lo[0]) / grid_mm)) + 1
    nz = int(math.ceil((hi[1] - lo[1]) / grid_mm)) + 1
    occ = np.zeros((nx, nz), dtype=bool)

    cx = lo[0] + (np.arange(nx) + 0.5) * grid_mm
    cz = lo[1] + (np.arange(nz) + 0.5) * grid_mm
    for tri in tris:
        a, b, c = pts[tri[0]], pts[tri[1]], pts[tri[2]]
        xmin = min(a[0], b[0], c[0]); xmax = max(a[0], b[0], c[0])
        zmin = min(a[1], b[1], c[1]); zmax = max(a[1], b[1], c[1])
        i0 = max(0, int((xmin - lo[0]) / grid_mm) - 1)
        i1 = min(nx - 1, int((xmax - lo[0]) / grid_mm) + 1)
        j0 = max(0, int((zmin - lo[1]) / grid_mm) - 1)
        j1 = min(nz - 1, int((zmax - lo[1]) / grid_mm) + 1)
        if i1 < i0 or j1 < j0:
            continue
        gx = cx[i0:i1 + 1][:, None]
        gz = cz[j0:j1 + 1][None, :]
        d1 = (b[0] - a[0]) * (gz - a[1]) - (b[1] - a[1]) * (gx - a[0])
        d2 = (c[0] - b[0]) * (gz - b[1]) - (c[1] - b[1]) * (gx - b[0])
        d3 = (a[0] - c[0]) * (gz - c[1]) - (a[1] - c[1]) * (gx - c[0])
        neg = (d1 < 0) | (d2 < 0) | (d3 < 0)
        pos = (d1 > 0) | (d2 > 0) | (d3 > 0)
        occ[i0:i1 + 1, j0:j1 + 1] |= ~(neg & pos)

    from collections import deque
    outside = np.zeros_like(occ)
    dq: deque = deque()
    for i in range(nx):
        for j in (0, nz - 1):
            if not occ[i, j] and not outside[i, j]:
                outside[i, j] = True
                dq.append((i, j))
    for j in range(nz):
        for i in (0, nx - 1):
            if not occ[i, j] and not outside[i, j]:
                outside[i, j] = True
                dq.append((i, j))
    while dq:
        i, j = dq.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if (0 <= ni < nx and 0 <= nj < nz
                    and not occ[ni, nj] and not outside[ni, nj]):
                outside[ni, nj] = True
                dq.append((ni, nj))

    enclosed = ~occ & ~outside
    labels = np.zeros((nx, nz), dtype=int)
    comp_cells: list[list[tuple[int, int]]] = []
    for i in range(nx):
        for j in range(nz):
            if enclosed[i, j] and labels[i, j] == 0:
                comp_id = len(comp_cells) + 1
                cells = []
                dq.append((i, j))
                labels[i, j] = comp_id
                while dq:
                    ci, cj = dq.popleft()
                    cells.append((ci, cj))
                    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ni, nj = ci + di, cj + dj
                        if (0 <= ni < nx and 0 <= nj < nz
                                and enclosed[ni, nj]
                                and labels[ni, nj] == 0):
                            labels[ni, nj] = comp_id
                            dq.append((ni, nj))
                comp_cells.append(cells)

    occ_i, occ_j = np.nonzero(occ)
    sil_w = (occ_i.max() - occ_i.min() + 1) * grid_mm
    sil_h = (occ_j.max() - occ_j.min() + 1) * grid_mm
    sil_cx = (occ_i.max() + occ_i.min()) / 2.0
    sil_min_j = occ_j.min()

    result: dict[str, Any] = {
        "grid_mm": grid_mm,
        "silhouette_width_mm": round(float(sil_w), 1),
        "silhouette_height_mm": round(float(sil_h), 1),
        "width_height_ratio": round(float(sil_w / sil_h), 4),
        "enclosed_void_count": len(comp_cells),
    }
    if not comp_cells:
        return result

    void = max(comp_cells, key=len)
    vi = np.array([c[0] for c in void])
    vj = np.array([c[1] for c in void])
    v_w = (vi.max() - vi.min() + 1) * grid_mm
    v_h = (vj.max() - vj.min() + 1) * grid_mm
    v_ci, v_cj = float(vi.mean()), float(vj.mean())
    result.update({
        "void_width_mm": round(float(v_w), 1),
        "void_height_mm": round(float(v_h), 1),
        "void_width_fraction": round(float(v_w / sil_w), 4),
        "void_aspect": round(float(v_w / v_h), 4),
        "void_centroid_height_fraction": round(
            float((v_cj - sil_min_j) * grid_mm / sil_h), 4),
        "void_offset_fraction": round(
            float((v_ci - sil_cx) * grid_mm / sil_w), 4),
    })

    # projected_side_to_apex_band_ratio (ADR-066, owner ruling
    # 2026-09-05 — operational re-derivation of the retired rim_ratio):
    #   numerator   = the WIDER of the left/right occupied runs
    #                 outward from the void bbox at the void-centroid
    #                 ROW;
    #   denominator = the occupied run downward from the silhouette top
    #                 at the void-centroid COLUMN (which crosses the
    #                 void by construction — the retired topmost-pixel
    #                 column was discontinuous: it missed the void on
    #                 the reference and hit it on the geometry).
    # This is a PROJECTION metric only: it claims nothing about the
    # reference's 3-D apex scoop and rim shaping, which remain a
    # separate mandatory visual-gate comparison.
    row = int(round(v_cj))
    left_edge, right_edge = int(vi.min()), int(vi.max())
    rim_left = 0
    i = left_edge - 1
    while i >= 0 and occ[i, row]:
        rim_left += 1
        i -= 1
    rim_right = 0
    i = right_edge + 1
    while i < nx and occ[i, row]:
        rim_right += 1
        i += 1
    col = int(round(v_ci))
    col_cells = np.nonzero(occ[col, :])[0]
    apex_band = 0
    if len(col_cells):
        j = int(col_cells.max())
        while j >= 0 and occ[col, j]:
            apex_band += 1
            j -= 1
    result.update({
        "rim_left_mm": round(rim_left * grid_mm, 1),
        "rim_right_mm": round(rim_right * grid_mm, 1),
        "apex_band_mm": round(apex_band * grid_mm, 1),
        "projected_side_to_apex_band_ratio": round(
            max(rim_left, rim_right) / apex_band, 4) if apex_band else None,
    })
    return result
