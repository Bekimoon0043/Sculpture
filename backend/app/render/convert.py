"""Blender-backed format conversion — backend side (Phase 9B.5).

USD, USDZ, FBX and Alembic are the four export formats nothing else in this
stack can write. OCCT does not produce them and trimesh does not produce them;
Blender does, and Phase 9B put Blender in the system. This module is the
bridge between `app.geometry.export_formats` and the render worker.

It reuses the render handoff exactly: a job directory on the shared scratch
mount, a staged input mesh, basenames only in both directions, and a
`result.json` written atomically as the completion signal. The only
difference is `"kind": "convert"` in the manifest.

DEGRADING HONESTLY
------------------
The render worker is an optional service behind a compose profile. If it is
not running, conversion must not hang and must not raise something that reads
like a bug in the exporter. `convert_via_worker` returns an empty mapping and
a plain-language reason, which `write_exports` turns back into the same
`unavailable` status these four formats have always had — with a reason that
tells the operator the one command that fixes it.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
import uuid
from pathlib import Path

from app.render.queue import scratch_dir

log = logging.getLogger("luxuryform.render.convert")

#: The formats convert_scene.py can write. Anything else is a programming
#: error on the backend side, not an operator-facing condition.
CONVERTIBLE = ("USD", "USDZ", "FBX", "ABC")

#: Per-format allowance, matched to the worker's own budget. Alembic and FBX
#: are seconds; USDZ is the slowest because it packages.
DEFAULT_TIMEOUT_PER_FORMAT_S = 120.0

#: How long to wait for the worker to notice the job at all. A worker that is
#: not running never will, and the operator should be told in seconds rather
#: than after a full conversion budget has elapsed.
PICKUP_TIMEOUT_S = 20.0

POLL_S = 0.5


class ConversionUnavailable(RuntimeError):
    """The worker could not be reached. Carries an operator-facing reason."""


def convert_via_worker(
    mesh_path: Path,
    formats: list[str],
    *,
    timeout_s: float | None = None,
    root: Path | None = None,
) -> dict[str, Path]:
    """Convert `mesh_path` into `formats`; return {FORMAT: produced file}.

    Raises ConversionUnavailable if the render worker never picks the job up.
    Formats the worker failed on are simply absent from the mapping — a
    partial result is still worth shipping, and the caller reports per format.
    """
    wanted = [f.upper() for f in formats]
    unknown = [f for f in wanted if f not in CONVERTIBLE]
    if unknown:
        raise ValueError(
            f"not Blender-convertible: {', '.join(unknown)}; "
            f"this path writes {', '.join(CONVERTIBLE)}"
        )
    mesh_path = Path(mesh_path)
    if not mesh_path.exists():
        raise FileNotFoundError(f"mesh to convert does not exist: {mesh_path}")

    root = root or scratch_dir()
    job_id = "conv" + uuid.uuid4().hex[:12]
    job_dir = root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(job_dir, 0o777)
    except OSError:
        pass  # Windows bind mounts use synthetic permissions

    staged = job_dir / f"input{mesh_path.suffix.lower() or '.glb'}"
    shutil.copyfile(mesh_path, staged)

    manifest = {
        "kind": "convert",
        "design_id": job_id,
        # BASENAME: the worker sees this directory at a different absolute
        # path than we do (app.render.queue explains why).
        "input_mesh": staged.name,
        "formats": wanted,
        "output_dir": str(job_dir),
    }
    # job.json last: it is what makes the worker pick the directory up, so
    # the input must already be staged when it appears.
    (job_dir / "job.json").write_text(json.dumps(manifest, sort_keys=True),
                                      encoding="utf-8")

    budget = timeout_s or (len(wanted) * DEFAULT_TIMEOUT_PER_FORMAT_S)
    result_path = job_dir / "result.json"
    claimed_path = job_dir / ".claimed"

    deadline = time.monotonic() + budget + PICKUP_TIMEOUT_S
    pickup_deadline = time.monotonic() + PICKUP_TIMEOUT_S
    claimed = False
    while time.monotonic() < deadline:
        if result_path.exists():
            break
        if not claimed and claimed_path.exists():
            claimed = True  # worker is alive; the full budget now applies
        if not claimed and time.monotonic() > pickup_deadline:
            raise ConversionUnavailable(
                "the render worker did not pick up the conversion job within "
                f"{PICKUP_TIMEOUT_S:.0f}s; start it with "
                "'docker compose --profile render up -d render-worker'"
            )
        time.sleep(POLL_S)
    else:
        raise ConversionUnavailable(
            f"the render worker claimed the job but produced no result within "
            f"{budget:.0f}s"
        )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    produced: dict[str, Path] = {}
    for entry in payload.get("formats", []):
        if not entry.get("ok"):
            log.warning("convert %s failed: %s", entry.get("format"),
                        entry.get("error"))
            continue
        path = job_dir / Path(entry["path"]).name
        if path.exists() and path.stat().st_size > 0:
            produced[entry["format"]] = path
        else:
            log.warning("convert %s claimed success but %s is missing/empty",
                        entry.get("format"), path)
    return produced


__all__ = ["convert_via_worker", "ConversionUnavailable", "CONVERTIBLE"]
