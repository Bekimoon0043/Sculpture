"""Render worker: watches the scratch mount and drives Blender (Phase 9B).

    python render_worker.py /scratch

Runs under the container's SYSTEM CPython, not Blender's. It must never
import bpy -- the scene script (render_scene.py) is the only thing that does,
and it is launched as a subprocess. Keeping the two apart means a Blender
crash is an exit code this process can report, not a process that takes the
worker down with it.

Stdlib only, on purpose: no pip install in this image, so no PyPI outage or
resolver change can ever break the renderer.

PROTOCOL (the backend side is backend/app/render/queue.py)
----------------------------------------------------------
  in   <scratch>/<job_id>/job.json
       {"design_id", "input_mesh", "views": [...], "output_dir"}
       input_mesh is a BASENAME inside the job directory, never an absolute
       path -- the backend mounts this same host directory at a DIFFERENT
       in-container path (/render_scratch), so an absolute path written by
       the backend would not resolve here. Everything is resolved against
       job_dir on both sides.
  out  <scratch>/<job_id>/<view>.png
  out  <scratch>/<job_id>/result.json
       {"ok", "error", "views": [{"name","path","elapsed_s"}], "total_s"}

result.json is written LAST and written ATOMICALLY (temp file + os.replace),
because the backend polls for its existence as the completion signal. A
half-written result.json would be parsed as a finished job.

ADR-028 shape: backend and worker bind the SAME host directory. They do NOT
see it at the same in-container path (the backend's /scratch is already the
geo-worker's), which is exactly why the protocol is basename-only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

BLENDER_BIN = os.environ.get("BLENDER_BIN", "/usr/local/bin/blender")
SCENE_SCRIPT = Path(__file__).resolve().parent / "render_scene.py"
CONVERT_SCRIPT = Path(__file__).resolve().parent / "convert_scene.py"

#: How often to rescan for new job directories.
POLL_S = float(os.environ.get("LUXURYFORM_RENDER_POLL_S", "0.5"))

#: Cycles threads. Defaults to 2: the operator's i7-8550U has 4 physical
#: cores and the backend + geo-worker also want CPU. Overridable per host.
RENDER_THREADS = int(os.environ.get("LUXURYFORM_RENDER_THREADS", "2"))

#: Added to the summed per-view budgets before the subprocess is killed.
#: Covers Blender start-up, GLB import and the denoise pass, none of which
#: belong to any single view's budget.
TIMEOUT_MARGIN_S = 90.0


def log(msg):
    print("[render_worker] %s" % msg, flush=True)


def write_atomic(path: Path, payload: dict) -> None:
    """Write JSON so a reader never observes a partial file."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def run_blender(script: Path, spec_path: Path, job_dir: Path,
                timeout: float, log_name: str):
    """Run one Blender script as a subprocess.

    Returns (ok, error). Blender's full output always lands in the job
    directory: when a conversion or render fails, the reason is in there and
    nowhere else, and the operator should not have to reproduce the failure
    to read it.
    """
    cmd = [BLENDER_BIN, "-b", "--factory-startup",
           "--python", str(script), "--", str(spec_path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, ("blender exceeded the %.0fs budget for this job and "
                       "was killed" % timeout)
    except FileNotFoundError:
        return False, "blender binary not found at %s" % BLENDER_BIN

    (job_dir / log_name).write_text(
        (proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or ""),
        encoding="utf-8")

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-12:]
        return False, ("blender exited %d: %s"
                       % (proc.returncode, " | ".join(tail)))
    return True, None


#: Formats convert_scene.py knows how to write. Kept here so the worker can
#: reject an unknown one before paying for a Blender launch.
CONVERT_FORMATS = ("USD", "USDZ", "FBX", "ABC")

#: Per-format allowance before Blender is killed, plus start-up margin.
CONVERT_TIMEOUT_PER_FORMAT_S = 120.0


def run_convert(job_dir: Path, manifest: dict, mesh_path: Path,
                started: float) -> dict:
    """Convert one mesh into the Blender-only export formats."""
    wanted = [str(f).upper() for f in (manifest.get("formats") or [])]
    if not wanted:
        return {"ok": False, "formats": [], "total_s": 0.0,
                "error": "convert job lists no formats"}
    unknown = [f for f in wanted if f not in CONVERT_FORMATS]
    if unknown:
        return {"ok": False, "formats": [], "total_s": 0.0,
                "error": "unknown format(s) %s; this worker writes %s"
                         % (", ".join(unknown), ", ".join(CONVERT_FORMATS))}

    spec = {"input_mesh": str(mesh_path),
            "output_dir": str(job_dir),
            "formats": wanted}
    spec_path = job_dir / "convert_spec.json"
    spec_path.write_text(json.dumps(spec, sort_keys=True), encoding="utf-8")

    timeout = len(wanted) * CONVERT_TIMEOUT_PER_FORMAT_S + TIMEOUT_MARGIN_S
    log("job %s: convert %s, timeout %.0fs"
        % (job_dir.name, ",".join(wanted), timeout))

    ok, error = run_blender(CONVERT_SCRIPT, spec_path, job_dir, timeout,
                            "blender_convert.log")
    if not ok:
        return {"ok": False, "formats": [], "total_s": time.time() - started,
                "error": error}

    produced = job_dir / "convert.json"
    if not produced.exists():
        return {"ok": False, "formats": [], "total_s": time.time() - started,
                "error": ("blender exited 0 but wrote no convert.json -- see "
                          "blender_convert.log in the job directory")}

    results = json.loads(produced.read_text(encoding="utf-8")).get("results", [])

    # Verify rather than trust: confirm each claimed file is really on disk
    # and non-empty. A format that claims success but produced nothing would
    # otherwise be shipped in an export package as a broken file.
    for entry in results:
        if not entry.get("ok"):
            continue
        out = job_dir / Path(entry["path"]).name
        if not out.exists() or out.stat().st_size == 0:
            entry["ok"] = False
            entry["error"] = "exporter claimed success but wrote no usable file"

    succeeded = [r for r in results if r.get("ok")]
    # Partial success is still success: the caller is told per format, and one
    # unwritable format must not deny the operator the other three.
    return {"ok": bool(succeeded), "formats": results,
            "total_s": round(time.time() - started, 3),
            "error": None if succeeded else "no format converted successfully"}


def run_job(job_dir: Path) -> dict:
    """Run one job. Returns the result payload (never raises).

    Two kinds, dispatched on manifest["kind"]:
      "render"  (default) -- four canonical views, render_scene.py
      "convert" -- USD/USDZ/FBX/ABC, convert_scene.py
    The default is "render" so a manifest written before convert existed
    still means what it meant.
    """
    started = time.time()
    try:
        manifest = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": "unreadable job.json: %s" % exc,
                "views": [], "total_s": 0.0}

    kind = manifest.get("kind", "render")
    if kind not in ("render", "convert"):
        return {"ok": False, "views": [], "total_s": 0.0,
                "error": "unknown job kind %r (expected 'render' or 'convert')"
                         % kind}

    # `input_step` is accepted for one reason only: to give a job written by
    # an older backend a clear error instead of a KeyError. Blender has no
    # STEP importer -- see render_scene.py.
    mesh = manifest.get("input_mesh")
    if not mesh:
        legacy = manifest.get("input_step")
        if legacy:
            return {"ok": False, "views": [], "total_s": 0.0,
                    "error": ("job.json supplies 'input_step' (%s) but Blender "
                              "cannot import STEP; the backend must send "
                              "'input_mesh' pointing at the assembly GLB"
                              % legacy)}
        return {"ok": False, "error": "job.json has no 'input_mesh'",
                "views": [], "total_s": 0.0}

    # Resolve against OUR view of the job directory, and take only the
    # basename: an absolute path from the backend names a mount point that
    # does not exist in this container.
    mesh_path = job_dir / Path(mesh).name
    if not mesh_path.exists():
        return {"ok": False, "views": [], "total_s": 0.0,
                "error": ("input mesh %r is not in the job directory %s; the "
                          "backend must stage it there before queueing"
                          % (Path(mesh).name, job_dir))}

    if kind == "convert":
        return run_convert(job_dir, manifest, mesh_path, started)

    views = manifest.get("views") or []
    if not views:
        return {"ok": False, "error": "job.json lists no views",
                "views": [], "total_s": 0.0}

    # The manifest's output_dir is advisory (it holds the BACKEND's path for
    # this directory, which is not valid here). We always write into our own.
    out_dir = job_dir
    spec = {
        "input_mesh": str(mesh_path),
        "output_dir": str(out_dir),
        "views": views,
        "threads": RENDER_THREADS,
        # Fixed seed: Cycles' sampling pattern is then identical between
        # rounds, so a visible difference between two renders comes from the
        # geometry changing and not from noise.
        "seed": int(manifest.get("seed", 0)),
    }
    spec_path = job_dir / "scene_spec.json"
    spec_path.write_text(json.dumps(spec, sort_keys=True), encoding="utf-8")

    budget = sum(float(v.get("time_budget_s", 120.0)) for v in views)
    timeout = budget + TIMEOUT_MARGIN_S

    log("job %s: %d view(s), timeout %.0fs" % (job_dir.name, len(views), timeout))

    ok, error = run_blender(SCENE_SCRIPT, spec_path, job_dir, timeout,
                            "blender.log")
    if not ok:
        return {"ok": False, "views": [], "total_s": time.time() - started,
                "error": error}

    views_json = out_dir / "views.json"
    if not views_json.exists():
        return {"ok": False, "views": [], "total_s": time.time() - started,
                "error": ("blender exited 0 but wrote no views.json -- see "
                          "blender.log in the job directory")}

    produced = json.loads(views_json.read_text(encoding="utf-8"))
    rendered = produced.get("views", [])

    # Do not take the scene script's word for it: confirm every promised PNG
    # exists and is a real PNG. A zero-byte or truncated file here would
    # otherwise reach a vision API and be billed for.
    missing = []
    for view in rendered:
        png = out_dir / Path(view["path"]).name
        if not png.exists() or png.stat().st_size == 0:
            missing.append(view["name"])
            continue
        with open(png, "rb") as fh:
            if fh.read(8) != b"\x89PNG\r\n\x1a\n":
                missing.append("%s (not a PNG)" % view["name"])
    if missing:
        return {"ok": False, "views": [], "total_s": time.time() - started,
                "error": "views did not produce a valid PNG: %s"
                         % ", ".join(missing)}

    return {"ok": True, "error": None, "views": rendered,
            "bbox": produced.get("bbox"),
            "total_s": round(time.time() - started, 3)}


