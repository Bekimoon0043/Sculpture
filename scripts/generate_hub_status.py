#!/usr/bin/env python3
"""generate_hub_status.py — derive a status JSON for the LuxuryCon AI Command Hub.

ONE DIRECTION: this repo -> the Hub. Nothing here ever reads from, or writes
back to, the Hub. The SQLite database is opened READ-ONLY (mode=ro URI), so a
status run can never mutate platform data.

NOTHING IN THIS FILE IS HAND-MAINTAINED STATE. Every value is derived, at run
time, from:

  - git                    -> commit sha, subject, date, branch, tree cleanliness
  - PHASE_*_PLAN.md        -> build order (numbered steps), phase presence
  - PHASE_*_REPORT.md      -> phase closure, gate verdict headings + dates
  - scripts/gate_phase*.py -> which gates exist
  - LIMITATIONS.md         -> open limitations (RETIRED sections skipped)
  - DECISIONS.md           -> latest ADR number, title, date
  - the SQLite DB          -> API spend (ai_calls) and budget events

If a value cannot be determined it is written as JSON `null` AND an entry
explaining why is appended to the top-level "undetermined" list. A previous
value is NEVER carried forward and a value is NEVER guessed: this script does
not read its own prior output.

Exit codes (non-interactive friendly, no prompts, all output on stdout):

  0  status file written; every field determined
  2  status file written and valid; one or more fields are null
     (each one is listed in the "undetermined" array, with a reason)
  1  fatal: no status file was written

Usage:
  python scripts/generate_hub_status.py
  python scripts/generate_hub_status.py --out /path/beside/your/hub.html/luxuryform_status.json
  python scripts/generate_hub_status.py --db ./data/luxuryform.db --print-json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

GENERATOR_VERSION = "1.0.0"
STATUS_SCHEMA = "luxuryform.hub.status/1"
DEFAULT_DB_RELATIVE = "data/luxuryform.db"
DEFAULT_OUT_RELATIVE = "hub/luxuryform_status.json"

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


# --------------------------------------------------------------------------
# undetermined-value bookkeeping
# --------------------------------------------------------------------------


class Undetermined:
    """Collects every field that could not be derived, with the reason why."""

    def __init__(self) -> None:
        self.items: list[dict[str, str]] = []

    def record(self, field: str, reason: str):
        """Register `field` as undetermined and return None (to be stored)."""
        self.items.append({"field": field, "reason": reason})
        return None


# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> tuple[str | None, str | None]:
    """Run a git command. Returns (stdout, None) or (None, reason)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return None, "git executable not found on PATH"
    except subprocess.TimeoutExpired:
        return None, f"git {' '.join(args)} timed out after 30s"
    except OSError as exc:
        return None, f"git {' '.join(args)} could not be invoked: {exc}"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        first = detail[0] if detail else "(no output)"
        return None, f"git {' '.join(args)} exited {proc.returncode}: {first}"
    return proc.stdout, None


def collect_source(repo: Path, und: Undetermined) -> dict:
    """Commit identity of the tree this status was derived from."""
    out: dict = {
        "commit_sha": None,
        "commit_sha_short": None,
        "commit_subject": None,
        "commit_date_utc": None,
        "branch": None,
        "working_tree_clean": None,
        "dirty_paths": None,
    }

    unit = "\x1f"
    log, reason = _git(repo, "log", "-1", f"--format=%H{unit}%s{unit}%cI")
    if log is None:
        und.record("source.commit_sha", reason or "unknown git failure")
        und.record("source.commit_subject", reason or "unknown git failure")
        und.record("source.commit_date_utc", reason or "unknown git failure")
    else:
        parts = log.strip("\n").split(unit)
        if len(parts) == 3:
            sha, subject, date_iso = parts
            out["commit_sha"] = sha
            out["commit_sha_short"] = sha[:12]
            out["commit_subject"] = subject
            out["commit_date_utc"] = date_iso
        else:
            why = "git log -1 returned an unparseable record"
            und.record("source.commit_sha", why)
            und.record("source.commit_subject", why)
            und.record("source.commit_date_utc", why)

    branch, reason = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch is None:
        und.record("source.branch", reason or "unknown git failure")
    else:
        out["branch"] = branch.strip()

    status, reason = _git(repo, "status", "--porcelain")
    if status is None:
        und.record("source.working_tree_clean", reason or "unknown git failure")
        und.record("source.dirty_paths", reason or "unknown git failure")
    else:
        dirty = [line.rstrip("\n") for line in status.splitlines() if line.strip()]
        out["working_tree_clean"] = not dirty
        out["dirty_paths"] = dirty

    return out


