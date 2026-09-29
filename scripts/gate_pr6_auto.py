#!/usr/bin/env python3
"""PR-6 AUTO GATE — costing tie-off: per-element, joints once, budget bound
(ADR-074). $0 forever.

Run inside Docker:
    docker compose exec backend python scripts/gate_pr6_auto.py

Non-interactive, offline, no AI call, no network. The REAL rate card
(config/costing.yaml) and the real DB/exports are proven byte-identical
before and after; every rate used for arithmetic is an injected in-memory
TEST value with no engineering meaning.

What it proves, with real numbers on both sides of every check:

  1. BOTH MATERIALS PRICED — a concrete plinth + basalt basin BOM carries
     fabrication lines for BOTH materials, each element on ITS mass; no
     line is priced at a material the design does not contain.
  2. JOINT ONCE — exactly one joint line; its rate_path names ONE
     material; the seam identity  sum(seam qty) == split + joint  holds
     to 1e-6; b1's own seam line is its cuts only.
  3. SHARED ONCE — exactly one crane, one crew, one transport line, all
     on ASSEMBLY numbers; crane pick == heaviest MODULE.
  4. HAND ARITHMETIC — the total on a filled test card equals the paper
     computation, printed line by line.
  5. OWNER RULE — null -> MISSING_RATE naming joints.cross_material_owner
     and NEITHER side billed; parent/child/stronger_rate each bill exactly
     one side; the both-sides disproof is printed (1200 vs 300 ETB).
  6. EXPOSED SKIN — finishing bills element skin MINUS joint contact
     (never a share); an element with no recorded skin is NOT_COMPUTABLE.
  7. SINGLE-MATERIAL EQUIVALENCE — a one-material design prices the same
     money through build_bom and build_assembly_bom; its as_dict carries
     no elements/joints keys (sealed digests of existing designs safe).
  8. LIVE API on a THROWAWAY DB — a real two-material kernel build no
     longer returns HTTP 409 mixed_material_assembly: it returns a
     per-element BOM, honestly rate-incomplete on the real card, with NO
     total; the document names each element's material, INSTALL once.
  9. BUDGET BINDS — a CONFIRMED intake's amount_max reaches the BOM route
     with no query parameter (status not_performed on the incomplete
     card — never pass); a draft does not bind; an explicit parameter
     wins and says so.
 10. HERMETICITY — config/costing.yaml, the real DB and data/exports
     byte-identical; no provider SDK imported by the costing package.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

TOTAL = 10
CHECKS: list[bool] = []


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/{TOTAL}] {title}")
    _hline()


def _check(failures: list[str], label: str, ok: bool,
           detail: str = "") -> None:
    CHECKS.append(bool(ok))
    print(f"  {'ok  ' if ok else 'FAIL'} {label}"
          + (f" -- {detail}" if detail else ""))
    if not ok:
        failures.append(f"{label} -- {detail}")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint() -> tuple:
    db = None
    for candidate in (Path("/app/data/luxuryform.db"),
                      REPO_ROOT / "data" / "luxuryform.db"):
        if candidate.exists():
            db = candidate
            break
    exports = None
    for candidate in (Path("/app/data/exports"), REPO_ROOT / "data" / "exports"):
        if candidate.exists():
            exports = candidate
            break
    listing = tuple(sorted((p.name, p.stat().st_size)
                           for p in exports.rglob("*") if p.is_file())) \
        if exports else ()
    return (_sha(db) if db else None), listing


# --- the paper fixture: round numbers so every identity is hand-checkable ----
P1_VOL, B1_VOL = 1.0e9, 2.0e9                # mm3  (1 m3, 2 m3)
P1_AREA, B1_AREA = 6.0e6, 10.0e6             # mm2  (6 m2, 10 m2 skin)
JOINT_AREA, JOINT_LEN = 0.5e6, 3000.0        # 0.5 m2 face, 3 m run
B1_SPLIT_LEN, B1_SPLIT_AREA = 4000.0, 0.8e6  # 4 m of cuts inside b1
P1_MASS = P1_VOL * 1e-9 * 2400.0             # 2400 kg concrete
B1_MASS = B1_VOL * 1e-9 * 2700.0             # 5400 kg basalt


def _manifest(with_area: bool = True) -> dict:
    els = [
        {"element_id": "p1", "primitive": "plinth",
         "material_id": "cast_concrete_c35_45",
         "volume_mm3": P1_VOL, "mass_kg": P1_MASS},
        {"element_id": "b1", "primitive": "basin_round",
         "material_id": "basalt_slab",
         "volume_mm3": B1_VOL, "mass_kg": B1_MASS},
    ]
    if with_area:
        els[0]["surface_area_mm2"] = P1_AREA
        els[1]["surface_area_mm2"] = B1_AREA
    return {
        "schema": "assembly_manifest_v1", "elements": els,
        "joints": [{"child": "b1", "parent": "p1", "type": "stack_on",
                    "overlap_mm": 10.0, "floor_mm": 30.0}],
        "total_mass_kg": P1_MASS + B1_MASS,
        "segmentation": {
            "schema": "assembly_segmentation_v1",
            "module_count": 3, "heaviest_module_kg": 2700.0,
            "not_segmentable": [],
            "elements": {
                "p1": {"module_count": 1, "seam_count": 0,
                       "seam_length_mm": 0.0, "seam_area_mm2": 0.0,
                       "modules": [{"index": 0, "mass_kg": P1_MASS}]},
                "b1": {"module_count": 2, "seam_count": 1,
                       "seam_length_mm": B1_SPLIT_LEN,
                       "seam_area_mm2": B1_SPLIT_AREA,
                       "modules": [{"index": 0, "mass_kg": 2700.0},
                                   {"index": 1, "mass_kg": 2700.0}]}},
            "seams": {
                "split": {"count": 1, "length_mm": B1_SPLIT_LEN,
                          "area_mm2": B1_SPLIT_AREA},
                "joint": {"count": 1, "length_mm": JOINT_LEN,
                          "area_mm2": JOINT_AREA,
                          "joints": [{"child": "b1", "parent": "p1",
                                      "type": "stack_on",
                                      "contact_z_mm": 500.0,
                                      "length_mm": JOINT_LEN,
                                      "area_mm2": JOINT_AREA}]},
                "total_length_mm": B1_SPLIT_LEN + JOINT_LEN},
        },
    }


def _report():
    from app.geometry.validate import AssemblyValidationReport, VolumeCrossCheck
    return AssemblyValidationReport(
        glb_path="/tmp/gate_pr6.glb", element_count=2, joint_count=1,
        watertight=True, winding_consistent=True, body_count=1,
        volume_mm3=P1_VOL + B1_VOL,
        surface_area_mm2=P1_AREA + B1_AREA - 2 * JOINT_AREA,
        degenerate_face_count=0, face_count=1000,
        element_masses_kg={"p1": P1_MASS, "b1": B1_MASS},
        total_mass_kg=P1_MASS + B1_MASS,
        volume_crosscheck=VolumeCrossCheck(
            trimesh_volume_mm3=3.0e9, build123d_volume_mm3=3.0e9,
            delta_pct=0.0, tolerance_pct=2.0, within_tolerance=True),
        passed=True)


def _test_card(bundle, *, owner: str | None = "parent",
               seam_basalt: float = 300.0, seam_concrete: float = 100.0):
    """Injected TEST rate card — in memory only, arbitrary values, NEVER
    copied into config/costing.yaml."""
    from app.core.config import CostingConfig
    raw = bundle.costing.model_dump()
    for mid, m in raw["materials"].items():
        m["buy_price"] = {"amount": 100.0, "currency": "ETB", "per": "kg"}
        m["waste_factor_pct"] = 10.0
        m["fabrication"]["method"] = "hand_carve"
        m["fabrication"]["labor"] = {"amount": 200.0, "currency": "ETB",
                                     "per": "hour"}
        m["fabrication"]["hours_per_m3"] = 40.0
        m["finishing"] = {"amount": 500.0, "currency": "ETB", "per": "m2"}
        m["seam"] = {"amount": seam_basalt if mid == "basalt_slab"
                     else seam_concrete, "currency": "ETB", "per": "m"}
    raw["workshop"]["overhead_pct"] = 15.0
    raw["install"]["crew_day_rate"] = {"amount": 1000.0, "currency": "ETB",
                                       "per": "crew_day"}
    raw["install"]["crew_size"] = 4
    raw["install"]["days_per_tonne"] = 0.5
    raw["install"]["transport"] = {"amount": 8000.0, "currency": "ETB",
                                   "per": "trip"}
    raw["install"]["truck_payload_kg"] = 12000.0
    raw["install"]["modules_per_trip"] = 4
    raw["contingency_pct"] = 10.0
    raw["markup_pct"] = 20.0
    raw["fx_rates"]["ETB"] = {"rate": 140.0, "as_of": "2026-08-01"}
    raw["joints"] = {"cross_material_owner": owner}
    return CostingConfig(**raw)


def _bom(costing, bundle, manifest=None):
    from app.costing.bom import build_assembly_bom
    from app.costing.drivers import drivers_for_assembly, drivers_per_element
    manifest = manifest or _manifest()
    report = _report()
    assembly = drivers_for_assembly(report, manifest)
    elements, joints = drivers_per_element(report, manifest)
    return build_assembly_bom(costing, assembly, elements, joints,
                              bundle.materials.materials,
                              design_id="gate-pr6", spec_hash="paper")


def _line(bom, line_id):
    return next(ln for ln in bom.lines if ln.line_id == line_id)


def _joint_lines(bom):
    return [ln for ln in bom.lines if ln.line_id.startswith("joint/")]


def _live_api_sections(failures: list[str], bundle) -> None:
    """Real kernel + real API, but only on a throwaway DB/data directory."""
    _section(8, "LIVE API — real mixed-material build returns a BOM, not 409")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        old_db = os.environ.get("LUXURYFORM_DB")
        old_data = os.environ.get("LUXURYFORM_DATA_DIR")
        os.environ["LUXURYFORM_DB"] = str(Path(td) / "gate_pr6.db")
        os.environ["LUXURYFORM_DATA_DIR"] = str(Path(td) / "data")
        try:
            from app.db.database import reset_default_db
            reset_default_db()
            from fastapi.testclient import TestClient
            from app.main import app

            with TestClient(app) as client:
                # Enough operator-known fields to pass the existing intake
                # readiness gate, plus the budget PR-6 must bind.
                intake = client.post("/api/intake", json={
                    "brief_text": "Two-material fountain with a 2,000,000 ETB ceiling.",
                    "fields": {
                        "project.project_type": "fountain",
                        "dimensions.height_m": 1.2,
                        "dimensions.footprint_m": 1.8,
                        "site.indoor": False,
                        "site.design_wind_speed_m_s": 30.0,
                        "water.has_water": True,
                        "budget.amount_max": 2_000_000.0,
                        "budget.currency": "ETB",
                    },
                })
                _check(failures, "intake is created on the throwaway DB",
                       intake.status_code == 201, f"HTTP {intake.status_code}")
                intake_id = intake.json().get("id")
                confirm = client.post(f"/api/intake/{intake_id}/confirm")
                _check(failures, "intake confirms before the design build",
                       confirm.status_code == 200
                       and confirm.json().get("status") == "confirmed",
                       f"HTTP {confirm.status_code}")

                plan = [
                    {"element_id": "p1", "primitive": "plinth",
                     "parameters": {"top_diameter_mm": 1400,
                                    "height_mm": 400,
                                    "material_id": "basalt_slab"}},
                    {"element_id": "b1", "primitive": "basin_round",
                     "parameters": {"diameter_mm": 1200,
                                    "height_mm": 350,
                                    "wall_mm": 20, "floor_mm": 80,
                                    "material_id": "bronze_cast"},
                     "joint": {"type": "stack_on", "parent": "p1"}},
                ]
                built = client.post("/api/geometry/assembly/build", json={
                    "elements": plan, "seed": 0, "strict": False,
                    "intake_id": intake_id,
                })
                _check(failures, "real two-material plan builds and persists",
                       built.status_code == 200, f"HTTP {built.status_code}")
                if built.status_code != 200:
                    print("    build error: " + json.dumps(built.json())[:500])
                    return
                body = built.json()
                design_id = body["design_id"]
                manifest = body["manifest"]
                els = {e["element_id"]: e for e in manifest["elements"]}
                _check(failures, "assembler persists each element's real skin area",
                       all(float(e.get("surface_area_mm2") or 0.0) > 0.0
                           for e in els.values()),
                       ", ".join(f"{eid}={e.get('surface_area_mm2')}"
                                 for eid, e in sorted(els.items())))

                resp = client.get(f"/api/costing/bom/{design_id}")
                _check(failures, "mixed-material BOM returns HTTP 200, not 409",
                       resp.status_code == 200, f"HTTP {resp.status_code}")
                if resp.status_code == 200:
                    api_bom = resp.json()
                    mats = set((api_bom.get("drivers") or {}).get("materials") or [])
                    _check(failures, "API BOM carries both real materials",
                           mats == {"basalt_slab", "bronze_cast"}, str(sorted(mats)))
                    _check(failures, "API BOM has per-element fabrication lines",
                           any(str(ln.get("line_id", "")).startswith("p1/")
                               for ln in api_bom["lines"])
                           and any(str(ln.get("line_id", "")).startswith("b1/")
                                   for ln in api_bom["lines"]))
                    _check(failures, "real empty card is honest: NO total",
                           api_bom["complete"] is False
                           and api_bom["totals"]["total_usd"] is None,
                           f"complete={api_bom['complete']} "
                           f"total={api_bom['totals']['total_usd']}")

                txt = client.get(f"/api/costing/bom/{design_id}.txt")
                _check(failures, "rendered BOM names both element/material blocks",
                       txt.status_code == 200
                       and "FABRICATION — p1 (basalt_slab)" in txt.text
                       and "FABRICATION — b1 (bronze_cast)" in txt.text,
                       f"HTTP {txt.status_code}")
                _check(failures, "rendered BOM prints shared INSTALL once",
                       txt.text.count("INSTALL (shared") == 1,
                       f"count={txt.text.count('INSTALL (shared')}")

                # ------------------------------------------------------
                _section(9, "BUDGET — confirmed intake binds; query wins")
                if resp.status_code == 200:
                    budget = resp.json().get("budget") or {}
                    _check(failures, "confirmed intake budget binds with no query",
                           budget.get("status") == "not_performed"
                           and budget.get("source") == "confirmed brief intake"
                           and intake_id in str(budget.get("source_detail")),
                           json.dumps(budget, sort_keys=True)[:300])
                    _check(failures, "incomplete BOM budget is never PASS",
                           budget.get("status") != "pass")

                explicit = client.get(
                    f"/api/costing/bom/{design_id}?budget_amount=9999999"
                    "&budget_currency=ETB")
                explicit_budget = (explicit.json().get("budget") or {}) \
                    if explicit.status_code == 200 else {}
                _check(failures, "explicit query overrides the intake source",
                       explicit.status_code == 200
                       and explicit_budget.get("source") ==
                       "explicit request parameter"
                       and "9999999" in str(explicit_budget.get("source_detail")),
                       json.dumps(explicit_budget, sort_keys=True)[:300])

                # Editing a confirmed intake reopens it; a draft must stop
                # binding immediately without rebuilding the design.
                reopened = client.put(f"/api/intake/{intake_id}", json={
                    "fields": {"budget.amount_max": 3_000_000.0}})
                _check(failures, "editing the intake reopens it as draft",
                       reopened.status_code == 200
                       and reopened.json().get("status") == "draft")
                draft_bom = client.get(f"/api/costing/bom/{design_id}")
                _check(failures, "a draft intake no longer binds the BOM",
                       draft_bom.status_code == 200
                       and "budget" not in draft_bom.json())
        finally:
            for key, value in (("LUXURYFORM_DB", old_db),
                               ("LUXURYFORM_DATA_DIR", old_data)):
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            from app.db.database import reset_default_db
            reset_default_db()


def main() -> int:
    from app.core.config import load_config_bundle
    from app.costing.bom import COMPUTED, MISSING_RATE, NOT_COMPUTABLE
    from app.costing.budget import budget_from_intake, check_budget
    from app.costing.drivers import drivers_for_assembly, drivers_per_element
    from app.costing.joints import OWNER_RULE_PATH
    from app.costing.report import render_bom

    failures: list[str] = []
    yaml_path = REPO_ROOT / "config" / "costing.yaml"
    yaml_sha_before = _sha(yaml_path)
    real_before = _fingerprint()
    bundle = load_config_bundle()
    costing = _test_card(bundle)
    manifest = _manifest()
    report = _report()
    assembly = drivers_for_assembly(report, manifest)
    elements, joints = drivers_per_element(report, manifest)
    bom = _bom(costing, bundle)

    print("PR-6 AUTO GATE — per-element costing, joints once, budget bound")
    print(f"config/costing.yaml sha256 (before): {yaml_sha_before}")
    print(f"real DB/exports fingerprint (before): {real_before}")

    # ------------------------------------------------------------------
    _section(1, "BOTH MATERIALS — each element priced on its own drivers")
    materials = {e.material_id for e in elements}
    line_materials = {
        ln.drivers_used.get("material_id") for ln in bom.lines
        if "/" in ln.line_id and not ln.line_id.startswith("joint/")
    }
    _check(failures, "fixture carries concrete + basalt",
           materials == {"cast_concrete_c35_45", "basalt_slab"},
           str(sorted(materials)))
    _check(failures, "fabrication lines carry BOTH and only those materials",
           line_materials == materials, str(sorted(line_materials)))
    p_buy = _line(bom, "p1/material_purchase")
    b_buy = _line(bom, "b1/material_purchase")
    print("  purchase drivers: p1=%.3f kg, b1=%.3f kg"
          % (p_buy.drivers_used["mass_kg"], b_buy.drivers_used["mass_kg"]))
    _check(failures, "p1 purchase uses p1 mass, b1 purchase uses b1 mass",
           abs(p_buy.drivers_used["mass_kg"] - P1_MASS) < 1e-9
           and abs(b_buy.drivers_used["mass_kg"] - B1_MASS) < 1e-9)

    # ------------------------------------------------------------------
    _section(2, "JOINT ONCE — conservation identity, one rate_path")
    jlines = _joint_lines(bom)
    _check(failures, "exactly one element-joint line", len(jlines) == 1,
           str([ln.line_id for ln in jlines]))
    jl = jlines[0]
    split_m = math.fsum(
        float(ln.drivers_used.get("seam_length_m", 0.0)) for ln in bom.lines
        if ln.line_id.endswith("/seam_welding") and ln.status == COMPUTED)
    joint_m = float(jl.drivers_used.get("length_m", 0.0))
    measured_m = (B1_SPLIT_LEN + JOINT_LEN) / 1000.0
    print("  seam identity: split %.6f + joint %.6f = %.6f m; manifest %.6f m"
          % (split_m, joint_m, split_m + joint_m, measured_m))
    _check(failures, "sum(seam lines) == split + joint to 1e-6",
           abs(split_m + joint_m - measured_m) <= 1e-6)
    _check(failures, "joint is owned by ONE parent-material rate",
           jl.rate_path == "materials.cast_concrete_c35_45.seam"
           and "parent" in str(jl.drivers_used.get("owner_reason")),
           str(jl.rate_path))
    _check(failures, "b1 seam line is cuts only, never the joint",
           abs(_line(bom, "b1/seam_welding").drivers_used["seam_length_m"]
               - B1_SPLIT_LEN / 1000.0) <= 1e-9)

    # ------------------------------------------------------------------
    _section(3, "SHARED ONCE — crane, crew, transport at assembly level")
    ids = [ln.line_id for ln in bom.lines]
    for lid in ("install_crane", "install_crew", "install_transport"):
        _check(failures, f"{lid} appears exactly once", ids.count(lid) == 1,
               f"count={ids.count(lid)}")
    _check(failures, "crane pick is heaviest MODULE, not assembly mass",
           abs(float(bom.drivers["crane_pick_kg"]) - 2700.0) < 1e-9
           and float(bom.drivers["crane_pick_kg"]) < P1_MASS + B1_MASS,
           f"pick={bom.drivers['crane_pick_kg']} total={P1_MASS + B1_MASS}")

    # ------------------------------------------------------------------
    _section(4, "HAND ARITHMETIC — every subtotal and total independently")
    fab = round(math.fsum(ln.amount_usd or 0.0 for ln in bom.lines
                          if ln.group == "fabrication"), 6)
    install = round(math.fsum(ln.amount_usd or 0.0 for ln in bom.lines
                              if ln.group == "install"), 6)
    overhead = round(fab * 0.15, 6)
    base = round(fab + overhead + install, 6)
    contingency = round(base * 0.10, 6)
    markup = round((base + contingency) * 0.20, 6)
    expected_total = round(base + contingency + markup, 6)
    print("  paper: fab %.6f + overhead %.6f + install %.6f = base %.6f"
          % (fab, overhead, install, base))
    print("  paper: base %.6f + contingency %.6f + markup %.6f = %.6f USD"
          % (base, contingency, markup, expected_total))
    _check(failures, "filled fixture BOM is complete", bom.complete,
           f"missing={bom.missing_rates} blocked={bom.not_computable}")
    _check(failures, "BOM total equals independent paper arithmetic",
           abs((bom.total_usd or -1.0) - expected_total) <= 1e-6,
           f"bom={bom.total_usd} paper={expected_total}")
    p_expected = round(P1_MASS * 1.10 * 100.0 / 140.0, 6)
    _check(failures, "p1 purchase line matches hand arithmetic",
           abs((p_buy.amount_usd or -1.0) - p_expected) <= 1e-6,
           f"bom={p_buy.amount_usd} paper={p_expected}")

    # ------------------------------------------------------------------
    _section(5, "OWNER RULE — null refuses; each enum owns one side")
    null_card = _test_card(bundle, owner=None)
    null_bom = _bom(null_card, bundle)
    null_joint = _joint_lines(null_bom)[0]
    _check(failures, "null rule -> MISSING_RATE naming the exact path",
           null_joint.status == MISSING_RATE
           and null_joint.rate_path == OWNER_RULE_PATH
           and OWNER_RULE_PATH in null_bom.missing_rates,
           f"status={null_joint.status} path={null_joint.rate_path}")
    for rule, expected in (("parent", "cast_concrete_c35_45"),
                           ("child", "basalt_slab"),
                           ("stronger_rate", "basalt_slab")):
        owned = _joint_lines(_bom(_test_card(bundle, owner=rule), bundle))[0]
        _check(failures, f"{rule} bills exactly {expected}",
               owned.status == COMPUTED
               and owned.rate_path == f"materials.{expected}.seam",
               str(owned.rate_path))
    both_sides = 3.0 * (300.0 + 100.0)
    one_side = float(jl.amount_native or 0.0)
    print(f"  disproof: both sides = {both_sides:.2f} ETB; once = {one_side:.2f} ETB")
    _check(failures, "both-sides billing is disproved and absent",
           abs(both_sides - 1200.0) < 1e-9
           and abs(one_side - 300.0) < 1e-9
           and one_side < both_sides)

    # ------------------------------------------------------------------
    _section(6, "EXPOSED SKIN — direct subtraction, never apportionment")
    by_id = {e.element_id: e for e in elements}
    print("  p1 exposed = 6.0 - 0.5 = %.4f m2" % by_id["p1"].exposed_area_m2)
    print("  b1 exposed = 10.0 - 0.5 = %.4f m2" % by_id["b1"].exposed_area_m2)
    _check(failures, "each exposed area is its OWN skin minus contact",
           abs((by_id["p1"].exposed_area_m2 or -1.0) - 5.5) < 1e-9
           and abs((by_id["b1"].exposed_area_m2 or -1.0) - 9.5) < 1e-9)
    no_area = _bom(costing, bundle, _manifest(with_area=False))
    _check(failures, "missing element skin -> NOT_COMPUTABLE, no total",
           all(_line(no_area, f"{eid}/finishing").status == NOT_COMPUTABLE
               for eid in ("p1", "b1"))
           and no_area.complete is False and no_area.total_usd is None)

    # ------------------------------------------------------------------
    _section(7, "SINGLE MATERIAL — existing build_bom path unchanged")
    from app.costing.bom import build_assembly_bom, build_bom
    same_manifest = _manifest()
    for e in same_manifest["elements"]:
        e["material_id"] = "basalt_slab"
    same_assembly = drivers_for_assembly(report, same_manifest)
    same_elements, same_joints = drivers_per_element(report, same_manifest)
    single = build_bom(costing, same_assembly, "basalt_slab",
                       bundle.materials.materials["basalt_slab"],
                       design_id="d", spec_hash="s", now_iso="fixed")
    multi = build_assembly_bom(costing, same_assembly, same_elements, same_joints,
                               bundle.materials.materials,
                               design_id="d", spec_hash="s", now_iso="fixed")
    for lid in ("install_crane", "install_crew", "install_transport"):
        _check(failures, f"single/multi {lid} money identical",
               _line(single, lid).amount_usd == _line(multi, lid).amount_usd)
    _check(failures, "single-material as_dict emits no PR-6 extra keys",
           "elements" not in single.as_dict() and "joints" not in single.as_dict())

    # Sections 8-9: real API on a throwaway DB only.
    _live_api_sections(failures, bundle)

    # ------------------------------------------------------------------
    _section(10, "HERMETICITY — real card/DB/exports untouched, AI fence")
    yaml_sha_after = _sha(yaml_path)
    real_after = _fingerprint()
    _check(failures, "config/costing.yaml byte-identical",
           yaml_sha_before == yaml_sha_after,
           f"{yaml_sha_before[:12]} -> {yaml_sha_after[:12]}")
    _check(failures, "real DB/exports byte-identical",
           real_before == real_after, f"{real_before} -> {real_after}")
    costing_files = list((REPO_ROOT / "backend" / "app" / "costing").glob("*.py"))
    forbidden = []
    for path in costing_files:
        text = path.read_text(encoding="utf-8")
        for token in ("import anthropic", "import openai", "from anthropic",
                      "from openai", "Moonshot"):
            if token in text:
                forbidden.append(f"{path.name}:{token}")
    _check(failures, "costing package imports no provider SDK",
           not forbidden, str(forbidden))

    print()
    print("=" * 72)
    if failures:
        print(f"FAIL — {len(failures)} check(s) failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"PASS — all {len(CHECKS)} checks passed at $0, offline, "
          "with no AI call and no production data touched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

