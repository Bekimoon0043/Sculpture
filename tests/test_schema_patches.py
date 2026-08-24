"""Additive schema patch tests (ADR-023, 2026-08-07).

Defect found by the operator's first live session: their luxuryform.db was
created under the EARLIER v3 (before the ADR-022 cache columns) and
persisted in a Docker volume — editing schema.sql never alters an existing
database, so the session crashed mid-run with
"table ai_calls has no column named cached_input_tokens".

Proves:
  1. a pre-patch v3 file gets the cache columns via ALTER TABLE at startup,
     its data preserved, the patches recorded in schema_patches;
  2. the patch pass is idempotent;
  3. a v3 file missing a NON-patchable column raises SchemaDriftError at
     startup with the operator remedy — never a mid-session crash after
     provider calls have been billed.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.core.config import REPO_ROOT
from app.db.database import Database, SchemaDriftError, _split_sql_script

SCHEMA = (REPO_ROOT / "backend" / "app" / "db" / "schema.sql").read_text(
    encoding="utf-8"
)

_CACHE_FRAGMENTS = [
    "    cached_input_tokens INTEGER NOT NULL DEFAULT 0,  -- cache-READ class (ADR-022)\n",
    "    cache_write_input_tokens INTEGER NOT NULL DEFAULT 0, -- cache-WRITE class (anthropic only)\n",
]

_LINEAGE_FRAGMENTS = [
    "    project_id      TEXT REFERENCES projects(id), -- NULL = legacy/ungrouped\n",
    "    parent_design_id TEXT REFERENCES designs(id)  -- NULL = root variant\n",
]

# ADR-025: the corrected column postdates the operator's live database too.
_CORRECTED_BLOCK = (
    "    degraded           INTEGER NOT NULL DEFAULT 0, -- 1 = provider failure left a seat empty/reduced\n"
    "    corrected          INTEGER NOT NULL DEFAULT 0  -- ADR-025: 1 = a bounded re-ask succeeded (self-correction)\n"
)
_CORRECTED_ORIGINAL = (
    "    degraded           INTEGER NOT NULL DEFAULT 0  -- 1 = ran without parallel comparison\n"
)


def _old_v3_script() -> str:
    """The v3 schema as it existed BEFORE the ADR-022 cache columns and the
    ADR-025 corrected column (i.e. the operator's real live database)."""
    script = SCHEMA
    for frag in _CACHE_FRAGMENTS:
        assert frag in script, "schema.sql changed — update this test"
        script = script.replace(frag, "")
    for frag in _LINEAGE_FRAGMENTS:
        assert frag in script, "schema.sql changed — update this test"
        script = script.replace(frag, "")
    script = script.replace(
        "    step_path       TEXT,                    -- canonical STEP artifact\n",
        "    step_path       TEXT                     -- canonical STEP artifact\n",
    )
    assert _CORRECTED_BLOCK in script, "schema.sql changed — update this test"
    script = script.replace(_CORRECTED_BLOCK, _CORRECTED_ORIGINAL)
    return script


def _create_db(path, script: str) -> None:
    con = sqlite3.connect(str(path))
    for statement in _split_sql_script(script):
        con.execute(statement)
    con.commit()
    con.close()


def test_prepatch_v3_file_is_altered_data_preserved(tmp_path):
    path = tmp_path / "oldv3.db"
    _create_db(path, _old_v3_script())
    con = sqlite3.connect(str(path))
    con.execute(
        "INSERT INTO ai_calls (id, session_id, ts, provider, model, purpose,"
        " prompt, response, tokens_in, tokens_out, latency_ms, cost_usd,"
        " pricing_version, status) VALUES ('c1','s1','2026-08-07T00:00:00Z',"
        "'kimi','kimi-k3','test','p','r',1,1,1.0,0.001,'2026-08-v2','ok')"
    )
    con.commit()
    con.close()

    Database(path).init_db()

    con = sqlite3.connect(str(path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(ai_calls)")}
    assert {"cached_input_tokens", "cache_write_input_tokens"} <= cols
    cols = {r[1] for r in con.execute("PRAGMA table_info(council_calls)")}
    assert {"cached_input_tokens", "cache_write_input_tokens"} <= cols
    # data preserved, new columns default to 0
    assert con.execute(
        "SELECT id, cached_input_tokens FROM ai_calls"
    ).fetchall() == [("c1", 0)]
    cols = {r[1] for r in con.execute("PRAGMA table_info(council_sessions)")}
    assert "corrected" in cols
    patches = con.execute(
        "SELECT table_name, column_name FROM schema_patches ORDER BY 1, 2"
    ).fetchall()
    # EVERY declared patch must have been applied and recorded. Deriving the
    # expectation from the declaration (rather than a hardcoded list) keeps
    # this honest as later phases add columns — Phase 8 added
    # validation_reports.status, Phase 9A added six on exports — while still
    # failing loudly if a declared patch is silently skipped.
    from app.db.database import _ADDITIVE_COLUMN_PATCHES

    assert patches == sorted(_ADDITIVE_COLUMN_PATCHES)
    assert ("council_sessions", "corrected") in patches      # ADR-023
    assert ("validation_reports", "status") in patches       # Phase 8
    assert ("exports", "sha256") in patches                  # Phase 9A
    assert ("designs", "project_id") in patches              # Phase 15E
    assert ("designs", "parent_design_id") in patches        # Phase 15E
    con.close()

    # idempotent: a second startup applies nothing and does not fail
    Database(path).init_db()


def test_unpatchable_drift_fails_loudly_at_startup(tmp_path):
    # a v3-shaped file (has arbiter_decisions) missing a non-patch column
    i = SCHEMA.index("CREATE TABLE IF NOT EXISTS ai_calls")
    j = SCHEMA.index(");", i)
    drifted = (
        SCHEMA[:i]
        + SCHEMA[i:j].replace(
            "    prompt          TEXT NOT NULL,"
            "           -- full prompt, always (Rule 8)\n",
            "",
        )
        + SCHEMA[j:]
    )
    path = tmp_path / "drift.db"
    _create_db(path, drifted)

    with pytest.raises(SchemaDriftError, match="ai_calls.prompt"):
        Database(path).init_db()


def test_fresh_database_has_everything(tmp_path):
    path = tmp_path / "fresh.db"
    Database(path).init_db()
    con = sqlite3.connect(str(path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(ai_calls)")}
    assert {"cached_input_tokens", "cache_write_input_tokens"} <= cols
    con.close()
