"""FF-A2 (ADR-066): the explicit hollow-lens topology contract across
the published parameter range.

A valid default cannot hide topology collapse elsewhere: representative
minimum / default / maximum combinations AND targeted worst-case
combinations of twist, wobble (bow) and bore extremes all go through
the full production integrity stack against the declared
EXPECTED_TOPOLOGY — including the sealed-cavity / bore-separation
truths (owner delta items 2 and 4).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")
trimesh = pytest.importorskip("trimesh", reason="trimesh not installed")

from app.geometry.freeform_validation import (  # noqa: E402
    _mesh_boundary_topology,
    run_freeform_integrity,
)
from app.geometry.primitives import freeform_loop  # noqa: E402

DEFAULTS = json.loads(
    (Path(__file__).parent / "fixtures" / "freeform_loop_spec_v1.json")
    .read_text())["elements"][0]["parameters"]

# Representative combinations across the published range plus the named
# worst cases. Every combination must first pass validate() — the
# matrix exercises the ACCEPTED range; the corridor/hollowability
# refusals keep the rest out.
MATRIX = {
    "default": {},
    "min_envelope": {"height_mm": 3500, "width_mm": 2100,
                     "depth_mm": 500, "bore_width_mm": 800,
                     "bore_height_mm": 950, "wobble_mm": 100,
                     "base_plate_diameter_mm": 500},
    "max_envelope": {"height_mm": 5000, "width_mm": 3400,
                     "depth_mm": 1400, "bore_width_mm": 1500,
                     "bore_height_mm": 1750, "wobble_mm": 400},
    # Worst ACCEPTED combinations, each MEASURED to build (2026-09-05);
    # the kernel's robustness cliff beyond them refuses loudly and is
    # pinned by the refusal tests below (ADR-066).
    "worst_twist_bow_low": {"height_mm": 3500, "width_mm": 2400,
                            "depth_mm": 800, "section_twist_deg": 90,
                            "wobble_mm": 875, "bore_width_mm": 700,
                            "bore_height_mm": 850},
    "bore_high_and_offset": {"bore_center_height_fraction": 0.62,
                             "plan_skew_ratio": -0.18,
                             "bore_width_mm": 900,
                             "bore_height_mm": 1000},
    "thick_wall": {"wall_mm": 20, "depth_mm": 1100,
                   "bore_width_mm": 900, "bore_height_mm": 1050},
    "low_waist_blunt_base": {"waist_height_fraction": 0.35,
                             "bore_center_height_fraction": 0.55,
                             "bore_width_mm": 800, "bore_height_mm": 900,
                             "plan_skew_ratio": 0.08,
                             "base_plate_diameter_mm": 700},
}

#: MEASURED kernel-cliff combinations (2026-09-05): each failed its
#: hollowing boolean SILENTLY on this pinned image and must now refuse
#: as a deterministic ConstraintViolation — never build corrupt, never
#: 500. If a future image moves the cliff, these pins say so loudly.
CLIFF = {
    "five_metre_heavy_twist": {
        "height_mm": 5000, "width_mm": 3200, "depth_mm": 1200,
        "section_twist_deg": -90, "wobble_mm": 900,
        "bore_width_mm": 1100, "bore_height_mm": 1300},
    "five_metre_heavy_twist_low_bow": {
        "height_mm": 5000, "width_mm": 3200, "depth_mm": 1200,
        "section_twist_deg": -90, "wobble_mm": 600,
        "bore_width_mm": 1100, "bore_height_mm": 1300},
    "quarter_waist": {
        "waist_height_fraction": 0.25,
        "bore_center_height_fraction": 0.55,
        "bore_width_mm": 800, "bore_height_mm": 900,
        "plan_skew_ratio": 0.08, "base_plate_diameter_mm": 700},
}


def params_for(name):
    raw = dict(DEFAULTS)
    raw.update(MATRIX[name])
    return freeform_loop.validate(raw, None)


@pytest.fixture(scope="module")
def built():
    """Build each matrix combination once (they are expensive)."""
    cache = {}

    def _get(name):
        if name not in cache:
            cache[name] = freeform_loop.build(params_for(name))
        return cache[name]
    return _get


@pytest.mark.parametrize("name", sorted(MATRIX))
def test_combination_validates(name):
    params_for(name)  # raises ConstraintViolation on a bad matrix entry


@pytest.mark.parametrize("name", sorted(CLIFF))
def test_kernel_cliff_refuses_loudly_never_silently(name):
    """The measured kernel-cliff combinations (ADR-066): the hollowing
    boolean fails on them, and that failure must surface as a
    DETERMINISTIC ConstraintViolation refusal carrying the real stage
    numbers — a silently corrupt build here would be the ADR-064
    silent-boolean class reaching production."""
    from app.geometry.primitives.base import ConstraintViolation
    raw = dict(DEFAULTS)
    raw.update(CLIFF[name])
    p = freeform_loop.validate(raw, None)
    with pytest.raises(ConstraintViolation) as exc:
        freeform_loop.build(p)
    assert "construction refused" in str(exc.value)


@pytest.mark.parametrize("name", sorted(MATRIX))
def test_topology_contract_holds(built, name):
    solid = built(name)
    report = run_freeform_integrity(
        solid, expected_topology=freeform_loop.EXPECTED_TOPOLOGY)
    by_name = {c["check"]: c for c in report["checks"]}

    assert by_name["body_count"]["value"] == 1, name
    for key in ("boundary_components", "closed_internal_cavities",
                "per_component_genus", "per_component_euler",
                "through_openings"):
        row = by_name[f"topology_{key}"]
        assert row["status"] == "pass", (name, key, row)
    assert by_name["topology_accidental_extra_bodies_or_voids"][
        "status"] == "pass", name
    assert report["status"] == "pass", (
        name, [c for c in report["checks"] if c["status"] != "pass"])


@pytest.mark.parametrize("name", sorted(MATRIX))
def test_bore_to_cavity_clearance_measured_everywhere(built, name):
    """Owner clarification 2: the measured clearance is authoritative
    and must hold across the range, not only at the default."""
    p = params_for(name)
    wm = freeform_loop.measure_wall(p, built(name))
    assert wm["status"] == "measured", (name, wm)
    btc = wm["bore_to_cavity_mm"]
    assert btc is not None, (name, wm)
    assert btc >= p.wall_mm - 0.5, (name, btc, p.wall_mm)


def test_topology_mismatch_fails_loudly(built):
    """A wrong expectation must FAIL — the contract is compared, not
    echoed."""
    wrong = dict(freeform_loop.EXPECTED_TOPOLOGY)
    wrong["per_component_genus"] = [0, 0]
    wrong["through_openings"] = 0
    report = run_freeform_integrity(built("default"),
                                    expected_topology=wrong)
    assert report["status"] == "fail"
    failing = {c["check"] for c in report["checks"]
               if c["status"] == "fail"}
    assert "topology_per_component_genus" in failing
    assert "topology_through_openings" in failing


def test_cavity_is_detected_by_negative_signed_volume(built):
    """The mechanism itself: the welded mesh has exactly two boundary
    components and the cavity's signed volume is negative."""
    import numpy as np

    solid = built("default")
    verts, tris = solid.tessellate(tolerance=1.0, angular_tolerance=0.1)
    mesh = trimesh.Trimesh(
        vertices=np.array([[v.X, v.Y, v.Z] for v in verts]),
        faces=np.array(tris), process=True)
    mesh.merge_vertices()
    topo = _mesh_boundary_topology(mesh)
    assert topo is not None
    assert topo["boundary_components"] == 2
    vols = [c["signed_volume_mm3"] for c in topo["components"]]
    assert vols[0] > 0 and vols[1] < 0, vols


def test_no_expectation_reports_informationally():
    """FF-A1 behavior unchanged: without a declared contract the report
    carries the measured topology as an informational pass row."""
    from build123d import Torus
    report = run_freeform_integrity(Torus(400, 100))
    by_name = {c["check"]: c for c in report["checks"]}
    row = by_name["boundary_component_topology"]
    assert row["status"] == "pass"
    assert row["value"]["boundary_components"] == 1
    assert row["value"]["per_component_genus"] == [1]
    assert "topology_boundary_components" not in by_name
