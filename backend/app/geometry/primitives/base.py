"""Shared machinery for the primitive library (Phase 6 slice A, ADR-032).

Every primitive is one module exposing the same surface:

    PRIMITIVE_ID          str — the registry key (== massing.elements[].primitive)
    PURPOSE               str — one line, feeds the A2 two-tier prompt index
    CAN_PARENT_STACK      bool — may a child stack_on this primitive?
    CAN_PARENT_INSERT     bool — may a child concentric_insert into it?
    PARAMETERS            dict — unit/default/min/max/type/notes per parameter
    validate(raw, materials=None) -> params model (ConstraintViolation on breach)
    build(params) -> build123d Solid — ONE watertight solid, origin at the
                     centre of the base face, axis Z (the cascade convention)
    anchors(params) -> {"base": 0.0, "top": z_mm, "seat": z_mm | None}
                     seat = where an inserted child STANDS (top of the floor
                     for a basin); None = nothing can stand inside
    max_outer_diameter_mm(params) -> float — widest footprint, for fit checks
    inner_diameter_mm(params) -> float | None — clear interior bore of a
                     basin-like primitive; None = no interior

The validation pattern is the cascade's (ADD-4): ranges enforced by a
pydantic model GENERATED from PARAMETERS (no duplicated bounds to drift),
cross-parameter hard constraints collected into ONE ConstraintViolation
whose every message carries the real computed numbers.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import Field, create_model

from app.core.config import Material, load_config_bundle


class ConstraintViolation(ValueError):
    """Raised by a primitive's validate() / the assembler with EVERY violated
    rule listed. Each entry is a plain-language sentence carrying the real
    computed numbers (ADD-4) — the operator can act on it directly."""

    def __init__(self, violations: list[str]) -> None:
        if not violations:
            raise ValueError("ConstraintViolation needs at least one violation")
        self.violations = list(violations)
        super().__init__("; ".join(self.violations))


def load_materials() -> dict[str, Material]:
    return load_config_bundle().materials.materials


def make_params_model(name: str, parameters: dict[str, dict[str, Any]]):
    """Build the pydantic ranges model from a PARAMETERS table.

    A spec entry with ``"optional": True`` becomes ``type | None`` with
    default None — used for derived defaults (e.g. column_wall_mm defaults
    to basin_wall_mm, floor_mm to wall_mm) that are resolved in validate()
    AFTER range checking, so the resolution rule lives in exactly one place.
    """
    fields: dict[str, Any] = {}
    for pname, spec in parameters.items():
        py_type: Any = {"int": int, "float": float, "str": str}[spec["type"]]
        if spec.get("optional"):
            fields[pname] = (
                py_type | None,
                Field(default=None, ge=spec["min"], le=spec["max"]),
            )
        elif py_type is str:
            fields[pname] = (py_type, Field(default=spec["default"]))
        else:
            fields[pname] = (
                py_type,
                Field(default=spec["default"], ge=spec["min"], le=spec["max"]),
            )
    return create_model(name, **fields)


def merge_raw(
    primitive_id: str,
    parameters: dict[str, dict[str, Any]],
    raw: dict[str, Any],
    violations: list[str],
) -> dict[str, Any]:
    """Defaults + raw, with unknown keys reported (never silently dropped)."""
    for name in sorted(set(raw) - set(parameters)):
        violations.append(
            f"unknown parameter {name!r} for {primitive_id}; known parameters: "
            + ", ".join(sorted(parameters))
        )
    merged = {name: spec["default"] for name, spec in parameters.items()}
    merged.update({k: v for k, v in raw.items() if k in parameters})
    return merged


def collect_model_errors(exc: Exception, violations: list[str]) -> None:
    """Reformat pydantic ValidationError entries into real-number sentences."""
    for err in exc.errors():  # type: ignore[attr-defined]
        loc = ".".join(str(p) for p in err.get("loc", ())) or "?"
        msg = err.get("msg", "invalid")
        given = err.get("input", "?")
        violations.append(f"{loc}={given!r}: {msg}")


def check_material(
    primitive_id: str,
    material_id: str,
    materials: dict[str, Material],
    violations: list[str],
) -> Material | None:
    material = materials.get(material_id)
    if material is None:
        violations.append(
            f"{primitive_id}: material_id={material_id!r} not in materials.yaml "
            f"(available: {', '.join(sorted(materials))})"
        )
    return material


def check_wall_envelope(
    label: str,
    wall_mm: float,
    material_id: str,
    material: Material,
    violations: list[str],
) -> None:
    """Hard constraint 2 (ADR-027), shared by every primitive with a wall."""
    if wall_mm < material.min_wall_mm:
        violations.append(
            f"{label}={wall_mm:g} < material minimum "
            f"{material.min_wall_mm:g} mm for {material_id} ({material.name})"
        )
    elif wall_mm > material.max_wall_mm:
        violations.append(
            f"{label}={wall_mm:g} > material maximum "
            f"{material.max_wall_mm:g} mm for {material_id} ({material.name}) "
            "— per-material fabrication envelope (materials.yaml, ADR-027)"
        )


def taper_radius_delta_mm(height_mm: float, taper_deg: float) -> float:
    """Horizontal radius change over a height at a taper angle from vertical."""
    return height_mm * math.tan(math.radians(taper_deg))


def revolve_closed_profile(draw) -> "object":
    """Draw a closed XZ-plane profile and revolve it 360° about Z.

    ``draw()`` issues BuildLine calls (Polyline/RadiusArc). The revolved
    result is watertight BY CONSTRUCTION (Rule 6): a closed profile revolved
    about the axis it touches is always a valid closed solid.
    """
    from build123d import Axis, BuildLine, BuildSketch, Plane, make_face, revolve

    with BuildSketch(Plane.XZ) as sketch:
        with BuildLine():
            draw()
        make_face()
    return revolve(sketch.sketch, Axis.Z)
