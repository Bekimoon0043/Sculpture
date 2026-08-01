"""Tests for trimesh validation — every number present, cross-check enforced."""

from __future__ import annotations

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")
trimesh = pytest.importorskip("trimesh", reason="trimesh not installed")

from app.core.config import load_config_bundle  # noqa: E402
from app.geometry import (  # noqa: E402
    GeometryBuild,
    export_glb,
    validate_mesh,
    validate_params,
)


@pytest.fixture()
def built_glb(tmp_path):
    params = validate_params({})
    build = GeometryBuild(seed=11, params=params)
    solid = build.build()
    glb = tmp_path / "cascade.glb"
    export_glb(solid, glb)
    material = load_config_bundle().materials.materials[params.material_id]
    return glb, solid, material, params.material_id


def test_all_numbers_present_and_real(built_glb):
    glb, solid, material, material_id = built_glb
    report = validate_mesh(
        glb, material, material_id=material_id,
        reference_volume_mm3=float(solid.volume),
    )
    assert report.watertight is True
    assert report.winding_consistent is True
    assert report.volume_mm3 > 0
    assert report.surface_area_mm2 > 0
    assert isinstance(report.euler_number, int)
    assert len(report.bounds_mm) == 6
    assert report.degenerate_face_count == 0
    assert report.face_count > 0
    # basalt_slab density 2700 kg/m3; mass = volume[mm3] * 1e-9 * 2700
    assert report.mass_kg == pytest.approx(report.volume_mm3 * 2700e-9, rel=1e-9)
    assert report.mass_kg > 0
    assert report.passed is True


def test_volume_crosscheck_includes_both_numbers(built_glb):
    glb, solid, material, material_id = built_glb
    report = validate_mesh(
        glb, material, material_id=material_id,
        reference_volume_mm3=float(solid.volume),
    )
    cc = report.volume_crosscheck
    assert cc is not None
    assert cc.trimesh_volume_mm3 == pytest.approx(report.volume_mm3)
    assert cc.build123d_volume_mm3 == pytest.approx(float(solid.volume))
    assert cc.within_tolerance is True
    assert cc.delta_pct <= 2.0


def test_volume_crosscheck_fails_on_wrong_reference(built_glb):
    glb, solid, material, material_id = built_glb
    report = validate_mesh(
        glb, material, material_id=material_id,
        reference_volume_mm3=float(solid.volume) * 1.5,  # 50% off
    )
    assert report.volume_crosscheck is not None
    assert report.volume_crosscheck.within_tolerance is False
    assert report.passed is False


def test_check_rows_for_panel(built_glb):
    glb, solid, material, material_id = built_glb
    report = validate_mesh(
        glb, material, material_id=material_id,
        reference_volume_mm3=float(solid.volume),
    )
    rows = report.check_rows()
    names = {r["check"] for r in rows}
    assert {
        "watertight", "winding_consistent", "volume_mm3", "surface_area_mm2",
        "euler_number", "bounds_mm", "degenerate_face_count", "mass_kg",
        "volume_crosscheck",
    } <= names
    assert all("value" in r and "passed" in r for r in rows)
