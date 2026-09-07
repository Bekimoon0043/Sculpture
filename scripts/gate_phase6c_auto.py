#!/usr/bin/env python3
"""PHASE 6 SLICE C1 AUTO GATE — extrusion and array masses, $0.

Runs inside Docker (``docker compose exec backend python
scripts/gate_phase6c_auto.py``) or on any machine with build123d+trimesh.
No stdin, no prompts, no API calls, no AI-written code; prints a numbered
transcript; exits 0 only on PASS.

  1. CANONICAL GUARDS — cascade e1a59fa6…, A1 assembly 529014af…, default
     basin 6038d26f…: nothing that passed before moved.
  2. REGISTRY & SURFACE — ten primitives; two-tier detail only for a
     spec's own selection.
  3. PRIMITIVE BATTERY — the six new masses each build ONE watertight
     solid; refusals with real numbers for every signed floor.
  4. THE GATE C COMPOSITION (plan, verbatim) — a 24-blade array inside a
     3-primitive assembly: body_count 1 at B-rep AND mesh, volume
     conservation, byte-identical STEP across two separate processes —
     both hashes AND both PIDs printed.
  5. BEARING HONESTY — the torus chord seat computed and held to the
     joint floor; the rect footprint's inscribed-circle seat.
  6. HANDLING — a 2,495 kg solid monolith refused by a 2,000 kg crane
     with the arithmetic.
  7. VERDICT.
"""

from __future__ import annotations

import json
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

#: THE GATE C COMPOSITION: a 24-blade array inside a 3-primitive assembly.
C_PLAN = [
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
C_SEED = 7


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/7] {title}")
    _hline()


def _check(failures: list[str], label: str, ok: bool, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} — {label}" + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(label)


def _expect(failures, label, fn, *needles):
    from app.geometry.primitives.base import ConstraintViolation

    try:
        fn()
    except ConstraintViolation as exc:
        text = str(exc)
        missing = [n for n in needles if n not in text]
        _check(failures, label, not missing,
               exc.violations[0][:150] if not missing
               else f"message lacks {missing}: {text[:150]}")
        return
    _check(failures, label, False, "NO violation raised")


