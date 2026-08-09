"""SQLite database access for LuxuryForm Studio v1.

SQLite in WAL mode (ADR-001): crash-safe, single-file, zero-administration —
the right fit for a local-first platform operated by a non-programmer.

The database path comes from the LUXURYFORM_DB environment variable
(default ./data/luxuryform.db) and is auto-created, including parent dirs.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

log = logging.getLogger("luxuryform.db")

SCHEMA_SQL_PATH = Path(__file__).resolve().parent / "schema.sql"
DEFAULT_DB_PATH = "./data/luxuryform.db"

#: Current schema version. v2 = Phase 2 (designs cascade columns,
#: schema_migrations bookkeeping). v3 = Phase 3 (normalized Council tables:
#: council_calls, engineering_reviews, defect_lists, arbiter_decisions;
#: council_sessions/design_specs re-shaped for the real Council).
SCHEMA_VERSION = 3

#: Column whose presence proves a `designs` table is at least Phase 2 shape.
_PHASE2_DESIGNS_MARKER_COLUMN = "spec_hash"

#: Table whose presence proves the file is already Phase 3 shape.
_PHASE3_MARKER_TABLE = "arbiter_decisions"


class SchemaDriftError(RuntimeError):
    """The database file does not match the code's schema and the mismatch
    is NOT auto-patchable. Raised at startup — never mid-session after
    provider calls have been billed."""


#: Additive columns introduced after a schema version shipped. schema.sql
#: CREATE TABLE statements never touch an EXISTING database file, so these
#: are applied via ALTER TABLE at startup, idempotently, and recorded in the
#: schema_patches table. (ADR-023: the operator's v3 file predates the
#: ADR-022 cache columns and crashed mid-session.)
_ADDITIVE_COLUMN_PATCHES: dict[tuple[str, str], str] = {
    ("ai_calls", "cached_input_tokens"):
        "cached_input_tokens INTEGER NOT NULL DEFAULT 0",
    ("ai_calls", "cache_write_input_tokens"):
        "cache_write_input_tokens INTEGER NOT NULL DEFAULT 0",
    ("council_calls", "cached_input_tokens"):
        "cached_input_tokens INTEGER NOT NULL DEFAULT 0",
    ("council_calls", "cache_write_input_tokens"):
        "cache_write_input_tokens INTEGER NOT NULL DEFAULT 0",
}


class Database:
    """Owns the SQLAlchemy engine for one SQLite database file."""

    def __init__(self, path: str | Path | None = None) -> None:
        raw = str(path) if path is not None else os.environ.get(
            "LUXURYFORM_DB", DEFAULT_DB_PATH
        )
        self.path = Path(raw)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{self.path}", future=True, isolation_level="AUTOCOMMIT"
        )

        @event.listens_for(self.engine, "connect")
        def _set_pragmas(dbapi_conn: sqlite3.Connection, _record) -> None:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        self._session_factory = sessionmaker(
            bind=self.engine, class_=Session, future=True, autoflush=True,
            expire_on_commit=False,
        )

    def init_db(self) -> None:
        """Migrate if needed, then create every table from schema.sql.

        Migration (SPEC_PHASE2 §2 pattern, extended in Phase 3): an old
        database file is RENAMED to a backup (never deleted) and a fresh
        current-schema database is created. Phase 1 file (designs without
        spec_hash) -> ``<name>.phase1-backup.db``; Phase 2 file (has
        spec_hash but no arbiter_decisions table) ->
        ``<name>.phase2-backup.db`` (plus ``-2``, ``-3`` ... if a backup
        already exists).
        """
        note = self._migrate_old_file_if_needed()
        script = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
        with self.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            for statement in _split_sql_script(script):
                conn.exec_driver_sql(statement)
            conn.exec_driver_sql(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at, note) "
                "VALUES (:version, :applied_at, :note)",
                {
                    "version": SCHEMA_VERSION,
                    "applied_at": datetime.now(timezone.utc).isoformat(),
                    "note": note,
                },
            )
            self._apply_additive_patches(conn)
        self._verify_no_drift()

    @staticmethod
    def _apply_additive_patches(conn) -> None:
        """ALTER TABLE any known post-version columns into an existing file.

        Idempotent: PRAGMA table_info decides, schema_patches records. Runs
        BEFORE the app serves anything, so a schema mismatch can never
        surface as a mid-session crash after billed provider calls.
        """
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_patches ("
            "table_name TEXT NOT NULL, column_name TEXT NOT NULL, "
            "applied_at TEXT NOT NULL, "
            "PRIMARY KEY (table_name, column_name))"
        )
        for (table, column), ddl in sorted(_ADDITIVE_COLUMN_PATCHES.items()):
            existing = {
                row[1]
                for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            if not existing:  # table itself absent -> schema.sql creates it
                continue
            if column in existing:
                continue
            conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {ddl}")
            conn.exec_driver_sql(
                "INSERT OR IGNORE INTO schema_patches "
                "(table_name, column_name, applied_at) VALUES (?, ?, ?)",
                (table, column, datetime.now(timezone.utc).isoformat()),
            )
            log.warning(
                "schema patch applied: %s.%s added via ALTER TABLE "
                "(recorded in schema_patches)", table, column,
            )

    def _verify_no_drift(self) -> None:
        """Fail loudly if a mapped column is missing and NOT auto-patchable.

        The operator-facing remedy is printed verbatim: back up the file,
        delete it, restart — never a silent guess.
        """
        from app.db.models import Base  # local import: models imports nothing here

        missing: list[str] = []
        with self.engine.connect() as conn:
            for table in Base.metadata.sorted_tables:
                existing = {
                    row[1]
                    for row in conn.exec_driver_sql(
                        f"PRAGMA table_info({table.name})"
                    )
                }
                if not existing:
                    continue  # absent tables are created by schema.sql
                for column in table.columns:
                    if column.name not in existing:
                        missing.append(f"{table.name}.{column.name}")
        if missing:
            raise SchemaDriftError(
                "database schema does not match the code; missing columns: "
                + ", ".join(missing)
                + ". These are NOT auto-patchable. Remedy: stop the stack, "
                "copy the database file somewhere safe (it keeps all your "
                "history), delete the original, and start again — a fresh "
                "current-schema database is created automatically."
            )

    def _migrate_old_file_if_needed(self) -> str:
        """Rename a Phase 1 or Phase 2 database file out of the way; return
        the schema_migrations note for this init."""
        if not self.path.exists():
            return "fresh Phase 3 schema (v3) created"
        conn = sqlite3.connect(str(self.path))
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            columns = (
                {row[1] for row in conn.execute("PRAGMA table_info(designs)")}
                if "designs" in tables
                else set()
            )
        finally:
            conn.close()

        if _PHASE3_MARKER_TABLE in tables:
            return "existing Phase 3 database; schema (v3) verified idempotently"

        if "designs" in tables and _PHASE2_DESIGNS_MARKER_COLUMN not in columns:
            phase, backup_tag = "Phase 1", "phase1-backup"
        elif "designs" not in tables:
            # Pre-Phase-2 file without designs (only possible from very early
            # Phase 1 dev); treat as Phase 1.
            phase, backup_tag = "Phase 1", "phase1-backup"
        else:
            phase, backup_tag = "Phase 2", "phase2-backup"

        backup = self._next_backup_path(backup_tag)
        # Close our own engine's connections before moving the file.
        self.engine.dispose()
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(self.path) + suffix)
            if candidate.exists():
                candidate.rename(Path(str(backup) + suffix))
        log.warning(
            "%s database %s renamed to %s; a fresh Phase 3 database was "
            "created. The backup is never deleted automatically.",
            phase,
            self.path,
            backup,
        )
        return (
            f"{phase} database renamed to {backup.name} (never deleted); "
            "fresh Phase 3 schema (v3) created"
        )

    def _next_backup_path(self, tag: str = "phase1-backup") -> Path:
        """First free <stem>.<tag><.suffix>[, -2, -3...] path."""
        base = self.path.with_name(f"{self.path.stem}.{tag}{self.path.suffix}")
        candidate = base
        counter = 2
        while candidate.exists():
            candidate = Path(f"{base}-{counter}")
            counter += 1
        return candidate

    @contextmanager
    def get_session(self) -> Iterator[Session]:
        """Transactional session scope; commits on success, rolls back on error."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def _split_sql_script(script: str) -> list[str]:
    """Split schema.sql into individual statements.

    Inline ``--`` comments are stripped line-by-line first (the script has no
    string literals containing ``--`` or ``;``), then the remainder is split
    on ``;``.
    """
    code_lines = []
    for line in script.splitlines():
        code = line.split("--", 1)[0]  # drop full-line and inline comments
        if code.strip():
            code_lines.append(code)
    statements = [s.strip() for s in "\n".join(code_lines).split(";")]
    return [s for s in statements if s]


_default_db: Database | None = None


def get_default_db() -> Database:
    """Process-wide Database for the API, honouring LUXURYFORM_DB."""
    global _default_db
    if _default_db is None:
        _default_db = Database()
    return _default_db


def reset_default_db() -> None:
    """Drop the cached default Database (used by the gate to re-point
    LUXURYFORM_DB at its own throwaway file)."""
    global _default_db
    _default_db = None
