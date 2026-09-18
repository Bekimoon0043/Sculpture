#!/usr/bin/env python3
"""PR-5 AUTO GATE — AI contract and document repair (ADR-068). $0 forever.

Run inside Docker:
    docker compose exec backend python scripts/gate_pr5_auto.py

Non-interactive, offline, no AI call, no provider, no database opened for
writing. Every manifest below is TEMPORARY in-memory gate data; the only
production data touched is a read-only fingerprint of the real DB, taken
AFTER the backend reports healthy and the DB/WAL fingerprint has settled
(D-26: never seconds after a rebuild, never behind an arbitrary sleep).

What it proves, with real strings and numbers on both sides:

  1. THE AI CONTRACT — the GEOMETRIST surface says the crane picks the
     heaviest MODULE after segmentation and max_module_m binds per axis;
     the retired wording is absent (tokens assembled at runtime so this
     file never carries them); the PRIMITIVE INDEX is registry-driven —
     every registered primitive is offered, count printed, none asserted.
  2. THE GATE BASES — on a temporary segmented manifest with limits absent,
     both needs_input rows speak module and axis, never per-element; with
     limits present the lift row names "heaviest of 9 modules".
  3. THE SCORER — five scorings printed with their basis: measured
     heaviest module; single complete element; multi-element unsegmented
     (unavailable, None); no lift limit (unavailable, None, nothing
     defaulted); incomplete mass (unavailable, None, armature named);
     score_delta never compares None.
  4. THE DOCUMENTS — every dated correction present, every original
     sentence PRESERVED verbatim beneath/above it; LIMITATIONS §11/§12
     struck through, not deleted.
  5. THE D-10 SWEEP — every equality in every roster gate against a
     growth collection (registry, legacy mass set, declared inputs, import
     whitelist, rate-card entries, reference manifest) must carry a
     `D-10-frozen:` marker stating a real reason (>= 8 words, naming an
     ADR/record, not merely "intentional"); the three converted checks are
     verified in their new form; structural equalities are listed as
     reviewed, not hidden.
  6. HERMETICITY — backend healthy, DB/WAL fingerprint stable BEFORE and
     identical AFTER, no network, $0.
"""

from __future__ import annotations

import ast
import hashlib
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

TOTAL = 6

#: assembled at runtime so THIS FILE never carries the retired wording
RETIRED = ("checked per" + " element", "bind per" + " element",
           "per-" + "element mass vs", "per-" + "element bounding box")

#: growth collections: literals about these expire as the platform grows.
#: MS-A1 (2026-09-16, ADR-071): the roster census literal renamed
#: expected_eleven -> expected_twelve in gate_ffa2_auto; SC-A1 (ADR-072)
#: renamed it expected_twelve -> expected_thirteen. The sweep token
#: follows the literal so the census pin is caught by name in any form.
GROWTH_TOKENS = ("PRIMITIVES", "LEGACY_COMPLETE_MASS_PRIMITIVES",
                 "INCOMPLETE_MASS_INPUTS", "ALLOWED_IMPORT_ROOTS",
                 "missing_entries", "images", "jpgs", "roles",
                 "expected_thirteen", "EXPECTED_TOPOLOGY")
MARKER = "D-10-frozen:"
MIN_REASON_WORDS = 8
GENERIC_REASONS = ("intentional", "on purpose", "by design", "ok", "fine")


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/{TOTAL}] {title}")
    _hline()


def _check(failures: list[str], label: str, ok: bool,
           detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}"
          + (f" -- {detail}" if detail else ""))
    if not ok:
        failures.append(f"{label} -- {detail}")


# ---------------------------------------------------------------------------
# temporary gate data — never persisted
# ---------------------------------------------------------------------------

def _element(eid: str, mass: float, primitive: str = "basin_round") -> dict:
    return {"element_id": eid, "primitive": primitive,
            "material_id": "basalt_slab", "mass_kg": mass,
            "bbox_mm": [2000.0, 2000.0, 800.0],
            "parameters": {"wall_mm": 80.0}}


