"""FF-A1 auto gate — incomplete-mass truth + freeform_integrity_v1 (ADR-065).

$0, offline, non-interactive. Sections:

  [1] AST consumer census — every read of a mass key in backend/app,
      resolved to (module :: enclosing symbol) with Python's ast, matched
      against the ADR-065 allowlist. No regex, no file:line identities.
  [2] Behavioral truth, per consumer, on a crafted incomplete manifest.
  [3] Impossible-PASS proof: mass-dependent checks cannot pass while the
      mass truth is incomplete.
  [4] Production integrity stack on real registered-primitive geometry,
      incl. the fail-closed indeterminate path.
  [5] Classifier matrix: missing/failed/indeterminate/unknown/malformed
      required evidence => REFUSED; legacy no-snapshot untouched.
  [6] Legacy byte-compat on the REAL persisted designs (read-only; skips
      loudly when no DB is present on this checkout).
  [7] Frontend truth allowlist (typed symbols + the banned phrase gone).
  [8] Hermeticity + $0 static scan.

This gate never builds AI-loop code and never writes production data.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
BACKEND = REPO / "backend" / "app"

CHECKS: list[bool] = []
SECTIONS_RUN: list[str] = []
SECTIONS_SKIPPED: list[str] = []

MASS_KEYS = {"mass_kg", "total_mass_kg", "crane_pick_kg",
             "known_geometry_mass_kg"}

#: The ADR-065 census allowlist — (module, top-level symbol). A mass key
#: read anywhere else in backend/app fails this gate by symbol name.
CENSUS_ALLOWLIST = {
    ("app.geometry.mass_model", "*"),
    ("app.geometry.assembly", "assemble"),
    ("app.geometry.validate", "ElementReport"),
    ("app.geometry.validate", "AssemblyValidationReport"),
    ("app.geometry.validate", "validate_assembly"),
    ("app.geometry.validate", "validate_mesh"),
    ("app.geometry.gates", "_mass_centroid"),
    ("app.geometry.gates", "validate_structural_gate"),
    ("app.geometry.gates", "validate_fabrication_gate"),
    ("app.geometry.gates", "_rigging_check"),
    ("app.geometry.gates", "stored_water_mass_kg"),
    ("app.geometry.segmentation", "segment_solid"),
    ("app.geometry.segmentation", "SegmentResult"),
    # Module masses are GEOMETRY-KNOWN (module volume x density); their
    # completeness gating lives in the fabrication gate (needs_input on
    # incomplete elements), proven behaviorally in section 2.
    ("app.geometry.segmentation", "_module_record"),
    ("app.geometry.assembly", "build_segmentation"),
    # The cascade's single-element report: cascade is a frozen legacy
    # complete-mass primitive, so this path can never see incomplete mass.
    ("app.geometry.validate", "ValidationReport"),
    # Renders CostDrivers values; drivers REFUSE incomplete mass upstream
    # (IncompleteMassError), so no incomplete figure can reach this text.
    ("app.costing.report", "render_bom"),
    ("app.geometry.freeform_validation", "run_freeform_integrity"),
    ("app.costing.drivers", "*"),
    ("app.costing.bom", "*"),
    # PR-4 (ADR-067), D-10 instance seven. The trip allocator is pure
    # arithmetic over (module id, mass) pairs handed to it by
    # bom.transport(): it opens no manifest, no validation report and no
    # database, and it never decides whether a mass is complete. Every
    # path that reaches it runs drivers_for_assembly FIRST, which raises
    # IncompleteMassError on an incomplete mass before a single module
    # mass is read (proven behaviourally by gate_pr4_auto section 7e),
    # so an INCOMPLETE mass can never reach these symbols at all.
    # Listed as three EXACT symbols by operator ruling 2026-09-07 — not a
    # module wildcard — so a future symbol in this module must be audited
    # on its own merits rather than inheriting the exemption.
    ("app.costing.transport", "NoFeasibleAllocation"),
    ("app.costing.transport", "TripAllocation"),
    ("app.costing.transport", "allocate_trips"),
    ("app.dna.store", "derive_tags"),
    ("app.dna.store", "precedent_block"),
    ("app.council.critique", "objective_score"),
    ("app.council.prompts", "*"),
    ("app.api.routes_assembly", "persist_assembly_design"),
    ("app.api.routes_assembly", "list_designs"),
    ("app.api.routes_costing", "*"),
    ("app.geometry.luxexchange", "build_luxexchange_package"),
    ("app.geometry.package_class", "*"),
}


def ok(section: str, label: str, passed: bool, detail: str = "") -> bool:
    CHECKS.append(bool(passed))
    print("  %-4s [%s] %s%s" % ("ok" if passed else "FAIL", section, label,
                                (" -- " + detail) if detail else ""))
    return bool(passed)


def section(title: str) -> None:
    print("\n[%s]" % title)
    SECTIONS_RUN.append(title)


def skipped(title: str, why: str) -> None:
    print("\n[%s] SKIPPED -- %s" % (title, why))
    SECTIONS_SKIPPED.append(title)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# [1] AST census
# ---------------------------------------------------------------------------

def _enclosing_symbols(tree: ast.Module) -> list[tuple[str, ast.AST]]:
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            out.append((node.name, node))
    return out


def _mentions_mass(node: ast.AST) -> set[str]:
    """Every syntactic way a mass key is read or bound: string subscripts
    and .get keys (Constant), attribute access, bare names (dataclass
    fields, locals), argument names and keyword arguments."""
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                and sub.value in MASS_KEYS:
            found.add(sub.value)
        elif isinstance(sub, ast.Attribute) and sub.attr in MASS_KEYS:
            found.add(sub.attr)
        elif isinstance(sub, ast.Name) and sub.id in MASS_KEYS:
            found.add(sub.id)
        elif isinstance(sub, ast.arg) and sub.arg in MASS_KEYS:
            found.add(sub.arg)
        elif isinstance(sub, ast.keyword) and sub.arg in MASS_KEYS:
            found.add(sub.arg)
    return found


def census() -> None:
    section("1 AST consumer census (ADR-065 allowlist)")
    findings: dict[tuple[str, str], set[str]] = {}
    for py in sorted(BACKEND.rglob("*.py")):
        module = "app." + ".".join(
            py.relative_to(BACKEND).with_suffix("").parts)
        module = module.replace(".__init__", "")
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for name, node in _enclosing_symbols(tree):
            keys = _mentions_mass(node)
            if keys:
                findings[(module, name)] = keys
        # module-level mentions outside any def/class
        top = ast.Module(body=[n for n in tree.body if not isinstance(
            n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))],
            type_ignores=[])
        keys = _mentions_mass(top)
        if keys:
            findings[(module, "<module>")] = keys
    unlisted = []
    for (module, symbol), keys in sorted(findings.items()):
        allowed = ((module, symbol) in CENSUS_ALLOWLIST
                   or (module, "*") in CENSUS_ALLOWLIST)
        if not allowed:
            unlisted.append((module, symbol, sorted(keys)))
    ok("1", "every mass consumer is on the ADR-065 allowlist",
       not unlisted,
       "; ".join(f"{m}::{s} reads {k}" for m, s, k in unlisted) or
       f"{len(findings)} consumer symbols found, all listed")
    print("      consumers found: %d (allowlist entries: %d)"
          % (len(findings), len(CENSUS_ALLOWLIST)))


# ---------------------------------------------------------------------------
# [2]-[5] behavioral sections (import the app)
# ---------------------------------------------------------------------------

def behavioral() -> None:
    from app.core.config import DEFAULT_GATE_PROFILE_ID, load_config_bundle
    from app.costing.drivers import IncompleteMassError, drivers_for_assembly
    from app.council.critique import objective_score
    from app.dna.store import derive_tags
    from app.geometry import freeform_validation as fv
    from app.geometry import gates as gates_mod
    from app.geometry.mass_model import (
        MALFORMED_REQUIRED_GATES,
        MassTruth,
        assembly_mass_truth,
        element_mass_truth,
        required_validation_gates,
    )
    from app.geometry.package_class import CLASS_REFUSED, classify_reports
    from app.geometry.primitives import torus_ring
    from app.geometry.validate import (
        AssemblyValidationReport,
        VolumeCrossCheck,
    )

    missing_inputs = ("armature mass and centroid "
                      "(FABRICATOR-INPUT-REQUIRED)",)

    def element(mass=900.0, incomplete=True):
        e = {
            "element_id": "root_01", "primitive": "plinth",
            "material_id": "basalt_slab", "parameters": {"wall_mm": 120.0},
            "placement_mm": {"x": 0.0, "y": 0.0, "z": 0.0},
            "volume_mm3": mass / 2700.0 * 1e9, "mass_kg": mass,
            "bbox_mm": [2000.0, 2000.0, 400.0],
            "bbox_min_mm": [-1000.0, -1000.0, 0.0],
            "bbox_max_mm": [1000.0, 1000.0, 400.0],
            "centroid_mm": {"x": 0.0, "y": 0.0, "z": 200.0},
        }
        if incomplete:
            e["mass_model"] = MassTruth(False, mass, missing_inputs).wire()
        return e

    def manifest(incomplete=True, mass=900.0):
        m = {
            "schema": "assembly_manifest_v1", "seed": 7,
            "elements": [element(mass, incomplete)], "joints": [],
            "fabrication_limits": {"max_lift_kg": 3000.0,
                                   "max_module_m": None},
            "fabrication_limit_violations": [], "strict": True,
            "total_mass_kg": None if incomplete else mass,
            "assembly_bbox_min_mm": [-1000.0, -1000.0, 0.0],
            "assembly_bbox_max_mm": [1000.0, 1000.0, 400.0],
            "body_count_brep": 1,
        }
        if incomplete:
            m["mass_model"] = MassTruth(False, mass, missing_inputs).wire()
        return m

    bundle = load_config_bundle()
    profile_id = DEFAULT_GATE_PROFILE_ID
    profile = bundle.gate_profiles.profile(profile_id)
    materials = bundle.materials.materials

    section("2 behavioral truth per consumer (incomplete manifest)")
    truth = assembly_mass_truth(manifest())
    ok("2", "total_mass_kg is None (never zero)",
       truth.total_mass_kg is None and truth.total_mass_kg != 0.0)
    ok("2", "known-geometry figure carries its basis",
       "incomplete" in truth.basis_text()
       and "FABRICATOR-INPUT-REQUIRED" in truth.basis_text())
    bad = element()
    bad["mass_model"] = {"mass_complete": True,
                         "known_geometry_mass_kg": 1.0,
                         "missing_mass_inputs": ["x"]}
    bad_truth = element_mass_truth(bad)
    ok("2", "inconsistent mass-model data fails closed",
       bad_truth.mass_complete is False
       and bad_truth.total_mass_kg is None,
       "; ".join(bad_truth.missing_mass_inputs)[:100])

    structural = gates_mod.validate_structural_gate(
        manifest(), materials, profile=profile, profile_id=profile_id,
        constants=bundle.gate_profiles.constants,
        version=bundle.gate_profiles.version)
    rows = {c.check: c for c in structural.checks}
    ok("2", "structural total_mass_kg -> needs_input naming inputs",
       rows["total_mass_kg"].status == "needs_input"
       and "FABRICATOR-INPUT-REQUIRED" in rows["total_mass_kg"].message)
    ok("2", "centroid/overturning/bearing not evaluated",
       "center_of_mass_lever_mm" not in rows
       and "ground_bearing_pressure_kpa" not in rows
       and rows["stability"].status == "needs_input")

    fabrication = gates_mod.validate_fabrication_gate(
        manifest(), materials, profile=profile, profile_id=profile_id,
        version=bundle.gate_profiles.version)
    frows = {c.check: c for c in fabrication.checks}
    ok("2", "lift/crane -> needs_input naming inputs",
       frows["root_01.mass_kg"].status == "needs_input"
       and "INCOMPLETE" in frows["root_01.mass_kg"].message)

    light = manifest()
    light["elements"][0]["mass_kg"] = 10.0
    light["elements"][0]["mass_model"] = MassTruth(
        False, 10.0, missing_inputs).wire()
    fab_light = gates_mod.validate_fabrication_gate(
        light, materials, profile=profile, profile_id=profile_id,
        version=bundle.gate_profiles.version)
    lrows = {c.check: c for c in fab_light.checks}
    ok("2", "no-rigging-needed cannot pass on incomplete mass",
       lrows["rigging_declared"].status == "needs_input")

    report = AssemblyValidationReport(
        glb_path="x.glb", element_count=1, joint_count=0, watertight=True,
        winding_consistent=True, body_count=1, volume_mm3=1e8,
        surface_area_mm2=1e6, degenerate_face_count=0, face_count=100,
        element_masses_kg={"root_01": 900.0}, total_mass_kg=None,
        volume_crosscheck=VolumeCrossCheck(
            trimesh_volume_mm3=1e8, build123d_volume_mm3=1e8, delta_pct=0.0,
            tolerance_pct=2.0, within_tolerance=True),
        passed=True)
    try:
        drivers_for_assembly(report, manifest())
        ok("2", "costing refuses incomplete mass", False, "no exception")
    except IncompleteMassError as exc:
        ok("2", "costing/BOM not_computable with inputs named",
           exc.known_geometry_mass_kg == 900.0
           and bool(exc.missing_mass_inputs),
           str(exc)[:100])

    tags = derive_tags({"manifest": manifest(),
                        "request": {"seed": 7, "water": {}}}, {}, "pass",
                       None)
    ok("2", "DNA tags: null total + mass_complete flag",
       tags["total_mass_kg"] is None and tags["mass_complete"] is False)
    ok("2", "critique mass component contributes nothing on incomplete mass",
       objective_score({"total_mass_kg": None, "max_lift_kg": 1000.0})
       < objective_score({"total_mass_kg": 100.0, "max_lift_kg": 1000.0}))
    total_row = next(r for r in report.check_rows()
                     if r["check"] == "total_mass_kg")
    ok("2", "mesh-report row labels known-geometry figure, no bare total",
       total_row["value"].get("mass_complete") is False
       and total_row["value"].get("total_mass_kg") is None,
       json.dumps(total_row["value"]))

    section("3 impossible-PASS proof (mass checks under incomplete truth)")
    attempts = 0
    passes = []
    for mass in (0.5, 10.0, 900.0, 2999.0, 5000.0):
        m = manifest(mass=mass)
        s = gates_mod.validate_structural_gate(
            m, materials, profile=profile, profile_id=profile_id,
            constants=bundle.gate_profiles.constants,
            version=bundle.gate_profiles.version)
        f = gates_mod.validate_fabrication_gate(
            m, materials, profile=profile, profile_id=profile_id,
            version=bundle.gate_profiles.version)
        for c in list(s.checks) + list(f.checks):
            if c.check in ("total_mass_kg", "root_01.mass_kg",
                           "rigging_declared", "stability"):
                attempts += 1
                if c.status == "pass":
                    passes.append((mass, c.check))
    ok("3", "no mass-dependent check passed in %d attempts" % attempts,
       not passes, str(passes))

    section("4 production integrity stack (real kernel geometry)")
    params = torus_ring.validate(
        {"major_diameter_mm": 1800, "minor_diameter_mm": 320}, None)
    solid = torus_ring.build(params)
    integ = fv.run_freeform_integrity(solid)
    by_name = {c["check"]: c for c in integ["checks"]}
    ok("4", "torus_ring passes the stack", integ["status"] == "pass",
       json.dumps({k: v["value"] for k, v in by_name.items()})[:160])
    ok("4", "genus measured", by_name["genus"]["value"] == 1)
    ok("4", "volume cross-check within tolerance",
       by_name["volume_cross_check"]["value"] <= fv.REL_VOL_TOL,
       "rel diff %s (tol %s)" % (by_name["volume_cross_check"]["value"],
                                 fv.REL_VOL_TOL))
    original = fv.occ_self_interference
    try:
        fv.occ_self_interference = lambda wrapped: {
            "available": True, "pattern": "gate-test",
            "has_errors": False, "is_valid": False}
        indeterminate = fv.run_freeform_integrity(solid)
    finally:
        fv.occ_self_interference = original
    ok("4", "indeterminate OCC verdict fails closed as needs_input",
       indeterminate["status"] == "needs_input")

    section("5 classifier: required evidence => REFUSED matrix")
    base = {
        "assembly_mesh": {"watertight": True, "passed": True},
        "structure_static_v1": {"status": "pass", "checks": []},
        "hydraulics": {"status": "pass", "checks": []},
        "fabrication": {"status": "pass", "checks": []},
    }
    req = ("freeform_integrity_v1",)
    cases = [
        ("missing row", dict(base), req, True),
        ("failed row", {**base, "freeform_integrity_v1": {
            "status": "fail", "checks": []}}, req, True),
        ("indeterminate row", {**base, "freeform_integrity_v1": {
            "status": "needs_input", "checks": []}}, req, True),
        ("unknown required gate", dict(base), ("mystery_v9",), True),
        ("malformed snapshot", dict(base), (MALFORMED_REQUIRED_GATES,), True),
        ("passing row", {**base, "freeform_integrity_v1": {
            "status": "pass", "checks": []}}, req, False),
        ("legacy: no snapshot", dict(base), (), False),
    ]
    for label, reports, required, expect_refused in cases:
        result = classify_reports(reports,
                                  required_validation_gates=required)
        refused = result.package_class == CLASS_REFUSED
        ok("5", label + (" => REFUSED" if expect_refused else " => not refused"),
           refused == expect_refused,
           result.reasons[0][:110] if result.reasons else "")
    m_ok = manifest(incomplete=False)
    ok("5", "legacy manifest yields no snapshot",
       required_validation_gates(m_ok) == ())


def legacy_compat() -> None:
    db_path = None
    for candidate in (Path("/app/data/luxuryform.db"),
                      REPO / "data" / "luxuryform.db"):
        if candidate.exists():
            db_path = candidate
            break
    if db_path is None:
        skipped("6 legacy byte-compat on real designs",
                "no production DB on this checkout")
        return
    section("6 legacy byte-compat + key consistency on real persisted "
            "designs (read-only)")
    # D-10 INSTANCE SIX (corrected by operator ruling 2026-09-07): the
    # original check asserted EVERY stored manifest is legacy-clean — a
    # truth of the FF-A1 era with a built-in expiry, which correctly
    # FAILED 1-of-35 on 2026-09-07 the moment the operator persisted the
    # first real freeform_loop design (70b12dd3…) during the FF-A2
    # visual walk. That FAIL is preserved verbatim in ADR-066/NEXT.md.
    # The timeless checks below state ADR-065 decision 2 exactly:
    # legacy-clean applies to ALL-LEGACY manifests; new keys and a
    # non-legacy primitive must imply each other, both directions.
    import sqlite3
    from app.geometry.mass_model import (
        LEGACY_COMPLETE_MASS_PRIMITIVES,
        required_validation_gates,
    )
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, parameter_json FROM designs").fetchall()
    finally:
        con.close()
    n_legacy = 0
    n_nonlegacy = 0
    legacy_offenders = []
    key_offenders = []
    for design_id, raw in rows:
        try:
            stored = json.loads(raw or "{}")
        except ValueError:
            continue
        manifest = (stored or {}).get("manifest") or {}
        if not manifest:
            continue
        prims = {e.get("primitive") for e in manifest.get("elements", [])}
        all_legacy = prims <= LEGACY_COMPLETE_MASS_PRIMITIVES
        has_new_keys = ("mass_model" in manifest
                        or "required_validation_gates" in manifest)
        if all_legacy:
            n_legacy += 1
            if has_new_keys:
                legacy_offenders.append((design_id, "new keys present"))
            if required_validation_gates(manifest) != ():
                legacy_offenders.append((design_id, "snapshot not empty"))
            if manifest.get("total_mass_kg") in (None, 0):
                legacy_offenders.append(
                    (design_id, "stored total is null/zero"))
        else:
            n_nonlegacy += 1
            # No silent validation bypass: an incomplete-capable design
            # must carry its truth keys explicitly.
            if "mass_model" not in manifest:
                key_offenders.append((design_id, "non-legacy without "
                                                 "mass_model"))
            if "required_validation_gates" not in manifest:
                key_offenders.append((design_id, "non-legacy without "
                                                 "required_validation_gates"))
    print("  designs: %d all-legacy, %d non-legacy (incomplete-capable)"
          % (n_legacy, n_nonlegacy))
    ok("6", "every ALL-LEGACY manifest is legacy-clean (%d checked)"
       % n_legacy, not legacy_offenders, str(legacy_offenders[:3]))
    ok("6", "new keys <=> non-legacy primitive, both directions "
       "(%d non-legacy checked)" % n_nonlegacy,
       not key_offenders, str(key_offenders[:3]))


def frontend_truth() -> None:
    section("7 frontend truth allowlist")
    client = REPO / "frontend" / "src" / "api" / "client.ts"
    inspector = REPO / "frontend" / "src" / "workspace" / "InspectorPanel.tsx"
    ctext = client.read_text(encoding="utf-8")
    itext = inspector.read_text(encoding="utf-8")
    ok("7", "client.ts exports the MassModel type",
       "export interface MassModel" in ctext)
    ok("7", "manifest total typed number | null",
       "total_mass_kg: number | null" in ctext)
    ok("7", "InspectorPanel labels the incomplete basis",
       "missing_mass_inputs" in itext and "(incomplete)" in itext)
    ok("7", "the 'real mass' phrase is gone",
       "real mass" not in itext)


def hermeticity_and_scan(before: tuple) -> None:
    section("8 hermeticity + $0 static scan")
    after = _fingerprint()
    ok("8", "real DB byte-identical", before[0] == after[0],
       str(after[0])[:12] if after[0] else "no DB on this checkout")
    ok("8", "data/exports unchanged", before[1] == after[1],
       "%d files" % len(after[1]))
    forbidden = tuple("import " + m for m in
                      ("requests", "httpx", "urllib", "socket")) + \
        tuple(p + " " + m for p in ("from", "import")
              for m in ("anthropic", "openai"))
    for path in (BACKEND / "geometry" / "mass_model.py",
                 BACKEND / "geometry" / "freeform_validation.py",
                 Path(__file__).resolve()):
        code = "\n".join(ln for ln in
                         path.read_text(encoding="utf-8").splitlines()
                         if not ln.lstrip().startswith("#"))
        bad = [t for t in forbidden if t in code]
        ok("8", "%s network/provider-free" % path.name, not bad,
           ", ".join(bad))


def _fingerprint() -> tuple:
    db = None
    for candidate in (Path("/app/data/luxuryform.db"),
                      REPO / "data" / "luxuryform.db"):
        if candidate.exists():
            db = candidate
            break
    db_sha = sha256_file(db) if db else None
    exports = None
    for candidate in (Path("/app/data/exports"), REPO / "data" / "exports"):
        if candidate.exists():
            exports = candidate
            break
    listing = tuple(sorted((p.name, p.stat().st_size)
                           for p in exports.rglob("*") if p.is_file())) \
        if exports else ()
    return db_sha, listing


def main() -> int:
    print("=" * 72)
    print("FF-A1 AUTO GATE -- incomplete-mass truth + freeform integrity "
          "(ADR-065)")
    print("repo root: %s" % REPO)
    print("=" * 72)
    before = _fingerprint()
    census()
    behavioral()
    legacy_compat()
    frontend_truth()
    hermeticity_and_scan(before)

    print("\n" + "=" * 72)
    print("sections run:     %s" % "; ".join(SECTIONS_RUN))
    print("sections skipped: %s" % ("; ".join(SECTIONS_SKIPPED) or "none"))
    passed = sum(1 for c in CHECKS if c)
    failed = len(CHECKS) - passed
    if failed:
        print("FAIL -- %d of %d checks failed." % (failed, len(CHECKS)))
        print("=" * 72)
        return 1
    print("PASS -- all %d checks in every section that ran passed at $0, "
          "offline, with no AI call and no production data touched."
          % passed)
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
