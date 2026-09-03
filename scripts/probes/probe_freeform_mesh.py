"""PR-2.5 approach (b): deterministic procedural mesh-native construction.

SANDBOX-ONLY (ADR-005/ADR-064): constructs geometry; runs exclusively in
the geo-worker sandbox via scripts/run_pr25_discovery.py.

The generator is a pure function of its parameters: a centreline path
p(t), a deterministic frame, and a section curve s(t, u) (superellipse
with varying width/height/twist) produce an exact N x M vertex grid;
faces index that grid in a fixed order. Open paths are capped with
triangle fans. No RNG anywhere. Canonical bytes = the probe_common OBJ
writer; GLB is exported for viewing only (hash logged, determinism not
claimed for GLB bytes).

WHAT THIS PROBE DELIBERATELY CANNOT DO (the honest comparative point):
there is no boolean/fusion machinery on this route in the installed stack
(no CGAL/libigl/OpenVDB, and scikit-image marching cubes is NOT
installed). So ref13 (hull-minus-voids) and ref16 (fused lobes) are not
constructible here without new dependencies, and ref14 comes out as three
DISJOINT interlocked bodies. Each of those is recorded as a 'failed' or
qualified row -- that gap is a primary discovery finding, not a defect.

Units: mm. Scale: owner-ruled 3.5-5.0 m envelope.
"""

from __future__ import annotations

import argparse
import math
import traceback
from pathlib import Path

import numpy as np

from probe_common import (DISCOVERY_SEED, result_entry, sha256_file,
                          write_canonical_obj, write_results)

PROBE = "probe_freeform_mesh"

#: Grid resolution (path stations x section points). probe-only-judgement:
#: dense enough for smooth silhouettes, small enough for the 2 GB sandbox.
N_PATH = 160
N_SECT = 48


def _frames(points, closed):
    """Deterministic sliding frame along a polyline path: tangent by
    central difference; x-axis = global Z (or X when vertical) projected
    off the tangent -- the same convention as the BREP probe."""
    p = np.asarray(points, dtype=np.float64)
    if closed:
        tan = np.roll(p, -1, axis=0) - np.roll(p, 1, axis=0)
    else:
        tan = np.gradient(p, axis=0)
    tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    x_axis = np.zeros_like(tan)
    for i, t in enumerate(tan):
        up = np.array([0.0, 0.0, 1.0])
        if abs(float(np.dot(t, up))) > 0.999:
            up = np.array([1.0, 0.0, 0.0])
        x = np.cross(up, t)
        x_axis[i] = x / np.linalg.norm(x)
    y_axis = np.cross(tan, x_axis)
    return tan, x_axis, y_axis


def tube_mesh(path_fn, width_fn, height_fn, twist_fn, closed,
              n_path=N_PATH, n_sect=N_SECT, super_n=2.6):
    """Superellipse tube around a parametric path. Returns (V, F)."""
    ts = np.linspace(0.0, 1.0, n_path, endpoint=not closed)
    pts = np.array([path_fn(t) for t in ts])
    tan, xa, ya = _frames(pts, closed)
    us = np.linspace(0.0, 2.0 * math.pi, n_sect, endpoint=False)
    cu, su = np.cos(us), np.sin(us)
    # superellipse radius profile (n=super_n gives the soft-square ribbon
    # sections the references show; probe-only-judgement)
    denom = (np.abs(cu) ** super_n + np.abs(su) ** super_n) ** (1.0 / super_n)
    verts = np.empty((len(ts), n_sect, 3), dtype=np.float64)
    for i, t in enumerate(ts):
        w = width_fn(t) / 2.0
        h = height_fn(t) / 2.0
        tw = math.radians(twist_fn(t))
        ct, st = math.cos(tw), math.sin(tw)
        px = (cu / denom) * w
        py = (su / denom) * h
        rx = px * ct - py * st
        ry = px * st + py * ct
        verts[i] = (pts[i][None, :] + rx[:, None] * xa[i][None, :]
                    + ry[:, None] * ya[i][None, :])
    V = verts.reshape(-1, 3)
    F = []
    rows = len(ts)
    last_row = rows if closed else rows - 1
    for i in range(last_row):
        i2 = (i + 1) % rows
        for j in range(n_sect):
            j2 = (j + 1) % n_sect
            a = i * n_sect + j
            b = i * n_sect + j2
            c = i2 * n_sect + j
            d = i2 * n_sect + j2
            F.append((a, b, d))
            F.append((a, d, c))
    if not closed:
        # triangle-fan caps (centroid vertex at each end)
        start_c = len(V)
        V = np.vstack([V, verts[0].mean(axis=0), verts[-1].mean(axis=0)])
        end_c = start_c + 1
        for j in range(n_sect):
            j2 = (j + 1) % n_sect
            F.append((start_c, verts[0].shape[0] * 0 + j2, j))
            base = (rows - 1) * n_sect
            F.append((end_c, base + j, base + j2))
    return V, np.array(F, dtype=np.int64)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

