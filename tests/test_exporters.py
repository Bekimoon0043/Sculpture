"""Exporter tests: GLB magic bytes, STEP header carries the injected timestamp."""

from __future__ import annotations

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")

from app.geometry import GeometryBuild, export_glb, export_step, validate_params  # noqa: E402


@pytest.fixture()
def solid():
    return GeometryBuild(seed=5, params=validate_params({"tiers": 2})).build()


def test_glb_magic_bytes_and_sha256(solid, tmp_path):
    glb = tmp_path / "cascade.glb"
    sha = export_glb(solid, glb)
    raw = glb.read_bytes()
    assert raw[:4] == b"glTF"  # binary glTF magic
    assert len(raw) > 1000
    import hashlib

    assert hashlib.sha256(raw).hexdigest() == sha


def test_step_file_contains_injected_timestamp_string(solid, tmp_path):
    step = tmp_path / "cascade.step"
    export_step(solid, step, "2026-01-01T00:00:42")
    text = step.read_text(encoding="utf-8", errors="replace")
    assert "2026-01-01T00:00:42" in text
    assert "ISO-10303-21" in text  # real STEP Part 21 header


def test_step_sha256_returned_matches_file(solid, tmp_path):
    import hashlib

    step = tmp_path / "cascade.step"
    sha = export_step(solid, step, "2026-01-01T00:00:00")
    assert hashlib.sha256(step.read_bytes()).hexdigest() == sha
