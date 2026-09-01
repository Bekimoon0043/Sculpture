"""gate_scope_audit_auto.py — the Master Scope Development Audit auto gate.

$0, offline, non-interactive, stdlib only. Runs on the host or in the
backend container, from the repo root or scripts/. It verifies that the
scope and audit documents are internally consistent and that the audit's
evidence anchors exist in the working tree — by stable symbols and quoted
substrings, never by line numbers.

Exit 0 = PASS, exit 1 = FAIL. Every check prints its real numbers.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = "bfa5a77"
EXPECTED_WEIGHT_TOTAL = 112
EXPECTED_SYSTEMS = 30

FAILURES: list[str] = []


def check(section: str, ok: bool, detail: str) -> None:
    tag = "ok  " if ok else "FAIL"
    print(f"  {tag} {detail}")
    if not ok:
        FAILURES.append(f"[{section}] {detail}")


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def extract_json_block(text: str, marker: str) -> dict:
    m = re.search(rf"<!--\s*{marker}\s*(\{{.*?\}})\s*-->", text, re.DOTALL)
    if m is None:
        raise ValueError(f"marker {marker} not found")
    return json.loads(m.group(1))


def main() -> int:
    print("=" * 72)
    print("SCOPE AUDIT AUTO GATE — documents, arithmetic, evidence anchors")
    print(f"repo root: {ROOT}")
    print("=" * 72)

    # ---------------------------------------------------------------
    print("\n[1] SCOPE.md — present, authoritative wording, weights sum 112")
    scope_path = ROOT / "SCOPE.md"
    check("1", scope_path.is_file(), f"SCOPE.md exists: {scope_path.is_file()}")
    if not scope_path.is_file():
        return finish()
    scope = read("SCOPE.md")
    for phrase, why in [
        ("recovered", "provenance: recovered from the owner's transcript"),
        ("112", "the 112-point weight total is stated"),
        ("countersign", "authority requires the owner's countersignature"),
        ("owner ruling", "future changes require an explicit owner ruling"),
        ("Free-form Sculpture Demonstrator", "Milestone A name"),
        ("Internal Fabrication-Geometry Beta", "Milestone B name"),
        ("Production v1", "Milestone C name"),
        ("80%", "Milestone C threshold stated"),
    ]:
        check("1", phrase in scope, f"SCOPE.md carries: {why}")

    weight_lines = re.findall(
        r"^\d{1,2} [A-Za-z/][^\n]*?\s[—-]\s*(\d+)%\s*$", scope, re.MULTILINE
    )
    weights = [int(w) for w in weight_lines]
    check("1", len(weights) == EXPECTED_SYSTEMS,
          f"weight lines parsed: {len(weights)} (expected {EXPECTED_SYSTEMS})")
    check("1", sum(weights) == EXPECTED_WEIGHT_TOTAL,
          f"weights sum to {sum(weights)} (expected {EXPECTED_WEIGHT_TOTAL})")

    # ---------------------------------------------------------------
    print("\n[2] DEVELOPMENT_AUDIT.md — baseline, score table arithmetic")
    audit_path = ROOT / "DEVELOPMENT_AUDIT.md"
    check("2", audit_path.is_file(), f"DEVELOPMENT_AUDIT.md exists: {audit_path.is_file()}")
    if not audit_path.is_file():
        return finish()
    audit = read("DEVELOPMENT_AUDIT.md")
    check("2", BASELINE in audit, f"audit records baseline commit {BASELINE}")

    try:
        table = extract_json_block(audit, "SCORE-TABLE")
    except ValueError as exc:
        check("2", False, f"SCORE-TABLE block: {exc}")
        return finish()

    rows = table.get("scores", [])
    check("2", len(rows) == EXPECTED_SYSTEMS,
          f"SCORE-TABLE rows: {len(rows)} (expected {EXPECTED_SYSTEMS})")
    ids = [r[0] for r in rows]
    check("2", ids == list(range(1, EXPECTED_SYSTEMS + 1)),
          "SCORE-TABLE ids are exactly 1..30 in order")
    tbl_weights = [r[1] for r in rows]
    check("2", tbl_weights == weights,
          "SCORE-TABLE weights match SCOPE.md weights, in order")
    bad_scores = [r for r in rows if not (0 <= r[2] <= 5)]
    check("2", not bad_scores, f"all scores within 0..5 (violations: {bad_scores})")

    raw = sum(w * s / 5.0 for _, w, s in rows)
    stated_raw = float(table.get("raw_total", -1))
    check("2", abs(raw - stated_raw) < 0.005,
          f"recomputed raw total {raw:.2f} == stated {stated_raw:.2f}")
    normalized = raw / EXPECTED_WEIGHT_TOTAL * 100.0
    stated_norm = float(table.get("normalized", -1))
    check("2", abs(normalized - stated_norm) < 0.05,
          f"recomputed normalized {normalized:.2f} == stated {stated_norm:.2f}")
    check("2", table.get("baseline") == BASELINE,
          f"SCORE-TABLE baseline '{table.get('baseline')}' == {BASELINE}")

    # the human-readable table must carry the same scores, row for row
    md_rows = re.findall(
        r"^\|\s*(\d{1,2})\s*\|[^|]+\|\s*(\d+)\s*\|\s*(\d)\s*\|", audit, re.MULTILINE
    )
    md_map = {int(n): (int(w), int(s)) for n, w, s in md_rows}
    mismatches = [
        (r[0], md_map.get(r[0]), (r[1], r[2]))
        for r in rows
        if md_map.get(r[0]) != (r[1], r[2])
    ]
    check("2", len(md_map) >= EXPECTED_SYSTEMS,
          f"markdown scorecard rows found: {len(md_map)} (expected >= {EXPECTED_SYSTEMS})")
    check("2", not mismatches,
          f"markdown table matches SCORE-TABLE (mismatches: {mismatches[:3]})")

    # ---------------------------------------------------------------
    print("\n[3] Evidence anchors — files exist, quoted symbols present")
    try:
        anchors = extract_json_block(audit, "EVIDENCE-ANCHORS")["anchors"]
    except (ValueError, KeyError) as exc:
        check("3", False, f"EVIDENCE-ANCHORS block: {exc}")
        return finish()
    for a in anchors:
        rel, needle = a["file"], a.get("must_contain", "")
        p = ROOT / rel
        if not p.is_file():
            check("3", False, f"{rel}: MISSING")
            continue
        if needle:
            found = needle in read(rel)
            check("3", found, f"{rel}: contains {needle!r}" if found
                  else f"{rel}: does NOT contain {needle!r}")
        else:
            check("3", True, f"{rel}: exists")

    # ---------------------------------------------------------------
    print("\n[4] Score reconciliation — all four figures recorded")
    for figure in ("27.68", "34.6", "33.9", "31.6"):
        check("4", figure in audit, f"reconciliation carries {figure}%")
    check("4", "one-third" in audit,
          "executive summary uses the 'one-third' phrasing, not false precision")
    check("4", "unrunnable" in audit.lower(),
          "the owner's original 6m->8m test is preserved as unrunnable")

    # ---------------------------------------------------------------
    print("\n[5] Milestones and queue order")
    for name in ("Free-form Sculpture Demonstrator",
                 "Internal Fabrication-Geometry Beta"):
        check("5", name in audit, f"audit uses milestone name: {name}")
    next_md = read("NEXT.md")
    for name in ("Free-form Sculpture Demonstrator",
                 "Internal Fabrication-Geometry Beta", "LF-103A"):
        check("5", name in next_md, f"NEXT.md carries: {name}")
    i_103a, i_25 = next_md.find("LF-103A"), next_md.find("PR-2.5")
    check("5", 0 <= i_103a < i_25 if i_25 >= 0 else False,
          f"NEXT.md orders LF-103A (at {i_103a}) before PR-2.5 (at {i_25})")
    check("5", "not Production v1" in next_md or "NOT Production v1" in next_md,
          "NEXT.md states PR-0..PR-9 delivers Milestone B, not Production v1")

    # ---------------------------------------------------------------
    print("\n[6] Cross-references")
    lim = read("LIMITATIONS.md")
    check("6", "## 21" in lim,
          "LIMITATIONS.md has section 21 (advisory export boundary)")
    claude_md = read("CLAUDE.md")
    check("6", "does not exist" not in claude_md.split("SCOPE.md")[-1][:200]
          if "SCOPE.md" in claude_md else False,
          "CLAUDE.md no longer claims SCOPE.md does not exist")
    check("6", "ADR-062" in read("DECISIONS.md"), "DECISIONS.md carries ADR-062")
    check("6", (ROOT / "gate_scope_audit_visual.md").is_file(),
          "gate_scope_audit_visual.md exists")

    return finish()


def finish() -> int:
    print("\n" + "=" * 72)
    if FAILURES:
        print(f"FAIL — {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        print("=" * 72)
        return 1
    print("PASS — scope audit documents consistent; all evidence anchors "
          "verified at $0, offline, no line numbers relied on.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
