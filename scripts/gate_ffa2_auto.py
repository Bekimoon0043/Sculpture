"""FF-A2 auto gate — the freeform_loop hollow-lens primitive (ADR-066).

$0, offline, non-interactive, hermetic (backend container). Sections:

  [1] Registry truth + declarations + the recorded parameter table
      (owner clarification 3: exact defaults and ranges in the
      transcript).
  [2] Refusal truth: 316L-only, the hard 3500-5000 scale, wall floor,
      W/H envelope cross-combinations — verbatim messages.
  [3] Determinism: the acceptance fixture built in TWO separate
      processes; both PIDs and both STEP sha256 digests printed.
  [4] The built fixture through the production integrity stack against
      the declared EXPECTED_TOPOLOGY, the AUTHORITATIVE measured
      bore-to-cavity clearance (owner clarification 2: FAIL below
      wall − 0.5 mm), and the honest wall-measurement block; the
      no-verified-wall-claim scan (runtime-assembled token).
  [5] Fixture fidelity: the six committed ref-08 landmark bands,
      measured from the built geometry and asserted verbatim. The
      bands are NEVER adjusted here.
  [6] End-to-end mass/export truth on a THROWAWAY database: incomplete
      mass everywhere, costing 409, PRE-FABRICATION package with the
      unresolved-only warrant, and the REFUSED negatives (missing,
      failed AND indeterminate integrity rows).
  [7] Segmentation as analysis: measured modules, volume conservation,
      and the over-envelope behaviour (segments or refuses — both are
      honest results, whichever the kernel gives is printed).
  [8] Hermeticity + $0: the real DB and data/exports untouched,
      no network/provider imports, no reference JPG in the image tree.

Never a Council call, never a render, never AI-loop code.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
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


FIXTURE_PATH = REPO / "tests" / "fixtures" / "freeform_loop_spec_v1.json"
LANDMARKS_PATH = (REPO / "briefs" / "freeform_references"
                  / "ref08_landmarks.json")


def registry_and_parameters() -> None:
    section("1 registry truth + declarations + recorded parameters")
    from app.geometry.mass_model import LEGACY_COMPLETE_MASS_PRIMITIVES
    from app.geometry.primitives import PRIMITIVES, freeform_loop as fl

    expected_eleven = {
        "tiered_cascade", "basin_round", "plinth", "sculptural_column",
        "basin_rect", "stepped_monolith", "water_wall", "torus_ring",
        "blade_fin_array", "lotus_petal_array", "freeform_loop",
    }
    print("  registered: %s" % ", ".join(sorted(PRIMITIVES)))
    # D-10-frozen: ADR-066 ruling — the registry's exact set lives in exactly
    # ONE roster gate, so widening the library fails exactly one check by
    # design; the slice that adds a primitive moves this set with its ADR.
    ok("1", "registry is exactly the eleven (exact set lives HERE)",
       set(PRIMITIVES) == expected_eleven)
    # D-10-frozen: ADR-065 byte-compat seam — the legacy complete-mass set
    # names the primitives whose manifests predate the mass model; it is
    # frozen forever and can never grow, so its count is a permanent truth.
    ok("1", "freeform_loop NOT in the frozen legacy ten",
       "freeform_loop" not in LEGACY_COMPLETE_MASS_PRIMITIVES
       and len(LEGACY_COMPLETE_MASS_PRIMITIVES) == 10)
    # D-10-frozen: ADR-066 declaration pin — the three armature inputs are
    # this primitive's own fabricator contract; a fourth missing input would
    # be a new professional dependency needing its own owner ruling.
    ok("1", "FF-A1 declarations armed",
       fl.REQUIRES_FREEFORM_INTEGRITY is True
       and len(fl.INCOMPLETE_MASS_INPUTS) == 3)
    ok("1", "topology contract is the approved values",
       fl.EXPECTED_TOPOLOGY == {
           "kernel_solids": 1, "through_openings": 1,
           "boundary_components": 2, "closed_internal_cavities": 1,
           "per_component_genus": [1, 1], "per_component_euler": [0, 0],
           "accidental_extra_bodies_or_voids": 0})
    ok("1", "bore_center_height_fraction renamed (clarification 1)",
       "bore_center_height_fraction" in fl.PARAMETERS
       and "bore_height_fraction" not in fl.PARAMETERS)
    ok("1", "tube-annulus construction absent (failed dev evidence only)",
       not any(hasattr(fl, n) for n in
               ("_closed_loop", "_half_loft", "_fold_check"))
       and "taper_ratio" not in fl.PARAMETERS)
    print("  recorded parameter table (owner clarification 3):")
    for name in sorted(fl.PARAMETERS):
        spec = fl.PARAMETERS[name]
        print("    %-28s default=%-8s min=%-6s max=%-6s"
              % (name, spec["default"], spec["min"], spec["max"]))
    ok("1", "delta parameters recorded with exact defaults/ranges",
       all(k in fl.PARAMETERS for k in
           ("depth_mm", "bore_width_mm", "bore_height_mm",
            "bore_center_height_fraction", "waist_height_fraction")))


def refusal_truth() -> None:
    section("2 refusal truth: 316L-only, scale, envelope")
    from app.geometry.primitives import freeform_loop as fl
    from app.geometry.primitives.base import ConstraintViolation

    defaults = json.loads(FIXTURE_PATH.read_text())["elements"][0][
        "parameters"]

    def refuses(needle: str, **over) -> tuple[bool, str]:
        raw = dict(defaults)
        raw.update(over)
        try:
            fl.validate(raw, None)
            return False, "ACCEPTED"
        except ConstraintViolation as exc:
            msg = "; ".join(exc.violations)
            return needle in msg, msg[:90]

    for mat in ("basalt_slab", "cast_concrete_c35_45", "bronze_cast"):
        got, msg = refuses("UNBUILT", material_id=mat)
        print("    %s -> %s" % (mat, msg))
        ok("2", "%s refuses as unbuilt process" % mat, got)
    got, msg = refuses("3500", height_mm=3499, width_mm=2100)
    ok("2", "height 3499 refuses (owner floor)", got, msg)
    got, msg = refuses("5000", height_mm=5001, width_mm=3100)
    ok("2", "height 5001 refuses (owner ceiling)", got, msg)
    got, msg = refuses("6", wall_mm=5.999)
    ok("2", "wall 5.999 refuses (embedment 3 + ligament 3)", got, msg)
    got, msg = refuses("0.336", height_mm=5000, width_mm=1680)
    ok("2", "height=5000 width=1680 refuses (ratio 0.336)", got, msg)
    got, msg = refuses("1.029", height_mm=3500, width_mm=3600)
    ok("2", "height=3500 width=3600 refuses (ratio 1.029)", got, msg)
    got, msg = refuses("corridor", bore_width_mm=2000, bore_height_mm=2500)
    ok("2", "oversized bore corridor refuses with numbers", got, msg)


BUILD_SNIPPET = r"""
import json, os, sys
from app.geometry.primitives import freeform_loop as fl
from app.geometry.exporters import export_step
from app.geometry.kernel import step_timestamp_for
params = json.loads(open(sys.argv[1]).read())["elements"][0]["parameters"]
p = fl.validate(params, None)
solid = fl.build(p)
sha = export_step(solid, sys.argv[2], step_timestamp_for(8))
print("pid=%d sha256=%s" % (os.getpid(), sha))
"""


def determinism() -> None:
    section("3 determinism: two separate processes, byte-identical STEP")
    results = []
    with tempfile.TemporaryDirectory() as td:
        for i in (1, 2):
            out = str(Path(td) / ("ffa2_%d.step" % i))
            proc = subprocess.run(
                [sys.executable, "-c", BUILD_SNIPPET, str(FIXTURE_PATH),
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


def build_fixture():
    from app.geometry.primitives import freeform_loop as fl
    params = json.loads(FIXTURE_PATH.read_text())["elements"][0][
        "parameters"]
    p = fl.validate(params, None)
    return p, fl.build(p)


def integrity_and_wall(p, solid) -> None:
    section("4 integrity + topology contract + authoritative bore "
            "clearance + wall truth")
    from app.geometry.freeform_validation import run_freeform_integrity
    from app.geometry.primitives import freeform_loop as fl

    report = run_freeform_integrity(
        solid, expected_topology=fl.EXPECTED_TOPOLOGY)
    by = {c["check"]: c for c in report["checks"]}
    for c in report["checks"]:
        print("    %-44s %-11s value=%s" % (c["check"], c["status"],
                                            str(c["value"])[:44]))
    ok("4", "integrity stack status is pass", report["status"] == "pass")
    ok("4", "boundary components == 2",
       by["topology_boundary_components"]["value"] == 2)
    ok("4", "per-component genus == [1, 1]",
       by["topology_per_component_genus"]["value"] == [1, 1])
    ok("4", "exactly one sealed internal cavity",
       by["topology_closed_internal_cavities"]["value"] == 1)
    ok("4", "exactly one through-opening",
       by["topology_through_openings"]["value"] == 1)

    wm = fl.measure_wall(p, solid)
    print("    wall_measurement: %s" % json.dumps(
        {k: wm.get(k) for k in ("method", "status", "min_mm", "max_mm",
                                "bore_to_cavity_mm", "junction_excluded")}))
    ok("4", "wall measurement produced (measured or honest unavailable)",
       wm.get("status") in ("measured", "unavailable"))
    btc = wm.get("bore_to_cavity_mm")
    threshold = float(p.wall_mm) - 0.5
    ok("4", "AUTHORITATIVE bore-to-cavity clearance >= wall - 0.5",
       btc is not None and float(btc) >= threshold,
       "measured %s vs %.1f mm (owner clarification 2)" % (btc, threshold))

    forbidden = "verified " + "wall"
    module_src = Path(fl.__file__).read_text(encoding="utf-8").lower()
    claims = [ln.strip() for ln in module_src.splitlines()
              if forbidden in ln.lower()
              and "never" not in ln.lower() and "not" not in ln.lower()]
    ok("4", "no verified-wall claim in the primitive", not claims,
       claims[0][:60] if claims else "")


def fidelity(solid) -> None:
    section("5 fixture fidelity: the six committed landmark bands")
    from app.geometry.primitives import freeform_loop as fl

    lm = json.loads(LANDMARKS_PATH.read_text())
    hard = lm["bands"]["hard_runtime_constraints"]
    fix = lm["bands"]["fixture_fidelity_checks"]
    pm = fl.projection_metrics(solid)
    print("    measured: %s" % json.dumps(
        {k: pm.get(k) for k in
         ("width_height_ratio", "void_width_fraction", "void_aspect",
          "void_centroid_height_fraction", "void_offset_fraction",
          "projected_side_to_apex_band_ratio", "rim_left_mm",
          "rim_right_mm", "apex_band_mm")}))
    ok("5", "exactly one enclosed through-void in projection",
       pm.get("enclosed_void_count") == 1,
       str(pm.get("enclosed_void_count")))
    bands = {"width_height_ratio": hard["width_height_ratio"]["band"]}
    for key in ("void_width_fraction", "void_aspect",
                "void_centroid_height_fraction", "void_offset_fraction",
                "projected_side_to_apex_band_ratio"):
        bands[key] = fix[key]["band"]
    for key, (lo, hi) in bands.items():
        v = pm.get(key)
        ok("5", "%s in [%s, %s]" % (key, lo, hi),
           v is not None and lo <= v <= hi, "measured %s" % v)
    twist_default = json.loads(FIXTURE_PATH.read_text())["elements"][0][
        "parameters"]["section_twist_deg"]
    ok("5", "twist direction matches the landmark (+ = CCW from above)",
       twist_default > 0, "fixture twist %s deg" % twist_default)
    # Owner ruling 2026-09-05: history preserved, and the projection
    # metric claims nothing about the reference's 3-D apex scoop —
    # that comparison is a separate mandatory visual-gate step.
    ratio_entry = fix["projected_side_to_apex_band_ratio"]
    ok("5", "band derived from the exact instrument result (recorded)",
       ratio_entry["derivation"]["raw_instrument_output"][
           "exact_ratio"] == "122/139 = 0.877698"
       and ratio_entry["band"] == [0.7022, 1.0532])
    ok("5", "retired rim_ratio preserved as history, not erased",
       "rim_ratio_HISTORICAL" in fix
       and fix["rim_ratio_HISTORICAL"]["band"] == [1.6, 2.4])
    ok("5", "projection metric explicitly does NOT claim the 3-D scoop",
       "visual" in ratio_entry["derivation"]["scope"].lower())


def end_to_end() -> None:
    section("6 end-to-end mass/export truth (throwaway DB)")
    import importlib
    with tempfile.TemporaryDirectory() as td:
        old_db = os.environ.get("LUXURYFORM_DB")
        old_data = os.environ.get("LUXURYFORM_DATA_DIR")
        os.environ["LUXURYFORM_DB"] = str(Path(td) / "gate_ffa2.db")
        os.environ["LUXURYFORM_DATA_DIR"] = str(Path(td) / "data")
        try:
            from app.db.database import get_default_db, reset_default_db
            reset_default_db()
            from fastapi.testclient import TestClient
            from sqlalchemy import select
            from app.db.models import ValidationReportRow
            from app.geometry.freeform_validation import (
                FREEFORM_INTEGRITY_GATE)
            from app.main import app

            payload = {k: v for k, v in
                       json.loads(FIXTURE_PATH.read_text()).items()
                       if not k.startswith("_")}
            with TestClient(app) as client:
                resp = client.post("/api/geometry/assembly/build",
                                   json=payload)
                ok("6", "fixture builds through the real API",
                   resp.status_code == 200,
                   "HTTP %d" % resp.status_code)
                body = resp.json()
                manifest = body["manifest"]
                design_id = body["design_id"]
                ok("6", "total_mass_kg is null, never zero",
                   manifest["total_mass_kg"] is None)
                el = manifest["elements"][0]
                ok("6", "element mass_model incomplete, armature named",
                   el["mass_model"]["mass_complete"] is False
                   and any("armature" in m for m in
                           el["mass_model"]["missing_mass_inputs"]))
                # MassTruth.wire() rounds to 3 decimals — assert THAT
                # contract exactly (the ADR-064 rounding lesson).
                ok("6", "known-geometry figure is real and includes the "
                        "plate",
                   el["mass_model"]["known_geometry_mass_kg"]
                   == round(el["volume_mm3"] * 1e-9 * 8000.0, 3),
                   "%.3f kg" % el["mass_model"]["known_geometry_mass_kg"])
                ok("6", "applicability snapshot persisted",
                   manifest["required_validation_gates"] ==
                   [FREEFORM_INTEGRITY_GATE]
                   and manifest["expected_topology"][
                       "per_component_genus"] == [1, 1])
                gates_out = body["validation_gates"]
                fab = {c["check"]: c for c in
                       gates_out["fabrication"]["checks"]}
                ok("6", "lift needs_input on incomplete mass",
                   fab["loop_01.mass_kg"]["status"] == "needs_input")
                ok("6", "fabrication_wall_approval always unresolved",
                   fab["loop_01.fabrication_wall_approval"][
                       "status"] == "needs_input")
                ok("6", "forming_radius always unresolved",
                   fab["loop_01.forming_radius_mm"][
                       "status"] == "needs_input")
                bore_row = fab.get("loop_01.bore_to_cavity_clearance")
                ok("6", "bore clearance row present and passing",
                   bore_row is not None and bore_row["status"] == "pass",
                   str((bore_row or {}).get("value")))
                struct = {c["check"]: c for c in
                          gates_out["structure_static_v1"]["checks"]}
                ok("6", "structural total needs_input",
                   struct["total_mass_kg"]["status"] == "needs_input")

                resp = client.get("/api/costing/bom/%s" % design_id)
                ok("6", "costing refuses 409 incomplete_mass",
                   resp.status_code == 409
                   and resp.json()["detail"]["error"] == "incomplete_mass")

                resp = client.post(
                    "/api/geometry/assembly/%s/exports" % design_id)
                ok("6", "export seals PRE-FABRICATION",
                   resp.status_code == 200
                   and resp.json()["package_class"] == "pre_fabrication",
                   "HTTP %d" % resp.status_code)
                zresp = client.get(
                    "/api/geometry/assembly/%s/luxexchange.zip" % design_id)
                import io
                import zipfile
                with zipfile.ZipFile(io.BytesIO(zresp.content)) as zf:
                    names = set(zf.namelist())
                    gate_json = "validation/%s.json" % \
                        FREEFORM_INTEGRITY_GATE
                    sealed = json.loads(zf.read(gate_json)) \
                        if gate_json in names else {}
                    warrant = zf.read("ENGINEERING_WARRANT.txt").decode(
                        "utf-8") if "ENGINEERING_WARRANT.txt" in names \
                        else ""
                ok("6", "passing integrity verdict sealed in validation "
                        "evidence", sealed.get("status") == "pass")
                ok("6", "warrant names the unresolved professional inputs",
                   "armature mass" in warrant
                   and "forming radius" in warrant.lower()
                   and "fabrication_wall_approval" in warrant)
                ok("6", "warrant carries no passing statuses",
                   all("pass" not in ln.split("status:")[1]
                       for ln in warrant.splitlines() if "status:" in ln))

                # REFUSED negatives: missing, failed, indeterminate.
                db = get_default_db()

                def tamper(new_status):
                    r = client.post("/api/geometry/assembly/build",
                                    json=payload)
                    did = r.json()["design_id"]
                    with db.get_session() as s:
                        for row in s.execute(
                            select(ValidationReportRow).where(
                                ValidationReportRow.design_id == did,
                                ValidationReportRow.gate_name ==
                                FREEFORM_INTEGRITY_GATE)).scalars().all():
                            if new_status is None:
                                s.delete(row)
                            else:
                                rep = json.loads(row.numbers_json)
                                rep["status"] = new_status
                                row.numbers_json = json.dumps(
                                    rep, sort_keys=True)
                                row.status = new_status
                                row.passed = 0
                    return client.post(
                        "/api/geometry/assembly/%s/exports" % did)
                for status, label in ((None, "missing"),
                                      ("fail", "failed"),
                                      ("needs_input", "indeterminate")):
                    r = tamper(status)
                    ok("6", "%s integrity row => REFUSED (409)" % label,
                       r.status_code == 409, "HTTP %d" % r.status_code)
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


def segmentation_analysis(p, solid) -> None:
    section("7 segmentation as analysis (never a transport claim)")
    from app.geometry.assembly import assemble
    params = json.loads(FIXTURE_PATH.read_text())["elements"][0][
        "parameters"]
    _, manifest = assemble(
        [{"element_id": "loop_01", "primitive": "freeform_loop",
          "parameters": params}],
        seed=8, fabrication={"max_lift_kg": 3000, "max_module_m": 5.0},
        strict=False)
    seg = manifest["segmentation"]["elements"]["loop_01"]
    modules = seg["modules"]
    total = sum(m["volume_mm3"] for m in modules)
    el_vol = manifest["elements"][0]["volume_mm3"]
    delta_pct = abs(total - el_vol) / el_vol * 100.0
    print("    modules: %d; volume conservation delta %.6f%%"
          % (len(modules), delta_pct))
    ok("7", "modules measured with conserved volume",
       len(modules) >= 1 and delta_pct < 0.01,
       "%d modules, %.6f%%" % (len(modules), delta_pct))
    # Over-envelope: segments or refuses — both honest; report which.
    try:
        _, m2 = assemble(
            [{"element_id": "loop_01", "primitive": "freeform_loop",
              "parameters": params}],
            seed=8, fabrication={"max_lift_kg": 3000,
                                 "max_module_m": 2.0},
            strict=False)
        seg2 = m2["segmentation"]["elements"]["loop_01"]
        if seg2.get("refusal"):
            outcome = "REFUSED: %s" % str(seg2["refusal"])[:70]
            honest = True
        else:
            n = len(seg2["modules"])
            outcome = "segmented into %d modules" % n
            honest = n > 1
    except Exception as exc:
        outcome = "raised: %s" % str(exc)[:70]
        honest = True  # a loud refusal is an honest outcome (v4 cond. 9)
    print("    over-envelope (max_module_m=2.0): %s" % outcome)
    ok("7", "over-envelope segments or refuses loudly", honest, outcome)


def hermeticity(before: tuple) -> None:
    section("8 hermeticity + $0 static scan")
    after = _fingerprint()
    ok("8", "real DB byte-identical", before[0] == after[0],
       str(after[0])[:12] if after[0] else "no DB on this checkout")
    ok("8", "data/exports unchanged", before[1] == after[1],
       "%d files" % len(after[1]))
    forbidden = tuple("import " + m for m in
                      ("requests", "httpx", "socket")) + \
        tuple(p + " " + m for p in ("from", "import")
              for m in ("anthropic", "openai"))
    from app.geometry.primitives import freeform_loop as fl
    for path in (Path(fl.__file__), Path(__file__).resolve()):
        code = "\n".join(ln for ln in
                         path.read_text(encoding="utf-8").splitlines()
                         if not ln.lstrip().startswith("#"))
        bad = [t for t in forbidden if t in code]
        ok("8", "%s network/provider-free" % path.name, not bad,
           ", ".join(bad))
    jpgs = list((REPO / "briefs").rglob("*.jpg")) if \
        (REPO / "briefs").exists() else []
    ok("8", "no reference JPG in this tree (operator-local only)",
       not jpgs, "%d found" % len(jpgs))


def main() -> int:
    print("=" * 72)
    print("FF-A2 AUTO GATE -- freeform_loop hollow-lens primitive "
          "(ADR-066)")
    print("repo root: %s" % REPO)
    print("=" * 72)
    before = _fingerprint()
    registry_and_parameters()
    refusal_truth()
    determinism()
    p, solid = build_fixture()
    integrity_and_wall(p, solid)
    fidelity(solid)
    end_to_end()
    segmentation_analysis(p, solid)
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
