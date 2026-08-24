"""Render job queue — backend side.

Writes job manifests to the render scratch mount that the render-worker
container watches, then polls for result.json.

Protocol (container-side):
  in:  <scratch>/<job_id>/job.json
       {
         "design_id": str,
         "input_mesh": str,          # BASENAME, e.g. "input.glb" (see below)
         "views": [{"name": str, "camera": str, "resolution": int,
                    "samples": int, "time_budget_s": float}],
         "output_dir": str             # <scratch>/<job_id>/ (worker writes here)
       }
  out: <scratch>/<job_id>/result.json
       {"ok": bool, "error": str|None,
        "views": [{"name": str, "path": str, "elapsed_s": float}],
        "total_s": float}
  out: <scratch>/<job_id>/<name>.png

ADR-028 shape, with one deliberate difference: the backend and render-worker
bind the SAME host directory, but at DIFFERENT in-container paths, because
/scratch on the backend is already the geo-worker's mount.  See below.

WHY THE MESH IS COPIED INTO THE JOB DIRECTORY, AND WHY BASENAMES
-----------------------------------------------------------------
The backend keeps design artifacts under /app/data, which the render worker
does NOT mount.  Pointing the worker at the backend's own artifact path would
hand it a filename it cannot open.  So `submit()` stages the mesh into the job
directory, and the manifest names that copy.  Staging also pins the job to the
geometry as it was at submit time: a re-export midway through a critique round
cannot change what an already-queued job renders.

The two containers see the shared directory at DIFFERENT in-container paths --
the backend at /render_scratch, the worker at /scratch -- because /scratch is
already the geo-worker's mount on the backend.  So unlike the geo handoff,
absolute paths do NOT cross verbatim here.  Every filename in the protocol is
therefore a BASENAME, resolved by each side against its own view of the job
directory.  That is the one rule keeping this handoff correct; do not put an
absolute path into job.json or result.json.

The mesh is a GLB, not the STEP.  Blender cannot import STEP and this image
carries no OCCT (docker/render/render_scene.py).  The GLB is the same
tessellation the viewport already uses (app.geometry.exporters.export_glb).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.render import RenderJob, RenderStatus, RenderView

log = logging.getLogger("luxuryform.render")

#: Backstop if the render worker never answers.
DEFAULT_POLL_S = 0.5
DEFAULT_MARGIN_S = 60.0


def scratch_dir() -> Path:
    """Shared render scratch mount.

    Environment override: LUXURYFORM_RENDER_SCRATCH (set by compose to
    /scratch).  Fallback for local dev: <repo>/data/render_scratch.
    """
    from app.core.config import REPO_ROOT

    explicit = os.environ.get("LUXURYFORM_RENDER_SCRATCH")
    if explicit:
        return Path(explicit)
    return Path(
        os.environ.get("LUXURYFORM_DATA_DIR", str(REPO_ROOT / "data"))
    ) / "render_scratch"


@dataclass
class RenderResult:
    """Collected result of a render job."""

    ok: bool
    error: str | None = None
    views: dict[str, Path] = field(default_factory=dict)
    total_s: float = 0.0


class RenderRunner(Protocol):
    """Backend abstraction over the render worker handoff.

    Production uses the real scratch mount; tests inject a scripted runner so
    the orchestration is provable offline at $0.
    """

    def submit(self, job: RenderJob) -> None: ...

    def collect(self, job_id: str, timeout_s: float) -> RenderResult: ...


class ScratchRenderRunner:
    """Production runner: queue on scratch, wait for render-worker result."""

    def __init__(
        self,
        root: Path | None = None,
        poll_s: float = DEFAULT_POLL_S,
    ) -> None:
        self._root = root or scratch_dir()
        self._poll_s = poll_s

    def _job_dir(self, job_id: str) -> Path:
        return self._root / job_id

    def submit(self, job: RenderJob) -> None:
        job_dir = self._job_dir(job_id=job.id)
        job_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(job_dir, 0o777)
        except OSError:
            pass  # Windows bind mounts use synthetic permissions

        source = Path(job.input_mesh)
        if not source.exists():
            raise FileNotFoundError(
                f"render input mesh {source} does not exist; export the design "
                "before queueing a render"
            )
        staged = job_dir / f"input{source.suffix.lower() or '.glb'}"
        shutil.copyfile(source, staged)
        views_json = [
            {
                "name": v.name,
                "camera": v.camera.value,
                "resolution": v.resolution,
                "samples": v.samples,
                "time_budget_s": v.time_budget_s,
            }
            for v in job.views
        ]
        manifest = {
            "design_id": job.design_id,
            # BASENAME only -- the worker sees this directory at a different
            # absolute path (see the module docstring).
            "input_mesh": staged.name,
            "views": views_json,
            # Advisory only: the worker writes into its own view of the job
            # directory. Kept for operators reading job.json by hand.
            "output_dir": str(job_dir),
        }
        (job_dir / "job.json").write_text(
            json.dumps(manifest, sort_keys=True), encoding="utf-8"
        )
        log.info("render job %s queued at %s", job.id, job_dir)

    def collect(self, job_id: str, timeout_s: float) -> RenderResult:
        job_dir = self._job_dir(job_id=job_id)
        result_path = job_dir / "result.json"
        deadline = time.monotonic() + timeout_s + DEFAULT_MARGIN_S
        while time.monotonic() < deadline:
            if result_path.exists():
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                return self._resolve(job_dir, payload)
            time.sleep(self._poll_s)
        return RenderResult(
            ok=False,
            error=(
                f"render-worker produced no result within {timeout_s + DEFAULT_MARGIN_S:.0f}s — "
                "is the render-worker container running? (docker compose ps render-worker)"
            ),
        )

    def _resolve(self, job_dir: Path, payload: dict[str, Any]) -> RenderResult:
        if not payload.get("ok"):
            return RenderResult(
                ok=False,
                error=payload.get("error") or "render worker reported failure with no error",
            )
        views: dict[str, Path] = {}
        missing: list[str] = []
        for v in payload.get("views", []):
            name = v["name"]
            basename = Path(v["path"]).name
            path = job_dir / basename
            if not path.exists():
                missing.append(f"{name} -> {path}")
            views[name] = path
        if missing:
            return RenderResult(
                ok=False,
                error="render result references files the backend cannot see: " + "; ".join(missing),
            )
        return RenderResult(
            ok=True,
            views=views,
            total_s=float(payload.get("total_s", 0.0)),
        )


def submit_render_job(
    design_id: str,
    input_mesh: str,
    views: list[RenderView] | None = None,
    runner: RenderRunner | None = None,
) -> RenderJob:
    """Queue a render job and return its handle."""
    job_id = uuid.uuid4().hex[:16]
    job = RenderJob(
        id=job_id,
        design_id=design_id,
        input_mesh=input_mesh,
        views=views or [],
    )
    (runner or ScratchRenderRunner()).submit(job)
    return job


def poll_render_job(job_id: str, timeout_s: float = 120.0,
                    runner: RenderRunner | None = None) -> RenderResult:
    """Block until a render job finishes or times out."""
    return (runner or ScratchRenderRunner()).collect(job_id, timeout_s)
