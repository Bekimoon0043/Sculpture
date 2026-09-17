#!/usr/bin/env python3
"""FF-A3 AUTO GATE — a typed brief can ask for the ref-08 loop (ADR-069).

$0, offline, non-interactive, hermetic (backend container). No provider,
no render, no AI-written code executed. Sections:

  [1] VOCABULARY TRUTH — the Designer index (real builder) carries every
      freeform_loop parameter with unit/range/default, the 316L-only line,
      the incomplete-mass inputs and the PRE-FABRICATION line, all derived
      from the registry at run time; the schema's primitive description
      names no phantom ids; the schema's dimension/ratio rule is stated.
  [2] MAPPER TRUTH — every registry key reachable by a spec-level name,
      no alias dangles; the rank-1 Council spec maps to EXACTLY the FF-A2
      acceptance parameters; a ratio carrying ANY unit is refused
      verbatim; unknown names and a material contradiction refused.
  [3] DESIGNER BOUNDARY — a scripted session whose first reply names
      freeform_loop with a 4 mm wall is re-asked with the registry's own
      text, the corrected reply persists, the bad one never does.
  [4] TYPED INTAKE -> BRIEF — the intake fixture created and confirmed
      through the real API (operator fields, no parser call); the
      composed Council brief equals the fixture's brief_text with the
      one intake id substituted (both ids printed).
  [5] FIXTURE REPLAY — the synthetic fixture replays; every spec is
      registry-valid; rank 1 states all 12 scalars + material_id
      explicitly (correction 9); the fixture equals what the live prompt
      builders produce today (loud expiry); synthetic: true printed.
  [6] TRUSTED BUILD of the rank-1 spec — mapper -> limits -> assemble ->
      persist through the shared path with the confirmed intake's water
      context: one element, total_mass_kg null, applicability snapshot
      from the registry, integrity PASS against the persisted topology,
      hydraulics "has_water = false", lift/structural NEEDS INPUT naming
      the armature; STEP sha256 equal to the FF-A2 fixture built in a
      SECOND process (both PIDs and both digests printed).
  [7] EXPORT TRUTH — PRE-FABRICATION package, unresolved-only warrant,
      two package builds byte-identical.
  [8] NEGATIVES — two lenses refused (single-element claim), wrong
      material refused at the boundary, ratio-with-unit refused at the
      boundary.
  [9] HERMETICITY — real DB/WAL fingerprint settled BEFORE (health +
      two identical reads, D-26-safe) and identical AFTER; no provider
      import in the new code; no reference JPG in the tree.

Synthetic hand-authored Council alternatives prove replay and pipeline
compatibility only — not that an AI selected the primitive from prose.
The live demonstration is the visual gate's, cost-approved separately.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

CHECKS: list[bool] = []
SECTIONS_RUN: list[str] = []

COUNCIL_FIXTURE = REPO / "tests" / "fixtures" / "council_session_ffa3_v1.json"
INTAKE_FIXTURE = REPO / "tests" / "fixtures" / "intake_ffa3_v1.json"
FFA2_FIXTURE = REPO / "tests" / "fixtures" / "freeform_loop_spec_v1.json"
SCHEMA_PATH = REPO / "schemas" / "design_spec_v1.json"


def section(title: str) -> None:
    SECTIONS_RUN.append(title.split()[0])
    print("\n[%s]" % title)
    print("-" * 72)


def ok(sec: str, label: str, cond: bool, detail: str = "") -> None:
    CHECKS.append(bool(cond))
    line = "  [%s] %-60s %s" % (sec, label, "PASS" if cond else "FAIL")
    if detail:
        line += "  (%s)" % detail
    print(line)


# ---------------------------------------------------------------------------
# hermeticity helpers (D-26-safe: health + settled fingerprint, no sleep)
# ---------------------------------------------------------------------------

def _db_paths() -> tuple[Path | None, Path | None]:
    for candidate in (Path("/app/data/luxuryform.db"),
                      REPO / "data" / "luxuryform.db"):
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
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:8000/api/health", timeout=5.0)
        body = r.json()
        good = r.status_code == 200 and body.get("status") == "ok" \
            and bool((body.get("db") or {}).get("ok"))
        return good, "HTTP %d status=%r" % (r.status_code, body.get("status"))
    except Exception as exc:  # noqa: BLE001
        return False, "%s: %s" % (type(exc).__name__, exc)


def _settled_fingerprint() -> tuple:
    deadline = time.monotonic() + 60.0
    polls = 0
    healthy, why = _backend_healthy()
    while not healthy and time.monotonic() < deadline:
        polls += 1
        time.sleep(0.25)
        healthy, why = _backend_healthy()
    ok("9", "backend healthy before any production fingerprint", healthy,
       "%s after %d poll(s)" % (why, polls))
    prev = _fingerprint()
    stable = 0
    while time.monotonic() < deadline:
        time.sleep(0.25)
        cur = _fingerprint()
        stable += 1
        if cur == prev:
            ok("9", "DB/WAL fingerprint settled (two identical reads)", True,
               "db=%s wal=%s after %d poll(s)" % (cur[0], cur[1], stable))
            return cur
        prev = cur
    ok("9", "DB/WAL fingerprint settled (two identical reads)", False,
       "never quiesced within 60 s")
    return prev


# ---------------------------------------------------------------------------

def _rank1(fx: dict) -> dict:
    chosen = fx["arbiter_decision"]["chosen_spec_ids"][0]
    return next(e["spec"] for e in fx["design_specs"]
                if e["spec"]["meta"]["spec_id"] == chosen)


def vocabulary_truth() -> None:
    section("1 vocabulary truth: what the DESIGNER is told (registry-driven)")
    from app.council.prompts import primitive_index_surface
    from app.geometry.primitives import PRIMITIVES, freeform_loop as fl
    from app.geometry.spec_mapper import _UNITLESS_SUFFIXES

    text = primitive_index_surface()
    start = text.index("- freeform_loop:")
    rest = text[start + 1:]
    end = rest.find("\n- ")
    block = rest if end == -1 else rest[:end]
    print("  printed freeform_loop block:")
    for ln in block.splitlines():
        print("    | " + ln)
    scalar_keys = [k for k in fl.PARAMETERS if k != "material_id"]
    # D-10-frozen: ADR-066 parameter-table pin restated by owner correction 3
    # (ADR-069): 12 scalars + material_id is this primitive's recorded
    # contract; a new parameter needs its own ADR and moves this count.
    ok("1", "12 scalar keys + material_id = 13 registry keys",
       len(scalar_keys) == 12 and len(fl.PARAMETERS) == 13,
       "%d + 1" % len(scalar_keys))
    missing = [k for k in scalar_keys if k not in block
               or "[%s..%s]" % (fl.PARAMETERS[k]["min"], fl.PARAMETERS[k]["max"])
               not in block]
    ok("1", "every scalar key printed with its [min..max]", not missing,
       ", ".join(missing) or "%d keys" % len(scalar_keys))
    ratio_keys = [k for k in scalar_keys if k.endswith(_UNITLESS_SUFFIXES)]
    # D-10-frozen: ADR-066 declares exactly three dimensionless keys in this
    # primitive's recorded table (skew, bore centre, waist); a fourth ratio
    # would be a parameter-table change needing its own ADR.
    ok("1", "ratio keys marked PLAIN number", "PLAIN number" in block
       and len(ratio_keys) == 3, ", ".join(ratio_keys))
    ok("1", "316L-only line derived from SUPPORTED_MATERIAL",
       fl.SUPPORTED_MATERIAL in block and "ONLY material_id" in block)
    ok("1", "incomplete-mass inputs derived from INCOMPLETE_MASS_INPUTS",
       all(m in block for m in fl.INCOMPLETE_MASS_INPUTS),
       "%d inputs" % len(fl.INCOMPLETE_MASS_INPUTS))
    ok("1", "PRE-FABRICATION line derived from REQUIRES_FREEFORM_INTEGRITY",
       "PRE-FABRICATION" in block and fl.REQUIRES_FREEFORM_INTEGRITY)
    ok("1", "every registered primitive gets a vocabulary line",
       text.count("parameters:") == len(PRIMITIVES),
       "%d of %d" % (text.count("parameters:"), len(PRIMITIVES)))

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    el = schema["$defs"]["element"]["properties"]
    desc = el["primitive"]["description"]
    named = re.findall(r"\b[a-z]+_[a-z_]+\b", desc)
    phantom = [n for n in named if n not in PRIMITIVES]
    ok("1", "schema primitive description names no phantom primitive",
       not phantom, ", ".join(phantom) or "no ids named; live index cited")
    pdesc = el["parameters"]["description"]
    ok("1", "schema states {value, unit} for dimensions, PLAIN scalars for "
            "ratios/counts/enums",
       "{value, unit}" in pdesc and "PLAIN scalars" in pdesc
       and "refused" in pdesc)


def mapper_truth(fx: dict) -> None:
    section("2 mapper truth: spec names -> registry keys, ratios plain")
    from app.geometry.primitives import freeform_loop as fl
    from app.geometry.primitives.base import ConstraintViolation
    from app.geometry.spec_mapper import (
        _UNITLESS_SUFFIXES, assembly_plan_from_spec, spec_aliases_for)

    aliases = spec_aliases_for("freeform_loop")
    dangling = sorted(set(aliases.values()) - set(fl.PARAMETERS))
    ok("2", "no alias dangles (every target is a registry key)", not dangling,
       ", ".join(dangling) or "%d aliases" % len(aliases))
    unreachable = [k for k in fl.PARAMETERS if k != "material_id"
                   and k not in aliases.values()]
    ok("2", "every scalar key has at least one spec-level name",
       not unreachable, ", ".join(unreachable) or "all 12")

    rank1 = _rank1(fx)
    plan = assembly_plan_from_spec(rank1)
    expected = json.loads(FFA2_FIXTURE.read_text(encoding="utf-8"))[
        "elements"][0]["parameters"]
    got = plan[0]["parameters"]
    for key in sorted(fl.PARAMETERS):
        print("    %-30s spec-> %-24s FF-A2 fixture %s" % (
            key, got.get(key), expected.get(key)))
    same = set(got) == set(expected) and all(
        (abs(float(got[k]) - float(expected[k])) < 1e-9
         if isinstance(expected[k], (int, float)) else got[k] == expected[k])
        for k in expected)
    ok("2", "rank-1 Council spec maps to EXACTLY the FF-A2 acceptance "
            "parameters", same)

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    units = schema["$defs"]["dimension"]["properties"]["unit"]["enum"]
    refused = 0
    tried = 0
    for key in (k for k in fl.PARAMETERS if k.endswith(_UNITLESS_SUFFIXES)):
        name = next(n for n, t in aliases.items() if t == key)
        for unit in units:
            tried += 1
            bad = copy.deepcopy(rank1)
            bad["massing"]["elements"][0]["parameters"][name] = {
                "value": 0.15, "unit": unit}
            try:
                assembly_plan_from_spec(bad)
            except ConstraintViolation as exc:
                if "dimensionless ratio" in str(exc) and key in str(exc):
                    refused += 1
                    if unit == units[0]:
                        print("    refusal: %s" % exc.violations[0])
    ok("2", "every ratio x every unit refused verbatim", refused == tried,
       "%d/%d" % (refused, tried))

    for label, mutate, needle in (
        ("unknown parameter name refused naming the keys",
         lambda s: s["massing"]["elements"][0]["parameters"].update(
             {"petal_count": 8}), "petal_count"),
        ("parameters.material_id contradiction refused",
         lambda s: s["massing"]["elements"][0]["parameters"].update(
             {"material_id": "basalt_slab"}), "contradicts"),
    ):
        bad = copy.deepcopy(rank1)
        mutate(bad)
        try:
            assembly_plan_from_spec(bad)
            ok("2", label, False, "no refusal")
        except ConstraintViolation as exc:
            ok("2", label, needle in str(exc), exc.violations[0][:70])


def designer_boundary(pricing, council_cfg) -> None:
    section("3 Designer boundary: registry refusal -> re-ask, never persisted")
    from app.council.orchestrator import CouncilOrchestrator, DispatchOutcome
    from app.db.database import Database
    from app.db.models import CouncilCallRow, CouncilSessionRow, DesignSpecRow
    from tests.test_council_orchestrator import (
        MODELS, ScriptedDispatcher, _arbiter_decision_json)

    fx = json.loads(COUNCIL_FIXTURE.read_text(encoding="utf-8"))
    base = _rank1(fx)
    bad = copy.deepcopy(base)
    bad["meta"]["spec_id"] = "0f0f0f0f-ffa3-4000-8000-000000000bad"
    bad["massing"]["elements"][0]["parameters"]["wall"] = {
        "value": 4, "unit": "mm"}
    good = copy.deepcopy(base)
    good["meta"]["spec_id"] = "0f0f0f0f-ffa3-4000-8000-00000000900d"

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = Database(Path(td) / "boundary.db")
        db.init_db()

        class Aware(ScriptedDispatcher):
            def dispatch(self, **kw):
                if kw["role"] == "arbiter" and kw["side"] == "primary":
                    with db.get_session() as s:
                        ids = [r.id for r in s.query(DesignSpecRow).all()]
                    return DispatchOutcome(
                        provider=kw["provider"], model=MODELS[kw["provider"]],
                        text=_arbiter_decision_json(ids), tokens_in=2000,
                        tokens_out=900, latency_ms=100.0,
                        cost_usd=pricing.cost_usd(kw["provider"],
                                                  MODELS[kw["provider"]],
                                                  2000, 900),
                        pricing_version=pricing.pricing_version)
                return super().dispatch(**kw)

        d = Aware(pricing, base)
        d.designer_script[("anthropic", 1)] = [json.dumps(bad), json.dumps(good)]
        orch = CouncilOrchestrator(db, pricing, d, council_cfg)
        sid = orch.run_session("typed brief (scripted boundary section)")
        with db.get_session() as s:
            sess = s.get(CouncilSessionRow, sid)
            reasks = [c.prompt for c in s.query(CouncilCallRow).filter_by(
                session_id=sid, role="designer").all()
                if "registry refusal" in c.prompt]
            ids = {r.id for r in s.query(DesignSpecRow).all()}
            n_specs = len([r for r in s.query(DesignSpecRow).filter_by(
                session_id=sid).all()])
        ok("3", "session completed with corrected=1",
           sess.status == "completed" and sess.corrected == 1,
           "status=%s corrected=%d" % (sess.status, sess.corrected))
        needle = "wall_mm=4.0: Input should be greater than or equal to 6"
        ok("3", "exactly one re-ask carrying the registry's own text",
           len(reasks) == 1 and needle in reasks[0],
           "%d re-ask(s)" % len(reasks))
        if reasks:
            line = next(ln for ln in reasks[0].splitlines()
                        if "registry refusal" in ln)
            print("    re-ask line: %s" % line[:110])
        ok("3", "the refused spec was never persisted; 6 valid specs stand",
           "0f0f0f0f-ffa3-4000-8000-000000000bad" not in ids and n_specs == 6,
           "%d specs" % n_specs)


def intake_to_brief(client, fx: dict) -> str:
    section("4 typed intake -> composed Council brief (real API)")
    from app.api.routes_council import RunSessionRequest, _compose_brief
    from app.db.database import get_default_db

    intake_fx = json.loads(INTAKE_FIXTURE.read_text(encoding="utf-8"))
    r = client.post("/api/intake", json={"brief_text": intake_fx["brief_text"],
                                         "fields": intake_fx["fields"]})
    ok("4", "intake created from operator-typed fields", r.status_code == 201,
       "HTTP %d" % r.status_code)
    body = r.json()
    intake_id = body["id"]
    sources = {v.get("source") for section_ in body["intake"].values()
               if isinstance(section_, dict) for v in section_.values()
               if isinstance(v, dict)}
    ok("4", "no parsed/default field — operator or unknown only",
       sources <= {"operator", "unknown"}, ", ".join(sorted(sources)))
    c = client.post("/api/intake/%s/confirm" % intake_id)
    ok("4", "intake confirmed (tiers 1-2 answered)", c.status_code == 200,
       "HTTP %d status=%s" % (c.status_code, c.json().get("status")))
    composed, ctx = _compose_brief(
        RunSessionRequest(brief_text=intake_fx["brief_text"], intake_id=intake_id),
        get_default_db())
    print("    API intake id     : %s" % intake_id)
    print("    fixture intake id : %s" % intake_fx["intake_id_in_fixture"])
    same = composed.replace(intake_id, intake_fx["intake_id_in_fixture"]) \
        == fx["session"]["brief_text"]
    ok("4", "composed brief == fixture brief_text (one id substituted)", same,
       "%d chars" % len(composed))
    ok("4", "dry design: has_water false is operator-sourced",
       body["intake"]["water"]["has_water"]["value"] is False
       and body["intake"]["water"]["has_water"]["source"] == "operator")
    return intake_id


def fixture_replay(db, pricing) -> dict:
    section("5 fixture replay + registry validity + explicit parameters")
    from app.council.orchestrator import _validate_live_primitives
    from app.council.replay import load_fixture, replay_session
    from app.db.models import CouncilSessionRow, DesignSpecRow
    from app.geometry.primitives import freeform_loop as fl
    from app.geometry.spec_mapper import spec_aliases_for
    import make_ffa3_fixture as gen

    fx = load_fixture(COUNCIL_FIXTURE)
    print("    synthetic: %s" % fx["synthetic"])
    ok("5", "fixture is marked synthetic and states what it proves",
       fx["synthetic"] is True
       and "prove replay and pipeline compatibility only" in fx["note"]
       and "not that an AI selected the primitive from prose" in fx["note"])
    regenerated = gen.dumps(gen.build_fixture())
    ok("5", "fixture == live prompt builders + schema + registry today",
       regenerated == COUNCIL_FIXTURE.read_text(encoding="utf-8"),
       "%d bytes" % len(regenerated))
    sid = replay_session(db, pricing, fx)
    with db.get_session() as s:
        sess = s.get(CouncilSessionRow, sid)
        specs = [json.loads(r.spec_json) for r in
                 s.query(DesignSpecRow).filter_by(session_id=sid).all()]
    print("    replayed %s: %d calls, %d specs, recomputed $%s (never spent)"
          % (sid[:8], len(fx["calls"]), len(specs), sess.total_cost_usd))
    ok("5", "6 specs replayed, cost recomputed > 0",
       len(specs) == 6 and sess.total_cost_usd > 0)
    problems = {sp["meta"]["spec_id"][:8]: _validate_live_primitives(sp)
                for sp in specs}
    ok("5", "every spec names freeform_loop and passes mapper + validate()",
       all(sp["massing"]["elements"][0]["primitive"] == "freeform_loop"
           for sp in specs) and not any(problems.values()),
       "; ".join("%s: %s" % (k, v) for k, v in problems.items() if v) or "6/6")
    rank1 = _rank1(fx)
    aliases = spec_aliases_for("freeform_loop")
    params = rank1["massing"]["elements"][0]["parameters"]
    stated = {aliases.get(n, n) for n in params}
    for name, value in params.items():
        print("    %-24s -> %-28s = %s" % (name, aliases.get(name, name), value))
    ok("5", "rank 1 states all 12 scalars + material_id explicitly (13/13)",
       stated == set(fl.PARAMETERS), "%d/%d" % (len(stated), len(fl.PARAMETERS)))
    return fx


def trusted_build(client, fx: dict, intake_id: str) -> dict:
    section("6 trusted build of the rank-1 spec (mapper -> assemble -> "
            "persist)")
    from sqlalchemy import select

    from app.api.routes_assembly import (
        AssemblyBuildRequest, persist_assembly_design)
    from app.db.database import get_default_db
    from app.db.models import DesignRow, ValidationReportRow
    from app.geometry import assemble
    from app.geometry.freeform_validation import FREEFORM_INTEGRITY_GATE
    from app.geometry.primitives import PRIMITIVES
    from app.geometry.spec_mapper import (
        assembly_plan_from_spec, fabrication_limits_from_spec)

    rank1 = _rank1(fx)
    plan = assembly_plan_from_spec(rank1)
    limits = fabrication_limits_from_spec(rank1)
    seed = int(rank1["meta"]["seed"])
    print("    limits from spec: %s; seed %d" % (limits, seed))
    t0 = time.perf_counter()
    solid, manifest, element_solids = assemble(
        plan, seed=seed, fabrication=limits, strict=True, return_solids=True)
    request = AssemblyBuildRequest(elements=plan, fabrication=limits,
                                   seed=seed, strict=True, intake_id=intake_id)
    db = get_default_db()
    result = persist_assembly_design(
        request, solid, manifest, element_solids, t0=t0, db=db,
        spec_id=rank1["meta"]["spec_id"])
    design_id = result["design_id"]
    print("    design %s built in %.1f s; STEP %s" % (
        design_id[:8], time.perf_counter() - t0, result["step_sha256"][:16]))
    ok("6", "one element, primitive freeform_loop",
       len(manifest["elements"]) == 1
       and manifest["elements"][0]["primitive"] == "freeform_loop")
    ok("6", "total_mass_kg is null (never zero)",
       manifest["total_mass_kg"] is None)
    declared = sorted({FREEFORM_INTEGRITY_GATE for e in manifest["elements"]
                       if getattr(PRIMITIVES[e["primitive"]],
                                  "REQUIRES_FREEFORM_INTEGRITY", False)})
    ok("6", "required_validation_gates == what the registry declares",
       manifest.get("required_validation_gates") == declared and declared,
       ", ".join(declared))
    with db.get_session() as s:
        rows = s.execute(select(ValidationReportRow).where(
            ValidationReportRow.design_id == design_id)).scalars().all()
        reports = {r.gate_name: (r.status, json.loads(r.numbers_json))
                   for r in rows}
        drow = s.get(DesignRow, design_id)
        lineage = drow.spec_id
    ok("6", "design row carries the Council spec id (lineage)",
       lineage == rank1["meta"]["spec_id"])
    integ = reports.get(FREEFORM_INTEGRITY_GATE)
    ok("6", "freeform_integrity_v1 row PASS against the persisted topology",
       integ is not None and integ[0] == "pass"
       and manifest.get("expected_topology", {}).get("per_component_genus")
       == [1, 1], str(integ[0] if integ else None))

    def checks(name):
        rep = reports.get(name)
        return {c["check"]: c for c in (rep[1].get("checks") or [])} if rep else {}

    hyd = checks("hydraulics_v1") or checks("hydraulics")
    hyd_name = "hydraulics_v1" if "hydraulics_v1" in reports else "hydraulics"
    wd = hyd.get("water_designed", {})
    ok("6", "hydraulics: water_designed basis 'has_water = false' from the "
            "intake", "has_water = false" in str(wd.get("basis")),
       "%s: %s" % (hyd_name, wd.get("basis")))
    fab = checks("fabrication")
    lift = fab.get("loop_01.mass_kg", {})
    ok("6", "fabrication lift row NEEDS INPUT naming the armature",
       lift.get("status") == "needs_input"
       and "armature" in json.dumps(lift).lower(), str(lift.get("status")))
    struct = checks("structure_static_v1")
    tm = struct.get("total_mass_kg", {})
    ok("6", "structural total_mass_kg NEEDS INPUT",
       tm.get("status") == "needs_input", str(tm.get("status")))

    # determinism across gates: the same parameters + seed as the FF-A2
    # acceptance fixture must give the same STEP bytes in a SECOND process.
    code = r"""
