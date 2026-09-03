"""PR-2.5 approach (a): controlled OpenCASCADE BREP loft/sweep/spline.

SANDBOX-ONLY (ADR-005/ADR-064): this file constructs geometry and runs
exclusively inside the geo-worker sandbox via scripts/run_pr25_discovery.py.
Never import it from a test or a gate.

Five fixtures mirror the geometric language of the five primary B-11
references (silhouette + topology, per the owner's fidelity ruling; all
proportions are tagged image-derived-estimate in the discovery report and
carry uncertainty). All coordinates in mm at the owner-ruled 3.5-5.0 m
scale. One extra fixture is DELIBERATELY pathological (a self-crossing
sweep): the validation stack must refuse it; a construction-time refusal
by the kernel itself also counts (the gate accepts either).

Every fixture is wrapped so a failure is recorded as evidence with the
real exception text and the probe continues (owner clarification 4).
"""

from __future__ import annotations

import argparse
import math
import traceback
from pathlib import Path

from probe_common import (DISCOVERY_SEED, result_entry, sha256_file,
                          write_results)

PROBE = "probe_freeform_brep"


# --------------------------------------------------------------------------
# Construction helpers (all pure functions of their arguments + the seed)
# --------------------------------------------------------------------------

def _frame_x_dir(tangent):
    """Deterministic section x-axis: global Z projected off the tangent;
    falls back to global X when the path runs vertically."""
    from build123d import Vector
    up = Vector(0, 0, 1)
    if abs(tangent.normalized().dot(up)) > 0.999:
        up = Vector(1, 0, 0)
    x = up.cross(tangent).normalized()
    return x


def _placed_sections(path_edge, section_fn, ts):
    """Build section faces on planes along the path at parameters ts.

    section_fn(t) returns a 2D Sketch centred on origin (already twisted
    via its constructor `rotation` argument).
    """
    from build123d import Plane
    sections = []
    for t in ts:
        origin = path_edge.position_at(t)
        tangent = path_edge.tangent_at(t)
        plane = Plane(origin=origin, z_dir=tangent,
                      x_dir=_frame_x_dir(tangent))
        sections.append(plane * section_fn(t))
    return sections


def _measures(shape):
    bb = shape.bounding_box()
    size = bb.size
    return {
        "volume_mm3": round(float(shape.volume), 3),
        "bbox_mm": [round(float(size.X), 3), round(float(size.Y), 3),
                    round(float(size.Z), 3)],
        "solid_count": len(shape.solids()),
        "kernel_is_valid": bool(shape.is_valid),
    }


def _export(shape, out_dir: Path, name: str) -> dict:
    """Deterministic STEP (contractual bytes) + GLB (viewing, hash logged)."""
    from app.geometry.exporters import export_glb, export_step
    from app.geometry.kernel import step_timestamp_for
    step_path = out_dir / ("%s.step" % name)
    glb_path = out_dir / ("%s.glb" % name)
    export_step(shape, step_path, step_timestamp_for(DISCOVERY_SEED))
    export_glb(shape, glb_path)
    return {
        "step": {"file": step_path.name, "sha256": sha256_file(step_path)},
        "glb": {"file": glb_path.name, "sha256": sha256_file(glb_path)},
    }


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

def fx_ref11_twist_ribbon():
    """Ref 11 language: open 3D spline path, section rotated 0->270 deg and
    scaled along it (loft through 24 placed sections)."""
    from build123d import RectangleRounded, Spline, loft
    path = Spline((0, 0, 0), (150, -250, 800), (-220, 180, 1600),
                  (200, 120, 2400), (-120, -200, 3200), (0, 0, 4000))
    n = 24

    def section(t):
        width = 800.0 - 500.0 * t          # mm, image-derived-estimate
        height = 220.0                      # mm, image-derived-estimate
        twist = 270.0 * t                   # deg
        return RectangleRounded(width, height, 60.0, rotation=twist)

    ts = [i / (n - 1) for i in range(n)]
    return loft(_placed_sections(path, section, ts), ruled=False)


def fx_ref08_void_loop():
    """Ref 08 language: one closed loop with a large through-void.
    Constant elliptical section swept along a periodic 3D spline."""
    from build123d import Ellipse, Plane, Spline, sweep
    pts = []
    n = 8
    for i in range(n):
        a = 2.0 * math.pi * i / n
        # upright rounded-diamond loop, mild out-of-plane wobble (mm)
        x = 1150.0 * math.sin(a)
        z = 2050.0 + 1750.0 * math.cos(a)
        y = 140.0 * math.sin(2.0 * a)
        pts.append((x, y, z))
    path = Spline(*pts, periodic=True)
    origin = path.position_at(0.0)
    tangent = path.tangent_at(0.0)
    section = Plane(origin=origin, z_dir=tangent,
                    x_dir=_frame_x_dir(tangent)) * Ellipse(300.0, 190.0)
    return sweep(section, path=path)