def _segmented(total: float = 11346.137) -> dict:
    return {
        "schema": "assembly_manifest_v1",
        "elements": [_element("b1", total)],
        "total_mass_kg": total,
        "fabrication_limits": {"max_lift_kg": 2000.0,
                               "max_module_m": {"x": 2.4, "y": 2.4, "z": 2.2}},
        "segmentation": {
            "schema": "assembly_segmentation_v1",
            "module_count": 9, "heaviest_module_kg": 1472.31,
            "not_segmentable": [],
            "elements": {"b1": {"module_count": 9, "modules": [
                {"index": i, "mass_kg": 1472.31 if i == 0 else 1234.23,
                 "bbox_mm": [1700.0, 1700.0, 800.0]} for i in range(9)]}},
            "seams": {"split": {"count": 12, "length_mm": 50112.0,
                                "area_mm2": 3531278.0},
                      "joint": {"count": 0, "length_mm": 0.0,
                                "area_mm2": 0.0, "joints": []},
                      "total_length_mm": 50112.0},
        },
    }


# ---------------------------------------------------------------------------
# hermeticity (D-26-safe)
# ---------------------------------------------------------------------------

def _db_paths() -> tuple[Path | None, Path | None]:
    for candidate in (Path("/app/data/luxuryform.db"),
                      REPO_ROOT / "data" / "luxuryform.db"):
        if candidate.exists():
            wal = candidate.with_name(candidate.name + "-wal")
            return candidate, (wal if wal.exists() else None)
    return None, None


def _fingerprint() -> tuple[str | None, str | None]:
    db, wal = _db_paths()
    if db is None:
        return None, None
    return (hashlib.sha256(db.read_bytes()).hexdigest()[:12],
            hashlib.sha256(wal.read_bytes()).hexdigest()[:12] if wal else "no-wal")


def _backend_healthy() -> tuple[bool, str]:
    """True when the live backend answers /api/health ok. Loopback only —
    no network beyond this machine. Absent server (host run) is reported
    honestly, not faked."""
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:8000/api/health", timeout=5.0)
        body = r.json()
        ok = r.status_code == 200 and body.get("status") == "ok" \
            and bool((body.get("db") or {}).get("ok"))
        return ok, f"HTTP {r.status_code} status={body.get('status')!r}"
    except Exception as exc:  # noqa: BLE001 - reported, never hidden
        return False, f"{type(exc).__name__}: {exc}"


def _settled_fingerprint(failures: list[str]) -> tuple[str | None, str | None]:
    """Wait for the backend to be healthy AND for two consecutive identical
    DB+WAL fingerprints — a condition, not a duration. Bounded: FAILS loudly
    if the backend never answers or the DB never quiesces."""
    deadline = time.monotonic() + 60.0
    attempts = 0
    healthy, why = _backend_healthy()
    while not healthy and time.monotonic() < deadline:
        attempts += 1
        time.sleep(0.25)
        healthy, why = _backend_healthy()
    _check(failures, "backend healthy before any production fingerprint",
           healthy, f"{why} after {attempts} poll(s)")
    prev = _fingerprint()
    stable_polls = 0
    while time.monotonic() < deadline:
        time.sleep(0.25)
        cur = _fingerprint()
        stable_polls += 1
        if cur == prev:
            _check(failures, "DB/WAL fingerprint settled (two identical reads)",
                   True, f"db={cur[0]} wal={cur[1]} after {stable_polls} poll(s)")
            return cur
        prev = cur
    _check(failures, "DB/WAL fingerprint settled (two identical reads)",
           False, "never quiesced within 60 s — refusing to measure")
    return prev


# ---------------------------------------------------------------------------
# the D-10 sweep
# ---------------------------------------------------------------------------

def _marker_reason(lines: list[str], lineno: int) -> str | None:
    """The D-10-frozen reason in the 8 lines above a hit, joined."""
    window = lines[max(0, lineno - 9):lineno - 1]
    for i, ln in enumerate(window):
        if MARKER in ln:
            text = ln.split(MARKER, 1)[1]
            for cont in window[i + 1:]:
                s = cont.strip()
                if s.startswith("#"):
                    text += " " + s.lstrip("# ")
                else:
                    break
            return text.strip()
    return None


