#!/usr/bin/env python3
"""Backup and restore — Phase 13 slice A.

    python scripts/backup_restore.py backup  --out backups/luxuryform-YYYYMMDD.zip
    python scripts/backup_restore.py restore --archive backups/x.zip --into DIR
    python scripts/backup_restore.py verify  --dir DIR

Backup covers the two things that ARE the platform's memory: the SQLite
database and the artifact store (data/designs, data/exports). The database
is copied with sqlite3's online backup API — never a file copy of a live
database, which snapshots a torn WAL state and corrupts silently.

Restore unpacks into a fresh directory and then PROVES itself: it runs the
shipped LUXEXCHANGE verifier (Phase 9A) against the newest restored package
and compares row counts against the manifest written at backup time. "The
files are there" is not a restore proof; a package that re-verifies is.

Operator usage (PowerShell, from the repo root):

    docker compose exec backend python scripts/backup_restore.py backup --out data/backups/latest.zip
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

MANIFEST_NAME = "backup_manifest.json"
#: Tables whose row counts prove the database restored whole.
COUNTED_TABLES = (
    "sessions", "ai_calls", "council_sessions", "design_specs", "designs",
    "validation_reports", "exports", "designdna", "intakes", "jobs",
)


def _db_path() -> Path:
    return Path(os.environ.get("LUXURYFORM_DB", str(REPO_ROOT / "data" / "luxuryform.db")))


def _data_dir() -> Path:
    return Path(os.environ.get("LUXURYFORM_DATA_DIR", str(REPO_ROOT / "data")))


def _table_counts(db_file: Path) -> dict[str, int]:
    con = sqlite3.connect(str(db_file))
    counts: dict[str, int] = {}
    for table in COUNTED_TABLES:
        try:
            counts[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = -1  # table absent in this schema generation
    con.close()
    return counts


def cmd_backup(out: Path) -> int:
    db_path = _db_path()
    data_dir = _data_dir()
    if not db_path.exists():
        print(f"FAIL: database not found at {db_path}")
        return 2

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / "luxuryform.db"
        # Online backup: consistent even while the backend is writing.
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(snapshot))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()

        counts = _table_counts(snapshot)
        artifact_files: list[str] = []
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=1) as zf:
            zf.write(snapshot, "luxuryform.db")
            for sub in ("designs", "exports"):
                root = data_dir / sub
                if not root.exists():
                    continue
                for path in sorted(root.rglob("*")):
                    if path.is_file():
                        arc = f"artifacts/{sub}/{path.relative_to(root).as_posix()}"
                        zf.write(path, arc)
                        artifact_files.append(arc)
            zf.writestr(MANIFEST_NAME, json.dumps({
                "schema": "luxuryform_backup_v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "table_counts": counts,
                "artifact_count": len(artifact_files),
            }, indent=2, sort_keys=True))

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"backup written: {out} ({size_mb:.1f} MB)")
    print(f"  tables : { {k: v for k, v in counts.items() if v > 0} }")
    print(f"  files  : {len(artifact_files)} artifacts")
    return 0


def cmd_restore(archive: Path, into: Path) -> int:
    if not archive.exists():
        print(f"FAIL: archive not found: {archive}")
        return 2
    into.mkdir(parents=True, exist_ok=True)
    if any(into.iterdir()):
        print(f"FAIL: restore target {into} is not empty — refusing to merge "
              f"a backup over existing data")
        return 2
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(into)
    # Normalise layout: db at root, artifacts under data-like structure.
    print(f"restored into {into}")
    print("  database : luxuryform.db")
    print("  artifacts: artifacts/designs, artifacts/exports")
    return cmd_verify(into)


def cmd_verify(restored: Path) -> int:
    """Prove the restore: manifest counts match, and the newest LUXEXCHANGE
    package still verifies with its own shipped checker."""
    manifest_path = restored / MANIFEST_NAME
    db_file = restored / "luxuryform.db"
    failures: list[str] = []

    if not manifest_path.exists() or not db_file.exists():
        print("FAIL: not a luxuryform backup (manifest or database missing)")
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    counts_now = _table_counts(db_file)
    for table, expected in manifest["table_counts"].items():
        got = counts_now.get(table, -1)
        if got != expected:
            failures.append(f"table {table}: manifest says {expected}, restored has {got}")

    packages = sorted((restored / "artifacts" / "exports").rglob("luxexchange_v1.zip"))
    if packages:
        newest = packages[-1]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with zipfile.ZipFile(newest) as zf:
                    zf.extractall(tmp)
                proc = subprocess.run(
                    [sys.executable, str(Path(tmp) / "verify_luxexchange.py")],
                    capture_output=True, text=True, cwd=tmp,
                )
            if proc.returncode != 0:
                failures.append(
                    f"restored package {newest.name} FAILED its own verifier:\n"
                    + proc.stdout.strip()
                )
            else:
                print(f"  package  : {newest.relative_to(restored)} re-verified OK")
        except (zipfile.BadZipFile, OSError) as exc:
            # A corrupt archive must be a REPORT, not a traceback — the
            # operator reads this output to decide whether to trust a restore.
            failures.append(
                f"restored package {newest.name} is corrupt and could not even "
                f"be opened: {exc}"
            )
    else:
        print("  package  : no LUXEXCHANGE package in this backup (nothing exported yet)")

    if failures:
        print("RESTORE VERIFICATION FAILED")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("RESTORE VERIFICATION PASSED")
    print(f"  tables checked: {len(manifest['table_counts'])}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("restore")
    r.add_argument("--archive", type=Path, required=True)
    r.add_argument("--into", type=Path, required=True)
    v = sub.add_parser("verify")
    v.add_argument("--dir", type=Path, required=True)
    args = parser.parse_args()
    if args.cmd == "backup":
        return cmd_backup(args.out)
    if args.cmd == "restore":
        return cmd_restore(args.archive, args.into)
    return cmd_verify(args.dir)


if __name__ == "__main__":
    sys.exit(main())