def commit_subjects(repo: Path, limit: int = 300) -> tuple[list[dict], str | None]:
    """Recent commits as [{sha, subject}], newest first."""
    unit = "\x1f"
    log, reason = _git(repo, "log", f"-{limit}", f"--format=%H{unit}%s")
    if log is None:
        return [], reason
    commits = []
    for line in log.splitlines():
        if unit not in line:
            continue
        sha, _, subject = line.partition(unit)
        commits.append({"sha": sha, "subject": subject})
    return commits, None


# --------------------------------------------------------------------------
# markdown helpers
# --------------------------------------------------------------------------


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def headings(text: str) -> list[tuple[int, str]]:
    """(line_number, heading_text) for every ATX markdown heading."""
    found = []
    for i, line in enumerate(text.splitlines(), start=1):
        if line.startswith("#"):
            found.append((i, line.lstrip("#").strip()))
    return found


def clean_inline(s: str) -> str:
    """Strip the markdown that would otherwise leak into the Hub display."""
    s = re.sub(r"~~(.+?)~~", r"\1", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def excerpt(lines: list[str], limit: int = 240) -> str:
    body = clean_inline(" ".join(l.strip() for l in lines if l.strip()))
    if len(body) <= limit:
        return body
    cut = body[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def sections(text: str, level: str = "## ") -> list[dict]:
    """Split markdown into [{heading, line, body:[str]}] at the given level."""
    result: list[dict] = []
    current: dict | None = None
    for i, line in enumerate(text.splitlines(), start=1):
        if line.startswith(level) and not line.startswith(level + "#"):
            current = {"heading": line[len(level):].strip(), "line": i, "body": []}
            result.append(current)
        elif current is not None:
            current["body"].append(line)
    return result


# --------------------------------------------------------------------------
# phases and build steps
# --------------------------------------------------------------------------

PHASE_FILE = re.compile(r"^PHASE_(\d+)_(PLAN|REPORT)\.md$")


def collect_phases(repo: Path, und: Undetermined) -> dict:
    plans: dict[int, Path] = {}
    reports: dict[int, Path] = {}
    for entry in sorted(repo.glob("PHASE_*.md")):
        m = PHASE_FILE.match(entry.name)
        if not m:
            continue
        (plans if m.group(2) == "PLAN" else reports)[int(m.group(1))] = entry

    known = sorted(set(plans) | set(reports))
    if not known:
        return {
            "total_phases": und.record(
                "phase.total_phases", "no PHASE_<n>_PLAN.md or PHASE_<n>_REPORT.md found"
            ),
            "current_phase": und.record(
                "phase.current_phase", "no PHASE_<n>_PLAN.md or PHASE_<n>_REPORT.md found"
            ),
            "current_phase_state": und.record(
                "phase.current_phase_state", "no phase files found to derive state from"
            ),
            "build_step": None,
            "phases": [],
        }

    # "Phase N of M" is the only place the phase count is written down.
    total_phases = None
    for name in ("README.md", *(p.name for p in reports.values()), *(p.name for p in plans.values())):
        text = read_text(repo / name)
        if not text:
            continue
        m = re.search(r"[Pp]hase\s+\d+\s+of\s+(\d+)", text)
        if m:
            total_phases = int(m.group(1))
            break
    if total_phases is None:
        und.record("phase.total_phases", "no 'Phase N of M' statement found in README.md or the phase files")

    phase_rows = []
    for n in known:
        plan, report = plans.get(n), reports.get(n)
        state, evidence = None, None
        if report is not None:
            text = read_text(report) or ""
            m = re.search(rf"PHASE\s+{n}\s+(?:IS\s+)?CLOSED", text, re.I)
            if m:
                state = "closed"
                line_no = text[: m.start()].count("\n") + 1
                evidence = f"{report.name}:{line_no}: {clean_inline(m.group(0))}"
        if state is None:
            if plan is not None and report is None:
                state = "in_progress"
            elif report is not None:
                state = "built_not_closed"
            else:
                state = None
                und.record(
                    f"phase.phases[{n}].state",
                    f"phase {n} has neither a closure statement nor a plan/report combination that implies a state",
                )
        phase_rows.append(
            {
                "phase": n,
                "plan_file": plan.name if plan else None,
                "report_file": report.name if report else None,
                "state": state,
                "closure_evidence": evidence,
            }
        )

    current_phase = max(known)
    current_row = next(r for r in phase_rows if r["phase"] == current_phase)

    return {
        "total_phases": total_phases,
        "current_phase": current_phase,
        "current_phase_state": current_row["state"],
        "build_step": collect_build_step(repo, current_phase, plans.get(current_phase), und),
        "phases": phase_rows,
    }


BUILD_ORDER_HEADING = re.compile(r"^\d*\.?\s*build order\b", re.I)
BUILD_STEP_COMMIT = re.compile(r"phase\s*(\d+)\s*build\s*step\s*(\d+)", re.I)


def collect_build_step(repo: Path, phase: int, plan: Path | None, und: Undetermined) -> dict:
    """Build order from the plan; last completed step from commit subjects."""
    out: dict = {
        "phase": phase,
        "total_steps": None,
        "steps": [],
        "last_completed_step": None,
        "last_completed_evidence": None,
        "next_step": None,
        "next_step_description": None,
    }

    if plan is None:
        und.record(f"phase.build_step.total_steps", f"no PHASE_{phase}_PLAN.md to read a build order from")
    else:
        text = read_text(plan)
        if text is None:
            und.record("phase.build_step.total_steps", f"{plan.name} could not be read")
        else:
            block = None
            for sec in sections(text):
                if BUILD_ORDER_HEADING.match(sec["heading"]):
                    block = sec["body"]
                    break
            if block is None:
                und.record(
                    "phase.build_step.total_steps",
                    f"{plan.name} has no '## N. Build order' section to enumerate steps from",
                )
            else:
                steps: list[dict] = []
                for line in block:
                    m = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
                    if m:
                        steps.append({"step": int(m.group(1)), "description": m.group(2).strip()})
                    elif steps and line.strip() and line.startswith((" ", "\t")):
                        steps[-1]["description"] += " " + line.strip()
                for s in steps:
                    s["description"] = clean_inline(s["description"])
                out["steps"] = steps
                out["total_steps"] = len(steps) or None
                if not steps:
                    und.record(
                        "phase.build_step.total_steps",
                        f"the Build order section of {plan.name} contains no numbered steps",
                    )

    commits, reason = commit_subjects(repo)
    if reason is not None:
        und.record("phase.build_step.last_completed_step", reason)
        return out

    best: tuple[int, dict] | None = None
    for c in commits:
        m = BUILD_STEP_COMMIT.search(c["subject"])
        if m and int(m.group(1)) == phase:
            step = int(m.group(2))
            if best is None or step > best[0]:
                best = (step, c)

    if best is None:
        und.record(
            "phase.build_step.last_completed_step",
            f"no commit subject in the last {len(commits)} commits matches "
            f"'phase {phase} build step <n>', so no step can be claimed complete",
        )
        return out

    step, commit = best
    out["last_completed_step"] = step
    out["last_completed_evidence"] = f"{commit['sha'][:12]}: {commit['subject']}"
    if out["total_steps"] is not None and step < out["total_steps"]:
        out["next_step"] = step + 1
        nxt = next((s for s in out["steps"] if s["step"] == step + 1), None)
        out["next_step_description"] = nxt["description"] if nxt else None
    return out


# --------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------


def collect_gates(repo: Path, phases: list[int], und: Undetermined) -> list[dict]:
    """Gate verdicts are read from markdown HEADINGS only.

    Body text is deliberately excluded: the phase reports quote example
    verdict strings and no-keys FAIL transcripts inline, and a naive
    full-text scan would report those as the real result.
    """
    md_headings: list[tuple[str, int, str]] = []
    for md in sorted(repo.glob("*.md")):
        text = read_text(md)
        if text is None:
            continue
        for line_no, heading in headings(text):
            md_headings.append((md.name, line_no, heading))

    rows = []
    for n in phases:
        scripts = sorted(p.name for p in repo.glob(f"scripts/gate_phase{n}*.py"))
        row: dict = {
            "phase": n,
            "gate_scripts": scripts,
            "status": None,
            "date": None,
            "evidence": None,
        }

        verdict_re = re.compile(rf"PHASE\s+{n}\s+GATE:\s*(PASS|FAIL)", re.I)
        closed_re = re.compile(rf"PHASE\s+{n}\s+(?:IS\s+)?CLOSED", re.I)

        hit = None
        for name, line_no, heading in md_headings:
            m = verdict_re.search(heading)
            if m:
                hit = (m.group(1).upper(), name, line_no, heading)
                break
        if hit is None:
            for name, line_no, heading in md_headings:
                if closed_re.search(heading):
                    hit = ("CLOSED", name, line_no, heading)
                    break

        if hit is None:
            und.record(
                f"gates[phase {n}].status",
                f"no markdown heading states a 'PHASE {n} GATE: PASS/FAIL' verdict "
                f"or a 'PHASE {n} CLOSED' closure"
                + (f"; {scripts[0]} exists but has recorded no result" if scripts else "; no gate script exists yet"),
            )
            und.record(f"gates[phase {n}].date", f"no gate verdict heading found for phase {n}")
            rows.append(row)
            continue

        status, name, line_no, heading = hit
        row["status"] = status
        row["evidence"] = f"{name}:{line_no}: {clean_inline(heading)}"
        date = ISO_DATE.search(heading)
        if date:
            row["date"] = date.group(0)
        else:
            und.record(
                f"gates[phase {n}].date",
                f"the verdict heading '{clean_inline(heading)}' ({name}:{line_no}) carries no YYYY-MM-DD date",
            )
        rows.append(row)

    return rows


# --------------------------------------------------------------------------
# limitations
# --------------------------------------------------------------------------

LIMITATION_HEADING = re.compile(r"^(\d+)\.\s+(.*)$")


def collect_limitations(repo: Path, und: Undetermined) -> dict:
    path = repo / "LIMITATIONS.md"
    text = read_text(path)
    if text is None:
        return {
            "source_file": "LIMITATIONS.md",
            "open_count": und.record("limitations.open_count", "LIMITATIONS.md not found or unreadable"),
            "retired_count": und.record("limitations.retired_count", "LIMITATIONS.md not found or unreadable"),
            "open": [],
            "retired": [],
        }

    open_items, retired_items = [], []
    for sec in sections(text):
        m = LIMITATION_HEADING.match(sec["heading"])
        if not m:
            continue
        number = int(m.group(1))
        raw_title = m.group(2)
        title = clean_inline(raw_title)

        if "RETIRED" in raw_title.upper():
            title = clean_inline(re.sub(r"[—-]\s*RETIRED.*$", "", raw_title))
            date = ISO_DATE.search(raw_title)
            retired_items.append(
                {
                    "number": number,
                    "title": title,
                    "retired_date": date.group(0) if date else None,
                    "line": sec["line"],
                }
            )
            continue

        sub_items = [
            clean_inline(sm.group(1))
            for sm in (re.match(r"^\s*-\s+\*\*(.+?)\*\*", line) for line in sec["body"])
            if sm
        ]
        open_items.append(
            {
                "number": number,
                "title": title,
                "excerpt": excerpt(sec["body"]),
                "sub_items": sub_items[:12],
                "line": sec["line"],
            }
        )

    if not open_items and not retired_items:
        und.record(
            "limitations.open_count",
            "LIMITATIONS.md was read but contains no '## <n>. <title>' sections to parse",
        )
        return {
            "source_file": "LIMITATIONS.md",
            "open_count": None,
            "retired_count": None,
            "open": [],
            "retired": [],
        }

    return {
        "source_file": "LIMITATIONS.md",
        "open_count": len(open_items),
        "retired_count": len(retired_items),
        "open": open_items,
        "retired": retired_items,
    }


# --------------------------------------------------------------------------
# ADRs
# --------------------------------------------------------------------------

ADR_HEADING = re.compile(r"^ADR-(\d+)\s*(v\d+)?\s*[—–-]\s*(.+)$")


def collect_latest_adr(repo: Path, und: Undetermined) -> dict:
    path = repo / "DECISIONS.md"
    text = read_text(path)
    empty = {"source_file": "DECISIONS.md", "number": None, "id": None, "title": None, "date": None, "line": None}
    if text is None:
        for field in ("number", "id", "title", "date"):
            und.record(f"latest_adr.{field}", "DECISIONS.md not found or unreadable")
        return empty

    best: dict | None = None
    for line_no, heading in headings(text):
        m = ADR_HEADING.match(heading.strip())
        if not m:
            continue
        number = int(m.group(1))
        # Highest number wins; on a tie the later occurrence wins (e.g. "ADR-017 v2").
        if best is None or number >= best["number"]:
            title = m.group(3).strip()
            date = ISO_DATE.search(title)
            best = {
                "source_file": "DECISIONS.md",
                "number": number,
                "id": f"ADR-{m.group(1)}" + (f" {m.group(2)}" if m.group(2) else ""),
                "title": clean_inline(re.sub(r"\s*\(\d{4}-\d{2}-\d{2}\)\s*$", "", title)),
                "date": date.group(0) if date else None,
                "line": line_no,
            }

    if best is None:
        for field in ("number", "id", "title", "date"):
            und.record(f"latest_adr.{field}", "DECISIONS.md contains no '## ADR-<n> — <title>' headings")
        return empty

    if best["date"] is None:
        und.record(
            "latest_adr.date",
            f"the heading for {best['id']} (DECISIONS.md:{best['line']}) carries no YYYY-MM-DD date",
        )
    return best


# --------------------------------------------------------------------------
# spend (SQLite, READ-ONLY)
# --------------------------------------------------------------------------


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def collect_spend(db_path: Path, und: Undetermined) -> dict:
    out: dict = {
        "db_path": str(db_path),
        "db_present": False,
        "source_table": "ai_calls",
        "cumulative_usd": None,
        "call_count": None,
        "error_count": None,
        "pricing_versions": None,
        "first_call_utc": None,
        "last_call_utc": None,
        "last_session": None,
        "budget_events": None,
    }

    null_fields = (
        "cumulative_usd",
        "call_count",
        "error_count",
        "pricing_versions",
        "first_call_utc",
        "last_call_utc",
        "last_session",
        "budget_events",
    )

    if not db_path.is_file():
        reason = (
            f"database file not found at {db_path} — data/ is gitignored, so the DB "
            f"lives on the operator's machine (or in the backend container volume), "
            f"not in a fresh clone. Pass --db to point at it."
        )
        for f in null_fields:
            und.record(f"spend.{f}", reason)
        return out

    out["db_present"] = True
    try:
        # mode=ro: this connection physically cannot write to the platform DB.
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error as exc:
        reason = f"could not open {db_path} read-only: {exc}"
        for f in null_fields:
            und.record(f"spend.{f}", reason)
        return out

    try:
        present = _tables(conn)

        if "ai_calls" not in present:
            reason = f"table 'ai_calls' does not exist in {db_path.name}"
            for f in ("cumulative_usd", "call_count", "error_count", "pricing_versions", "first_call_utc", "last_call_utc", "last_session"):
                und.record(f"spend.{f}", reason)
        else:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(cost_usd), 0.0), "
                "COALESCE(SUM(CASE WHEN status='error' THEN 1 ELSE 0 END), 0), "
                "MIN(ts), MAX(ts) FROM ai_calls"
            ).fetchone()
            out["call_count"] = row[0]
            out["cumulative_usd"] = round(float(row[1]), 6)
            out["error_count"] = row[2]
            out["first_call_utc"] = row[3]
            out["last_call_utc"] = row[4]
            out["pricing_versions"] = [
                r[0] for r in conn.execute(
                    "SELECT DISTINCT pricing_version FROM ai_calls ORDER BY pricing_version"
                )
            ]
            if row[0] == 0:
                und.record(
                    "spend.last_session",
                    "ai_calls is empty — no session has spent anything yet",
                )
            else:
                out["last_session"] = _last_session(conn, present, und)

        if "budget_events" not in present:
            und.record("spend.budget_events", f"table 'budget_events' does not exist in {db_path.name}")
        else:
            counts = {
                r[0]: r[1]
                for r in conn.execute("SELECT event_type, COUNT(*) FROM budget_events GROUP BY event_type")
            }
            latest = conn.execute(
                "SELECT ts, event_type, session_id, detail FROM budget_events ORDER BY ts DESC, id DESC LIMIT 1"
            ).fetchone()
            latest_row = None
            if latest is not None:
                try:
                    detail = json.loads(latest[3])
                except (TypeError, ValueError):
                    detail = latest[3]
                latest_row = {
                    "ts": latest[0],
                    "event_type": latest[1],
                    "session_id": latest[2],
                    "detail": detail,
                }
            out["budget_events"] = {
                "total": sum(counts.values()),
                "by_type": counts,
                "latest": latest_row,
            }
    except sqlite3.Error as exc:
        reason = f"SQLite error while reading {db_path.name}: {exc}"
        for f in null_fields:
            if out[f] is None:
                und.record(f"spend.{f}", reason)
    finally:
        conn.close()

    return out


