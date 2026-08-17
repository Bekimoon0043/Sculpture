#!/usr/bin/env python3
"""COSTING AUTO GATE — LuxuryForm Studio v1 (non-interactive half, $0 forever).

Run inside Docker:
    docker compose exec backend python scripts/gate_costing_auto.py

Proves the four operator rules with real numbers and no API calls:

  1. RATE CARD STATE — what is filled in config/costing.yaml and what is not.
  2. DRIVERS — every cost driver comes from a validation report the platform
     already produced; the two the operator named that do NOT exist yet are
     reported as unavailable, never as zero.
  3. TRACEABILITY — against a filled TEST rate card, every computed line
     carries its formula, its rate, and the config path the rate came from.
  4. MISSING-RATE HONESTY — against the REPO's actual rate card, the BOM is
     incomplete, every gap is named, and there is no total.
  5. BUDGET — binding on a complete BOM (refuses with real numbers), and
     NEVER reported as pass on an incomplete one.
  6. THE DOCUMENT — the rendered BOM, printed in full.
  7. VERDICT.

The measured numbers used throughout are the REAL ones from the design that
passed the Phase 4 live gate on 2026-08-17 (design 70716728, basalt cascade):
volume 1,271,287,346.316879 mm3, surface 42,954,224.45121378 mm2,
mass 3,432.4758350555735 kg.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))


def _hline() -> None:
    print("-" * 72)


def _section(no: int, total: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/{total}] {title}")
    _hline()


def main() -> int:
    import yaml

    from app.core.config import CostingConfig, Material, load_config_bundle
    from app.costing.bom import COMPUTED, NOT_COMPUTABLE, build_bom
    from app.costing.budget import BudgetViolation, check_budget
    from app.costing.drivers import drivers_from_validation
    from app.costing.report import render_bom
    from app.geometry.validate import ValidationReport, VolumeCrossCheck

    total = 7
    failures: list[str] = []

    report = ValidationReport(
        glb_path="(phase 4 live gate)", material_id="basalt_slab",
        watertight=True, winding_consistent=True,
        volume_mm3=1271287346.316879, surface_area_mm2=42954224.45121378,
        euler_number=0,
        bounds_mm=[-1300.0, -1299.6, 0.0, 1300.0, 1299.6, 1710.0],
        degenerate_face_count=0, face_count=30240,
        mass_kg=3432.4758350555735,
        volume_crosscheck=VolumeCrossCheck(
            trimesh_volume_mm3=1271287346.316879,
            build123d_volume_mm3=1271814019.4899116, delta_pct=0.0414,
            tolerance_pct=2.0, within_tolerance=True),
        passed=True)

    bundle = load_config_bundle()
    basalt = bundle.materials.materials["basalt_slab"]

    # -- 1 ---------------------------------------------------------------
    _section(1, total, "RATE CARD STATE (config/costing.yaml)")
    missing = bundle.costing.missing_entries()
    print(f"costing_version: {bundle.costing.costing_version}")
    print(f"filled: {not missing}   missing entries: {len(missing)}")
    for path in missing:
        print(f"  NULL  {path}")
    if not missing:
        print("  (rate card is fully filled)")

    # -- 2 ---------------------------------------------------------------
    _section(2, total, "COST DRIVERS — from the validation report only")
    drivers = drivers_from_validation(report)
    for k, v in drivers.as_dict().items():
        print(f"  {k:20} {v}")
    print()
    for name, why in (drivers.unavailable or {}).items():
        print(f"  UNAVAILABLE {name}: {why}")
    if drivers.module_count is not None or drivers.seam_length_m is not None:
        failures.append("module_count/seam_length must be None, not a guess")
    if abs(drivers.mass_kg - report.mass_kg) > 1e-9:
        failures.append("mass driver does not match the validation report")
    if abs(drivers.crane_pick_kg - report.mass_kg) > 1e-9:
        failures.append("crane pick weight wrong for a monolithic solid")
    print("  PASS — drivers read from validation, nothing re-measured")

    # -- 3 ---------------------------------------------------------------
    _section(3, total, "TRACEABILITY — filled TEST rate card")
    raw = bundle.costing.model_dump()
    for mid in raw["materials"]:
        m = raw["materials"][mid]
        m["buy_price"] = {"amount": 100.0, "currency": "ETB", "per": "kg"}
        m["waste_factor_pct"] = 10.0
        m["fabrication"]["method"] = "hand_carve"
        m["fabrication"]["labor"] = {"amount": 200.0, "currency": "ETB",
                                     "per": "hour"}
        m["fabrication"]["hours_per_m3"] = 40.0
        m["finishing"] = {"amount": 500.0, "currency": "ETB", "per": "m2"}
    raw["workshop"]["overhead_pct"] = 15.0
    raw["install"]["crew_day_rate"] = {"amount": 1000.0, "currency": "ETB",
                                       "per": "crew_day"}
    raw["install"]["crew_size"] = 4
    raw["install"]["days_per_tonne"] = 0.5
    raw["install"]["transport"] = {"amount": 8000.0, "currency": "ETB",
                                   "per": "trip"}
    raw["contingency_pct"] = 10.0
    raw["markup_pct"] = 20.0
    raw["fx_rates"]["ETB"] = {"rate": 140.0, "as_of": "2026-08-01"}
    filled = CostingConfig(**raw)
    print("  (test rates — arbitrary values, NEVER copy these into "
          "costing.yaml)")

    test_bom = build_bom(filled, drivers, "basalt_slab", basalt,
                         design_id="gate-costing", spec_hash="(test)")
    traced = 0
    for ln in test_bom.lines:
        if ln.status != COMPUTED:
            continue
        traced += 1
        print(f"  {ln.label}")
        print(f"     {ln.formula}")
        print(f"     rate {ln.rate_text}  [{ln.rate_path}]  "
              f"-> {ln.amount_usd:,.2f} USD  ({ln.fx_text})")
        if not (ln.rate_path and ln.rate_text and ln.drivers_used):
            failures.append(f"line {ln.line_id} is not fully traced")
    if traced == 0:
        failures.append("no computed lines on the filled card")
    print(f"  PASS — {traced} computed lines, each with formula + rate path")

    print()
    print("  Lines still NOT COMPUTABLE even with every rate supplied:")
    for ln in test_bom.lines:
        if ln.status == NOT_COMPUTABLE:
            print(f"     {ln.line_id}: {ln.blocker[:150]}")
    if test_bom.missing_rates:
        failures.append("filled card should leave no missing rates: "
                        f"{test_bom.missing_rates}")

    # -- 4 ---------------------------------------------------------------
    _section(4, total, "MISSING-RATE HONESTY — the REPO's actual rate card")
    real_bom = build_bom(bundle.costing, drivers, "basalt_slab", basalt,
                         design_id="70716728-e895-4da2-baef-54ea1967aa1c",
                         spec_hash="c5fafffa6fa25dd2fcf035df7b9b09a0"
                                   "c261071de625b5486784de75da0b8456")
    print(f"  complete: {real_bom.complete}")
    print(f"  total_usd: {real_bom.total_usd}")
    print(f"  missing rates named: {len(real_bom.missing_rates)}")
    print(f"  not-computable lines: {real_bom.not_computable}")
    if real_bom.complete or real_bom.total_usd is not None:
        failures.append("an unfilled rate card must NOT produce a total")
    for ln in real_bom.lines:
        if ln.status != COMPUTED and (ln.amount_native is not None
                                      or ln.amount_usd is not None):
            failures.append(f"line {ln.line_id} carries money without a rate")
    print("  PASS — no total, every gap named, no number invented")

    # -- 5 ---------------------------------------------------------------
    _section(5, total, "BUDGET CONSTRAINT — binding, and never falsely PASS")
    incomplete_check = check_budget(
        real_bom, {"amount": 1.0, "currency": "ETB", "fx_date": "2026-08-01"},
        bundle.costing)
    print(f"  incomplete BOM -> {incomplete_check.status}")
    print(f"     {incomplete_check.reason}")
    if incomplete_check.status != "not_performed":
        failures.append("incomplete BOM must yield not_performed")

    # A fully computable BOM, for the binding half of the check: take the
    # filled-card BOM and drop the two segmentation-blocked lines, then total
    # it by hand at the same percentages. This is a GATE CONSTRUCT, not a
    # quote — it exists only to prove the budget constraint refuses.
    complete_bom = build_bom(filled, drivers, "basalt_slab", basalt)
    keep = [ln for ln in complete_bom.lines if ln.status != NOT_COMPUTABLE]
    complete_bom.lines = keep
    complete_bom.not_computable = []
    fab = round(sum(ln.amount_usd or 0 for ln in keep
                    if ln.group == "fabrication"), 6)
    ins = round(sum(ln.amount_usd or 0 for ln in keep
                    if ln.group == "install"), 6)
    oh = round(fab * 0.15, 6)
    base = round(fab + oh + ins, 6)
    cont = round(base * 0.10, 6)
    mk = round((base + cont) * 0.20, 6)
    complete_bom.complete = True
    complete_bom.subtotal_fabrication_usd = fab
    complete_bom.overhead_usd = oh
    complete_bom.subtotal_install_usd = ins
    complete_bom.base_usd = base
    complete_bom.contingency_usd = cont
    complete_bom.markup_usd = mk
    complete_bom.total_usd = round(base + cont + mk, 6)
    complete_bom.total_formula = [f"TOTAL = {complete_bom.total_usd:,.2f} USD"]

    print(f"  complete BOM total: {complete_bom.total_usd:,.2f} USD "
          "(test rates)")
    try:
        check_budget(complete_bom,
                     {"amount": 1000.0, "currency": "ETB",
                      "fx_date": "2026-08-01"}, filled)
        failures.append("over-budget design was NOT refused")
        print("  FAIL — over-budget design was not refused")
    except BudgetViolation as exc:
        print(f"  over-budget -> REFUSED: {exc.message}")

    ok = check_budget(complete_bom,
                      {"amount": 500_000_000.0, "currency": "ETB",
                       "fx_date": "2026-08-01"}, filled)
    print(f"  within budget -> {ok.status}, headroom "
          f"{ok.headroom_usd:,.2f} USD")
    if ok.status != "pass":
        failures.append("a design inside budget should pass")

    # -- 6 ---------------------------------------------------------------
    _section(6, total, "THE DOCUMENT — rendered BOM (repo rate card)")
    print(render_bom(real_bom, incomplete_check))

    # -- 7 ---------------------------------------------------------------
    _section(total, total, "VERDICT")
    print()
    _hline()
    if failures:
        print("COSTING GATE: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("COSTING GATE: PASS")
    if missing:
        print()
        print(f"NOTE: the rate card has {len(missing)} unfilled entries, so no")
        print("real BOM can total yet. The gate proves the machinery is honest")
        print("about that — it does not prove a client-ready quote exists.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
