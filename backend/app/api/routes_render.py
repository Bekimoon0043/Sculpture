"""Render job API (Phase 5).

POST /api/render/jobs        -> queue a render job for a design
GET  /api/render/jobs/{id}   -> poll status / result
GET  /api/render/jobs/{id}/views/{name} -> download a PNG
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db.database import get_default_db
from app.db.models import DesignRow
from app.render import DEFAULT_VIEWS, RenderView
from app.render.queue import ScratchRenderRunner, poll_render_job, submit_render_job

router = APIRouter(tags=["render"])


class _CreateJob(BaseModel):
    design_id: str = Field(..., min_length=1)
    views: list[dict[str, object]] | None = None


@router.post("/render/jobs")
def create_render_job(body: _CreateJob) -> dict[str, object]:
    """Queue a render job for an existing design.

    Renders from the design's GLB, not its STEP: Blender has no STEP importer
    (see docker/render/render_scene.py).  The GLB is the same tessellation the
    viewport already shows, so what the operator sees rendered is what they
    saw in the browser.
    """
    db = get_default_db()
    with db.get_session() as s:
        design = s.get(DesignRow, body.design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="design not found")
    mesh_path = design.glb_path
    if not mesh_path:
        raise HTTPException(
            status_code=400,
            detail=(
                f"design {body.design_id!r} has no GLB artifact to render; "
                "run the geometry build for this design first"
            ),
        )
    if not Path(mesh_path).exists():
        raise HTTPException(
            status_code=409,
            detail=(
                f"design {body.design_id!r} records a GLB at {mesh_path} but "
                "the file is missing on disk"
            ),
        )

    views = _parse_views(body.views) if body.views else DEFAULT_VIEWS
    job = submit_render_job(
        design_id=body.design_id,
        input_mesh=mesh_path,
        views=views,
    )
    return _job_to_response(job)


@router.get("/render/jobs/{job_id}")
def get_render_job(job_id: str) -> dict[str, object]:
    """Poll a queued render job; blocks up to a short timeout if still running."""
    result = poll_render_job(job_id, timeout_s=30.0)
    return {
        "id": job_id,
        "status": "done" if result.ok else "failed",
        "error": result.error,
        "views": [
            {"name": name, "path": str(path)}
            for name, path in result.views.items()
        ],
        "total_s": result.total_s,
    }


@router.get("/render/jobs/{job_id}/views/{view_name}")
def get_render_view(job_id: str, view_name: str):
    """Serve a rendered PNG."""
    runner = ScratchRenderRunner()
    path = runner._job_dir(job_id) / f"{view_name}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="render view not found")
    return FileResponse(path, media_type="image/png")


def _parse_views(raw: list[dict[str, object]]) -> list[RenderView]:
    views: list[RenderView] = []
    for item in raw:
        camera_str = str(item.get("camera", "ortho_front"))
        views.append(
            RenderView(
                name=str(item.get("name", "view")),
                camera=camera_str,  # type: ignore[arg-type]
                resolution=int(item.get("resolution", 1024)),
                samples=int(item.get("samples", 64)),
                time_budget_s=float(item.get("time_budget_s", 120.0)),
            )
        )
    return views


def _job_to_response(job) -> dict[str, object]:
    return {
        "id": job.id,
        "design_id": job.design_id,
        "status": job.status.value,
        "created_at": job.created_at,
        "views": [
            {
                "name": v.name,
                "camera": v.camera.value,
                "resolution": v.resolution,
                "samples": v.samples,
                "time_budget_s": v.time_budget_s,
            }
            for v in job.views
        ],
    }
