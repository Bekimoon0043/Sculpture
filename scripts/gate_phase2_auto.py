#!/usr/bin/env python3
"""PHASE 2 AUTO GATE — LuxuryForm Studio v1 [ADD-2, non-interactive half].

Runs on the host (``python scripts/gate_phase2_auto.py`` from the repo root,
venv active, build123d+trimesh installed) or inside Docker
(``docker compose exec backend python scripts/gate_phase2_auto.py``).
No stdin, no prompts; prints a numbered transcript; exits 0 only on PASS.

  1. CONFIG & FRESH GATE DB
  2. DETERMINISM [Amendment 1] — same spec+seed built in TWO SEPARATE
     PROCESSES; both STEP sha256 printed; byte-identical or FAIL.
  3. CONSTRAINTS [ADD-4] — hard-constraint breaches raise violations whose
     messages carry the REAL numbers (digit regex enforced); texts printed.
  4. VALIDATION — trimesh on the exported GLB; every real number printed;
     watertight MUST be true; volume cross-check prints BOTH numbers.
  5. GLB ROUND-TRIP — trimesh bounds match build123d bounds within 1 mm.
  6. API ROUND-TRIP [ADD-3] — FastAPI TestClient (in-process, no ports):
     defaults -> build tiers=3 -> build tiers=4 -> volume/hash/validation
     changed -> latest.glb 200 with glTF magic. Before/after volumes printed.
  7. VERDICT — PASS (exit 0) or FAIL with exact reasons (exit 1).

The OPERATOR half of the gate (browser eye-check) is
docs/operator/gate_phase2_visual.md.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

GATE_DB_PATH = REPO_ROOT / "data" / "gate_run_phase2.db"

PASS = "PASS"
FAIL = "FAIL"


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/7] {title}")
    _hline()


def main() -> int:
    import logging

    logging.getLogger("luxuryform.config").setLevel(logging.CRITICAL)
    failures: list[str] = []

    # ------------------------------------------------------------------
    _section(1, "CONFIG & FRESH GATE DB")
    from app.core.config import ConfigError, load_config_bundle
    from app.db.database import Database

    try:
        bundle = load_config_bundle()
    except ConfigError as exc:
        print(f"FAIL — config: {exc}")
        return _verdict([f"config: {exc}"])

    print(f"materials loaded: {', '.join(sorted(bundle.materials.materials))}")
    for mid, m in sorted(bundle.materials.materials.items()):
        print(
            f"  {mid}: density={m.density_kg_per_m3:g} kg/m3, "
            f"min_wall={m.min_wall_mm:g} mm"
        )

    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(GATE_DB_PATH) + suffix)
        if candidate.exists():
            candidate.unlink()
    GATE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = Database(GATE_DB_PATH)
    db.init_db()
    print(f"gate DB: fresh {GATE_DB_PATH} (deleted first, schema v2 applied)")
    from sqlalchemy import text as sql_text

    with db.engine.connect() as conn:
        versions = conn.execute(
            sql_text("SELECT version, note FROM schema_migrations ORDER BY version")
        ).all()
    for version, note in versions:
        print(f"schema_migrations: v{version} — {note}")

    import build123d
    import trimesh

    print(f"build123d {build123d.__version__} / trimesh {trimesh.__version__}")
    print(f"{PASS} — section 1")

    workdir = Path(tempfile.mkdtemp(prefix="luxuryform_gate2_"))

    # ------------------------------------------------------------------
    _section(2, "DETERMINISM PROOF (Amendment 1) — two separate processes")
    seed = 42
    step_a = workdir / "determinism_run_a.step"
    step_b = workdir / "determinism_run_b.step"
    hashes: dict[str, str] = {}
    for label, path in (("run A", step_a), ("run B", step_b)):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "_cascade_build_once.py"),
             str(path), str(seed)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(f"FAIL — {label} subprocess exited {proc.returncode}")
            print(proc.stdout)
            print(proc.stderr)
            failures.append(f"determinism {label}: subprocess failed")
            continue
        print(proc.stdout.strip().replace("\n", "\n  "))
        sha_line = [l for l in proc.stdout.splitlines() if l.startswith("sha256=")]
        hashes[label] = sha_line[0].split("=", 1)[1] if sha_line else "<missing>"
    if len(hashes) == 2:
        print(f"STEP sha256 run A: {hashes['run A']}")
        print(f"STEP sha256 run B: {hashes['run B']}")
        identical = step_a.read_bytes() == step_b.read_bytes()
        print(f"byte-identical: {identical}")
        if hashes["run A"] == hashes["run B"] and identical:
            print(f"{PASS} — section 2: same spec + same seed -> byte-identical STEP")
        else:
            print("FAIL — the two STEP files differ")
            failures.append(
                f"determinism: hashes differ A={hashes['run A']} B={hashes['run B']}"
            )

    # ------------------------------------------------------------------
    _section(3, "HARD CONSTRAINTS [ADD-4] — real numbers in every error")
    from app.geometry.registry import ConstraintViolation, validate_params

    constraint_cases = [
        (
            "basin too small",
            {"basin_diameter_mm": 2400, "tier_top_diameter_mm": 1000,
             "tier_diameter_step_mm": 800},
            ["basin_diameter_mm=2400"],
        ),
        (
            "wall below material minimum",
            {"basin_wall_mm": 10},
            ["basin_wall_mm=10", "material minimum 20"],
        ),
        (
            "lip fillet too deep for dish",
            {"dish_depth_mm": 40, "lip_fillet_mm": 25, "basin_wall_mm": 30},
            ["lip_fillet_mm=25"],
        ),
    ]
    section3_ok = True
    for title, params, needles in constraint_cases:
        try:
            validate_params(params)
            print(f"FAIL — {title}: no ConstraintViolation raised for {params}")
            failures.append(f"constraints: {title} did not raise")
            section3_ok = False
            continue
        except ConstraintViolation as exc:
            print(f"{title}: ConstraintViolation with {len(exc.violations)} violation(s):")
            for v in exc.violations:
                print(f"  - {v}")
            ok = all(any(n in v for v in exc.violations) for n in needles)
            digits = all(re.search(r"\d", v) for v in exc.violations)
            if not ok:
                print(f"FAIL — {title}: expected numbers {needles} in the messages")
                failures.append(f"constraints: {title} missing expected numbers")
                section3_ok = False
            if not digits:
                print(f"FAIL — {title}: a violation message carries no digits")
                failures.append(f"constraints: {title} message without real numbers")
                section3_ok = False
    if section3_ok:
        print(f"{PASS} — section 3")

    # ------------------------------------------------------------------
    _section(4, "VALIDATION — trimesh real numbers on the default build")
    from app.geometry import GeometryBuild, export_glb, export_step, validate_mesh

    params = validate_params({})
    build = GeometryBuild(seed=seed, params=params)
    solid = build.build()
    glb_path = workdir / "validation_cascade.glb"
    step_path = workdir / "validation_cascade.step"
    export_glb(solid, glb_path)
    step_sha = export_step(solid, step_path, build.step_timestamp)
    material = bundle.materials.materials[params.material_id]
    report = validate_mesh(
        glb_path, material, material_id=params.material_id,
        reference_volume_mm3=float(solid.volume),
    )
    print(f"default build: spec_hash={build.spec_hash}")
    print(f"canonical STEP sha256: {step_sha}")
    print("trimesh measured numbers:")
    for row in report.check_rows():
        verdict = "PASS" if row["passed"] else "FAIL"
        print(f"  [{verdict}] {row['check']}: {row['value']}")
    if report.volume_crosscheck:
        cc = report.volume_crosscheck
        print(
            f"  volume cross-check: trimesh {cc.trimesh_volume_mm3:.3f} mm3 vs "
            f"build123d {cc.build123d_volume_mm3:.3f} mm3 "
            f"(delta {cc.delta_pct:.4f}%, tolerance {cc.tolerance_pct:g}%)"
        )
    if report.watertight and report.passed:
        print(f"{PASS} — section 4: watertight=true, every check passed")
    else:
        print(f"FAIL — watertight={report.watertight} passed={report.passed}")
        failures.append("validation: default build failed mesh checks")

    # ------------------------------------------------------------------
    _section(5, "GLB ROUND-TRIP — trimesh bounds vs build123d bounds (1 mm)")
    # report.bounds_mm is already converted back to the CAD frame (mm, Z-up)
    # by validate_mesh; compare against the exact B-rep bounding box.
    mesh_min = tuple(report.bounds_mm[:3])
    mesh_max = tuple(report.bounds_mm[3:])
    bbox = solid.bounding_box()
    brep_min = (bbox.min.X, bbox.min.Y, bbox.min.Z)
    brep_max = (bbox.max.X, bbox.max.Y, bbox.max.Z)
    print(f"trimesh  bounds min: {[round(v, 3) for v in mesh_min]}")
    print(f"trimesh  bounds max: {[round(v, 3) for v in mesh_max]}")
    print(f"build123d bounds min: {[round(v, 3) for v in brep_min]}")
    print(f"build123d bounds max: {[round(v, 3) for v in brep_max]}")
    max_dev = max(
        abs(a - b)
        for a, b in zip(mesh_min + mesh_max, brep_min + brep_max)
    )
    print(f"max bounds deviation: {max_dev:.4f} mm (tolerance 1.0 mm)")
    if max_dev <= 1.0:
        print(f"{PASS} — section 5")
    else:
        failures.append(f"glb round-trip: bounds deviate {max_dev:.4f} mm > 1 mm")

    # ------------------------------------------------------------------
    _section(6, "API ROUND-TRIP [ADD-3] — FastAPI TestClient, in-process")
    from app.db.database import reset_default_db
    os.environ["LUXURYFORM_DB"] = str(GATE_DB_PATH)
    os.environ["LUXURYFORM_DATA_DIR"] = str(workdir / "api_data")
    reset_default_db()
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/geometry/cascade/defaults")
        print(f"GET /api/geometry/cascade/defaults -> {resp.status_code}")
        if resp.status_code != 200 or "tiers" not in resp.json().get("parameters", {}):
            failures.append("api: defaults endpoint broken")
        else:
            print(f"  {len(resp.json()['parameters'])} parameters served")

        r3 = client.post("/api/geometry/cascade/build",
                         json={"parameters": {"tiers": 3}, "seed": seed})
        r4 = client.post("/api/geometry/cascade/build",
                         json={"parameters": {"tiers": 4}, "seed": seed})
        if r3.status_code != 200 or r4.status_code != 200:
            print(f"FAIL — builds returned {r3.status_code}/{r4.status_code}")
            print(r3.text[:500])
            print(r4.text[:500])
            failures.append("api: build POST failed")
        else:
            b3, b4 = r3.json(), r4.json()
            v3 = b3["validation"]["volume_mm3"]
            v4 = b4["validation"]["volume_mm3"]
            print(f"volume tiers=3: {v3:.3f} mm3   step sha256: {b3['step_sha256']}")
            print(f"volume tiers=4: {v4:.3f} mm3   step sha256: {b4['step_sha256']}")
            print(f"server build_ms: {b3['build_ms']:.1f} / {b4['build_ms']:.1f} ms")
            checks = [
                ("volume changed", v3 != v4),
                ("spec_hash changed", b3["spec_hash"] != b4["spec_hash"]),
                ("step hash changed", b3["step_sha256"] != b4["step_sha256"]),
                (
                    "validation numbers changed",
                    b3["validation"]["surface_area_mm2"]
                    != b4["validation"]["surface_area_mm2"],
                ),
            ]
            for label, ok in checks:
                print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
                if not ok:
                    failures.append(f"api: {label} — not true")
        glb_resp = client.get("/api/geometry/cascade/latest.glb")
        magic_ok = glb_resp.status_code == 200 and glb_resp.content[:4] == b"glTF"
        print(
            f"GET /api/geometry/cascade/latest.glb -> {glb_resp.status_code}, "
            f"{len(glb_resp.content)} bytes, glTF magic: "
            f"{glb_resp.content[:4]!r}"
        )
        if not magic_ok:
            failures.append("api: latest.glb missing or bad magic")
        else:
            print(
                f"{PASS} — section 6: backend rebuild path works; if the browser "
                "does not update, the bug is isolated to the frontend"
            )
    reset_default_db()

    # ------------------------------------------------------------------
    _section(7, "VERDICT")
    return _verdict(failures)


def _verdict(failures: list[str]) -> int:
    if failures:
        print(f"PHASE 2 AUTO GATE: FAIL — {'; '.join(failures)}")
        return 1
    print("PHASE 2 AUTO GATE: PASS")
    print()
    print("Next: the operator visual gate — docs/operator/gate_phase2_visual.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
