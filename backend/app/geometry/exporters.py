"""Canonical exporters — STEP (deterministic) and GLB (viewport/viewer).

ADR-009/ADR-010: both use build123d 0.11.1 NATIVE export functions, verified
against live docs fetched 2026-08-01 and against the installed package:
  export_step(to_export, file_path, ..., *, timestamp: str|datetime|None=None)
  export_gltf(to_export, file_path, unit=Unit.MM, binary=False,
              linear_deflection=0.001, angular_deflection=0.1)

STEP determinism (Amendment 1): the STEP header normally embeds a wall-clock
timestamp, which would defeat byte-identical output. We ALWAYS inject the
seed-derived timestamp from kernel.step_timestamp_for — no export without it.

GLB deflection: the live-doc default linear_deflection=0.001 (mm) would
tessellate a 2.6 m fountain into tens of millions of triangles. We export at
linear_deflection=GLB_LINEAR_DEFLECTION_MM (1 mm) — visually smooth at
fountain scale, well under the 1M-triangle viewport budget (PHASE2_PLAN §7).
The canonical artifact is STEP; the GLB is a preview/validation mesh
(LIMITATIONS.md).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from build123d import Solid, export_gltf, export_step as _b123d_export_step

from app.geometry.canonicalize import canonicalize_step_file

#: Tessellation tolerance for the preview/validation GLB, in mm.
GLB_LINEAR_DEFLECTION_MM = 1.0
GLB_ANGULAR_DEFLECTION_RAD = 0.1


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_step(solid: Solid, path: str | Path, timestamp: str | datetime) -> str:
    """Write the canonical STEP file with an injected header timestamp.

    The timestamp MUST come from kernel.step_timestamp_for(seed) — that is
    what makes (spec, seed) -> byte-identical STEP. Returns the file sha256.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _b123d_export_step(solid, str(path), timestamp=timestamp)
    # OCCT numbers assembly occurrences from a PROCESS-global counter, so a
    # second export of the same solid in the same process differs in one
    # label. Renumber per file (canonicalize.py) — metadata only, and a
    # first-in-process export is unchanged, so the Phase 2 canonical hash
    # still reproduces byte-for-byte.
    canonicalize_step_file(path)
    return _sha256(path)


def export_glb(solid: Solid, path: str | Path) -> str:
    """Write binary glTF (GLB) via build123d's native export_gltf(binary=True).

    Returns the file sha256. GLB bytes are NOT part of the determinism
    guarantee (LIMITATIONS.md) — STEP is the canonical artifact.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    export_gltf(
        solid,
        str(path),
        binary=True,
        linear_deflection=GLB_LINEAR_DEFLECTION_MM,
        angular_deflection=GLB_ANGULAR_DEFLECTION_RAD,
    )
    return _sha256(path)
