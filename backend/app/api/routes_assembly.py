"""Primitive-agnostic assembly API — Phase 7A, 8 and 9A.

A caller builds from the live primitive registry, persists the returned
`assembly_manifest_v1`, reloads it, runs the layered validation gates
(Phase 8), and produces a reproducible, self-verifying LUXEXCHANGE package
(Phase 9A).

Two design rules this module now keeps that the foundation slice did not:

* GET never mutates. Exporting is a POST that creates a job; the GETs read
  status and serve artifacts. The old download endpoint wrote files and
  inserted DB rows on every request, so three clicks produced nine export
  rows.
* A warning is never reported as a pass. `overall_status` rolls up the four
  Phase 8 statuses, and `passed` means `pass` — not "did not fail".
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.config import (
    DEFAULT_GATE_PROFILE_ID,
    REPO_ROOT,
    load_config_bundle,
)
from app.db.database import get_default_db
from app.db.models import (
    DesignRow,
    DesignSpecRow,
    ExportRow,
    JobRow,
    ProjectRow,
    ValidationReportRow,
)
from app.geometry import ConstraintViolation, PRIMITIVES, assemble
from app.geometry.export_formats import (
    FORMAT_REGISTRY,
    FORMATS_BY_NAME,
    write_exports,
)
from app.geometry.exporters import export_glb, export_step
from app.geometry.gates import WaterContext, validate_layered_gates, worst_status
from app.geometry.kernel import step_timestamp_for
from app.geometry.luxexchange import build_luxexchange_package
from app.geometry.scene_glb import export_scene_glb
from app.geometry.validate import validate_assembly

log = logging.getLogger("luxuryform.api.assembly")

router = APIRouter(prefix="/geometry/assembly", tags=["geometry"])

PACKAGE_NAME = "luxexchange_v1.zip"


def data_dir() -> Path:
    """Root for exported design files (env-overridable for tests)."""
    return Path(os.environ.get("LUXURYFORM_DATA_DIR", str(REPO_ROOT / "data")))


class AssemblyBuildRequest(BaseModel):
    elements: list[dict[str, Any]]
    fabrication: dict[str, Any] | None = None
    water: WaterContext | None = None
    hydraulic_network: dict[str, Any] | None = None
    gate_profile_id: str | None = None
    #: Phase 12: a confirmed intake supplies water context and per-project
    #: site facts (altitude, wind, bearing). Explicit request fields win
    #: over intake-derived ones.
    intake_id: str | None = None
    #: Phase 15E: grouping and explicit branch ancestry. Both are metadata,
    #: never part of the canonical geometry payload/spec hash.
    project_id: str | None = None
    parent_design_id: str | None = None
    seed: int = 0
    #: ADR-034. False (the default for this operator-facing route) builds the
    #: geometry even when a declared workshop limit is breached, and reports
    #: the breach through the fabrication gate. The AI fabrication loop calls
    #: assemble(strict=True) directly and is unaffected.
    strict: bool = False


class ProjectCreateRequest(BaseModel):
    name: str
    brief_text: str = ""


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    status: Literal["open", "archived"] | None = None


def _materials_public() -> dict[str, dict[str, Any]]:
    bundle = load_config_bundle()
    return {
        mid: {
            "name": m.name,
            "category": m.category,
            "density_kg_per_m3": m.density_kg_per_m3,
            "min_wall_mm": m.min_wall_mm,
        }
        for mid, m in bundle.materials.materials.items()
    }


def _primitive_registry_public() -> dict[str, dict[str, Any]]:
    return {
        pid: {
            "purpose": getattr(module, "PURPOSE", ""),
            "can_parent_stack": bool(getattr(module, "CAN_PARENT_STACK", False)),
            "can_parent_insert": bool(getattr(module, "CAN_PARENT_INSERT", False)),
            "parameters": getattr(module, "PARAMETERS"),
        }
        for pid, module in sorted(PRIMITIVES.items())
    }


def _gate_profiles_public() -> dict[str, Any]:
    profiles = load_config_bundle().gate_profiles
    return {
        "version": profiles.version,
        "default": DEFAULT_GATE_PROFILE_ID,
        "profiles": {
            pid: {
                "name": p.name,
                "signed_off": p.signed_off,
                "site_altitude_m": p.site_altitude_m,
                # Which thresholds are still unsupplied, so the UI can say
                # what to fill in rather than only showing needs_input rows.
                "unset_thresholds": sorted(
                    field
                    for field in (
                        "design_wind_speed_m_s", "overturning_safety_factor",
                        "allowable_bearing_kpa", "min_freeboard_mm",
                        "min_reservoir_turnover_min", "jet_velocity_m_s",
                        "nozzle_bore_tolerance_pct", "max_bore_aspect_ratio",
                        "min_service_void_mm", "manual_handling_limit_kg",
                    )
                    if getattr(p, field) is None
                ),
            }
            for pid, p in sorted(profiles.profiles.items())
        },
    }


def _canonical_payload(
    request: AssemblyBuildRequest,
    water: WaterContext | None,
    site_overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema": "assembly_request_v1",
        "seed": int(request.seed),
        "elements": request.elements,
        "fabrication": request.fabrication or {},
        "water": water.model_dump() if water else {},
        "hydraulic_network": request.hydraulic_network or {},
        "gate_profile_id": request.gate_profile_id or DEFAULT_GATE_PROFILE_ID,
        "intake_id": request.intake_id,
        "site_overrides": site_overrides or {},
    }


def _intake_context(
    request: AssemblyBuildRequest,
) -> tuple[WaterContext | None, dict[str, Any] | None]:
    """Resolve water + site context, intake-aware (Phase 12).

    Explicit request water wins over intake water — a caller who states the
    context is not silently second-guessed. Site facts only ever come from
    the intake (there is no request-level site field on purpose: the intake
    is the audited channel for them).
    """
    water = request.water
    site_overrides: dict[str, Any] | None = None
    if request.intake_id:
        from app.db.models import IntakeRow
        from app.intake.models import IntakeV1, to_site_overrides, to_water_context

        db = get_default_db()
        with db.get_session() as session:
            row = session.get(IntakeRow, request.intake_id)
        if row is None:
            raise HTTPException(
                status_code=422,
                detail={"violations": [f"intake {request.intake_id} does not exist"]},
            )
        intake = IntakeV1.model_validate(json.loads(row.normalized_json))
        if water is None:
            water = WaterContext.model_validate(to_water_context(intake))
        site_overrides = to_site_overrides(intake) or None
    return water, site_overrides


def _spec_hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _stored_parameters(
    request_payload: dict[str, Any],
    manifest: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "assembly_design_record_v1",
        "request": request_payload,
        "manifest": manifest,
        "artifacts": artifacts,
    }


def _tool_versions() -> dict[str, Any]:
    versions: dict[str, Any] = {
        "luxuryform_export_package": "1",
        "python": platform.python_version(),
    }
    for name in ("build123d", "trimesh", "ezdxf"):
        try:
            module = __import__(name)
            versions[name] = getattr(module, "__version__", "unknown")
        except Exception as exc:
            versions[f"{name}_error"] = str(exc)
    return versions


def _validation_rows(design_id: str) -> dict[str, Any]:
    db = get_default_db()
    with db.get_session() as session:
        rows = session.execute(
            select(ValidationReportRow)
            .where(ValidationReportRow.design_id == design_id)
            .order_by(ValidationReportRow.created_at.asc())
        ).scalars().all()
    return {row.gate_name: json.loads(row.numbers_json) for row in rows}


#: Statuses a stored report may legitimately carry.
_KNOWN_STATUSES = frozenset({"pass", "warn", "fail", "needs_input"})


def _row_status(row: ValidationReportRow) -> str:
    """Status of one persisted report, without ever inventing a pass.

    Three cases, in order:

    1. The `status` column is set — Phase 8 onward. Use it.
    2. The column is NULL but the stored JSON carries a status — a report
       written between the layered-gate slice and the Phase 8 column patch.
       Use that.
    3. Neither — a pre-Phase-8 row whose only signal is `passed`, which back
       then meant "did not fail" and so cannot distinguish a pass from a
       warning. We do not know, so we say we do not know: `needs_input`.
       Mapping it to `pass` is precisely the lie Phase 8 exists to stop
       (ADR-036), and it would resurface every time an old row was read.
    """
    if row.status in _KNOWN_STATUSES:
        return row.status
    try:
        stored = json.loads(row.numbers_json)
    except (ValueError, TypeError):
        stored = {}
    status = stored.get("status") if isinstance(stored, dict) else None
    if status in _KNOWN_STATUSES:
        return status
    if isinstance(stored, dict) and isinstance(stored.get("passed"), bool):
        # A mesh report: `passed` there really is a two-state verdict.
        if stored.get("schema") is None and "watertight" in stored:
            return "pass" if stored["passed"] else "fail"
    return "needs_input"


def _validation_statuses(design_id: str) -> dict[str, str]:
    db = get_default_db()
    with db.get_session() as session:
        rows = session.execute(
            select(ValidationReportRow)
            .where(ValidationReportRow.design_id == design_id)
        ).scalars().all()
    return {row.gate_name: _row_status(row) for row in rows}


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

@router.get("/defaults")
def get_assembly_defaults() -> dict[str, Any]:
    """Live primitive registry + materials + gate profiles for the UI."""
    return {
        "schema": "assembly_defaults_v1",
        "primitives": _primitive_registry_public(),
        "materials": _materials_public(),
        "joint_types": ["stack_on", "concentric_insert"],
        "gate_profiles": _gate_profiles_public(),
        "export_formats": [
            {"format": f.format, "tier": f.tier, "purpose": f.purpose}
            for f in FORMAT_REGISTRY
        ],
    }


@router.post("/build")
def post_assembly_build(request: AssemblyBuildRequest) -> dict[str, Any]:
    """Assemble -> export STEP/GLB -> validate -> persist -> respond."""
    t0 = time.perf_counter()
    _validate_lineage(request)
    try:
        solid, manifest, element_solids = assemble(
            request.elements,
            seed=request.seed,
            fabrication=request.fabrication,
            strict=request.strict,
            return_solids=True,
        )
    except ConstraintViolation as exc:
        raise HTTPException(
            status_code=422,
            detail={"violations": exc.violations},
        ) from exc
    return persist_assembly_design(
        request, solid, manifest, element_solids, t0=t0
    )


def persist_assembly_design(
    request: AssemblyBuildRequest,
    solid: Any,
    manifest: dict[str, Any],
    element_solids: dict[str, Any],
    *,
    t0: float,
    db: Any = None,
    spec_id: str | None = None,
    generated_program_id: str | None = None,
    sandbox_step_sha256: str | None = None,
) -> dict[str, Any]:
    """Export, validate and persist ONE assembly design — the single
    persistence path for both the operator API above and the Phase 4/6
    fabrication loop (slice A2 bridge).

    Two callers, one function, on purpose: the spec_hash, the canonical
    payload and the STEP bytes must be identical whichever door a design
    came through, or the same geometry would exist under two identities
    (ADR-038 keys precedent on the digest). ``spec_id`` /
    ``generated_program_id`` / ``sandbox_step_sha256`` are fabrication
    lineage; the API path leaves them None.
    """
    water, site_overrides = _intake_context(request)
    request_payload = _canonical_payload(request, water, site_overrides)
    profile_id = request.gate_profile_id or DEFAULT_GATE_PROFILE_ID
    spec_hash = _spec_hash(request_payload)
    out_dir = data_dir() / "designs" / spec_hash
    step_path = out_dir / "assembly.step"
    glb_path = out_dir / "assembly.glb"
    step_sha256 = export_step(solid, step_path, step_timestamp_for(request.seed))
    glb_sha256 = export_glb(solid, glb_path)
    # Phase 14: the pickable per-element scene for the designer workspace.
    # Same geometry, one named node per element; assembly.glb stays fused.
    scene_glb_path = out_dir / "scene.glb"
    scene_glb_sha256 = export_scene_glb(element_solids, scene_glb_path)

    mesh_report = validate_assembly(glb_path, manifest)
    try:
        layered_reports = validate_layered_gates(
            manifest, water=water, gate_profile_id=profile_id,
            site_overrides=site_overrides,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail={"violations": [str(exc)]}) from exc
    build_ms = (time.perf_counter() - t0) * 1000.0

    gate_statuses = {"assembly_mesh": "pass" if mesh_report.passed else "fail"}
    gate_statuses.update({name: r.status for name, r in layered_reports.items()})
    overall = worst_status(gate_statuses.values())

    now = datetime.now(timezone.utc).isoformat()
    design_id = str(uuid.uuid4())
    artifacts = {
        "step_path": str(step_path),
        "glb_path": str(glb_path),
        "step_sha256": step_sha256,
        "glb_sha256": glb_sha256,
        "scene_glb_path": str(scene_glb_path),
        "scene_glb_sha256": scene_glb_sha256,
    }
    if sandbox_step_sha256 is not None:
        # Fabrication lineage: what the ADR-005 sandbox exported for the
        # same program. Recorded so a cross-image determinism drift is
        # visible in the stored record, never silently absorbed.
        artifacts["sandbox_step_sha256"] = sandbox_step_sha256
    db = db if db is not None else get_default_db()
    with db.get_session() as session:
        session.add(
            DesignRow(
                id=design_id,
                created_at=now,
                spec_id=spec_id,
                geometry_hash=step_sha256,
                parameter_json=json.dumps(
                    _stored_parameters(request_payload, manifest, artifacts),
                    sort_keys=True,
                ),
                status="assembly_built",
                seed=request.seed,
                spec_hash=spec_hash,
                build_ms=build_ms,
                glb_path=str(glb_path),
                step_path=str(step_path),
                project_id=request.project_id,
                parent_design_id=request.parent_design_id,
                generated_program_id=generated_program_id,
            )
        )
        session.flush()
        session.add(
            ValidationReportRow(
                id=str(uuid.uuid4()), created_at=now, design_id=design_id,
                gate_name="assembly_mesh",
                passed=1 if mesh_report.passed else 0,
                status=gate_statuses["assembly_mesh"],
                numbers_json=mesh_report.model_dump_json(),
            )
        )
        for gate_name, report in layered_reports.items():
            session.add(
                ValidationReportRow(
                    id=str(uuid.uuid4()), created_at=now, design_id=design_id,
                    gate_name=gate_name,
                    # Phase 8: `passed` means PASS. A warn is not a pass.
                    passed=1 if report.status == "pass" else 0,
                    status=report.status,
                    numbers_json=json.dumps(report.model_dump_wire(), sort_keys=True),
                )
            )

    log.info(
        "assembly build persisted: design=%s spec_hash=%s seed=%d overall=%s",
        design_id, spec_hash, request.seed, overall,
    )
    return {
        "design_id": design_id,
        "project_id": request.project_id,
        "parent_design_id": request.parent_design_id,
        "spec_hash": spec_hash,
        "seed": request.seed,
        "strict": request.strict,
        "gate_profile_id": profile_id,
        "step_sha256": step_sha256,
        "glb_sha256": glb_sha256,
        "glb_url": "/api/geometry/assembly/latest.glb",
        "step_url": "/api/geometry/assembly/latest.step",
        "scene_glb_url": f"/api/geometry/assembly/{design_id}/scene.glb",
        "exports_url": f"/api/geometry/assembly/{design_id}/exports",
        "luxexchange_url": f"/api/geometry/assembly/{design_id}/luxexchange.zip",
        "build_ms": build_ms,
        "manifest": manifest,
        "overall_status": overall,
        "passed": overall == "pass",
        "validation": {**mesh_report.model_dump(), "rows": mesh_report.check_rows()},
        "validation_gates": {
            name: {**report.model_dump_wire(), "rows": report.check_rows()}
            for name, report in layered_reports.items()
        },
    }


@router.post("/preview.glb")
def post_assembly_preview(request: AssemblyBuildRequest) -> Response:
    """Return a CAD-kernel draft GLB without persisting or claiming a gate.

    This deliberately runs the same assembler as a full build. It skips STEP
    export, mesh/layered validation and every database write, so the response
    is real geometry but remains an explicitly unvalidated draft.
    """
    t0 = time.perf_counter()
    try:
        _, _, element_solids = assemble(
            request.elements,
            seed=request.seed,
            fabrication=request.fabrication,
            strict=False,
            return_solids=True,
        )
    except ConstraintViolation as exc:
        raise HTTPException(
            status_code=422,
            detail={"violations": exc.violations},
        ) from exc

    preview_payload = {
        "schema": "assembly_preview_v1",
        "elements": request.elements,
        "fabrication": request.fabrication or {},
        "seed": int(request.seed),
    }
    preview_hash = _spec_hash(preview_payload)
    with tempfile.TemporaryDirectory(prefix="luxuryform_preview_") as tmp:
        path = Path(tmp) / "preview.glb"
        export_scene_glb(element_solids, path)
        content = path.read_bytes()

    build_ms = (time.perf_counter() - t0) * 1000.0
    return Response(
        content=content,
        media_type="model/gltf-binary",
        headers={
            "Cache-Control": "no-store",
            "X-LuxuryForm-Preview-Hash": preview_hash,
            "X-LuxuryForm-Build-Ms": f"{build_ms:.3f}",
            "X-LuxuryForm-Element-Count": str(len(element_solids)),
        },
    )


# ---------------------------------------------------------------------------
# Reading the latest build
# ---------------------------------------------------------------------------

def _latest_assembly_design() -> DesignRow:
    db = get_default_db()
    with db.get_session() as session:
        row = session.execute(
            select(DesignRow)
            .where(DesignRow.status == "assembly_built")
            .order_by(DesignRow.created_at.desc())
            .limit(1)
        ).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="no assembly build yet")
    return row


def _design_or_404(design_id: str) -> DesignRow:
    db = get_default_db()
    with db.get_session() as session:
        row = session.get(DesignRow, design_id)
    if row is None or row.status != "assembly_built":
        raise HTTPException(status_code=404, detail=f"no assembly design {design_id}")
    return row


def _module_limit_provenance(row: DesignRow) -> dict[str, Any]:
    """The PR-1 (ADR-059) compatibility truth table, computed live.

    - spec_id NULL  + scalar  -> deliberate cubic Designer/API limit; valid.
    - spec_id NULL  + {x,y,z} -> deliberate per-axis API limit; valid.
    - spec_id SET   + {x,y,z} -> corrected spec build; valid.
    - spec_id SET   + scalar  -> historical collapsed-spec design;
      needs_input, rebuild required (recovered spec axes named when the
      original Design Spec verifies: max(x,y,z) must equal the stored
      scalar, or the origin is unknown).
    - Missing, malformed or mismatched original-spec provenance ->
      needs_input; NEVER assume cubic.

    Returned dict: kind, status ("ok" | "needs_input"), optional
    spec_max_module_m, and — when a rebuild is required — the one exact
    safe next action.
    """
    stored = json.loads(row.parameter_json)
    limit = ((stored.get("request") or {}).get("fabrication")
             or {}).get("max_module_m")
    if limit is None:
        return {"kind": "no_limit", "status": "ok"}
    if isinstance(limit, dict):
        kind = "per_axis_spec_build" if row.spec_id else "per_axis_request"
        return {"kind": kind, "status": "ok"}
    if isinstance(limit, bool) or not isinstance(limit, (int, float)):
        return {
            "kind": "malformed", "status": "needs_input",
            "action": _rebuild_action(row, None),
        }
    if row.spec_id is None:
        return {"kind": "cubic_request", "status": "ok"}

    # Spec-backed scalar: the collapse. Recover and VERIFY the original.
    db = get_default_db()
    with db.get_session() as session:
        spec_row = session.get(DesignSpecRow, row.spec_id)
    spec_limit: dict[str, Any] | None = None
    if spec_row is not None:
        try:
            spec = json.loads(spec_row.spec_json)
            candidate = (spec.get("fabrication") or {}).get("max_module_m")
            if (isinstance(candidate, dict)
                    and set(candidate) == {"x", "y", "z"}):
                spec_limit = {a: float(candidate[a]) for a in ("x", "y", "z")}
        except (ValueError, TypeError):
            spec_limit = None
    if spec_limit is not None:
        # The mapper stored max(x,y,z); anything else means the generated
        # program did not use the mapper and the origin is unknown.
        if abs(max(spec_limit.values()) - float(limit)) <= 1e-9:
            return {
                "kind": "collapsed_spec", "status": "needs_input",
                "spec_max_module_m": spec_limit,
                "action": _rebuild_action(row, spec_limit),
            }
    return {
        "kind": "unverifiable", "status": "needs_input",
        "action": _rebuild_action(row, None),
    }


def _rebuild_action(row: DesignRow,
                    spec_limit: dict[str, float] | None) -> str:
    if spec_limit is not None:
        limit_text = (f'{{"x": {spec_limit["x"]:g}, "y": {spec_limit["y"]:g},'
                      f' "z": {spec_limit["z"]:g}}}')
        source = f"its Design Spec ({row.spec_id}) declares"
    else:
        limit_text = '{"x": ..., "y": ..., "z": ...}'
        source = "confirm the true per-axis envelope with the operator and use"
    return (
        f"rebuild this design once: POST /api/geometry/assembly/build with "
        f"the stored elements and seed, and fabrication.max_module_m set "
        f"per-axis — {source} {limit_text}. Stored artifacts stay readable; "
        f"only geometry-rebuilding operations are refused until then."
    )


def _refuse_ambiguous_rebuild(row: DesignRow, operation: str) -> None:
    """PR-1 Amendment 2: a geometry-REBUILDING operation must not silently
    reinterpret a collapsed-spec scalar as a cubic envelope. Viewing stored
    artifacts stays allowed; the rebuild paths refuse with the one action."""
    provenance = _module_limit_provenance(row)
    if provenance["status"] != "ok":
        raise HTTPException(
            status_code=409,
            detail=(
                f"{operation} refused: this design's stored "
                f"fabrication.max_module_m is a single number whose per-axis "
                f"truth was discarded at build time "
                f"(provenance: {provenance['kind']}). "
                + provenance["action"]
            ),
        )


@router.get("/latest/manifest")
def get_latest_manifest() -> dict[str, Any]:
    row = _latest_assembly_design()
    stored = json.loads(row.parameter_json)
    return {
        "created_at": row.created_at,
        "design_id": row.id,
        "project_id": row.project_id,
        "parent_design_id": row.parent_design_id,
        "spec_hash": row.spec_hash,
        "seed": row.seed,
        "manifest": stored["manifest"],
        "request": stored["request"],
        "artifacts": stored["artifacts"],
        "module_limit_provenance": _module_limit_provenance(row),
    }


@router.get("/latest.glb")
def get_latest_glb() -> FileResponse:
    row = _latest_assembly_design()
    if not row.glb_path or not Path(row.glb_path).exists():
        raise HTTPException(status_code=404, detail="latest assembly has no GLB on disk")
    return FileResponse(row.glb_path, media_type="model/gltf-binary", filename="assembly.glb")


@router.get("/latest.step")
def get_latest_step() -> FileResponse:
    row = _latest_assembly_design()
    if not row.step_path or not Path(row.step_path).exists():
        raise HTTPException(status_code=404, detail="latest assembly has no STEP on disk")
    return FileResponse(row.step_path, media_type="application/step", filename="assembly.step")


def _validation_payload(row: DesignRow) -> dict[str, Any]:
    by_gate = _validation_rows(row.id)
    if not by_gate:
        raise HTTPException(status_code=404, detail="no assembly validation report yet")
    statuses = _validation_statuses(row.id)
    overall = worst_status(statuses.values())
    return {
        "design_id": row.id,
        "gate_name": "phase8_layered",
        "overall_status": overall,
        # A warn is NOT a pass, and neither is needs_input.
        "passed": overall == "pass",
        "blocking": overall == "fail",
        "gate_statuses": statuses,
        "validation": by_gate.get("assembly_mesh"),
        "gates": by_gate,
    }


@router.get("/latest/validation")
def get_latest_validation() -> dict[str, Any]:
    return _validation_payload(_latest_assembly_design())


@router.get("/{design_id}/validation")
def get_design_validation(design_id: str) -> dict[str, Any]:
    return _validation_payload(_design_or_404(design_id))


# ---------------------------------------------------------------------------
# Phase 14 — designer workspace reads
# ---------------------------------------------------------------------------
# The workspace needs three things the latest-only routes cannot give it:
# a PICKABLE per-element scene, per-design artifact reads (history restore
# and side-by-side compare load designs that are no longer "latest"), and a
# browsable design list for the history strip.


def _ensure_scene_glb(row: DesignRow) -> Path:
    """Path to the design's scene.glb, regenerating it if absent.

    Designs built before Phase 14 have no scene.glb on disk. The stored
    request is a complete, replayable build input and the assembler is
    deterministic, so the scene is rebuilt from it once and cached next to
    assembly.glb. GET stays semantically a read: same inputs, same file,
    no DB writes.
    """
    if not row.glb_path:
        raise HTTPException(status_code=404, detail="design has no GLB on disk")
    path = Path(row.glb_path).parent / "scene.glb"
    if path.exists():
        # Existing artifacts stay viewable whatever the limit provenance.
        return path
    # Regeneration REBUILDS geometry from the stored request — refuse if
    # that would silently reinterpret a collapsed-spec scalar (ADR-059).
    _refuse_ambiguous_rebuild(row, "scene.glb regeneration")
    stored = json.loads(row.parameter_json)
    request = stored.get("request") or {}
    try:
        _, _, element_solids = assemble(
            request.get("elements") or [],
            seed=int(request.get("seed", 0)),
            fabrication=request.get("fabrication") or None,
            # The design built successfully once; strict=False keeps a
            # recorded workshop-limit breach from turning a read into a 500.
            strict=False,
            return_solids=True,
        )
    except ConstraintViolation as exc:
        # Deterministic rebuild of a previously built design cannot violate
        # constraints unless config (materials.yaml) changed underneath it.
        # Say exactly that instead of pretending the design is gone.
        raise HTTPException(
            status_code=409,
            detail=(
                "stored design no longer rebuilds under the current "
                f"material/config values: {'; '.join(exc.violations[:3])}"
            ),
        ) from exc
    export_scene_glb(element_solids, path)
    return path


@router.get("/latest/scene.glb")
def get_latest_scene_glb() -> FileResponse:
    path = _ensure_scene_glb(_latest_assembly_design())
    return FileResponse(path, media_type="model/gltf-binary", filename="scene.glb")


@router.get("/designs")
def list_designs(
    limit: int = 50,
    project_id: str | None = None,
    ungrouped: bool = False,
) -> dict[str, Any]:
    """Newest-first assembly builds — the history strip's persistence.

    Summary only (the full manifest rides on /{design_id}/manifest): what a
    designer needs to recognise a variant — when, what elements, how heavy,
    and the honest validation verdict.
    """
    limit = max(1, min(int(limit), 200))
    db = get_default_db()
    if project_id and ungrouped:
        raise HTTPException(status_code=422, detail="choose project_id or ungrouped, not both")
    query = select(DesignRow).where(DesignRow.status == "assembly_built")
    if project_id:
        query = query.where(DesignRow.project_id == project_id)
    elif ungrouped:
        query = query.where(DesignRow.project_id.is_(None))
    with db.get_session() as session:
        if project_id and session.get(ProjectRow, project_id) is None:
            raise HTTPException(status_code=404, detail=f"no project {project_id}")
        rows = session.execute(
            query.order_by(DesignRow.created_at.desc()).limit(limit)
        ).scalars().all()
    designs = []
    for row in rows:
        try:
            stored = json.loads(row.parameter_json)
        except (ValueError, TypeError):
            stored = {}
        manifest = stored.get("manifest") or {}
        elements = manifest.get("elements") or []
        statuses = _validation_statuses(row.id)
        designs.append({
            "design_id": row.id,
            "project_id": row.project_id,
            "parent_design_id": row.parent_design_id,
            "created_at": row.created_at,
            "spec_hash": row.spec_hash,
            "seed": row.seed,
            "element_count": len(elements),
            "primitives": [e.get("primitive") for e in elements],
            "element_ids": [e.get("element_id") for e in elements],
            "total_mass_kg": manifest.get("total_mass_kg"),
            "overall_status": worst_status(statuses.values()) if statuses else None,
            "glb_url": f"/api/geometry/assembly/{row.id}.glb",
            "scene_glb_url": f"/api/geometry/assembly/{row.id}/scene.glb",
        })
    return {"count": len(designs), "designs": designs}


@router.get("/{design_id}/scene.glb")
def get_design_scene_glb(design_id: str) -> FileResponse:
    path = _ensure_scene_glb(_design_or_404(design_id))
    return FileResponse(path, media_type="model/gltf-binary", filename="scene.glb")


@router.get("/{design_id}.glb")
def get_design_glb(design_id: str) -> FileResponse:
    row = _design_or_404(design_id)
    if not row.glb_path or not Path(row.glb_path).exists():
        raise HTTPException(status_code=404, detail="design has no GLB on disk")
    return FileResponse(row.glb_path, media_type="model/gltf-binary", filename="assembly.glb")


@router.get("/{design_id}/manifest")
def get_design_manifest(design_id: str) -> dict[str, Any]:
    row = _design_or_404(design_id)
    stored = json.loads(row.parameter_json)
    return {
        "created_at": row.created_at,
        "design_id": row.id,
        "project_id": row.project_id,
        "parent_design_id": row.parent_design_id,
        "spec_hash": row.spec_hash,
        "seed": row.seed,
        "manifest": stored["manifest"],
        "request": stored["request"],
        "artifacts": stored["artifacts"],
        # PR-1 (ADR-059): computed live, never stored — whether this
        # design's module limit is trustworthy per-axis, a deliberate
        # cubic envelope, or a collapsed-spec scalar needing a rebuild.
        "module_limit_provenance": _module_limit_provenance(row),
    }


# ---------------------------------------------------------------------------
# Export jobs (Phase 9A)
# ---------------------------------------------------------------------------

def _package_dir(design_id: str) -> Path:
    return data_dir() / "exports" / design_id


def _export_rows(design_id: str) -> list[dict[str, Any]]:
    db = get_default_db()
    with db.get_session() as session:
        rows = session.execute(
            select(ExportRow).where(ExportRow.design_id == design_id)
        ).scalars().all()
    # Registry order, not alphabetical: STEP is the file a machinist opens
    # and belongs at the top of its group, not after BREP. Anything not in
    # the registry (the package row) sorts last.
    order = {spec.format: i for i, spec in enumerate(FORMAT_REGISTRY)}
    rows = sorted(rows, key=lambda r: (order.get(r.format, len(order)), r.format))
    out = []
    for r in rows:
        spec = FORMATS_BY_NAME.get(r.format)
        out.append({
            "format": r.format,
            "status": r.status,
            "path": r.path or None,
            "sha256": r.sha256,
            "bytes": r.bytes,
            "duration_ms": r.duration_ms,
            "error": r.error,
            "job_id": r.job_id,
            "created_at": r.created_at,
            "tier": spec.tier if spec else "package",
            "purpose": spec.purpose if spec else "the package itself",
            "filename": spec.filename if spec else PACKAGE_NAME,
            # Only offer a link for something that can actually be fetched.
            "download_url": (
                f"/api/geometry/assembly/{design_id}/exports/{r.format}/download"
                if r.status == "included" and r.format in FORMATS_BY_NAME
                else None
            ),
        })
    return out


def _upsert_export_rows(
    design_id: str, job_id: str, entries: list[dict[str, Any]], versions: str
) -> None:
    """One row per (design_id, format). Re-exporting UPDATES, never appends."""
    now = datetime.now(timezone.utc).isoformat()
    db = get_default_db()
    with db.get_session() as session:
        existing = {
            r.format: r
            for r in session.execute(
                select(ExportRow).where(ExportRow.design_id == design_id)
            ).scalars().all()
        }
        for entry in entries:
            row = existing.get(entry["format"])
            if row is None:
                row = ExportRow(
                    id=str(uuid.uuid4()), created_at=now, design_id=design_id,
                    format=entry["format"], path="", tool_versions_json=versions,
                )
                session.add(row)
            row.path = entry.get("path") or ""
            row.status = entry["status"]
            row.sha256 = entry.get("sha256")
            row.bytes = entry.get("bytes")
            row.duration_ms = entry.get("duration_ms")
            row.error = entry.get("error") or entry.get("reason")
            row.job_id = job_id
            row.tool_versions_json = versions


def _costing_for(design_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """BOM for the package, or an honest reason it could not be computed.

    reproducible=True: the sealed BOM is stamped with the design's own
    creation time, never the wall clock, so two exports of one design
    produce the same package digest (ADR-035/037, hole found in ADR-056).
    """
    try:
        from app.api.routes_costing import _bom_for

        _, bom, _params = _bom_for(design_id, reproducible=True)
        return bom.as_dict(), None
    except HTTPException as exc:
        return None, f"costing unavailable: {exc.detail}"
    except Exception as exc:
        return None, f"costing unavailable: {type(exc).__name__}: {exc}"


@router.post("/{design_id}/exports")
def post_design_exports(design_id: str) -> dict[str, Any]:
    """Run every export format, then seal a reproducible LUXEXCHANGE package.

    This is the only endpoint that writes. It is idempotent by design: the
    same design re-exported overwrites its own rows and produces a
    byte-identical package.
    """
    row = _design_or_404(design_id)
    # The export job REBUILDS the solid from the stored request — refuse
    # rather than silently reinterpret a collapsed-spec scalar (ADR-059).
    _refuse_ambiguous_rebuild(row, "export/package rebuild")
    stored = json.loads(row.parameter_json)
    manifest = stored["manifest"]
    request_payload = stored["request"]
    seed = int(row.seed or 0)

    job_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()
    db = get_default_db()
    with db.get_session() as session:
        session.add(JobRow(
            id=job_id, session_id=design_id, ts=started, job_type="export",
            status="running",
            state_json=json.dumps({"design_id": design_id, "step": "rebuild_solid"}),
        ))

    def _finish(status: str, state: dict[str, Any], halt: str | None = None) -> None:
        with db.get_session() as session:
            job = session.get(JobRow, job_id)
            if job is not None:
                job.status = status
                job.state_json = json.dumps(state, sort_keys=True)
                job.halt_reason = halt

    t0 = time.perf_counter()
    try:
        # Rebuild the solid from the persisted manifest's own request. The
        # B-rep is needed for the CAD-tier formats and is not stored.
        solid, _ = assemble(
            request_payload["elements"],
            seed=seed,
            fabrication=request_payload.get("fabrication") or None,
            strict=False,
        )
    except Exception as exc:
        # Phase 13 R3: classify the failure so the operator knows the next
        # action. input = fix the request; resource = free disk/memory;
        # defect = our bug, do not retry.
        if isinstance(exc, ConstraintViolation):
            klass = "input"
        elif isinstance(exc, (OSError, MemoryError)):
            klass = "resource"
        else:
            klass = "defect"
        _finish("failed", {"design_id": design_id, "step": "rebuild_solid"},
                halt=f"{klass}: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"could not rebuild geometry for export: {type(exc).__name__}: {exc}",
        ) from exc

    out_dir = _package_dir(design_id)
    results = write_exports(
        solid, out_dir,
        step_path=Path(row.step_path) if row.step_path else None,
        glb_path=Path(row.glb_path) if row.glb_path else None,
        seed=seed,
    )

    costing, costing_reason = _costing_for(design_id)
    validation_reports = _validation_rows(design_id)
    package_path = out_dir / PACKAGE_NAME
    versions = _tool_versions()

    _, package_manifest, digest = build_luxexchange_package(
        package_path,
        seed=seed,
        design={
            "design_id": row.id,
            "created_at": row.created_at,
            "status": row.status,
            "spec_hash": row.spec_hash,
            "geometry_hash": row.geometry_hash,
            "seed": seed,
            "gate_statuses": _validation_statuses(design_id),
            "overall_status": worst_status(_validation_statuses(design_id).values()),
        },
        request_payload=request_payload,
        assembly_manifest=manifest,
        validation_reports=validation_reports,
        exports=results,
        costing=costing,
        costing_unavailable_reason=costing_reason,
        # Provenance is keyed to the DESIGN, not to this export run. Using
        # the export wall clock here would make the package bytes differ on
        # every re-export for a reason that has nothing to do with the
        # design. When the export ran is recorded on the job row, which is
        # where a timestamp belongs.
        provenance={
            "design_created_at": row.created_at,
            "platform": platform.platform(),
            "tool_versions": versions,
        },
    )

    entries = [r.to_manifest_entry() for r in results]
    entries.append({
        "format": "LUXEXCHANGE",
        "status": "included",
        "tier": "package",
        "purpose": "portable, self-verifying design package",
        "path": str(package_path),
        "sha256": hashlib.sha256(package_path.read_bytes()).hexdigest(),
        "bytes": package_path.stat().st_size,
    })
    _upsert_export_rows(
        design_id, job_id, entries, json.dumps(versions, sort_keys=True)
    )
    duration_ms = (time.perf_counter() - t0) * 1000.0
    _finish("completed", {
        "design_id": design_id, "step": "sealed",
        "content_digest": digest, "duration_ms": duration_ms,
    })

    log.info(
        "export job %s completed for design %s: digest=%s in %.0f ms",
        job_id, design_id, digest, duration_ms,
    )
    return {
        "design_id": design_id,
        "job_id": job_id,
        "schema": package_manifest["schema"],
        "content_digest": digest,
        "package_path": str(package_path),
        "package_sha256": entries[-1]["sha256"],
        "duration_ms": duration_ms,
        "exports": entries,
        "tool_versions": versions,
        "luxexchange_url": f"/api/geometry/assembly/{design_id}/luxexchange.zip",
    }


def _exports_status(row: DesignRow) -> dict[str, Any]:
    rows = _export_rows(row.id)
    package_path = _package_dir(row.id) / PACKAGE_NAME
    db = get_default_db()
    with db.get_session() as session:
        job = session.execute(
            select(JobRow).where(JobRow.session_id == row.id)
            .where(JobRow.job_type == "export")
            .order_by(JobRow.ts.desc()).limit(1)
        ).scalars().first()
        job_state = (
            {"job_id": job.id, "status": job.status, "ts": job.ts,
             "state": json.loads(job.state_json), "halt_reason": job.halt_reason}
            if job else None
        )
    return {
        "design_id": row.id,
        "schema": "luxexchange_v1",
        "package_built": package_path.exists(),
        "package_path": str(package_path) if package_path.exists() else None,
        "package_bytes": package_path.stat().st_size if package_path.exists() else None,
        "content_digest": (job_state or {}).get("state", {}).get("content_digest"),
        "last_job": job_state,
        "exports": rows,
        "counts": _status_counts(rows),
        "luxexchange_url": f"/api/geometry/assembly/{row.id}/luxexchange.zip",
        # The formats this build could produce, so the UI can show what is
        # possible before anything has been exported.
        "catalog": [
            {"format": f.format, "tier": f.tier, "purpose": f.purpose}
            for f in FORMAT_REGISTRY
        ],
    }


def _project_payload(row: ProjectRow, variant_count: int) -> dict[str, Any]:
    return {
        "project_id": row.id,
        "created_at": row.created_at,
        "name": row.name,
        "brief_text": row.brief_text,
        "status": row.status,
        "variant_count": variant_count,
    }


@router.get("/projects")
def list_projects() -> dict[str, Any]:
    """Project selector data, newest first, including archived projects."""
    db = get_default_db()
    with db.get_session() as session:
        rows = session.execute(
            select(ProjectRow).order_by(ProjectRow.created_at.desc())
        ).scalars().all()
        counts = {
            row.id: session.scalar(
                select(func.count())
                .select_from(DesignRow)
                .where(
                    DesignRow.project_id == row.id,
                    DesignRow.status == "assembly_built",
                )
            ) or 0
            for row in rows
        }
    return {
        "count": len(rows),
        "projects": [_project_payload(row, counts[row.id]) for row in rows],
    }


@router.post("/projects", status_code=201)
def create_project(request: ProjectCreateRequest) -> dict[str, Any]:
    name = request.name.strip()
    if not name or len(name) > 120:
        raise HTTPException(
            status_code=422,
            detail="project name must contain 1 to 120 characters",
        )
    row = ProjectRow(
        id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        name=name,
        brief_text=request.brief_text.strip(),
        status="open",
    )
    db = get_default_db()
    with db.get_session() as session:
        session.add(row)
    return _project_payload(row, 0)


@router.patch("/projects/{project_id}")
def update_project(project_id: str, request: ProjectUpdateRequest) -> dict[str, Any]:
    db = get_default_db()
    with db.get_session() as session:
        row = session.get(ProjectRow, project_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"no project {project_id}")
        if request.name is not None:
            name = request.name.strip()
            if not name or len(name) > 120:
                raise HTTPException(
                    status_code=422,
                    detail="project name must contain 1 to 120 characters",
                )
            row.name = name
        if request.status is not None:
            row.status = request.status
        count = session.scalar(
            select(func.count())
            .select_from(DesignRow)
            .where(
                DesignRow.project_id == row.id,
                DesignRow.status == "assembly_built",
            )
        ) or 0
    return _project_payload(row, count)


def _validate_lineage(request: AssemblyBuildRequest) -> None:
    """Reject unknown, archived or cross-project lineage before CAD work."""
    db = get_default_db()
    with db.get_session() as session:
        if request.project_id:
            project = session.get(ProjectRow, request.project_id)
            if project is None:
                raise HTTPException(
                    status_code=422,
                    detail={"violations": [f"project {request.project_id} does not exist"]},
                )
            if project.status != "open":
                raise HTTPException(
                    status_code=422,
                    detail={"violations": [f"project {request.project_id} is archived"]},
                )
        if request.parent_design_id:
            parent = session.get(DesignRow, request.parent_design_id)
            if parent is None or parent.status != "assembly_built":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "violations": [
                            f"parent design {request.parent_design_id} does not exist"
                        ]
                    },
                )
            if parent.project_id != request.project_id:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "violations": [
                            "parent design and new design must belong to the same project"
                        ]
                    },
                )


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = row.get("status") or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


# NOTE: the /latest/... routes MUST be registered before the /{design_id}/...
# ones. FastAPI matches in registration order, so a path parameter declared
# first would swallow "latest" as a design id and 404 on it.

@router.get("/latest/exports")
def get_latest_exports() -> dict[str, Any]:
    """Export status. Reads only — no files written, no rows inserted."""
    return _exports_status(_latest_assembly_design())


@router.get("/{design_id}/exports")
def get_design_exports(design_id: str) -> dict[str, Any]:
    return _exports_status(_design_or_404(design_id))


def _serve_package(row: DesignRow) -> FileResponse:
    package_path = _package_dir(row.id) / PACKAGE_NAME
    if not package_path.exists():
        raise HTTPException(
            status_code=409,
            detail=(
                f"no export package for design {row.id} yet — POST to "
                f"/api/geometry/assembly/{row.id}/exports to build one"
            ),
        )
    return FileResponse(
        package_path, media_type="application/zip",
        filename=f"luxexchange_{row.id}.zip",
    )


def _serve_export_file(row: DesignRow, fmt: str) -> FileResponse:
    """Serve ONE exported file.

    The operator's most common real request is "just send me the DXF" — a
    format listed in the panel that cannot be downloaded on its own is a
    dead end. Reads only; the file must already have been exported.
    """
    spec = FORMATS_BY_NAME.get(fmt.upper())
    if spec is None:
        raise HTTPException(
            status_code=404,
            detail=f"unknown format {fmt!r}; known: {sorted(FORMATS_BY_NAME)}",
        )
    db = get_default_db()
    with db.get_session() as session:
        export = session.execute(
            select(ExportRow)
            .where(ExportRow.design_id == row.id)
            .where(ExportRow.format == spec.format)
        ).scalars().first()
        status = export.status if export else None
        path = Path(export.path) if export and export.path else None
        error = export.error if export else None

    if export is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{spec.format} has not been exported for design {row.id} — POST "
                f"to /api/geometry/assembly/{row.id}/exports first"
            ),
        )
    if status != "included" or path is None or not path.exists():
        raise HTTPException(
            status_code=409,
            detail=(
                f"{spec.format} is not available for this design "
                f"(status: {status}). {error or spec.reason or ''}".strip()
            ),
        )
    return FileResponse(path, media_type=spec.media_type, filename=spec.filename)


@router.get("/latest/exports/{fmt}/download")
def get_latest_export_file(fmt: str) -> FileResponse:
    return _serve_export_file(_latest_assembly_design(), fmt)


@router.get("/{design_id}/exports/{fmt}/download")
def get_design_export_file(design_id: str, fmt: str) -> FileResponse:
    return _serve_export_file(_design_or_404(design_id), fmt)


@router.get("/latest/luxexchange.zip")
def get_latest_luxexchange_zip() -> FileResponse:
    return _serve_package(_latest_assembly_design())


@router.get("/{design_id}/luxexchange.zip")
def get_design_luxexchange_zip(design_id: str) -> FileResponse:
    return _serve_package(_design_or_404(design_id))