def fx_ref08_varying_loop():
    """Ref 08, harder claim: the SAME closed loop with a VARYING section
    (multisection sweep along a periodic path). Expected to be the
    fragile case; failure here is a real finding, not a defect."""
    from build123d import Ellipse, Spline, sweep
    pts = []
    n = 8
    for i in range(n):
        a = 2.0 * math.pi * i / n
        x = 1150.0 * math.sin(a)
        z = 2050.0 + 1750.0 * math.cos(a)
        y = 140.0 * math.sin(2.0 * a)
        pts.append((x, y, z))
    path = Spline(*pts, periodic=True)

    def section(t):
        grow = 1.0 + 0.45 * math.sin(2.0 * math.pi * t)
        return Ellipse(300.0 * grow, 190.0 / grow)

    ts = [i / 12.0 for i in range(12)]
    return sweep(sections=_placed_sections(path, section, ts),
                 path=path, multisection=True)


def fx_ref13_double_loop():
    """Ref 13 language: one vertical body, TWO through-voids (target genus
    2), section orientation varying up the height. Outer lofted hull minus
    two swept void tubes."""
    from build123d import Ellipse, Plane, Spline, Vector, loft, sweep

    # Outer hull: lofted ellipses, hourglass widths, 25 deg twist at waist.
    zs = [0, 700, 1500, 2300, 3100, 3900, 4600]
    widths = [820, 1350, 760, 1240, 900, 460, 90]     # mm, image-derived
    depths = [460, 660, 420, 620, 470, 260, 60]
    twists = [0, 8, 25, 12, 4, 0, 0]
    sections = []
    for z, w, d, tw in zip(zs, widths, depths, twists):
        sections.append(Plane(origin=(0, 0, z)) *
                        Ellipse(w / 2.0, d / 2.0, rotation=tw))
    hull = loft(sections, ruled=False)

    def void_tube(center_z, x_off, rx, rz):
        # Straight through-thickness sweep along Y (depth axis).
        path = Spline((x_off, -900.0, center_z), (x_off, 900.0, center_z))
        origin = path.position_at(0.0)
        tangent = path.tangent_at(0.0)
        section = Plane(origin=origin, z_dir=tangent,
                        x_dir=Vector(1, 0, 0)) * Ellipse(rx, rz)
        return sweep(section, path=path)

    # Void radii sized to stay INSIDE the lofted hull at their stations --
    # the first probe iteration used image-guessed 420/360 mm radii that
    # were wider than the hourglass waist and BISECTED the body into two
    # solids (recorded in the discovery report as fixture-development
    # evidence; a genuine kernel capability needs one genus-2 body).
    hull -= void_tube(1250.0, 0.0, 300.0, 260.0)
    hull -= void_tube(3150.0, 0.0, 280.0, 230.0)
    return hull


def fx_ref14_interwoven():
    """Ref 14 language: central mass with ribbons weaving around it, all
    FUSED into one body with multiple voids; the two ribbons keep a
    declared clearance (they touch only the column, never each other)."""
    from build123d import Ellipse, Plane, Spline, loft, sweep

    zs = [0, 900, 1900, 2900, 3800, 4200]
    radii = [520, 480, 430, 380, 300, 210]  # mm, image-derived-estimate
    sections = [Plane(origin=(0, 0, z)) * Ellipse(r, r * 0.82)
                for z, r in zip(zs, radii)]
    column = loft(sections, ruled=False)

    def ribbon(center_z, tilt_deg, phase_deg):
        # A closed ring is deliberately ASSEMBLED from two overlapping
        # OPEN sweeps and fused: the first probe iteration swept a single
        # periodic spline and the seam came out defective (duplicate seam
        # faces, kernel-invalid -- kept as evidence in ref08_void_loop),
        # which then degenerated the column fuse. Open sweeps are healthy.
        tilt = math.radians(tilt_deg)
        phase = math.radians(phase_deg)

        def pt(a):
            a = a + phase
            r = 980.0
            x = r * math.cos(a)
            y = r * math.sin(a)
            z = center_z + math.sin(a) * math.tan(tilt) * 560.0
            # pull the two crossing stations INTO the column so fuse joins
            near_cross = min(abs(math.remainder(a - phase, 2 * math.pi)),
                             abs(abs(math.remainder(a - phase, 2 * math.pi))
                                 - math.pi))
            if near_cross < 0.35:
                x *= 0.30
                y *= 0.30
            return (x, y, z)

        def half(a0, a1):
            n = 9
            pts = [pt(a0 + (a1 - a0) * i / (n - 1)) for i in range(n)]
            path = Spline(*pts)
            origin = path.position_at(0.0)
            tangent = path.tangent_at(0.0)
            section = Plane(origin=origin, z_dir=tangent,
                            x_dir=_frame_x_dir(tangent)) * Ellipse(230.0,
                                                                   130.0)
            return sweep(section, path=path)

        overlap = 0.30
        return half(-overlap, math.pi + overlap) + \
            half(math.pi - overlap, 2.0 * math.pi + overlap)

    # 700 mm vertical separation between ribbon centres keeps ribbon-ribbon
    # clearance while both intersect the column (probe-only-judgement).
    solid = column + ribbon(1500.0, 16.0, 0.0) + ribbon(2600.0, -14.0, 90.0)
    return solid


