"""The tiered-cascade primitive — one watertight solid, by construction.

Moved under primitives/ in Phase 6 slice A1 (ADR-032): the BUILDER is the
Phase 2 code unchanged (the Phase 2 canonical STEP sha256 e1a59fa6… must
keep reproducing byte-identically — the slice A1 gate asserts it), and the
parameter registry that used to live in registry.py now lives beside it, so
one module carries the whole primitive (the Phase 6 module protocol).

Classic LuxuryCon cascade: round base basin, central column (with plumbing
bore), N stacked dishes of decreasing diameter.

Construction (Rule 6 — watertight BY CONSTRUCTION, never by repair):
  * every element is a solid of revolution: a closed BuildSketch profile in
    the XZ plane revolved 360° about the Z axis;
  * the basin is a tub (outer wall + floor in one profile);
  * each dish is a shallow bowl profile whose lip fillet is drawn INTO the
    profile as a true circular arc (RadiusArc) — the revolved lip is then an
    exact toroidal surface. No fragile post-hoc 3D filleting, so the validated
    parameter ranges never hit a fillet failure (ADR-010);
  * column + dishes + basin are FUSED into one solid;
  * the plumbing bore is cut through the whole stack (a through-hole never
    splits the solid: the column keeps a full wall, enforced by hard
    constraint 4).

Coordinate system: Z up, origin at the centre of the basin's bottom face.
Dish i (0 = top/smallest) has diameter tier_top + i*step and its bottom at
basin_height + (tiers-1-i)*tier_spacing; the widest dish hangs over the basin
interior (hard constraint 1 guarantees the fit).

Hard constraints (all violations are collected and reported together):
  1. basin_diameter_mm >= widest_dish + 2*basin_wall_mm + min_clearance_mm
     where widest_dish = tier_top_diameter_mm + (tiers-1)*tier_diameter_step_mm
  2. basin_wall_mm AND column_wall_mm inside the selected material's wall
     envelope [min_wall_mm..max_wall_mm] (materials.yaml, ADR-027)
  3. lip_fillet_mm < dish_depth_mm / 2
  4. column_diameter_mm >= bore_diameter_mm + 2*column_wall_mm
     (construction safety: the column must keep a full wall around the
     plumbing bore. PER-MEMBER WALLS, slice A1: the wall here is the
     COLUMN's own, no longer the basin's — the Phase 4 live run legally
     thinned the Council's 180 mm basin wall to 60 mm to satisfy this
     constraint through the shared parameter; that resolution is now
     unnecessary. column_wall_mm defaults to basin_wall_mm, so existing
     parameter sets build bit-for-bit identical geometry.)
  5. lip_fillet_mm < basin_wall_mm
     (construction safety: the weir fillet is drawn into the dish profile;
     it must leave a real rim ledge inside the dish wall it rounds)
  6. tier_spacing_mm >= dish_depth_mm
     (design rule, defensible in numbers: the vertical gap between dishes is
     spacing - depth; overlapping dishes are a design error, not a silent
     fusion)
  7. min_clearance_mm >= the material's min_clearance_mm floor
     (materials.yaml, ADR-029 — at clearance 0 the widest dish rim is
     TANGENT to the basin inner wall, the fuse carries coincident surfaces
     and the mesh is not watertight. Constraint 1 alone cannot catch this:
     it is satisfied exactly at tangency. Proven by the live gate failure
     of 2026-08-09.)

UNIT CONVENTION: min_clearance_mm is DIAMETRAL — it is subtracted from a
diameter, so the physical radial gap is min_clearance_mm / 2.

build123d 0.11.1 API, verified against the installed package (ADR-009).
"""

from __future__ import annotations

from typing import Any

from pydantic import field_validator

from app.core.config import Material
from app.geometry.primitives.base import (
    ConstraintViolation,
    check_material,
    check_wall_envelope,
    collect_model_errors,
    load_materials,
    make_params_model,
    merge_raw,
)

PRIMITIVE_ID = "tiered_cascade"
PURPOSE = (
    "tiered cascade fountain: round basin, central column with plumbing "
    "bore, N stacked overflowing dishes — one fused watertight solid"
)
# The cascade is a complete fountain: nothing stacks on a dish rim, and its
# interior is already occupied by its own column. It composes as a CHILD
# (e.g. stacked on a plinth), never as a parent.
CAN_PARENT_STACK = False
CAN_PARENT_INSERT = False

