"""LF-103A — the package classifier: CLEAN / PRE-FABRICATION / REFUSED.

The classifier is a pure function over PERSISTED gate reports. It never
re-reads config, never touches the DB, never consults the clock. The rules
under test are the owner's rulings of 2026-09-01 (ADR-062 amendment 2,
LF-103A final conditions 1-3):

* FAILED never packages. NEEDS_INPUT / warn / unsigned / missing / empty
  evidence is PRE-FABRICATION. CLEAN requires a coherent, signed,
  identity-carrying evidence basis — and is builder/test-only until the
  validation-run identity debt closes.
* Absent evidence NEVER defaults to CLEAN.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.geometry.package_class import (  # noqa: E402
    CLASS_CLEAN,
    CLASS_PRE_FABRICATION,
    CLASS_REFUSED,
    FABRICATION_CAPABLE_FORMATS,
    KNOWN_SEALED_CLASSES,
    LEGACY_UNCLASSIFIED,
    PackageRefused,  # noqa: F401  (imported to prove it lives OUTSIDE routers)
    classify_reports,
    download_filename,
    marked_entry_name,
    package_download_filename,
    read_sealed_package_class,
    role_for,
    select_reports,
    warrant_text,
)

# ---------------------------------------------------------------------------
# Report builders — shaped exactly like LayeredGateReport.model_dump_wire()
# and the assembly_mesh AssemblyValidationReport JSON.
# ---------------------------------------------------------------------------

def layered(
    gate_name: str,
    status: str,
    *,
    signed: bool = False,
    profile: str = "public_plaza",
    version: int = 1,
    basis_id: str | None = None,
    checks: list[dict] | None = None,
) -> dict:
    report = {
        "schema": "layered_validation_report_v2",
        "gate_name": gate_name,
        "status": status,
        "gate_profile_id": profile,
        "gate_profiles_version": version,
        "profile_signed_off": signed,
        "checks": checks if checks is not None else [
            {
                "check": f"{gate_name}.example",
                "status": status,
                "on_violation": "fail",
                "value": 1.0,
                "limit": 2.0,
                "units": "mm",
                "basis": f"gate_profiles.yaml:{profile}.example",
                "message": f"example row for {gate_name}",
            }
        ],
    }
    if basis_id is not None:
        report["validation_basis"] = basis_id
    return report


def mesh(passed: bool = True) -> dict:
    # The mesh report has no "schema" key and carries "watertight" — the
    # exact shape _row_status distinguishes it by.
    return {"passed": passed, "watertight": passed, "body_count": 1}


def full_set(status: str = "pass", **kw) -> dict[str, dict]:
    return {
        "assembly_mesh": mesh(True),
        "structure_static_v1": layered("structure_static_v1", status, **kw),
        "hydraulics": layered("hydraulics", status, **kw),
        "fabrication": layered("fabrication", status, **kw),
    }


def signed_clean_set(basis_id: str = "basis-1") -> dict[str, dict]:
    return full_set("pass", signed=True, basis_id=basis_id)


# ---------------------------------------------------------------------------
# The truth table
# ---------------------------------------------------------------------------

def test_all_pass_but_unsigned_is_pre_fabrication():
    """A package must never appear production-ready while thresholds are
    unsigned (ADR-062)."""
    result = classify_reports(full_set("pass", signed=False),
                              geometry_hash_matches=True)
    assert result.package_class == CLASS_PRE_FABRICATION
    assert any("signed" in r for r in result.reasons)


def test_all_pass_signed_with_shared_basis_and_hash_is_clean():
    result = classify_reports(signed_clean_set(), geometry_hash_matches=True)
    assert result.package_class == CLASS_CLEAN
    assert result.warrant_rows == []


def test_signed_but_no_validation_basis_identity_is_pre_fabrication():
    """LF-103A final condition 1: rows lacking a shared validation-run
    identity are never CLEAN — production rows carry none today."""
    result = classify_reports(full_set("pass", signed=True, basis_id=None),
                              geometry_hash_matches=True)
    assert result.package_class == CLASS_PRE_FABRICATION


def test_mismatched_basis_identity_is_pre_fabrication():
    reports = signed_clean_set()
    reports["hydraulics"]["validation_basis"] = "some-other-run"
    result = classify_reports(reports, geometry_hash_matches=True)
    assert result.package_class == CLASS_PRE_FABRICATION


def test_mixed_profile_ids_are_pre_fabrication_even_signed():
    reports = signed_clean_set()
    reports["hydraulics"]["gate_profile_id"] = "indoor_lobby"
    result = classify_reports(reports, geometry_hash_matches=True)
    assert result.package_class == CLASS_PRE_FABRICATION


def test_mixed_profile_versions_are_pre_fabrication_even_signed():
    reports = signed_clean_set()
    reports["fabrication"]["gate_profiles_version"] = 2
    result = classify_reports(reports, geometry_hash_matches=True)
    assert result.package_class == CLASS_PRE_FABRICATION


def test_geometry_hash_mismatch_is_pre_fabrication_even_signed():
    result = classify_reports(signed_clean_set(), geometry_hash_matches=False)
    assert result.package_class == CLASS_PRE_FABRICATION


def test_unknown_geometry_hash_is_pre_fabrication_even_signed():
    result = classify_reports(signed_clean_set(), geometry_hash_matches=None)
    assert result.package_class == CLASS_PRE_FABRICATION


def test_any_fail_is_refused():
    reports = full_set("pass", signed=True, basis_id="b")
    reports["fabrication"] = layered("fabrication", "fail")
    result = classify_reports(reports, geometry_hash_matches=True)
    assert result.package_class == CLASS_REFUSED


def test_mesh_fail_is_refused():
    reports = full_set("pass")
    reports["assembly_mesh"] = mesh(False)
    assert classify_reports(reports).package_class == CLASS_REFUSED


def test_needs_input_is_pre_fabrication():
    result = classify_reports(full_set("needs_input"))
    assert result.package_class == CLASS_PRE_FABRICATION
    assert result.warrant_rows  # the unresolved checks ride into the warrant


def test_downgraded_warn_is_pre_fabrication_with_reason():
    """status==warn AND on_violation==fail is a breach masked by an
    unsigned profile — the structural downgrade predicate."""
    checks = [{
        "check": "overturning_safety_factor", "status": "warn",
        "on_violation": "fail", "value": 1.1, "limit": 1.5, "units": None,
        "basis": "gate_profiles.yaml:public_plaza.overturning_safety_factor",
        "message": "breached — reported as a warning only: not signed off",
    }]
    reports = full_set("pass", signed=False)
    reports["structure_static_v1"] = layered(
        "structure_static_v1", "warn", checks=checks)
    result = classify_reports(reports)
    assert result.package_class == CLASS_PRE_FABRICATION
    assert any("unsigned" in r or "signed" in r for r in result.reasons)


def test_missing_layered_gate_is_pre_fabrication_never_pass():
    """worst_status([]) == 'pass' is the trap: absence of a safety gate must
    read as missing evidence, not as a clean pass."""
    reports = signed_clean_set()
    del reports["structure_static_v1"]
    result = classify_reports(reports, geometry_hash_matches=True)
    assert result.package_class == CLASS_PRE_FABRICATION
    assert any("structure_static_v1" in r for r in result.reasons)


def test_missing_both_mesh_rows_is_pre_fabrication():
    reports = signed_clean_set()
    del reports["assembly_mesh"]
    result = classify_reports(reports, geometry_hash_matches=True)
    assert result.package_class == CLASS_PRE_FABRICATION


def test_empty_reports_are_pre_fabrication_never_clean():
    """The absent-statuses default. Every pre-LF-103A caller that supplies
    no reports must land here — a CLEAN default would mint falsely
    fabrication-ready packages."""
    result = classify_reports({}, geometry_hash_matches=True)
    assert result.package_class == CLASS_PRE_FABRICATION


def test_legacy_mesh_alias_is_accepted():
    reports = signed_clean_set()
    reports["mesh"] = reports.pop("assembly_mesh")
    result = classify_reports(reports, geometry_hash_matches=True)
    assert result.package_class == CLASS_CLEAN


# ---------------------------------------------------------------------------
# Deterministic row selection (duplicates + mesh alias)
# ---------------------------------------------------------------------------

def test_select_reports_resolves_duplicates_created_at_desc_then_id_desc():
    rows = [
        ("hydraulics", "2026-08-01T00:00:00", "id-a", {"marker": "old"}),
        ("hydraulics", "2026-08-02T00:00:00", "id-b", {"marker": "new"}),
        # created_at tie — id DESC breaks it deterministically.
        ("fabrication", "2026-08-02T00:00:00", "id-1", {"marker": "low"}),
        ("fabrication", "2026-08-02T00:00:00", "id-2", {"marker": "high"}),
    ]
    picked = select_reports(rows)
    assert picked["hydraulics"]["marker"] == "new"
    assert picked["fabrication"]["marker"] == "high"


def test_select_reports_prefers_assembly_mesh_over_legacy_mesh():
    rows = [
        ("mesh", "2026-08-05T00:00:00", "id-l", {"marker": "legacy"}),
        ("assembly_mesh", "2026-08-01T00:00:00", "id-m", {"marker": "modern"}),
    ]
    picked = select_reports(rows)
    assert picked["assembly_mesh"]["marker"] == "modern"
    assert "mesh" not in picked


# ---------------------------------------------------------------------------
# Role ownership — documented mapping, never free-text parsing
# ---------------------------------------------------------------------------

def test_role_map_covers_the_known_disciplines():
    assert role_for("structure_static_v1", "overturning_safety_factor") \
        == "structural engineer"
    assert "geotechnical" in role_for(
        "structure_static_v1", "ground_bearing_pressure_kpa")
    assert role_for("hydraulics", "reservoir_turnover_min") \
        == "MEP/fountain engineer"
    assert role_for("fabrication", "rigging_declared") == "rigging reviewer"
    assert role_for("fabrication", "basin_01.mass_kg") == "workshop/fabricator"


def test_unknown_mapping_never_invents_a_discipline():
    assert role_for("some_future_gate", "anything") \
        == "qualified professional review required"


# ---------------------------------------------------------------------------
# The warrant — deterministic bytes, honest content
# ---------------------------------------------------------------------------

def test_warrant_is_deterministic_and_names_the_unresolved_checks():
    reports = full_set("needs_input")
    result = classify_reports(reports)
    text_a = warrant_text("design-x", 7, result)
    text_b = warrant_text("design-x", 7, result)
    assert text_a == text_b
    assert "PRE-FABRICATION" in text_a
    assert "design-x" in text_a
    assert "structure_static_v1" in text_a
    # Every warrant row's professional owner appears.
    assert "qualified professional review required" in text_a or "engineer" in text_a


def test_warrant_orders_rows_deterministically():
    reports_a = full_set("needs_input")
    reports_b = dict(reversed(list(full_set("needs_input").items())))
    assert warrant_text("d", 1, classify_reports(reports_a)) == \
        warrant_text("d", 1, classify_reports(reports_b))


# ---------------------------------------------------------------------------
# Marking helpers
# ---------------------------------------------------------------------------

def test_marked_entry_name_marks_the_basename():
    assert marked_entry_name("exports/assembly.step") \
        == "exports/assembly.PRE-FABRICATION.step"
    assert marked_entry_name("exports/assembly.dxf") \
        == "exports/assembly.PRE-FABRICATION.dxf"


def test_download_filenames_carry_the_class():
    pre = download_filename("d1", "assembly.step", CLASS_PRE_FABRICATION)
    assert "PRE-FABRICATION" in pre and pre.endswith(".step")
    diag = download_filename("d1", "assembly.glb", CLASS_REFUSED)
    assert "DIAGNOSTIC-NOT-FOR-FABRICATION" in diag
    clean = download_filename("d1", "assembly.step", CLASS_CLEAN)
    assert "PRE-FABRICATION" not in clean and "DIAGNOSTIC" not in clean


def test_package_download_filename_by_class():
    assert "PRE-FABRICATION" in package_download_filename("d1",
                                                          CLASS_PRE_FABRICATION)
    assert package_download_filename("d1", CLASS_CLEAN) == "luxexchange_d1.zip"


def test_fabrication_capable_formats_are_the_cad_tier():
    assert FABRICATION_CAPABLE_FORMATS == {"STEP", "BREP", "STL", "DXF", "SVG"}


# ---------------------------------------------------------------------------
# Sealed-manifest reading — strict enum, fails closed (final condition 3)
# ---------------------------------------------------------------------------

def _seal_zip(tmp_path: Path, manifest: dict | None, name="pkg.zip") -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as zf:
        if manifest is not None:
            import json
            zf.writestr("luxexchange_v1.json", json.dumps(manifest))
    return path


def test_sealed_class_round_trip(tmp_path):
    assert read_sealed_package_class(
        _seal_zip(tmp_path, {"package_class": "clean"})) == CLASS_CLEAN
    assert read_sealed_package_class(
        _seal_zip(tmp_path, {"package_class": "pre_fabrication"}, "b.zip")) \
        == CLASS_PRE_FABRICATION


def test_missing_or_invalid_class_is_legacy_unclassified(tmp_path):
    assert read_sealed_package_class(
        _seal_zip(tmp_path, {"schema": "luxexchange_v1"})) == LEGACY_UNCLASSIFIED
    assert read_sealed_package_class(
        _seal_zip(tmp_path, {"package_class": "totally_fine"}, "b.zip")) \
        == LEGACY_UNCLASSIFIED
    assert read_sealed_package_class(
        _seal_zip(tmp_path, None, "c.zip")) == LEGACY_UNCLASSIFIED
    corrupt = tmp_path / "corrupt.zip"
    corrupt.write_bytes(b"this is not a zip")
    assert read_sealed_package_class(corrupt) == LEGACY_UNCLASSIFIED
    assert read_sealed_package_class(tmp_path / "absent.zip") \
        == LEGACY_UNCLASSIFIED


def test_known_sealed_classes_enum_is_exactly_two():
    assert KNOWN_SEALED_CLASSES == {CLASS_CLEAN, CLASS_PRE_FABRICATION}
