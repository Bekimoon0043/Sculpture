"""SC-A1 auto gate — the crescent_ring sculpture primitive (ADR-072).

$0, offline, non-interactive, hermetic. Sections:

  [1] Registry truth + declarations — the registry is exactly the
      thirteen (the exact set lives HERE, roster-gate style, with the
      D-10-frozen reason for the 12 -> 13 growth), the two-material
      allowed set (stainless_316l_cast NEW in materials.yaml /
      stainless_316l_sheet) and the primitive's recorded constants.
  [2] Refusal truth: every signed floor refuses loudly through
      validate() with the real computed numbers in the message — a
      non-allowed material refused by name, the tube gauge outside the
      CHOSEN material's wall envelope, the oval >= tube squash rule,
      the arc_span range breach, the NADIR rule (an arc that misses
      azimuth 270 deg refused naming the arc numbers), and the derived
      `height` key refused naming the relationship.
  [3] Determinism: the photo replica (R=800, tube=350, span=300, gap=0,
      cast) built in TWO separate processes; both PIDs and both STEP
      sha256 digests printed.
  [4] Integrity: the photo replica AND a slim crescent (R=1000,
      tube=120, span=330) pass the production freeform-integrity stack
      (status pass, one body) and sit within 2% of analytic
      torus-segment theory.
  [5] Demo fidelity: the photo replica measures 1950 mm tall x 1950 mm
      long x 350 mm deep with min.Z == 0 (relationships pinned and
      printed); the build-time bound is asserted (< 60 s, measured
      printed, expected < 1 s uncontended).
  [6] End-to-end on a THROWAWAY database: a 316L-cast plinth +
      crescent_ring stack_on through the spec mapper and the assembler
      -> one fused watertight body with COMPLETE mass; the same plan
      persisted through the real API; a costing BOM computes honestly
      rate-incomplete; the export classification verdict is printed and
      is never REFUSED.
  [7] Mapper/Designer reachability: every registry key of the primitive
      is reachable by a spec-level name (ADR-069 anti-drift, proven FROM
      the registry); a spec `height` key is refused NAMING the derived
      relationship; the Designer prompt index mentions crescent_ring
      exactly once.
  [8] Negative: a massing spec naming crescent_ring with basalt_slab is
      refused at the Designer boundary by name.
  [9] Hermeticity + $0: the real DB and data/exports untouched, no
      network/provider imports, no TRACKED reference JPG.

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


#: The photo-replica demo fixture — the client reference piece read at
#: photo precision (0.4 m deep x 1.9 m tall x 2.0 m long).
PHOTO = {
    "centerline_radius_mm": 800,
    "tube_diameter_mm": 350,
    "arc_span_deg": 300,
    "gap_azimuth_deg": 0,
    "material_id": "stainless_316l_cast",
}

#: Slim full-ish crescent fixture for the second integrity run.
SLIM = {
    "centerline_radius_mm": 1000,
    "tube_diameter_mm": 120,
    "arc_span_deg": 330,
    "gap_azimuth_deg": 0,
    "material_id": "stainless_316l_cast",
}

#: Small 90 deg-span fixture for the NADIR-rule refusal (swept arc
#: [110, 200] misses azimuth 270 deg).
QUARTER = {
    "centerline_radius_mm": 400,
    "tube_diameter_mm": 80,
    "arc_span_deg": 90,
    "gap_azimuth_deg": 0,
    "material_id": "stainless_316l_cast",
}

#: The SC-A1 massing spec: a 316L-cast plinth with a crescent stacked on
#: it (ADR-069 spec form; the same shape the slice test uses). BOTH
#: elements carry stainless_316l_cast: the BOM prices one material and
#: a mixed-material assembly is refused by name (routes_costing).
SCA1_SPEC = {
    "meta": {"seed": 7},
    "fabrication": {"max_lift_kg": 20000,
                    "max_module_m": {"x": 4.0, "y": 4.0, "z": 4.0}},
    "massing": {
        "elements": [
            {
                "element_id": "p1",
                "primitive": "plinth",
                "parameters": {
                    "top_diameter": {"value": 1200, "unit": "mm"},
                    "height": {"value": 300, "unit": "mm"},
                },
                "material_id": "stainless_316l_cast",
                "position": {"x_m": 0, "y_m": 0, "z_m": 0},
            },
            {
                "element_id": "cre1",
                "primitive": "crescent_ring",
                "parameters": {
                    "radius": {"value": 800, "unit": "mm"},
                    "tube": {"value": 350, "unit": "mm"},
                    "span": {"value": 300, "unit": "deg"},
                    "gap": {"value": 0, "unit": "deg"},
                },
                "material_id": "stainless_316l_cast",
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
    from app.geometry.primitives import PRIMITIVES, crescent_ring as cr
    from app.geometry.primitives.base import load_materials

    # D-10-frozen: the registry's exact set lives in exactly ONE roster
    # gate (the FF-A2-established convention), so widening the library
    # fails exactly one check by design; SC-A1 (ADR-072) widened the
    # library 12 -> 13 with crescent_ring and moved the set here from
    # gate_msa1_auto, which carried it for the twelve of the MS-A1 era.
    expected_thirteen = {
        "tiered_cascade", "basin_round", "plinth", "sculptural_column",
        "basin_rect", "stepped_monolith", "water_wall", "torus_ring",
        "blade_fin_array", "lotus_petal_array", "freeform_loop",
        "perforated_screen", "crescent_ring",
    }
    print("  registered: %s" % ", ".join(sorted(PRIMITIVES)))
    # D-10-frozen: the thirteen-id exact set above is this gate's roster
    # contract for SC-A1 — the next widening slice moves it with its ADR,
    # exactly as ADR-072 moved it from the MS-A1 twelve.
    ok("1", "registry is exactly the thirteen (exact set lives HERE)",
       set(PRIMITIVES) == expected_thirteen)
    ok("1", "allowed set is cast 316L + formed heavy sheet 316L",
       tuple(cr.SUPPORTED_MATERIALS)
       == ("stainless_316l_cast", "stainless_316l_sheet"))
    ok("1", "cannot parent children (curved tube top, not a face)",
       cr.CAN_PARENT_STACK is False and cr.CAN_PARENT_INSERT is False)
    ok("1", "segmentation mode is planar_grid (a continuous mass)",
       cr.SEGMENTATION_MODE == "planar_grid")
    ok("1", "complete mass: no INCOMPLETE_MASS_INPUTS declaration",
       not getattr(cr, "INCOMPLETE_MASS_INPUTS", ()))
    ok("1", "volume-theory tolerance is the recorded 2% bound",
       cr.VOLUME_THEORY_TOLERANCE == 0.02, "module constant")
    ok("1", "nadir azimuth is the recorded 270 deg constant",
       cr.NADIR_AZIMUTH_DEG == 270.0, "module constant")
    mat = load_materials()["stainless_316l_cast"]
    ok("1", "stainless_316l_cast declared in materials.yaml (8000 kg/m3, "
            "wall 3..500, no stock sheet)",
       mat.density_kg_per_m3 == 8000 and mat.min_wall_mm == 3
       and mat.max_wall_mm == 500 and mat.stock_size_mm is None)
    print("  recorded parameter table:")
    for name in sorted(cr.PARAMETERS):
        spec = cr.PARAMETERS[name]
        print("    %-24s default=%-8s min=%-6s max=%-6s"
              % (name, spec["default"], spec["min"], spec["max"]))
    ok("1", "six registry keys (5 scalars + optional oval + material_id)",
       len(cr.PARAMETERS) == 6)


# ---------------------------------------------------------------------------
# [2] refusal truth
# ---------------------------------------------------------------------------

def refusal_truth() -> None:
    section("2 refusal truth: every signed floor refuses with real numbers")
    from app.geometry.primitives import crescent_ring as cr
    from app.geometry.primitives.base import (
        ConstraintViolation, check_wall_envelope, load_materials)

    def refuses(needle: str, base: dict | None = None, **over):
        raw = dict(base or PHOTO)
        raw.update(over)
        try:
            cr.validate(raw, None)
            return False, "ACCEPTED"
        except ConstraintViolation as exc:
            return needle in "; ".join(exc.violations), "; ".join(
                exc.violations)

    for mat_id in ("basalt_slab", "bronze_cast", "cast_concrete_c35_45"):
        got, msg = refuses("UNBUILT", material_id=mat_id)
        print("    %s -> %s" % (mat_id, msg[:110]))
        ok("2", "%s refused by name as UNBUILT" % mat_id,
           got and mat_id in msg and "stainless_316l_cast" in msg)

    # tube gauge outside the CHOSEN material's wall envelope: 350 mm
    # against the 316L SHEET ceiling (20 mm) — both numbers in the msg.
    got, msg = refuses("tube_diameter_mm=350", material_id="stainless_316l_sheet")
    print("    sheet envelope: %s" % msg[:110])
    ok("2", "tube 350 vs sheet envelope 3..20 refuses with both numbers",
       got and "20" in msg and "stainless_316l_sheet" in msg)

    # defence in depth, the perforated_screen precedent: the static
    # ranges (tube max 500 = cast max_wall 500) guarantee the cast
    # envelope floor, so pin the runtime message via a construct-bypassed
    # model (materials.yaml is the truth).
    mat = load_materials()["stainless_316l_cast"]
    p = cr.CrescentRingParams.model_construct(
        **dict(PHOTO, tube_diameter_mm=600))
    violations: list[str] = []
    check_wall_envelope("tube_diameter_mm", p.tube_diameter_mm,
                        "stainless_316l_cast", mat, violations)
    print("    cast envelope: %s" % "; ".join(violations)[:110])
    ok("2", "tube 600 > cast ceiling 500 refuses with both numbers",
       any("600" in v and "500" in v for v in violations))

    got, msg = refuses("squash", tube_depth_oval_mm=350)
    print("    oval: %s" % msg[:110])
    ok("2", "oval 350 >= tube 350 refuses (not a squash)",
       got and "tube_depth_oval_mm=350" in msg
       and "tube_diameter_mm 350" in msg)

    got, msg = refuses("arc_span_deg=89", arc_span_deg=89)
    print("    span low: %s" % msg[:110])
    ok("2", "arc_span 89 below range refuses naming the parameter and floor",
       got and "90" in msg)
    got, msg = refuses("arc_span_deg=331", arc_span_deg=331)
    print("    span high: %s" % msg[:110])
    ok("2", "arc_span 331 above range refuses naming the parameter and cap",
       got and "330" in msg)

    got, msg = refuses("nadir", base=QUARTER, gap_azimuth_deg=200)
    print("    nadir: %s" % msg[:140])
    ok("2", "arc missing azimuth 270 refuses naming the arc (110 -> 200)",
       got and "270" in msg and "110" in msg and "200" in msg)

    got, msg = refuses("DERIVED", height=1950)
    print("    height: %s" % msg[:140])
    ok("2", "spec height key refused naming the derived relationship",
       got and "2 x centerline_radius_mm + tube_diameter_mm" in msg)


# ---------------------------------------------------------------------------
# [3] determinism: two separate processes, byte-identical STEP
# ---------------------------------------------------------------------------

BUILD_SNIPPET = r"""
import json, os, sys
from app.geometry.primitives import crescent_ring as cr
from app.geometry.exporters import export_step
from app.geometry.kernel import step_timestamp_for
params = json.loads(open(sys.argv[1]).read())
p = cr.validate(params, None)
solid = cr.build(p)
sha = export_step(solid, sys.argv[2], step_timestamp_for(8))
print("pid=%d sha256=%s" % (os.getpid(), sha))
"""


def determinism() -> None:
    section("3 determinism: two separate processes, byte-identical STEP")
    results = []
    with tempfile.TemporaryDirectory() as td:
        params_path = Path(td) / "sca1_params.json"
        params_path.write_text(json.dumps(PHOTO))
        for i in (1, 2):
            out = str(Path(td) / ("sca1_%d.step" % i))
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
# [4] integrity: photo replica + slim crescent through the production stack
# ---------------------------------------------------------------------------

def integrity() -> None:
    section("4 integrity: photo + slim crescents through the production "
            "stack")
    from app.geometry.freeform_validation import run_freeform_integrity
    from app.geometry.primitives import crescent_ring as cr

    for label, raw in (("photo replica", PHOTO), ("slim crescent", SLIM)):
        p = cr.validate(dict(raw), None)
        solid = cr.build(p)
        report = run_freeform_integrity(solid)
        by = {c["check"]: c for c in report["checks"]}
        print("    %s: status=%s body_count=%s genus=%s" % (
            label, report["status"], by["body_count"]["value"],
            by["genus"]["value"]))
        ok("4", "%s: integrity stack status is pass" % label,
           report["status"] == "pass")
        ok("4", "%s: body_count == 1 (one swept solid)" % label,
           by["body_count"]["value"] == 1)
        ok("4", "%s: genus == 0 (a partial torus, no through-opening)"
           % label, by["genus"]["value"] == 0)
        volume = float(solid.volume)
        theory = cr.swept_volume_mm3(p)
        rel = abs(volume - theory) / theory
        print("    %s: volume %.0f mm3 vs torus-segment theory %.0f mm3 "
              "(rel dev %.2e)" % (label, volume, theory, rel))
        ok("4", "%s: volume within 2%% of analytic torus-segment theory"
           % label, rel <= 0.02, "rel dev %.2e" % rel)


# ---------------------------------------------------------------------------
# [5] demo fidelity: the photo replica's measured envelope + build bound
# ---------------------------------------------------------------------------

def demo_fidelity() -> None:
    section("5 demo fidelity: photo-replica envelope + build-time bound")
    from app.geometry.primitives import crescent_ring as cr

    p = cr.validate(dict(PHOTO), None)
    t0 = time.monotonic()
    solid = cr.build(p)
    elapsed = time.monotonic() - t0
    bb = solid.bounding_box()
    height = float(bb.max.Z) - float(bb.min.Z)
    length = float(bb.max.X) - float(bb.min.X)
    depth = float(bb.max.Y) - float(bb.min.Y)
    print("    measured: %.3f mm tall x %.3f mm long x %.3f mm deep; "
          "min.Z = %.6f" % (height, length, depth, float(bb.min.Z)))
    ok("5", "1950 mm tall (2R + tube = 2x800 + 350)",
       abs(height - 1950.0) < 1e-3, "%.3f" % height)
    ok("5", "1950 mm long (both side azimuths swept)",
       abs(length - 1950.0) < 1e-3, "%.3f" % length)
    ok("5", "350 mm deep (= tube_diameter)",
       abs(depth - 350.0) < 1e-3, "%.3f" % depth)
    ok("5", "min.Z == 0 (nadir tube point on the base plane)",
       abs(float(bb.min.Z)) < 1e-3, "%.6f" % float(bb.min.Z))
    ok("5", "derived helpers agree with the measured solid",
       abs(cr.top_mm(p) - 1950.0) < 1e-6
       and abs(cr.length_mm(p) - 1950.0) < 1e-6)
    print("    built in %.2f s (sandbox timeout 120 s, assertion < 60 s)"
          % elapsed)
    ok("5", "builds in well under the bound", elapsed < 60.0,
       "%.2f s < 60 s" % elapsed)


# ---------------------------------------------------------------------------
# [6] end-to-end on a throwaway DB
# ---------------------------------------------------------------------------

def end_to_end() -> None:
    section("6 end-to-end: cast plinth + crescent stack, BOM, export "
            "verdict (throwaway DB)")
    import importlib
    from app.geometry import registry

    plan = registry.assembly_plan_from_spec(SCA1_SPEC)
    limits = registry.fabrication_limits_from_spec(SCA1_SPEC)
    by_id = {e["element_id"]: e for e in plan}
    ok("6", "mapper gives the crescent a stack_on joint to the plinth",
       by_id["cre1"].get("joint") == {"type": "stack_on", "parent": "p1"})
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
    crescent = next(e for e in manifest["elements"]
                    if e["element_id"] == "cre1")
    ok("6", "crescent mass_model COMPLETE, no missing inputs",
       crescent["mass_model"]["mass_complete"] is True
       and crescent["mass_model"]["missing_mass_inputs"] == [])
    ok("6", "crescent mass == volume x 8000 within 0.5%",
       abs(crescent["mass_kg"] - crescent["volume_mm3"] * 1e-9 * 8000.0)
       / crescent["mass_kg"] < 0.005,
       "%.3f kg" % crescent["mass_kg"])
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
        os.environ["LUXURYFORM_DB"] = str(Path(td) / "gate_sca1.db")
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
                # design); the crescent MUST carry an explicit complete
                # block.
                from app.geometry.mass_model import (
                    assembly_mass_truth, element_mass_truth)
                truths = {eid: element_mass_truth(e) for eid, e in
                          els.items()}
                ok("6", "every element COMPLETE (legacy plinth implicit, "
                        "crescent explicit)",
                   all(t.mass_complete for t in truths.values())
                   and els["cre1"]["mass_model"]["mass_complete"] is True,
                   ", ".join("%s=%s" % (eid, t.mass_complete)
                             for eid, t in sorted(truths.items())))
                ok("6", "assembly mass truth COMPLETE with the manifest "
                        "total",
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
                    ok("6", "BOM is priced for stainless_316l_cast with "
                            "driver-backed lines",
                       bom["material_id"] == "stainless_316l_cast"
                       and len(bom["lines"]) > 0)
                    # The rate card is unconfigured by design (every
                    # amount is null in costing.yaml — gate_costing_auto
                    # pins that the real BOM is incomplete with NO
                    # total). The honest SC-A1 verdict: the COMPLETE
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
                ok("6", "export classification is the honest PRE_FABRICATION "
                        "verdict (unsigned evidence), never REFUSED",
                   resp.status_code == 200
                   and verdict == "pre_fabrication")
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
    from app.geometry.primitives import crescent_ring as cr
    from app.geometry.spec_mapper import assembly_plan_from_spec, \
        spec_aliases_for

    aliases = spec_aliases_for("crescent_ring")
    dangling = sorted(set(aliases.values()) - set(cr.PARAMETERS))
    ok("7", "no alias dangles (every target is a registry key)", not dangling,
       ", ".join(dangling) or "%d aliases" % len(aliases))
    unreachable = [k for k in cr.PARAMETERS if k != "material_id"
                   and k not in aliases.values()]
    ok("7", "every registry key reachable by a spec-level name",
       not unreachable, ", ".join(unreachable) or "all %d keys"
       % (len(cr.PARAMETERS) - 1))

    spec = json.loads(json.dumps(SCA1_SPEC))
    spec["massing"]["elements"] = [spec["massing"]["elements"][1]]
    del spec["massing"]["elements"][0]["parent_id"]
    spec["massing"]["elements"][0]["parameters"]["height"] = {
        "value": 1.95, "unit": "m"}
    try:
        assembly_plan_from_spec(spec)
        got, msg = False, "ACCEPTED"
    except Exception as exc:  # noqa: BLE001 - the refusal text is the check
        from app.geometry.primitives.base import ConstraintViolation
        got = isinstance(exc, ConstraintViolation) and \
            "2 x centerline_radius_mm + tube_diameter_mm" in str(exc)
        msg = str(exc)[:140]
    print("    height refusal: %s" % msg)
    ok("7", "spec height key refused NAMING the derived relationship "
            "(height = 2 x centerline_radius + tube_diameter)", got)

    text = primitive_index_surface()
    n = text.count("crescent_ring")
    start = text.index("- crescent_ring:")
    rest = text[start + 1:]
    end = rest.find("\n- ")
    block = rest if end == -1 else rest[:end]
    print("    printed crescent_ring block:")
    for ln in block.splitlines():
        print("    | " + ln)
    ok("7", "the Designer index mentions crescent_ring exactly once",
       n == 1, "%d occurrence(s)" % n)


# ---------------------------------------------------------------------------
# [8] negative: basalt crescent refused at the Designer boundary
# ---------------------------------------------------------------------------

def negatives() -> None:
    section("8 negative: basalt crescent refused at the Designer boundary")
    import copy

    from app.council.orchestrator import _validate_live_primitives

    wrong = copy.deepcopy(SCA1_SPEC)
    wrong["massing"]["elements"][1]["material_id"] = "basalt_slab"
    errs = _validate_live_primitives(wrong)
    for e in errs:
        print("    refusal: %s" % e[:110])
    ok("8", "basalt crescent refused at the boundary naming 316L",
       any("basalt_slab" in e and "stainless_316l_cast" in e for e in errs),
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
    from app.geometry.primitives import crescent_ring as cr
    for path in (Path(cr.__file__), Path(__file__).resolve()):
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
    print("SC-A1 AUTO GATE -- crescent_ring sculpture primitive (ADR-072)")
    print("repo root: %s" % REPO)
    print("=" * 72)
    before = _fingerprint()
    registry_truth()
    refusal_truth()
    determinism()
    integrity()
    demo_fidelity()
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
