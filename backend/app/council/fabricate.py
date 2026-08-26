"""Fabrication stage (Phase 4) — the GEOMETRIST writes code; the loop runs.

Flow per attempt (bounded repair, default 3):
  1. GEOMETRIST code call (audited + priced through the Phase 3 machinery,
     role "geometrist_code" — separated in every rollup, per the operator's
     2026-08-09 order: "I want to see what a repair loop costs").
  2. AST gate. Rejection -> persist the program WITH its rejection reason
     (operator order: the catalogue of what the model tried that it was not
     allowed to do informs the Phase 6 vocabulary widening) -> repair.
  3. Sandbox execution (ADR-005 realized: separate container, non-root, no
     network, read-only fs except scratch, CPU/mem limits, hard timeout).
     AI-written code executes NOWHERE else.
  4. Phase 2 validation gate on the exported GLB (trusted code, backend
     side) — real numbers, same checks as the Phase 2 gate.
  5. Persist the program row (every attempt, every status) — any geometry
     traces back to the code and the spec that made it.

Success-rate reporting (operator order): first-attempt success and
per-repair-round success are computed SEPARATELY by success_rates() — if
first-attempt success is low, the registry surface in the prompt needs
enriching before Phase 6 adds more primitives.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from app.council import prompts
from app.db.models import CouncilSessionRow, DesignSpecRow, GeneratedProgramRow
from app.geometry.ast_gate import check_program

log = logging.getLogger("luxuryform.council.fabricate")

#: Repair bound (operator-approved plan: "retry limit", reported actuals).
DEFAULT_MAX_ATTEMPTS = 3

#: Sandbox hard timeout per execution (ADR-005). The worker enforces it.
DEFAULT_TIMEOUT_S = 120


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Sandbox runner abstraction — production talks to the scratch mount the
# geo-worker container watches; tests inject a scripted runner that NEVER
# executes anything.
# ---------------------------------------------------------------------------


@dataclass
class SandboxResult:
    ok: bool
    error: str | None = None
    artifacts: dict[str, Any] | None = None  # step/glb paths + sha256
    brep_volume_mm3: float | None = None
    params: dict[str, Any] | None = None


class SandboxRunner(Protocol):
    def run(self, program_text: str, spec: dict[str, Any],
            timeout_s: float) -> SandboxResult: ...


def scratch_dir() -> Path:
    """Shared scratch mount (backend side). The geo-worker watches the same
    host directory at the SAME in-container path (ADR-028: compose binds
    ./data/geo_scratch to /scratch on BOTH services and sets
    LUXURYFORM_GEO_SCRATCH=/scratch on both). The env var, when set, IS
    the scratch directory; unset, fall back to <data>/geo_scratch."""
    from app.core.config import REPO_ROOT

    explicit = os.environ.get("LUXURYFORM_GEO_SCRATCH")
    if explicit:
        return Path(explicit)
    return Path(
        os.environ.get("LUXURYFORM_DATA_DIR", str(REPO_ROOT / "data"))
    ) / "geo_scratch"


def _resolve_artifacts(
    job_dir: Path, artifacts: dict[str, Any] | None
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve worker-reported artifact names against the BACKEND's view of
    the job dir and verify every file is actually visible.

    ADR-028: the worker writes artifact BASENAMES into result.json (never
    container-side absolute paths — the first live run crashed because
    /scratch/... paths are meaningless inside the backend container). A
    claimed-success result whose files the backend cannot READ is a mount
    mismatch; it is returned as an honest failure, never an exception.
    """
    resolved: dict[str, Any] = {}
    missing: list[str] = []
    for key, value in (artifacts or {}).items():
        if key.endswith("_sha256"):
            resolved[key] = value
            continue
        name = str(value)
        if Path(name).name != name:
            return None, (
                f"worker reported a non-basename artifact path {name!r} "
                f"for {key!r} — refusing to resolve container-side paths "
                "(ADR-028)"
            )
        candidate = job_dir / name
        if not candidate.exists():
            missing.append(f"{key} -> {candidate}")
        resolved[key] = str(candidate)
    if missing:
        return None, (
            "result.json claimed success but the backend cannot see "
            + "; ".join(missing)
            + " — the backend and geo-worker scratch mounts disagree "
            "(ADR-028: both services must bind ./data/geo_scratch to "
            "/scratch)"
        )
    return resolved, None


