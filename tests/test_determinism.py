"""Determinism tests (Amendment 1): same spec + same seed -> byte-identical STEP.

In-process proof; the GATE additionally proves it across two separate
processes (scripts/gate_phase2_auto.py section 2).
"""

from __future__ import annotations

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")

from app.geometry import GeometryBuild, export_step, validate_params  # noqa: E402
from app.geometry.kernel import (  # noqa: E402
    canonical_spec_json,
    spec_hash_for,
    step_timestamp_for,
)


def test_spec_hash_stable_and_seed_sensitive():
    params = validate_params({"tiers": 3})
    h1 = spec_hash_for(params, 42)
    h2 = spec_hash_for(validate_params({"tiers": 3}), 42)
    assert h1 == h2
    assert spec_hash_for(params, 43) != h1
    assert spec_hash_for(validate_params({"tiers": 4}), 42) != h1
    # canonical JSON is sorted and contains both parameter set and seed
    canon = canonical_spec_json(params, 42)
    assert '"seed":42' in canon
    assert canon.index('"basin_diameter_mm"') < canon.index('"tiers"')


def test_step_timestamp_derived_from_seed_only():
    from datetime import datetime

    assert step_timestamp_for(0) == datetime(2026, 1, 1)
    assert step_timestamp_for(42).isoformat() == "2026-01-01T00:00:42"


def test_double_export_fixed_timestamp_byte_identical(tmp_path):
    params = validate_params({})
    build1 = GeometryBuild(seed=42, params=params)
    solid1 = build1.build()
    build2 = GeometryBuild(seed=42, params=validate_params({}))
    solid2 = build2.build()

    p1 = tmp_path / "run1.step"
    p2 = tmp_path / "run2.step"
    sha1 = export_step(solid1, p1, build1.step_timestamp)
    sha2 = export_step(solid2, p2, build2.step_timestamp)
    assert sha1 == sha2
    assert p1.read_bytes() == p2.read_bytes()


def test_different_seed_gives_different_step_bytes(tmp_path):
    params = validate_params({})
    solid = GeometryBuild(seed=1, params=params).build()
    pa = tmp_path / "a.step"
    pb = tmp_path / "b.step"
    export_step(solid, pa, step_timestamp_for(1))
    export_step(solid, pb, step_timestamp_for(2))
    # timestamp differs -> header differs -> bytes differ (the seed matters)
    assert pa.read_bytes() != pb.read_bytes()
