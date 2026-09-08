"""PR-2.5 discovery auto gate — $0, offline, non-interactive (ADR-064).

Split into three section groups so the permanent roster stays truthful on
ANY checkout (owner amendments 1/5/7):

  REPO sections    always run; need only committed files.
  ARTIFACT/LOCAL   run when the discovery artifacts / the operator-local
                   reference images exist; otherwise print a loud SKIPPED
                   line and do NOT fail — regenerate artifacts with
                   `python scripts\\run_pr25_discovery.py`.
  HOST section     `--host-drift` only, on the operator's machine: git
                   metadata is NOT assumed to exist inside the image.

The gate never executes probe code and never constructs geometry: it
reads files, re-hashes bytes and re-parses JSON (ADR-005 kept).
Exit 0 = every section that ran passed. Exit 1 = any check failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

CHECKS = []
SECTIONS_RUN = []
SECTIONS_SKIPPED = []


def ok(section, label, passed, detail=""):
    CHECKS.append(passed)
    print("  %-4s %s%s" % ("ok" if passed else "FAIL", label,
                           (" -- " + detail) if detail else ""))
    return passed


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_dir(*candidates) -> Path | None:
    for c in candidates:
        if c is not None and c.exists():
            return c
    return None


def section(title):
    print("\n[%s]" % title)
    SECTIONS_RUN.append(title)


def skipped(title, why):
    print("\n[%s] SKIPPED -- %s" % (title, why))
    SECTIONS_SKIPPED.append(title)


# --------------------------------------------------------------------------
# REPO sections
# --------------------------------------------------------------------------

def repo_manifest():
    section("1 reference manifest (repo)")
    path = REPO / "briefs" / "freeform_references" / "reference_manifest.json"
    if not ok("1", "reference_manifest.json exists", path.exists(), str(path)):
        return None
    man = json.loads(path.read_text(encoding="utf-8-sig"))
    images = man.get("images", [])
    # D-10-frozen: the B-11 reference manifest is the owner's fixed record of
    # the 16 references delivered 2026-09-02 and the roles assigned to them
    # in the PR-2.5 discovery (ADR-064) — historical evidence, not a growing
    # set. B-11b (mesh/lattice) is a NEW reference class that must arrive as
    # its own manifest entry with its own ruling, and this gate failing on
    # that day is the intended signal.
    ok("1", "16 entries", len(images) == 16, "found %d" % len(images))
    roles = {}
    for e in images:
        roles.setdefault(e.get("role"), set()).add(e.get("file", "??")[:2])
        ok("1", "%s sha256 well-formed" % e.get("file"),
           bool(re.fullmatch(r"[0-9a-f]{64}", e.get("sha256", ""))))
    # D-10-frozen: same fixed B-11 record as above — the primary/secondary/
    # engineering-context role assignment is the discovery's recorded ruling.
    ok("1", "primary role covers exactly 08/11/13/14/16",
       roles.get("primary") == {"08", "11", "13", "14", "16"},
       str(sorted(roles.get("primary") or [])))
    # D-10-frozen: same fixed B-11 record — see the marker on "16 entries".
    ok("1", "roles cover engineering-context 01-07 and secondary 09/10/12/15",
       roles.get("engineering-context") == {"01", "02", "03", "04", "05",
                                            "06", "07"}
       and roles.get("secondary") == {"09", "10", "12", "15"})
    ok("1", "mesh/lattice gap recorded (B-11b)",
       "B-11b" in man.get("mesh_lattice_note", ""))
    return man


def repo_report():
    section("2 discovery report (repo)")
    path = REPO / "PR2_5_FREEFORM_DISCOVERY.md"
    if not ok("2", "PR2_5_FREEFORM_DISCOVERY.md exists", path.exists()):
        return None
    text = path.read_text(encoding="utf-8-sig")
    # Markdown wraps sentences across lines; every phrase check runs
    # against whitespace-normalized text so a line break never hides a
    # required sentence (or a banned one).
    flat = " ".join(text.split())
    for heading in ("## Owner rulings", "## Method", "## Capability matrix",
                    "## Approach comparison", "## Parameter frames",
                    "## Acceptance gate design", "## Open items"):
        ok("2", "section %r present" % heading, heading in text)
    ok("2", "STEP-canonicality ruling sentence present",
       "any change to STEP as the canonical artifact requires an explicit "
       "architectural ruling" in flat)
    ok("2", "B-11b open and release-blocking",
       "B-11b" in flat and "release-blocking" in flat)
    for banned in ("1900–2100", "1900-2100", "15–25 mm", "15-25 mm",
                   "crane-trivial", "560 kg", "+30%", "+30 %"):
        ok("2", "banned invented value %r absent" % banned,
           banned not in flat)
    for tag in ("owner-ruling", "measured-from-dimensioned-reference",
                "image-derived-estimate", "materials.yaml",
                "probe-only-judgement", "FABRICATOR-INPUT-REQUIRED"):
        ok("2", "provenance tag %r used" % tag, tag in flat)
    ok("2", "skin mass labeled non-engineering discovery estimate",
       "non-engineering discovery estimate" in flat)
    ok("2", "armature honesty sentence present",
       "not computable until the armature is designed" in flat)
    m = re.search(r"```json capability-matrix\n(.*?)```", text, re.DOTALL)
    if not ok("2", "fenced capability-matrix JSON present", bool(m)):
        return None
    rows = json.loads(m.group(1))
    ok("2", "matrix has >= 12 rows", len(rows) >= 12, "%d rows" % len(rows))
    limitations = (REPO / "LIMITATIONS.md").read_text(encoding="utf-8-sig")
    ok("2", "LIMITATIONS carries 'kernel feasibility probed; no user-facing "
            "free-form capability implemented'",
       "kernel feasibility probed; no user-facing free-form capability "
       "implemented" in limitations)
    audit = (REPO / "DEVELOPMENT_AUDIT.md").read_text(encoding="utf-8-sig")
    ok("2", "audit score untouched (31.6 still recorded)", "31.6" in audit)
    return rows


def repo_static_scan():
    section("3 static $0 scan (repo)")
    files = sorted((HERE / "probes").glob("*.py"))
    files += [HERE / "run_pr25_discovery.py", Path(__file__).resolve()]
    # Tokens are assembled at runtime so this gate's own source (which it
    # also scans) never contains the forbidden literals.
    forbidden = tuple("import " + m for m in
                      ("requests", "httpx", "urllib", "socket")) + \
        tuple(p + " " + m for p in ("from", "import")
              for m in ("anthropic", "openai")) + \
        tuple(s + "://" for s in ("http", "https"))
    ok("3", ">= 8 discovery sources found", len(files) >= 8,
       "%d files" % len(files))
    for path in files:
        code = "\n".join(ln for ln in
                         path.read_text(encoding="utf-8").splitlines()
                         if not ln.lstrip().startswith("#"))
        bad = [t for t in forbidden if t in code]
        ok("3", "%s network/provider-free" % path.name, not bad, ", ".join(bad))


# --------------------------------------------------------------------------
# ARTIFACT sections
# --------------------------------------------------------------------------

def artifact_sections(matrix_rows):
    disc = find_dir(Path("/scratch/pr25_discovery"),
                    REPO / "data" / "geo_scratch" / "pr25_discovery")
    if disc is None or not (disc / "summary.json").exists():
        skipped("4-8 discovery artifacts",
                "no summary.json (run: python scripts\\run_pr25_discovery.py)")
        return
    summary = json.loads((disc / "summary.json").read_text(encoding="utf-8"))

    section("4 report matrix == orchestrator summary")
    entries = summary["entries_passA"]
    key = lambda r: (r["fixture"], r["approach"])  # noqa: E731
    summary_map = {key(e): e["status"] for e in entries}
    if matrix_rows is None:
        ok("4", "report matrix available", False, "report failed to parse")
    else:
        report_map = {key(r): r["status"] for r in matrix_rows}
        ok("4", "same fixture set", set(report_map) == set(summary_map),
           "report-only: %s | summary-only: %s"
           % (sorted(set(report_map) - set(summary_map)),
              sorted(set(summary_map) - set(report_map))))
        for k in sorted(set(report_map) & set(summary_map)):
            ok("4", "%s/%s status matches" % k, report_map[k] == summary_map[k],
               "report=%s summary=%s" % (report_map[k], summary_map[k]))

    section("5 artifact bytes re-hash to recorded sha256")
    pass_a = disc / "passA"
    for e in entries:
        if e["status"] != "constructed":
            continue
        for kind, art in sorted(e["artifacts"].items()):
            f = pass_a / art["file"]
            if not f.exists():
                ok("5", "%s %s exists" % (e["fixture"], kind), False, str(f))
                continue
            ok("5", "%s %s hash" % (e["fixture"], kind),
               sha256_file(f) == art["sha256"])

    section("6 cross-process determinism (contractual bytes)")
    rows = summary["determinism"]
    ok("6", "determinism rows exist", len(rows) > 0, "%d rows" % len(rows))
    for row in rows:
        ok("6", "%s identical across two sandbox processes" % row["file"],
           row["identical"] is True,
           "A=%s B=%s" % (row["passA_sha256"][:12],
                          str(row["passB_sha256"])[:12]))

    section("7 deliberate-bad fixtures refused")
    bads = [e for e in entries if e.get("expected_invalid")]
    ok("7", "expected-invalid fixtures present (self-crossing sweep + "
            "silent tangent-overlap fuse)",
       {e["fixture"] for e in bads} >= {"bad_self_crossing",
                                        "bad_tangent_overlap_fuse"},
       str(sorted(e["fixture"] for e in bads)))
    for bad in bads:
        if bad["status"] == "failed":
            ok("7", "%s refused at construction/guard" % bad["fixture"],
               True, bad["detail"].splitlines()[-1][:120])
        else:
            val = [v for v in summary["validation_passA"]
                   if v["fixture"] == bad["fixture"]]
            ok("7", "%s flagged by independent validation" % bad["fixture"],
               bool(val) and val[0]["flagged_invalid"] is True,
               "; ".join(val[0]["reasons"])[:200] if val
               else "no validation row")

    section("8 validation coverage and pass-agreement")
    val_a = {(v["fixture"], v["approach"]): v["flagged_invalid"]
             for v in summary["validation_passA"]}
    val_b = {(v["fixture"], v["approach"]): v["flagged_invalid"]
             for v in summary["validation_passB"]}
    for e in entries:
        if e["status"] != "constructed":
            continue
        k = key(e)
        ok("8", "%s/%s validated in both passes" % k,
           k in val_a and k in val_b)
        if k in val_a and k in val_b:
            ok("8", "%s/%s verdict agrees across passes" % k,
               val_a[k] == val_b[k], "A=%s B=%s" % (val_a[k], val_b[k]))

    render_root = find_dir(Path("/render_scratch"),
                           REPO / "data" / "render_scratch")
    renders = summary.get("renders", [])
    if not renders or render_root is None:
        skipped("9 render evidence", "no render rows in summary "
                "(worker down or --skip-render)")
    else:
        section("9 render evidence (annotated PNGs)")
        for r in renders:
            if not ok("9", "%s rendered ok" % r["job"], r["ok"],
                      str(r.get("error"))[:160]):
                continue
            for view in ("ortho_front", "ortho_side", "perspective_3q"):
                png = render_root / r["job"] / ("%s.annotated.png" % view)
                good = png.exists() and png.stat().st_size > 0 and \
                    png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
                ok("9", "%s/%s.annotated.png is a real PNG"
                   % (r["job"], view), good)


# --------------------------------------------------------------------------
# OPERATOR-LOCAL section
# --------------------------------------------------------------------------

def local_reference_images(man):
    refs = REPO / "briefs" / "freeform_references"
    jpgs = sorted(refs.glob("*.jpg"))
    if not jpgs:
        skipped("10 operator-local reference images",
                "no JPGs on this checkout (they are private and uncommitted; "
                "the visual gate requires them)")
        return
    section("10 operator-local reference images vs manifest")
    if man is None:
        ok("10", "manifest available", False)
        return
    by_name = {e["file"]: e["sha256"] for e in man["images"]}
    # D-10-frozen: the same fixed B-11 record as section 1 — the operator's
    # 16 local reference JPGs are the delivered set of 2026-09-02 (ADR-064),
    # matched by sha256 to the committed manifest; a 17th file is a new
    # reference class (B-11b) that arrives with its own manifest ruling.
    ok("10", "16 local images", len(jpgs) == 16, "found %d" % len(jpgs))
    for jpg in jpgs:
        expected = by_name.get(jpg.name)
        actual = sha256_file(jpg)
        ok("10", "%s hash matches manifest" % jpg.name, expected == actual,
           "" if expected == actual else "manifest=%s actual=%s"
           % (str(expected)[:12], actual[:12]))


# --------------------------------------------------------------------------
# Hermeticity + host drift
# --------------------------------------------------------------------------

def hermeticity(before):
    section("11 hermeticity -- this gate touched no production data")
    after = _data_fingerprint()
    ok("11", "real DB byte-identical", before[0] == after[0],
       "sha %s" % str(after[0])[:12])
    ok("11", "data/exports tree unchanged", before[1] == after[1],
       "%d files" % len(after[1]))


def _data_fingerprint():
    db = find_dir(Path("/app/data/luxuryform.db"),
                  REPO / "data" / "luxuryform.db")
    db_sha = sha256_file(db) if db else None
    exports = find_dir(Path("/app/data/exports"), REPO / "data" / "exports")
    listing = tuple(sorted((p.name, p.stat().st_size)
                           for p in exports.rglob("*") if p.is_file())) \
        if exports else ()
    return db_sha, listing


#: The PR-2.5 discovery close commit, pinned by FULL hash (operator
#: ruling 2026-09-04, the fifth D-10-class correction): the original
#: section 12 asserted "no production drift" against the LIVE working
#: tree vs HEAD — a slice-scoped promise in a permanent gate, which
#: correctly failed the moment FF-A1 carried legitimate uncommitted
#: backend work. The permanent truth this section records is HISTORICAL:
#: the discovery commit itself changed nothing under backend/app,
#: config or schemas.
DISCOVERY_CLOSE_COMMIT = "5cb0af3e2445c09b7426037fb8d02104be1ffeae"


def host_drift():
    section("12 host drift check (--host-drift)")
    try:
        resolved = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet",
             DISCOVERY_CLOSE_COMMIT + "^{commit}"],
            capture_output=True, text=True, cwd=str(REPO), timeout=60)
        if not ok("12", "discovery close commit %s resolves"
                  % DISCOVERY_CLOSE_COMMIT[:12],
                  resolved.returncode == 0
                  and resolved.stdout.strip() == DISCOVERY_CLOSE_COMMIT,
                  resolved.stdout.strip() or resolved.stderr.strip()):
            return
        diff = subprocess.run(
            ["git", "diff", "--name-only",
             DISCOVERY_CLOSE_COMMIT + "~1", DISCOVERY_CLOSE_COMMIT, "--",
             "backend/app", "config", "schemas"],
            capture_output=True, text=True, cwd=str(REPO), timeout=60)
        touched = [ln for ln in diff.stdout.splitlines() if ln.strip()]
        ok("12", "the discovery commit changed no backend/app, config or "
                 "schemas paths (historical, permanent)",
           diff.returncode == 0 and not touched, ", ".join(touched))
        tracked = subprocess.run(
            ["git", "ls-files", "briefs/freeform_references"],
            capture_output=True, text=True, cwd=str(REPO), timeout=60)
        jpgs = [ln for ln in tracked.stdout.splitlines()
                if ln.endswith(".jpg")]
        ok("12", "no reference JPG tracked by git", not jpgs, ", ".join(jpgs))
    except FileNotFoundError:
        ok("12", "git available on host", False,
           "run this section on the operator's machine, not in the image")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host-drift", action="store_true",
                    help="also run the host-side git drift section "
                         "(needs git; never available inside the image)")
    args = ap.parse_args()

    print("=" * 72)
    print("PR-2.5 DISCOVERY AUTO GATE -- $0, offline, split-mode (ADR-064)")
    print("repo root: %s" % REPO)
    print("=" * 72)

    before = _data_fingerprint()
    man = repo_manifest()
    rows = repo_report()
    repo_static_scan()
    artifact_sections(rows)
    local_reference_images(man)
    if args.host_drift:
        host_drift()
    hermeticity(before)

    print("\n" + "=" * 72)
    print("sections run:     %s" % "; ".join(SECTIONS_RUN))
    print("sections skipped: %s" % ("; ".join(SECTIONS_SKIPPED) or "none"))
    passed = sum(1 for c in CHECKS if c)
    failed = len(CHECKS) - passed
    if failed:
        print("FAIL -- %d of %d checks failed. Discovery evidence is NOT "
              "gate-clean." % (failed, len(CHECKS)))
        print("=" * 72)
        return 1
    print("PASS -- all %d checks in every section that ran passed at $0, "
          "offline, with no probe code executed by this gate." % passed)
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