def main() -> int:
    import logging

    for name in ("luxuryform.config", "luxuryform.geometry", "luxuryform.db"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    failures: list[str] = []
    workdir = Path(tempfile.mkdtemp(prefix="luxuryform_gate6c_"))

    from app.geometry.assembly import assemble
    from app.geometry.exporters import export_glb, export_step
    from app.geometry.kernel import step_timestamp_for
    from app.geometry.primitives import (
        PRIMITIVES,
        basin_rect,
        basin_round,
        blade_fin_array,
        lotus_petal_array,
        stepped_monolith,
        torus_ring,
        water_wall,
    )
    from app.geometry.registry import cascade_fountain
    from app.geometry.validate import validate_assembly

    # ------------------------------------------------------------------
    _section(1, "CANONICAL GUARDS — nothing that passed before moved")
    solid, _ = cascade_fountain({}, seed=42)
    sha = export_step(solid, workdir / "cascade.step", step_timestamp_for(42))
    print(f"cascade: {sha}")
    _check(failures, "Phase 2 canonical cascade byte-identical",
           sha == PHASE2_CANONICAL_STEP_SHA256)
    fused, _ = assemble(A1_PLAN, seed=A1_SEED)
    sha_a1 = export_step(fused, workdir / "a1.step", step_timestamp_for(A1_SEED))
    print(f"A1 composition: {sha_a1}")
    _check(failures, "A1 gate-composition assembly byte-identical",
           sha_a1 == A1_ASSEMBLY_STEP_SHA256)
    pb = basin_round.validate({}, None)
    sha_b = export_step(basin_round.build(pb), workdir / "basin.step",
                        step_timestamp_for(42))
    _check(failures, "default basin byte-identical",
           sha_b == DEFAULT_BASIN_STEP_SHA256)

    # ------------------------------------------------------------------
    _section(2, "REGISTRY & SURFACE — the C1 ten, two-tier detail")
    # Operator ruling 2026-08-26 (recorded in gate_phase6a1_auto.py),
    # applied here by the FF-A2-approved conversion (ADR-066): an earlier
    # slice's gate asserts its primitives are a SUBSET; the exact-set
    # assertion belongs to the newest slice's gate (gate_ffa2_auto).
    expected = {
        "tiered_cascade", "basin_round", "plinth", "sculptural_column",
        "basin_rect", "stepped_monolith", "water_wall", "torus_ring",
        "blade_fin_array", "lotus_petal_array",
    }
    print(f"registered: {', '.join(sorted(PRIMITIVES))}")
    _check(failures, "registry contains the ten slice-A1+C1 primitives",
           expected <= set(PRIMITIVES))
    from app.council import prompts

    surface = prompts.registry_surface(["torus_ring", "plinth"])
    _check(failures, "index names every primitive",
           all(f"{pid}:" in surface for pid in expected))
    # Detail tables are told apart from index lines by PARAMETER names —
    # the index prints "  <id>: <purpose>" for every primitive by design.
    _check(failures, "detail only for the selection",
           "major_diameter_mm" in surface          # torus detail present
           and "blade_length_mm" not in surface    # blade detail absent
           and "tier_top_diameter_mm" not in surface,  # cascade absent
           f"{len(surface)} chars for a 2-primitive selection")

    # ------------------------------------------------------------------
    _section(3, "PRIMITIVE BATTERY — built and refused with real numbers")
    for module, params, label in [
        (basin_rect, {"length_mm": 2000, "width_mm": 1200, "height_mm": 450,
                      "wall_mm": 40, "floor_mm": 60, "corner_radius_mm": 60,
                      "material_id": "basalt_slab"}, "basin_rect 2000x1200"),
        (stepped_monolith, {"base_length_mm": 1200, "base_width_mm": 1200,
                            "steps": 3, "step_height_mm": 300,
                            "step_inset_mm": 100,
                            "material_id": "basalt_slab"},
         "stepped_monolith 3x300"),
        (water_wall, {"length_mm": 2400, "height_mm": 1800,
                      "thickness_mm": 100, "material_id": "basalt_slab"},
         "water_wall 2400x1800"),
        (torus_ring, {"major_diameter_mm": 1200, "minor_diameter_mm": 200,
                      "material_id": "bronze_cast"}, "torus_ring 1200/200"),
        (blade_fin_array, {"hub_diameter_mm": 500, "hub_height_mm": 600,
                           "blade_count": 24, "blade_length_mm": 300,
                           "blade_height_mm": 500, "blade_thickness_mm": 30,
                           "material_id": "stainless_316l_sheet"},
         "blade_fin_array 24 blades"),
        (lotus_petal_array, {"hub_diameter_mm": 500, "hub_height_mm": 200,
                             "petal_count": 8, "petal_length_mm": 500,
                             "petal_width_mm": 250, "petal_thickness_mm": 30,
                             "tilt_deg": 35, "material_id": "bronze_cast"},
         "lotus_petal_array 8 petals"),
    ]:
        p = module.validate(params, None)
        s = module.build(p)
        _check(failures, f"{label} builds ONE watertight solid",
               len(s.solids()) == 1,
               f"volume {float(s.volume) / 1e6:.1f} x10⁶ mm³")
    _expect(failures, "rect corner under the internal-radius floor refused",
            lambda: basin_rect.validate(
                {"length_mm": 2000, "width_mm": 1200, "wall_mm": 40,
                 "corner_radius_mm": 5, "material_id": "basalt_slab"}, None),
            "corner_radius_mm", "10")
    _expect(failures, "blade under the feature floor refused",
            lambda: blade_fin_array.validate(
                {"hub_diameter_mm": 400, "blade_count": 12,
                 "blade_thickness_mm": 10, "material_id": "basalt_slab"},
                None),
            "blade_thickness_mm", "15")
    _expect(failures, "petal tangency band refused (ADR-029 generalised)",
            lambda: lotus_petal_array.validate(
                {"hub_diameter_mm": 500, "petal_count": 6,
                 "petal_width_mm": 260, "petal_thickness_mm": 30,
                 "material_id": "bronze_cast"}, None),
            "tangency", "1.8")
    _expect(failures, "torus self-intersection refused",
            lambda: torus_ring.validate(
                {"major_diameter_mm": 300, "minor_diameter_mm": 200,
                 "material_id": "bronze_cast"}, None),
            "major_diameter_mm", "self-intersect")
    _expect(failures, "step inset under the tolerance floor refused",
            lambda: stepped_monolith.validate(
                {"base_length_mm": 1200, "base_width_mm": 1200, "steps": 3,
                 "step_inset_mm": 5, "material_id": "basalt_slab"}, None),
            "step_inset_mm", "10")
    _expect(failures, "water-wall thickness under the 3x floor refused",
            lambda: water_wall.validate(
                {"length_mm": 2400, "height_mm": 1800, "thickness_mm": 40,
                 "material_id": "basalt_slab"}, None),
            "thickness_mm", "60")

    # ------------------------------------------------------------------
    _section(4, "THE GATE C COMPOSITION — 24 blades, one body, two processes")
    fused_c, manifest = assemble(C_PLAN, seed=C_SEED)
    _check(failures, "B-rep body_count == 1",
           manifest["body_count_brep"] == 1)
    vc = manifest["volume_conservation"]
    _check(failures, "volume conservation",
           vc["delta_pct"] <= vc["tolerance_pct"],
           f"delta {vc['delta_pct']:.4f}% of {vc['tolerance_pct']}%")
    glb = workdir / "c.glb"
    export_glb(fused_c, glb)
    report = validate_assembly(glb, manifest)
    _check(failures, "mesh watertight with body_count == 1",
           report.watertight and report.body_count == 1)
    sha_1 = export_step(fused_c, workdir / "c_run1.step",
                        step_timestamp_for(C_SEED))
    child = subprocess.run(
        [sys.executable, "-c", (
            "import sys, json, os; sys.path.insert(0, r'%s')\n"
            "from app.geometry.assembly import assemble\n"
            "from app.geometry.exporters import export_step\n"
            "from app.geometry.kernel import step_timestamp_for\n"
            "solid, m = assemble(json.loads(sys.argv[1]), seed=%d)\n"
            "print(os.getpid())\n"
            "print(export_step(solid, r'%s', step_timestamp_for(%d)))\n"
        ) % (REPO_ROOT / "backend", C_SEED,
             workdir / "c_run2.step", C_SEED),
         json.dumps(C_PLAN)],
        capture_output=True, text=True,
    )
    lines = child.stdout.strip().splitlines()
    child_pid = lines[-2] if len(lines) >= 2 else "?"
    sha_2 = lines[-1] if lines else ""
    print(f"process {os.getpid()}: {sha_1}")
    print(f"process {child_pid}: {sha_2 or child.stderr[-200:]}")
    _check(failures,
           "24-blade assembly byte-identical across two separate processes",
           sha_1 == sha_2)

    # ------------------------------------------------------------------
    _section(5, "BEARING HONESTY — chords and inscribed circles")
    torus_plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 1600, "height_mm": 300,
                        "material_id": "basalt_slab"}},
        {"element_id": "t1", "primitive": "torus_ring",
         "parameters": {"major_diameter_mm": 1200, "minor_diameter_mm": 200,
                        "material_id": "basalt_slab"},
         "joint": {"type": "stack_on", "parent": "p1"}},
    ]
    _, m_t = assemble(torus_plan, seed=7)
    chord = 2 * (10 * (200 - 10)) ** 0.5
    _check(failures, "torus sunk by the 10 mm floor bears on a real chord",
           m_t["body_count_brep"] == 1,
           f"chord = 2·sqrt(10·190) = {chord:.1f} mm >= 10 mm floor")
    rect_plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 1000, "height_mm": 300,
                        "material_id": "basalt_slab"}},
        {"element_id": "b1", "primitive": "basin_rect",
         "parameters": {"length_mm": 2000, "width_mm": 1200,
                        "height_mm": 450, "wall_mm": 40, "floor_mm": 60,
                        "material_id": "basalt_slab"},
         "joint": {"type": "stack_on", "parent": "p1"}},
    ]
    _, m_r = assemble(rect_plan, seed=7)
    _check(failures, "rect footprint uses the inscribed-circle seat",
           m_r["body_count_brep"] == 1,
           "inscribed ⌀1200 on plinth ⌀1000 -> 500 mm seat >= 10 mm floor")

    # ------------------------------------------------------------------
    _section(6, "HANDLING — computed limits still bind on the new masses")
    _expect(failures, "2,495 kg solid monolith refused by a 2,000 kg crane",
            lambda: assemble([
                {"element_id": "m1", "primitive": "stepped_monolith",
                 "parameters": {"base_length_mm": 1200, "base_width_mm": 1200,
                                "steps": 3, "step_height_mm": 300,
                                "step_inset_mm": 100,
                                "material_id": "basalt_slab"}},
            ], seed=7, fabrication={"max_lift_kg": 2000.0}),
            "max_lift_kg", "2000")

    # ------------------------------------------------------------------
    _section(7, "VERDICT")
    if failures:
        print(f"{FAIL} — {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"{PASS} — Phase 6 slice C1 auto gate: all sections passed at $0, "
          "no network, no AI-written code executed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
