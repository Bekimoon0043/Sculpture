"""Phase 13 slice A — jobs, cost reconciliation, backup/restore.

The reconciliation test is the point: a dashboard that adds up its own
numbers proves nothing; one that reconciles two independently written
ledgers catches a lost or double-counted call.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.database import reset_default_db
from app.db.models import AICallRow, JobRow, SessionRow

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LUXURYFORM_DB", str(tmp_path / "ops_test.db"))
    monkeypatch.setenv("LUXURYFORM_DATA_DIR", str(tmp_path / "data"))
    reset_default_db()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    reset_default_db()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_call(session, session_id: str, cost: float, *, purpose="council_designer",
               provider="anthropic", status="ok") -> None:
    session.add(AICallRow(
        id=str(uuid.uuid4()), session_id=session_id, ts=_now(),
        provider=provider, model="m", purpose=purpose, prompt="p", response="r",
        tokens_in=10, tokens_out=10, latency_ms=1.0, cost_usd=cost,
        pricing_version="test", status=status, error=None,
    ))


# --- cost reconciliation ----------------------------------------------------

def test_costs_reconcile_two_independent_ledgers(client):
    from app.db.database import get_default_db

    db = get_default_db()
    with db.get_session() as session:
        # A clean session: ledger total equals the sum of its calls.
        session.add(SessionRow(id="s-clean", started_at=_now(), ended_at=_now(),
                               status="completed", total_cost_usd=0.30))
        session.flush()
        _seed_call(session, "s-clean", 0.10)
        _seed_call(session, "s-clean", 0.20, purpose="council_critic",
                   provider="openai")
        # A torn session: the ledger disagrees with the calls (the
        # enforcer crashed before updating the running total).
        session.add(SessionRow(id="s-torn", started_at=_now(), ended_at=_now(),
                               status="completed", total_cost_usd=9.99))
        session.flush()
        _seed_call(session, "s-torn", 0.05)
        # A stale session: calls exist, ledger never advanced past zero.
        # (A truly ORPHANED call is impossible in a healthy DB — the FK on
        # ai_calls.session_id forbids it, which this test just proved by
        # failing when it tried. The endpoint's no-ledger branch stays as
        # defense for restored or older files where PRAGMA foreign_keys
        # was off.)
        session.add(SessionRow(id="s-stale", started_at=_now(), ended_at=None,
                               status="running", total_cost_usd=0.0))
        session.flush()
        _seed_call(session, "s-stale", 0.07, status="error")

    body = client.get("/api/ops/costs").json()
    assert body["total_usd"] == pytest.approx(0.42)
    assert body["by_purpose"]["council_designer"]["calls"] == 3
    assert body["by_provider"]["openai"]["cost_usd"] == pytest.approx(0.20)
    # Failed calls get their own line — a flaky link must not look like work.
    assert body["error_calls"] == {"count": 1, "cost_usd": pytest.approx(0.07)}

    rec = body["reconciliation"]
    assert rec["clean"] is False
    findings = {m["session_id"]: m["finding"] for m in rec["mismatches"]}
    assert "disagree" in findings["s-torn"]
    assert "disagree" in findings["s-stale"]
    assert "s-clean" not in findings


def test_costs_are_clean_on_an_untouched_database(client):
    body = client.get("/api/ops/costs").json()
    assert body["total_usd"] == 0
    assert body["reconciliation"]["clean"] is True


# --- jobs -------------------------------------------------------------------

def test_jobs_listing_carries_state_and_failure_class(client):
    from app.db.database import get_default_db

    db = get_default_db()
    with db.get_session() as session:
        session.add(JobRow(id="j-ok", session_id="d1", ts=_now(),
                           job_type="export", status="completed",
                           state_json=json.dumps({"step": "sealed"}),
                           halt_reason=None))
        session.add(JobRow(id="j-bad", session_id="d2", ts=_now(),
                           job_type="export", status="failed",
                           state_json=json.dumps({"step": "rebuild_solid"}),
                           halt_reason="defect: RuntimeError: boom"))
        session.add(JobRow(id="j-old", session_id="d3", ts=_now(),
                           job_type="export", status="failed",
                           state_json="{}", halt_reason="something unprefixed"))

    body = client.get("/api/ops/jobs").json()
    by_id = {j["id"]: j for j in body["jobs"]}
    assert by_id["j-ok"]["failure_class"] is None
    assert by_id["j-ok"]["state"] == {"step": "sealed"}
    assert by_id["j-bad"]["failure_class"] == "defect"
    assert by_id["j-old"]["failure_class"] == "unclassified"


# --- backup / restore -------------------------------------------------------

build123d = pytest.importorskip("build123d", reason="build123d not installed")


def test_backup_restores_whole_and_the_package_reverifies(client, tmp_path, monkeypatch):
    """Full circle: build a design, export its package, back everything up,
    restore into a fresh directory, and prove the restore with the package's
    own shipped verifier plus table counts."""
    payload = {
        "seed": 7,
        "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0},
        "elements": [
            {"element_id": "plinth_01", "primitive": "plinth",
             "parameters": {"top_diameter_mm": 2200, "height_mm": 300,
                            "wall_mm": 120}},
        ],
    }
    design_id = client.post("/api/geometry/assembly/build", json=payload).json()["design_id"]
    client.post(f"/api/geometry/assembly/{design_id}/exports")

    env = {
        "LUXURYFORM_DB": str(tmp_path / "ops_test.db"),
        "LUXURYFORM_DATA_DIR": str(tmp_path / "data"),
    }
    import os

    run_env = {**os.environ, **env}
    script = str(REPO_ROOT / "scripts" / "backup_restore.py")
    archive = tmp_path / "backup.zip"

    backup = subprocess.run(
        [sys.executable, script, "backup", "--out", str(archive)],
        capture_output=True, text=True, env=run_env,
    )
    assert backup.returncode == 0, backup.stdout + backup.stderr
    assert archive.exists()

    restored = tmp_path / "restored"
    restore = subprocess.run(
        [sys.executable, script, "restore", "--archive", str(archive),
         "--into", str(restored)],
        capture_output=True, text=True, env=run_env,
    )
    assert restore.returncode == 0, restore.stdout + restore.stderr
    assert "RESTORE VERIFICATION PASSED" in restore.stdout
    assert "re-verified OK" in restore.stdout, (
        "the LUXEXCHANGE package must re-verify from the restored tree"
    )

    # Refusing to merge over existing data is part of the contract.
    again = subprocess.run(
        [sys.executable, script, "restore", "--archive", str(archive),
         "--into", str(restored)],
        capture_output=True, text=True, env=run_env,
    )
    assert again.returncode == 2
    assert "not empty" in again.stdout


def test_restore_verification_catches_a_corrupted_artifact(client, tmp_path):
    payload = {
        "seed": 7,
        "elements": [
            {"element_id": "p", "primitive": "plinth",
             "parameters": {"top_diameter_mm": 2200, "height_mm": 300,
                            "wall_mm": 120}},
        ],
    }
    design_id = client.post("/api/geometry/assembly/build", json=payload).json()["design_id"]
    client.post(f"/api/geometry/assembly/{design_id}/exports")

    import os

    run_env = {**os.environ,
               "LUXURYFORM_DB": str(tmp_path / "ops_test.db"),
               "LUXURYFORM_DATA_DIR": str(tmp_path / "data")}
    script = str(REPO_ROOT / "scripts" / "backup_restore.py")
    archive = tmp_path / "b.zip"
    subprocess.run([sys.executable, script, "backup", "--out", str(archive)],
                   capture_output=True, text=True, env=run_env)
    restored = tmp_path / "r"
    subprocess.run([sys.executable, script, "restore", "--archive", str(archive),
                    "--into", str(restored)],
                   capture_output=True, text=True, env=run_env)

    # Corrupt one byte inside the restored package, then re-verify.
    pkg = sorted((restored / "artifacts" / "exports").rglob("luxexchange_v1.zip"))[-1]
    data = bytearray(pkg.read_bytes())
    data[len(data) // 2] ^= 0x01
    pkg.write_bytes(bytes(data))

    verify = subprocess.run(
        [sys.executable, script, "verify", "--dir", str(restored)],
        capture_output=True, text=True, env=run_env,
    )
    assert verify.returncode == 1
    assert "FAILED" in verify.stdout
    assert "corrupt" in verify.stdout
