"""PR-2.5 approach (c) input: deterministically GENERATE the import fixture.

SANDBOX-ONLY (ADR-005/ADR-064): constructs geometry; runs exclusively in
the geo-worker sandbox via scripts/run_pr25_discovery.py.

Owner clarification 6: the imported mesh must be an original,
repository-safe fixture that is deterministically generated before import,
with a pinned hash. This script IS that generator: a subdivided
icosahedron (2 levels, deterministic edge-key ordering) deformed by FIXED
sinusoidal harmonics (no RNG at all), scaled to a 3800 mm tall blob. It
is smooth and organic; it is deliberately NOT a mesh/lattice structure --
it does not and must not satisfy B-11b, which stays open.

The orchestrator runs this twice (once per pass) and the gate verifies the
two recorded hashes are identical and match the file bytes.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from probe_common import DISCOVERY_SEED, write_canonical_obj, write_results, result_entry

PROBE = "gen_import_fixture"


def icosahedron():
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    verts = [(-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0),
             (0, -1, phi), (0, 1, phi), (0, -1, -phi), (0, 1, -phi),
             (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1)]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
             (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
             (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
             (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    V = np.array(verts, dtype=np.float64)
    V /= np.linalg.norm(V, axis=1, keepdims=True)
    return V, faces


def subdivide(V, F):
    """One loop of midpoint subdivision projected to the unit sphere.
    Midpoint indices come from a dict keyed by SORTED vertex pairs and the
    dict is only ever read back through those same keys, so the vertex
    order is a pure function of the face list -- deterministic."""
    V = list(map(tuple, V))
    cache = {}

    def midpoint(a, b):
        key = (a, b) if a < b else (b, a)
        if key not in cache:
            va, vb = np.array(V[a]), np.array(V[b])
            m = (va + vb) / 2.0
            m /= np.linalg.norm(m)
            cache[key] = len(V)
            V.append(tuple(m))
        return cache[key]

    out = []
    for a, b, c in F:
        ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
        out += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
    return np.array(V, dtype=np.float64), out


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

    V, F = icosahedron()
    for _ in range(3):
        V, F = subdivide(V, F)

    # Fixed-harmonic organic deformation (no RNG; coefficients are the
    # fixture definition). r stays strictly positive.
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    theta = np.arctan2(y, x)
    phi_ang = np.arccos(np.clip(z, -1.0, 1.0))
    r = (1.0
         + 0.16 * np.sin(3.0 * theta) * np.sin(phi_ang) ** 2
         + 0.11 * np.cos(2.0 * theta + 1.0) * np.sin(2.0 * phi_ang)
         + 0.07 * np.cos(4.0 * phi_ang))
    V = V * r[:, None]

    # Scale to a 3800 mm tall organic blob (owner-ruled monumental band),
    # squashed 0.72 in Y so it reads as a form, not a sphere.
    z_extent = V[:, 2].max() - V[:, 2].min()
    V = V * (3800.0 / z_extent)
    V[:, 1] *= 0.72
    V[:, 2] -= V[:, 2].min()

    obj_path = out_dir / "import_fixture_blob.obj"
    sha = write_canonical_obj(obj_path, V, np.array(F, dtype=np.int64),
                              "import_fixture_blob")
    bb = V.max(axis=0) - V.min(axis=0)
    entries = [result_entry(
        "import_fixture_blob", "import", status="constructed",
        detail=("deterministic subdivided icosahedron + fixed harmonics; "
                "original repo-safe fixture; NOT a lattice, does not close "
                "B-11b"),
        artifacts={"obj": {"file": obj_path.name, "sha256": sha}},
        measures={"vertex_count": int(len(V)), "face_count": int(len(F)),
                  "bbox_mm": [round(float(b), 3) for b in bb]})]
    write_results(out_dir, PROBE, entries, [])
    print("%s: fixture sha256=%s" % (PROBE, sha))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
