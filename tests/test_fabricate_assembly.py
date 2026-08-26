"""Phase 6 slice A2 — the fabrication -> design bridge + two-tier surface.

Same discipline as test_fabrication.py: the sandbox runner is SCRIPTED
(canned SandboxResults) — AI-written code executes nowhere but the
geo-worker container, tests included. What IS real here: the geometry
(registry.assemble builds the actual OCCT solid), the manifest, the GLB
the validation gate measures, the STEP export whose sha256 the bridge
must reproduce byte-for-byte, and every database row.
"""

from __future__ import annotations

import json

import pytest

from app.council import prompts
from app.council.fabricate import SandboxResult, fabricate_spec
from app.db.models import DesignRow, DesignSpecRow, GeneratedProgramRow
from tests.test_fabrication import (
    FabDispatcher,
    ScriptedRunner,
    _fab_orchestrator,
    _first_spec_id,
    _ok_result,
    _run_council_session,
)

pytest.importorskip("build123d")


@pytest.fixture()
def base_spec(repo_root):
    from tests.test_design_spec_schema import valid_example_spec
    return valid_example_spec()

#: Trusted program TEXT for the dispatcher script. Never executed — the
#: ScriptedRunner returns canned results — but it must pass the ADR-030
#: AST gate ({registry, math} only) like a real geometrist program.
ASSEMBLY_PROGRAM = """import registry

def build(spec):
    elements = registry.assembly_plan_from_spec(spec)
    fabrication = registry.fabrication_limits_from_spec(spec)
    solid, manifest = registry.assemble(
        elements, seed=spec["meta"]["seed"], fabrication=fabrication)
    return solid, manifest, spec["meta"]["seed"]
"""

#: The slice A1 gate composition (prompt example values): three different
#: primitives, two joint types, all inside the signed basalt envelopes.
A1_PLAN = [
    {
        "element_id": "b1",
        "primitive": "basin_round",
        "parameters": {
            "diameter_mm": 600, "height_mm": 300, "wall_mm": 25,
            "floor_mm": 60, "material_id": "basalt_slab",
        },
        "joint": {"type": "stack_on", "parent": "p1"},
    },
    {
        "element_id": "c1",
        "primitive": "sculptural_column",
        "parameters": {
            "diameter_mm": 100, "height_mm": 400,
            "material_id": "basalt_slab",
        },
        "joint": {"type": "concentric_insert", "parent": "b1"},
    },
    {
        "element_id": "p1",
        "primitive": "plinth",
        "parameters": {
            "top_diameter_mm": 700, "height_mm": 300,
            "material_id": "basalt_slab",
        },
    },
]

FABRICATION_LIMITS = {"max_lift_kg": 2000.0, "max_module_m": 3.0}
SEED = 42  # valid_example_spec meta.seed — the manifest must carry it


@pytest.fixture()
def assembled(tmp_path):
    """REAL geometry: the A1 composition built once, with real exports."""
    from app.geometry import assemble
    from app.geometry.exporters import export_glb, export_step
    from app.geometry.kernel import step_timestamp_for

    solid, manifest, element_solids = assemble(
        A1_PLAN, seed=SEED, fabrication=FABRICATION_LIMITS, strict=True,
        return_solids=True,
    )
    glb = tmp_path / "sandbox.glb"
    glb_sha = export_glb(solid, glb)
    step = tmp_path / "sandbox.step"
    step_sha = export_step(solid, step, step_timestamp_for(SEED))
    return {
        "solid": solid,
        "manifest": manifest,
        "glb_path": glb,
        "glb_sha256": glb_sha,
        "step_path": step,
        "step_sha256": step_sha,
    }


def _sandbox_result(assembled) -> SandboxResult:
    m = assembled["manifest"]
    return SandboxResult(
        ok=True,
        artifacts={
            "step": str(assembled["step_path"]),
            "glb": str(assembled["glb_path"]),
            "step_sha256": assembled["step_sha256"],
            "glb_sha256": assembled["glb_sha256"],
        },
        brep_volume_mm3=m["volume_conservation"]["assembly_volume_mm3"],
        params=m,
    )


def _set_assembly_massing(db, spec_id: str) -> None:
    """Point the stored spec's massing at the three slice-A1 primitives."""
    with db.get_session() as s:
        row = s.get(DesignSpecRow, spec_id)
        spec = json.loads(row.spec_json)
        spec["massing"]["elements"] = [
            {
                "element_id": el["element_id"],
                "primitive": el["primitive"],
                "parameters": {
                    k: v for k, v in el["parameters"].items()
                    if k != "material_id"
                },
                "material_id": el["parameters"]["material_id"],
                "position": {"x_m": 0, "y_m": 0, "z_m": 0, "rot_z_deg": 0},
                **(
                    {"parent_id": el["joint"]["parent"]}
                    if "joint" in el else {}
                ),
            }
            for el in A1_PLAN
        ]
        row.spec_json = json.dumps(spec)


# --- two-tier surface (plan §3) ---------------------------------------------


def test_registry_surface_two_tier_detail():
    surface = prompts.registry_surface(
        ["basin_round", "plinth", "sculptural_column"]
    )
    # Detail ONLY for the used primitives; cascade table absent.
    assert "  basin_round:" in surface
    assert "  plinth:" in surface
    assert "  sculptural_column:" in surface
    assert "tier_top_diameter_mm" not in surface
    # The index still names every primitive, cascade included.
    assert "tiered_cascade:" in surface
    # Cascade-only guidance leaves with the cascade table.
    assert "UNITS AND SOLVING ORDER" not in surface
    # Assembly constraints are always present.
    assert "Assembly A. exactly ONE root element" in surface