class ScratchSandboxRunner:
    """Production runner: queue a job on the scratch mount, wait for the
    geo-worker container's result.json. Executes NOTHING itself."""

    def __init__(self, root: Path | None = None, poll_s: float = 0.5) -> None:
        self._root = root or scratch_dir()
        self._poll_s = poll_s

    def run(self, program_text: str, spec: dict[str, Any],
            timeout_s: float) -> SandboxResult:
        job_id = uuid.uuid4().hex[:16]
        job_dir = self._root / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        # The geo-worker runs as uid 1000 (ADR-005 non-root) and must WRITE
        # result.json into this backend-created directory on the bind mount.
        try:
            os.chmod(job_dir, 0o777)
        except OSError:
            pass  # Windows Desktop bind mounts: perms are synthetic anyway
        (job_dir / "program.py").write_text(program_text, encoding="utf-8")
        (job_dir / "job.json").write_text(
            json.dumps({"spec": spec, "timeout_s": timeout_s}), encoding="utf-8"
        )
        # The worker's hard timeout plus margin for polling/queueing.
        deadline = time.monotonic() + timeout_s + 60.0
        result_path = job_dir / "result.json"
        while time.monotonic() < deadline:
            if result_path.exists():
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                if payload["ok"]:
                    resolved, error = _resolve_artifacts(
                        job_dir, payload.get("artifacts")
                    )
                    if error is not None:
                        return SandboxResult(
                            ok=False, error=error,
                            brep_volume_mm3=payload.get("brep_volume_mm3"),
                            params=payload.get("params"),
                        )
                    payload["artifacts"] = resolved
                return SandboxResult(
                    ok=bool(payload["ok"]),
                    error=payload.get("error"),
                    artifacts=payload.get("artifacts"),
                    brep_volume_mm3=payload.get("brep_volume_mm3"),
                    params=payload.get("params"),
                )
            time.sleep(self._poll_s)
        return SandboxResult(
            ok=False,
            error=(
                f"sandbox produced no result within {timeout_s + 60:.0f}s — "
                "is the geo-worker container running? "
                "(docker compose ps geo-worker)"
            ),
        )


def probe_scratch(timeout_s: float = 60.0, poll_s: float = 0.5) -> dict[str, Any]:
    """Cross-container round-trip probe (ADR-028).

    Queues a PROBE job (no code — the worker answers it inline with its
    hostname/pid) on the shared scratch mount and waits for result.json.
    Proves the backend can READ a file the geo-worker actually WROTE — the
    exact handoff the first live run broke. Raises TimeoutError with an
    actionable message if the worker never answers.
    """
    root = scratch_dir()
    root.mkdir(parents=True, exist_ok=True)
    job_dir = root / f"probe-{uuid.uuid4().hex[:12]}"
    job_dir.mkdir()
    try:
        os.chmod(job_dir, 0o777)
    except OSError:
        pass
    (job_dir / "job.json").write_text(
        json.dumps({"probe": True}), encoding="utf-8"
    )
    deadline = time.monotonic() + timeout_s
    result_path = job_dir / "result.json"
    while time.monotonic() < deadline:
        if result_path.exists():
            return json.loads(result_path.read_text(encoding="utf-8"))
        time.sleep(poll_s)
    raise TimeoutError(
        f"geo-worker did not answer the probe within {timeout_s:.0f}s — "
        "is the container running? (docker compose ps geo-worker)"
    )


# ---------------------------------------------------------------------------
# The stage
# ---------------------------------------------------------------------------


@dataclass
class FabricationOutcome:
    success: bool
    session_id: str
    spec_id: str
    attempts: int
    program_ids: list[str] = field(default_factory=list)
    final_status: str = ""
    artifacts: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    error: str | None = None
    #: Phase 6 slice A2: the DesignRow id persisted for a passing ASSEMBLY
    #: fabrication (viewable in the Designer, exportable via Phase 9A).
    #: None for cascade fabrications and when the bridge failed (the
    #: failure is recorded in the program row's artifacts_json).
    design_id: str | None = None


