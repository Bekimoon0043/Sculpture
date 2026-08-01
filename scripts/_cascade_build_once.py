#!/usr/bin/env python3
"""Build the cascade ONCE and export its canonical STEP (gate helper).

Usage:
    python scripts/_cascade_build_once.py <out.step> <seed> [params-json]

Prints exactly:
    sha256=<step file sha256>
    spec_hash=<canonical spec hash>

Run TWICE as separate processes by gate_phase2_auto.py section 2 to prove
Amendment 1 byte-determinism across processes (never two calls in one).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.geometry import GeometryBuild, export_step, validate_params  # noqa: E402


def main() -> int:
    out = Path(sys.argv[1])
    seed = int(sys.argv[2])
    raw = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    params = validate_params(raw)
    build = GeometryBuild(seed, params)
    solid = build.build()
    sha = export_step(solid, out, build.step_timestamp)
    print(f"sha256={sha}")
    print(f"spec_hash={build.spec_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
