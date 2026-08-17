"""Cascade parameter registry + hard-constraint validation [ADD-4].

Single source of truth for the tiered-cascade parameter set (PHASE2_PLAN.md
§3 table, 12 parameters, plus min_clearance_mm as the 13th per SPEC_PHASE2
§1). Every parameter carries unit, default, min, max and type; the frontend
renders its input panel straight from CASCADE_PARAMETERS, and validate_params
enforces both the per-parameter ranges and the cross-parameter HARD
CONSTRAINTS below — every violation message carries the REAL computed
numbers, never a bare "invalid".

Hard constraints (all violations are collected and reported together):
  1. basin_diameter_mm >= widest_dish + 2*basin_wall_mm + min_clearance_mm
     where widest_dish = tier_top_diameter_mm + (tiers-1)*tier_diameter_step_mm
  2. basin_wall_mm inside the selected material's wall envelope
     [min_wall_mm..max_wall_mm] (materials.yaml, ADR-027)
  3. lip_fillet_mm < dish_depth_mm / 2
  4. column_diameter_mm >= bore_diameter_mm + 2*basin_wall_mm
     (construction safety: the column must keep a full wall around the
     plumbing bore, otherwise the fused solid loses its core — Rule 6,
     watertight by construction)
  5. lip_fillet_mm < basin_wall_mm
     (construction safety: the weir fillet is drawn into the dish profile;
     it must leave a real rim ledge inside the dish wall it rounds)
  6. tier_spacing_mm >= dish_depth_mm
     (design rule, defensible in numbers: the vertical gap between dishes is
     spacing - depth; overlapping dishes are a design error, not a silent
     fusion)
  7. min_clearance_mm >= the material's min_clearance_mm floor
     (materials.yaml, ADR-029 — construction safety, the same class as 4:
     at clearance 0 the widest dish rim is TANGENT to the basin inner wall,
     the fuse carries coincident surfaces and the mesh is not watertight.
     Constraint 1 alone cannot catch this: it is satisfied exactly at
     tangency. Proven by the live gate failure of 2026-08-09.)

UNIT CONVENTION: min_clearance_mm is DIAMETRAL — it is subtracted from a
diameter in constraint 1, so the physical radial gap between the dish rim
and the basin wall is min_clearance_mm / 2.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, create_model, field_validator

from app.core.config import Material, load_config_bundle

# ---------------------------------------------------------------------------
# The registry — PHASE2_PLAN.md §3 verbatim + min_clearance_mm (SPEC_PHASE2 §1)
# ---------------------------------------------------------------------------

CASCADE_PARAMETERS: dict[str, dict[str, Any]] = {
    "tiers": {
        "unit": "count",
        "default": 3,
        "min": 1,
        "max": 5,
        "type": "int",
        "notes": "dish count",
    },
    "tier_top_diameter_mm": {
        "unit": "mm",
        "default": 600,
        "min": 200,
        "max": 2000,
        "type": "float",
        "notes": "smallest (top) dish diameter",
    },
    "tier_diameter_step_mm": {
        "unit": "mm",
        "default": 400,
        "min": 100,
        "max": 1000,
        "type": "float",
        "notes": "each lower dish grows by this",
    },
    "dish_depth_mm": {
        "unit": "mm",
        "default": 90,
        "min": 40,
        "max": 600,
        "type": "float",
        "notes": "dish bowl outer depth (ADR-027: ceiling 600 for "
        "monumental stonework; hard constraint 6 keeps spacing >= depth)",
    },
    "tier_spacing_mm": {
        "unit": "mm",
        "default": 350,
        "min": 150,
        "max": 900,
        "type": "float",
        "notes": "vertical gap between dishes",
    },
    "lip_fillet_mm": {
        "unit": "mm",
        "default": 8,
        "min": 2,
        "max": 30,
        "type": "float",
        "notes": "weir edge fillet radius",
    },
    "column_diameter_mm": {
        "unit": "mm",
        "default": 200,
        "min": 80,
        "max": 600,
        "type": "float",
        "notes": "central column diameter",
    },
    "basin_diameter_mm": {
        "unit": "mm",
        "default": 2600,
        "min": 400,
        "max": 6000,
        "type": "float",
        "notes": "must exceed widest dish + walls + clearance (hard constraint 1)",
    },
    "basin_height_mm": {
        "unit": "mm",
        "default": 450,
        "min": 200,
        "max": 900,
        "type": "float",
        "notes": "basin outer height",
    },
    "basin_wall_mm": {
        "unit": "mm",
        "default": 20,
        "min": 3,
        "max": 300,
        "type": "float",
        "notes": "basin/dish wall; must sit inside the material's wall "
        "envelope [min_wall_mm..max_wall_mm] (hard constraint 2, ADR-027)",
    },
    "bore_diameter_mm": {
        "unit": "mm",
        "default": 50,
        "min": 25,
        "max": 150,
        "type": "float",
        "notes": "plumbing service void (Amendment-3-ready)",
    },
    "material_id": {
        "unit": "materials.yaml key",
        "default": "basalt_slab",
        "min": None,
        "max": None,
        "type": "str",
        "notes": "drives mass calc + min-wall constraint",
    },
    "min_clearance_mm": {
        "unit": "mm",
        "default": 100,
        # ADR-029: the static floor is the SMALLEST per-material floor in
        # materials.yaml (the union, exactly as ADR-027 did for walls); hard
        # constraint 7 then narrows it to the SELECTED material. 0 is gone:
        # it puts the dish rim tangent to the basin wall and the fused solid
        # is not watertight (live gate failure 2026-08-09).
        "min": 20,
        "max": 1000,
        "type": "float",
        "notes": (
            "free water/fall gap between widest dish and basin wall — "
            "DIAMETRAL, so the physical radial gap is half this number; "
            "per-material floor applies (constraint 7)"
        ),
    },
}


class ConstraintViolation(ValueError):
    """Raised by validate_params with EVERY violated rule listed.

    Each entry in ``violations`` is a plain-language sentence carrying the
    real computed numbers (ADD-4) — the operator can act on it directly.
    """

    def __init__(self, violations: list[str]) -> None:
        if not violations:
            raise ValueError("ConstraintViolation needs at least one violation")
        self.violations = list(violations)
        super().__init__("; ".join(self.violations))


# ---------------------------------------------------------------------------
# CascadeParams — pydantic model generated FROM the registry (no duplicated
# bounds to drift out of sync; a test asserts the mapping).
# ---------------------------------------------------------------------------

def _model_fields() -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for name, spec in CASCADE_PARAMETERS.items():
        py_type: Any = {"int": int, "float": float, "str": str}[spec["type"]]
        if py_type is str:
            fields[name] = (py_type, Field(default=spec["default"]))
        else:
            fields[name] = (
                py_type,
                Field(default=spec["default"], ge=spec["min"], le=spec["max"]),
            )
    return fields


_CascadeParamsBase = create_model("_CascadeParamsBase", **_model_fields())


class CascadeParams(_CascadeParamsBase):  # type: ignore[misc]
    """A fully validated cascade parameter set (ranges only — cross-parameter
    hard constraints live in validate_params, which returns this model)."""

    @field_validator("tiers", mode="before")
    @classmethod
    def _tiers_is_int(cls, value: Any) -> Any:
        # pydantic would coerce 3.5 -> 3 silently in lax mode; forbid that.
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"tiers must be a whole number, got {value!r}")
        return value

    def widest_dish_diameter_mm(self) -> float:
        """Diameter of the lowest (widest) dish."""
        return self.tier_top_diameter_mm + (self.tiers - 1) * self.tier_diameter_step_mm

    def required_basin_diameter_mm(self) -> float:
        """Minimum basin diameter from hard constraint 1."""
        return (
            self.widest_dish_diameter_mm()
            + 2 * self.basin_wall_mm
            + self.min_clearance_mm
        )

    def canonical_dict(self) -> dict[str, Any]:
        """Parameters as a plain dict, sorted-key ready for canonical JSON."""
        return dict(self.model_dump())


def _materials() -> dict[str, Material]:
    return load_config_bundle().materials.materials


def validate_params(
    raw: dict[str, Any],
    materials: dict[str, Material] | None = None,
) -> CascadeParams:
    """Validate a raw parameter dict against ranges + hard constraints.

    Missing keys fall back to registry defaults. Unknown keys, range
    breaches, unknown materials and every hard-constraint breach are
    collected into ONE ConstraintViolation whose messages carry the real
    numbers.
    """
    materials = materials if materials is not None else _materials()
    violations: list[str] = []

    unknown = sorted(set(raw) - set(CASCADE_PARAMETERS))
    for name in unknown:
        violations.append(
            f"unknown parameter {name!r}; known parameters: "
            + ", ".join(sorted(CASCADE_PARAMETERS))
        )

    merged = {name: spec["default"] for name, spec in CASCADE_PARAMETERS.items()}
    merged.update({k: v for k, v in raw.items() if k in CASCADE_PARAMETERS})

    try:
        params = CascadeParams.model_validate(merged)
    except Exception as exc:  # pydantic ValidationError — reformat each error
        for err in exc.errors():  # type: ignore[attr-defined]
            loc = ".".join(str(p) for p in err.get("loc", ())) or "?"
            msg = err.get("msg", "invalid")
            given = err.get("input", "?")
            violations.append(f"{loc}={given!r}: {msg}")
        raise ConstraintViolation(violations) from exc

    # --- hard constraint 1: basin must swallow the widest dish + clearance --
    widest = params.widest_dish_diameter_mm()
    required = params.required_basin_diameter_mm()
    if params.basin_diameter_mm < required:
        violations.append(
            f"basin_diameter_mm={params.basin_diameter_mm:g} < required "
            f"{required:g} (= widest dish {widest:g} + 2*wall "
            f"2x{params.basin_wall_mm:g} + clearance {params.min_clearance_mm:g})"
        )

    # --- hard constraint 2: wall inside the material's envelope ------------
    material = materials.get(params.material_id)
    if material is None:
        violations.append(
            f"material_id={params.material_id!r} not in materials.yaml "
            f"(available: {', '.join(sorted(materials))})"
        )
    elif params.basin_wall_mm < material.min_wall_mm:
        violations.append(
            f"basin_wall_mm={params.basin_wall_mm:g} < material minimum "
            f"{material.min_wall_mm:g} mm for {params.material_id} "
            f"({material.name})"
        )
    elif params.basin_wall_mm > material.max_wall_mm:
        violations.append(
            f"basin_wall_mm={params.basin_wall_mm:g} > material maximum "
            f"{material.max_wall_mm:g} mm for {params.material_id} "
            f"({material.name}) — per-material fabrication envelope "
            "(materials.yaml, ADR-027)"
        )

    # --- hard constraint 3: lip fillet must fit the dish depth ---------------
    half_depth = params.dish_depth_mm / 2
    if params.lip_fillet_mm >= half_depth:
        violations.append(
            f"lip_fillet_mm={params.lip_fillet_mm:g} must be < dish_depth_mm/2 "
            f"= {params.dish_depth_mm:g}/2 = {half_depth:g}"
        )

    # --- hard constraint 4: column keeps a full wall around the bore --------
    min_column = params.bore_diameter_mm + 2 * params.basin_wall_mm
    if params.column_diameter_mm < min_column:
        violations.append(
            f"column_diameter_mm={params.column_diameter_mm:g} < required "
            f"{min_column:g} (= bore {params.bore_diameter_mm:g} + 2*wall "
            f"2x{params.basin_wall_mm:g}) — the column must keep a full wall "
            "around the plumbing bore"
        )

    # --- hard constraint 5: lip fillet fits inside the dish wall ------------
    if params.lip_fillet_mm >= params.basin_wall_mm:
        violations.append(
            f"lip_fillet_mm={params.lip_fillet_mm:g} must be < basin_wall_mm="
            f"{params.basin_wall_mm:g} — the weir fillet must leave a real "
            "rim ledge inside the dish wall it rounds"
        )

    # --- hard constraint 6: dishes must not overlap --------------------------
    if params.tier_spacing_mm < params.dish_depth_mm:
        violations.append(
            f"tier_spacing_mm={params.tier_spacing_mm:g} < dish_depth_mm="
            f"{params.dish_depth_mm:g} — dishes would overlap "
            f"(vertical gap = {params.tier_spacing_mm - params.dish_depth_mm:g} mm)"
        )

    # --- hard constraint 7: fall gap inside the material's floor -----------
    # Constraint 1 is satisfied EXACTLY at tangency (basin == required), so
    # it cannot catch a zero gap on its own — this one does (ADR-029).
    if material is not None and params.min_clearance_mm < material.min_clearance_mm:
        violations.append(
            f"min_clearance_mm={params.min_clearance_mm:g} < material "
            f"minimum {material.min_clearance_mm:g} mm for "
            f"{params.material_id} ({material.name}) — the fall gap between "
            f"the widest dish and the basin wall would be "
            f"{params.min_clearance_mm / 2:g} mm radial, below the "
            f"{material.min_clearance_mm / 2:g} mm this material is built "
            "to (materials.yaml, ADR-029). At zero the dish rim is tangent "
            "to the basin wall and the fused solid is NOT watertight."
        )

    if violations:
        raise ConstraintViolation(violations)
    return params


# ---------------------------------------------------------------------------
# Phase 4 fabrication primitive — the ONLY geometry call a generated program
# may make. Kept in registry.py so the sandbox-visible `registry` module is
# the single vocabulary source; Phase 6 adds more primitives HERE.
#
# SECURITY NOTE for future editors: everything importable from this module
# is reachable by AI-written code executing in the sandbox. Keep this
# module's public surface benign — no file, network, or process access.
# ---------------------------------------------------------------------------


def cascade_fountain(params: dict[str, Any], seed: int = 0):
    """THE Phase 4 primitive: dict of cascade parameters -> watertight solid.

    Validates ``params`` against the registry (ranges + hard constraints,
    real numbers in every violation) and builds the fused cascade solid.
    Returns ``(solid, validated_params)`` where ``solid`` is a build123d
    Shape and ``validated_params`` is the validated CascadeParams model —
    the runner persists ``validated_params.canonical_dict()`` for lineage.

    Raises ConstraintViolation listing EVERY violated constraint with the
    real computed numbers.
    """
    from app.geometry.kernel import GeometryBuild  # lazy: registry stays
    # importable without the geometry stack installed

    validated = validate_params(params)
    return GeometryBuild(seed, validated).build(), validated
