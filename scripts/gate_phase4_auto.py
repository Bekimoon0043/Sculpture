#!/usr/bin/env python3
"""PHASE 4 AUTO GATE — LuxuryForm Studio v1 (non-interactive half).

Run inside Docker:
    docker compose exec backend python scripts/gate_phase4_auto.py
    docker compose exec backend python scripts/gate_phase4_auto.py --live <session-id>

Fixture mode (default, $0): proves the fabrication LOOP end to end with a
scripted dispatcher and a scripted sandbox runner — prompt -> AST gate ->
sandbox -> Phase 2 validation -> persistence -> bounded repair. AI-written
code executes ONLY in the geo-worker container, so the real execution is
proven operator-side (--live), never in this gate.

  1. CONFIG & SCHEMA v4 — bundle loads; generated_programs table exists;
     researcher reassignment (openai primary) is live in council.yaml.
  2. AST GATE — the whitelist/blacklist proofs (import ban, dunder ban,
     export ban, missing build(), syntax error) with real reason strings.
  3. SANDBOX ISOLATION (static) — docker-compose geo-worker service carries
     every ADR-005 property: non-root, no network, read-only fs, scratch
     mount, CPU/memory limits; the worker enforces the hard timeout.
  4. FABRICATION LOOP ($0) — scripted session + fabrication: AST rejection
     persisted WITH reason, repair succeeds, rates computed (first attempt
     vs repair round SEPARATELY), geometrist_code separated in the rollup,
     programs listed in the transcript detail.
  5. LIVE (--live only) — real fabrication of the Arbiter's first-ranked
     spec from a real session; prints attempts, per-attempt status/cost,
     measured success, and the validation report's real numbers.
  6. VERDICT — PASS (exit 0) or FAIL with exact reasons (exit 1).

The OPERATOR half (browser eye-check) is docs/operator/gate_phase4_visual.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

GATE_DB_PATH = REPO_ROOT / "data" / "gate_run_phase4.db"


def _hline() -> None:
    print("-" * 72)


def _section(no: int, total: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/{total}] {title}")
    _hline()


def _verdict(failures: list[str]) -> int:
    print()
    _hline()
    if failures:
        print("VERDICT: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("VERDICT: PASS")
    return 0


def main() -> int:
    import logging

    logging.getLogger("luxuryform").setLevel(logging.CRITICAL)
    live = "--live" in sys.argv
    total = 6  # section 5 = live (or skip note), section 6 = verdict
    failures: list[str] = []

    # ------------------------------------------------------------------
    _section(1, total, "CONFIG & SCHEMA v4")
    import os

    os.environ["LUXURYFORM_DB"] = str(GATE_DB_PATH)
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(GATE_DB_PATH) + suffix)
        if p.exists():
            p.unlink()

    from app.core.config import load_config_bundle
    from app.db.database import Database

    bundle = load_config_bundle()
    print(f"pricing_version: {bundle.pricing.pricing_version}")
    researcher = bundle.council.roles["researcher"]
    print(f"researcher: primary={researcher.primary} parallel={researcher.parallel}")
    if researcher.primary != "openai" or researcher.parallel != "kimi":
        failures.append(
            "council.yaml researcher reassignment missing "
            f"(got {researcher.primary}|{researcher.parallel})"
        )

    db = Database(GATE_DB_PATH)
    db.init_db()
    with db.get_session() as s:
        names = {r[0] for r in s.execute(
            __import__("sqlalchemy").text(
                "SELECT name FROM sqlite_master WHERE type='table'"))}
    if "generated_programs" not in names:
        failures.append("schema v4: generated_programs table missing")
    else:
        print("schema v4: generated_programs present")

    # ------------------------------------------------------------------
    _section(2, total, "AST GATE")
    from app.geometry.ast_gate import check_program

    cases = [
        ("clean program", "import registry\n\ndef build(spec):\n"
         "    solid, v = registry.cascade_fountain({}, 0)\n"
         "    return solid, v.canonical_dict(), 0\n", None),
        ("import os", "import os\n\ndef build(spec):\n    return None, {}, 0\n",
         "not allowed"),
        ("dunder escape", "def build(spec):\n    x = spec.__class__\n"
         "    return None, {}, 0\n", "private attribute"),
        ("self-export", "def build(spec):\n    export_step(None, '/tmp/x')\n"
         "    return None, {}, 0\n", "export_step"),
        ("no build()", "import registry\nx = 1\n", "def build(spec)"),
        ("syntax error", "def build(spec)\n    return None\n", "syntax error"),
    ]
    for name, src, expect in cases:
        reason = check_program(src)
        if expect is None:
            ok = reason is None
        else:
            ok = reason is not None and expect in reason
        print(f"  {name}: {'ok' if ok else 'FAIL'} "
              f"({reason if reason else 'passes'})")
        if not ok:
            failures.append(f"AST gate case {name!r}: expected {expect!r}, "
                            f"got {reason!r}")

    # ------------------------------------------------------------------
    _section(3, total, "SANDBOX ISOLATION (static assertions)")
    import yaml

    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())
    svc = compose.get("services", {}).get("geo-worker", {})
    checks = {
        "non-root (user 1000:1000)": svc.get("user") == "1000:1000",
        "no network": svc.get("network_mode") == "none",
        "read-only filesystem": svc.get("read_only") is True,
        "scratch mount only": any(
            "geo_scratch" in str(v) for v in svc.get("volumes", [])),
        "CPU limit": "cpus" in svc,
        "memory limit": "mem_limit" in svc,
        "separate image reference": "image" in svc,
    }
    for label, ok in checks.items():
        print(f"  {label}: {'ok' if ok else 'FAIL'}")
        if not ok:
            failures.append(f"compose geo-worker: {label} missing")
    worker_src = (REPO_ROOT / "backend" / "app" / "geometry" / "worker.py").read_text()
    if "TimeoutExpired" in worker_src and "timeout" in worker_src:
        print("  hard timeout enforced by worker: ok")
    else:
        failures.append("worker hard-timeout enforcement not found")

    # ------------------------------------------------------------------
    _section(4, total, "FABRICATION LOOP (scripted, $0)")
    import tempfile

    from tests.test_design_spec_schema import valid_example_spec
    from tests.test_fabrication import (
        BAD_IMPORT_PROGRAM,
        GOOD,
        FabDispatcher,
        ScriptedRunner,
        _fab_orchestrator,
        _first_spec_id,
        _ok_result,
        _run_council_session,
        _scripted_report,
    )
    from app.council.fabricate import fabricate_spec, success_rates
    from app.db.models import CouncilCallRow, GeneratedProgramRow

    base_spec = valid_example_spec()
    sid = _run_council_session(db, bundle, base_spec)
    spec_id = _first_spec_id(db, sid)
    print(f"scripted council session: {sid[:8]}… spec {spec_id[:8]}…")

    d = FabDispatcher(bundle.pricing, base_spec, [BAD_IMPORT_PROGRAM, GOOD])
    runner = ScriptedRunner([_ok_result(Path(tempfile.mkdtemp()),
                                        with_real_glb=False)])
    orch = _fab_orchestrator(db, bundle, d)
    out = fabricate_spec(orch, sid, spec_id, runner,
                         artifact_root=Path(tempfile.mkdtemp()),
                         validator=lambda *a: _scripted_report(True))
    print(f"fabrication: success={out.success} attempts={out.attempts} "
          f"final={out.final_status}")
    if not (out.success and out.attempts == 2):
        failures.append("fabrication loop: expected pass at attempt 2")

    with db.get_session() as s:
        rows = (s.query(GeneratedProgramRow).filter_by(session_id=sid)
                .order_by(GeneratedProgramRow.attempt_no).all())
        print("program rows:", [(r.attempt_no, r.status) for r in rows])
        if not (len(rows) == 2 and rows[0].status == "ast_rejected"
                and rows[0].rejection_reason and rows[1].status == "passed"):
            failures.append("generated_programs rows wrong "
                            f"({[(r.attempt_no, r.status) for r in rows]})")
        calls = s.query(CouncilCallRow).filter_by(
            session_id=sid, role="geometrist_code").all()
        fab_cost = sum(c.cost_usd for c in calls)
        print(f"geometrist_code calls: {len(calls)}, cost ${fab_cost:.6f} "
              "(separate rollup line)")
        if len(calls) != 2:
            failures.append("geometrist_code call rows missing")

    rates = success_rates(db, session_id=sid)
    print(f"success rates: first_attempt={rates['first_attempt_pass_rate']} "
          f"per_round={rates['per_round']}")
    print(f"AST rejection catalogue: {rates['ast_rejection_catalogue']}")
    if rates["first_attempt_pass_rate"] != 0.0:
        failures.append("rates: first-attempt should be 0.0 (rejected first)")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routes_council import router
    from app.db.database import reset_default_db

    reset_default_db()
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    detail = client.get(f"/council/sessions/{sid}").json()
    by_role = detail["cost_rollup"]["by_role"]
    print(f"rollup by_role includes geometrist_code: "
          f"{'geometrist_code' in by_role} "
          f"(${by_role.get('geometrist_code', 0):.6f})")
    if "geometrist_code" not in by_role:
        failures.append("rollup does not separate geometrist_code")
    if len(detail.get("programs", [])) != 2:
        failures.append("transcript detail does not list generated programs")
    reset_default_db()

    # ------------------------------------------------------------------
    if live:
        _section(5, total, "LIVE FABRICATION (real API calls, real money)")
        live_sid = sys.argv[sys.argv.index("--live") + 1] if len(
            sys.argv) > sys.argv.index("--live") + 1 else None
        if not live_sid:
            print("usage: --live <session-id-or-prefix>")
            failures.append("--live needs a session id")
        else:
            import json as _json
            import urllib.request

            base = os.environ.get("LUXURYFORM_API", "http://localhost:8000")
            req = urllib.request.Request(
                f"{base}/api/council/sessions/{live_sid}/fabricate",
                data=_json.dumps({}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=1800) as resp:
                    result = _json.loads(resp.read().decode())
            except Exception as exc:
                print(f"FAIL — live fabrication request: {exc}")
                failures.append(f"live fabrication: {exc}")
                result = None
            if result is not None:
                print(_json.dumps(result, indent=2)[:3000])
                if not result.get("success"):
                    failures.append(
                        f"live fabrication failed: {result.get('error')}")
    else:
        _section(5, total, "LIVE FABRICATION — SKIPPED (fixture mode, $0)")
        print("pass --live <session-id> to fabricate the Arbiter's "
              "first-ranked spec for real (bounded repair, budget-capped).")

    # ------------------------------------------------------------------
    _section(total, total, "VERDICT")
    return _verdict(failures)


if __name__ == "__main__":
    raise SystemExit(main())
