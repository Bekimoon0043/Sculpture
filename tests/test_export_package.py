"""Phase 9A — export formats and the LUXEXCHANGE package.

The properties under test are the ones that make a package worth sending to
a fabricator:

* It is REPRODUCIBLE. The same design exports to the same bytes, so a hash
  identifies a design rather than an export run.
* It VERIFIES ITSELF, offline, with no LuxuryForm install — the verifier
  ships inside the ZIP and imports only the standard library.
* Its format list is HONEST. Four statuses, and the ones that are not
  produced say why in terms the operator can act on.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")
trimesh = pytest.importorskip("trimesh", reason="trimesh not installed")

from app.geometry import assemble  # noqa: E402
from app.geometry.canonicalize import (  # noqa: E402
    canonicalize_dxf_text,
    canonicalize_step_text,
)
from app.geometry.export_formats import (  # noqa: E402
    FORMAT_REGISTRY,
    write_exports,
)
from app.geometry.exporters import export_glb, export_step  # noqa: E402
from app.geometry.kernel import step_timestamp_for  # noqa: E402
from app.geometry.luxexchange import build_luxexchange_package  # noqa: E402

ELEMENTS = [
    {
        "element_id": "plinth_01",
        "primitive": "plinth",
        "parameters": {"top_diameter_mm": 2200, "height_mm": 300, "wall_mm": 120},
    },
    {
        "element_id": "basin_01",
        "primitive": "basin_round",
        "parameters": {
            "diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
            "floor_mm": 160, "min_clearance_mm": 220,
        },
        "joint": {"type": "stack_on", "parent": "plinth_01"},
    },
    {
        "element_id": "column_01",
        "primitive": "sculptural_column",
        "parameters": {"diameter_mm": 360, "height_mm": 900, "bore_mm": 150},
        "joint": {"type": "concentric_insert", "parent": "basin_01"},
    },
]

SEED = 7


def _build(tmp_path: Path, name: str = "run"):
    solid, manifest = assemble(ELEMENTS, seed=SEED, strict=False)
    out = tmp_path / name
    out.mkdir(parents=True, exist_ok=True)
    step, glb = out / "assembly.step", out / "assembly.glb"
    export_step(solid, step, step_timestamp_for(SEED))
    export_glb(solid, glb)
    results = write_exports(solid, out, step_path=step, glb_path=glb, seed=SEED)
    return solid, manifest, results, out


# ---------------------------------------------------------------------------
# Canonicalization — the two exporters that are non-deterministic on their own
# ---------------------------------------------------------------------------

def test_step_occurrence_counter_is_renumbered_per_file():
    """OCCT numbers occurrences from a PROCESS-global counter."""
    text = (
        "#224 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('7','=>[0:1:1:2]','',#5,#27,$);\n"
        "#225 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('9','=>[0:1:1:3]','',#5,#28,$);\n"
    )
    canonical = canonicalize_step_text(text)
    assert "NEXT_ASSEMBLY_USAGE_OCCURRENCE('1'" in canonical
    assert "NEXT_ASSEMBLY_USAGE_OCCURRENCE('2'" in canonical
    # Ids stay distinct within the file — that is the only job they have.
    assert canonicalize_step_text(canonical) == canonical


def test_step_canonicalization_touches_nothing_but_the_occurrence_id():
    text = (
        "FILE_NAME('Open CASCADE Shape Model','2026-01-01T00:00:07',('Author'),\n"
        "#10 = CARTESIAN_POINT('',(1.5,-2.25,3.0));\n"
        "#224 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('4','x','',#5,#27,$);\n"
    )
    canonical = canonicalize_step_text(text)
    assert "CARTESIAN_POINT('',(1.5,-2.25,3.0))" in canonical
    assert "2026-01-01T00:00:07" in canonical


def test_dxf_random_guids_and_wall_clock_are_replaced():
    text = (
        "  9\n$FINGERPRINTGUID\n  2\n{09B83CF5-A80C-4963-BEA3-99E561121685}\n"
        "  9\n$TDCREATE\n 40\n2461274.485914352\n"
        "  1\n1.4.4 @ 2026-08-21T11:31:34.281743+00:00\n"
    )
    a = canonicalize_dxf_text(text, 7, datetime(2026, 1, 1, 0, 0, 7))
    b = canonicalize_dxf_text(text, 7, datetime(2026, 1, 1, 0, 0, 7))
    assert a == b
    assert "09B83CF5" not in a
    assert "2461274.485914352" not in a
    assert "2026-08-21T11:31:34.281743" not in a
    # A different seed must give a different, still-stable value.
    assert canonicalize_dxf_text(text, 8, datetime(2026, 1, 1, 0, 0, 8)) != a


# ---------------------------------------------------------------------------
# Export formats
# ---------------------------------------------------------------------------

def test_every_cad_and_mesh_format_the_image_can_write_is_written(tmp_path):
    _, _, results, _ = _build(tmp_path)
    by_format = {r.format: r for r in results}

    # Verified against the installed libraries, not assumed.
    for fmt in ("STEP", "BREP", "STL", "DXF", "SVG", "GLB", "OBJ", "PLY"):
        assert by_format[fmt].status == "included", (
            f"{fmt}: {by_format[fmt].error or by_format[fmt].reason}"
        )
        assert by_format[fmt].bytes > 0
        assert len(by_format[fmt].sha256) == 64


def test_formats_needing_the_render_worker_are_unavailable_not_failed(tmp_path):
    _, _, results, _ = _build(tmp_path)
    by_format = {r.format: r for r in results}
    for fmt in ("USD", "USDZ", "FBX", "ABC"):
        assert by_format[fmt].status == "unavailable"
        assert "render worker" in by_format[fmt].reason


def test_dwg_and_skp_are_impossible_with_a_documented_workaround(tmp_path):
    _, _, results, _ = _build(tmp_path)
    by_format = {r.format: r for r in results}
    for fmt in ("DWG", "SKP"):
        assert by_format[fmt].status == "impossible"
        assert "README_DWG_SKP.txt" in by_format[fmt].reason


def test_a_missing_optional_library_is_unavailable_and_names_the_package(tmp_path):
    """pycollada/networkx are not in the image. That is not a code failure."""
    _, _, results, _ = _build(tmp_path)
    by_format = {r.format: r for r in results}
    for fmt in ("DAE", "3MF"):
        result = by_format[fmt]
        if result.status == "included":
            continue  # the library was added later — fine
        assert result.status == "unavailable"
        assert "pyproject.toml" in result.reason


def test_one_failing_exporter_does_not_cost_the_other_formats(tmp_path, monkeypatch):
    """Rule 12: a bad exporter must never take the whole package with it."""
    import app.geometry.export_formats as ef

    def _boom(solid, out, ctx):
        raise RuntimeError("simulated exporter defect")

    monkeypatch.setattr(ef, "_write_brep", _boom)
    monkeypatch.setattr(
        ef, "FORMAT_REGISTRY",
        tuple(
            f if f.format != "BREP" else type(f)(
                f.format, f.extension, f.tier, f.purpose, _boom,
                f.status_without_writer, f.reason, f.derived_from,
            )
            for f in FORMAT_REGISTRY
        ),
    )
    _, _, results, _ = _build(tmp_path)
    by_format = {r.format: r for r in results}
    assert by_format["BREP"].status == "failed"
    assert "simulated exporter defect" in by_format["BREP"].error
    assert by_format["STL"].status == "included"
    assert by_format["DXF"].status == "included"


def test_dxf_carries_a_real_drawing_with_named_layers(tmp_path):
    """A plan section plus a hidden-line elevation — what a fabricator cuts from."""
    _, _, results, out = _build(tmp_path)
    dxf = next(r for r in results if r.format == "DXF")
    assert dxf.notes["layers"]["PLAN"] >= 1
    assert dxf.notes["layers"]["ELEVATION"] >= 1
    assert dxf.notes["layers"]["HIDDEN"] >= 1
    text = (out / "assembly.dxf").read_text(errors="replace")
    for layer in ("PLAN", "ELEVATION", "HIDDEN"):
        assert layer in text


def test_mesh_tier_records_what_it_was_derived_from(tmp_path):
    """A triangulated mesh must never be mistaken for canonical geometry."""
    _, _, results, _ = _build(tmp_path)
    for fmt in ("OBJ", "PLY"):
        entry = next(r for r in results if r.format == fmt).to_manifest_entry()
        assert entry["derived_from"] == "assembly.glb"
        assert entry["tier"] == "mesh"
    step = next(r for r in results if r.format == "STEP").to_manifest_entry()
    assert step["tier"] == "cad"
    assert "derived_from" not in step


def test_all_exported_formats_are_byte_identical_across_runs(tmp_path):
    _, _, first, _ = _build(tmp_path, "a")
    _, _, second, _ = _build(tmp_path, "b")
    a = {r.format: r.sha256 for r in first if r.sha256}
    b = {r.format: r.sha256 for r in second if r.sha256}
    assert a == b, "an export format is not deterministic"


# ---------------------------------------------------------------------------
# The package
# ---------------------------------------------------------------------------

def _package(tmp_path: Path, name: str):
    _, manifest, results, out = _build(tmp_path, name)
    path, package_manifest, digest = build_luxexchange_package(
        out / "luxexchange_v1.zip",
        seed=SEED,
        design={"design_id": "d-1", "seed": SEED},
        request_payload={"elements": ELEMENTS, "seed": SEED},
        assembly_manifest=manifest,
        validation_reports={"assembly_mesh": {"passed": True}},
        exports=results,
        costing=None,
        costing_unavailable_reason="no BOM in this test",
        provenance={"design_created_at": "2026-08-21T00:00:00+00:00"},
    )
    return path, package_manifest, digest


def test_package_is_byte_identical_for_the_same_design(tmp_path):
    """Rule 5, extended from the canonical STEP to the deliverable."""
    a, _, digest_a = _package(tmp_path, "a")
    b, _, digest_b = _package(tmp_path, "b")
    assert digest_a == digest_b
    assert a.read_bytes() == b.read_bytes()


def test_package_contains_everything_a_recipient_needs(tmp_path):
    path, _, _ = _package(tmp_path, "a")
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
    for required in (
        "luxexchange_v1.json",
        "provenance.json",
        "CHECKSUMS.sha256",
        "verify_luxexchange.py",
        "README_DWG_SKP.txt",
        "assembly_manifest.json",
        "validation/assembly_mesh.json",
        "exports/assembly.step",
        "exports/assembly.dxf",
        "exports/assembly.stl",
    ):
        assert required in names, f"{required} missing from the package"


def test_the_shipped_verifier_passes_on_an_intact_package(tmp_path):
    """It must run with the standard library alone — a fabricator has no
    LuxuryForm install."""
    path, _, digest = _package(tmp_path, "a")
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(path) as zf:
        zf.extractall(extracted)

    proc = subprocess.run(
        [sys.executable, str(extracted / "verify_luxexchange.py")],
        capture_output=True, text=True, cwd=str(extracted),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VERIFICATION PASSED" in proc.stdout
    assert digest in proc.stdout


def test_the_verifier_catches_a_single_altered_byte(tmp_path):
    path, _, _ = _package(tmp_path, "a")
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(path) as zf:
        zf.extractall(extracted)

    target = extracted / "exports" / "assembly.step"
    data = bytearray(target.read_bytes())
    data[len(data) // 2] ^= 0x01
    target.write_bytes(bytes(data))

    proc = subprocess.run(
        [sys.executable, str(extracted / "verify_luxexchange.py")],
        capture_output=True, text=True, cwd=str(extracted),
    )
    assert proc.returncode != 0
    assert "VERIFICATION FAILED" in proc.stdout
    assert "exports/assembly.step" in proc.stdout


def test_the_verifier_notices_a_deleted_file(tmp_path):
    path, _, _ = _package(tmp_path, "a")
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(path) as zf:
        zf.extractall(extracted)
    (extracted / "exports" / "assembly.stl").unlink()

    proc = subprocess.run(
        [sys.executable, str(extracted / "verify_luxexchange.py")],
        capture_output=True, text=True, cwd=str(extracted),
    )
    assert proc.returncode != 0
    assert "MISSING" in proc.stdout


def test_content_digest_excludes_provenance_so_it_tracks_the_design(tmp_path):
    """Provenance carries host and tool versions. Those must not change the
    identity of the design content."""
    path, _, digest = _package(tmp_path, "a")
    with zipfile.ZipFile(path) as zf:
        checksums = zf.read("CHECKSUMS.sha256").decode("utf-8")
        provenance = json.loads(zf.read("provenance.json"))
    assert provenance["content_digest"] == digest
    assert hashlib.sha256(checksums.encode("utf-8")).hexdigest() == digest
    assert "provenance.json" not in checksums
    assert "CHECKSUMS.sha256" not in checksums
    assert "luxexchange_v1.json" in checksums


def test_package_manifest_is_honest_about_what_is_missing(tmp_path):
    _, manifest, _ = _package(tmp_path, "a")
    assert manifest["costing_included"] is False
    assert manifest["costing_unavailable_reason"] == "no BOM in this test"
    assert manifest["design_spec_included"] is False
    statuses = {e["format"]: e["status"] for e in manifest["exports"]}
    assert statuses["STEP"] == "included"
    assert statuses["DWG"] == "impossible"
    assert statuses["USD"] == "unavailable"
