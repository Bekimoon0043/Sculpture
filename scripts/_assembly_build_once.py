#!/usr/bin/env python3
"""Build the slice-A1 gate assembly ONCE and export STEP — determinism probe.

Called by gate_phase6a1_auto.py in TWO SEPARATE PROCESSES; each prints the
STEP sha256 so the gate can prove byte-identical assembly export across
process boundaries (Amendment 1 carried into Phase 6).

usage: python _assembly_build_once.py <out.step> <seed>
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

# The canonical gate composition — MUST stay identical to the plan in
# gate_phase6a1_auto.py (it imports this constant, so it cannot drift).
GATE_PLAN = [
    {"element_id": "p1", "primitive": "plinth",
     "parameters": {"top_diameter_mm": 700, "height_mm": 300,
                    "taper_deg": 5, "material_id": "basalt_slab"}},
    {"element_id": "b1", "primitive": "basin_round",
     "parameters": {"diameter_mm": 600, "height_mm": 300, "wall_mm": 25,
                    "floor_mm": 60, "material_id": "basalt_slab"},
     "joint": {"type": "stack_on", "parent": "p1"}},
    {"element_id": "c1", "primitive": "sculptural_column",
     "parameters": {"diameter_mm": 100, "height_mm": 400,
                    "material_id": "basalt_slab"},
     "joint": {"type": "concentric_insert", "parent": "b1"}},
]


def main(out_path: str, seed: int) -> int:
    from app.geometry.assembly import assemble
    from app.geometry.exporters import export_step
    from app.geometry.kernel import step_timestamp_for

    solid, manifest = assemble(GATE_PLAN, seed=seed)
    sha = export_step(solid, out_path, step_timestamp_for(seed))
    print(f"elements={len(manifest['elements'])} joints={len(manifest['joints'])} "
          f"volume_mm3={manifest['volume_conservation']['assembly_volume_mm3']:.3f}")
    print(f"sha256={sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], int(sys.argv[2])))
