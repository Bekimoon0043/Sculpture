"""gate_lf103a_auto.py — LF-103A: the export boundary enforces the verdict.

$0, offline, non-interactive, and HERMETIC (owner amendment 4): every
design, validation row, export and package this gate creates lives in a
temporary database and a temporary artifact root. Section [9] proves the
real configured database and the real data/exports tree are byte-for-byte
untouched. The historical-package check runs on a fixture this gate seals
itself — no live design id is referenced.

Sections:
  [1] classifier truth table   [2] role ownership map
  [3] REFUSED end-to-end       [4] PRE-FABRICATION end-to-end
  [5] byte determinism         [6] CLEAN branch (builder-level, signed)
  [7] builder bypass closed    [8] LEGACY_UNCLASSIFIED fails closed
  [9] hermeticity proof

Exit 0 = PASS, 1 = FAIL. Every check prints its real numbers.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

FAILURES: list[str] = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" :: {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def _section(n: int, title: str) -> None:
    print(f"\n[{n}] {title}")
    print("-" * 72)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_listing(root: Path) -> list[tuple[str, int, str]]:
    if not root.exists():
        return []
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out.append((p.relative_to(root).as_posix(), p.stat().st_size, _sha(p)))
    return out


def main() -> int:
    print("=" * 72)
    print("LF-103A AUTO GATE — the export boundary enforces the gate verdict")
    print("=" * 72)

    # Record the REAL surfaces before any override, for section [9].
    real_db = Path(os.environ.get("LUXURYFORM_DB", "data/luxuryform.db"))
    real_data = Path(os.environ.get("LUXURYFORM_DATA_DIR", "data"))
    real_db_sha = _sha(real_db) if real_db.exists() else None
    real_exports_before = _tree_listing(real_data / "exports")

    # Hermetic overrides BEFORE the app builds its engine.
    tmp = Path(tempfile.mkdtemp(prefix="lf103a_gate_"))
    os.environ["LUXURYFORM_DB"] = str(tmp / "gate.db")
    os.environ["LUXURYFORM_DATA_DIR"] = str(tmp / "data")

    from app.db.database import reset_default_db
    reset_default_db()

    from fastapi.testclient import TestClient
    from app.main import app
    from app.geometry.export_formats import ExportResult
    from app.geometry.luxexchange import PackageBuilder, build_luxexchange_package
    from app.geometry.package_class import (
        CLASS_CLEAN, CLASS_PRE_FABRICATION, CLASS_REFUSED, LEGACY_UNCLASSIFIED,
        PackageRefused, classify_reports, read_sealed_package_class, role_for,
    )

    def layered(gate, status, signed=False, basis=None):
        r = {"schema": "layered_validation_report_v2", "gate_name": gate,
             "status": status, "gate_profile_id": "public_plaza",
             "gate_profiles_version": 1, "profile_signed_off": signed,
             "checks": [{"check": f"{gate}.x", "status": status,
                         "on_violation": "fail", "value": 1, "limit": 2,
                         "units": "mm", "basis": "gate_profiles.yaml:x",
                         "message": "gate fixture row"}]}
        if basis is not None:
            r["validation_basis"] = basis
        return r

    def full(status, signed=False, basis=None):
        return {"assembly_mesh": {"passed": True, "watertight": True},
                "structure_static_v1": layered("structure_static_v1", status, signed, basis),
                "hydraulics": layered("hydraulics", status, signed, basis),
                "fabrication": layered("fabrication", status, signed, basis)}

    # -----------------------------------------------------------------
    _section(1, "CLASSIFIER TRUTH TABLE — from persisted evidence only")
    cases = [
        ("all pass, unsigned", full("pass"), None, CLASS_PRE_FABRICATION),
        ("all pass, signed, shared basis, hash ok", full("pass", True, "b1"),
         True, CLASS_CLEAN),
        ("signed but NO basis identity", full("pass", True), True,
         CLASS_PRE_FABRICATION),
        ("needs_input", full("needs_input"), None, CLASS_PRE_FABRICATION),
        ("any fail", full("fail"), True, CLASS_REFUSED),
        ("empty evidence", {}, True, CLASS_PRE_FABRICATION),
    ]
    for name, reports, hash_ok, expected in cases:
        got = classify_reports(reports, geometry_hash_matches=hash_ok).package_class
        _check(f"{name} -> {expected}", got == expected, f"got {got}")
    missing = full("pass", True, "b1")
    del missing["structure_static_v1"]
    _check("missing structural gate -> pre_fabrication (worst_status([]) trap)",
           classify_reports(missing, geometry_hash_matches=True).package_class
           == CLASS_PRE_FABRICATION)
    mixed = full("pass", True, "b1")
    mixed["hydraulics"]["gate_profile_id"] = "indoor_lobby"
    _check("mixed profile ids -> pre_fabrication",
           classify_reports(mixed, geometry_hash_matches=True).package_class
           == CLASS_PRE_FABRICATION)

    # -----------------------------------------------------------------
    _section(2, "ROLE OWNERSHIP — deterministic map, no invented disciplines")
    _check("structural check -> structural engineer",
           role_for("structure_static_v1", "overturning_safety_factor")
           == "structural engineer")
    _check("bearing -> geotechnical + structural",
           "geotechnical" in role_for("structure_static_v1",
                                      "ground_bearing_pressure_kpa"))
    _check("rigging -> rigging reviewer",
           role_for("fabrication", "rigging_declared") == "rigging reviewer")
    _check("unknown -> 'qualified professional review required'",
           role_for("mystery_gate", "anything")
           == "qualified professional review required")

    # -----------------------------------------------------------------
    _section(3, "REFUSED — a failed design cannot package or serve CAD")
    payload = {
        "seed": 7,
        "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0},
        "elements": [
            {"element_id": "plinth_01", "primitive": "plinth",
             "parameters": {"top_diameter_mm": 2200, "height_mm": 300,
                            "wall_mm": 120}},
            {"element_id": "basin_01", "primitive": "basin_round",
             "parameters": {"diameter_mm": 2000, "height_mm": 450,
                            "wall_mm": 40, "floor_mm": 160,
                            "min_clearance_mm": 220},
             "joint": {"type": "stack_on", "parent": "plinth_01"}},
        ],
    }
    with TestClient(app) as client:
        failing = dict(payload)
        failing["fabrication"] = {"max_lift_kg": 50}
        r = client.post("/api/geometry/assembly/build", json=failing)
        _check("a failing design still BUILDS (ADR-034)", r.status_code == 200,
               f"http {r.status_code}")
        fail_id = r.json()["design_id"]
        _check("its rollup is fail", r.json()["overall_status"] == "fail")

        r = client.post(f"/api/geometry/assembly/{fail_id}/exports")
        _check("package POST refuses with 409", r.status_code == 409)
        _check("the refusal names the failing check with real numbers",
               "mass_kg" in r.json().get("detail", ""),
               r.json().get("detail", "")[:90])
        r = client.get("/api/geometry/assembly/latest.step")
        _check("latest.step (fabrication-capable) refuses", r.status_code == 409)
        r = client.get(f"/api/geometry/assembly/{fail_id}.glb")
        _check("mesh GLB stays served, marked DIAGNOSTIC",
               r.status_code == 200 and "DIAGNOSTIC-NOT-FOR-FABRICATION"
               in r.headers.get("content-disposition", ""))
        r = client.get(f"/api/geometry/assembly/{fail_id}/scene.glb")
        _check("the viewport scene stream is untouched", r.status_code == 200)

        # -------------------------------------------------------------
        _section(4, "PRE-FABRICATION — marked, warranted, verifiable")
        r = client.post("/api/geometry/assembly/build", json=payload)
        ok_id = r.json()["design_id"]
        step_path = Path(
            client.get(f"/api/geometry/assembly/{ok_id}/manifest")
            .json()["artifacts"]["step_path"])
        r = client.post(f"/api/geometry/assembly/{ok_id}/exports")
        _check("export POST returns 200 (PRE-FAB is a produced deliverable)",
               r.status_code == 200)
        _check("response carries package_class",
               r.json().get("package_class") == "pre_fabrication")
        digest_1 = r.json()["content_digest"]

        z = client.get(f"/api/geometry/assembly/{ok_id}/luxexchange.zip")
        _check("package download filename says PRE-FABRICATION",
               "PRE-FABRICATION" in z.headers.get("content-disposition", ""))
        pkg = tmp / "pkg.zip"
        pkg.write_bytes(z.content)
        with zipfile.ZipFile(pkg) as zf:
            names = set(zf.namelist())
            manifest = json.loads(zf.read("luxexchange_v1.json"))
            dxf_name = next(n for n in names if n.endswith(".dxf"))
            dxf_bytes = zf.read(dxf_name)
            svg_name = next(n for n in names if n.endswith(".svg"))
            svg_bytes = zf.read(svg_name)
            warrant = zf.read("ENGINEERING_WARRANT.txt").decode("utf-8")
        _check("manifest package_class sealed",
               manifest.get("package_class") == "pre_fabrication")
        _check("warrant present and honest",
               "NOT fabrication-ready" in warrant and ok_id in warrant)
        _check("every exports/ entry is marked in its own filename",
               all("PRE-FABRICATION" in n for n in names
                   if n.startswith("exports/")),
               f"{sum(1 for n in names if n.startswith('exports/'))} entries")
        _check("the DXF drawing carries the printed notice",
               b"PRE-FABRICATION - NOT FOR CONSTRUCTION" in dxf_bytes
               and b"PREFAB_NOTICE" in dxf_bytes)
        _check("the SVG drawing carries the printed notice",
               b"PRE-FABRICATION - NOT FOR CONSTRUCTION" in svg_bytes)

        extract = tmp / "extract"
        with zipfile.ZipFile(pkg) as zf:
            zf.extractall(extract)
        proc = subprocess.run(
            [sys.executable, str(extract / "verify_luxexchange.py")],
            capture_output=True, text=True, cwd=str(extract))
        _check("the shipped verifier passes on a marked package",
               proc.returncode == 0,
               proc.stdout.strip().splitlines()[-1] if proc.stdout else "")

        r = client.get(f"/api/geometry/assembly/{ok_id}/exports/STEP/download")
        _check("CAD download filename marked, bytes CANONICAL and untouched",
               "PRE-FABRICATION" in r.headers.get("content-disposition", "")
               and r.content == step_path.read_bytes(),
               f"{len(r.content)} bytes")

        # -------------------------------------------------------------
        _section(5, "DETERMINISM — two seals, byte-identical, warrant included")
        r2 = client.post(f"/api/geometry/assembly/{ok_id}/exports")
        _check("content digest identical across re-export",
               r2.json()["content_digest"] == digest_1, digest_1[:24] + "...")
        z2 = client.get(f"/api/geometry/assembly/{ok_id}/luxexchange.zip")
        _check("the package ZIP is byte-identical",
               z2.content == pkg.read_bytes(), f"{len(z2.content)} bytes")

        # -------------------------------------------------------------
        _section(8, "LEGACY_UNCLASSIFIED — an old zip fails closed, untouched")
        r = client.post("/api/geometry/assembly/build", json=payload)
        legacy_id = r.json()["design_id"]
        legacy_dir = Path(os.environ["LUXURYFORM_DATA_DIR"]) / "exports" / legacy_id
        builder = PackageBuilder(seed=7)
        builder.add_json("luxexchange_v1.json", {"schema": "luxexchange_v1"})
        legacy_zip = legacy_dir / "luxexchange_v1.zip"
        builder.seal(legacy_zip, provenance={})
        before = legacy_zip.read_bytes()
        _check("fixture zip reads as LEGACY_UNCLASSIFIED",
               read_sealed_package_class(legacy_zip) == LEGACY_UNCLASSIFIED)
        r = client.get(f"/api/geometry/assembly/{legacy_id}/luxexchange.zip")
        _check("download refuses with 409", r.status_code == 409)
        _check("the refusal carries the one re-export action",
               "Re-export" in r.json().get("detail", "")
               or "re-seal" in r.json().get("detail", ""))
        _check("the original bytes are untouched",
               legacy_zip.read_bytes() == before, f"{len(before)} bytes")

    # -----------------------------------------------------------------
    _section(6, "CLEAN — builder-level only, signed + shared basis + hash")
    fake_step = tmp / "clean.step"
    fake_step.write_bytes(b"ISO-10303-21; gate fixture step;")
    step_sha = _sha(fake_step)
    clean_exports = [ExportResult(format="STEP", status="included", tier="cad",
                                  purpose="p", path=fake_step, sha256=step_sha,
                                  bytes=fake_step.stat().st_size)]
    path, manifest, _ = build_luxexchange_package(
        tmp / "clean.zip", seed=1,
        design={"design_id": "d-clean", "seed": 1, "geometry_hash": step_sha},
        request_payload={}, assembly_manifest={},
        validation_reports=full("pass", True, "basis-1"),
        exports=clean_exports)
    _check("signed+basis+hash seals CLEAN", manifest["package_class"] == CLASS_CLEAN)
    with zipfile.ZipFile(path) as zf:
        _check("a clean package carries no warrant and unmarked names",
               "ENGINEERING_WARRANT.txt" not in zf.namelist()
               and "exports/clean.step" in zf.namelist())
    path2, manifest2, _ = build_luxexchange_package(
        tmp / "clean2.zip", seed=1,
        design={"design_id": "d-clean", "seed": 1,
                "geometry_hash": "not-the-step-sha"},
        request_payload={}, assembly_manifest={},
        validation_reports=full("pass", True, "basis-1"),
        exports=clean_exports)
    _check("a geometry-hash mismatch drops CLEAN to PRE-FABRICATION",
           manifest2["package_class"] == CLASS_PRE_FABRICATION)

    # -----------------------------------------------------------------
    _section(7, "BYPASS CLOSED — the builder itself refuses")
    try:
        build_luxexchange_package(
            tmp / "bypass.zip", seed=1,
            design={"design_id": "d-bypass", "seed": 1},
            request_payload={}, assembly_manifest={},
            validation_reports=full("fail"), exports=[])
        _check("direct builder call with FAIL evidence raises", False)
    except PackageRefused as exc:
        _check("direct builder call with FAIL evidence raises", True,
               str(exc)[:70])
    _check("no bypass zip was written", not (tmp / "bypass.zip").exists())
    _, bare_manifest, _ = build_luxexchange_package(
        tmp / "bare.zip", seed=1, design={"design_id": "d-bare", "seed": 1},
        request_payload={}, assembly_manifest={},
        validation_reports={}, exports=[])
    _check("absent evidence defaults PRE-FABRICATION, never clean",
           bare_manifest["package_class"] == CLASS_PRE_FABRICATION)

    # -----------------------------------------------------------------
    _section(9, "HERMETICITY — the real database and exports are untouched")
    if real_db_sha is None:
        _check("real DB did not spring into existence", not real_db.exists(),
               str(real_db))
    else:
        _check("real database byte-identical",
               real_db.exists() and _sha(real_db) == real_db_sha,
               f"{real_db} sha {real_db_sha[:16]}...")
    _check("real data/exports tree identical "
           f"({len(real_exports_before)} files)",
           _tree_listing(real_data / "exports") == real_exports_before)

    # -----------------------------------------------------------------
    print("\n" + "=" * 72)
    if FAILURES:
        print(f"FAIL — LF-103A auto gate: {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        print("=" * 72)
        return 1
    print("PASS — LF-103A auto gate: FAILED never packages, PRE-FABRICATION "
          "is marked+warranted+deterministic, CLEAN needs a signed shared "
          "basis, legacy fails closed, bypass closed — all at $0, hermetic.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
