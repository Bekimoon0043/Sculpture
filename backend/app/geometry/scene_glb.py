"""Per-element named-node GLB — the designer workspace's pickable scene.

Phase 14. The canonical ``assembly.glb`` is one fused solid: correct for
validation and the export package, but nothing in it can be SELECTED — a
workspace viewport needs to know which triangles belong to which element.
This module writes ``scene.glb``: the same placed geometry, one GLB node
per element, node name == element_id.

Two deliberate properties:

* The geometry per element is tessellated by the SAME exporter at the SAME
  deflections as the fused preview GLB (exporters.py), so what the designer
  selects is what the validator meshed — no second tessellation policy.
* The fused ``assembly.glb`` and the STEP are untouched. ``scene.glb`` is a
  view for picking, outside the determinism contract exactly as the fused
  GLB already is (STEP remains the canonical artifact).

Composition goes through trimesh (already a dependency of the export
package): each element's single-solid GLB is loaded back and added to one
trimesh.Scene under its element_id, which trimesh writes into the glTF
node names. The auto gate parses the emitted binary and asserts the node
names match — the naming behaviour is PROVEN per build of the gate, not
assumed from documentation (ADR-009 spirit).
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

from app.geometry.exporters import export_glb


def export_scene_glb(solids: dict[str, Any], path: str | Path) -> str:
    """Write a GLB with one named node per element. Returns the file sha256.

    ``solids``: placed per-element solids from ``assemble(...,
    return_solids=True)``, keyed by element_id. Elements are composed in
    sorted id order (determinism of structure, not bytes).
    """
    import trimesh

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    scene = trimesh.Scene()
    with tempfile.TemporaryDirectory(prefix="scene_glb_") as tmp:
        for eid in sorted(solids):
            part_path = Path(tmp) / f"{eid}.glb"
            # Same exporter, same deflections as the fused preview GLB.
            export_glb(solids[eid], part_path)
            mesh = trimesh.load(str(part_path), file_type="glb", force="mesh")
            if mesh.is_empty:
                raise RuntimeError(
                    f"scene GLB: element {eid} tessellated to an empty mesh"
                )
            scene.add_geometry(mesh, node_name=eid, geom_name=eid)

    glb_bytes = scene.export(file_type="glb")
    path.write_bytes(glb_bytes)
    return hashlib.sha256(glb_bytes).hexdigest()
