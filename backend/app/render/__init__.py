"""Render orchestration (Phase 5 / Phase 9B).

The actual Cycles CPU rendering happens inside the separate `render-worker`
container (docker/render/Dockerfile).  This package only queues jobs on the
shared scratch mount and collects the resulting PNGs — the same handoff pattern
proven by app.council.fabricate and the geo-worker (ADR-005 / ADR-028).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class RenderStatus(str, Enum):
    """States a render job moves through."""

    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class RenderCamera(str, Enum):
    """Canonical camera rigs produced by the render worker."""

    ortho_front = "ortho_front"          # front elevation
    ortho_side = "ortho_side"              # left-side elevation
    ortho_top = "ortho_top"                # plan section
    perspective_3q = "perspective_3q"      # three-quarter perspective


@dataclass
class RenderView:
    """One view to render."""

    name: str
    camera: RenderCamera
    resolution: int = 1024
    samples: int = 64
    time_budget_s: float = 120.0


@dataclass
class RenderJob:
    """In-memory representation of a queued render job."""

    id: str
    design_id: str
    #: Tessellated mesh (GLB) the render worker imports. NOT a STEP file:
    #: Blender has no STEP importer, and the render image deliberately
    #: carries no OCCT (docker/render/render_scene.py explains why).
    input_mesh: str
    views: list[RenderView]
    status: RenderStatus = RenderStatus.queued
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: dict[str, Any] | None = None
    error: str | None = None


DEFAULT_VIEWS: list[RenderView] = [
    RenderView(name="front", camera=RenderCamera.ortho_front),
    RenderView(name="side", camera=RenderCamera.ortho_side),
    RenderView(name="top", camera=RenderCamera.ortho_top),
    RenderView(name="three_quarter", camera=RenderCamera.perspective_3q),
]


__all__ = [
    "RenderStatus",
    "RenderCamera",
    "RenderView",
    "RenderJob",
    "DEFAULT_VIEWS",
]