def fabricate_spec(
    orchestrator,
    session_id: str,
    spec_id: str,
    runner: SandboxRunner,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    artifact_root: Path | None = None,
    validator=None,
) -> FabricationOutcome:
    """Run the bounded code-generate -> gate -> sandbox -> validate loop.

    ``validator`` defaults to the real Phase 2 validate_mesh path; tests
    inject a scripted report for the failure path (a passing path is tested
    against REAL validation with a trimesh-built GLB)."""
    from app.core.config import REPO_ROOT, load_config_bundle

    with orchestrator._db.get_session() as s:
        spec_row = s.get(DesignSpecRow, spec_id)
        if spec_row is None or spec_row.session_id != session_id:
            raise ValueError(f"spec {spec_id} not found in session {session_id}")
        spec = json.loads(spec_row.spec_json)

    provider = orchestrator._pair("geometrist")[0]  # code writer = primary
    spec_json = json.dumps(spec, sort_keys=True)
    out = FabricationOutcome(False, session_id, spec_id, attempts=0)
    # FULL failure history (operator directive 2026-08-10): every attempt's
    # digest goes back into the next prompt, oldest first, so a value that
    # already failed can never be silently retried on a later attempt.
    failure_history: list[str] = []
    artifact_root = artifact_root or (
        Path(os.environ.get("LUXURYFORM_DATA_DIR", str(REPO_ROOT / "data")))
        / "fabrications" / session_id
    )

    # Two-tier prompt surface (slice A2, plan §3): full parameter detail
    # only for the primitives THIS spec names; the index always lists all.
    # Selection is computed here, never chosen by the model. Unknown or
    # legacy primitive names fall back to the full surface inside
    # registry_surface().
    used_primitives = [
        el.get("primitive")
        for el in (spec.get("massing", {}).get("elements") or [])
        if isinstance(el, dict)
    ]

    for attempt in range(1, max_attempts + 1):
        out.attempts = attempt
        prompt = prompts.fabrication_prompt(
            spec_json, failure_history, used_primitives=used_primitives
        )
        # optional=True (ADR-023): a provider failure is a failed ATTEMPT,
        # not a crashed fabrication — the error becomes the repair digest.
        outcome = orchestrator._call(
            session_id, "geometrist_code", "primary", provider, prompt,
            optional=True,
        )
        program_id = str(uuid.uuid4())
        row = GeneratedProgramRow(
            id=program_id,
            created_at=_utc_now_iso(),
            session_id=session_id,
            spec_id=spec_id,
            attempt_no=attempt,
            provider=outcome.provider or provider,
            model=outcome.model,
            program_text="",
            program_hash="",
            status="call_failed",
            rejection_reason=None,
            error_digest=None,
            artifacts_json=None,
            validation_json=None,
        )

        if outcome.status != "ok":
            row.error_digest = outcome.error
            failure_history.append(
                f"the provider call failed: {outcome.error}"
            )
            _persist_program(orchestrator, row)
            out.program_ids.append(program_id)
            out.final_status = "call_failed"
            continue

        program_text = prompts.extract_program(outcome.text)
        row.program_text = program_text
        row.program_hash = hashlib.sha256(program_text.encode()).hexdigest()

        # 2. AST gate — rejection reason persisted verbatim (catalogue).
        reason = check_program(program_text)
        if reason is not None:
            row.status = "ast_rejected"
            row.rejection_reason = reason
            row.error_digest = f"AST gate rejection: {reason}"
            failure_history.append(row.error_digest)
            _persist_program(orchestrator, row)
            out.program_ids.append(program_id)
            out.final_status = "ast_rejected"
            log.info("attempt %d AST-rejected: %s", attempt, reason)
            continue

        # 3. Sandbox execution.
        result = runner.run(program_text, spec, timeout_s)
        if not result.ok:
            row.status = "exec_failed"
            row.error_digest = f"sandbox execution failed:\n{result.error}"
            failure_history.append(row.error_digest)
            _persist_program(orchestrator, row)
            out.program_ids.append(program_id)
            out.final_status = "exec_failed"
            continue

        # Collect artifacts out of the scratch job dir into the data dir
        # (trusted copy — scratch is transient). A copy failure is an
        # honest PERSISTED attempt (ADR-028), never an unhandled 500.
        artifacts = dict(result.artifacts or {})
        dest_dir = artifact_root / program_id
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            for key in ("step", "glb"):
                src = Path(artifacts[key])
                dest = dest_dir / f"artifact.{key}"
                shutil.copyfile(src, dest)
                artifacts[key] = str(dest)
        except (OSError, KeyError) as exc:
            row.status = "collection_failed"
            row.error_digest = (
                f"geometry built but artifact collection failed: {exc} "
                "(ADR-028: the file the worker reported is not readable "
                "from the backend — check the /scratch mounts)"
            )
            failure_history.append(row.error_digest)
            _persist_program(orchestrator, row)
            out.program_ids.append(program_id)
            out.final_status = "collection_failed"
            continue
        row.artifacts_json = json.dumps(artifacts, sort_keys=True)
        # Slice A2: keep the manifest on the program row for every attempt
        # that produced one — forensics for failed attempts, lineage for the
        # passing one. NULL for cascade programs.
        sandbox_params = result.params or {}
        if sandbox_params.get("schema") == "assembly_manifest_v1":
            row.manifest_json = json.dumps(sandbox_params, sort_keys=True)

        # 4. Phase 2 validation gate — trusted code, real numbers.
        if validator is not None:
            report = validator(artifacts["glb"], result.params or {},
                               result.brep_volume_mm3)
        else:
            from app.geometry.validate import validate_assembly, validate_mesh

            params = result.params or {}
            if params.get("schema") == "assembly_manifest_v1":
                report = validate_assembly(artifacts["glb"], params)
            else:
                bundle = load_config_bundle()
                material_id = params.get("material_id", "basalt_slab")
                material = bundle.materials.materials[material_id]
                report = validate_mesh(
                    artifacts["glb"], material, material_id=material_id,
                    reference_volume_mm3=result.brep_volume_mm3,
                )
        row.validation_json = report.model_dump_json()

        if not report.passed:
            failed = [f"{r['check']}: {r['value']}" for r in report.check_rows()
                      if not r["passed"]]
            row.status = "validation_failed"
            row.error_digest = (
                "geometry built but FAILED validation (real numbers):\n"
                + "\n".join(failed)
            )
            failure_history.append(row.error_digest)
            _persist_program(orchestrator, row)
            out.program_ids.append(program_id)
            out.final_status = "validation_failed"
            continue

        # 5. PASS
        row.status = "passed"
        row.error_digest = None
        validation_json = row.validation_json
        # The program row is persisted FIRST: the design's
        # generated_program_id is a foreign key onto it.
        _persist_program(orchestrator, row)
        out.program_ids.append(program_id)
        # Slice A2 bridge: a passing ASSEMBLY fabrication becomes a real
        # DesignRow through the SAME persistence path the operator API
        # uses, so it is viewable in the Designer and exportable via
        # Phase 9A. A bridge failure is honest and loud — the fabrication
        # still passed (the sandbox artifacts exist), but the missing
        # design record is stated in artifacts_json, never invented.
        if sandbox_params.get("schema") == "assembly_manifest_v1":
            try:
                design = _persist_fabricated_assembly(
                    orchestrator, spec_id, program_id, sandbox_params,
                    artifacts,
                )
                out.design_id = design["design_id"]
                artifacts["design_id"] = design["design_id"]
                artifacts["design_step_sha256"] = design["step_sha256"]
            except Exception as exc:
                artifacts["design_bridge_error"] = str(exc)
                log.error(
                    "assembly design bridge FAILED for program %s: %s "
                    "(fabrication itself passed; the design record is "
                    "missing, not faked)", program_id, exc,
                )
            _update_program_artifacts(
                orchestrator, program_id,
                json.dumps(artifacts, sort_keys=True),
            )
        out.success = True
        out.final_status = "passed"
        out.artifacts = artifacts
        out.validation = json.loads(validation_json)
        return out

    out.error = f"no passing program after {max_attempts} attempts"
    return out


