"""FF-A1 (ADR-065): the production freeform_integrity_v1 stack.

Exercised against REAL kernel geometry from a registered primitive
(torus_ring — a genus-1 solid the trusted committed kernel builds, the
Phase 6 test precedent) plus deliberate defect cases. The discovery
run's semantics (ADR-064) are pinned: an indeterminate OCC verdict
fails closed under its own honest label, never as proof either way.
"""

from __future__ import annotations

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")
trimesh = pytest.importorskip("trimesh", reason="trimesh not installed")

from app.geometry import freeform_validation as fv  # noqa: E402
from app.geometry.primitives import torus_ring  # noqa: E402


def torus_solid():
    params = torus_ring.validate(
        {"major_diameter_mm": 1800, "minor_diameter_mm": 320}, None)
    return torus_ring.build(params)


class TestIntegrityOnRealGeometry:
    def test_torus_ring_passes_with_genus_one(self):
        report = fv.run_freeform_integrity(torus_solid())
        assert report["gate_name"] == "freeform_integrity_v1"
        assert report["status"] == "pass", report
        by_name = {c["check"]: c for c in report["checks"]}
        assert by_name["occ_analyzer_valid"]["status"] == "pass"
        assert by_name["occ_self_interference"]["status"] == "pass"
        assert by_name["body_count"]["value"] == 1
        assert by_name["tessellation_watertight"]["status"] == "pass"
        assert by_name["boundary_or_nonmanifold_edges"]["value"] == 0
        assert by_name["duplicate_faces"]["value"] == 0
        assert by_name["volume_cross_check"]["status"] == "pass"
        assert by_name["volume_cross_check"]["value"] <= fv.REL_VOL_TOL
        assert by_name["genus"]["value"] == 1

    def test_multi_body_compound_fails_body_count(self):
        from build123d import Box, Pos
        two = Pos(0, 0, 0) * Box(100, 100, 100) + \
            Pos(1000, 0, 0) * Box(100, 100, 100)
        report = fv.run_freeform_integrity(two)
        assert report["status"] == "fail"
        by_name = {c["check"]: c for c in report["checks"]}
        assert by_name["body_count"]["status"] == "fail"
        assert by_name["body_count"]["value"] == 2

    def test_indeterminate_occ_verdict_fails_closed(self, monkeypatch):
        monkeypatch.setattr(
            fv, "occ_self_interference",
            lambda wrapped: {"available": True, "pattern": "test",
                             "has_errors": False, "is_valid": False})
        report = fv.run_freeform_integrity(torus_solid())
        assert report["status"] == "needs_input"
        row = {c["check"]: c for c in report["checks"]}["occ_self_interference"]
        assert row["status"] == "needs_input"
        assert "INDETERMINATE" in row["message"]

    def test_unavailable_binding_fails_closed(self, monkeypatch):
        monkeypatch.setattr(
            fv, "occ_self_interference",
            lambda wrapped: {"available": False, "error": "no binding"})
        report = fv.run_freeform_integrity(torus_solid())
        assert report["status"] == "needs_input"

    def test_report_is_deterministic_for_same_solid(self):
        import json
        a = json.dumps(fv.run_freeform_integrity(torus_solid()),
                       sort_keys=True)
        b = json.dumps(fv.run_freeform_integrity(torus_solid()),
                       sort_keys=True)
        assert a == b