import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, %r)
from app.geometry import assemble
from app.geometry.exporters import export_step
from app.geometry.kernel import step_timestamp_for
fx = json.loads(Path(%r).read_text(encoding="utf-8"))
payload = {k: v for k, v in fx.items() if not k.startswith("_")}
solid, manifest = assemble(payload["elements"], seed=payload["seed"],
                           fabrication=payload["fabrication"], strict=True)
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
    sha = export_step(solid, Path(td) / "ffa2.step",
                      step_timestamp_for(int(payload["seed"])))
print(json.dumps({"pid": os.getpid(), "sha256": sha}))
""" % (str(REPO / "backend"), str(FFA2_FIXTURE))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, timeout=900)
    other = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.returncode == 0 \
        else {"pid": None, "sha256": proc.stderr[-300:]}
    print("    this process  pid %d  STEP %s" % (os.getpid(), result["step_sha256"]))
    print("    other process pid %s  STEP %s" % (other["pid"], other["sha256"]))
    ok("6", "STEP sha256 == FF-A2 fixture STEP built in a second process",
       proc.returncode == 0 and other["sha256"] == result["step_sha256"]
       and other["pid"] != os.getpid())
    return {"design_id": design_id, "manifest": manifest}


def export_truth(client, built: dict) -> None:
    section("7 export truth: PRE-FABRICATION, unresolved-only warrant, "
            "reproducible")
    design_id = built["design_id"]
    r = client.post("/api/geometry/assembly/%s/exports" % design_id)
    ok("7", "export seals PRE-FABRICATION",
       r.status_code == 200 and r.json().get("package_class") == "pre_fabrication",
       "HTTP %d %s" % (r.status_code, r.json().get("package_class")))
    z1 = client.get("/api/geometry/assembly/%s/luxexchange.zip" % design_id)
    z2 = client.get("/api/geometry/assembly/%s/luxexchange.zip" % design_id)
    ok("7", "two package downloads byte-identical",
       z1.status_code == 200 and z1.content == z2.content,
       "%d bytes sha %s" % (len(z1.content),
                            hashlib.sha256(z1.content).hexdigest()[:12]))
    with zipfile.ZipFile(io.BytesIO(z1.content)) as zf:
        names = set(zf.namelist())
        warrant = zf.read("ENGINEERING_WARRANT.txt").decode("utf-8") \
            if "ENGINEERING_WARRANT.txt" in names else ""
    ok("7", "warrant names the unresolved professional inputs",
       "armature mass" in warrant and "forming radius" in warrant.lower()
       and "fabrication_wall_approval" in warrant)
    ok("7", "warrant carries no passing statuses",
       bool(warrant) and all("pass" not in ln.split("status:")[1]
                             for ln in warrant.splitlines() if "status:" in ln))


def negatives(fx: dict) -> None:
    section("8 negatives: single-element claim, wrong material, ratio unit")
    from app.council.orchestrator import _validate_live_primitives
    from app.geometry import assemble
    from app.geometry.primitives.base import ConstraintViolation
    from app.geometry.spec_mapper import assembly_plan_from_spec

    rank1 = _rank1(fx)
    two = copy.deepcopy(rank1)
    second = copy.deepcopy(two["massing"]["elements"][0])
    second["element_id"] = "loop_02"
    second["position"] = {"x_m": 6.0, "y_m": 0.0, "z_m": 0.0}
    two["massing"]["elements"].append(second)
    outcome = ""
    try:
        plan = assembly_plan_from_spec(two)
        assemble(plan, seed=8, fabrication={"max_module_m": {"x": 5, "y": 5, "z": 5},
                                            "max_lift_kg": 3000}, strict=True)
        refused = False
        outcome = "BUILT — two roots accepted"
    except ConstraintViolation as exc:
        refused = True
        outcome = exc.violations[0][:90]
    ok("8", "two lenses (no joint possible) refused by the assembler", refused,
       outcome)
    stacked = copy.deepcopy(two)
    stacked["massing"]["elements"][1]["parent_id"] = "loop_01"
    try:
        plan = assembly_plan_from_spec(stacked)
        assemble(plan, seed=8, strict=True)
        refused = False
        outcome = "BUILT — a lens accepted a child"
    except ConstraintViolation as exc:
        refused = True
        outcome = exc.violations[0][:90]
    ok("8", "a lens stacked on a lens refused (cannot parent)", refused, outcome)

    wrong = copy.deepcopy(rank1)
    wrong["massing"]["elements"][0]["material_id"] = "basalt_slab"
    wrong["massing"]["elements"][0]["parameters"]["material_id"] = "basalt_slab"
    errs = _validate_live_primitives(wrong)
    ok("8", "wrong material refused at the Designer boundary by name",
       any("only 'stainless_316l_sheet'" in e for e in errs),
       (errs[0][:90] if errs else "accepted"))
    ratio = copy.deepcopy(rank1)
    ratio["massing"]["elements"][0]["parameters"]["skew"] = {
        "value": 0.15, "unit": "m"}
    errs = _validate_live_primitives(ratio)
    ok("8", "ratio with a unit refused at the Designer boundary",
       any("dimensionless ratio" in e for e in errs),
       (errs[0][:90] if errs else "accepted"))


def hermeticity_after(before: tuple) -> None:
    section("9 hermeticity after + $0 static scan")
    after = _fingerprint()
    ok("9", "real DB byte-identical", before[0] == after[0],
       "%s -> %s" % (before[0], after[0]))
    ok("9", "real WAL byte-identical", before[1] == after[1],
       "%s -> %s" % (before[1], after[1]))
    forbidden = tuple("import " + m for m in ("requests", "socket")) + \
        tuple(p + " " + m for p in ("from", "import")
              for m in ("anthropic", "openai"))
    from app.council import orchestrator, prompts
    from app.geometry import spec_mapper
    for path in (Path(spec_mapper.__file__), Path(prompts.__file__),
                 Path(orchestrator.__file__), HERE / "make_ffa3_fixture.py",
                 Path(__file__).resolve()):
        code = "\n".join(ln for ln in path.read_text(encoding="utf-8").splitlines()
                         if not ln.lstrip().startswith("#"))
        bad = [t for t in forbidden if t in code]
        ok("9", "%s provider-free" % path.name, not bad, ", ".join(bad))
    jpgs = list((REPO / "briefs").rglob("*.jpg")) if (REPO / "briefs").exists() else []
    # B-11 owner amendment 1 (2026-09-02, ADR-064): the reference set IS
    # operator-local by policy — gitignored and dockerignored with a
    # committed manifest. The security property is that none of it is
    # TRACKED: a committed reference JPG would ship in the image. So the
    # check fails on tracked files only (in the container the gitignored
    # set is absent and this passes vacuously).
    import shutil
    tracked = []
    if shutil.which("git") is None:
        tracked = jpgs  # cannot prove uncommitted — fail closed
    else:
        for j in jpgs:
            rel = j.relative_to(REPO).as_posix()
            proc = subprocess.run(
                ["git", "ls-files", "--error-unmatch", "--", rel],
                cwd=REPO, capture_output=True)
            if proc.returncode == 0:
                tracked.append(j)
    ok("9", "no TRACKED reference JPG (operator-local set stays "
            "uncommitted)",
       not tracked, "%d present, %d tracked" % (len(jpgs), len(tracked)))


def main() -> int:
    print("=" * 72)
    print("FF-A3 AUTO GATE -- a typed brief can ask for the ref-08 loop "
          "(ADR-069)")
    print("repo root: %s" % REPO)
    print("Synthetic hand-authored Council alternatives prove replay and "
          "pipeline\ncompatibility only -- not that an AI selected the "
          "primitive from prose.")
    print("=" * 72)
    section("9 hermeticity before (health + settled fingerprint, D-26-safe)")
    before = _settled_fingerprint()

    from app.core.config import load_config_bundle
    bundle = load_config_bundle()

    vocabulary_truth()
    fx = json.loads(COUNCIL_FIXTURE.read_text(encoding="utf-8"))
    mapper_truth(fx)
    designer_boundary(bundle.pricing, bundle.council)

    old_db = os.environ.get("LUXURYFORM_DB")
    old_data = os.environ.get("LUXURYFORM_DATA_DIR")
    # ignore_cleanup_errors: on Windows a SQLite connection from the API
    # run can outlive the reset and hold the throwaway DB open for a
    # moment; the directory is %TEMP% garbage either way.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        os.environ["LUXURYFORM_DB"] = str(Path(td) / "gate_ffa3.db")
        os.environ["LUXURYFORM_DATA_DIR"] = str(Path(td) / "data")
        try:
            from app.db.database import get_default_db, reset_default_db
            reset_default_db()
            from fastapi.testclient import TestClient
            from app.main import app
            with TestClient(app) as client:
                intake_id = intake_to_brief(client, fx)
                fx = fixture_replay(get_default_db(), bundle.pricing)
                built = trusted_build(client, fx, intake_id)
                export_truth(client, built)
                negatives(fx)
        finally:
            for key, val in (("LUXURYFORM_DB", old_db),
                             ("LUXURYFORM_DATA_DIR", old_data)):
                if val is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = val
            from app.db.database import reset_default_db
            reset_default_db()
            importlib.invalidate_caches()

    hermeticity_after(before)

    print("\n" + "=" * 72)
    print("sections run: %s" % "; ".join(SECTIONS_RUN))
    passed = sum(1 for c in CHECKS if c)
    failed = len(CHECKS) - passed
    if failed:
        print("FAIL -- %d of %d checks failed." % (failed, len(CHECKS)))
        print("=" * 72)
        return 1
    print("PASS -- all %d checks passed at $0, offline, with no AI call and "
          "no production data touched." % passed)
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
