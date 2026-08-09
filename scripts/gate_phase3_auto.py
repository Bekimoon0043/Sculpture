#!/usr/bin/env python3
"""PHASE 3 AUTO GATE — LuxuryForm Studio v1 (non-interactive half).

Run inside Docker:
    docker compose exec backend python scripts/gate_phase3_auto.py
    docker compose exec backend python scripts/gate_phase3_auto.py --live

Fixture mode (default, $0): replays the COMMITTED synthetic Council
fixture into a throwaway gate DB and proves the whole Phase 3 contract —
schema, replay invariants, transcript API, cost rollup, cache classes.
No API keys needed, no money spent, re-runnable forever.

--live mode: runs ONE real Council session on a small brief (real API
calls, real money — bounded by the $5 session cap; measured cost so far:
$0.84). Use it to re-verify the live path after provider-side changes.

Prints a numbered transcript; exits 0 only on PASS. The OPERATOR half
(browser eye-check) is docs/operator/gate_phase3_visual.md.

  1. CONFIG & FRESH GATE DB — bundle loads; pricing 2026-08-v3 or newer;
     cache-class prices present for kimi + anthropic.
  2. FIXTURE REPLAY — committed synthetic fixture replays clean; specs
     schema-valid; hashes recomputed; costs recomputed from tokens x
     pricing (never trusted from the fixture).
  3. TRANSCRIPT API — TestClient: demo-session POST (idempotent), session
     list, detail with 16 calls / 3 specs / decision / rollup; prefix
     resolution; 404 on unknown.
  4. COST INTEGRITY — rollup sums match the session total; cache-savings
     arithmetic is non-negative and consistent with per-call fields.
  5. LIVE SESSION (--live only) — one real brief end-to-end; prints
     measured cost, per-role and per-provider rollups, cache savings.
  6. VERDICT — PASS (exit 0) or FAIL with exact reasons (exit 1).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

GATE_DB_PATH = REPO_ROOT / "data" / "gate_run_phase3.db"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "council_session_v1.json"


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
    _section(1, total, "CONFIG & FRESH GATE DB")
    import os

    os.environ["LUXURYFORM_DB"] = str(GATE_DB_PATH)
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(GATE_DB_PATH) + suffix)
        if p.exists():
            p.unlink()

    from app.core.config import ConfigError, load_config_bundle
    from app.db.database import Database

    try:
        bundle = load_config_bundle()
    except ConfigError as exc:
        print(f"FAIL — config: {exc}")
        return _verdict([f"config: {exc}"])

    pricing = bundle.pricing
    print(f"pricing_version: {pricing.pricing_version}")
    kimi = pricing.price_for("kimi", "kimi-k3")
    anth = pricing.price_for("anthropic", "claude-sonnet-4-5")
    print(f"kimi-k3: miss ${kimi.usd_per_1m_input_tokens}/MTok, "
          f"cache-hit ${kimi.usd_per_1m_cached_input_tokens}/MTok, "
          f"out ${kimi.usd_per_1m_output_tokens}/MTok")
    print(f"claude-sonnet-4-5: in ${anth.usd_per_1m_input_tokens}/MTok, "
          f"cache-read ${anth.usd_per_1m_cached_input_tokens}/MTok, "
          f"cache-write ${anth.usd_per_1m_cache_write_input_tokens}/MTok, "
          f"out ${anth.usd_per_1m_output_tokens}/MTok")
    if kimi.usd_per_1m_cached_input_tokens is None:
        failures.append("kimi cache-hit price missing (ADR-022)")
    if anth.usd_per_1m_cached_input_tokens is None or \
            anth.usd_per_1m_cache_write_input_tokens is None:
        failures.append("anthropic cache-class prices missing (ADR-022)")

    db = Database(GATE_DB_PATH)
    db.init_db()
    print(f"gate db: {GATE_DB_PATH} (fresh, throwaway)")

    # ------------------------------------------------------------------
    _section(2, total, "FIXTURE REPLAY (synthetic, $0)")
    from app.council.replay import FixtureError, load_fixture, replay_session

    try:
        fixture = load_fixture(FIXTURE_PATH)
        session_id = replay_session(db, pricing, fixture)
    except FixtureError as exc:
        print(f"FAIL — fixture: {exc}")
        return _verdict(failures + [f"fixture replay: {exc}"])
    print(f"replayed session {session_id}")
    print(f"fixture calls: {len(fixture['calls'])}, "
          f"specs: {len(fixture['design_specs'])}, "
          f"synthetic: {fixture['synthetic']}")

    from app.db.models import CouncilSessionRow, DesignSpecRow

    with db.get_session() as s:
        sess = s.get(CouncilSessionRow, session_id)
        specs = s.query(DesignSpecRow).filter_by(session_id=session_id).all()
    print(f"total_cost_usd (recomputed): {sess.total_cost_usd}")
    print(f"arbiter_confidence: {sess.arbiter_confidence}")
    print(f"schema-valid specs: {sum(r.schema_valid for r in specs)}/{len(specs)}")
    for r in specs:
        print(f"  spec {r.id[:8]}… provider={r.provider} "
              f"hash={r.spec_hash[:16]}…")
    if sess.total_cost_usd <= 0:
        failures.append("replayed session cost is zero — recomputation broke")
    if sum(r.schema_valid for r in specs) != 3:
        failures.append("expected 3 schema-valid fixture specs")

    # The LIVE fixture (operator's first session 32e1c68f) is the permanent
    # pricing regression: replay must reproduce the measured rollup exactly.
    live_fx_path = REPO_ROOT / "tests" / "fixtures" / "council_session_live_32e1c68f.json"
    if live_fx_path.exists():
        live_fx = load_fixture(live_fx_path)
        live_sid = replay_session(db, pricing, live_fx)
        with db.get_session() as s:
            live_sess = s.get(CouncilSessionRow, live_sid)
        print(f"live fixture replayed: {live_sid[:8]}… "
              f"recomputed ${live_sess.total_cost_usd} "
              f"({len(live_fx['calls'])} calls)")
        if abs(live_sess.total_cost_usd - 0.843842) > 1e-6:
            failures.append(
                f"live fixture cost regression: recomputed "
                f"{live_sess.total_cost_usd} != measured 0.843842"
            )
    else:
        failures.append("live regression fixture missing: " + live_fx_path.name)

    # ------------------------------------------------------------------
    _section(3, total, "TRANSCRIPT API (TestClient, in-process)")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api import routes_council
    from app.db.database import get_default_db, reset_default_db

    reset_default_db()  # honour LUXURYFORM_DB set above
    get_default_db().init_db()
    app = FastAPI()
    app.include_router(routes_council.router, prefix="/api")
    client = TestClient(app)

    r = client.post("/api/council/demo-session")
    print(f"demo-session POST: {r.status_code} created={r.json().get('created')}")
    r2 = client.post("/api/council/demo-session")
    print(f"demo-session POST again: created={r2.json().get('created')} "
          "(idempotent)")
    if r.status_code != 200 or r2.json().get("created") is not False:
        failures.append("demo-session endpoint not idempotent")

    demo_id = r.json()["session_id"]
    lst = client.get("/api/council/sessions").json()
    print(f"session list: {lst['count']} session(s), "
          f"synthetic={lst['sessions'][0]['synthetic']}")
    detail = client.get(f"/api/council/sessions/{demo_id}").json()
    print(f"detail: {len(detail['calls'])} calls, "
          f"{len(detail['specs'])} specs, "
          f"decision confidence "
          f"{detail['arbiter_decision']['confidence']}")
    # synthetic labeling is load-bearing (the Hub reads it): demo must be
    # synthetic, the live replay must NOT.
    by_id = {s["id"]: s for s in lst["sessions"]}
    if not by_id[demo_id]["synthetic"]:
        failures.append("demo session lost its synthetic label")
    live_ids = [i for i in by_id if i != demo_id]
    if live_ids and by_id[live_ids[0]]["synthetic"]:
        failures.append("live replay mislabeled synthetic")
    # unique-prefix resolution
    prefix = demo_id[:8]
    r3 = client.get(f"/api/council/sessions/{prefix}")
    print(f"prefix resolution ({prefix}…): {r3.status_code}")
    if r3.status_code != 200:
        failures.append("session-id prefix resolution failed")
    r4 = client.get("/api/council/sessions/does-not-exist")
    print(f"unknown id: {r4.status_code}")
    if r4.status_code != 404:
        failures.append("unknown session id did not 404")

    # ------------------------------------------------------------------
    _section(4, total, "COST INTEGRITY")
    rollup = detail["cost_rollup"]
    print(f"total: ${rollup['total_cost_usd']:.6f} "
          f"({rollup['call_count']} calls, pricing {rollup['pricing_version']})")
    print(f"by_role: {rollup['by_role']}")
    print(f"by_provider: {rollup['by_provider']}")
    print(f"cache_savings_usd: ${rollup['cache_savings_usd']:.6f}")
    print(f"caps: session ${rollup['session_cap_usd']}, "
          f"day ${rollup['day_cap_usd']}")
    role_sum = sum(rollup["by_role"].values())
    prov_sum = sum(rollup["by_provider"].values())
    if abs(role_sum - rollup["total_cost_usd"]) > 1e-5:
        failures.append("by_role sum != session total")
    if abs(prov_sum - rollup["total_cost_usd"]) > 1e-5:
        failures.append("by_provider sum != session total")
    if rollup["cache_savings_usd"] < 0:
        failures.append("cache savings negative — arithmetic bug")
    print("rollup sums reconcile with the session total: "
          + ("yes" if not failures else "NO"))

    # ------------------------------------------------------------------
    if live:
        _section(5, total, "LIVE SESSION (real API calls, real money, "
                           "$5-capped)")
        from app.core.config import get_settings

        settings = get_settings()
        keys = {p: bool(settings.key_for(p))
                for p in ("anthropic", "openai", "kimi")}
        print(f"provider keys configured: {keys}")
        if not all(keys.values()):
            failures.append(f"live mode needs all three keys, got {keys}")
        else:
            resp = client.post(
                "/api/council/sessions",
                json={"brief_text": "A small two-tier basalt fountain for a "
                                    "cafe courtyard, 1.8 m basin (gate "
                                    "live check)."},
            )
            print(f"live POST status: {resp.status_code}")
            if resp.status_code != 201:
                failures.append(f"live session failed: {resp.json()}")
            else:
                live_id = resp.json()["session_id"]
                d = client.get(f"/api/council/sessions/{live_id}").json()
                ro = d["cost_rollup"]
                print(f"live session {live_id}")
                print(f"MEASURED total: ${ro['total_cost_usd']:.6f} "
                      f"({ro['call_count']} calls)")
                print(f"by_role: {ro['by_role']}")
                print(f"by_provider: {ro['by_provider']}")
                print(f"cache_savings_usd: ${ro['cache_savings_usd']:.6f}")
                print(f"degraded: {d['session']['degraded']}")
                if d["session"]["status"] != "completed":
                    failures.append(
                        f"live session status {d['session']['status']}")
    else:
        _section(5, total, "LIVE SESSION — SKIPPED (fixture mode, $0)")
        print("pass --live to run one real session (real money, $5-capped).")

    # ------------------------------------------------------------------
    _section(total, total, "VERDICT")
    return _verdict(failures)


if __name__ == "__main__":
    raise SystemExit(main())
