"""Fabrication stage tests (Phase 4) — the loop proven at $0.

The sandbox runner is SCRIPTED (canned SandboxResults): AI-written code
executes nowhere but the geo-worker container, and tests are no exception —
what these tests prove is the LOOP: prompt -> AST gate -> sandbox -> Phase 2
validation -> persistence -> bounded repair, with real numbers.

The PASSING path uses the REAL Phase 2 validation (trimesh-built GLB,
exact volume crosscheck) — only the OCCT build itself is container-side.
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from app.council.orchestrator import DispatchOutcome
from app.council.fabricate import (
    FabricationOutcome,
    SandboxResult,
    fabricate_spec,
    success_rates,
)
from app.council.orchestrator import CouncilOrchestrator
from app.db.models import CouncilCallRow, DesignSpecRow, GeneratedProgramRow
from tests.test_ast_gate import GOOD
from tests.test_council_orchestrator import (
    MODELS,
    ScriptedDispatcher,
    _arbiter_decision_json,
    _make_orch,
)

BAD_IMPORT_PROGRAM = "import os\n\ndef build(spec):\n    return None, {}, 0\n"


@pytest.fixture()
def base_spec(repo_root):
    from tests.test_design_spec_schema import valid_example_spec
    return valid_example_spec()


class FabDispatcher(ScriptedDispatcher):
    """ScriptedDispatcher + a queue of geometrist_code replies."""

    def __init__(self, pricing, base_spec, fab_script: list[str]):
        super().__init__(pricing, base_spec)
        self.fab_script = list(fab_script)
        self.fab_prompts: list[str] = []

    def dispatch(self, **kw):
        if kw["role"] == "geometrist_code":
            self.calls.append({"role": kw["role"], "side": kw["side"],
                               "provider": kw["provider"]})
            self.fab_prompts.append(kw["prompt"])
            text = self.fab_script.pop(0)
            tokens_in = 1000 + len(kw["prompt"]) // 4
            return DispatchOutcome(
                provider=kw["provider"], model=MODELS[kw["provider"]],
                text=text, tokens_in=tokens_in, tokens_out=700,
                latency_ms=100.0,
                cost_usd=self._pricing.cost_usd(
                    kw["provider"], MODELS[kw["provider"]], tokens_in, 700),
                pricing_version=self._pricing.pricing_version,
            )
        return super().dispatch(**kw)


class ScriptedRunner:
    """Canned sandbox results. NEVER executes anything."""

    def __init__(self, results: list[SandboxResult]):
        self.results = list(results)
        self.programs_seen: list[str] = []

    def run(self, program_text, spec, timeout_s):
        self.programs_seen.append(program_text)
        return self.results.pop(0)


def _run_council_session(db, config, base_spec) -> str:
    class ArbiterAware(ScriptedDispatcher):
        def dispatch(self, **kw):
            if kw["role"] == "arbiter" and kw["side"] == "primary" and not self.arbiter_script:
                with db.get_session() as s:
                    ids = [r.id for r in s.query(DesignSpecRow).all()]
                return DispatchOutcome(
                    provider=kw["provider"], model=MODELS[kw["provider"]],
                    text=_arbiter_decision_json(ids), tokens_in=2000, tokens_out=900,
                    latency_ms=100.0,
                    cost_usd=config.pricing.cost_usd(
                        kw["provider"], MODELS[kw["provider"]], 2000, 900),
                    pricing_version=config.pricing.pricing_version)
            return super().dispatch(**kw)

    orch = _make_orch(db, config, ArbiterAware(config.pricing, base_spec))
    return orch.run_session("A monumental lotus fountain for Hawassa (fabrication tests)")


def _first_spec_id(db, session_id: str) -> str:
    with db.get_session() as s:
        return s.query(DesignSpecRow).filter_by(session_id=session_id).first().id


def _fab_orchestrator(db, config, dispatcher):
    return CouncilOrchestrator(db, config.pricing, dispatcher, config.council)


def _ok_result(tmp_path, *, with_real_glb: bool) -> SandboxResult:
    step = tmp_path / "a.step"
    step.write_text("ISO-10303-21; (scripted)", encoding="utf-8")
    glb = tmp_path / "a.glb"
    volume = 1_000_000.0
    if with_real_glb:
        trimesh = pytest.importorskip("trimesh")
        # glTF is METERS (validate_mesh scales x1000 back to mm): a 100 mm
        # box is a 0.1 m box in the file.
        box = trimesh.creation.box(extents=(0.1, 0.1, 0.1))
        box.export(str(glb))
        volume = float(box.volume) * 1e9  # m3 -> mm3
    else:
        glb.write_bytes(b"glTF-scripted")
    return SandboxResult(
        ok=True,
        artifacts={"step": str(step), "glb": str(glb),
                   "step_sha256": "s", "glb_sha256": "g"},
        brep_volume_mm3=volume,
        params={"material_id": "basalt_slab", "tiers": 3},
    )


def _scripted_report(passed: bool):
    return SimpleNamespace(
        passed=passed,
        check_rows=lambda: [
            {"check": "watertight", "value": passed, "passed": passed}
        ],
        model_dump_json=lambda: json.dumps({"passed": passed}),
    )


# --- the loop ---------------------------------------------------------------


def test_pass_first_attempt_real_validation(db, config, base_spec, tmp_path):
    """First-attempt pass through the REAL Phase 2 validation path."""
    sid = _run_council_session(db, config, base_spec)
    spec_id = _first_spec_id(db, sid)
    d = FabDispatcher(config.pricing, base_spec, [GOOD])
    runner = ScriptedRunner([_ok_result(tmp_path, with_real_glb=True)])
    orch = _fab_orchestrator(db, config, d)

    out = fabricate_spec(orch, sid, spec_id, runner,
                         artifact_root=tmp_path / "fab")
    assert isinstance(out, FabricationOutcome)
    assert out.success and out.attempts == 1 and out.final_status == "passed"
    assert out.validation is not None and out.validation["passed"] is True

    with db.get_session() as s:
        rows = s.query(GeneratedProgramRow).filter_by(session_id=sid).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.status == "passed" and row.attempt_no == 1
        assert row.spec_id == spec_id
        from app.council import prompts as _p
        assert row.program_hash == hashlib.sha256(
            _p.extract_program(GOOD).encode()).hexdigest()
        assert row.validation_json is not None
        arts = json.loads(row.artifacts_json)
        # artifacts copied OUT of scratch into the artifact root
        assert str(tmp_path / "fab") in arts["glb"]
        # the code call is audited + priced under its own role (rollup split)
        call = s.query(CouncilCallRow).filter_by(
            session_id=sid, role="geometrist_code").one()
        assert call.cost_usd > 0 and call.status == "ok"


def test_ast_rejection_persisted_then_repair_passes(db, config, base_spec, tmp_path):
    """Operator order: rejected programs persist WITH their reason; the
    reason feeds the next repair round."""
    sid = _run_council_session(db, config, base_spec)
    spec_id = _first_spec_id(db, sid)
    d = FabDispatcher(config.pricing, base_spec, [BAD_IMPORT_PROGRAM, GOOD])
    runner = ScriptedRunner([_ok_result(tmp_path, with_real_glb=False)])
    orch = _fab_orchestrator(db, config, d)

    out = fabricate_spec(orch, sid, spec_id, runner,
                         artifact_root=tmp_path / "fab",
                         validator=lambda *a: _scripted_report(True))
    assert out.success and out.attempts == 2

    with db.get_session() as s:
        rows = (s.query(GeneratedProgramRow).filter_by(session_id=sid)
                .order_by(GeneratedProgramRow.attempt_no).all())
        assert [r.status for r in rows] == ["ast_rejected", "passed"]
        assert "import of 'os'" in rows[0].rejection_reason
        assert "AST gate rejection" in rows[0].error_digest
    # the repair round was TOLD the reason
    assert "AST gate rejection" in d.fab_prompts[1]
    assert "import of 'os'" in d.fab_prompts[1]


def test_exec_failure_then_repair_passes(db, config, base_spec, tmp_path):
    sid = _run_council_session(db, config, base_spec)
    spec_id = _first_spec_id(db, sid)
    d = FabDispatcher(config.pricing, base_spec, [GOOD, GOOD])
    runner = ScriptedRunner([
        SandboxResult(ok=False, error="Traceback ... ValueError: bad param"),
        _ok_result(tmp_path, with_real_glb=False),
    ])
    orch = _fab_orchestrator(db, config, d)

    out = fabricate_spec(orch, sid, spec_id, runner,
                         artifact_root=tmp_path / "fab",
                         validator=lambda *a: _scripted_report(True))
    assert out.success and out.attempts == 2
    with db.get_session() as s:
        statuses = [r.status for r in s.query(GeneratedProgramRow)
                    .filter_by(session_id=sid)
                    .order_by(GeneratedProgramRow.attempt_no)]
        assert statuses == ["exec_failed", "passed"]
    assert "sandbox execution failed" in d.fab_prompts[1]


def test_validation_failure_feeds_real_numbers(db, config, base_spec, tmp_path):
    sid = _run_council_session(db, config, base_spec)
    spec_id = _first_spec_id(db, sid)
    d = FabDispatcher(config.pricing, base_spec, [GOOD, GOOD])
    runner = ScriptedRunner([
        _ok_result(tmp_path, with_real_glb=False),
        _ok_result(tmp_path, with_real_glb=False),
    ])
    reports = [_scripted_report(False), _scripted_report(True)]
    orch = _fab_orchestrator(db, config, d)

    out = fabricate_spec(orch, sid, spec_id, runner,
                         artifact_root=tmp_path / "fab",
                         validator=lambda *a: reports.pop(0))
    assert out.success and out.attempts == 2
    assert "FAILED validation" in d.fab_prompts[1]
    assert "watertight" in d.fab_prompts[1]


def test_bounded_repair_gives_up_honestly(db, config, base_spec, tmp_path):
    sid = _run_council_session(db, config, base_spec)
    spec_id = _first_spec_id(db, sid)
    d = FabDispatcher(config.pricing, base_spec,
                      [BAD_IMPORT_PROGRAM, BAD_IMPORT_PROGRAM, BAD_IMPORT_PROGRAM])
    runner = ScriptedRunner([])  # never reached
    orch = _fab_orchestrator(db, config, d)

    out = fabricate_spec(orch, sid, spec_id, runner,
                         artifact_root=tmp_path / "fab", max_attempts=3)
    assert not out.success and out.attempts == 3
    assert "no passing program after 3 attempts" in out.error
    with db.get_session() as s:
        rows = s.query(GeneratedProgramRow).filter_by(session_id=sid).all()
        assert len(rows) == 3
        assert all(r.status == "ast_rejected" for r in rows)
        # the catalogue: every rejection reason persisted verbatim
        assert all("import of 'os'" in r.rejection_reason for r in rows)


def test_repair_prompt_carries_full_failure_history(db, config, base_spec, tmp_path):
    """Operator directive 2026-08-10: attempt 3 must see BOTH prior
    failures, not just the last one (live defect: attempt 3 repeated
    attempt 1's rejected value), plus an explicit no-repeat instruction."""
    sid = _run_council_session(db, config, base_spec)
    spec_id = _first_spec_id(db, sid)
    d = FabDispatcher(config.pricing, base_spec,
                      [BAD_IMPORT_PROGRAM, GOOD, GOOD])
    runner = ScriptedRunner([
        SandboxResult(ok=False, error="ConstraintViolation: wall=180"),
        _ok_result(tmp_path, with_real_glb=False),
    ])
    orch = _fab_orchestrator(db, config, d)

    out = fabricate_spec(orch, sid, spec_id, runner,
                         artifact_root=tmp_path / "fab",
                         validator=lambda *a: _scripted_report(True))
    assert out.success and out.attempts == 3

    p2, p3 = d.fab_prompts[1], d.fab_prompts[2]
    # attempt 2 saw attempt 1's failure only
    assert "ATTEMPT 1 FAILED" in p2 and "import of 'os'" in p2
    assert "ATTEMPT 2 FAILED" not in p2
    # attempt 3 saw BOTH prior failures, oldest first, verbatim
    assert "ATTEMPT 1 FAILED" in p3 and "ATTEMPT 2 FAILED" in p3
    assert p3.index("ATTEMPT 1 FAILED") < p3.index("ATTEMPT 2 FAILED")
    assert "import of 'os'" in p3
    assert "ConstraintViolation: wall=180" in p3
    # explicit no-repeat instruction
    assert "must NOT be repeated" in p3


# --- ADR-028: the cross-container handoff -----------------------------------


def test_resolve_artifacts_basenames_and_missing_files(tmp_path):
    """The worker reports BASENAMES; the backend resolves them against its
    own view of the job dir and a missing file is an honest error, never
    an exception (the first live run's 500)."""
    from app.council.fabricate import _resolve_artifacts

    job = tmp_path / "job"
    job.mkdir()
    (job / "artifact.step").write_text("ISO-10303-21;", encoding="utf-8")
    resolved, error = _resolve_artifacts(job, {
        "step": "artifact.step", "glb": "artifact.glb",
        "step_sha256": "s", "glb_sha256": "g",
    })
    assert resolved is None and error is not None
    assert "mounts disagree" in error and "artifact.glb" in error

    (job / "artifact.glb").write_bytes(b"glTF")
    resolved, error = _resolve_artifacts(job, {
        "step": "artifact.step", "glb": "artifact.glb",
        "step_sha256": "s",
    })
    assert error is None
    assert resolved["step"] == str(job / "artifact.step")
    assert resolved["step_sha256"] == "s"


def test_resolve_artifacts_refuses_container_absolute_paths(tmp_path):
    """A worker payload carrying /scratch/... (its own container view) is
    rejected outright — resolving it would re-create the live-run crash."""
    from app.council.fabricate import _resolve_artifacts

    resolved, error = _resolve_artifacts(
        tmp_path, {"step": "/scratch/job/artifact.step"})
    assert resolved is None
    assert "non-basename" in error and "ADR-028" in error


def test_collection_failure_is_an_honest_persisted_attempt(db, config, base_spec, tmp_path):
    """If artifact collection still fails (permissions, vanished file), the
    attempt persists as collection_failed with the reason and the repair
    loop continues — never an unhandled 500."""
    sid = _run_council_session(db, config, base_spec)
    spec_id = _first_spec_id(db, sid)
    phantom = SandboxResult(
        ok=True,
        artifacts={"step": str(tmp_path / "gone.step"),
                   "glb": str(tmp_path / "gone.glb"),
                   "step_sha256": "s", "glb_sha256": "g"},
        brep_volume_mm3=1.0, params={"material_id": "basalt_slab"},
    )
    d = FabDispatcher(config.pricing, base_spec, [GOOD, GOOD])
    runner = ScriptedRunner([phantom, _ok_result(tmp_path, with_real_glb=False)])
    orch = _fab_orchestrator(db, config, d)

    out = fabricate_spec(orch, sid, spec_id, runner,
                         artifact_root=tmp_path / "fab",
                         validator=lambda *a: _scripted_report(True))
    assert out.success and out.attempts == 2
    with db.get_session() as s:
        rows = (s.query(GeneratedProgramRow).filter_by(session_id=sid)
                .order_by(GeneratedProgramRow.attempt_no).all())
        assert [r.status for r in rows] == ["collection_failed", "passed"]
        assert "artifact collection failed" in rows[0].error_digest
    assert "artifact collection failed" in d.fab_prompts[1]


def test_worker_answers_probe_inline_without_executing(tmp_path):
    """The probe job (no program.py) is picked up and answered inline with
    the worker's hostname/pid — the gate's real round-trip assertion."""
    from app.geometry import worker

    job = tmp_path / "probe-x1"
    job.mkdir()
    (job / "job.json").write_text('{"probe": true}', encoding="utf-8")
    assert job in worker._pending_jobs(tmp_path)
    worker.execute_job(job)
    payload = json.loads((job / "result.json").read_text(encoding="utf-8"))
    assert payload["ok"] and payload["probe"]
    import socket
    assert payload["worker_hostname"] == socket.gethostname()
    assert payload["worker_pid"] > 0
    # a non-probe dir without program.py is NOT a job
    stray = tmp_path / "stray"
    stray.mkdir()
    (stray / "job.json").write_text('{"spec": {}}', encoding="utf-8")
    assert stray not in worker._pending_jobs(tmp_path)


def test_result_json_is_published_atomically(tmp_path):
    """The backend polls for result.json's EXISTENCE then parses it at once.
    If the file were created empty and filled afterwards, a poll landing in
    that window would read a truncated file and raise JSONDecodeError inside
    the fabrication loop. BOTH writers must publish via a temp sibling +
    os.replace, so the name only ever appears complete.

    Proven by observing the write, not by reading the source: a patched
    write_text asserts that at the moment ANY file is written, the published
    name does not yet exist — i.e. content lands under the temp name first.
    """
    from pathlib import Path as _Path

    from app.geometry import job_runner, worker

    for module, job_name in ((worker, "probe-atomic"), (job_runner, "job-atomic")):
        job = tmp_path / job_name
        job.mkdir()
        seen: list[tuple[str, bool]] = []
        real_write_text = _Path.write_text

        def spy(self, data, *args, **kwargs):
            # record: which name was written, and whether result.json
            # already existed at that instant
            seen.append((self.name, (job / "result.json").exists()))
            return real_write_text(self, data, *args, **kwargs)

        _Path.write_text = spy
        try:
            module._write_result(job, {"ok": True, "error": None})
        finally:
            _Path.write_text = real_write_text

        assert seen, f"{module.__name__} wrote nothing"
        name, existed = seen[-1]
        assert name == "result.json.tmp", (
            f"{module.__name__} wrote content straight to {name!r} — the "
            "poller can observe a half-written result.json"
        )
        assert not existed
        # after the replace, the real name is present and parses
        assert json.loads((job / "result.json").read_text(encoding="utf-8"))["ok"]
        assert not (job / "result.json.tmp").exists()


# --- rates + rollup separation ----------------------------------------------


def test_success_rates_counts_each_RUN_not_each_spec(db, config, base_spec, tmp_path):
    """A re-run of the SAME spec is a separate fabrication unit.

    Keying units on (session_id, spec_id) made every re-run of a spec
    collapse into one unit, so three failed runs followed by one
    first-attempt success reported first_attempt_pass_rate = 1.0 instead of
    0.25 — the metric hid exactly the signal it exists to raise. Runs are
    recovered from the attempt_no restart.
    """
    from app.council.fabricate import success_rates
    from app.db.models import GeneratedProgramRow

    sid = _run_council_session(db, config, base_spec)
    spec_id = _first_spec_id(db, sid)

    # run 1: three attempts, all failed;  run 2: one attempt, passed
    plan = [(1, "exec_failed"), (2, "exec_failed"), (3, "validation_failed"),
            (1, "passed")]
    with db.get_session() as s:
        for i, (attempt, status) in enumerate(plan):
            s.add(GeneratedProgramRow(
                id=f"p{i}", created_at=f"2026-08-09T0{i}:00:00+00:00",
                session_id=sid, spec_id=spec_id, attempt_no=attempt,
                provider="anthropic", model="m", program_text="",
                program_hash="", status=status, rejection_reason=None,
                error_digest=None, artifacts_json=None, validation_json=None))

    rates = success_rates(db, session_id=sid)
    assert rates["fabrication_units"] == 2, rates
    assert rates["first_attempt_pass_rate"] == 0.5, rates
    assert rates["per_round"]["round_1"] == {
        "reached": 2, "passed": 1, "pass_rate_of_reached": 0.5}, rates
    # only the failing run reached rounds 2 and 3
    assert rates["per_round"]["round_2"]["reached"] == 1
    assert rates["per_round"]["round_3"]["reached"] == 1
    assert rates["per_round"]["round_3"]["passed"] == 0


def test_success_rates_first_attempt_vs_repair_rounds(db, config, base_spec, tmp_path):
    """Operator order: first-attempt and per-round rates SEPARATELY."""
    sid = _run_council_session(db, config, base_spec)
    with db.get_session() as s:
        spec_ids = [r.id for r in s.query(DesignSpecRow)
                    .filter_by(session_id=sid).limit(2)]
    # unit A: pass at attempt 1; unit B: reject then pass at attempt 2
    d = FabDispatcher(config.pricing, base_spec, [GOOD])
    orch = _fab_orchestrator(db, config, d)
    fabricate_spec(orch, sid, spec_ids[0],
                   ScriptedRunner([_ok_result(tmp_path, with_real_glb=False)]),
                   artifact_root=tmp_path / "a",
                   validator=lambda *a: _scripted_report(True))

    d2 = FabDispatcher(config.pricing, base_spec, [BAD_IMPORT_PROGRAM, GOOD])
    orch2 = _fab_orchestrator(db, config, d2)
    fabricate_spec(orch2, sid, spec_ids[1],
                   ScriptedRunner([_ok_result(tmp_path, with_real_glb=False)]),
                   artifact_root=tmp_path / "b",
                   validator=lambda *a: _scripted_report(True))

    rates = success_rates(db)
    assert rates["fabrication_units"] == 2
    assert rates["first_attempt_pass_rate"] == 0.5
    assert rates["per_round"]["round_1"] == {
        "reached": 2, "passed": 1, "pass_rate_of_reached": 0.5}
    assert rates["per_round"]["round_2"] == {
        "reached": 1, "passed": 1, "pass_rate_of_reached": 1.0}
    assert any("not allowed" in k or "os" in k
               for k in rates["ast_rejection_catalogue"])

    # session-scoped rates work too
    scoped = success_rates(db, session_id=sid)
    assert scoped["fabrication_units"] == 2
    other = success_rates(db, session_id="nonexistent")
    assert other["fabrication_units"] == 0


def test_rollup_separates_geometrist_code_role(db, config, base_spec, tmp_path):
    """The transcript detail exposes geometrist_code as its own by_role line
    and lists generated programs (operator orders 3 + lineage)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routes_council import router

    sid = _run_council_session(db, config, base_spec)
    spec_id = _first_spec_id(db, sid)
    d = FabDispatcher(config.pricing, base_spec, [BAD_IMPORT_PROGRAM, GOOD])
    orch = _fab_orchestrator(db, config, d)
    fabricate_spec(orch, sid, spec_id,
                   ScriptedRunner([_ok_result(tmp_path, with_real_glb=False)]),
                   artifact_root=tmp_path / "fab",
                   validator=lambda *a: _scripted_report(True))

    from app.db.database import reset_default_db

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("LUXURYFORM_DB", str(db.path))
    reset_default_db()  # drop any cached default before re-pointing
    try:
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        detail = client.get(f"/council/sessions/{sid}").json()
    finally:
        monkeypatch.undo()
        reset_default_db()

    assert "geometrist_code" in detail["cost_rollup"]["by_role"]
    programs = detail["programs"]
    assert [p["status"] for p in programs] == ["ast_rejected", "passed"]
    assert programs[0]["rejection_reason"]
