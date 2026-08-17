"""API round-trip tests [ADD-3]: FastAPI TestClient, in-process, no ports.

Proves the exact path the UI button drives: defaults -> build -> build again
with a changed parameter -> new GLB served -> validation JSON — plus 422 with
real-number violations on a constraint breach.
"""

from __future__ import annotations

import re

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")
trimesh = pytest.importorskip("trimesh", reason="trimesh not installed")

from fastapi.testclient import TestClient  # noqa: E402

from app.db.database import reset_default_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LUXURYFORM_DB", str(tmp_path / "api_test.db"))
    monkeypatch.setenv("LUXURYFORM_DATA_DIR", str(tmp_path / "data"))
    reset_default_db()
    with TestClient(app) as test_client:  # startup event runs init_db
        yield test_client
    reset_default_db()


def test_defaults_endpoint(client):
    resp = client.get("/api/geometry/cascade/defaults")
    assert resp.status_code == 200
    body = resp.json()
    assert "tiers" in body["parameters"]
    assert len(body["parameters"]) == 13
    assert body["parameters"]["basin_diameter_mm"]["default"] == 2600
    assert "basalt_slab" in body["materials"]
    assert body["materials"]["basalt_slab"]["min_wall_mm"] == 20


def test_full_build_round_trip(client):
    r3 = client.post("/api/geometry/cascade/build",
                     json={"parameters": {"tiers": 3}, "seed": 42})
    assert r3.status_code == 200, r3.text
    b3 = r3.json()
    assert b3["validation"]["watertight"] is True
    assert b3["validation"]["passed"] is True
    assert b3["build_ms"] > 0
    assert len(b3["step_sha256"]) == 64

    r4 = client.post("/api/geometry/cascade/build",
                     json={"parameters": {"tiers": 4}, "seed": 42})
    assert r4.status_code == 200, r4.text
    b4 = r4.json()

    # the rebuild actually changed the geometry + artifacts
    assert b4["spec_hash"] != b3["spec_hash"]
    assert b4["step_sha256"] != b3["step_sha256"]
    assert b4["validation"]["volume_mm3"] != b3["validation"]["volume_mm3"]

    glb = client.get("/api/geometry/cascade/latest.glb")
    assert glb.status_code == 200
    assert glb.content[:4] == b"glTF"

    step = client.get("/api/geometry/cascade/latest.step")
    assert step.status_code == 200
    assert b"ISO-10303-21" in step.content

    val = client.get("/api/geometry/cascade/latest/validation")
    assert val.status_code == 200
    vbody = val.json()
    assert vbody["passed"] is True
    assert vbody["validation"]["volume_mm3"] == b4["validation"]["volume_mm3"]


def test_deterministic_rebuild_same_seed_same_step_hash(client):
    ra = client.post("/api/geometry/cascade/build",
                     json={"parameters": {"tiers": 2}, "seed": 99})
    rb = client.post("/api/geometry/cascade/build",
                     json={"parameters": {"tiers": 2}, "seed": 99})
    assert ra.status_code == rb.status_code == 200
    assert ra.json()["step_sha256"] == rb.json()["step_sha256"]
    assert ra.json()["spec_hash"] == rb.json()["spec_hash"]


def test_422_carries_real_number_violations(client):
    resp = client.post(
        "/api/geometry/cascade/build",
        json={"parameters": {"basin_diameter_mm": 1000}, "seed": 0},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    violations = detail["violations"]
    assert isinstance(violations, list) and violations
    joined = " ".join(violations)
    assert "basin_diameter_mm=1000" in joined
    assert "1540" in joined  # required basin diameter with defaults
    assert re.search(r"\d", joined)


def test_422_wall_below_material_minimum(client):
    resp = client.post(
        "/api/geometry/cascade/build",
        json={"parameters": {"basin_wall_mm": 5, "basin_diameter_mm": 4000}},
    )
    assert resp.status_code == 422
    joined = " ".join(resp.json()["detail"]["violations"])
    assert "basin_wall_mm=5" in joined
    assert "material minimum 20" in joined


def test_latest_glb_404_before_any_build(tmp_path, monkeypatch):
    monkeypatch.setenv("LUXURYFORM_DB", str(tmp_path / "empty.db"))
    monkeypatch.setenv("LUXURYFORM_DATA_DIR", str(tmp_path / "data"))
    reset_default_db()
    with TestClient(app) as c:
        assert c.get("/api/geometry/cascade/latest.glb").status_code == 404
        assert c.get("/api/geometry/cascade/latest/validation").status_code == 404
    reset_default_db()


def test_phase1_db_is_renamed_not_deleted(tmp_path, monkeypatch):
    """A Phase 1-shape database file (designs without spec_hash) is migrated
    by RENAMING it to a backup; the fresh DB records schema_migrations."""
    import sqlite3

    db_path = tmp_path / "luxuryform.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE designs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, "
        "spec_id TEXT NOT NULL, geometry_hash TEXT, parameter_json TEXT NOT NULL, "
        "status TEXT NOT NULL DEFAULT 'built')"
    )
    conn.execute(
        "INSERT INTO designs (id, created_at, spec_id, parameter_json) "
        "VALUES ('d1', '2026-07-31T00:00:00', 's1', '{}')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("LUXURYFORM_DB", str(db_path))
    monkeypatch.setenv("LUXURYFORM_DATA_DIR", str(tmp_path / "data"))
    reset_default_db()
    with TestClient(app) as c:
        resp = c.get("/api/geometry/cascade/defaults")
        assert resp.status_code == 200
    reset_default_db()

    backup = tmp_path / "luxuryform.phase1-backup.db"
    assert backup.exists(), "Phase 1 DB must be renamed, never deleted"
    kept = sqlite3.connect(str(backup))
    assert kept.execute("SELECT id FROM designs").fetchall() == [("d1",)]
    kept.close()

    fresh = sqlite3.connect(str(db_path))
    cols = {row[1] for row in fresh.execute("PRAGMA table_info(designs)")}
    assert "spec_hash" in cols
    assert "arbiter_decisions" in {
        row[0] for row in fresh.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    # Assert against the LIVE constant, never a literal: this test hardcoded
    # (3,) and started failing the moment Phase 4 bumped the schema to v4,
    # which is a bookkeeping change, not a regression in what it guards.
    from app.db.database import SCHEMA_VERSION

    versions = fresh.execute("SELECT version FROM schema_migrations").fetchall()
    assert (SCHEMA_VERSION,) in versions
    fresh.close()
