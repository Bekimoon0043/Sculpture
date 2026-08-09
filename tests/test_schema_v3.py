"""Schema v3 tests (Phase 3, build step 1).

- A fresh database gets the Phase 3 tables with the planned columns.
- A Phase 2-shape file (designs WITH spec_hash, no arbiter_decisions) is
  migrated by RENAMING it to <name>.phase2-backup.db — never deleted —
  and a fresh v3 database is created (SPEC_PHASE2 §2 pattern, extended).
- A v3 database re-inits idempotently (no rename, note says verified).
"""

from __future__ import annotations

import sqlite3

from app.db.database import Database, SCHEMA_VERSION

V3_TABLES = {
    "council_sessions",
    "council_calls",
    "design_specs",
    "engineering_reviews",
    "defect_lists",
    "arbiter_decisions",
}


def _tables(path) -> set[str]:
    conn = sqlite3.connect(str(path))
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def _columns(path, table: str) -> set[str]:
    conn = sqlite3.connect(str(path))
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_fresh_db_has_phase3_tables_and_columns(tmp_path):
    db = Database(tmp_path / "fresh.db")
    db.init_db()
    tables = _tables(tmp_path / "fresh.db")
    assert V3_TABLES <= tables

    assert {
        "id", "created_at", "brief_text", "status", "started_at", "ended_at",
        "total_cost_usd", "pricing_version", "arbiter_confidence", "degraded",
        "corrected",
    } <= _columns(tmp_path / "fresh.db", "council_sessions")
    assert {
        "id", "session_id", "ts", "role", "side", "provider", "model",
        "prompt", "response", "tokens_in", "tokens_out", "latency_ms",
        "cost_usd", "pricing_version", "status", "error",
    } <= _columns(tmp_path / "fresh.db", "council_calls")
    assert {
        "id", "created_at", "session_id", "provider", "alternative_no",
        "spec_json", "spec_hash", "seed", "schema_valid",
    } <= _columns(tmp_path / "fresh.db", "design_specs")
    assert {
        "id", "created_at", "session_id", "chosen_spec_ids_json",
        "confidence", "rationale", "disagreement_register_json", "binding",
    } <= _columns(tmp_path / "fresh.db", "arbiter_decisions")

    versions = _tables(tmp_path / "fresh.db")  # noqa: F841
    conn = sqlite3.connect(str(tmp_path / "fresh.db"))
    recorded = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    conn.close()
    assert SCHEMA_VERSION in recorded
    assert SCHEMA_VERSION == 3


def test_phase2_db_is_renamed_to_phase2_backup_never_deleted(tmp_path):
    """Build a Phase 2-shape file (designs with spec_hash, no v3 tables),
    then init: it must be renamed to .phase2-backup.db with data intact."""
    path = tmp_path / "luxuryform.db"
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE designs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, "
        "spec_id TEXT, geometry_hash TEXT, parameter_json TEXT NOT NULL, "
        "status TEXT NOT NULL DEFAULT 'built', seed INTEGER, spec_hash TEXT, "
        "build_ms REAL, glb_path TEXT, step_path TEXT)"
    )
    conn.execute(
        "INSERT INTO designs (id, created_at, spec_id, parameter_json, spec_hash) "
        "VALUES ('d-phase2', '2026-08-02T00:00:00', NULL, '{}', 'abc123')"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    db.init_db()

    backup = tmp_path / "luxuryform.phase2-backup.db"
    assert backup.exists(), "Phase 2 DB must be renamed to .phase2-backup.db"
    kept = sqlite3.connect(str(backup))
    rows = kept.execute("SELECT id, spec_hash FROM designs").fetchall()
    kept.close()
    assert rows == [("d-phase2", "abc123")], "backup data must be intact"

    fresh_tables = _tables(path)
    assert V3_TABLES <= fresh_tables, "fresh v3 database must be created"


def test_v3_db_reinit_is_idempotent_no_rename(tmp_path):
    path = tmp_path / "luxuryform.db"
    Database(path).init_db()
    Database(path).init_db()
    Database(path).init_db()
    assert not (tmp_path / "luxuryform.phase2-backup.db").exists()
    assert not (tmp_path / "luxuryform.phase1-backup.db").exists()
    assert V3_TABLES <= _tables(path)
    conn = sqlite3.connect(str(path))
    versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    conn.close()
    assert versions == {3}, "schema_migrations records a version once (PK)"


def test_phase1_db_still_renamed_to_phase1_backup(tmp_path):
    """The v1 -> backup path must survive the chain (oldest files)."""
    path = tmp_path / "luxuryform.db"
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE designs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, "
        "spec_id TEXT NOT NULL, geometry_hash TEXT, parameter_json TEXT NOT NULL, "
        "status TEXT NOT NULL DEFAULT 'built')"
    )
    conn.commit()
    conn.close()
    Database(path).init_db()
    assert (tmp_path / "luxuryform.phase1-backup.db").exists()
    assert V3_TABLES <= _tables(path)