def _sweep(failures: list[str]) -> None:
    growth_hits: list[tuple[str, int, str]] = []
    structural: list[tuple[str, int, str]] = []
    for path in sorted((REPO_ROOT / "scripts").glob("gate_*_auto.py")):
        src = path.read_text(encoding="utf-8")
        lines = src.splitlines()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            if not any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
                continue
            sides = [node.left] + list(node.comparators)
            # a FROZEN literal: a set/frozenset literal, or len(...) against
            # an int constant. len(a) == len(b) compares two live values and
            # freezes nothing, so it is not a hit.
            has_set = any(isinstance(s, ast.Set) or (
                isinstance(s, ast.Call) and getattr(s.func, "id", "")
                in ("frozenset", "set") and s.args
                and isinstance(s.args[0], (ast.Set, ast.List, ast.Tuple)))
                for s in sides)
            has_len = any(isinstance(s, ast.Call)
                          and getattr(s.func, "id", "") == "len" for s in sides)
            has_int = any(isinstance(s, ast.Constant) and isinstance(s.value, int)
                          and not isinstance(s.value, bool) for s in sides)
            if not (has_set or (has_len and has_int)):
                continue
            seg = ast.get_source_segment(src, node) or ""
            row = (path.name, node.lineno, " ".join(seg.split())[:80])
            if any(tok in seg for tok in GROWTH_TOKENS):
                growth_hits.append(row)
            else:
                structural.append(row)
    print(f"  growth-collection equalities: {len(growth_hits)}; "
          f"structural equalities reviewed (listed, not exempt): "
          f"{len(structural)}")
    for name, lineno, seg in growth_hits:
        lines = (REPO_ROOT / "scripts" / name).read_text(
            encoding="utf-8").splitlines()
        reason = _marker_reason(lines, lineno)
        words = len((reason or "").split())
        generic = (reason or "").strip().lower().rstrip(".") in GENERIC_REASONS
        cites = bool(re.search(r"ADR-\d+|B-\d+|record|ruling|seam|policy|"
                               r"contract", reason or ""))
        ok = reason is not None and words >= MIN_REASON_WORDS \
            and not generic and cites
        print(f"    {name}:{lineno}  {seg}")
        print(f"      reason: {reason if reason else '<NONE>'}")
        _check(failures, f"{name}:{lineno} carries a real D-10-frozen reason",
               ok, f"{words} words, cites={cites}, generic={generic}")
    for name, lineno, seg in structural:
        print(f"    reviewed {name}:{lineno}  {seg}")


# ---------------------------------------------------------------------------

