#!/usr/bin/env python3
"""Phase 13 slice A auto gate — backup/restore, jobs, cost reconciliation.

    docker compose exec backend python scripts/gate_phase13a_auto.py

$0, no network. Proves:

  1. backup -> restore into a fresh directory -> the LUXEXCHANGE package
     re-verifies with its own shipped checker, and table counts match
  2. a corrupted restore is CAUGHT, with the file named
  3. re-running an export is byte-equivalent to the first run (the resume
     semantics jobs inherit: skip-if-artifact-exists must change nothing)
  4. the jobs API reports status, checkpoint state and failure class
  5. the cost API reconciles the per-call book against the session ledger
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

PASS, FAIL = "PASS", "FAIL"


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/5] {title}")
    _hline()


def _check(failures: list[str], label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{('  — ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="luxform_gate13a_"))
    os.environ["LUXURYFORM_DB"] = str(tmp / "gate13a.db")
    os.environ["LUXURYFORM_DATA_DIR"] = str(tmp / "data")

    from fastapi.testclient import TestClient

    from app.db.database import reset_default_db
    reset_default_db()
    from app.main import app

    failures: list[str] = []
    script = str(REPO_ROOT / "scripts" / "backup_restore.py")
    payload = {
        "seed": 7,
        "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0},
        "elements": [
            {"element_id": "plinth_01", "primitive": "plinth",
             "parameters": {"top_diameter_mm": 2200, "height_mm": 300,
                            "wall_mm": 120}},
        ],
    }

    with TestClient(app) as client:
        design_id = client.post("/api/geometry/assembly/build", json=payload).json()["design_id"]
        first = client.post(f"/api/geometry/assembly/{design_id}/exports").json()

        # -------------------------------------------------------------
        _section(1, "BACKUP -> RESTORE -> the package re-verifies")
        archive = tmp / "backup.zip"
        backup = subprocess.run(
            [sys.executable, script, "backup", "--out", str(archive)],
            capture_output=True, text=True, env=os.environ.copy(),
        )
        _check(failures, "backup completes", backup.returncode == 0,
               backup.stdout.strip().splitlines()[0] if backup.stdout else backup.stderr[:80])

        restored = tmp / "restored"
        restore = subprocess.run(
            [sys.executable, script, "restore", "--archive", str(archive),
             "--into", str(restored)],
            capture_output=True, text=True, env=os.environ.copy(),
        )
        _check(failures, "restore verification passes",
               restore.returncode == 0 and "PASSED" in restore.stdout)
        _check(failures, "the LUXEXCHANGE package re-verified from the restore",
               "re-verified OK" in restore.stdout)
        _check(failures, "restore refuses to merge over existing data",
               subprocess.run(
                   [sys.executable, script, "restore", "--archive", str(archive),
                    "--into", str(restored)],
                   capture_output=True, text=True, env=os.environ.copy(),
               ).returncode == 2)

        # -------------------------------------------------------------
        _section(2, "TAMPER — a corrupted restore is caught, file named")
        pkg = sorted((restored / "artifacts" / "exports").rglob("luxexchange_v1.zip"))[-1]
        data = bytearray(pkg.read_bytes())
        data[len(data) // 2] ^= 0x01
        pkg.write_bytes(bytes(data))
        verify = subprocess.run(
            [sys.executable, script, "verify", "--dir", str(restored)],
            capture_output=True, text=True, env=os.environ.copy(),
        )
        _check(failures, "verification fails on the corrupted restore",
               verify.returncode == 1 and "FAILED" in verify.stdout)
        _check(failures, "the corrupt package is named",
               "luxexchange_v1.zip" in verify.stdout)

        # -------------------------------------------------------------
        _section(3, "RESUME EQUIVALENCE — re-export changes nothing")
        second = client.post(f"/api/geometry/assembly/{design_id}/exports").json()
        _check(failures, "the content digest is identical",
               first["content_digest"] == second["content_digest"],
               first["content_digest"][:16] + "...")
        _check(failures, "the package bytes are identical",
               first["package_sha256"] == second["package_sha256"])

        # -------------------------------------------------------------
        _section(4, "JOBS — status, checkpoint, failure class")
        jobs = client.get("/api/ops/jobs").json()["jobs"]
        export_jobs = [j for j in jobs if j["job_type"] == "export"]
        _check(failures, "both export jobs are listed", len(export_jobs) == 2)
        _check(failures, "completed jobs carry their checkpoint state",
               all(j["state"].get("step") == "sealed" for j in export_jobs),
               str(export_jobs[0]["state"])[:60])
        _check(failures, "completed jobs have no failure class",
               all(j["failure_class"] is None for j in export_jobs))

        # -------------------------------------------------------------
        _section(5, "COSTS — two ledgers reconciled")
        costs = client.get("/api/ops/costs").json()
        _check(failures, "a $0 run reconciles clean",
               costs["reconciliation"]["clean"] is True
               and costs["total_usd"] == 0)

        # Now tear one ledger on purpose and watch the finding surface.
        from app.db.database import get_default_db
        from app.db.models import AICallRow, SessionRow
        from datetime import datetime, timezone
        import uuid as _uuid

        db = get_default_db()
        now = datetime.now(timezone.utc).isoformat()
        with db.get_session() as session:
            session.add(SessionRow(id="torn", started_at=now, ended_at=now,
                                   status="completed", total_cost_usd=5.00))
            session.flush()
            session.add(AICallRow(
                id=str(_uuid.uuid4()), session_id="torn", ts=now,
                provider="openai", model="m", purpose="council_designer",
                prompt="p", response="r", tokens_in=1, tokens_out=1,
                latency_ms=1.0, cost_usd=0.01, pricing_version="t",
                status="ok", error=None,
            ))
        costs = client.get("/api/ops/costs").json()
        rec = costs["reconciliation"]
        _check(failures, "a torn ledger is a FINDING, not smoothed over",
               rec["clean"] is False and rec["mismatches"]
               and rec["mismatches"][0]["session_id"] == "torn",
               str(rec["mismatches"][:1]))

    print()
    _hline()
    print("VERDICT")
    _hline()
    if failures:
        print(f"{FAIL} — Phase 13a auto gate: {len(failures)} check(s) failed:")
        for item in failures:
            print(f"    - {item}")
        return 1
    print(f"{PASS} — Phase 13a auto gate: all sections passed at $0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
