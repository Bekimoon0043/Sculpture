"""PR-2.5 approach (c): human-authored reference-mesh import and fitting.

SANDBOX-ONLY (ADR-005/ADR-064): runs exclusively in the geo-worker
sandbox via scripts/run_pr25_discovery.py.

Reads the deterministically generated fixture (gen_import_fixture.py must
have run into the same pass directory first), validates it, fits it to a
target envelope (uniform scale to a 4200 mm height, the kind of operation
a real imported artist mesh would need), and re-exports canonically. The
question this probe answers is narrow: can an imported mesh be validated,
deterministically transformed and canonically re-serialized by the
installed stack? It says NOTHING about where trustworthy artist meshes
would come from -- that trust problem is discussed in the report, and
B-11b (real mesh/lattice reference) stays open.
"""

from __future__ import annotations

import argparse
import traceback
from pathlib import Path

import numpy as np

from probe_common import (DISCOVERY_SEED, result_entry, sha256_file,
                          write_canonical_obj, write_results)

PROBE = "probe_freeform_import"

TARGET_HEIGHT_MM = 4200.0  # owner-ruled monumental band (3500-5000 mm)


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
    src = out_dir / "import_fixture_blob.obj"
    try:
        import trimesh
        if not src.exists():
            raise FileNotFoundError(
                "import fixture missing at %s -- gen_import_fixture.py must "
                "run into this pass directory first" % src)
        src_sha = sha256_file(src)
        mesh = trimesh.load(str(src), file_type="obj", process=False)
        V = np.asarray(mesh.vertices, dtype=np.float64)
        F = np.asarray(mesh.faces, dtype=np.int64)

        z_extent = float(V[:, 2].max() - V[:, 2].min())
        scale = TARGET_HEIGHT_MM / z_extent
        V_fit = V * scale
        V_fit[:, 2] -= V_fit[:, 2].min()

        obj_path = out_dir / "import_fitted_blob.obj"
        fitted_sha = write_canonical_obj(obj_path, V_fit, F,
                                         "import_fitted_blob")
        glb_path = out_dir / "import_fitted_blob.glb"
        trimesh.Trimesh(vertices=V_fit, faces=F,
                        process=False).export(str(glb_path))
        bb = V_fit.max(axis=0) - V_fit.min(axis=0)
        entries.append(result_entry(
            "import_fitted_blob", "import", status="constructed",
            detail=("loaded fixture (sha256=%s), uniform-scaled %.6f to "
                    "%.0f mm height, canonical re-export" %
                    (src_sha, scale, TARGET_HEIGHT_MM)),
            artifacts={
                "obj": {"file": obj_path.name, "sha256": fitted_sha},
                "glb": {"file": glb_path.name,
                        "sha256": sha256_file(glb_path)},
                "source_obj": {"file": src.name, "sha256": src_sha},
            },
            measures={
                "vertex_count": int(len(V_fit)),
                "face_count": int(len(F)),
                "bbox_mm": [round(float(b), 3) for b in bb],
                "watertight_at_load": bool(mesh.is_watertight),
            }))
    except Exception:
        entries.append(result_entry(
            "import_fitted_blob", "import", status="failed",
            detail=traceback.format_exc(limit=4)))

    write_results(out_dir, PROBE, entries, [])
    print("%s: %s" % (PROBE, entries[0]["status"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
