"""MS-A1 auto gate — the perforated_screen mesh-class primitive (ADR-071).

$0, offline, non-interactive, hermetic. Sections:

  [1] Registry truth + declarations — the registry is exactly the twelve
      (the exact set lives HERE, roster-gate style, with the D-10-frozen
      reason for the 11 -> 12 growth) and the primitive's declarations
      (316L-only, planar_grid segmentation, stack_on parenting, the
      measured hole cap, the recorded curvature judgements).
  [2] Refusal truth: every signed floor refuses loudly through validate()
      with the real computed numbers in the message — ligament vs sheet,
      hole size vs sheet, the margin-fit rule (axis named), the 1500-hole
      build cap (nx/ny/total printed), the 5 x t curvature floor (named
      as the rolled-sheet forming judgement), the 270-degree wrap limit,
      the stock sheet breach (dims read from materials.yaml), and the
      316L-only rule (every other material refused by name).
  [3] Determinism: the default fixture panel built in TWO separate
      processes; both PIDs and both STEP sha256 digests printed.
  [4] Integrity: the built 42-hole solid passes the production
      freeform-integrity stack — status pass, one body, genus equal to
      the hole count, mass = volume x density within 0.5%.
  [5] Build-time bound: a realistic 1421-hole panel builds well under
      the 120 s sandbox timeout (assert < 90 s, measured time printed).
  [6] End-to-end on a THROWAWAY database: a 316L plinth + screen
      stack_on through the spec mapper and the assembler -> one fused
      watertight body with COMPLETE mass; the same plan persisted
      through the real API; a costing BOM computes; the export
      classification verdict is printed and is never REFUSED.
  [7] Mapper/Designer reachability: every registry key of the primitive
      is reachable by a spec-level name (ADR-069 anti-drift, proven FROM
      the registry) and the Designer prompt index mentions
      perforated_screen exactly once.
  [8] Negative: a massing spec naming perforated_screen with a non-316L
      material is refused at the Designer boundary by name.
  [9] Hermeticity + $0: the real DB and data/exports untouched, no
      network/provider imports, no reference JPG in the image tree.

Never a Council call, never a render, never AI-loop code.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

CHECKS: list[bool] = []
SECTIONS_RUN: list[str] = []
SECTIONS_SKIPPED: list[str] = []


def section(title: str) -> None:
    SECTIONS_RUN.append(title.split()[0])
    print("\n[%s]" % title)
    print("-" * 72)


def ok(sec: str, label: str, cond: bool, detail: str = "") -> None:
    CHECKS.append(bool(cond))
    mark = "PASS" if cond else "FAIL"
    line = "  [%s] %-58s %s" % (sec, label, mark)
    if detail:
        line += "  (%s)" % detail
    print(line)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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


#: Default flat fixture (748 holes) — the determinism acceptance panel.
DEFAULTS = {
    "height_mm": 900,
    "arc_width_mm": 1400,
    "sheet_thickness_mm": 6,
    "hole_shape": "circle",
    "hole_pitch_mm": 40,
    "hole_size_mm": 20,
    "edge_margin_mm": 25,
    "material_id": "stainless_316l_sheet",
}

#: Small fixture (42 holes) for the integrity-stack run — the
#: self-interference check is quadratic in the face count.
SMALL = {
    "height_mm": 500,
    "arc_width_mm": 600,
    "sheet_thickness_mm": 6,
    "hole_shape": "circle",
    "hole_pitch_mm": 80,
    "hole_size_mm": 30,
    "edge_margin_mm": 25,
    "material_id": "stainless_316l_sheet",
}

#: The MS-A1 massing spec: a 316L plinth with a perforated screen
#: stacked on it (ADR-069 spec form; the same shape the slice test uses).
MSA1_SPEC = {
    "meta": {"seed": 7},
    "fabrication": {"max_lift_kg": 5000,
                    "max_module_m": {"x": 4.0, "y": 4.0, "z": 4.0}},
    "massing": {
        "elements": [
            {
                "element_id": "p1",
                "primitive": "plinth",
                "parameters": {
                    "top_diameter": {"value": 900, "unit": "mm"},
                    "height": {"value": 300, "unit": "mm"},
                },
                "material_id": "stainless_316l_sheet",
                "position": {"x_m": 0, "y_m": 0, "z_m": 0},
            },
            {
                "element_id": "scr1",
                "primitive": "perforated_screen",
                "parameters": {
                    "height": {"value": 600, "unit": "mm"},
                    "width": {"value": 800, "unit": "mm"},
                    "sheet_thickness": {"value": 6, "unit": "mm"},
                    "hole_shape": "circle",
                    "hole_pitch": {"value": 60, "unit": "mm"},
                    "hole_size": {"value": 30, "unit": "mm"},
                    "edge_margin": {"value": 25, "unit": "mm"},
                },
                "material_id": "stainless_316l_sheet",
                "position": {"x_m": 0, "y_m": 0, "z_m": 0.3},
                "parent_id": "p1",
            },
        ]
    },
}


# ---------------------------------------------------------------------------
# [1] registry truth + declarations
# ---------------------------------------------------------------------------

def registry_truth() -> None:
    section("1 registry truth + declarations")
    from app.geometry.primitives import PRIMITIVES, perforated_screen as ps

    # D-10-frozen: the registry's exact set lives in exactly ONE roster
    # gate (the FF-A2-established convention), so widening the library
    # fails exactly one check by design; MS-A1 (mesh-class slice A,
    # ADR-071) widened the library to twelve with perforated_screen and
    # moved the set here from gate_ffa2_auto, which carried it for the
    # eleven of the FF-A2 era.
    expected_twelve = {
        "tiered_cascade", "basin_round", "plinth", "sculptural_column",
        "basin_rect", "stepped_monolith", "water_wall", "torus_ring",
        "blade_fin_array", "lotus_petal_array", "freeform_loop",
        "perforated_screen",
    }
    print("  registered: %s" % ", ".join(sorted(PRIMITIVES)))
    # D-10-frozen: the twelve-id exact set above is this gate's roster
    # contract for MS-A1 — the next widening slice moves it with its ADR,
    # exactly as ADR-071 moved it from the FF-A2 eleven.
    ok("1", "registry is exactly the twelve (exact set lives HERE)",
       set(PRIMITIVES) == expected_twelve)
    ok("1", "316L-only declaration",
       ps.SUPPORTED_MATERIAL == "stainless_316l_sheet")
    ok("1", "declares stack_on parenting, not insert",
       ps.CAN_PARENT_STACK is True and ps.CAN_PARENT_INSERT is False)
    ok("1", "segmentation mode is planar_grid (a continuous mass)",
       ps.SEGMENTATION_MODE == "planar_grid")
    ok("1", "complete mass: no INCOMPLETE_MASS_INPUTS declaration",
       not getattr(ps, "INCOMPLETE_MASS_INPUTS", ()))
    # The 1500 cap is a MEASURED build-time/render-load bound (D-25
    # context), the module's recorded constant — asserted against the
    # module, never re-typed from memory.
    ok("1", "MAX_TOTAL_HOLES is the recorded 1500 bound",
       ps.MAX_TOTAL_HOLES == 1500, "module constant")
    ok("1", "curvature judgements are the recorded values",
       ps.MIN_CURVATURE_TIMES_THICKNESS == 5.0
       and ps.MAX_ARC_WRAP_FRACTION == 0.75)
    ok("1", "hole shapes are the declared vocabulary",
       tuple(ps.HOLE_SHAPES) == ("circle", "hexagon"))
    print("  recorded parameter table:")
    for name in sorted(ps.PARAMETERS):
        spec = ps.PARAMETERS[name]
        print("    %-24s default=%-8s min=%-6s max=%-6s"
              % (name, spec["default"], spec["min"], spec["max"]))
    ok("1", "nine registry keys (8 scalars + material_id)",
       len(ps.PARAMETERS) == 9)


# ---------------------------------------------------------------------------
# [2] refusal truth
# ---------------------------------------------------------------------------

def refusal_truth() -> None:
    section("2 refusal truth: every signed floor refuses with real numbers")
    from app.geometry.primitives import perforated_screen as ps
    from app.geometry.primitives.base import (
        ConstraintViolation, load_materials)

    def refuses(needle: str, **over) -> tuple[bool, str]:
        raw = dict(DEFAULTS)
        raw.update(over)
        try:
            ps.validate(raw, None)
            return False, "ACCEPTED"
        except ConstraintViolation as exc:
            return needle in "; ".join(exc.violations), "; ".join(
                exc.violations)

    got, msg = refuses("ligament", hole_pitch_mm=20, hole_size_mm=16)
    print("    ligament: %s" % msg)
    ok("2", "ligament < sheet refuses (pitch 20 - size 16 = 4 < t 6)", got)
    got, msg = refuses("hole_size_mm=4", hole_size_mm=4)
    print("    hole size: %s" % msg)
    ok("2", "hole_size 4 < sheet 6 refuses (min_feature = wall)", got)

    # The static ranges guarantee the margin-fit rule can only fire on a
    # range edit — pin the message via a construct-bypassed model, the
    # freeform_loop defence-in-depth precedent.
    p = ps.PerforatedScreenParams.model_construct(
        **dict(DEFAULTS, arc_width_mm=300, hole_size_mm=200,
               edge_margin_mm=100))
    msgs = ps._margin_fit_violations(p)
    joined = "; ".join(msgs)
    print("    margin fit: %s" % joined[:110])
    ok("2", "grid-doesn't-fit margin refuses naming the X axis",
       any("arc width (X)" in m for m in msgs) and "100" in joined)

    got, msg = refuses("43216", arc_width_mm=3000, height_mm=1500,
                       hole_pitch_mm=10, hole_size_mm=8, edge_margin_mm=25)
    print("    hole cap: %s" % msg)
    ok("2", "holes cap refuses printing nx 296 x ny 146 = 43216 > 1500",
       got and "296" in msg and "146" in msg)

    got, msg = refuses("471", curvature_radius_mm=100, arc_width_mm=1000,
                       height_mm=600)
    print("    wrap: %s" % msg)
    ok("2", "wrap over 270 deg refuses (2π x 100 x 0.75 = 471 mm)", got)

    # Same defence-in-depth precedent for the 5 x t curvature floor:
    # the ranges (R min 100 = 5 x t max 20) guarantee it, so exercise
    # the runtime rule through a construct-bypassed model.
    p = ps.PerforatedScreenParams.model_construct(
        **dict(SMALL, arc_width_mm=200, curvature_radius_mm=50,
               sheet_thickness_mm=20))
    msgs = ps._curvature_violations(p)
    joined = "; ".join(msgs)
    print("    curvature: %s" % joined[:110])
    ok("2", "radius < 5 x t refuses, judgement floor named as such",
       any("rolled-sheet forming judgement" in m and "50" in m and "100" in m
           for m in msgs))

    mat = load_materials()["stainless_316l_sheet"]
    stock = mat.stock_size_mm
    p = ps.PerforatedScreenParams.model_construct(
        **dict(DEFAULTS, arc_width_mm=stock.length + 200))
    msg = ps._stock_violation(p, mat)
    print("    stock: %s" % (msg or "<none>")[:110])
    ok("2", "stock breach refuses naming the material's real stock dims",
       msg is not None
       and str(int(stock.length)) in msg and str(int(stock.width)) in msg
       and str(int(stock.length) + 200) in msg)

    for mat_id in ("basalt_slab", "bronze_cast"):
        got, msg = refuses("only 'stainless_316l_sheet'", material_id=mat_id)
        print("    %s -> %s" % (mat_id, msg))
        ok("2", "%s refused by name as UNBUILT" % mat_id,
           got and "UNBUILT" in msg)


# ---------------------------------------------------------------------------
# [3] determinism: two separate processes, byte-identical STEP
# ---------------------------------------------------------------------------

BUILD_SNIPPET = r"""
import json, os, sys
from app.geometry.primitives import perforated_screen as ps
from app.geometry.exporters import export_step
from app.geometry.kernel import step_timestamp_for
params = json.loads(open(sys.argv[1]).read())
p = ps.validate(params, None)
solid = ps.build(p)
sha = export_step(solid, sys.argv[2], step_timestamp_for(8))
print("pid=%d sha256=%s" % (os.getpid(), sha))
"""


def determinism() -> None:
    section("3 determinism: two separate processes, byte-identical STEP")
    results = []
    with tempfile.TemporaryDirectory() as td:
        params_path = Path(td) / "msa1_params.json"
        params_path.write_text(json.dumps(DEFAULTS))
        for i in (1, 2):
            out = str(Path(td) / ("msa1_%d.step" % i))
            proc = subprocess.run(
                [sys.executable, "-c", BUILD_SNIPPET, str(params_path),
                 out],
                capture_output=True, text=True, timeout=900)
            line = (proc.stdout or "").strip().splitlines()
            line = line[-1] if line else ""
            print("    run %d: %s (exit %d)" % (i, line, proc.returncode))
            results.append((proc.returncode, line))
    ok("3", "both processes built and exported", all(
        r[0] == 0 and "sha256=" in r[1] for r in results))
    if all("sha256=" in r[1] for r in results):
        pids = [r[1].split()[0] for r in results]
        shas = [r[1].split("sha256=")[1] for r in results]
        ok("3", "two distinct PIDs", pids[0] != pids[1],
           "%s vs %s" % (pids[0], pids[1]))
        ok("3", "STEP byte-identical across processes", shas[0] == shas[1],
           shas[0][:16])
        print("    pinned STEP sha256: %s" % shas[0])


# ---------------------------------------------------------------------------
# [4] integrity: the built 42-hole solid through the production stack
# ---------------------------------------------------------------------------

def integrity() -> None:
    section("4 integrity: 42-hole solid through the production stack")
    from app.geometry.freeform_validation import run_freeform_integrity
    from app.geometry.primitives import perforated_screen as ps
    from app.geometry.primitives.base import load_materials

    p = ps.validate(dict(SMALL), None)
    solid = ps.build(p)
    report = run_freeform_integrity(solid)
    by = {c["check"]: c for c in report["checks"]}
    for c in report["checks"]:
        print("    %-44s %-11s value=%s" % (c["check"], c["status"],
                                            str(c["value"])[:44]))
    ok("4", "integrity stack status is pass", report["status"] == "pass")
    ok("4", "body_count == 1 (one pierced sheet)",
       by["body_count"]["value"] == 1)
    nx, ny = ps.grid_counts(p)
    ok("4", "genus == the hole count (%d x %d = %d)"
       % (nx, ny, nx * ny),
       by["genus"]["value"] == nx * ny, "genus %s" % by["genus"]["value"])
    density = load_materials()["stainless_316l_sheet"].density_kg_per_m3
    vol_mm3 = float(solid.volume)
    mass_kg = vol_mm3 * 1e-9 * density
    gross_kg = (p.arc_width_mm * p.height_mm * p.sheet_thickness_mm
                * 1e-9 * density)
    print("    volume %.1f mm3 -> mass %.3f kg (gross sheet %.3f kg)"
          % (vol_mm3, mass_kg, gross_kg))
    ok("4", "mass == volume x 8000 within 0.5%",
       0 < mass_kg < gross_kg
       and abs(mass_kg - vol_mm3 * 1e-9 * 8000.0) / mass_kg < 0.005,
       "%.3f kg at density %s" % (mass_kg, density))


# ---------------------------------------------------------------------------
# [5] build-time bound
# ---------------------------------------------------------------------------

def build_time_bound() -> None:
    section("5 build-time bound: the 1421-hole realistic panel")
    from app.geometry.primitives import perforated_screen as ps

    p = ps.validate(dict(DEFAULTS, arc_width_mm=2000, height_mm=1200), None)
    nx, ny = ps.grid_counts(p)
    total = nx * ny
    print("    panel %g x %g mm, pitch %g: nx %d x ny %d = %d holes"
          % (p.arc_width_mm, p.height_mm, p.hole_pitch_mm, nx, ny, total))
    ok("5", "the panel is a realistic ~1400-hole grid (1400-2200 mm)",
       1400 <= p.arc_width_mm <= 2200 and total >= 1400,
       "%d holes" % total)
    t0 = time.monotonic()
    solid = ps.build(p)
    elapsed = time.monotonic() - t0
    print("    built in %.1f s (sandbox timeout 120 s)" % elapsed)
    ok("5", "builds in well under the timeout", elapsed < 90.0,
       "%.1f s < 90 s" % elapsed)
    ok("5", "one watertight body out of the single boolean",
       len(solid.solids()) == 1 and float(solid.volume) > 0.0)


# ---------------------------------------------------------------------------
# [6] end-to-end on a throwaway DB
# ---------------------------------------------------------------------------

def end_to_end() -> None:
    section("6 end-to-end: plinth + screen stack, BOM, export verdict "
            "(throwaway DB)")
    import importlib
    from app.geometry import registry

    plan = registry.assembly_plan_from_spec(MSA1_SPEC)
    limits = registry.fabrication_limits_from_spec(MSA1_SPEC)
    by_id = {e["element_id"]: e for e in plan}
    ok("6", "mapper gives the screen a stack_on joint to the plinth",
       by_id["scr1"].get("joint") == {"type": "stack_on", "parent": "p1"})
    t0 = time.perf_counter()
    solid, manifest = registry.assemble(plan, seed=7, fabrication=limits)
    print("    assembled in %.1f s" % (time.perf_counter() - t0))
    ok("6", "one fused watertight body (body_count_brep == 1)",
       manifest["body_count_brep"] == 1
       and len(solid.solids()) == 1)
    vc = manifest["volume_conservation"]
    ok("6", "volume conservation within tolerance",
       vc["delta_pct"] <= vc["tolerance_pct"],
       "delta %.6f%% (tol %s)" % (vc["delta_pct"], vc["tolerance_pct"]))
    screen = next(e for e in manifest["elements"]
                  if e["element_id"] == "scr1")
    ok("6", "screen mass_model COMPLETE, no missing inputs",
       screen["mass_model"]["mass_complete"] is True
       and screen["mass_model"]["missing_mass_inputs"] == [])
    ok("6", "screen mass == volume x 8000 within 0.5%",
       abs(screen["mass_kg"] - screen["volume_mm3"] * 1e-9 * 8000.0)
       / screen["mass_kg"] < 0.005,
       "%.3f kg" % screen["mass_kg"])
    ok("6", "assembly total_mass_kg is a real number (complete mass)",
       manifest["total_mass_kg"] is not None
       and manifest["total_mass_kg"] > 0.0,
       "%.3f kg" % (manifest["total_mass_kg"] or 0.0))

    # ignore_cleanup_errors: on Windows a SQLite connection from the API
    # run can outlive the reset and hold the throwaway DB open for a
    # moment; the directory is %TEMP% garbage either way.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        old_db = os.environ.get("LUXURYFORM_DB")
        old_data = os.environ.get("LUXURYFORM_DATA_DIR")
        os.environ["LUXURYFORM_DB"] = str(Path(td) / "gate_msa1.db")
        os.environ["LUXURYFORM_DATA_DIR"] = str(Path(td) / "data")
        try:
            from app.db.database import reset_default_db
            reset_default_db()
            from fastapi.testclient import TestClient
            from app.main import app

            with TestClient(app) as client:
                resp = client.post("/api/geometry/assembly/build", json={
                    "seed": 7, "fabrication": limits, "elements": plan})
                ok("6", "plan builds and persists through the real API",
                   resp.status_code == 200, "HTTP %d" % resp.status_code)
                body = resp.json()
                design_id = body["design_id"]
                manifest = body["manifest"]
                ok("6", "persisted manifest total_mass_kg is real",
                   manifest["total_mass_kg"] is not None
                   and manifest["total_mass_kg"] > 0.0)
                els = {e["element_id"]: e for e in manifest["elements"]}
                # Production completeness semantics: the plinth is a frozen
                # legacy complete-mass primitive (no mass_model block by
                # design); the screen MUST carry an explicit complete block.
                from app.geometry.mass_model import (
                    assembly_mass_truth, element_mass_truth)
                truths = {eid: element_mass_truth(e) for eid, e in
                          els.items()}
                ok("6", "every element COMPLETE (legacy plinth implicit, "
                        "screen explicit)",
                   all(t.mass_complete for t in truths.values())
                   and els["scr1"]["mass_model"]["mass_complete"] is True,
                   ", ".join("%s=%s" % (eid, t.mass_complete)
                             for eid, t in sorted(truths.items())))
                ok("6", "assembly mass truth COMPLETE with the manifest total",
                   assembly_mass_truth(manifest).mass_complete
                   and abs(assembly_mass_truth(manifest).total_mass_kg
                           - manifest["total_mass_kg"])
                   / manifest["total_mass_kg"] < 1e-6,
                   "truth %.6f vs manifest %.6f" % (
                       assembly_mass_truth(manifest).total_mass_kg,
                       manifest["total_mass_kg"]))

                resp = client.get(
                    "/api/geometry/assembly/%s/manifest" % design_id)
                ok("6", "manifest round-trips from the throwaway DB",
                   resp.status_code == 200
                   and resp.json()["manifest"]["total_mass_kg"]
                   == manifest["total_mass_kg"])

                resp = client.get("/api/costing/bom/%s" % design_id)
                ok("6", "costing BOM responds (complete mass, not the 409 "
                        "incomplete_mass refusal)",
                   resp.status_code == 200, "HTTP %d" % resp.status_code)
                if resp.status_code == 200:
                    bom = resp.json()
                    print("    BOM: %d lines, material %s, complete=%s, "
                          "missing rates=%d, not_computable=%d, total=%s"
                          % (len(bom["lines"]), bom["material_id"],
                             bom["complete"], len(bom["missing_rates"]),
                             len(bom["not_computable"]),
                             bom["totals"]["total_usd"]))
                    ok("6", "BOM is priced for stainless_316l_sheet with "
                            "driver-backed lines",
                       bom["material_id"] == "stainless_316l_sheet"
                       and len(bom["lines"]) > 0)
                    # The rate card is unconfigured by design (every
                    # amount is null in costing.yaml — gate_costing_auto
                    # pins that the real BOM is incomplete with NO
                    # total). The honest MS-A1 verdict: the COMPLETE
                    # mass reaches the rate engine (no incomplete_mass
                    # 409) and every line names its blocker.
                    ok("6", "BOM honestly rate-incomplete: no total while "
                              "the rate card is unconfigured",
                       bom["complete"] is False
                       and bom["totals"]["total_usd"] is None,
                       "complete=%s total=%s"
                       % (bom["complete"], bom["totals"]["total_usd"]))
                    ok("6", "every BOM line carries an honest status and "
                            "a named blocker",
                       all(ln["status"] in ("computed", "missing_rate",
                                            "not_computable",
                                            "not_applicable")
                           and (ln["status"] == "computed" or ln["blocker"])
                           for ln in bom["lines"]))

                resp = client.post(
                    "/api/geometry/assembly/%s/exports" % design_id)
                verdict = resp.json().get("package_class") \
                    if resp.status_code == 200 else "HTTP %d" % resp.status_code
                print("    export classification verdict: %s" % verdict)
                ok("6", "export classification is the honest non-REFUSED "
                        "verdict for a complete-mass assembly",
                   resp.status_code == 200
                   and verdict in ("clean", "pre_fabrication"))
                zresp = client.get(
                    "/api/geometry/assembly/%s/luxexchange.zip" % design_id)
                ok("6", "the sealed package downloads",
                   zresp.status_code == 200,
                   "%d bytes" % len(zresp.content))
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


# ---------------------------------------------------------------------------
# [7] mapper / Designer reachability
# ---------------------------------------------------------------------------

def mapper_designer() -> None:
    section("7 mapper + Designer reachability (ADR-069 anti-drift)")
    from app.council.prompts import primitive_index_surface
    from app.geometry.primitives import perforated_screen as ps
    from app.geometry.spec_mapper import spec_aliases_for

    aliases = spec_aliases_for("perforated_screen")
    dangling = sorted(set(aliases.values()) - set(ps.PARAMETERS))
    ok("7", "no alias dangles (every target is a registry key)", not dangling,
       ", ".join(dangling) or "%d aliases" % len(aliases))
    unreachable = [k for k in ps.PARAMETERS if k != "material_id"
                   and k not in aliases.values()]
    ok("7", "every registry key reachable by a spec-level name",
       not unreachable, ", ".join(unreachable) or "all %d keys"
       % (len(ps.PARAMETERS) - 1))

    text = primitive_index_surface()
    n = text.count("perforated_screen")
    start = text.index("- perforated_screen:")
    rest = text[start + 1:]
    end = rest.find("\n- ")
    block = rest if end == -1 else rest[:end]
    print("    printed perforated_screen block:")
    for ln in block.splitlines():
        print("    | " + ln)
    ok("7", "the Designer index mentions perforated_screen exactly once",
       n == 1, "%d occurrence(s)" % n)


# ---------------------------------------------------------------------------
# [8] negative: non-316L material refused at the Designer boundary
# ---------------------------------------------------------------------------

def negatives() -> None:
    section("8 negative: non-316L screen refused at the Designer boundary")
    import copy

    from app.council.orchestrator import _validate_live_primitives

    wrong = copy.deepcopy(MSA1_SPEC)
    wrong["massing"]["elements"][1]["material_id"] = "basalt_slab"
    wrong["massing"]["elements"][1]["parameters"]["material_id"] = \
        "basalt_slab"
    errs = _validate_live_primitives(wrong)
    for e in errs:
        print("    refusal: %s" % e[:110])
    ok("8", "basalt screen refused at the boundary naming 316L",
       any("only 'stainless_316l_sheet'" in e for e in errs),
       errs[0][:90] if errs else "accepted")


# ---------------------------------------------------------------------------
# [9] hermeticity + $0
# ---------------------------------------------------------------------------

def hermeticity(before: tuple) -> None:
    section("9 hermeticity + $0 static scan")
    after = _fingerprint()
    ok("9", "real DB byte-identical", before[0] == after[0],
       str(after[0])[:12] if after[0] else "no DB on this checkout")
    ok("9", "data/exports unchanged", before[1] == after[1],
       "%d files" % len(after[1]))
    forbidden = tuple("import " + m for m in
                      ("requests", "httpx", "socket")) + \
        tuple(p + " " + m for p in ("from", "import")
              for m in ("anthropic", "openai"))
    from app.geometry.primitives import perforated_screen as ps
    for path in (Path(ps.__file__), Path(__file__).resolve()):
        code = "\n".join(ln for ln in
                         path.read_text(encoding="utf-8").splitlines()
                         if not ln.lstrip().startswith("#"))
        bad = [t for t in forbidden if t in code]
        ok("9", "%s network/provider-free" % path.name, not bad,
           ", ".join(bad))
    jpgs = list((REPO / "briefs").rglob("*.jpg")) if \
        (REPO / "briefs").exists() else []
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 72)
    print("MS-A1 AUTO GATE -- perforated_screen mesh-class primitive "
          "(ADR-071)")
    print("repo root: %s" % REPO)
    print("=" * 72)
    before = _fingerprint()
    registry_truth()
    refusal_truth()
    determinism()
    integrity()
    build_time_bound()
    end_to_end()
    mapper_designer()
    negatives()
    hermeticity(before)

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
