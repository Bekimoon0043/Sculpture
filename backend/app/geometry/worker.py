"""Sandbox worker — the ONLY process that ever executes AI-written code.

Runs inside the geo-worker container (ADR-005 realized, Phase 4):
  * separate container (docker-compose service geo-worker)
  * non-root (user 1000:1000)
  * no network (network_mode: none)
  * read-only filesystem except the scratch mount (+ tmpfs /tmp)
  * CPU and memory limits (compose cpus/mem_limit)
  * hard timeout per job (enforced HERE via subprocess timeout)

The loop: watch the scratch mount for job directories (program.py +
job.json, no result.json yet), execute each via `python -m
app.geometry.job_runner <dir>` in a subprocess with the hard timeout, and
leave result.json for the backend to collect. One job at a time —
geometry builds are CPU-bound and the container is CPU-capped anyway.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("luxuryform.geo_worker")

POLL_INTERVAL_S = 0.5
#: Backstop if job.json somehow omits a timeout (the backend always sets one).
DEFAULT_HARD_TIMEOUT_S = 120
#: Extra seconds the subprocess may take to die after the hard timeout.
KILL_GRACE_S = 10


def _pending_jobs(scratch: Path) -> list[Path]:
    jobs = []
    for d in sorted(scratch.iterdir()):
        if not d.is_dir():
            continue
        if (d / "result.json").exists() or (d / ".claimed").exists():
            continue
        job_json = d / "job.json"
        if not job_json.exists():
            continue
        if (d / "program.py").exists():
            jobs.append(d)
            continue
        # ADR-028: probe jobs carry no code — job.json {"probe": true} is
        # answered inline so the gate can prove the backend can READ a
        # file the worker actually WROTE (the cross-container handoff).
        try:
            if json.loads(job_json.read_text(encoding="utf-8")).get("probe"):
                jobs.append(d)
        except Exception:
            continue  # malformed, no program — not ours; leave it
    return jobs


def execute_job(job_dir: Path) -> None:
    """Run one job with the hard timeout; ALWAYS leave a result.json."""
    (job_dir / ".claimed").write_text("1", encoding="utf-8")
    try:
        job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    except Exception as exc:  # malformed job file — answer it honestly
        (job_dir / "result.json").write_text(json.dumps({
            "ok": False, "error": f"malformed job.json: {exc}",
            "artifacts": None, "brep_volume_mm3": None, "params": None,
        }), encoding="utf-8")
        return
    # ADR-028 probe: answer inline (no subprocess, no code execution) with
    # proof of WHO answered — hostname + pid let the gate assert the file
    # was written by a DIFFERENT container than the one reading it.
    if job.get("probe"):
        (job_dir / "result.json").write_text(json.dumps({
            "ok": True,
            "probe": True,
            "worker_hostname": socket.gethostname(),
            "worker_pid": os.getpid(),
            "error": None, "artifacts": None,
            "brep_volume_mm3": None, "params": None,
        }), encoding="utf-8")
        log.info("probe %s answered inline", job_dir.name)
        return
    timeout_s = float(job.get("timeout_s", DEFAULT_HARD_TIMEOUT_S))
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "app.geometry.job_runner", str(job_dir)],
            timeout=timeout_s,
            capture_output=True,
            text=True,
        )
        elapsed = time.perf_counter() - t0
        log.info("job %s finished rc=%s in %.1fs", job_dir.name, proc.returncode, elapsed)
        if not (job_dir / "result.json").exists():
            (job_dir / "result.json").write_text(json.dumps({
                "ok": False,
                "error": f"job runner exited rc={proc.returncode} without a "
                         f"result; stderr tail: {(proc.stderr or '')[-1000:]}",
                "artifacts": None, "brep_volume_mm3": None, "params": None,
            }), encoding="utf-8")
    except subprocess.TimeoutExpired:
        (job_dir / "result.json").write_text(json.dumps({
            "ok": False,
            "error": f"hard timeout: exceeded {timeout_s:.0f}s sandbox limit",
            "artifacts": None, "brep_volume_mm3": None, "params": None,
        }), encoding="utf-8")
        log.warning("job %s killed at hard timeout %.0fs", job_dir.name, timeout_s)


def main() -> int:
    scratch = Path(sys.argv[1] if len(sys.argv) > 1 else "/scratch")
    scratch.mkdir(parents=True, exist_ok=True)
    log.info("geo-worker watching %s (pid %d)", scratch, __import__("os").getpid())
    while True:
        try:
            for job_dir in _pending_jobs(scratch):
                execute_job(job_dir)
        except Exception:
            log.exception("watcher loop error — continuing")
        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    raise SystemExit(main())