# ---------------------------------------------------------------------------
# The registry — PHASE2_PLAN.md §3 verbatim + min_clearance_mm (SPEC_PHASE2
# §1) + column_wall_mm (slice A1 per-member walls, ADR-032)
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
    "column_wall_mm": {
        "unit": "mm",
        "default": None,
        "min": 3,
        "max": 300,
        "type": "float",
        "optional": True,
        "notes": "the COLUMN's own wall around the plumbing bore (hard "
        "constraint 4). Omit to use basin_wall_mm — per-member walls, "
        "slice A1: the column no longer forces the basin wall thinner "
        "(closes LIMITATIONS §9 first bullet). Same material envelope "
        "as basin_wall_mm.",
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

# Phase 6 primitive protocol compatibility: every primitive module exposes
# PARAMETERS. Keep CASCADE_PARAMETERS as the long-standing public name for the
# cascade-specific API, but make registry-wide code safe.
PARAMETERS = CASCADE_PARAMETERS


_CascadeParamsBase = make_params_model("_CascadeParamsBase", CASCADE_PARAMETERS)


class CascadeParams(_CascadeParamsBase):  # type: ignore[misc]
    """A fully validated cascade parameter set (ranges only — cross-parameter
    hard constraints live in validate_params, which returns this model, and
    which also resolves column_wall_mm's derived default — a CascadeParams
    from validate_params never carries None)."""

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


def validate_params(
    raw: dict[str, Any],
    materials: dict[str, Material] | None = None,
) -> CascadeParams:
    """Validate a raw parameter dict against ranges + hard constraints.

    Missing keys fall back to registry defaults (column_wall_mm's default is
    DERIVED: basin_wall_mm). Unknown keys, range breaches, unknown materials
    and every hard-constraint breach are collected into ONE
    ConstraintViolation whose messages carry the real numbers.
    """
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []

    merged = merge_raw(PRIMITIVE_ID, CASCADE_PARAMETERS, raw, violations)

    try:
        params = CascadeParams.model_validate(merged)
    except Exception as exc:  # pydantic ValidationError — reformat each error
        collect_model_errors(exc, violations)
        raise ConstraintViolation(violations) from exc

    # Derived default (slice A1, per-member walls): with column_wall_mm
    # omitted the parameter set is EXACTLY the Phase 2/4 one — geometry
    # depends on it only through constraint 4, and the resolved value equals
    # what constraint 4 used before, so existing builds are bit-identical.
    if params.column_wall_mm is None:
        params = params.model_copy(update={"column_wall_mm": params.basin_wall_mm})

    # --- hard constraint 1: basin must swallow the widest dish + clearance --
    widest = params.widest_dish_diameter_mm()
    required = params.required_basin_diameter_mm()
    if params.basin_diameter_mm < required:
        violations.append(
            f"basin_diameter_mm={params.basin_diameter_mm:g} < required "
            f"{required:g} (= widest dish {widest:g} + 2*wall "
            f"2x{params.basin_wall_mm:g} + clearance {params.min_clearance_mm:g})"
        )

    # --- hard constraint 2: walls inside the material's envelope ------------
    material = check_material(PRIMITIVE_ID, params.material_id, materials, violations)
    if material is not None:
        check_wall_envelope(
            "basin_wall_mm", params.basin_wall_mm, params.material_id,
            material, violations,
        )
        # Per-member walls (A1): the column wall is fabricated in the same
        # material, so the same envelope applies to it.
        check_wall_envelope(
            "column_wall_mm", params.column_wall_mm, params.material_id,
            material, violations,
        )

    # --- hard constraint 3: lip fillet must fit the dish depth ---------------
    half_depth = params.dish_depth_mm / 2
    if params.lip_fillet_mm >= half_depth:
        violations.append(
            f"lip_fillet_mm={params.lip_fillet_mm:g} must be < dish_depth_mm/2 "
            f"= {params.dish_depth_mm:g}/2 = {half_depth:g}"
        )

    # --- hard constraint 4: column keeps a full wall around the bore --------
    min_column = params.bore_diameter_mm + 2 * params.column_wall_mm
    if params.column_diameter_mm < min_column:
        violations.append(
            f"column_diameter_mm={params.column_diameter_mm:g} < required "
            f"{min_column:g} (= bore {params.bore_diameter_mm:g} + 2*column "
            f"wall 2x{params.column_wall_mm:g}) — the column must keep a "
            "full wall around the plumbing bore (per-member walls, A1: set "
            "column_wall_mm independently instead of thinning basin_wall_mm)"
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


# alias for the Phase 6 module protocol (registry.assemble calls validate())
validate = validate_params


# ---------------------------------------------------------------------------
# Builder — Phase 2 code, geometry UNCHANGED (canonical STEP hash e1a59fa6…)
# ---------------------------------------------------------------------------


def _revolve_profile(z0: float, draw):
    """Draw a closed XZ-plane profile (local z offset by z0) and revolve it."""
    from build123d import Axis, BuildLine, BuildSketch, Plane, make_face, revolve

    with BuildSketch(Plane.XZ) as sketch:
        with BuildLine():
            draw(z0)
        make_face()
    return revolve(sketch.sketch, Axis.Z)


def _basin(p: CascadeParams):
    """Tub: outer cylinder wall + floor, one closed profile."""
    from build123d import Polyline

    R = p.basin_diameter_mm / 2
    H = p.basin_height_mm
    t = p.basin_wall_mm

    def draw(z0: float) -> None:
        Polyline(
            (0, z0),
            (R, z0),
            (R, z0 + H),
            (R - t, z0 + H),
            (R - t, z0 + t),
            (0, z0 + t),
            close=True,
        )

    return _revolve_profile(0.0, draw)


def _dish(p: CascadeParams, index: int):
    """Bowl i: shallow dish with the weir-lip fillet drawn into the profile."""
    from build123d import Polyline, RadiusArc

    diameter = p.tier_top_diameter_mm + index * p.tier_diameter_step_mm
    r = diameter / 2
    D = p.dish_depth_mm
    t = p.basin_wall_mm
    f = p.lip_fillet_mm
    # top dish (index 0) is highest; bottom of dish i:
    z0 = p.basin_height_mm + (p.tiers - 1 - index) * p.tier_spacing_mm

    def draw(base: float) -> None:
        Polyline(
            (0, base),
            (r, base),
            (r, base + D - f),          # outer wall up to the fillet tangent
        )
        # Lip fillet: true circular arc, tangent to outer wall and rim ledge.
        RadiusArc((r, base + D - f), (r - f, base + D), f)
        Polyline(
            (r - f, base + D),
            (r - t, base + D),          # rim ledge (f < t, constraint 5)
            (r - t, base + t),          # inner wall down
            (0, base + t),              # bowl floor
            (0, base),                  # close the profile at the axis
        )

    return _revolve_profile(z0, draw)


def _column(p: CascadeParams):
    """Central column, fused into the basin floor and the top dish."""
    from build123d import Cylinder, Pos

    z_top = (
        p.basin_height_mm
        + (p.tiers - 1) * p.tier_spacing_mm
        + p.basin_wall_mm               # flush with the top dish's inner floor
    )
    return Pos(0, 0, z_top / 2) * Cylinder(p.column_diameter_mm / 2, z_top)


def _bore(p: CascadeParams):
    """Plumbing service void through the entire stack (overshot both ends)."""
    from build123d import Cylinder, Pos

    z_top = (
        p.basin_height_mm
        + (p.tiers - 1) * p.tier_spacing_mm
        + p.dish_depth_mm
    )
    height = z_top + 2.0                # 1 mm overshot top and bottom
    return Pos(0, 0, z_top / 2) * Cylinder(p.bore_diameter_mm / 2, height)


def build_cascade(params: CascadeParams):
    """Build the full cascade as ONE watertight solid.

    Raises RuntimeError if the fused result is not exactly one solid — a
    construction defect must never ship silently (Rule 6).
    """
    result = _basin(params)
    result += _column(params)
    for i in range(params.tiers):
        result += _dish(params, i)
    result -= _bore(params)

    solids = result.solids()
    if len(solids) != 1:
        raise RuntimeError(
            f"cascade construction produced {len(solids)} solids, expected 1 — "
            "parameters validated but geometry is not one fused body"
        )
    return solids[0]


# Phase 6 module protocol name
build = build_cascade


def height_mm(p: CascadeParams) -> float:
    """Overall height: basin + tier stack + top dish depth."""
    return (
        p.basin_height_mm
        + (p.tiers - 1) * p.tier_spacing_mm
        + p.dish_depth_mm
    )


def anchors(p: CascadeParams) -> dict[str, float | None]:
    """base = origin plane; top = top dish rim; seat = None (the cascade's
    interior is occupied by its own column — nothing inserts into it)."""
    return {"base": 0.0, "top": height_mm(p), "seat": None}


def max_outer_diameter_mm(p: CascadeParams) -> float:
    return p.basin_diameter_mm


def inner_diameter_mm(p: CascadeParams) -> float | None:
    return None