def fx_ref16_split_rejoin():
    """Ref 16 language: a trunk that splits into two lobes and reunites
    (one through-void between them), fused into one body."""
    from build123d import Ellipse, Plane, RectangleRounded, Spline, loft

    trunk = loft([Plane(origin=(0, 0, 0)) * Ellipse(360.0, 210.0),
                  Plane(origin=(0, 0, 500)) * Ellipse(330.0, 200.0)],
                 ruled=False)

    def lobe(sign):
        path = Spline((0, 0, 420), (sign * 420, 60, 1300),
                      (sign * 560, -40, 2100), (sign * 380, 40, 2950),
                      (0, 0, 3800))
        n = 14

        def section(t):
            s = 1.0 - 0.35 * math.sin(math.pi * t)
            return RectangleRounded(430.0 * s, 260.0 * s, 80.0 * s,
                                    rotation=sign * 18.0 * math.sin(math.pi * t))

        ts = [i / (n - 1) for i in range(n)]
        return loft(_placed_sections(path, section, ts), ruled=False)

    tip = loft([Plane(origin=(0, 0, 3720)) * Ellipse(300.0, 180.0),
                Plane(origin=(0, 0, 4250)) * Ellipse(60.0, 40.0)],
               ruled=False)
    return trunk + lobe(+1.0) + lobe(-1.0) + tip


def fx_bad_self_crossing():
    """DELIBERATELY PATHOLOGICAL: a fat section swept along a figure-eight
    path that passes through the same region twice -- the swept solid must
    self-overlap. The validation stack (or the kernel itself, by refusing
    construction) MUST flag this; if it sails through every check the gate
    fails loudly (amended plan section 4, check 5)."""
    from build123d import Ellipse, Plane, Spline, sweep
    pts = []
    n = 12
    for i in range(n):
        a = 2.0 * math.pi * i / n
        # lemniscate-like: crosses near the z-axis twice per revolution
        x = 900.0 * math.sin(a)
        y = 650.0 * math.sin(a) * math.cos(a)
        z = 2000.0 + 400.0 * math.sin(a)
        pts.append((x, y, z))
    path = Spline(*pts, periodic=True)
    origin = path.position_at(0.0)
    tangent = path.tangent_at(0.0)
    section = Plane(origin=origin, z_dir=tangent,
                    x_dir=_frame_x_dir(tangent)) * Ellipse(340.0, 240.0)
    return sweep(section, path=path)


def fx_ref16_fillet_attempt(base_shape):
    """Ref 16 follow-up: can the junction seams be blended? Tries a 25 mm
    fillet on every edge of the fused split/rejoin body, then an 8 mm one
    if that fails. Complex fuse seams are exactly where OCC fillets die;
    either outcome is evidence for the 'smooth reunion' question."""
    from build123d import fillet
    try:
        return fillet(base_shape.edges(), radius=25.0), 25.0
    except Exception:
        return fillet(base_shape.edges(), radius=8.0), 8.0


def _ref08_loop_parts():
    """Shared machinery for the two closed-loop assembly fixtures below:
    analytic section placement around the ref-08 loop (position, tangent
    and section are exact functions of the WRAPPED parameter, so t=0 and
    t=1 evaluate bitwise-identically)."""
    from build123d import Ellipse, Plane, Vector, loft

    def loop_pt(t):
        t = t % 1.0
        a = 2.0 * math.pi * t
        return (1150.0 * math.sin(a), 140.0 * math.sin(2.0 * a),
                2050.0 + 1750.0 * math.cos(a))

    def loop_tan(t):
        t = t % 1.0
        a = 2.0 * math.pi * t
        return Vector(1150.0 * math.cos(a), 280.0 * math.cos(2.0 * a),
                      -1750.0 * math.sin(a)).normalized()

    def section(t):
        t = t % 1.0
        grow = 1.0 + 0.45 * math.sin(2.0 * math.pi * t)
        return Ellipse(300.0 * grow, 190.0 / grow)

    def placed(t):
        tan = loop_tan(t)
        return Plane(origin=loop_pt(t), z_dir=tan,
                     x_dir=_frame_x_dir(tan)) * section(t)

    def half(t0, t1, n=11):
        return loft([placed(t0 + (t1 - t0) * i / (n - 1))
                     for i in range(n)], ruled=False)

    return half


