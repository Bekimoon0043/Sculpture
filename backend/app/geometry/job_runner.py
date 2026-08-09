"""Job runner — executes ONE AI-written program inside the sandbox.

This module runs ONLY inside the geo-worker container (ADR-005: separate
container, non-root, no network, read-only filesystem except the scratch
mount, CPU/memory limits, hard timeout enforced by the worker watcher).
AI-written code executes nowhere else — not in the backend, not in tests.

Protocol (per job directory on the scratch mount):
  in : program.py   — the generated program (must define build(spec)
                      returning (solid, params_dict, seed))
  in : job.json     — {"spec": <Design Spec dict>}
  out: result.json  — {"ok": bool, "error": str|None, "artifacts": {...},
                       "brep_volume_mm3": float, "params": {...}}
  out: artifact.step / artifact.glb  (on success)

Defense in depth: the AST gate is re-run HERE (the backend ran it before
queuing the job; a job file that somehow bypassed the backend is still
stopped before exec).
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from app.geometry.ast_gate import check_program

RESULT_NAME = "result.json"


def _write_result(job_dir: Path, payload: dict) -> None:
    (job_dir / RESULT_NAME).write_text(
        json.dumps(payload, sort_keys=True), encoding="utf-8"
    )


def run_job(job_dir: Path) -> int:
    """Execute one queued job. Returns process exit code (0 = ran clean)."""
    program_path = job_dir / "program.py"
    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    spec = job["spec"]
    source = program_path.read_text(encoding="utf-8")

    # Defense in depth: re-check even though the backend gated already.
    reason = check_program(source)
    if reason is not None:
        _write_result(job_dir, {"ok": False, "error": f"AST gate (sandbox re-check): {reason}",
                                "artifacts": None, "brep_volume_mm3": None, "params": None})
        return 1

    try:
        from app.geometry import registry as _registry

        # The generated program imports `registry` — inject the alias so the
        # whitelist name resolves to the real fabrication API.
        sys.modules.setdefault("registry", _registry)

        namespace: dict = {}
        exec(compile(source, str(program_path), "exec"), namespace)  # noqa: S102 — the sandbox is the boundary
        build = namespace.get("build")
        if not callable(build):
            _write_result(job_dir, {"ok": False,
                                    "error": "program parsed but `build` is not callable",
                                    "artifacts": None, "brep_volume_mm3": None, "params": None})
            return 1
        result = build(spec)
        solid, params_dict, seed = result  # contract: (solid, params, seed)

        from app.geometry.exporters import export_glb, export_step
        from app.geometry.kernel import step_timestamp_for

        step_path = job_dir / "artifact.step"
        glb_path = job_dir / "artifact.glb"
        # Amendment 1 carries into Phase 4: deterministic STEP timestamps.
        step_sha = export_step(solid, step_path, step_timestamp_for(int(seed)))
        glb_sha = export_glb(solid, glb_path)
        params_dict = dict(params_dict)
        _write_result(job_dir, {
            "ok": True,
            "error": None,
            "artifacts": {
                "step": str(step_path), "glb": str(glb_path),
                "step_sha256": step_sha, "glb_sha256": glb_sha,
            },
            "brep_volume_mm3": float(solid.volume),
            "params": params_dict,
        })
        return 0
    except Exception:
        digest = traceback.format_exc(limit=8)
        _write_result(job_dir, {"ok": False,
                                "error": digest[-2000:],
                                "artifacts": None, "brep_volume_mm3": None, "params": None})
        return 1


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m app.geometry.job_runner <job_dir>", file=sys.stderr)
        return 2
    return run_job(Path(argv[1]))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
