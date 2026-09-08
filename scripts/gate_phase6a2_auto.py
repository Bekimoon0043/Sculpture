#!/usr/bin/env python3
"""PHASE 6 SLICE A2 AUTO GATE — the fabrication -> design bridge, $0.

Runs inside Docker (``docker compose exec backend python
scripts/gate_phase6a2_auto.py``) or on any machine with build123d+trimesh.
No stdin, no prompts, no API calls, no AI-written code (ADR-005: the
pipeline is driven with TRUSTED repo-authored inputs); prints a numbered
transcript; exits 0 only on PASS.

  1. CANONICAL GUARD — the default cascade (seed 42) still exports the
     Phase 2 canonical STEP sha256 e1a59fa6… byte-for-byte.
  2. TWO-TIER SURFACE — the fabrication prompt for a 3-primitive spec
     carries the full index plus detail ONLY for the used primitives;
     measured char counts printed; the ADR-024 static prefix is
     byte-identical across attempts of one run.
  3. PERSISTENCE ROUND-TRIP — the slice A1 composition, built by trusted
     code and persisted through the SAME helper the fabrication loop uses:
     the design is viewable (manifest, scene.glb, validation over HTTP)
     and exportable (LUXEXCHANGE ZIP, self-verified by its shipped
     stdlib verifier).
  4. BYTE-EQUALITY ACROSS PATHS — the bridge-persisted design's STEP
     sha256 equals a direct API build of the same request, and a second
     separate process reproduces it byte-for-byte.
  5. LINEAGE — design -> generated_program round-trip; rows with NULL
     lineage (all history) still load.
  6. MAPPER REFUSALS — assembly_plan_from_spec refuses an unknown
     primitive, a duplicate element_id and a unit mismatch, each naming
     the element and the reason.
  7. VERDICT.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

PASS = "PASS"
FAIL = "FAIL"

PHASE2_CANONICAL_STEP_SHA256 = (
    "e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13"
)
PHASE2_CANONICAL_SEED = 42

#: The slice A1 gate composition — trusted, repo-authored, all basalt.
GATE_PLAN = [
    {
        "element_id": "b1",
        "primitive": "basin_round",
        "parameters": {"diameter_mm": 600, "height_mm": 300, "wall_mm": 25,
                       "floor_mm": 60, "material_id": "basalt_slab"},
        "joint": {"type": "stack_on", "parent": "p1"},
    },
    {
        "element_id": "c1",
        "primitive": "sculptural_column",
        "parameters": {"diameter_mm": 100, "height_mm": 400,
                       "material_id": "basalt_slab"},
        "joint": {"type": "concentric_insert", "parent": "b1"},
    },
    {
        "element_id": "p1",
        "primitive": "plinth",
        "parameters": {"top_diameter_mm": 700, "height_mm": 300,
                       "material_id": "basalt_slab"},
    },
]
# PR-1 (ADR-059): the bridge design this gate persists carries spec
# lineage (spec_id set), and a spec-backed SCALAR limit is now the
# ambiguous-history class — its rebuild paths refuse by design. A
# current-code fabrication program passes the spec's per-axis object,
# so the stand-in models that. Was `"max_module_m": 3.0` until
# 2026-08-28 (the D-10 fixture-expiry pattern, fourth occurrence;
# reported red before this edit).
GATE_FABRICATION = {"max_lift_kg": 2000.0,
                    "max_module_m": {"x": 3.0, "y": 3.0, "z": 3.0}}
GATE_SEED = 42
USED_PRIMITIVES = ["basin_round", "plinth", "sculptural_column"]


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/7] {title}")
    _hline()


def _check(failures: list[str], label: str, ok: bool, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} — {label}" + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(label)


def main() -> int:
    import logging

    logging.getLogger("luxuryform.config").setLevel(logging.CRITICAL)
    logging.getLogger("luxuryform.geometry").setLevel(logging.CRITICAL)
    logging.getLogger("luxuryform.db").setLevel(logging.CRITICAL)
    failures: list[str] = []
    workdir = Path(tempfile.mkdtemp(prefix="luxuryform_gate6a2_"))

    # ------------------------------------------------------------------
    _section(1, "CANONICAL GUARD — Phase 2 STEP hash unchanged")
    from app.geometry.exporters import export_step
    from app.geometry.kernel import step_timestamp_for
    from app.geometry.registry import cascade_fountain

    solid_c, _ = cascade_fountain({}, seed=PHASE2_CANONICAL_SEED)
    sha_c = export_step(
        solid_c, workdir / "canonical.step",
        step_timestamp_for(PHASE2_CANONICAL_SEED),
    )
    print(f"expected: {PHASE2_CANONICAL_STEP_SHA256}")
    print(f"got:      {sha_c}")
    _check(failures, "canonical cascade STEP is byte-identical",
           sha_c == PHASE2_CANONICAL_STEP_SHA256)

    # ------------------------------------------------------------------
    _section(2, "TWO-TIER SURFACE — index always, detail per spec")
    from app.council import prompts

    full = prompts.registry_surface()
    tiered = prompts.registry_surface(USED_PRIMITIVES)
    print(f"full surface: {len(full)} chars (~{len(full) // 4} tokens)")
    print(f"3-primitive surface: {len(tiered)} chars "
          f"(~{len(tiered) // 4} tokens)")
    _check(failures, "index names every primitive",
           all(f"{pid}:" in tiered for pid in
               ("tiered_cascade", "basin_round", "plinth",
                "sculptural_column")))
    _check(failures, "detail present for the three used primitives",
           all(f"  {pid}:" in tiered for pid in USED_PRIMITIVES))
    _check(failures, "cascade parameter table ABSENT",
           "tier_top_diameter_mm" not in tiered)
    _check(failures, "cascade solving-order guidance ABSENT",
           "UNITS AND SOLVING ORDER" not in tiered)
    _check(failures, "unknown/legacy names fall back to the FULL surface",
           prompts.registry_surface(["outer_drum"]) == full)
    spec_json = json.dumps({"meta": {"seed": GATE_SEED}}, sort_keys=True)
    p1 = prompts.fabrication_prompt(spec_json, [],
                                    used_primitives=USED_PRIMITIVES)
    p2 = prompts.fabrication_prompt(spec_json, ["ATTEMPT 1 FAILED"],
                                    used_primitives=USED_PRIMITIVES)
    _check(failures,
           "ADR-024 static prefix byte-identical across repair attempts",
           p1.split(prompts.CACHE_BREAK)[0] == p2.split(prompts.CACHE_BREAK)[0])

    # ------------------------------------------------------------------
    _section(3, "PERSISTENCE ROUND-TRIP — viewable and exportable")
    os.environ["LUXURYFORM_DB"] = str(workdir / "gate.db")
    os.environ["LUXURYFORM_DATA_DIR"] = str(workdir / "data")
    from app.db.database import get_default_db, reset_default_db

    reset_default_db()
    from fastapi.testclient import TestClient

    from app.api.routes_assembly import (
        AssemblyBuildRequest,
        persist_assembly_design,
    )
    from app.db.models import (
        CouncilSessionRow,
        DesignRow,
        DesignSpecRow,
        GeneratedProgramRow,
    )
    from app.geometry import assemble
    from app.main import app

    with TestClient(app) as client:
        db = get_default_db()
        # A trusted stand-in lineage chain: session -> spec -> program row,
        # the FK targets the design record points back through. (No AI
        # wrote any of it; the gate never executes any program.)
        now = "2026-08-26T00:00:00+00:00"
        session_id = "gate6a2-session"
        spec_id = "gate6a2-spec"
        program_id = "gate6a2-trusted-program"
        with db.get_session() as s:
            s.add(CouncilSessionRow(
                id=session_id, created_at=now,
                brief_text="gate stand-in — no AI call was made",
                status="completed", started_at=now, ended_at=now,
                total_cost_usd=0.0, pricing_version="gate",
                arbiter_confidence=None, degraded=0, corrected=0,
            ))
            s.flush()
            s.add(DesignSpecRow(
                id=spec_id, created_at=now, session_id=session_id,
                provider="none", alternative_no=1,
                spec_json="{}", spec_hash="gate", seed=GATE_SEED,
                schema_valid=0,
            ))
            s.flush()
            s.add(GeneratedProgramRow(
                id=program_id, created_at=now,
                session_id=session_id, spec_id=spec_id, attempt_no=1,
                provider="none", model="none",
                program_text="# trusted gate stand-in — never executed",
                program_hash="-", status="passed",
                rejection_reason=None, error_digest=None,
                artifacts_json=None, validation_json=None,
                manifest_json=None,
            ))

        import time as _time

        t0 = _time.perf_counter()
        solid, manifest, element_solids = assemble(
            GATE_PLAN, seed=GATE_SEED, fabrication=GATE_FABRICATION,
            strict=True, return_solids=True,
        )
        request = AssemblyBuildRequest(
            elements=GATE_PLAN, fabrication=GATE_FABRICATION,
            seed=GATE_SEED, strict=True,
        )
        result = persist_assembly_design(
            request, solid, manifest, element_solids, t0=t0, db=db,
            spec_id=spec_id, generated_program_id=program_id,
            sandbox_step_sha256="gate-sandbox-sha-standin",
        )
        design_id = result["design_id"]
        print(f"persisted design: {design_id}")
        print(f"STEP sha256: {result['step_sha256']}")

        r = client.get(f"/api/geometry/assembly/{design_id}/manifest")
        _check(failures, "manifest endpoint answers 200",
               r.status_code == 200, f"HTTP {r.status_code}")
        body = r.json() if r.status_code == 200 else {}
        _check(failures, "manifest carries three elements",
               len(body.get("manifest", {}).get("elements", [])) == 3)
        r = client.get(f"/api/geometry/assembly/{design_id}/scene.glb")
        _check(failures, "scene.glb (per-element, pickable) answers 200",
               r.status_code == 200,
               f"HTTP {r.status_code}, {len(r.content)} bytes")
        r = client.get(f"/api/geometry/assembly/{design_id}/validation")
        _check(failures, "validation endpoint answers 200",
               r.status_code == 200, f"HTTP {r.status_code}")
        if r.status_code == 200:
            gates = r.json().get("gates", r.json())
            print(f"  validation payload keys: {sorted(gates)[:8]}")

        r = client.post(f"/api/geometry/assembly/{design_id}/exports")
        _check(failures, "export job accepted",
               r.status_code in (200, 201), f"HTTP {r.status_code}")
        r = client.get(f"/api/geometry/assembly/{design_id}/luxexchange.zip")
        _check(failures, "LUXEXCHANGE package downloads",
               r.status_code == 200,
               f"HTTP {r.status_code}, {len(r.content)} bytes")
        if r.status_code == 200:
            pkg = workdir / "luxexchange_v1.zip"
            pkg.write_bytes(r.content)
            extracted = workdir / "extracted"
            with zipfile.ZipFile(pkg) as zf:
                zf.extractall(extracted)
            verify = subprocess.run(
                [sys.executable, str(extracted / "verify_luxexchange.py")],
                cwd=str(extracted), capture_output=True, text=True,
            )
            print("  " + (verify.stdout.strip().splitlines() or ["(no output)"])[-1])
            _check(failures, "package self-verifies (shipped verifier, exit 0)",
                   verify.returncode == 0, verify.stderr.strip()[:120])

        # --------------------------------------------------------------
        _section(4, "BYTE-EQUALITY — one persistence path, one identity")
        r = client.post("/api/geometry/assembly/build", json={
            "elements": GATE_PLAN, "fabrication": GATE_FABRICATION,
            "seed": GATE_SEED, "strict": True,
        })
        _check(failures, "direct API build of the same request succeeds",
               r.status_code == 200, f"HTTP {r.status_code}")
        api_sha = r.json().get("step_sha256") if r.status_code == 200 else None
        print(f"bridge-path STEP sha256: {result['step_sha256']}")
        print(f"API-path STEP sha256:    {api_sha}")
        _check(failures, "STEP sha256 identical across both paths",
               api_sha == result["step_sha256"])
        _check(failures, "spec_hash identical across both paths",
               r.status_code == 200
               and r.json().get("spec_hash") == result["spec_hash"],
               str(result["spec_hash"])[:32] + "...")

    child = subprocess.run(
        [sys.executable, "-c", (
            "import sys, json; sys.path.insert(0, r'%s');\n"
            "from app.geometry import assemble\n"
            "from app.geometry.exporters import export_step\n"
            "from app.geometry.kernel import step_timestamp_for\n"
            "plan = json.loads(sys.argv[1])\n"
            "solid, m = assemble(plan, seed=%d, fabrication=json.loads(sys.argv[2]), strict=True)\n"
            "print(export_step(solid, r'%s', step_timestamp_for(%d)))\n"
        ) % (REPO_ROOT / "backend", GATE_SEED,
             workdir / "second_process.step", GATE_SEED),
         json.dumps(GATE_PLAN), json.dumps(GATE_FABRICATION)],
        capture_output=True, text=True,
    )
    second_sha = child.stdout.strip().splitlines()[-1] if child.returncode == 0 else ""
    print(f"second process STEP sha256: {second_sha or child.stderr[-200:]}")
    _check(failures, "byte-identical STEP across two separate processes",
           second_sha == result["step_sha256"])

    # ------------------------------------------------------------------
    _section(5, "LINEAGE — both directions, history tolerated")
    with get_default_db().get_session() as s:
        design = s.get(DesignRow, design_id)
        _check(failures, "design -> generated_program_id round-trip",
               design.generated_program_id == program_id
               and s.get(GeneratedProgramRow, program_id) is not None)
        record = json.loads(design.parameter_json)
        _check(failures, "sandbox STEP sha recorded for cross-image comparison",
               record["artifacts"].get("sandbox_step_sha256")
               == "gate-sandbox-sha-standin")
        rows = s.query(DesignRow).all()
        with_lineage = [r for r in rows if r.generated_program_id]
        without_lineage = [r for r in rows if r.generated_program_id is None]
        _check(failures,
               "NULL-lineage rows (the API path, all history) load alongside",
               len(with_lineage) == 1 and len(without_lineage) >= 1,
               f"{len(rows)} design rows read: {len(with_lineage)} bridged, "
               f"{len(without_lineage)} operator-built")

    # ------------------------------------------------------------------
    _section(6, "MAPPER REFUSALS — wrong specs fail before fabrication")
    from app.geometry.primitives.base import ConstraintViolation
    from app.geometry.spec_mapper import assembly_plan_from_spec

    def _expect(label: str, spec: dict, *needles: str) -> None:
        try:
            assembly_plan_from_spec(spec)
        except ConstraintViolation as exc:
            text = str(exc)
            missing = [n for n in needles if n not in text]
            _check(failures, label, not missing, exc.violations[0][:140])
            return
        _check(failures, label, False, "NO violation raised")

    def _spec(elements) -> dict:
        return {"massing": {"elements": elements}}

    # The example unknown must be a name the registry does NOT have. It was
    # `water_wall` until slice C1 made that real (2026-08-26), then the
    # literal `basin_spline` until PR-5 (2026-09-08, D-10 sweep): a literal
    # expires the day its primitive is built. Now the name is DERIVED at
    # run time and PROVEN absent from the live registry before use, so the
    # check can never rot into asserting the refusal of something real.
    from app.geometry.primitives import PRIMITIVES as _live
    unknown = "not_a_primitive_" + hashlib.sha256(
        ",".join(sorted(_live)).encode()).hexdigest()[:8]
    _check(failures, "the derived unknown name is outside the live registry",
           unknown not in _live, unknown)
    _expect(
        "unknown primitive refused, naming the live registry",
        _spec([{"element_id": "x1", "primitive": unknown,
                "material_id": "basalt_slab", "parameters": {}}]),
        unknown, "live registry",
    )
    _expect(
        "duplicate element_id refused",
        _spec([
            {"element_id": "p1", "primitive": "plinth",
             "material_id": "basalt_slab", "parameters": {}},
            {"element_id": "p1", "primitive": "plinth",
             "material_id": "basalt_slab", "parameters": {}},
        ]),
        "duplicated",
    )
    _expect(
        "unit mismatch refused (deg into mm)",
        _spec([{"element_id": "p1", "primitive": "plinth",
                "material_id": "basalt_slab",
                "parameters": {"height": {"value": 30, "unit": "deg"}}}]),
        "cannot map", "height",
    )

    # ADR-053 — the assembler refuses a knife-edge SEAT (the exact shape
    # the operator built live on 2026-08-26: basin ⌀2000 perched on a
    # hollow plinth ⌀2200/102 — a 2 mm basalt lip under 1,550 kg).
    knife_plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 2200, "height_mm": 800,
                        "wall_mm": 102, "material_id": "basalt_slab"}},
        {"element_id": "b1", "primitive": "basin_round",
         "parameters": {"diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
                        "floor_mm": 160, "material_id": "basalt_slab"},
         "joint": {"type": "stack_on", "parent": "p1"}},
    ]
    try:
        assemble(knife_plan, seed=7)
        _check(failures, "knife-edge stack seat refused (ADR-053)", False,
               "NO violation raised — a 2 mm lip was accepted")
    except ConstraintViolation as exc:
        text = str(exc)
        _check(failures, "knife-edge stack seat refused (ADR-053)",
               "radial seat" in text and "10 mm floor" in text,
               exc.violations[0][:140])

    # ------------------------------------------------------------------
    _section(7, "VERDICT")
    if failures:
        print(f"{FAIL} — {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"{PASS} — Phase 6 slice A2 auto gate: all sections passed at $0, "
          "no network, no AI-written code executed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