def fx_ref08_loop_from_halves():
    """Ref 08, the WORKING construction: a closed varying-section loop
    assembled from two BUTT-JOINED open lofts whose boundary sections are
    bitwise-identical (wrapped-parameter evaluation), then fused. This is
    the route left standing after the periodic sweep (seam-defective,
    kept above as evidence) and the periodic multisection sweep (refused
    by OCC) both fall away."""
    half = _ref08_loop_parts()
    return half(0.0, 0.5) + half(0.5, 1.0)


def fx_bad_tangent_overlap_fuse():
    """DELIBERATELY KEPT DEFECT SPECIMEN: the same two half-loops but
    OVERLAPPED (coaxial, near-tangent interpenetration) instead of
    butt-joined. On this stack OCC's fuse SILENTLY returns an empty
    Compound that still claims is_valid=True -- the exact silent-failure
    class the discovery plan's risk section named. The probe's
    empty-result guard must catch it and record 'failed'; it must never
    appear as a constructed artifact."""
    half = _ref08_loop_parts()
    return half(-0.06, 0.56) + half(0.44, 1.06)


FIXTURES = [
    ("ref11_twist_ribbon", fx_ref11_twist_ribbon, False),
    ("ref08_void_loop", fx_ref08_void_loop, False),
    ("ref08_varying_loop", fx_ref08_varying_loop, False),
    ("ref08_loop_from_halves", fx_ref08_loop_from_halves, False),
    ("bad_tangent_overlap_fuse", fx_bad_tangent_overlap_fuse, True),
    ("ref13_double_loop", fx_ref13_double_loop, False),
    ("ref14_interwoven", fx_ref14_interwoven, False),
    ("ref16_split_rejoin", fx_ref16_split_rejoin, False),
    ("bad_self_crossing", fx_bad_self_crossing, True),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args()
    if args.seed != DISCOVERY_SEED:
        raise SystemExit("seed mismatch: got %d, discovery pins %d"
                         % (args.seed, DISCOVERY_SEED))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    notes = []
    built = {}
    for name, builder, expected_invalid in FIXTURES:
        try:
            shape = builder()
            # Empty-result integrity guard: OCC booleans can SILENTLY
            # return an empty Compound that still claims is_valid=True
            # (measured 2026-09-02, near-tangent overlap fuse). An empty
            # or zero-volume result is a FAILURE, never an artifact.
            if len(shape.solids()) == 0 or float(shape.volume) <= 0.0:
                entries.append(result_entry(
                    name, "brep", status="failed",
                    detail=("construction returned an empty/zero-volume "
                            "result (solids=%d, volume=%.3f mm^3) -- "
                            "silent boolean failure caught by the "
                            "empty-result guard"
                            % (len(shape.solids()), float(shape.volume))),
                    expected_invalid=expected_invalid))
                continue
            built[name] = shape
            entries.append(result_entry(
                name, "brep", status="constructed",
                detail="constructed by build123d/OCC in the sandbox",
                artifacts=_export(shape, out_dir, name),
                measures=_measures(shape),
                expected_invalid=expected_invalid))
        except Exception:
            entries.append(result_entry(
                name, "brep", status="failed",
                detail=traceback.format_exc(limit=4),
                expected_invalid=expected_invalid))

    # Junction-blend follow-up only makes sense if the base body exists.
    if "ref16_split_rejoin" in built:
        try:
            blended, used_r = fx_ref16_fillet_attempt(built["ref16_split_rejoin"])
            entries.append(result_entry(
                "ref16_fillet_seams", "brep", status="constructed",
                detail="%.0f mm fillet over all edges of the fused body"
                       % used_r,
                artifacts=_export(blended, out_dir, "ref16_fillet_seams"),
                measures=_measures(blended)))
        except Exception:
            entries.append(result_entry(
                "ref16_fillet_seams", "brep", status="failed",
                detail=traceback.format_exc(limit=4)))
    else:
        notes.append("ref16_fillet_seams skipped: base body failed")

    write_results(out_dir, PROBE, entries, notes)
    print("%s: %d fixtures, %d constructed, %d failed"
          % (PROBE, len(entries),
             sum(1 for e in entries if e["status"] == "constructed"),
             sum(1 for e in entries if e["status"] == "failed")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