def _last_session(conn: sqlite3.Connection, present: set[str], und: Undetermined) -> dict | None:
    """Most recent session, costed from ai_calls (the schema's source of truth)."""
    session_id = None
    meta: dict = {}

    if "sessions" in present:
        row = conn.execute(
            "SELECT id, started_at, ended_at, status, total_cost_usd "
            "FROM sessions ORDER BY started_at DESC, id DESC LIMIT 1"
        ).fetchone()
        if row is not None:
            session_id = row[0]
            meta = {
                "session_id": row[0],
                "started_at": row[1],
                "ended_at": row[2],
                "status": row[3],
                "total_cost_usd_recorded": round(float(row[4]), 6) if row[4] is not None else None,
            }

    if session_id is None:
        # No sessions row: fall back to the most recently used session_id in ai_calls.
        row = conn.execute("SELECT session_id FROM ai_calls ORDER BY ts DESC LIMIT 1").fetchone()
        if row is None:
            return None
        session_id = row[0]
        meta = {
            "session_id": session_id,
            "started_at": None,
            "ended_at": None,
            "status": None,
            "total_cost_usd_recorded": None,
            "note": "no matching row in 'sessions'; identified from the most recent ai_calls entry",
        }
        und.record(
            "spend.last_session.started_at",
            "the most recent ai_calls session has no row in the 'sessions' table",
        )

    row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(cost_usd), 0.0), MIN(ts), MAX(ts), "
        "COALESCE(SUM(CASE WHEN status='error' THEN 1 ELSE 0 END), 0) "
        "FROM ai_calls WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    meta.update(
        {
            "call_count": row[0],
            "cost_usd": round(float(row[1]), 6),
            "first_call_utc": row[2],
            "last_call_utc": row[3],
            "error_count": row[4],
        }
    )

    by_provider = {
        r[0]: {"calls": r[1], "cost_usd": round(float(r[2]), 6)}
        for r in conn.execute(
            "SELECT provider, COUNT(*), COALESCE(SUM(cost_usd), 0.0) FROM ai_calls "
            "WHERE session_id = ? GROUP BY provider",
            (session_id,),
        )
    }
    meta["by_provider"] = by_provider
    return meta


