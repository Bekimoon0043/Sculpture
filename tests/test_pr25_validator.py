"""PR-2.5: unit tests for the ANALYSIS-ONLY validator + canonical writer.

ADR-064 line: AI-authored code that CONSTRUCTS design geometry through
the CAD kernel runs only in the geo-worker sandbox; these tests exercise
analysis functions against literal numeric fixtures (a hand-written
tetrahedron), which is test data, not design-geometry construction. No
build123d/OCC object is ever created here; the STEP path of the validator
is exercised by the orchestrated discovery run, not by unit tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"
                       / "probes"))

import probe_common  # noqa: E402
import validate_freeform  # noqa: E402

#: A unit tetrahedron as literal data (mm). Watertight, genus 0.
TET_V = np.array([[0.0, 0.0, 0.0], [100.0, 0.0, 0.0],
                  [0.0, 100.0, 0.0], [0.0, 0.0, 100.0]])
TET_F = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])


def tet_mesh(faces=TET_F):
    import trimesh
    return trimesh.Trimesh(vertices=TET_V.copy(), faces=faces.copy(),
                           process=False)


class TestCanonicalObjWriter:
    def test_byte_identical_across_two_writes(self, tmp_path):
        sha1 = probe_common.write_canonical_obj(tmp_path / "a.obj", TET_V,
                                                TET_F, "tet")
        sha2 = probe_common.write_canonical_obj(tmp_path / "b.obj", TET_V,
                                                TET_F, "tet")
        assert sha1 == sha2
        assert (tmp_path / "a.obj").read_bytes() == \
            (tmp_path / "b.obj").read_bytes()

    def test_bytes_are_ascii_with_lf_only(self, tmp_path):
        probe_common.write_canonical_obj(tmp_path / "a.obj", TET_V, TET_F,
                                         "tet")
        raw = (tmp_path / "a.obj").read_bytes()
        raw.decode("ascii")
        assert b"\r" not in raw

    def test_vertex_order_changes_the_bytes(self, tmp_path):
        sha1 = probe_common.write_canonical_obj(tmp_path / "a.obj", TET_V,
                                                TET_F, "tet")
        sha2 = probe_common.write_canonical_obj(tmp_path / "b.obj",
                                                TET_V[::-1].copy(),
                                                TET_F, "tet")
        assert sha1 != sha2


class TestMeshReport:
    def test_watertight_tetrahedron_is_clean(self):
        report = validate_freeform.mesh_report(tet_mesh())
        assert report["watertight"] is True
        assert report["winding_consistent"] is True
        assert report["boundary_or_nonmanifold_edges"] == 0
        assert report["duplicate_face_pairs"] == 0
        assert report["body_count"] == 1
        assert report["genus"] == 0
        # V=4, E=6, F=4 -> chi = 2
        assert report["euler_characteristic"] == 2
        # The validator's contract is DETERMINISTIC 3-decimal output
        # (round(float(mesh.volume), 3)); assert that contract exactly.
        # The first version of this test compared against the unrounded
        # analytic value at rel=1e-9 -- tighter than the rounding error
        # -- and the OPERATOR caught it red after rebuild (2026-09-03):
        # obtained 166666.667 vs expected 166666.66666666666.
        assert report["volume_mm3"] == round(100.0 ** 3 / 6.0, 3)
        assert validate_freeform.flag(report) == []

    def test_open_mesh_is_flagged_with_real_numbers(self):
        report = validate_freeform.mesh_report(tet_mesh(TET_F[:3]))
        assert report["watertight"] is False
        assert report["boundary_or_nonmanifold_edges"] == 3
        assert report["genus"] is None
        reasons = validate_freeform.flag(report)
        assert any("not watertight" in r for r in reasons)
        assert any("3 boundary/non-manifold edges" in r for r in reasons)

    def test_duplicate_faces_are_flagged(self):
        doubled = np.vstack([TET_F, TET_F[:1]])
        report = validate_freeform.mesh_report(tet_mesh(doubled))
        assert report["duplicate_face_pairs"] >= 1
        assert any("duplicate face pairs" in r
                   for r in validate_freeform.flag(report))

    def test_min_thickness_measures_or_degrades_honestly(self):
        """trimesh.proximity.thickness needs rtree, which the pinned image
        does not carry (measured 2026-09-02) -- on that image the check
        must degrade to a RECORDED error, never a crash or a silent
        number."""
        report = validate_freeform.mesh_report(tet_mesh())
        try:
            import rtree  # noqa: F401
            have_rtree = True
        except ImportError:
            have_rtree = False
        if have_rtree:
            assert report["thickness_error"] is None
            assert report["min_thickness_mm"] is not None
            assert 0.0 < report["min_thickness_mm"] <= 100.0
        else:
            assert report["min_thickness_mm"] is None
            assert "rtree" in report["thickness_error"]


class TestResultContracts:
    def test_result_entry_rejects_invented_statuses(self):
        with pytest.raises(ValueError):
            probe_common.result_entry("f", "brep", status="almost-worked",
                                      detail="")

    def test_results_json_is_sorted_and_seed_pinned(self, tmp_path):
        entry = probe_common.result_entry("f", "mesh", status="constructed",
                                          detail="d")
        path = probe_common.write_results(tmp_path, "probe_x", [entry], [])
        import json
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["seed"] == probe_common.DISCOVERY_SEED == 20260902
        assert path.read_text(encoding="utf-8") == json.dumps(
            payload, indent=2, sort_keys=True)