def fx_ref11_twist_tube():
    def path(t):
        return (150.0 * math.sin(3.1 * t * math.pi) * (1 - t * 0.4),
                -220.0 * math.sin(2.2 * t * math.pi),
                4000.0 * t)
    return tube_mesh(path,
                     width_fn=lambda t: 800.0 - 500.0 * t,
                     height_fn=lambda t: 220.0,
                     twist_fn=lambda t: 270.0 * t,
                     closed=False)


def fx_ref08_varying_loop():
    """Closed loop with a varying section -- trivial on this route, which
    is the comparative headline against the BREP multisection sweep."""
    def path(t):
        a = 2.0 * math.pi * t
        return (1150.0 * math.sin(a),
                140.0 * math.sin(2.0 * a),
                2050.0 + 1750.0 * math.cos(a))
    return tube_mesh(path,
                     width_fn=lambda t: 600.0 * (1.0 + 0.45 * math.sin(2.0 * math.pi * t)),
                     height_fn=lambda t: 380.0 / (1.0 + 0.45 * math.sin(2.0 * math.pi * t)),
                     twist_fn=lambda t: 30.0 * math.sin(2.0 * math.pi * t),
                     closed=True)


def fx_ref14_three_rings():
    """Three interlocked closed tubes. WITHOUT booleans they stay three
    disjoint bodies -- constructed deliberately to measure and record that
    limitation (validator will report body_count=3)."""
    def ring(center_z, tilt_deg, phase_deg):
        tilt = math.radians(tilt_deg)
        phase = math.radians(phase_deg)

        def path(t):
            a = 2.0 * math.pi * t + phase
            r = 950.0
            return (r * math.cos(a),
                    r * math.sin(a) * math.cos(tilt),
                    center_z + r * math.sin(a) * math.sin(tilt))
        return tube_mesh(path, lambda t: 300.0, lambda t: 200.0,
                         lambda t: 0.0, closed=True,
                         n_path=120, n_sect=36)

    parts = [ring(1700.0, 55.0, 0.0), ring(2300.0, -55.0, 120.0),
             ring(2000.0, 0.0, 60.0)]
    V = np.vstack([p[0] for p in parts])
    F = []
    off = 0
    for pv, pf in parts:
        F.append(pf + off)
        off += len(pv)
    return V, np.vstack(F)


FIXTURES = [
    ("ref11_twist_tube", fx_ref11_twist_tube, False),
    ("ref08_varying_loop", fx_ref08_varying_loop, False),
    ("ref14_three_rings", fx_ref14_three_rings, False),
]

#: Forms this route cannot build with the installed stack; recorded as
#: honest 'failed' rows so the capability matrix carries the gap.
NOT_CONSTRUCTIBLE = {
    "ref13_double_loop": ("needs boolean subtraction (hull minus void "
                          "tubes) or an implicit/SDF route; neither exists "
                          "in the installed stack (no CGAL/libigl/OpenVDB; "
                          "scikit-image marching cubes NOT installed)"),
    "ref16_split_rejoin": ("needs mesh boolean union of trunk+lobes with "
                           "a clean junction; no boolean machinery on "
                           "this route in the installed stack"),
}


def _glb_export(V, F, out_dir: Path, name: str) -> dict:
    import trimesh
    mesh = trimesh.Trimesh(vertices=V, faces=F, process=False)
    glb_path = out_dir / ("%s.glb" % name)
    mesh.export(str(glb_path))
    return {"file": glb_path.name, "sha256": sha256_file(glb_path)}


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
    for name, builder, expected_invalid in FIXTURES:
        try:
            V, F = builder()
            obj_path = out_dir / ("mesh_%s.obj" % name)
            obj_sha = write_canonical_obj(obj_path, V, F, name)
            bb = V.max(axis=0) - V.min(axis=0)
            entries.append(result_entry(
                name, "mesh", status="constructed",
                detail="parametric numpy tube generator, canonical OBJ",
                artifacts={
                    "obj": {"file": obj_path.name, "sha256": obj_sha},
                    "glb": _glb_export(V, F, out_dir, "mesh_%s" % name),
                },
                measures={
                    "vertex_count": int(len(V)),
                    "face_count": int(len(F)),
                    "bbox_mm": [round(float(b), 3) for b in bb],
                },
                expected_invalid=expected_invalid))
        except Exception:
            entries.append(result_entry(
                name, "mesh", status="failed",
                detail=traceback.format_exc(limit=4),
                expected_invalid=expected_invalid))

    for name, why in sorted(NOT_CONSTRUCTIBLE.items()):
        entries.append(result_entry(
            name, "mesh", status="failed",
            detail="not constructible on this route: %s" % why))

    write_results(out_dir, PROBE, entries, notes)
    print("%s: %d rows, %d constructed, %d failed/not-constructible"
          % (PROBE, len(entries),
             sum(1 for e in entries if e["status"] == "constructed"),
             sum(1 for e in entries if e["status"] == "failed")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