# --------------------------------------------------------------------------
# assembly + output
# --------------------------------------------------------------------------


def build_status(repo: Path, db_path: Path) -> dict:
    und = Undetermined()

    source = collect_source(repo, und)
    phase = collect_phases(repo, und)
    gate_phases = [p["phase"] for p in phase["phases"]] or []
    gates = collect_gates(repo, gate_phases, und)
    limitations = collect_limitations(repo, und)
    latest_adr = collect_latest_adr(repo, und)
    spend = collect_spend(db_path, und)

    return {
        "schema": STATUS_SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": {
            "script": "scripts/generate_hub_status.py",
            "version": GENERATOR_VERSION,
            "direction": "repo -> hub (one way; the Hub never writes to the repo)",
            "derived": True,
            "note": "Every field is derived at run time. Nulls are never guessed or carried forward.",
        },
        "repo_path": str(repo),
        "source": source,
        "phase": phase,
        "gates": gates,
        "limitations": limitations,
        "latest_adr": latest_adr,
        "spend": spend,
        "undetermined": und.items,
    }


def summarize(status: dict) -> str:
    src = status["source"]
    ph = status["phase"]
    step = ph.get("build_step") or {}
    sp = status["spend"]
    lim = status["limitations"]
    adr = status["latest_adr"]

    def show(v, dash="null"):
        return dash if v is None else v

    lines = [
        f"source commit : {show(src['commit_sha_short'])}  {show(src['commit_subject'])}",
        f"commit date   : {show(src['commit_date_utc'])}   branch: {show(src['branch'])}",
        f"working tree  : {'clean' if src['working_tree_clean'] else 'DIRTY' if src['working_tree_clean'] is False else 'null'}",
        f"phase         : {show(ph['current_phase'])} of {show(ph['total_phases'])}  ({show(ph['current_phase_state'])})",
        f"build step    : {show(step.get('last_completed_step'))} of {show(step.get('total_steps'))} complete"
        + (f"  -> next: step {step['next_step']}" if step.get("next_step") else ""),
        f"gates         : " + ", ".join(
            f"P{g['phase']}={show(g['status'])}" + (f"@{g['date']}" if g["date"] else "") for g in status["gates"]
        ),
        f"limitations   : {show(lim['open_count'])} open, {show(lim['retired_count'])} retired",
        f"latest ADR    : {show(adr['id'])} ({show(adr['date'])}) {show(adr['title'], '')}",
        f"spend         : cumulative ${sp['cumulative_usd']:.6f}" if sp["cumulative_usd"] is not None
        else "spend         : null (see undetermined)",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve()
    default_repo = here.parent.parent

    parser = argparse.ArgumentParser(
        prog="generate_hub_status.py",
        description="Derive the LuxuryCon Hub status JSON from this repository (read-only, one-way).",
    )
    parser.add_argument("--repo", default=str(default_repo), help="repository root (default: parent of scripts/)")
    parser.add_argument("--out", default=None, help=f"output JSON path (default: <repo>/{DEFAULT_OUT_RELATIVE})")
    parser.add_argument(
        "--db",
        default=None,
        help=f"SQLite DB path (default: $LUXURYFORM_DB, else <repo>/{DEFAULT_DB_RELATIVE})",
    )
    parser.add_argument("--print-json", action="store_true", help="also print the full JSON to stdout")
    parser.add_argument("--indent", type=int, default=2, help="JSON indent (default 2)")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"FATAL: repo path is not a directory: {repo}")
        return 1

    out_path = Path(args.out).resolve() if args.out else (repo / DEFAULT_OUT_RELATIVE)
    db_path = Path(args.db) if args.db else Path(os.environ.get("LUXURYFORM_DB") or (repo / DEFAULT_DB_RELATIVE))
    db_path = db_path if db_path.is_absolute() else (repo / db_path)

    status = build_status(repo, db_path.resolve())

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp.write_text(json.dumps(status, indent=args.indent, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(out_path)
    except OSError as exc:
        print(f"FATAL: could not write {out_path}: {exc}")
        return 1

    print(f"LuxuryForm -> Hub status (generator {GENERATOR_VERSION}, schema {STATUS_SCHEMA})")
    print(f"wrote: {out_path}")
    print("")
    print(summarize(status))

    undetermined = status["undetermined"]
    if undetermined:
        print("")
        print(f"undetermined ({len(undetermined)}) — written as null, never guessed:")
        for item in undetermined:
            print(f"  - {item['field']}: {item['reason']}")

    if args.print_json:
        print("")
        print(json.dumps(status, indent=args.indent, ensure_ascii=False))

    if undetermined:
        print("")
        print("exit 2: status file written and valid; some fields are null (listed above)")
        return 2
    print("")
    print("exit 0: status file written; every field determined")
    return 0


if __name__ == "__main__":
    sys.exit(main())
