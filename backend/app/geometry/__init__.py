"""Geometry kernel for LuxuryForm Studio — Phase 2.

Public API:
    GeometryBuild      — build context (seed + params -> solid + spec_hash)
    CASCADE_PARAMETERS — the tiered-cascade parameter registry
    CascadeParams      — validated parameter model (pydantic)
    ConstraintViolation— raised with ALL hard-constraint violations listed
    validate_params    — dict -> CascadeParams (hard constraints, real numbers)
    build_cascade      — CascadeParams -> one watertight build123d solid
    export_step        — solid + path + deterministic timestamp -> sha256
    export_glb         — solid + path -> sha256 (native binary glTF)
    validate_mesh      — GLB + material -> ValidationReport (trimesh numbers)
    ValidationReport   — the persisted validation result model

The registry (parameters + hard constraints) is importable WITHOUT the
geometry stack installed; kernel/cascade/exporters/validate are loaded
lazily on first access (PEP 562) and do require build123d / trimesh.
"""

from typing import TYPE_CHECKING

from app.geometry.registry import (
    CASCADE_PARAMETERS,
    CascadeParams,
    ConstraintViolation,
    validate_params,
)

if TYPE_CHECKING:  # static view only; runtime loads lazily via __getattr__
    from app.geometry.cascade import build_cascade
    from app.geometry.exporters import export_glb, export_step
    from app.geometry.kernel import GeometryBuild
    from app.geometry.validate import ValidationReport, validate_mesh

_LAZY = {
    "GeometryBuild": "app.geometry.kernel",
    "build_cascade": "app.geometry.cascade",
    "export_step": "app.geometry.exporters",
    "export_glb": "app.geometry.exporters",
    "validate_mesh": "app.geometry.validate",
    "ValidationReport": "app.geometry.validate",
}

__all__ = [
    "GeometryBuild",
    "CASCADE_PARAMETERS",
    "CascadeParams",
    "ConstraintViolation",
    "validate_params",
    "build_cascade",
    "export_step",
    "export_glb",
    "validate_mesh",
    "ValidationReport",
]


def __getattr__(name: str):
    module_path = _LAZY.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache
    return value