def main() -> int:
    from app.core.config import DEFAULT_GATE_PROFILE_ID, load_config_bundle
    from app.council.critique import (
        MASS_BASIS_MEASURED,
        MASS_BASIS_SINGLE,
        MASS_BASIS_UNAVAILABLE,
        facts_from_manifest,
        objective_score_detail,
        score_delta,
    )
    from app.council.prompts import registry_surface
    from app.geometry.gates import validate_fabrication_gate
    from app.geometry.mass_model import MassTruth
    from app.geometry.primitives import PRIMITIVES

    failures: list[str] = []
    print("PR-5 AUTO GATE — AI contract and document repair (ADR-068)")

    # ------------------------------------------------------------------
    _section(6, "HERMETICITY (before) — health + settled fingerprint")
    before = _settled_fingerprint(failures)

    # ------------------------------------------------------------------
    _section(1, "THE AI CONTRACT — what the GEOMETRIST is told")
    surface = registry_surface()
    for ln in surface.splitlines():
        if "max_lift_kg" in ln or "MODULE" in ln or "per axis" in ln:
            print(f"  | {ln}")
    _check(failures, "contract: lift binds on the heaviest MODULE after segmentation",
           "heaviest MODULE after" in surface)
    _check(failures, "contract: max_module_m binds per axis",
           "binds per axis" in surface)
    for token in RETIRED:
        _check(failures, f"retired wording {token!r} absent", token not in surface)
    offered = [p for p in sorted(PRIMITIVES) if p in surface]
    print(f"  PRIMITIVE INDEX offers {len(offered)} of {len(PRIMITIVES)} "
          f"registered: {', '.join(offered)}")
    _check(failures, "the index is registry-driven (every primitive offered)",
           len(offered) == len(PRIMITIVES))
    print("  NOTE: freeform_loop IS on the fabrication-time index above; "
          "since FF-A3 (ADR-069) the Designer index, the trusted mapper and "
          "the Designer-boundary check can also request and validate it — "
          "gate_ffa3_auto.py proves that path.")

    # ------------------------------------------------------------------
    _section(2, "THE GATE BASES — module and axis, never per-element")
    bundle = load_config_bundle()
    pid = DEFAULT_GATE_PROFILE_ID

    def gate(m: dict):
        return validate_fabrication_gate(
            m, bundle.materials.materials,
            profile=bundle.gate_profiles.profile(pid), profile_id=pid,
            version=bundle.gate_profiles.version)

    m = _segmented()
    m["fabrication_limits"] = {}
    rows = {r["check"]: r for r in gate(m).check_rows()}
    lift, env = rows["b1.mass_kg"], rows["b1.module_bbox_mm"]
    print(f"  lift  [{lift['status']}] basis: {lift['basis']}")
    print(f"  env   [{env['status']}] basis: {env['basis']}")
    _check(failures, "lift needs_input basis names the heaviest module + kg",
           lift["status"] == "needs_input" and "heaviest module" in lift["basis"]
           and "1472.3" in lift["basis"])
    _check(failures, "envelope needs_input basis says each axis on its own limit",
           env["status"] == "needs_input" and "each axis" in env["basis"])
    for row in (lift, env):
        _check(failures, f"{row['check']} carries no per-element wording",
               not any(t in row["basis"] + row["message"] for t in RETIRED)
               and ("per-" + "element") not in row["basis"] + row["message"])
    rows = {r["check"]: r for r in gate(_segmented()).check_rows()}
    lift = rows["b1.mass_kg"]
    print(f"  lift  [{lift['status']}] value {lift['value']} kg — {lift['basis']}")
    _check(failures, "with limits: lift row is the heaviest of 9 modules",
           lift["status"] == "pass" and "heaviest of 9 modules" in lift["basis"]
           and abs(float(lift["value"]) - 1472.31) < 0.01)

    # ------------------------------------------------------------------
    _section(3, "THE SCORER — five bases, printed; None is None")
    cases = []
    cases.append(("9-module basin (complete, segmented)", _segmented()))
    single = {"schema": "assembly_manifest_v1",
              "elements": [_element("p1", 850.0, "plinth")],
              "total_mass_kg": 850.0,
              "fabrication_limits": {"max_lift_kg": 2000.0}}
    cases.append(("single complete element, unsegmented", single))
    multi = {"schema": "assembly_manifest_v1",
             "elements": [_element("p1", 850.0, "plinth"), _element("b1", 3000.0)],
             "total_mass_kg": 3850.0,
             "fabrication_limits": {"max_lift_kg": 2000.0}}
    cases.append(("two elements, unsegmented", multi))
    nolift = _segmented()
    nolift["fabrication_limits"] = {"max_module_m": {"x": 2.4, "y": 2.4, "z": 2.2}}
    cases.append(("segmented, NO lift limit declared", nolift))
    incomplete = _segmented()
    incomplete["elements"][0]["primitive"] = "freeform_loop"
    incomplete["elements"][0]["mass_model"] = MassTruth(
        False, 853.036, ("armature mass (FABRICATOR-INPUT-REQUIRED)",)).wire()
    incomplete["total_mass_kg"] = None
    cases.append(("free-form, INCOMPLETE mass, segmented", incomplete))
    results = {}
    for label, manifest in cases:
        facts = facts_from_manifest(manifest)
        d = objective_score_detail(facts)
        results[label] = d
        print(f"  {label}")
        print(f"    score={d.score!r}  basis={d.handling.kind}  "
              f"pick={d.handling.pick_mass_kg}  lift={d.handling.max_lift_kg}")
        print(f"    reason: {d.handling.reason}")
    d = results["9-module basin (complete, segmented)"]
    _check(failures, "segmented complete design scores the heaviest MODULE (1472.31 kg)",
           d.score is not None and d.handling.kind == MASS_BASIS_MEASURED
           and abs(d.handling.pick_mass_kg - 1472.31) < 1e-6
           and abs(d.handling_score - (1 - 1472.31 / 2000.0)) < 1e-9,
           f"handling_score={d.handling_score}")
    d = results["single complete element, unsegmented"]
    _check(failures, "single complete element: total is the pick weight",
           d.score is not None and d.handling.kind == MASS_BASIS_SINGLE
           and d.handling.pick_mass_kg == 850.0)
    d = results["two elements, unsegmented"]
    _check(failures, "multi-element unsegmented: unavailable, score None",
           d.score is None and d.handling.kind == MASS_BASIS_UNAVAILABLE
           and "2 elements" in d.handling.reason)
    d = results["segmented, NO lift limit declared"]
    _check(failures, "no lift limit: unavailable, None, nothing defaulted",
           d.score is None and d.handling.max_lift_kg is None
           and "max_lift_kg" in d.handling.reason
           and "1000" not in d.handling.reason)
    d = results["free-form, INCOMPLETE mass, segmented"]
    _check(failures, "incomplete mass: unavailable even with a heaviest module",
           d.score is None and "armature mass" in d.handling.reason)
    real = results["9-module basin (complete, segmented)"].score
    _check(failures, "score_delta never compares an unavailable score",
           score_delta(None, real) is None and score_delta(real, None) is None
           and score_delta(0.5, 0.8) == 0.3)
    _check(failures, "a bare total_mass_kg with no basis is refused",
           objective_score_detail({"total_mass_kg": 100.0,
                                   "max_lift_kg": 1000.0}).score is None)

    # ------------------------------------------------------------------
    _section(4, "THE DOCUMENTS — corrected, with history preserved")
    docs = {
        "PHASE_6_REPORT.md": (
            "## PHASE 6 GATE: PASS - slices A1 (2026-08-20)",
            "Correction 2026-09-08 (PR-5, ADR-068)", "NOT closed"),
        "PHASE_11_12_13A_REPORT.md": (
            "**Phase 9B and Phase 10 are untouched.**",
            "Correction 2026-09-08 (PR-5, ADR-068)", "BUILT and auto-gated on 2026-08-24"),
        "LIMITATIONS.md": (
            "~~**The mapper speaks the slice A1 vocabulary.**",
            "CORRECTED 2026-09-08 (PR-5, ADR-068)", "TEN primitives"),
        "docs/operator/07_validation_gates.md": (
            "heaviest of 9 modules", "per axis", "NEEDS INPUT by design"),
    }
    for rel, needles in docs.items():
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            _check(failures, f"{rel} contains {needle[:48]!r}", needle in text)
    lim = (REPO_ROOT / "LIMITATIONS.md").read_text(encoding="utf-8")
    _check(failures, "LIMITATIONS §12 split-line sentence struck, not deleted",
           "~~**Split-line feasibility is a count, not a plan.**" in lim
           and "RETIRED 2026-09-08 (PR-5, ADR-068" in lim)

    # ------------------------------------------------------------------
    _section(5, "THE D-10 SWEEP — every frozen growth literal justified")
    _sweep(failures)
    conv = {
        "gate_phase6a2_auto.py": ("not_a_primitive_", "derived unknown name"),
        "gate_scope_audit_auto.py": ("queue entries scanned", "## 2. THE WORK QUEUE"),
        "gate_phase6c2_auto.py": ("carries the six slice-C2 paths", "_has_path"),
    }
    for name, needles in conv.items():
        text = (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")
        _check(failures, f"{name} converted to its timeless form",
               all(n in text for n in needles))
    c2_code = "\n".join(
        l for l in (REPO_ROOT / "scripts" / "gate_phase6c2_auto.py")
        .read_text(encoding="utf-8").splitlines()
        if not l.lstrip().startswith("#"))
    _check(failures, "gate_phase6c2 no longer pins missing_entries() == 39",
           "== 39" not in c2_code)
    unknown = "not_a_primitive_" + hashlib.sha256(
        ",".join(sorted(PRIMITIVES)).encode()).hexdigest()[:8]
    _check(failures, "6a2's derived unknown name is outside the live registry",
           unknown not in PRIMITIVES, unknown)

    # ------------------------------------------------------------------
    _section(6, "HERMETICITY (after) — fingerprint identical, $0")
    after = _fingerprint()
    print(f"  before db={before[0]} wal={before[1]}   after db={after[0]} wal={after[1]}")
    _check(failures, "real DB + WAL byte-identical across the gate",
           before == after)
    own = Path(__file__).read_text(encoding="utf-8")
    code = "\n".join(l for l in own.splitlines() if not l.lstrip().startswith("#"))
    # tokens assembled at runtime so this scan never matches its own list
    provider_tokens = tuple(p + " " + m for p in ("import", "from")
                            for m in ("anthro" + "pic", "open" + "ai"))
    _check(failures, "this gate is provider-free",
           not any(t in code for t in provider_tokens))
    print("  loopback health check only; no AI call; every manifest above was "
          "temporary gate data; $0")

    # ------------------------------------------------------------------
    print()
    _hline()
    if failures:
        print(f"FAIL — {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — all checks in every section passed at $0, offline, with no "
          "AI call and the real DB untouched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
