"""PR-2.5 discovery slice: repo-reproducible asset tests (ADR-064).

Everything here runs offline at $0 against committed files only -- no
probe artifacts, no reference images (those are operator-local and MUST
NOT be required by any repo-reproducible check, owner amendment 1/5).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REFS = REPO / "briefs" / "freeform_references"
PROBES = REPO / "scripts" / "probes"

PRIMARY = {"08", "11", "13", "14", "16"}
SECONDARY = {"09", "10", "12", "15"}
ENGINEERING = {"01", "02", "03", "04", "05", "06", "07"}


def load_manifest():
    return json.loads((REFS / "reference_manifest.json").read_text(
        encoding="utf-8-sig"))


class TestReferenceManifest:
    def test_manifest_has_16_entries_with_valid_hashes(self):
        man = load_manifest()
        images = man["images"]
        assert len(images) == 16
        for entry in images:
            assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), entry["file"]
            assert re.fullmatch(r"\d{2}_[a-z0-9_]+\.jpg", entry["file"])

    def test_roles_partition_exactly_as_ruled(self):
        man = load_manifest()
        by_role: dict[str, set] = {}
        for entry in man["images"]:
            by_role.setdefault(entry["role"], set()).add(entry["file"][:2])
        assert by_role["primary"] == PRIMARY
        assert by_role["secondary"] == SECONDARY
        assert by_role["engineering-context"] == ENGINEERING

    def test_dimensioned_references_carry_notes(self):
        man = load_manifest()
        noted = {e["file"][:2] for e in man["images"] if "dimension_notes" in e}
        # 01/07/12 are the only images with stated dimensions
        # (REFERENCE_ANALYSIS.md); everything else is image-derived only.
        assert noted == {"01", "07", "12"}

    def test_mesh_lattice_gap_recorded(self):
        man = load_manifest()
        assert "B-11b" in man["mesh_lattice_note"]

    def test_jpgs_are_git_and_docker_ignored(self):
        gitignore = (REPO / ".gitignore").read_text(encoding="utf-8-sig")
        dockerignore = (REPO / ".dockerignore").read_text(encoding="utf-8-sig")
        assert "briefs/freeform_references/*.jpg" in gitignore
        assert "briefs/freeform_references/*.jpg" in dockerignore

    def test_manifest_embeds_no_image_bytes(self):
        raw = (REFS / "reference_manifest.json").read_bytes()
        assert len(raw) < 16_384
        assert b"base64" not in raw.lower()


class TestProbeSourcesStayOffline:
    """The $0 rule, statically enforced on every discovery source file."""

    # Assembled at runtime: the gate scans its own source, so neither it
    # nor this test may contain the forbidden literals verbatim.
    FORBIDDEN = tuple("import " + m for m in
                      ("requests", "httpx", "urllib", "socket")) + \
        tuple(p + " " + m for p in ("from", "import")
              for m in ("anthropic", "openai")) + \
        tuple(s + "://" for s in ("http", "https"))

    def sources(self):
        files = sorted(PROBES.glob("*.py"))
        files.append(REPO / "scripts" / "run_pr25_discovery.py")
        files.append(REPO / "scripts" / "gate_pr25_discovery_auto.py")
        assert len(files) >= 8
        return files

    def test_no_network_or_provider_imports(self):
        for path in self.sources():
            text = path.read_text(encoding="utf-8")
            code_lines = [ln for ln in text.splitlines()
                          if not ln.lstrip().startswith("#")]
            joined = "\n".join(code_lines)
            for token in self.FORBIDDEN:
                assert token not in joined, "%s contains %r" % (path.name,
                                                                token)

    def test_geometry_probes_declare_sandbox_only(self):
        for name in ("probe_freeform_brep.py", "probe_freeform_mesh.py",
                     "probe_freeform_import.py", "gen_import_fixture.py"):
            text = (PROBES / name).read_text(encoding="utf-8")
            assert "SANDBOX-ONLY" in text, name


class TestDiscoveryReport:
    REPORT = REPO / "PR2_5_FREEFORM_DISCOVERY.md"

    def report(self):
        # Whitespace-normalized: markdown wraps sentences across lines.
        return " ".join(self.REPORT.read_text(encoding="utf-8-sig").split())

    def test_report_exists_with_required_sections(self):
        text = self.report()
        for heading in ("## Owner rulings", "## Method",
                        "## Capability matrix", "## Approach comparison",
                        "## Parameter frames", "## Acceptance gate design",
                        "## Open items"):
            assert heading in text, heading

    def test_canonical_artifact_ruling_sentence_present(self):
        assert ("any change to STEP as the canonical artifact requires an "
                "explicit architectural ruling") in self.report()

    def test_b11b_stays_open_and_release_blocking(self):
        text = self.report()
        assert "B-11b" in text
        assert "release-blocking" in text

    def test_no_invented_fabrication_numbers(self):
        text = self.report()
        for banned in ("1900–2100", "1900-2100", "15–25 mm",
                       "15-25 mm", "crane-trivial", "560 kg", "+30%",
                       "+30 %"):
            assert banned not in text, "banned invented value: %r" % banned

    def test_provenance_vocabulary_is_the_ruled_six(self):
        text = self.report()
        for tag in ("owner-ruling", "measured-from-dimensioned-reference",
                    "image-derived-estimate", "materials.yaml",
                    "probe-only-judgement", "FABRICATOR-INPUT-REQUIRED"):
            assert tag in text, tag

    def test_skin_mass_is_labeled_non_engineering(self):
        text = self.report()
        assert "non-engineering discovery estimate" in text
        assert "not computable until the armature is designed" in text

    def test_capability_matrix_block_parses(self):
        raw = self.REPORT.read_text(encoding="utf-8-sig")
        m = re.search(r"```json capability-matrix\n(.*?)```", raw,
                      re.DOTALL)
        assert m, "fenced `json capability-matrix` block missing"
        rows = json.loads(m.group(1))
        assert len(rows) >= 12
        for row in rows:
            assert row["approach"] in ("brep", "mesh", "import")
            assert row["status"] in ("constructed", "failed")


class TestScopeGuards:
    def test_limitations_carries_the_probed_not_implemented_sentence(self):
        text = (REPO / "LIMITATIONS.md").read_text(encoding="utf-8-sig")
        assert ("kernel feasibility probed; no user-facing free-form "
                "capability implemented") in text

    def test_audit_score_unchanged(self):
        text = (REPO / "DEVELOPMENT_AUDIT.md").read_text(encoding="utf-8-sig")
        assert "31.6" in text
