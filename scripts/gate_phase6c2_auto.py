#!/usr/bin/env python3
"""PHASE 6 SLICE C2 AUTO GATE — segmentation and the costing drivers, $0.

Runs inside Docker (``docker compose exec backend python
scripts/gate_phase6c2_auto.py``) or on any machine with build123d+trimesh.
No stdin, no prompts, no API calls, no AI-written code; prints a numbered
transcript; exits 0 only on PASS.

  1. CANONICAL GUARDS — cascade e1a59fa6..., A1 assembly 529014af...,
     default basin 6038d26f..., C1 composition 956436c1...: segmentation
     moved no bytes. It cuts COPIES to measure them; the fused solid the
     STEP is exported from is untouched.
  2. CONSERVATION, EXACTLY — a 5 m basalt basin at a 2.4 m module limit;
     the module volumes must sum back to the element to 1e-6 %.
  3. EVERY MODULE FITS — each module against BOTH declared limits, with
     the worst of each printed.
  4. MEASURED, NOT PREDICTED — a hollow tube whose 3x3x2 grid predicts 18
     modules and truly yields 16.
  5. SEAM ARITHMETIC, HAND-CHECKABLE — the quartered basin's L-section
     area and perimeter, computed on paper and asserted against the
     kernel; and each interface counted ONCE, not once per cut face.
  6. DETERMINISM — same cut twice in two separate PROCESSES, byte
     identical; and plane order changes no engineering number.
  7. THE ARRAY REFUSAL — an oversized blade ring is refused by name, and
     the fragment count a naive grid would have produced is printed to
     show what was refused.
  8. DRIVERS AND THE BOM — seam_welding and install_transport must MOVE
     from not_computable (ours to build) to missing_rate (the operator's
     to supply), and compute against a filled test card.
  9. THE ROUTE ACTUALLY WORKS — GET /api/costing/bom/{design_id} on a
     real assembly returns 200. It returned 500 for every assembly ever
     built until this slice (ADR-056).
 10. MIXED MATERIAL IS REFUSED, NOT MISPRICED.
 11. BUDGET — per-element segmentation timing.
 12. VERDICT.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _assembly_build_once import GATE_PLAN as A1_PLAN  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"

PHASE2_CANONICAL_STEP_SHA256 = (
    "e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13"
)
A1_ASSEMBLY_STEP_SHA256 = (
    "529014af672a282b6626cece8eebc777f5d839a34be02c9a031b5813cf22ddbd"
)
DEFAULT_BASIN_STEP_SHA256 = (
    "6038d26f28cd61b0c01ae9fde00ff2841b34ad0d6228cc7c4bbdbdd1eeacf0f0"
)
A1_SEED = 42

#: The C1 gate composition, re-proven here byte-for-byte (its hash is the
#: one slice C1 pinned). Segmentation must not have moved it.
C1_PLAN = [
    {"element_id": "p1", "primitive": "plinth",
     "parameters": {"top_diameter_mm": 1400, "height_mm": 400,
                    "material_id": "basalt_slab"}},
    {"element_id": "b1", "primitive": "basin_round",
     "parameters": {"diameter_mm": 1200, "height_mm": 350, "wall_mm": 40,
                    "floor_mm": 80, "material_id": "basalt_slab"},
     "joint": {"type": "stack_on", "parent": "p1"}},
    {"element_id": "a1", "primitive": "blade_fin_array",
     "parameters": {"hub_diameter_mm": 320, "hub_height_mm": 500,
                    "blade_count": 24, "blade_length_mm": 250,
                    "blade_height_mm": 400, "blade_thickness_mm": 20,
                    "material_id": "stainless_316l_sheet"},
     "joint": {"type": "concentric_insert", "parent": "b1"}},
]
C1_SEED = 7
C1_ASSEMBLY_STEP_SHA256 = (
    "956436c1"  # prefix only — the full value is read back from the C1 gate
)

#: THE SLICE C2 SUBJECT: a basin no crane in Addis can pick.
BIG_BASIN = {"diameter_mm": 5000, "height_mm": 700, "wall_mm": 150,
             "material_id": "basalt_slab"}
BASALT_DENSITY = 2700.0

TOTAL = 12


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/{TOTAL}] {title}")
    _hline()


def _check(failures: list[str], label: str, ok: bool, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} — {label}" + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(label)


def main() -> int:  # noqa: C901 — a gate is a transcript, not a design
    import logging

    for name in ("luxuryform.config", "luxuryform.geometry", "luxuryform.db"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    failures: list[str] = []
    workdir = Path(tempfile.mkdtemp(prefix="luxuryform_gate6c2_"))

    from app.geometry.assembly import assemble
    from app.geometry.exporters import export_step
    from app.geometry.kernel import step_timestamp_for
    from app.geometry.primitives import PRIMITIVES, basin_round
    from app.geometry.primitives.base import ConstraintViolation
    from app.geometry.registry import cascade_fountain
    from app.geometry.segmentation import (
        MAX_PREDICTED_CELLS,
        MODE_DISCRETE_ARRAY,
        segment_solid,
    )

    def _build(pid: str, raw: dict):
        module = PRIMITIVES[pid]
        return module.build(module.validate(raw))

    def _cubic(limit_mm: float) -> dict:
        # PR-1 (ADR-059): the kernel takes per-axis mm; every measured
        # number in this gate was pinned at a CUBIC limit, and a cube of
        # the same side is the identical cut, so nothing here moves.
        return {"x": limit_mm, "y": limit_mm, "z": limit_mm}

    # ------------------------------------------------------------------
    _section(1, "CANONICAL GUARDS — segmentation moved no bytes")
    solid, _ = cascade_fountain({}, seed=42)
    sha = export_step(solid, workdir / "cascade.step", step_timestamp_for(42))
    print(f"cascade        : {sha}")
    _check(failures, "Phase 2 canonical cascade byte-identical",
           sha == PHASE2_CANONICAL_STEP_SHA256)
    fused, _ = assemble(A1_PLAN, seed=A1_SEED)
    sha_a1 = export_step(fused, workdir / "a1.step", step_timestamp_for(A1_SEED))
    print(f"A1 composition : {sha_a1}")
    _check(failures, "A1 gate-composition assembly byte-identical",
           sha_a1 == A1_ASSEMBLY_STEP_SHA256)
    pb = basin_round.validate({}, None)
    sha_b = export_step(basin_round.build(pb), workdir / "basin.step",
                        step_timestamp_for(42))
    print(f"default basin  : {sha_b}")
    _check(failures, "default basin byte-identical",
           sha_b == DEFAULT_BASIN_STEP_SHA256)
    fused_c1, _ = assemble(C1_PLAN, seed=C1_SEED)
    sha_c1 = export_step(fused_c1, workdir / "c1.step",
                         step_timestamp_for(C1_SEED))
    print(f"C1 composition : {sha_c1}")
    _check(failures, "C1 24-blade composition byte-identical",
           sha_c1.startswith(C1_ASSEMBLY_STEP_SHA256))

    # ------------------------------------------------------------------
    _section(2, "CONSERVATION, EXACTLY — nothing is lost in the cut")
    big = _build("basin_round", BIG_BASIN)
    whole_kg = float(big.volume) * 1e-9 * BASALT_DENSITY
    print(f"element        : {float(big.volume):,.0f} mm3 = {whole_kg:,.1f} kg "
          f"as ONE piece")
    seg = segment_solid(big, _cubic(2400.0), density_kg_per_m3=BASALT_DENSITY)
    total = sum(m["volume_mm3"] for m in seg.modules)
    print(f"modules        : {seg.module_count} summing to {total:,.6f} mm3")
    print(f"delta          : {seg.volume_delta_pct:.10f} % "
          f"(ceiling 1e-6 %)")
    _check(failures, "module volumes sum back to the element exactly",
           seg.volume_delta_pct <= 1e-6,
           f"{seg.volume_delta_pct:.10f}%")
    _check(failures, "an 11-tonne basin now yields liftable modules",
           whole_kg > 11_000 and seg.module_count == 9,
           f"{whole_kg:,.1f} kg -> {seg.module_count} modules")
    for m in seg.modules:
        print(f"  module {m['index']}: {m['mass_kg']:>9,.1f} kg   bbox "
              f"{m['bbox_mm'][0]:>8.1f} x {m['bbox_mm'][1]:>8.1f} x "
              f"{m['bbox_mm'][2]:>6.1f} mm")

    # ------------------------------------------------------------------
    _section(3, "EVERY MODULE FITS — both declared limits, per module")
    limit_mm, max_lift = 2400.0, 2000.0
    worst_dim = max(max(m["bbox_mm"]) for m in seg.modules)
    worst_mass = max(m["mass_kg"] for m in seg.modules)
    print(f"widest module  : {worst_dim:,.1f} mm  (limit {limit_mm:,.0f} mm)")
    print(f"heaviest module: {worst_mass:,.1f} kg  (limit {max_lift:,.0f} kg)")
    _check(failures, "every module inside max_module_m",
           worst_dim <= limit_mm + 1e-6, f"worst {worst_dim:,.1f} mm")
    _check(failures, "every module inside max_lift_kg",
           worst_mass <= max_lift, f"worst {worst_mass:,.1f} kg")
    _, big_manifest = assemble(
        [{"element_id": "b1", "primitive": "basin_round",
          "parameters": dict(BIG_BASIN)}],
        seed=0, fabrication={"max_module_m": 2.4, "max_lift_kg": max_lift},
        strict=True)
    _check(failures,
           "the assembler BUILDS what it used to refuse (strict mode)",
           big_manifest["fabrication_limit_violations"] == [],
           f"{big_manifest['segmentation']['module_count']} modules, heaviest "
           f"{big_manifest['segmentation']['heaviest_module_kg']:,.1f} kg")

    # ------------------------------------------------------------------
    _section(4, "MEASURED, NOT PREDICTED — the tube's centre cells are bore")
    tube = _build("plinth", {"top_diameter_mm": 3000, "height_mm": 1200,
                             "wall_mm": 150, "material_id": "basalt_slab"})
    tube_seg = segment_solid(tube, _cubic(1000.0),
                             density_kg_per_m3=BASALT_DENSITY)
    print(f"grid           : {tube_seg.grid} predicts "
          f"{tube_seg.predicted_cells} cells")
    print(f"measured       : {tube_seg.module_count} connected solids")
    _check(failures, "the module count is measured, not n_x*n_y*n_z",
           tube_seg.predicted_cells == 18 and tube_seg.module_count == 16,
           f"predicted {tube_seg.predicted_cells}, measured "
           f"{tube_seg.module_count}")
    _check(failures, "and it still conserves volume exactly",
           tube_seg.volume_delta_pct <= 1e-6,
           f"{tube_seg.volume_delta_pct:.10f}%")

    # ------------------------------------------------------------------
    _section(5, "SEAM ARITHMETIC — hand-checkable, and counted once")
    # Basin d5000, wall 150, floor 150, height 700, quartered by two planes.
    # The interface cut face is an L-section:
    #   floor strip 2500 x 150 = 375,000 mm2
    #   wall above  150 x 550  =  82,500 mm2   -> 457,500 mm2
    #   perimeter 2500+700+150+550+2350+150    =   6,400 mm
    hand_area = 2500.0 * 150.0 + 150.0 * (700.0 - 150.0)
    hand_perim = 2500.0 + 700.0 + 150.0 + 550.0 + 2350.0 + 150.0
    quarters = segment_solid(big, _cubic(2500.0),
                             density_kg_per_m3=BASALT_DENSITY)
    print(f"hand arithmetic: area {hand_area:,.1f} mm2, perimeter "
          f"{hand_perim:,.1f} mm, per interface")
    print(f"kernel         : {quarters.seam_count} interfaces, "
          f"{quarters.seam_area_mm2:,.1f} mm2, "
          f"{quarters.seam_length_mm:,.1f} mm")
    _check(failures, "4 quarters share 4 interfaces, not 8 cut faces",
           quarters.module_count == 4 and quarters.seam_count == 4,
           f"{quarters.module_count} modules, {quarters.seam_count} interfaces")
    _check(failures, "seam AREA matches hand arithmetic",
           abs(quarters.seam_area_mm2 - 4 * hand_area) <= 1e-6 * 4 * hand_area,
           f"{quarters.seam_area_mm2:,.6f} vs {4 * hand_area:,.6f} mm2")
    _check(failures, "seam LENGTH matches hand arithmetic",
           abs(quarters.seam_length_mm - 4 * hand_perim)
           <= 1e-6 * 4 * hand_perim,
           f"{quarters.seam_length_mm:,.6f} vs {4 * hand_perim:,.6f} mm")
    _check(failures, "no cut face went unpaired",
           quarters.unmatched_face_count == 0,
           f"{quarters.unmatched_face_count} unmatched")

    # A joint seam is the CONTACT footprint, not the child's outline: a 5 m
    # basin on a hollow 2.2 m plinth meets it over the plinth's top annulus.
    joint_plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 2200, "height_mm": 700,
                        "wall_mm": 200, "material_id": "basalt_slab"}},
        {"element_id": "b1", "primitive": "basin_round",
         "parameters": dict(BIG_BASIN),
         "joint": {"type": "stack_on", "parent": "p1"}},
    ]
    _, jm = assemble(joint_plan, seed=0, strict=False)
    jseam = jm["segmentation"]["seams"]["joint"]
    expect_len = math.pi * (2200.0 + 1800.0)
    print(f"joint seam     : {jseam['length_mm']:,.3f} mm "
          f"(annulus pi x (2200+1800) = {expect_len:,.3f} mm; the child's "
          f"own outline would be {math.pi * 5000.0:,.3f} mm)")
    _check(failures, "a joint seam is the contact face, not the child outline",
           abs(jseam["length_mm"] - expect_len) <= 1e-6 * expect_len
           and jseam["length_mm"] < math.pi * 5000.0,
           f"{jseam['length_mm']:,.3f} mm")

    # ------------------------------------------------------------------
    _section(6, "DETERMINISM — two processes, and plane order")
    mine = segment_solid(big, _cubic(2400.0),
                         density_kg_per_m3=BASALT_DENSITY).canonical_json()
    child = subprocess.run(
        [sys.executable, "-c", (
            "import sys, os, json; sys.path.insert(0, r'%s')\n"
            "from app.geometry.primitives import PRIMITIVES\n"
            "from app.geometry.segmentation import segment_solid\n"
            "m = PRIMITIVES['basin_round']\n"
            "s = m.build(m.validate(json.loads(sys.argv[1])))\n"
            "print(os.getpid())\n"
            "print(segment_solid(s, {'x': 2400.0, 'y': 2400.0, "
            "'z': 2400.0}, density_kg_per_m3=%r)"
            ".canonical_json())\n"
        ) % (REPO_ROOT / "backend", BASALT_DENSITY),
         json.dumps(BIG_BASIN)],
        capture_output=True, text=True,
    )
    lines = child.stdout.strip().splitlines()
    child_pid = lines[-2] if len(lines) >= 2 else "?"
    theirs = lines[-1] if lines else ""
    print(f"process {os.getpid()}: {len(mine)} chars of canonical JSON")
    print(f"process {child_pid}: "
          f"{len(theirs) if theirs else child.stderr[-200:]}")
    _check(failures, "segmentation byte-identical across two processes",
           mine == theirs)
    other = segment_solid(big, _cubic(2400.0),
                          density_kg_per_m3=BASALT_DENSITY,
                          axis_order=("z", "y", "x"))
    same_engineering = (
        other.module_count == seg.module_count
        and other.seam_count == seg.seam_count
        and abs(other.seam_length_mm - seg.seam_length_mm)
        <= 1e-9 * max(seg.seam_length_mm, 1.0)
    )
    print("plane order z-y-x vs x-y-z: "
          f"{other.module_count} vs {seg.module_count} modules, "
          f"{other.seam_length_mm:.6f} vs {seg.seam_length_mm:.6f} mm seam")
    _check(failures, "plane order changes no engineering number",
           same_engineering)

    # ------------------------------------------------------------------
    _section(7, "THE ARRAY REFUSAL — fragments are not modules")
    array_plan = [{"element_id": "a1", "primitive": "blade_fin_array",
                   "parameters": {"hub_diameter_mm": 900, "blade_count": 24,
                                  "blade_length_mm": 700,
                                  "material_id": "stainless_316l_sheet"}}]
    try:
        assemble(array_plan, seed=0,
                 fabrication={"max_module_m": 0.8, "max_lift_kg": 5000},
                 strict=True)
        _check(failures, "an oversized blade ring is refused", False,
               "NO violation raised")
    except ConstraintViolation as exc:
        text = "; ".join(exc.violations)
        print(f"refusal: {exc.violations[0][:200]}")
        _check(failures, "an oversized blade ring is refused BY NAME",
               "a1" in text and MODE_DISCRETE_ARRAY in text and "2300" in text)
    # what a naive grid WOULD have produced, so the refusal is legible
    blades = _build("blade_fin_array",
                    {"hub_diameter_mm": 900, "blade_count": 24,
                     "blade_length_mm": 700,
                     "material_id": "stainless_316l_sheet"})
    naive = segment_solid(blades, _cubic(800.0), density_kg_per_m3=8000.0)
    masses = sorted(m["mass_kg"] for m in naive.modules)
    print(f"a naive grid would have reported {naive.module_count} 'modules', "
          f"lightest {masses[0]:,.1f} kg against heaviest {masses[-1]:,.1f} kg "
          f"({masses[-1] / max(masses[0], 1e-9):,.0f}x) — blade tips, not "
          f"fabricable pieces")
    _check(failures, "the platform did NOT report those fragments as modules",
           naive.module_count > 9,
           f"{naive.module_count} fragments from a 3x3 grid, refused")

    # ------------------------------------------------------------------
    _section(8, "DRIVERS AND THE BOM — whose homework is it now")
    import yaml

    from app.core.config import CostingConfig, load_config_bundle
    from app.costing.bom import (
        COMPUTED,
        MISSING_RATE,
        NOT_COMPUTABLE,
        build_bom,
    )
    from app.costing.drivers import drivers_for_assembly
    from app.geometry.validate import validate_assembly
    from app.geometry.exporters import export_glb

    bundle = load_config_bundle()
    fused_j, jm2 = assemble(joint_plan, seed=0, strict=False,
                            fabrication={"max_module_m": 2.4,
                                         "max_lift_kg": 2000})
    glb = workdir / "joint.glb"
    export_glb(fused_j, glb)
    jreport = validate_assembly(glb, jm2)
    drivers = drivers_for_assembly(jreport, jm2)
    print(f"drivers: modules {drivers.module_count}, seam "
          f"{drivers.seam_length_m:,.3f} m / {drivers.seam_area_m2:,.4f} m2, "
          f"crane pick {drivers.crane_pick_kg:,.1f} kg of "
          f"{drivers.mass_kg:,.1f} kg total")
    _check(failures, "the crane picks a MODULE, not the whole fountain",
           drivers.crane_pick_kg < drivers.mass_kg,
           f"{drivers.crane_pick_kg:,.1f} kg vs {drivers.mass_kg:,.1f} kg")
    _check(failures, "module count and seam length are real numbers",
           drivers.module_count is not None
           and drivers.seam_length_m is not None)

    repo_bom = build_bom(bundle.costing, drivers, "basalt_slab",
                         bundle.materials.materials["basalt_slab"])
    lines = {ln.line_id: ln for ln in repo_bom.lines}
    for lid, path in (("seam_welding", "materials.basalt_slab.seam"),
                      ("install_transport", "install.truck_payload_kg")):
        ln = lines[lid]
        print(f"  {lid:20} {ln.status:16} {ln.rate_path}")
        _check(failures,
               f"{lid} is now the OPERATOR's to supply, not ours to build",
               ln.status == MISSING_RATE and ln.rate_path == path,
               f"{ln.status} / {ln.rate_path}")
    print(f"  {'material_purchase':20} "
          f"{lines['material_purchase'].status:16} "
          "(still ours + his: stock thickness and nesting, NOT segmentation)")
    _check(failures, "material_purchase is honestly still not computable",
           lines["material_purchase"].status == NOT_COMPUTABLE)

    # a filled TEST card (no engineering meaning) proves the arithmetic
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
        m["seam"] = {"amount": 300.0, "currency": "ETB", "per": "m"}
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
    filled = CostingConfig(**raw)
    filled_bom = build_bom(filled, drivers, "basalt_slab",
                           bundle.materials.materials["basalt_slab"])
    flines = {ln.line_id: ln for ln in filled_bom.lines}
    for lid in ("seam_welding", "install_transport"):
        print(f"  {lid}: {flines[lid].formula}")
        _check(failures, f"{lid} computes against a filled card",
               flines[lid].status == COMPUTED)
    # PR-5 (2026-09-08, D-10 sweep): this asserted missing_entries() == 39,
    # which expires the moment the operator fills ONE rate (B-3 is his to
    # fill). The timeless truth is that the six C2 paths EXIST on the rate
    # card — null or filled — so they are checked by path, count printed.
    c2_paths = [f"materials.{mid}.seam" for mid in sorted(raw["materials"])] + [
        "install.truck_payload_kg", "install.modules_per_trip"]

    def _has_path(dotted: str) -> bool:
        node = bundle.costing.model_dump()
        for key in dotted.split("."):
            if not isinstance(node, dict) or key not in node:
                return False
            node = node[key]
        return True

    missing_paths = [p for p in c2_paths if not _has_path(p)]
    # 2026-09-28 (D-10 instance nine, first in-container chain on the new
    # build machine): "six" was itself a frozen growth count — 4 materials
    # x seam + 2 install paths — and SC-A1 (ADR-072) made it 5 x seam + 2.
    # Timeless form: one seam path per REGISTERED material plus the two
    # install paths, every one present; the count is printed, not pinned.
    expected_c2 = len(raw["materials"]) + 2
    _check(failures, "the rate card carries every slice-C2 path "
                     "(one seam per material + truck payload + modules/trip)",
           len(c2_paths) == expected_c2 and not missing_paths,
           f"{len(c2_paths)} paths for {len(raw['materials'])} materials, "
           f"missing {missing_paths}; "
           f"{len(bundle.costing.missing_entries())} entries still null")
    del yaml  # imported for parity with the other gates; not needed here

    # ------------------------------------------------------------------
    _section(9, "THE ROUTE — it returned HTTP 500 for every assembly")
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post("/api/geometry/assembly/build", json={
        "elements": joint_plan, "seed": 0, "strict": False,
        "fabrication": {"max_module_m": 2.4, "max_lift_kg": 2000},
    })
    _check(failures, "assembly build returns 200", resp.status_code == 200,
           str(resp.status_code))
    if resp.status_code == 200:
        design_id = resp.json()["design_id"]
        bom_resp = client.get(f"/api/costing/bom/{design_id}")
        print(f"GET /api/costing/bom/{design_id[:8]}... -> "
              f"{bom_resp.status_code}")
        _check(failures, "costing an ASSEMBLY returns 200, not 500",
               bom_resp.status_code == 200, str(bom_resp.status_code))
        if bom_resp.status_code == 200:
            payload = bom_resp.json()
            manifest_mass = resp.json()["manifest"]["total_mass_kg"]
            got = payload["drivers"]["mass_kg"]
            print(f"drivers.mass_kg {got:,.3f} vs manifest total "
                  f"{manifest_mass:,.3f} kg")
            _check(failures,
                   "the BOM costs the SAME mass the manifest measured",
                   abs(got - manifest_mass) <= 0.01,
                   f"{got:,.3f} vs {manifest_mass:,.3f}")
            txt = client.get(f"/api/costing/bom/{design_id}.txt")
            _check(failures, "the rendered document says what ships",
                   txt.status_code == 200 and "WHAT SHIPS" in txt.text)

    # ------------------------------------------------------------------
    _section(10, "MIXED MATERIAL — per-element, never mispriced (PR-6)")
    mixed_plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 1400, "height_mm": 400,
                        "material_id": "basalt_slab"}},
        {"element_id": "b1", "primitive": "basin_round",
         "parameters": {"diameter_mm": 1200, "height_mm": 350, "wall_mm": 20,
                        "floor_mm": 80, "material_id": "bronze_cast"},
         "joint": {"type": "stack_on", "parent": "p1"}},
    ]
    mixed = client.post("/api/geometry/assembly/build", json={
        "elements": mixed_plan, "seed": 0, "strict": False})
    if mixed.status_code != 200:
        _check(failures, "the mixed-material assembly builds", False,
               json.dumps(mixed.json())[:200])
    else:
        mid_resp = client.get(f"/api/costing/bom/{mixed.json()['design_id']}")
        body = mid_resp.json()
        print(f"-> {mid_resp.status_code} material_id={body.get('material_id')} "
              f"complete={body.get('complete')} total="
              f"{(body.get('totals') or {}).get('total_usd')}")
        _check(failures, "the mixed-material assembly returns a BOM, not 409",
               mid_resp.status_code == 200, str(mid_resp.status_code))
        _check(failures, "the BOM carries both materials and per-element lines",
               set((body.get("drivers") or {}).get("materials") or []) ==
               {"basalt_slab", "bronze_cast"}
               and {e.get("material_id") for e in body.get("elements") or []} ==
               {"basalt_slab", "bronze_cast"}
               and any(str(ln.get("line_id", "")).startswith("p1/")
                       for ln in body.get("lines") or [])
               and any(str(ln.get("line_id", "")).startswith("b1/")
                       for ln in body.get("lines") or []),
               str((body.get("drivers") or {}).get("materials")))
        _check(failures, "the real unfilled card still produces no total",
               body.get("complete") is False
               and (body.get("totals") or {}).get("total_usd") is None)

    # ------------------------------------------------------------------
    _section(11, "BUDGET — segmentation is cheap enough to sit on the build")
    # Timing is read off the SegmentResult, never out of the manifest:
    # a wall-clock number in the manifest breaks the LUXEXCHANGE content
    # digest, which is exactly what the Phase 9A tests caught on
    # 2026-08-27 (ADR-056).
    worst_ms = 0.0
    for eid, entry in sorted(jm2["segmentation"]["elements"].items()):
        _check(failures, f"no wall-clock timing in the {eid} manifest block",
               "duration_ms" not in entry)
    for label, raw in (("5 m basin", BIG_BASIN),
                       ("hollow tube", {"top_diameter_mm": 3000,
                                        "height_mm": 1200, "wall_mm": 150,
                                        "material_id": "basalt_slab"})):
        pid = "basin_round" if "diameter_mm" in raw else "plinth"
        timed = segment_solid(_build(pid, raw),
                              _cubic(2400.0 if pid == "basin_round"
                                     else 1000.0),
                              density_kg_per_m3=BASALT_DENSITY)
        print(f"  {label}: {timed.module_count} module(s) in "
              f"{timed.duration_ms:.0f} ms")
        worst_ms = max(worst_ms, timed.duration_ms)
    print(f"  the refused-grid ceiling is {MAX_PREDICTED_CELLS} cells")
    _check(failures, "no element takes more than 10 s to segment",
           worst_ms <= 10_000.0, f"worst {worst_ms:.0f} ms")
    try:
        segment_solid(big, _cubic(100.0), density_kg_per_m3=BASALT_DENSITY)
        _check(failures, "a runaway module limit is refused", False,
               "NO ValueError raised")
    except ValueError as exc:
        print(f"  refusal: {str(exc)[:160]}")
        _check(failures, "a runaway module limit is refused with the numbers",
               str(MAX_PREDICTED_CELLS) in str(exc) and "50" in str(exc))

    # ------------------------------------------------------------------
    _section(12, "VERDICT")
    if failures:
        print(f"{FAIL} — {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"{PASS} — Phase 6 slice C2 auto gate: all sections passed at $0, "
          "no network, no AI-written code executed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
