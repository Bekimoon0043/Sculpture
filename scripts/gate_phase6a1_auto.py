#!/usr/bin/env python3
"""PHASE 6 SLICE A1 AUTO GATE — the assembly core, $0, non-interactive.

Runs inside Docker (``docker compose exec backend python
scripts/gate_phase6a1_auto.py``) or on any machine with build123d+trimesh.
No stdin, no prompts, no API calls; prints a numbered transcript; exits 0
only on PASS.

  1. REGISTRY & SIGNED ENVELOPES — four primitives registered; the signed
     Part-2 material values (joint overlap / min feature / internal radius)
     loaded and printed, including 316L's formula floors.
  2. ADR-030 — the AST gate REJECTS a build123d import and passes the
     registry+math program: the registry is the ceiling on capability.
  3. PHASE 2 HASH PROTECTION — the default cascade (seed 42) still exports
     the CANONICAL STEP sha256 e1a59fa6… byte-for-byte (per-member walls
     added without moving a single vertex), asserted EXPLICITLY per the
     signed sheet Part 5.
  4. CONSTRAINT BATTERY — the assembler refuses, with real numbers: overlap
     under the material floor; the tangent knife edge (ADR-029 generalised);
     an insert punching the parent floor; an insert that does not fit; a
     floating body; a 2,121 kg solid plinth against a 2,000 kg crane (and
     the hollow one passes); an oversized module.
  5. THE GATE COMPOSITION — three different primitives fuse into ONE
     watertight assembly: body_count 1 at B-rep AND mesh level, every joint
     proven to interfere, volume conservation, full validation rows printed.
  6. ASSEMBLY DETERMINISM — the same plan + seed built in TWO SEPARATE
     PROCESSES exports byte-identical STEP (Amendment 1 survives Phase 6).
  7. VERDICT.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

PASS = "PASS"
FAIL = "FAIL"

#: The Phase 2 canonical STEP sha256 (PHASE_2_REPORT.md, proven cross-machine
#: 2026-08-04). Slice A1 must reproduce it BYTE-FOR-BYTE: column_wall_mm
#: defaults to basin_wall_mm and geometry reads it only through constraint 4.
PHASE2_CANONICAL_STEP_SHA256 = (
    "e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13"
)
PHASE2_CANONICAL_SEED = 42


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/7] {title}")
    _hline()


def _expect_violation(failures: list[str], label: str, fn, *needles: str) -> None:
    from app.geometry.primitives.base import ConstraintViolation

    try:
        fn()
    except ConstraintViolation as exc:
        text = str(exc)
        missing = [n for n in needles if n not in text]
        if missing:
            print(f"FAIL — {label}: violation raised but lacks {missing}")
            print(f"  got: {text[:300]}")
            failures.append(f"{label}: message lacks {missing}")
        else:
            first = exc.violations[0]
            print(f"ok — {label}:")
            print(f"    {first[:200]}")
        return
    print(f"FAIL — {label}: NO violation raised")
    failures.append(f"{label}: not refused")


def main() -> int:
    import logging

    logging.getLogger("luxuryform.config").setLevel(logging.CRITICAL)
    logging.getLogger("luxuryform.geometry").setLevel(logging.CRITICAL)
    failures: list[str] = []
    workdir = Path(tempfile.mkdtemp(prefix="luxuryform_gate6a1_"))

    # ------------------------------------------------------------------
    _section(1, "REGISTRY & SIGNED ENVELOPES (ADR-032)")
    from app.core.config import load_config_bundle
    from app.geometry.registry import PRIMITIVES

    expected = {"tiered_cascade", "basin_round", "plinth", "sculptural_column"}
    got = set(PRIMITIVES)
    print(f"registered primitives: {', '.join(sorted(got))}")
    if got != expected:
        failures.append(f"registry: expected {sorted(expected)}, got {sorted(got)}")
        print(f"FAIL — registry mismatch")
    mats = load_config_bundle().materials.materials
    print(f"{'material':24s} {'overlap':>8s} {'feature':>8s} {'int.radius':>10s}")
    signed = {
        "basalt_slab": (10, 15, 10),
        "cast_concrete_c35_45": (15, 25, 10),
        "bronze_cast": (5, 2, 3),
        "stainless_316l_sheet": (3, "wall", "wall"),
    }
    for mid, (jo, mf, mr) in sorted(signed.items()):
        m = mats[mid]
        actual = (m.joint_overlap_mm, m.min_feature_mm, m.min_internal_radius_mm)
        print(f"{mid:24s} {str(actual[0]):>8s} {str(actual[1]):>8s} {str(actual[2]):>10s}")
        if actual != (jo, mf, mr):
            failures.append(f"{mid}: envelope {actual} != signed {(jo, mf, mr)}")
            print(f"FAIL — {mid} does not match the signed sheet")
    s = mats["stainless_316l_sheet"]
    print(f"316L formula floors at wall=5: feature {s.min_feature_floor_mm(5):g} mm, "
          f"radius {s.min_internal_radius_floor_mm(5):g} mm")
    if s.min_feature_floor_mm(5) != 5 or s.min_internal_radius_floor_mm(5) != 5:
        failures.append("316L formula floors broken")
    print(f"{PASS if not failures else FAIL} — section 1")

    # ------------------------------------------------------------------
    _section(2, "ADR-030 — the registry is the ceiling on capability")
    from app.geometry.ast_gate import ALLOWED_IMPORT_ROOTS, check_program

    print(f"AST whitelist: {sorted(ALLOWED_IMPORT_ROOTS)}")
    if ALLOWED_IMPORT_ROOTS != frozenset({"registry", "math"}):
        failures.append(f"AST whitelist is {sorted(ALLOWED_IMPORT_ROOTS)}")
        print("FAIL — whitelist must be exactly {registry, math}")
    banned = "from build123d import Pos\n\ndef build(spec):\n    return None, {}, 0\n"
    reason = check_program(banned)
    print(f"build123d import -> {reason!r}")
    if reason is None or "build123d" not in reason:
        failures.append("AST gate accepted a build123d import")
        print("FAIL — build123d import must be rejected")
    legal = ("import registry\nimport math\n\n"
             "def build(spec):\n"
             "    solid, validated = registry.cascade_fountain({}, seed=0)\n"
             "    return solid, validated.canonical_dict(), 0\n")
    reason = check_program(legal)
    print(f"registry+math program -> {'accepted' if reason is None else reason!r}")
    if reason is not None:
        failures.append(f"AST gate rejected the legal program: {reason}")
    print(f"{PASS if not failures else FAIL} — section 2")

    # ------------------------------------------------------------------
    _section(3, "PHASE 2 CANONICAL HASH — asserted explicitly (sheet Part 5)")
    from app.geometry.exporters import export_step
    from app.geometry.kernel import step_timestamp_for
    from app.geometry.registry import cascade_fountain

    solid, validated = cascade_fountain({}, seed=PHASE2_CANONICAL_SEED)
    print(f"column_wall_mm resolved: {validated.column_wall_mm:g} "
          f"(= basin_wall_mm {validated.basin_wall_mm:g})")
    step_path = workdir / "cascade_canonical.step"
    sha = export_step(solid, step_path, step_timestamp_for(PHASE2_CANONICAL_SEED))
    print(f"canonical STEP sha256: {sha}")
    print(f"expected  (Phase 2) : {PHASE2_CANONICAL_STEP_SHA256}")
    if sha != PHASE2_CANONICAL_STEP_SHA256:
        failures.append("Phase 2 canonical STEP hash CHANGED — Amendment 1 broken")
        print("FAIL — the per-member wall change moved geometry")
    else:
        print(f"{PASS} — section 3: per-member walls, zero geometry drift")

    # ------------------------------------------------------------------
    _section(4, "CONSTRAINT BATTERY — refusals with real numbers")
    from app.geometry.assembly import assemble
    from _assembly_build_once import GATE_PLAN  # scripts/ is on sys.path
    import copy

    def plan(edits):
        p = copy.deepcopy(GATE_PLAN)
        for (idx, key), value in edits.items():
            if key == "joint":
                p[idx]["joint"].update(value)
            else:
                p[idx]["parameters"].update(value)
        return p

    _expect_violation(
        failures, "overlap under the material floor (constraint 9)",
        lambda: assemble(plan({(1, "joint"): {"overlap_mm": 5}})),
        "overlap_mm=5 < the 10 mm floor", "ADR-029",
    )
    _expect_violation(
        failures, "tangent knife edge through the basin floor (ADR-029)",
        lambda: assemble(plan({(2, "joint"): {"overlap_mm": 50}})),
        "TANGENT", "ADR-029",
    )
    _expect_violation(
        failures, "undeclared interference through the basin floor",
        lambda: assemble(plan({(2, "joint"): {"overlap_mm": 55}})),
        "WITHOUT a declared joint",
    )
    _expect_violation(
        failures, "insert punching through the parent floor",
        lambda: assemble(plan({(2, "joint"): {"overlap_mm": 70}})),
        "punch through",
    )
    _expect_violation(
        failures, "insert that does not fit the parent interior",
        lambda: assemble(plan({(2, "parameters"): {"diameter_mm": 500}})),
        "does not fit inside", "min_clearance_mm",
    )
    # Needle updated 2026-08-26 (ADR-053): this same floating body is now
    # refused EARLIER by the seat-bearing check, with the arithmetic
    # (-100.0 mm seat) instead of the late B-rep interference proof. The
    # protection is unchanged — the refusal moved left; the B-rep proof
    # remains in the assembler as the construction-level backstop.
    _expect_violation(
        failures, "floating body (declared joint never touches)",
        lambda: assemble([
            {"element_id": "p1", "primitive": "plinth",
             "parameters": {"top_diameter_mm": 500, "height_mm": 300,
                            "wall_mm": 100,
                            "material_id": "cast_concrete_c35_45"}},
            {"element_id": "c1", "primitive": "sculptural_column",
             "parameters": {"diameter_mm": 100, "height_mm": 300,
                            "material_id": "bronze_cast"},
             "joint": {"type": "stack_on", "parent": "p1"}},
        ]),
        "radial seat", "15 mm floor",
    )
    solid_plinth = [{"element_id": "p1", "primitive": "plinth",
                     "parameters": {"top_diameter_mm": 1000, "height_mm": 1000,
                                    "material_id": "basalt_slab"}}]
    _expect_violation(
        failures, "2,121 kg solid plinth vs a 2,000 kg crane (sheet §4.2)",
        lambda: assemble(solid_plinth, fabrication={"max_lift_kg": 2000}),
        "max_lift_kg 2000", "hollowing",
    )
    hollow_plinth = [{"element_id": "p1", "primitive": "plinth",
                      "parameters": {"top_diameter_mm": 1000, "height_mm": 1000,
                                     "wall_mm": 180,
                                     "material_id": "basalt_slab"}}]
    _, m = assemble(hollow_plinth, fabrication={"max_lift_kg": 2000})
    hollow_mass = m["elements"][0]["mass_kg"]
    print(f"ok — the SAME plinth hollowed to 180 mm: {hollow_mass:.1f} kg "
          "passes the same crane (hollowing, not shrinking)")
    if not (1240 < hollow_mass < 1265):
        failures.append(f"hollow plinth mass {hollow_mass:.1f} kg outside §4.2 arithmetic")
    _expect_violation(
        failures, "element bigger than max_module_m (segmentation is slice C)",
        lambda: assemble(solid_plinth, fabrication={"max_module_m": 0.8}),
        "max_module_m 0.8", "slice C",
    )
    print(f"{PASS if not failures else FAIL} — section 4")

    # ------------------------------------------------------------------
    _section(5, "THE GATE COMPOSITION — three primitives, ONE watertight body")
    from app.geometry.exporters import export_glb
    from app.geometry.validate import validate_assembly

    solid, manifest = assemble(copy.deepcopy(GATE_PLAN), seed=7)
    brep_bodies = len(solid.solids())
    print(f"primitives composed: "
          + ", ".join(f"{e['element_id']}({e['primitive']})"
                      for e in manifest["elements"]))
    print(f"body_count (B-rep): {brep_bodies}")
    for j in manifest["joints"]:
        print(f"joint {j['child']} -{j['type']}-> {j['parent']}: overlap "
              f"{j['overlap_mm']:g} mm (floor {j['floor_mm']:g}), "
              f"intersection {j['intersection_volume_mm3']:.1f} mm3")
    vc = manifest["volume_conservation"]
    print(f"volume conservation: members {vc['sum_member_volumes_mm3']:.1f} - "
          f"intersections {vc['sum_joint_intersections_mm3']:.1f} vs fused "
          f"{vc['assembly_volume_mm3']:.1f} mm3 "
          f"(delta {vc['delta_pct']:.4f}% of {vc['tolerance_pct']:g}%)")
    glb_path = workdir / "gate_assembly.glb"
    export_glb(solid, glb_path)
    report = validate_assembly(glb_path, manifest)
    for row in report.check_rows():
        print(f"  {row['check']:24s} {str(row['value']):<52s} "
              f"{'ok' if row['passed'] else 'FAIL'}")
    if brep_bodies != 1:
        failures.append(f"B-rep body count {brep_bodies}")
    if not report.passed:
        bad = [r["check"] for r in report.check_rows() if not r["passed"]]
        failures.append(f"assembly validation failed: {bad}")
        print(f"FAIL — section 5: {bad}")
    else:
        print(f"{PASS} — section 5: one watertight assembly from three primitives")

    # ------------------------------------------------------------------
    _section(6, "ASSEMBLY DETERMINISM — two separate processes")
    seed = 42
    hashes: dict[str, str] = {}
    paths = {"run A": workdir / "assembly_a.step",
             "run B": workdir / "assembly_b.step"}
    for label, path in paths.items():
        proc = subprocess.run(
            [sys.executable,
             str(REPO_ROOT / "scripts" / "_assembly_build_once.py"),
             str(path), str(seed)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            print(f"FAIL — {label} subprocess exited {proc.returncode}")
            print(proc.stdout)
            print(proc.stderr)
            failures.append(f"assembly determinism {label}: subprocess failed")
            continue
        print(f"{label}: " + proc.stdout.strip().replace("\n", "\n  "))
        sha_line = [l for l in proc.stdout.splitlines() if l.startswith("sha256=")]
        hashes[label] = sha_line[0].split("=", 1)[1] if sha_line else "<missing>"
    if len(hashes) == 2:
        identical = paths["run A"].read_bytes() == paths["run B"].read_bytes()
        print(f"byte-identical: {identical}")
        if hashes["run A"] == hashes["run B"] and identical:
            print(f"{PASS} — section 6: same plan + seed -> byte-identical "
                  "assembly STEP")
        else:
            failures.append(
                f"assembly determinism: A={hashes['run A']} B={hashes['run B']}")
            print("FAIL — the two assembly STEP files differ")

    # ------------------------------------------------------------------
    _section(7, "VERDICT")
    return _verdict(failures)


def _verdict(failures: list[str]) -> int:
    if failures:
        print(f"{FAIL} — {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"{PASS} — Phase 6 slice A1 auto gate: all sections passed at $0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