def _persist_program(orchestrator, row: GeneratedProgramRow) -> None:
    with orchestrator._db.get_session() as s:
        s.add(row)


def _update_program_artifacts(
    orchestrator, program_id: str, artifacts_json: str
) -> None:
    """Amend a persisted program row with the bridge outcome (design id or
    honest bridge error) — the row itself was committed before the bridge
    ran, because the design's generated_program_id FK points at it."""
    with orchestrator._db.get_session() as s:
        stored = s.get(GeneratedProgramRow, program_id)
        stored.artifacts_json = artifacts_json


# ---------------------------------------------------------------------------
# Slice A2: fabrication -> design bridge (trusted rebuild + shared persist)
# ---------------------------------------------------------------------------


def _plan_from_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Reconstruct the assembly plan from an assembly_manifest_v1.

    The manifest carries every element's VALIDATED parameters (defaults
    resolved) and every joint's type/parent/overlap — enough to rebuild the
    identical solid in trusted code. Deterministic: elements arrive sorted
    by element_id from the assembler and stay that way.
    """
    joints_by_child = {j["child"]: j for j in manifest.get("joints", [])}
    plan: list[dict[str, Any]] = []
    for el in manifest["elements"]:
        entry: dict[str, Any] = {
            "element_id": el["element_id"],
            "primitive": el["primitive"],
            "parameters": dict(el["parameters"]),
        }
        joint = joints_by_child.get(el["element_id"])
        if joint is not None:
            entry["joint"] = {
                "type": joint["type"],
                "parent": joint["parent"],
                "overlap_mm": joint["overlap_mm"],
            }
        plan.append(entry)
    return plan


def _persist_fabricated_assembly(
    orchestrator,
    spec_id: str,
    program_id: str,
    manifest: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    """Rebuild the assembly in TRUSTED backend code and persist it through
    the same helper the operator API uses (routes_assembly).

    The sandbox already built and validated this geometry; rebuilding here
    (deterministic — same registry, same parameters, same seed) is what
    yields the per-element solids for the scene GLB and guarantees the
    stored STEP comes from the one shared export path. The sandbox's own
    STEP sha256 rides along in the record for cross-image comparison.
    """
    from app.api.routes_assembly import (
        AssemblyBuildRequest,
        persist_assembly_design,
    )
    from app.geometry import assemble

    t0 = time.perf_counter()
    plan = _plan_from_manifest(manifest)
    fabrication = {
        k: v
        for k, v in (manifest.get("fabrication_limits") or {}).items()
        if v is not None
    } or None
    seed = int(manifest.get("seed", 0))
    request = AssemblyBuildRequest(
        elements=plan, fabrication=fabrication, seed=seed, strict=True
    )
    solid, rebuilt_manifest, element_solids = assemble(
        plan,
        seed=seed,
        fabrication=fabrication,
        strict=True,
        return_solids=True,
    )
    return persist_assembly_design(
        request,
        solid,
        rebuilt_manifest,
        element_solids,
        t0=t0,
        db=orchestrator._db,
        spec_id=spec_id,
        generated_program_id=program_id,
        sandbox_step_sha256=artifacts.get("step_sha256"),
    )


# ---------------------------------------------------------------------------
# Success rates (operator order 2026-08-09: first attempt AND each repair
# round, SEPARATELY)
# ---------------------------------------------------------------------------


def success_rates(db, session_id: str | None = None) -> dict[str, Any]:
    """Per-attempt pass rates over generated_programs rows.

    A "fabrication unit" is one RUN of the repair loop — one call to
    fabricate_spec. Rates:
      first_attempt: units passed at attempt 1 / all units
      round_k: units passed at attempt k / units that REACHED attempt k
    Also returns the rejection catalogue counts by AST-gate reason.

    A unit is NOT (session_id, spec_id): the same spec is fabricated again
    every time the operator re-runs the loop after a fix, and keying on the
    pair collapsed all of those into one unit. Measured on the real data,
    that reported a 1.0 first-attempt rate when three earlier runs of the
    same spec had failed outright — the metric flattered itself exactly
    where it was meant to warn (operator order 2026-08-09: a low
    first-attempt rate is the signal to enrich the registry surface).

    Runs are recovered WITHOUT a schema change: attempt_no restarts at 1 on
    every fabricate_spec call, so within one (session, spec) ordered by
    created_at, a new run begins wherever attempt_no does not increase.
    """
    with db.get_session() as s:
        q = s.query(GeneratedProgramRow)
        if session_id is not None:
            q = q.filter_by(session_id=session_id)
        rows = q.order_by(GeneratedProgramRow.created_at,
                          GeneratedProgramRow.attempt_no).all()

    by_spec: dict[tuple[str, str], list[GeneratedProgramRow]] = {}
    for r in rows:
        by_spec.setdefault((r.session_id, r.spec_id), []).append(r)

    units: dict[tuple[str, str, int], list[GeneratedProgramRow]] = {}
    for (sid, spec), spec_rows in by_spec.items():
        run = 0
        previous = None
        for r in spec_rows:
            if previous is None or r.attempt_no <= previous:
                run += 1          # attempt counter restarted -> new run
            previous = r.attempt_no
            units.setdefault((sid, spec, run), []).append(r)

    reached: dict[int, int] = {}
    passed_at: dict[int, int] = {}
    rejections: dict[str, int] = {}
    for unit_rows in units.values():
        passed = False
        for r in unit_rows:
            if passed:
                break
            reached[r.attempt_no] = reached.get(r.attempt_no, 0) + 1
            if r.status == "ast_rejected" and r.rejection_reason:
                key = r.rejection_reason.split(":", 1)[-1].strip()[:80]
                rejections[key] = rejections.get(key, 0) + 1
            if r.status == "passed":
                passed_at[r.attempt_no] = passed_at.get(r.attempt_no, 0) + 1
                passed = True

    total = len(units)
    rates: dict[str, Any] = {
        "fabrication_units": total,
        "first_attempt_pass_rate": (
            round(passed_at.get(1, 0) / total, 4) if total else None
        ),
        "per_round": {
            f"round_{k}": {
                "reached": reached[k],
                "passed": passed_at.get(k, 0),
                "pass_rate_of_reached": round(passed_at.get(k, 0) / reached[k], 4),
            }
            for k in sorted(reached)
        },
        "ast_rejection_catalogue": dict(
            sorted(rejections.items(), key=lambda kv: -kv[1])
        ),
    }
    return rates
