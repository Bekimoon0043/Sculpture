"""Scene + camera rig documentation for the render worker.

The actual Blender scene setup lives in ``docker/render/render_scene.py``
because it runs inside the render-worker container, not inside the backend
Python environment.  This module documents the rig and provides any backend-
side helpers that prepare scene parameters.
"""

from __future__ import annotations

import math

from app.render import RenderCamera


#: Canonical views rendered for every critique round.
CAMERA_DESCRIPTIONS: dict[RenderCamera, dict[str, object]] = {
    RenderCamera.ortho_front: {
        "type": "orthographic",
        "direction": (0.0, -1.0, 0.0),   # looking along -Y
        "up": (0.0, 0.0, 1.0),
        "name": "front",
    },
    RenderCamera.ortho_side: {
        "type": "orthographic",
        "direction": (-1.0, 0.0, 0.0),   # looking along -X
        "up": (0.0, 0.0, 1.0),
        "name": "side",
    },
    RenderCamera.ortho_top: {
        "type": "orthographic",
        "direction": (0.0, 0.0, -1.0),   # looking down
        "up": (0.0, -1.0, 0.0),
        "name": "top",
    },
    RenderCamera.perspective_3q: {
        "type": "perspective",
        "direction": (1.0, -1.0, 0.6),   # three-quarter
        "up": (0.0, 0.0, 1.0),
        "name": "three_quarter",
    },
}


def camera_distance_for_bbox(size_x: float, size_y: float, size_z: float,
                             camera: RenderCamera) -> float:
    """Return a camera-to-target distance that frames the design.

    For orthographic cameras the distance only affects clipping; for
    perspective cameras it controls how much of the view the object fills.
    """
    diag = math.sqrt(size_x ** 2 + size_y ** 2 + size_z ** 2)
    if camera == RenderCamera.perspective_3q:
        return diag * 1.4
    return diag * 1.2


__all__ = ["CAMERA_DESCRIPTIONS", "camera_distance_for_bbox"]