def claim(job_dir: Path) -> bool:
    """Take ownership of a job directory exactly once.

    A marker file created with O_EXCL is the claim. Without it, a worker
    restarted mid-job would re-render work already in flight.
    """
    marker = job_dir / ".claimed"
    try:
        fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.close(fd)
    return True


def main(argv):
    if len(argv) < 2:
        raise SystemExit("usage: render_worker.py <scratch_dir>")
    scratch = Path(argv[1])
    scratch.mkdir(parents=True, exist_ok=True)

    for script in (SCENE_SCRIPT, CONVERT_SCRIPT):
        if not script.exists():
            raise SystemExit("blender script missing at %s" % script)
    if not shutil.which(BLENDER_BIN) and not Path(BLENDER_BIN).exists():
        raise SystemExit("blender not found at %s" % BLENDER_BIN)

    log("watching %s (blender=%s, threads=%d)"
        % (scratch, BLENDER_BIN, RENDER_THREADS))

    while True:
        try:
            for job_dir in sorted(p for p in scratch.iterdir() if p.is_dir()):
                if not (job_dir / "job.json").exists():
                    continue
                if (job_dir / "result.json").exists():
                    continue
                if not claim(job_dir):
                    continue
                try:
                    result = run_job(job_dir)
                except Exception:
                    result = {"ok": False, "views": [], "total_s": 0.0,
                              "error": "render worker crashed: %s"
                                       % traceback.format_exc(limit=6)}
                # result.json last and atomic: it is the completion signal.
                write_atomic(job_dir / "result.json", result)
                log("job %s -> %s" % (job_dir.name,
                                      "ok" if result.get("ok") else
                                      "FAILED: %s" % result.get("error")))
        except FileNotFoundError:
            # The scratch mount can disappear briefly while compose restarts
            # the backend. Keep watching rather than exiting.
            pass
        time.sleep(POLL_S)


if __name__ == "__main__":
    main(sys.argv)
