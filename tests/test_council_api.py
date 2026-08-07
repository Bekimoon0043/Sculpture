"""Council transcript API tests (Phase 3, build step 3).

In-process FastAPI TestClient against a throwaway DB. Proves:
  1. POST /api/council/demo-session replays the committed synthetic fixture
     ($0) and is idempotent (second call creates nothing);
  2. GET /api/council/sessions lists it, labeled synthetic;
  3. GET /api/council/sessions/{id} returns the full transcript — 16 calls,
     3 schema-valid specs, reviews, defect lists, arbiter decision — plus
     the cost rollup with caps and cache-savings arithmetic;
  4. unknown session id -> 404.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_council
from app.db.database import get_default_db, reset_default_db

# A minimal app mounting ONLY the council router: app.main also imports
# routes_geometry -> build123d, which is unavailable outside Docker. The
# full-app wiring (main.py includes routes_council) is asserted by
# tests/test_structure.py and exercised end-to-end in Docker.
app = FastAPI()
app.include_router(routes_council.router, prefix="/api")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LUXURYFORM_DB", str(tmp_path / "council_api_test.db"))
    monkeypatch.setenv("LUXURYFORM_DATA_DIR", str(tmp_path / "data"))
    reset_default_db()
    get_default_db().init_db()
    with TestClient(app) as test_client:
        yield test_client
    reset_default_db()


def test_demo_session_load_list_detail(client):
    # 1. load the demo session — $0, synthetic
    r = client.post("/api/council/demo-session")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    assert body["synthetic"] is True
    session_id = body["session_id"]

    # idempotent: second load creates nothing
    r2 = client.post("/api/council/demo-session")
    assert r2.status_code == 200
    assert r2.json()["created"] is False

    # 2. session list, labeled synthetic
    r = client.get("/api/council/sessions")
    assert r.status_code == 200
    sessions = r.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["id"] == session_id
    assert sessions[0]["synthetic"] is True
    assert sessions[0]["status"] == "completed"
    assert sessions[0]["total_cost_usd"] > 0

    # 3. full transcript
    r = client.get(f"/api/council/sessions/{session_id}")
    assert r.status_code == 200, r.text
    d = r.json()

    assert d["session"]["id"] == session_id
    assert d["session"]["synthetic"] is True

    # 16 calls with full prompt/response and ADR-022 cache fields present
    assert len(d["calls"]) == 16
    roles = {c["role"] for c in d["calls"]}
    assert "designer" in roles and "arbiter" in roles
    for c in d["calls"]:
        assert c["prompt"] and c["response"]
        assert "cached_input_tokens" in c
        assert "cache_write_input_tokens" in c

    # 3 schema-valid specs with tamper-evident hashes
    assert len(d["specs"]) == 3
    for spec in d["specs"]:
        assert spec["schema_valid"] == 1
        assert len(spec["spec_hash"]) == 64
        json.loads(spec["spec_json"])  # parses

    assert len(d["engineering_reviews"]) == 2
    assert len(d["defect_lists"]) == 2

    decision = d["arbiter_decision"]
    assert decision is not None
    assert 0.0 <= decision["confidence"] <= 1.0
    chosen = json.loads(decision["chosen_spec_ids_json"])
    assert len(chosen) == 3
    assert decision["binding"] == 1

    # cost rollup: totals agree, caps present, cache arithmetic is honest
    rollup = d["cost_rollup"]
    assert rollup["call_count"] == 16
    assert rollup["total_cost_usd"] == d["session"]["total_cost_usd"]
    assert abs(sum(rollup["by_role"].values()) - rollup["total_cost_usd"]) < 1e-5
    assert abs(sum(rollup["by_provider"].values()) - rollup["total_cost_usd"]) < 1e-5
    assert rollup["session_cap_usd"] == 5.00
    assert rollup["day_cap_usd"] == 25.00
    assert "cache_savings_usd" in rollup
    assert rollup["pricing_version"] == "2026-08-v3"


def test_main_app_wires_council_router():
    # The minimal test app above mounts routes_council directly; this source
    # assertion proves the REAL app (app.main, imported in Docker tests where
    # build123d exists) serves the same routes.
    from app.core.config import REPO_ROOT

    src = (REPO_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert "routes_council" in src
    assert 'app.include_router(routes_council.router, prefix="/api")' in src


def test_unknown_session_404(client):
    r = client.get("/api/council/sessions/does-not-exist")
    assert r.status_code == 404
