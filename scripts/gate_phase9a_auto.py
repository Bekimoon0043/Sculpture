#!/usr/bin/env python3
"""Phase 9A auto gate — export formats and the LUXEXCHANGE package. $0, forever.

Non-interactive, NO NETWORK REQUIRED. Exit 0 = PASS, 1 = FAIL.

    docker compose exec backend python scripts/gate_phase9a_auto.py

What it proves, in the operator's terms:

  1. Ten real formats come out of the libraries already in the image.
  2. The same design always exports to the same bytes.
  3. The package checks itself — with plain Python, on someone else's machine.
  4. Tampering is caught.
  5. What is missing says why, in words the operator can act on.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

PASS, FAIL = "PASS", "FAIL"
SEED = 7

ELEMENTS = [
    {"element_id": "plinth_01", "primitive": "plinth",
     "parameters": {"top_diameter_mm": 2200, "height_mm": 300, "wall_mm": 120}},
    {"element_id": "basin_01", "primitive": "basin_round",
     "parameters": {"diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
                    "floor_mm": 160, "min_clearance_mm": 220},
     "joint": {"type": "stack_on", "parent": "plinth_01"}},
    {"element_id": "column_01", "primitive": "sculptural_column",
     "parameters": {"diameter_mm": 360, "height_mm": 900, "bore_mm": 150},
     "joint": {"type": "concentric_insert", "parent": "basin_01"}},
]


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/6] {title}")
    _hline()


def _check(failures: list[str], label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{('  — ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def _export(root: Path, name: str):
    from app.geometry import assemble
    from app.geometry.export_formats import write_exports
    from app.geometry.exporters import export_glb, export_step
    from app.geometry.kernel import step_timestamp_for
    from app.geometry.luxexchange import build_luxexchange_package

    solid, manifest = assemble(ELEMENTS, seed=SEED, strict=False)
    out = root / name
    out.mkdir(parents=True, exist_ok=True)
    step, glb = out / "assembly.step", out / "assembly.glb"
    export_step(solid, step, step_timestamp_for(SEED))
    export_glb(solid, glb)
    results = write_exports(solid, out, step_path=step, glb_path=glb, seed=SEED)
    path, package_manifest, digest = build_luxexchange_package(
        out / "luxexchange_v1.zip", seed=SEED,
        design={"design_id": "gate", "seed": SEED},
        request_payload={"elements": ELEMENTS, "seed": SEED},
        assembly_manifest=manifest,
        validation_reports={"assembly_mesh": {"passed": True}},
        exports=results,
        costing=None, costing_unavailable_reason="not costed in this gate",
        provenance={"design_created_at": "2026-08-21T00:00:00+00:00"},
    )
    return results, path, package_manifest, digest


def main() -> int:
    failures: list[str] = []
    root = Path(tempfile.mkdtemp(prefix="luxform_gate9a_"))

    # -----------------------------------------------------------------
    _section(1, "FORMATS — what the installed libraries actually write")
    results, package_a, manifest_a, digest_a = _export(root, "a")
    by_format = {r.format: r for r in results}

    for fmt in ("STEP", "BREP", "STL", "DXF", "SVG", "GLB", "OBJ", "PLY"):
        r = by_format[fmt]
        _check(failures, f"{fmt} written from the {r.tier} tier",
               r.status == "included",
               f"{r.bytes} bytes" if r.status == "included" else (r.error or r.reason))
    included = [r for r in results if r.status == "included"]
    print(f"  note  {len(included)} formats produced, "
          f"{sum(r.bytes or 0 for r in included) / 1024:.0f} kB total")

    dxf = by_format["DXF"]
    _check(failures, "the DXF is a real drawing with named layers",
           set(dxf.notes.get("layers", {})) >= {"PLAN", "ELEVATION", "HIDDEN"},
           str(dxf.notes.get("layers")))

    # -----------------------------------------------------------------
    _section(2, "HONESTY — what is missing says why")
    # The Blender tier has TWO honest outcomes, and the gate accepts either
    # depending on whether the render worker is up. What it does not accept
    # is silence: a format that is missing without saying why.
    #
    #   worker down -> "unavailable", reason naming the command that fixes it
    #   worker up   -> "included", produced and downloadable, but NOT sealed
    #                  into the package, because two conversions of the same
    #                  design differ by a few timestamp bytes and the package
    #                  is guaranteed byte-reproducible (see section 3). The
    #                  manifest must say so per format rather than omit it.
    for fmt in ("USD", "USDZ", "FBX", "ABC"):
        r = by_format[fmt]
        if r.status == "included":
            entry = next((e for e in manifest_a["exports"]
                          if e["format"] == fmt), None)
            _check(failures,
                   f"{fmt} is produced and its exclusion from the ZIP is stated",
                   entry is not None
                   and entry.get("in_package") is False
                   and "byte-reproducible" in (entry.get("excluded_reason") or ""),
                   str(entry)[:110] if entry else "no manifest entry")
            continue
        _check(failures, f"{fmt} is unavailable, not silently omitted",
               r.status == "unavailable" and "render worker" in (r.reason or ""),
               (r.reason or "")[:70])
    _check(failures,
           "the manifest names every format omitted for non-reproducibility",
           isinstance(manifest_a.get("omitted_non_reproducible"), list),
           str(manifest_a.get("omitted_non_reproducible")))
    for fmt in ("DWG", "SKP"):
        r = by_format[fmt]
        _check(failures, f"{fmt} is declared impossible with a workaround",
               r.status == "impossible" and "README_DWG_SKP.txt" in (r.reason or ""))
    for fmt in ("DAE", "3MF"):
        r = by_format[fmt]
        if r.status == "included":
            print(f"  note  {fmt} is now available (optional library installed)")
            continue
        _check(failures, f"{fmt} names the missing optional package",
               r.status == "unavailable" and "pyproject.toml" in (r.reason or ""),
               (r.reason or "")[:70])

    # -----------------------------------------------------------------
    _section(3, "REPRODUCIBILITY — the same design gives the same bytes")
    _, package_b, _, digest_b = _export(root, "b")
    _check(failures, "content digest is identical across two exports",
           digest_a == digest_b, digest_a[:32] + "...")
    _check(failures, "the package ZIP is byte-identical",
           package_a.read_bytes() == package_b.read_bytes(),
           f"{package_a.stat().st_size} bytes")

    # -----------------------------------------------------------------
    _section(4, "CONTENTS — everything a recipient needs is in the box")
    with zipfile.ZipFile(package_a) as zf:
        names = set(zf.namelist())
        checksums = zf.read("CHECKSUMS.sha256").decode("utf-8")
    for required in ("luxexchange_v1.json", "provenance.json", "CHECKSUMS.sha256",
                     "verify_luxexchange.py", "README_DWG_SKP.txt",
                     "assembly_manifest.json", "exports/assembly.step",
                     "exports/assembly.dxf"):
        _check(failures, f"contains {required}", required in names)
    _check(failures, "provenance is excluded from the checksum set",
           "provenance.json" not in checksums,
           "so host and tool versions cannot change the design's identity")
    _check(failures, "no absolute host path leaks into the manifest",
           all(not (e.get("path") or "").startswith(("/", "C:"))
               for e in manifest_a["exports"]))

    # -----------------------------------------------------------------
    _section(5, "SELF-VERIFICATION — plain Python, no LuxuryForm install")
    extracted = root / "extracted"
    with zipfile.ZipFile(package_a) as zf:
        zf.extractall(extracted)
    proc = subprocess.run(
        [sys.executable, str(extracted / "verify_luxexchange.py")],
        capture_output=True, text=True, cwd=str(extracted),
    )
    _check(failures, "the shipped verifier passes on an intact package",
           proc.returncode == 0, proc.stdout.strip().splitlines()[-1] if proc.stdout else "")
    _check(failures, "it reports the same content digest",
           digest_a in proc.stdout)

    # -----------------------------------------------------------------
    _section(6, "TAMPER DETECTION")
    target = extracted / "exports" / "assembly.step"
    data = bytearray(target.read_bytes())
    data[len(data) // 2] ^= 0x01          # flip ONE bit
    target.write_bytes(bytes(data))
    proc = subprocess.run(
        [sys.executable, str(extracted / "verify_luxexchange.py")],
        capture_output=True, text=True, cwd=str(extracted),
    )
    _check(failures, "one flipped bit is caught", proc.returncode != 0)
    _check(failures, "the altered file is named", "exports/assembly.step" in proc.stdout)

    (extracted / "exports" / "assembly.stl").unlink()
    proc = subprocess.run(
        [sys.executable, str(extracted / "verify_luxexchange.py")],
        capture_output=True, text=True, cwd=str(extracted),
    )
    _check(failures, "a deleted file is caught", "MISSING" in proc.stdout)

    # -----------------------------------------------------------------
    print()
    _hline()
    print("VERDICT")
    _hline()
    print(f"  package: {package_a}")
    print(f"  digest : {digest_a}")
    if failures:
        print(f"{FAIL} — Phase 9A auto gate: {len(failures)} check(s) failed:")
        for item in failures:
            print(f"    - {item}")
        return 1
    print(f"{PASS} — Phase 9A auto gate: all sections passed at $0, no network.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