def test_registry_surface_full_fallback_and_unknown_names():
    full = prompts.registry_surface()
    assert "tier_top_diameter_mm" in full
    assert "  basin_round:" in full
    assert "UNITS AND SOLVING ORDER" in full
    # Legacy/unknown primitive names (the Phase 4 five-element massing)
    # fall back to the FULL surface, byte-identical.
    assert prompts.registry_surface(["outer_drum", "ring_inner"]) == full
    assert prompts.registry_surface([]) == full


def test_fabrication_prompt_static_prefix_within_run():
    """ADR-024: repair attempts share the byte-identical cached prefix."""
    spec_json = json.dumps({"meta": {"seed": 1}}, sort_keys=True)
    used = ["plinth", "basin_round"]
    p1 = prompts.fabrication_prompt(spec_json, [], used_primitives=used)
    p2 = prompts.fabrication_prompt(
        spec_json, ["--- ATTEMPT 1 FAILED ---"], used_primitives=used
    )
    prefix1 = p1.split(prompts.CACHE_BREAK)[0]
    prefix2 = p2.split(prompts.CACHE_BREAK)[0]
    assert prefix1 == prefix2


# --- the bridge (fabrication -> design record) ------------------------------


def test_fabricate_assembly_persists_design(
    db, config, base_spec, tmp_path, monkeypatch, assembled
):
    monkeypatch.setenv("LUXURYFORM_DATA_DIR", str(tmp_path / "data"))
    sid = _run_council_session(db, config, base_spec)
    spec_id = _first_spec_id(db, sid)
    _set_assembly_massing(db, spec_id)

    d = FabDispatcher(config.pricing, base_spec, [ASSEMBLY_PROGRAM])
    runner = ScriptedRunner([_sandbox_result(assembled)])
    orch = _fab_orchestrator(db, config, d)
    out = fabricate_spec(orch, sid, spec_id, runner,
                         artifact_root=tmp_path / "fab")

    assert out.success and out.final_status == "passed"
    assert out.design_id is not None

    # The prompt used the two-tier surface: detail for the spec's three
    # primitives, no cascade parameter table.
    assert "  plinth:" in d.fab_prompts[0]
    assert "tier_top_diameter_mm" not in d.fab_prompts[0]

    with db.get_session() as s:
        design = s.get(DesignRow, out.design_id)
        program = s.get(GeneratedProgramRow, out.program_ids[-1])
        assert design is not None
        # Lineage, both directions.
        assert design.generated_program_id == out.program_ids[-1]
        assert design.spec_id == spec_id
        manifest_on_row = json.loads(program.manifest_json)
        assert manifest_on_row["schema"] == "assembly_manifest_v1"
        # THE load-bearing check: the bridge's trusted rebuild exported
        # byte-identical STEP to a direct export of the same composition.
        assert design.geometry_hash == assembled["step_sha256"]
        # The sandbox's own export sha rides along for cross-image
        # comparison, and the design points back at it.
        record = json.loads(design.parameter_json)
        assert record["schema"] == "assembly_design_record_v1"
        assert (record["artifacts"]["sandbox_step_sha256"]
                == assembled["step_sha256"])
        # Validation rows were persisted for the design (mesh + layered).
        from app.db.models import ValidationReportRow

        gate_names = {
            r.gate_name
            for r in s.query(ValidationReportRow)
            .filter_by(design_id=out.design_id).all()
        }
    assert "assembly_mesh" in gate_names
    assert len(gate_names) > 1  # layered gates persisted too


def test_bridge_failure_is_honest(
    db, config, base_spec, tmp_path, monkeypatch, assembled
):
    """A bridge failure never fakes a design and never hides (Rule 12)."""
    monkeypatch.setenv("LUXURYFORM_DATA_DIR", str(tmp_path / "data"))

    def _boom(*args, **kwargs):
        raise RuntimeError("scripted bridge failure (disk full)")

    monkeypatch.setattr(
        "app.council.fabricate._persist_fabricated_assembly", _boom
    )
    sid = _run_council_session(db, config, base_spec)
    spec_id = _first_spec_id(db, sid)
    _set_assembly_massing(db, spec_id)

    d = FabDispatcher(config.pricing, base_spec, [ASSEMBLY_PROGRAM])
    runner = ScriptedRunner([_sandbox_result(assembled)])
    orch = _fab_orchestrator(db, config, d)
    out = fabricate_spec(orch, sid, spec_id, runner,
                         artifact_root=tmp_path / "fab")

    # The fabrication itself PASSED (sandbox artifacts exist) …
    assert out.success and out.final_status == "passed"
    # … but no design is invented, and the failure is stated on the row.
    assert out.design_id is None
    with db.get_session() as s:
        program = s.get(GeneratedProgramRow, out.program_ids[-1])
        artifacts = json.loads(program.artifacts_json)
        assert "scripted bridge failure" in artifacts["design_bridge_error"]
        assert s.query(DesignRow).count() == 0


def test_cascade_fabrication_unchanged(db, config, base_spec, tmp_path):
    """A cascade (non-assembly) pass creates NO design row — the bridge
    only fires on assembly_manifest_v1 params."""
    from tests.test_ast_gate import GOOD

    sid = _run_council_session(db, config, base_spec)
    spec_id = _first_spec_id(db, sid)
    d = FabDispatcher(config.pricing, base_spec, [GOOD])
    runner = ScriptedRunner([_ok_result(tmp_path, with_real_glb=True)])
    orch = _fab_orchestrator(db, config, d)
    out = fabricate_spec(orch, sid, spec_id, runner,
                         artifact_root=tmp_path / "fab")

    assert out.success
    assert out.design_id is None
    with db.get_session() as s:
        assert s.query(DesignRow).count() == 0
        program = s.get(GeneratedProgramRow, out.program_ids[-1])
        assert program.manifest_json is None
