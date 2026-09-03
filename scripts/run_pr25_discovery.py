"""PR-2.5 discovery orchestrator -- THE one documented host-side command.

    python scripts\\run_pr25_discovery.py            (full run)
    python scripts\\run_pr25_discovery.py --skip-render

Owner clarification 2, implemented exactly:

  * geometry probes run ONLY in the geo-worker sandbox
    (docker compose run --rm -T --no-deps geo-worker ...): network none,
    user 1000:1000, read-only fs except /scratch, cpus 1.0, mem 2 GB --
    inherited from the service definition -- plus a HARD host-side timeout
    (PROBE_TIMEOUT_S) enforced here with docker rm -f on breach;
  * every probe runs TWICE, in two separate sandbox processes (passA and
    passB), for cross-process determinism evidence;
  * artifacts land in the dedicated discovery directory
    data/geo_scratch/pr25_discovery/ (inside the sandbox's ONLY writable
    mount -- ADR-064 records why; never the DB, never data/exports);
  * read-only validation and annotation run in the backend container,
    which ORCHESTRATES NOTHING and launches no sibling containers -- all
    docker invocations happen here on the host;
  * the run starts by WIPING data/geo_scratch/pr25_discovery/ and
    data/render_scratch/pr25_* so it never relies on artifacts from an
    earlier run and reruns cleanly from a fresh checkout;
  * section coverage and a single exit code are reported at the end.

A probe fixture FAILING to construct is recorded evidence, not an
orchestration error (owner clarification 4). The exit code is non-zero
only when the orchestration itself breaks (docker failure, timeout,
missing results, render protocol failure).

$0: no network beyond the local docker daemon, no AI calls, no downloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRATCH_HOST = REPO / "data" / "geo_scratch" / "pr25_discovery"
SCRATCH_CTR = "/scratch/pr25_discovery"
RENDER_HOST = REPO / "data" / "render_scratch"
PROBE_SRC = REPO / "scripts" / "probes"
SEED = 20260902

#: Hard per-probe wall-clock budget, host-enforced. probe-only-judgement:
#: generous for 7 lofts/sweeps on the sandbox's single CPU.
PROBE_TIMEOUT_S = 1800

#: Render job poll budget per fixture (3 views). probe-only-judgement.
RENDER_TIMEOUT_S = 600

PROBES = ("gen_import_fixture.py", "probe_freeform_brep.py",
          "probe_freeform_mesh.py", "probe_freeform_import.py")

VIEWS = [
    {"name": "ortho_front", "camera": "ortho_front", "resolution": 768,
     "samples": 24, "time_budget_s": 90.0},
    {"name": "ortho_side", "camera": "ortho_side", "resolution": 768,
     "samples": 24, "time_budget_s": 90.0},
    {"name": "perspective_3q", "camera": "perspective_3q", "resolution": 768,
     "samples": 24, "time_budget_s": 90.0},
]


def sh(args, timeout=None, **kw):
    return subprocess.run(args, capture_output=True, text=True,
                          timeout=timeout, cwd=str(REPO), **kw)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def image_id(container: str) -> str | None:
    r = sh(["docker", "inspect", "--format", "{{.Image}}", container])
    return r.stdout.strip()[7:19] if r.returncode == 0 else None


def run_sandbox_probe(probe: str, pass_name: str, log_dir: Path) -> dict:
    """One probe, one separate sandbox process, hard host-side timeout."""
    name = "pr25-%s-%s" % (pass_name, probe.replace(".py", "").replace("_", "-"))
    args = ["docker", "compose", "run", "--rm", "-T", "--no-deps",
            "--name", name, "geo-worker", "python",
            "%s/probes/%s" % (SCRATCH_CTR, probe),
            "--out", "%s/%s" % (SCRATCH_CTR, pass_name),
            "--seed", str(SEED)]
    t0 = time.monotonic()
    try:
        r = sh(args, timeout=PROBE_TIMEOUT_S)
        ok = r.returncode == 0
        out, err, rc = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as exc:
        sh(["docker", "rm", "-f", name])
        ok, rc = False, -1
        out = (exc.stdout or "")
        err = (exc.stderr or "") + "\nHARD TIMEOUT after %ds -- container removed" % PROBE_TIMEOUT_S
    (log_dir / ("%s.%s.log" % (pass_name, probe))).write_text(
        "exit=%s\n--- stdout ---\n%s\n--- stderr ---\n%s" % (rc, out, err),
        encoding="utf-8")
    return {"probe": probe, "pass": pass_name, "ok": ok, "exit": rc,
            "elapsed_s": round(time.monotonic() - t0, 1)}


def backend_exec(args, timeout=900):
    """Analysis exec in the backend. A TimeoutExpired is RETURNED as a
    failed CompletedProcess, never raised -- the 2026-09-02 run crashed
    here when an overnight host suspension consumed the wall-clock
    budget while the in-container work was healthy. NOTE: on timeout the
    docker CLI dies but the exec'd python may keep running inside the
    container; the stderr note says so and the orchestrator records the
    step as failed either way."""
    cmd = ["docker", "compose", "exec", "-T", "backend", "python"] + args
    try:
        return sh(cmd, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        def _s(v):
            if v is None:
                return ""
            return v.decode("utf-8", "replace") if isinstance(v, bytes) else v
        return subprocess.CompletedProcess(
            cmd, returncode=-1, stdout=_s(exc.stdout),
            stderr=_s(exc.stderr) + "\nHARD TIMEOUT after %ds (wall clock "
            "-- host suspension counts; the in-container process may still "
            "be running)" % timeout)


def collect_entries(pass_dir: Path) -> list[dict]:
    entries = []
    for res in sorted(pass_dir.glob("*.results.json")):
        entries.extend(json.loads(res.read_text(encoding="utf-8"))["entries"])
    return entries


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-render", action="store_true")
    args = ap.parse_args()

    coverage = []
    failures = []

    # [0] clean slate -- ONLY inside the two dedicated discovery areas
    if SCRATCH_HOST.exists():
        shutil.rmtree(SCRATCH_HOST)
    for old in RENDER_HOST.glob("pr25_*"):
        shutil.rmtree(old, ignore_errors=True)
    (SCRATCH_HOST / "probes").mkdir(parents=True)
    for py in sorted(PROBE_SRC.glob("*.py")):
        shutil.copy2(py, SCRATCH_HOST / "probes" / py.name)
    coverage.append("clean-slate+copy-probes")

    def worker_running() -> bool:
        # render-worker sits behind a compose profile, so `compose ps`
        # needs the profile flag; docker inspect is unambiguous.
        r = sh(["docker", "inspect", "-f", "{{.State.Running}}",
                "luxuryform-render-worker-1"])
        return r.returncode == 0 and r.stdout.strip() == "true"

    backend_img = image_id("luxuryform-backend-1")
    worker_state_start = worker_running()
    print("backend image: %s | render-worker at start: %r"
          % (backend_img, worker_state_start))

    # [1] sandbox probes, two separate passes
    runs = []
    for pass_name in ("passA", "passB"):
        (SCRATCH_HOST / pass_name).mkdir(exist_ok=True)
        for probe in PROBES:
            res = run_sandbox_probe(probe, pass_name, SCRATCH_HOST)
            runs.append(res)
            print("  [%s] %-28s exit=%-3s %5.1fs"
                  % (pass_name, probe, res["exit"], res["elapsed_s"]))
            if not res["ok"]:
                failures.append("%s/%s exited %s" % (pass_name, probe, res["exit"]))
    coverage.append("sandbox-probes-x2")

    # [2] read-only validation of both passes (backend container)
    validations = {}
    for pass_name in ("passA", "passB"):
        out_json = "%s/validation_%s.json" % (SCRATCH_CTR, pass_name)
        # The OCC self-interference check is the expensive part (~12 min
        # of real compute); the budget is wall-clock and a host
        # suspension counts against it (measured 2026-09-02/03), so it is
        # deliberately far larger than the compute needs.
        r = backend_exec(["%s/probes/validate_freeform.py" % SCRATCH_CTR,
                          "%s/%s" % (SCRATCH_CTR, pass_name), out_json],
                         timeout=14400)
        (SCRATCH_HOST / ("validation_%s.log" % pass_name)).write_text(
            r.stdout + "\n" + r.stderr, encoding="utf-8")
        if r.returncode != 0:
            failures.append("validation %s exited %d" % (pass_name, r.returncode))
        else:
            validations[pass_name] = json.loads(
                (SCRATCH_HOST / ("validation_%s.json" % pass_name))
                .read_text(encoding="utf-8"))["validated"]
    coverage.append("independent-validation-x2")

    # [3] cross-process determinism on contractual bytes (STEP + canonical OBJ)
    determinism = []
    pass_a = SCRATCH_HOST / "passA"
    pass_b = SCRATCH_HOST / "passB"
    for f in sorted(list(pass_a.glob("*.step")) + list(pass_a.glob("*.obj"))):
        twin = pass_b / f.name
        row = {"file": f.name, "passA_sha256": sha256_file(f),
               "passB_sha256": sha256_file(twin) if twin.exists() else None}
        row["identical"] = row["passA_sha256"] == row["passB_sha256"]
        determinism.append(row)
        if not row["identical"]:
            failures.append("determinism: %s differs across passes" % f.name)
    # GLB hashes recorded for information only -- NOT a determinism contract
    glb_info = []
    for f in sorted(pass_a.glob("*.glb")):
        twin = pass_b / f.name
        glb_info.append({"file": f.name, "passA_sha256": sha256_file(f),
                         "passB_sha256": sha256_file(twin) if twin.exists() else None})
    coverage.append("determinism-cross-process")

    # [4] renders (passA artifacts) through the EXISTING render protocol
    renders = []
    if args.skip_render:
        coverage.append("renders-SKIPPED(--skip-render)")
    elif not worker_state_start:
        coverage.append("renders-SKIPPED(worker-not-running)")
        failures.append("render worker not running -- start it with: "
                        "docker compose --profile render up -d render-worker")
    else:
        entries = [e for e in collect_entries(pass_a)
                   if e["status"] == "constructed" and "glb" in e["artifacts"]]
        for e in entries:
            job_id = "pr25_%s__%s" % (e["approach"], e["fixture"])
            job_dir = RENDER_HOST / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pass_a / e["artifacts"]["glb"]["file"],
                         job_dir / "input.glb")
            # job.json LAST: its presence is what the worker claims on.
            (job_dir / "job.json").write_text(json.dumps({
                "design_id": job_id, "input_mesh": "input.glb",
                "views": VIEWS, "seed": SEED,
                "output_dir": str(job_dir)}, sort_keys=True),
                encoding="utf-8")
            t0 = time.monotonic()
            result = None
            while time.monotonic() - t0 < RENDER_TIMEOUT_S:
                rj = job_dir / "result.json"
                if rj.exists():
                    result = json.loads(rj.read_text(encoding="utf-8"))
                    break
                time.sleep(2.0)
            ok = bool(result and result.get("ok"))
            renders.append({"job": job_id, "fixture": e["fixture"],
                            "approach": e["approach"], "ok": ok,
                            "error": None if ok else
                            (result or {}).get("error", "TIMEOUT after %ds"
                                               % RENDER_TIMEOUT_S)})
            print("  [render] %-40s %s" % (job_id, "ok" if ok else "FAILED"))
            if not ok:
                failures.append("render %s failed" % job_id)
        coverage.append("renders-passA")

        # [5] caption annotation (backend, Pillow, analysis-only)
        if renders:
            spec = {"jobs": [{
                "job_dir": r["job"],
                "label": "PR2.5 %s | %s | glb %s | pass A" % (
                    r["fixture"], r["approach"],
                    next((e["artifacts"]["glb"]["sha256"][:8]
                          for e in collect_entries(pass_a)
                          if e["fixture"] == r["fixture"]
                          and e["approach"] == r["approach"]), "?"))}
                for r in renders if r["ok"]]}
            spec_path = SCRATCH_HOST / "annotate_spec.json"
            spec_path.write_text(json.dumps(spec, sort_keys=True),
                                 encoding="utf-8")
            r = backend_exec(["%s/probes/annotate_views.py" % SCRATCH_CTR,
                              "/render_scratch",
                              "%s/annotate_spec.json" % SCRATCH_CTR])
            print(r.stdout.strip())
            if r.returncode != 0:
                failures.append("annotation exited %d: %s"
                                % (r.returncode, r.stderr.strip()[:400]))
            coverage.append("annotation")

    worker_state_end = worker_running()

    # [6] summary
    summary = {
        "seed": SEED,
        "backend_image": backend_img,
        "render_worker_running_at_start": bool(worker_state_start),
        "render_worker_running_at_end": bool(worker_state_end),
        "probe_runs": runs,
        "entries_passA": collect_entries(pass_a),
        "validation_passA": validations.get("passA", []),
        "validation_passB": validations.get("passB", []),
        "determinism": determinism,
        "glb_hashes_info_only": glb_info,
        "renders": renders,
        "coverage": coverage,
        "orchestration_failures": failures,
    }
    (SCRATCH_HOST / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print("\nsections run: %s" % ", ".join(coverage))
    if failures:
        print("ORCHESTRATION FAILURES (%d):" % len(failures))
        for f in failures:
            print("  - %s" % f)
        print("EXIT 1 -- see logs under %s" % SCRATCH_HOST)
        return 1
    print("orchestration complete -- summary at %s" % (SCRATCH_HOST / "summary.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
