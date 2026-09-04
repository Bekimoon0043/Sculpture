"""Layered validation gates — Phase 8 (L5 Validation Gate).

Mesh validation (`validate.py`) proves the exported GLB is one watertight
body. These gates read the trusted `assembly_manifest_v1` and produce
structural, hydraulic and fabrication reports with measured values.

Four things make this file different from a pile of if-statements:

1. FOUR statuses, never three. `needs_input` is not `warn`. "We could not
   check the hydraulics" and "we checked and they are fine" are different
   answers, and collapsing them is how a validation layer starts lying.

2. POLICY is separate from OUTCOME. `on_violation` is declared by the check
   up front; `status` is what happened. A check can be a warn-level check
   that was violated — impossible to express when severity IS the outcome.

3. Every limit names its source in `basis` (Rule 11). A threshold with no
   provenance cannot be re-read in a year and cannot be audited. Magic
   constants are structurally impossible here: the number comes from
   materials.yaml, from gate_profiles.yaml, from the Design Spec, or from
   arithmetic whose formula is written into the basis string.

4. Nothing non-finite ever reaches JSON. `json.dumps` emits bare `Infinity`,
   which is not valid JSON and breaks every strict parser downstream —
   including the export package a fabricator receives.

These are rigid-body and arithmetic checks. They are NOT finite-element
analysis, and every structural message says so.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import (
    DEFAULT_GATE_PROFILE_ID,
    GateConstants,
    GateProfile,
    Material,
    load_config_bundle,
)
from app.geometry.mass_model import assembly_mass_truth, element_mass_truth
from app.geometry.primitives.base import load_materials
from app.geometry.segmentation import (
    axes_fit_mm,
    binding_axis_mm,
    format_limit_m,
    normalize_module_limit_m,
)

#: Outcome of one check.
Status = Literal["pass", "warn", "fail", "needs_input"]

#: Worst-first. Used to roll checks up to a gate and gates up to a design.
_STATUS_RANK: dict[str, int] = {"fail": 3, "needs_input": 2, "warn": 1, "pass": 0}

STRUCTURE_GATE = "structure_static_v1"
HYDRAULICS_GATE = "hydraulics"
FABRICATION_GATE = "fabrication"


def worst_status(statuses) -> Status:
    """Roll several statuses up: fail > needs_input > warn > pass."""
    worst: Status = "pass"
    for status in statuses:
        if _STATUS_RANK[status] > _STATUS_RANK[worst]:
            worst = status  # type: ignore[assignment]
    return worst


def _finite(value: Any) -> Any:
    """Replace non-finite floats with None, recursively.

    A NaN or inf in a report is always a defect upstream, but it must never
    become invalid JSON in a persisted row or a shipped package.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    return value


class GateCheck(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    check: str
    status: Status
    #: What a violation MEANS for this check — declared up front, independent
    #: of whether it was violated.
    on_violation: Literal["warn", "fail"] = "fail"
    value: Any = None
    limit: Any = None
    units: str | None = None
    #: Provenance of `limit`. Required (Rule 11).
    basis: str
    message: str

    @property
    def passed(self) -> bool:
        """Back-compatible boolean. `needs_input` is NOT a pass."""
        return self.status == "pass"


class LayeredGateReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Renamed from `schema`: that name shadows BaseModel.schema and warns on
    # every import under pydantic 2.10. The JSON wire shape is unchanged.
    schema_id: str = Field(
        default="layered_validation_report_v2", serialization_alias="schema"
    )
    gate_name: str
    status: Status
    gate_profile_id: str
    gate_profiles_version: int
    profile_signed_off: bool
    checks: list[GateCheck]

    @property
    def passed(self) -> bool:
        """True only on a clean pass. A warn is not a pass; nor is needs_input."""
        return self.status == "pass"

    @property
    def blocking(self) -> bool:
        """True when this gate must stop acceptance."""
        return self.status == "fail"

    def check_rows(self) -> list[dict[str, object]]:
        return [
            {
                "check": c.check,
                "value": c.value,
                "limit": c.limit,
                "units": c.units,
                "status": c.status,
                "on_violation": c.on_violation,
                "basis": c.basis,
                "passed": c.passed,
                "message": c.message,
            }
            for c in self.checks
        ]

    def model_dump_wire(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# Check construction
# ---------------------------------------------------------------------------

class _Builder:
    """Accumulates checks for one gate under one profile.

    `enforced` comes from the profile's `signed_off` flag. When a profile has
    not been signed off, a breach of one of ITS thresholds reports `warn`
    instead of `fail` — the platform still shows the real number, but nothing
    is blocked on a threshold nobody approved. Material and Design Spec
    limits are always enforced; they were signed when they were entered.
    """

    def __init__(self, gate_name: str, profile_id: str, profile: GateProfile,
                 version: int) -> None:
        self.gate_name = gate_name
        self.profile_id = profile_id
        self.profile = profile
        self.version = version
        self.checks: list[GateCheck] = []

    def add(
        self,
        check: str,
        *,
        ok: bool,
        value: Any,
        limit: Any,
        basis: str,
        message: str,
        units: str | None = None,
        on_violation: Literal["warn", "fail"] = "fail",
        profile_threshold: bool = False,
    ) -> None:
        """Record a check that was actually evaluated."""
        if ok:
            status: Status = "pass"
        elif on_violation == "warn":
            status = "warn"
        elif profile_threshold and not self.profile.signed_off:
            status = "warn"
            message = (
                f"{message} — reported as a warning only: gate profile "
                f"'{self.profile_id}' is not signed off, so nothing is blocked "
                f"on this threshold. Set signed_off: true in "
                f"config/gate_profiles.yaml once it is approved."
            )
        else:
            status = "fail"
        self.checks.append(GateCheck(
            check=check, status=status, on_violation=on_violation,
            value=_finite(value), limit=_finite(limit), units=units,
            basis=basis, message=message,
        ))

    def needs_input(
        self,
        check: str,
        *,
        missing: str,
        basis: str,
        message: str,
        units: str | None = None,
    ) -> None:
        """Record a check that COULD NOT be evaluated. Never a pass, never a warn."""
        self.checks.append(GateCheck(
            check=check, status="needs_input", on_violation="fail",
            value=None, limit=None, units=units, basis=basis,
            message=f"{message} — missing: {missing}",
        ))

    def report(self) -> LayeredGateReport:
        return LayeredGateReport(
            gate_name=self.gate_name,
            status=worst_status(c.status for c in self.checks),
            gate_profile_id=self.profile_id,
            gate_profiles_version=self.version,
            profile_signed_off=self.profile.signed_off,
            checks=self.checks,
        )


def _wall_values(params: dict[str, Any]) -> list[tuple[str, float]]:
    values: list[tuple[str, float]] = []
    for name in ("wall_mm", "basin_wall_mm", "dish_wall_mm", "column_wall_mm", "floor_mm"):
        value = params.get(name)
        if isinstance(value, (int, float)) and value > 0:
            values.append((name, float(value)))
    return values


def _roots(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    elements = list(manifest.get("elements") or [])
    child_ids = {str(j.get("child")) for j in (manifest.get("joints") or [])}
    return [e for e in elements if str(e.get("element_id")) not in child_ids]


def _mass_centroid(elements: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    """Mass-weighted world centroid. Returns (x, y, z, total_mass).

    Weighted by per-element MASS, not volume — a bronze insert in a basalt
    basin moves the centre of mass and a volume average would miss it.
    """
    total = mx = my = mz = 0.0
    for e in elements:
        mass = float(e.get("mass_kg") or 0.0)
        c = e.get("centroid_mm") or {}
        total += mass
        mx += mass * float(c.get("x") or 0.0)
        my += mass * float(c.get("y") or 0.0)
        mz += mass * float(c.get("z") or 0.0)
    if total <= 0:
        return 0.0, 0.0, 0.0, 0.0
    return mx / total, my / total, mz / total, total


# ---------------------------------------------------------------------------
# Water context
# ---------------------------------------------------------------------------

class WaterContext(BaseModel):
    """Typed hydraulic inputs.

    Phase 12 (brief intake) populates this from the Design Spec. Until it
    does, a field left None makes its checks report `needs_input` naming the
    field — which is the honest answer, and the reason this is a schema and
    not a free-form dict.
    """

    model_config = ConfigDict(extra="ignore")

    #: None means "not stated". False means "this design has no water".
    has_water: bool | None = None
    flow_l_per_min: float | None = Field(default=None, ge=0)
    operating_depth_mm: float | None = Field(default=None, ge=0)
    nozzle_bore_mm: float | None = Field(default=None, gt=0)
    recirculating: bool | None = None
    drain_element_id: str | None = None

    @classmethod
    def from_any(cls, value: "WaterContext | dict[str, Any] | None") -> "WaterContext":
        if value is None:
            return cls()
        if isinstance(value, WaterContext):
            return value
        return cls.model_validate(value)


def _basin_capacity_l(params: dict[str, Any]) -> tuple[float, float, float]:
    """Return (capacity_l, inner_radius_mm, usable_depth_mm) for a basin."""
    diameter = float(params.get("diameter_mm") or 0.0)
    wall = float(params.get("wall_mm") or 0.0)
    height = float(params.get("height_mm") or 0.0)
    floor = float(params.get("floor_mm") or 0.0)
    inner_radius = max((diameter - 2 * wall) / 2.0, 0.0)
    usable_depth = max(height - floor, 0.0)
    capacity_l = math.pi * inner_radius * inner_radius * usable_depth / 1_000_000.0
    return capacity_l, inner_radius, usable_depth


# ---------------------------------------------------------------------------
# Structural gate
# ---------------------------------------------------------------------------

def validate_structural_gate(
    manifest: dict[str, Any],
    materials: dict[str, Material] | None = None,
    *,
    profile: GateProfile,
    profile_id: str,
    constants: GateConstants,
    version: int,
    stored_water_mass_kg: float = 0.0,
) -> LayeredGateReport:
    """Rigid-body static checks. NOT finite-element analysis.

    Checks the numbers Phase 6 guarantees (one fused body, positive mass, a
    single load path) and then the two that decide whether a monument is
    safe where it stands: overturning under the profile's wind case, and
    ground bearing pressure under its own weight plus stored water.
    """
    materials = materials if materials is not None else load_materials()
    b = _Builder(STRUCTURE_GATE, profile_id, profile, version)
    elements = list(manifest.get("elements") or [])
    joints = list(manifest.get("joints") or [])

    body_count = manifest.get("body_count_brep")
    b.add(
        "body_count_brep",
        ok=body_count == 1, value=body_count, limit=1, units="bodies",
        basis="assembly.py fuse invariant: one B-rep body per assembly",
        message="assembly must be one fused B-rep body",
    )

    # FF-A1 (ADR-065): every mass-dependent verdict below binds on the
    # COMPLETE total mass. When the manifest's mass truth is incomplete,
    # total/centroid/overturning/bearing all report needs_input naming the
    # missing inputs — a partial mass must never pass a stability check.
    mass_truth = assembly_mass_truth(manifest)
    if mass_truth.mass_complete:
        total_mass = float(manifest.get("total_mass_kg") or 0.0)
        b.add(
            "total_mass_kg",
            ok=total_mass > 0, value=round(total_mass, 3), limit="> 0", units="kg",
            basis="sum of per-element B-rep volume x materials.yaml density",
            message="total assembly mass is computed from per-element volumes and densities",
        )
    else:
        total_mass = 0.0
        b.needs_input(
            "total_mass_kg",
            missing="; ".join(mass_truth.missing_mass_inputs),
            basis="ADR-065 mass model: structural verdicts require the "
                  "COMPLETE assembly mass",
            message=(f"total assembly mass is INCOMPLETE — known-geometry "
                     f"mass {mass_truth.known_geometry_mass_kg:.1f} kg "
                     "excludes required inputs"),
            units="kg",
        )

    by_id = {str(e.get("element_id")): e for e in elements}
    roots = _roots(manifest)
    b.add(
        "root_count",
        ok=len(roots) == 1, value=len(roots), limit=1, units="elements",
        basis="assembly joint tree: exactly one element touches the support",
        message="load path needs one root element touching the support",
    )

    unresolved = [
        j for j in joints
        if str(j.get("parent")) not in by_id or str(j.get("child")) not in by_id
    ]
    b.add(
        "joint_load_path",
        ok=not unresolved, value=len(joints) - len(unresolved), limit=len(joints),
        units="joints",
        basis="every joint must reference elements present in the manifest",
        message="every declared joint must connect known elements",
    )

    for e in elements:
        material_id = str(e.get("material_id"))
        if materials.get(material_id) is None:
            b.add(
                f"{e.get('element_id')}.material",
                ok=False, value=material_id, limit=sorted(materials), units=None,
                basis="config/materials.yaml material ids",
                message="element material must exist in materials.yaml",
            )

    if not roots or total_mass <= 0:
        missing = "one root element and a positive total mass"
        if not mass_truth.mass_complete:
            missing = ("the complete assembly mass — "
                       + "; ".join(mass_truth.missing_mass_inputs))
        b.needs_input(
            "stability",
            missing=missing,
            basis="rigid-body statics requires a support footprint and a mass",
            message=("stability (centroid, overturning, ground bearing) "
                     "cannot be evaluated for this assembly"),
        )
        return b.report()

    # --- footprint, in WORLD coordinates ----------------------------------
    root = roots[0]
    fx_min, fy_min = float(root["bbox_min_mm"][0]), float(root["bbox_min_mm"][1])
    fx_max, fy_max = float(root["bbox_max_mm"][0]), float(root["bbox_max_mm"][1])
    base_z = float(root["bbox_min_mm"][2])
    cx, cy, cz, _ = _mass_centroid(elements)

    # Distance from the centre of mass to the NEAREST tipping edge. Negative
    # means the centre of mass is already outside the footprint.
    lever_mm = min(cx - fx_min, fx_max - cx, cy - fy_min, fy_max - cy)
    b.add(
        "center_of_mass_lever_mm",
        ok=lever_mm > 0, value=round(lever_mm, 3), limit="> 0", units="mm",
        basis="mass-weighted element centroids vs root footprint edges (world coords)",
        message=(
            "horizontal distance from the centre of mass to the nearest tipping "
            "edge; at or below zero the piece is already unstable at rest"
        ),
    )

    footprint_area_m2 = ((fx_max - fx_min) / 1000.0) * ((fy_max - fy_min) / 1000.0)
    g = constants.gravity_m_s2

    # --- ground bearing pressure ------------------------------------------
    bearing_mass = total_mass + max(stored_water_mass_kg, 0.0)
    water_note = (
        f" (includes {stored_water_mass_kg:.1f} kg stored water)"
        if stored_water_mass_kg > 0
        else " (self weight only; no water context supplied)"
    )
    if footprint_area_m2 <= 0:
        b.needs_input(
            "ground_bearing_pressure_kpa",
            missing="a root footprint with positive plan area",
            basis="pressure = m*g / A_footprint",
            message="bearing pressure cannot be evaluated",
            units="kPa",
        )
    elif profile.allowable_bearing_kpa is None:
        pressure_kpa = bearing_mass * g / footprint_area_m2 / 1000.0
        b.needs_input(
            "ground_bearing_pressure_kpa",
            missing=f"gate_profiles.yaml:{profile_id}.allowable_bearing_kpa "
                    f"(geotechnical survey for the actual site)",
            basis="pressure = m*g / A_footprint; allowable value is site-specific",
            message=(
                f"the piece applies {pressure_kpa:.1f} kPa over "
                f"{footprint_area_m2:.3f} m2{water_note}, but no allowable "
                f"bearing pressure has been supplied to compare it against"
            ),
            units="kPa",
        )
    else:
        pressure_kpa = bearing_mass * g / footprint_area_m2 / 1000.0
        b.add(
            "ground_bearing_pressure_kpa",
            ok=pressure_kpa <= profile.allowable_bearing_kpa,
            value=round(pressure_kpa, 2),
            limit=profile.allowable_bearing_kpa, units="kPa",
            basis=f"pressure = m*g / A_footprint; g from gate_profiles.yaml:"
                  f"constants.gravity_m_s2; limit from gate_profiles.yaml:"
                  f"{profile_id}.allowable_bearing_kpa",
            message=(
                f"applied ground pressure over {footprint_area_m2:.3f} m2 of "
                f"footprint{water_note}; exceeding the allowable value means the "
                f"foundation must spread the load further"
            ),
            profile_threshold=True,
        )

    # --- overturning under the profile wind case --------------------------
    _overturning_checks(
        b, manifest, profile, profile_id, constants,
        total_mass=total_mass, lever_mm=lever_mm, base_z=base_z, g=g,
    )
    return b.report()


def _overturning_checks(
    b: _Builder,
    manifest: dict[str, Any],
    profile: GateProfile,
    profile_id: str,
    constants: GateConstants,
    *,
    total_mass: float,
    lever_mm: float,
    base_z: float,
    g: float,
) -> None:
    """Rigid-body overturning: restoring moment vs wind moment."""
    if profile.design_wind_speed_m_s is None:
        b.needs_input(
            "overturning_safety_factor",
            missing=f"gate_profiles.yaml:{profile_id}.design_wind_speed_m_s "
                    f"(local wind map or the project structural engineer)",
            basis="SF = (m*g*b) / (q*Cd*A*z); q = 0.5*rho*v^2",
            message="overturning cannot be evaluated without a design wind speed",
        )
        return

    bb_min = [float(v) for v in manifest.get("assembly_bbox_min_mm") or [0, 0, 0]]
    bb_max = [float(v) for v in manifest.get("assembly_bbox_max_mm") or [0, 0, 0]]
    width_m = max(bb_max[0] - bb_min[0], bb_max[1] - bb_min[1]) / 1000.0
    height_m = (bb_max[2] - bb_min[2]) / 1000.0
    area_m2 = width_m * height_m
    # Uniform pressure on a rectangular silhouette resolves at mid-height.
    arm_m = ((bb_max[2] + bb_min[2]) / 2.0 - base_z) / 1000.0

    rho = constants.air_density_at_m(profile.site_altitude_m)
    v = float(profile.design_wind_speed_m_s)
    q_pa = 0.5 * rho * v * v
    wind_force_n = q_pa * profile.wind_drag_coefficient * area_m2
    overturning_nm = wind_force_n * max(arm_m, 0.0)
    restoring_nm = total_mass * g * (lever_mm / 1000.0)

    b.add(
        "design_wind_pressure_pa",
        ok=True, value=round(q_pa, 2), limit=None, units="Pa",
        basis=f"q = 0.5*rho*v^2; rho = {rho:.4f} kg/m3 from ISA at "
              f"{profile.site_altitude_m:g} m (gate_profiles.yaml:"
              f"{profile_id}.site_altitude_m); v from "
              f"gate_profiles.yaml:{profile_id}.design_wind_speed_m_s",
        message=(
            f"dynamic wind pressure at site altitude; sea-level air density "
            f"({constants.air_density_sea_level_kg_per_m3} kg/m3) would overstate "
            f"this by {(constants.air_density_sea_level_kg_per_m3 / rho - 1) * 100:.0f}%"
        ),
    )

    if overturning_nm <= 0:
        b.add(
            "overturning_safety_factor",
            ok=True, value="no wind case", limit=profile.overturning_safety_factor,
            units=None,
            basis=f"gate_profiles.yaml:{profile_id}.design_wind_speed_m_s = "
                  f"{v:g} m/s",
            message="this profile declares no wind load, so there is no overturning moment",
        )
        return

    safety_factor = restoring_nm / overturning_nm
    if profile.overturning_safety_factor is None:
        b.needs_input(
            "overturning_safety_factor",
            missing=f"gate_profiles.yaml:{profile_id}.overturning_safety_factor "
                    f"(a policy value your structural engineer signs)",
            basis="SF = (m*g*b) / (q*Cd*A*z)",
            message=(
                f"computed safety factor is {safety_factor:.2f} "
                f"(restoring {restoring_nm:.0f} N.m vs overturning "
                f"{overturning_nm:.0f} N.m over {area_m2:.2f} m2 of silhouette), "
                f"but no required factor has been supplied. Below 1.0 the piece tips"
            ),
        )
        return

    b.add(
        "overturning_safety_factor",
        ok=safety_factor >= profile.overturning_safety_factor,
        value=round(safety_factor, 3),
        limit=profile.overturning_safety_factor, units=None,
        basis=f"SF = (m*g*b) / (q*Cd*A*z); Cd from gate_profiles.yaml:"
              f"{profile_id}.wind_drag_coefficient; required factor from "
              f"gate_profiles.yaml:{profile_id}.overturning_safety_factor",
        message=(
            f"rigid-body overturning about the nearest footprint edge — restoring "
            f"{restoring_nm:.0f} N.m against wind {overturning_nm:.0f} N.m on "
            f"{area_m2:.2f} m2 at {arm_m:.2f} m. This is statics, not FEA: it says "
            f"whether the piece tips, not whether it cracks"
        ),
        profile_threshold=True,
    )


# ---------------------------------------------------------------------------
# Hydraulic gate
# ---------------------------------------------------------------------------

def validate_hydraulic_gate(
    manifest: dict[str, Any],
    *,
    water: WaterContext | dict[str, Any] | None = None,
    profile: GateProfile,
    profile_id: str,
    version: int,
    constants: GateConstants,
) -> LayeredGateReport:
    """Hydraulic checks derived from the Design Spec water context.

    With no water context the gate reports `needs_input` — NOT a warning.
    Nothing here is a magic range: the nozzle bore is derived from the
    declared flow and the profile's jet velocity, and every limit names the
    profile field it came from.
    """
    ctx = WaterContext.from_any(water)
    b = _Builder(HYDRAULICS_GATE, profile_id, profile, version)
    elements = list(manifest.get("elements") or [])
    basins = [e for e in elements if e.get("primitive") == "basin_round"]

    if ctx.has_water is None:
        b.needs_input(
            "water_designed",
            missing="water_context_v1.has_water (Design Spec water choreography; "
                    "populated by Phase 12 brief intake)",
            basis="hydraulic checks require a declared water design",
            message="cannot tell whether this design carries water",
        )
        return b.report()

    if not ctx.has_water:
        b.add(
            "water_designed",
            ok=True, value=False, limit=None, units=None,
            basis="water_context_v1.has_water = false",
            message="this design carries no water; hydraulic checks do not apply",
        )
        return b.report()

    b.add(
        "reservoir_basin",
        ok=bool(basins), value=len(basins), limit=">= 1", units="basins",
        basis="a water design requires at least one basin primitive to hold water",
        message="a water design needs at least one basin_round reservoir",
    )
    if not basins:
        return b.report()

    total_capacity_l = 0.0
    for basin in basins:
        eid = basin.get("element_id")
        params = basin.get("parameters") or {}
        capacity_l, inner_radius, usable_depth = _basin_capacity_l(params)
        total_capacity_l += capacity_l
        b.add(
            f"{eid}.reservoir_capacity_l",
            ok=capacity_l > 0, value=round(capacity_l, 2), limit="> 0", units="L",
            basis="pi * r_inner^2 * (height_mm - floor_mm), from the element parameters",
            message=(
                f"basin interior capacity from a {inner_radius:.0f} mm inner radius "
                f"and {usable_depth:.0f} mm of usable depth"
            ),
        )

        # --- freeboard --------------------------------------------------
        if ctx.operating_depth_mm is None:
            b.needs_input(
                f"{eid}.freeboard_mm",
                missing="water_context_v1.operating_depth_mm",
                basis=f"freeboard = usable depth - operating depth; minimum from "
                      f"gate_profiles.yaml:{profile_id}.min_freeboard_mm",
                message="splash-out margin cannot be checked without an operating depth",
                units="mm",
            )
        elif profile.min_freeboard_mm is None:
            b.needs_input(
                f"{eid}.freeboard_mm",
                missing=f"gate_profiles.yaml:{profile_id}.min_freeboard_mm",
                basis="freeboard = usable depth - operating depth",
                message="no minimum freeboard has been supplied for this profile",
                units="mm",
            )
        else:
            freeboard = usable_depth - float(ctx.operating_depth_mm)
            b.add(
                f"{eid}.freeboard_mm",
                ok=freeboard >= profile.min_freeboard_mm,
                value=round(freeboard, 2), limit=profile.min_freeboard_mm, units="mm",
                basis=f"freeboard = (height_mm - floor_mm) - "
                      f"water_context_v1.operating_depth_mm; minimum from "
                      f"gate_profiles.yaml:{profile_id}.min_freeboard_mm",
                message=(
                    "vertical margin from the design water surface to the rim; "
                    "below the minimum the basin throws water onto the surround"
                ),
                profile_threshold=True,
            )

        # --- service void for pipe runs ---------------------------------
        inserts = [
            e for e in elements
            if any(
                str(j.get("child")) == str(e.get("element_id"))
                and str(j.get("parent")) == str(eid)
                and j.get("type") == "concentric_insert"
                for j in (manifest.get("joints") or [])
            )
        ]
        for insert in inserts:
            insert_params = insert.get("parameters") or {}
            insert_radius = float(insert_params.get("diameter_mm") or 0.0) / 2.0
            void_mm = inner_radius - insert_radius
            if profile.min_service_void_mm is None:
                b.needs_input(
                    f"{insert.get('element_id')}.service_void_mm",
                    missing=f"gate_profiles.yaml:{profile_id}.min_service_void_mm",
                    basis="void = basin inner radius - insert radius",
                    message="pipe-run clearance has no minimum for this profile",
                    units="mm",
                )
                continue
            b.add(
                f"{insert.get('element_id')}.service_void_mm",
                ok=void_mm >= profile.min_service_void_mm,
                value=round(void_mm, 2), limit=profile.min_service_void_mm, units="mm",
                basis=f"void = basin inner radius - insert radius; minimum from "
                      f"gate_profiles.yaml:{profile_id}.min_service_void_mm",
                message=(
                    "clear annulus between the insert and the basin wall; pipework "
                    "and service access have to fit through it"
                ),
                profile_threshold=True,
            )

    # --- turnover -------------------------------------------------------
    if ctx.flow_l_per_min is None:
        b.needs_input(
            "reservoir_turnover_min",
            missing="water_context_v1.flow_l_per_min",
            basis="turnover = capacity_l / flow_l_per_min",
            message="reservoir turnover cannot be checked without a pump flow",
            units="min",
        )
    elif ctx.flow_l_per_min <= 0:
        b.add(
            "reservoir_turnover_min",
            ok=False, value=ctx.flow_l_per_min, limit="> 0", units="L/min",
            basis="water_context_v1.flow_l_per_min",
            message="a water design with zero flow has no circulation",
        )
    elif profile.min_reservoir_turnover_min is None:
        b.needs_input(
            "reservoir_turnover_min",
            missing=f"gate_profiles.yaml:{profile_id}.min_reservoir_turnover_min",
            basis="turnover = capacity_l / flow_l_per_min",
            message="no minimum turnover has been supplied for this profile",
            units="min",
        )
    else:
        turnover = total_capacity_l / float(ctx.flow_l_per_min)
        b.add(
            "reservoir_turnover_min",
            ok=turnover >= profile.min_reservoir_turnover_min,
            value=round(turnover, 2), limit=profile.min_reservoir_turnover_min,
            units="min",
            basis=f"turnover = total capacity {total_capacity_l:.1f} L / "
                  f"water_context_v1.flow_l_per_min; minimum from "
                  f"gate_profiles.yaml:{profile_id}.min_reservoir_turnover_min",
            message=(
                "minutes for the pump to move the whole reservoir once; too short "
                "and the basin aerates and the pump draws air"
            ),
            profile_threshold=True,
        )

    _nozzle_bore_check(b, ctx, profile, profile_id)
    return b.report()


def _nozzle_bore_check(
    b: _Builder, ctx: WaterContext, profile: GateProfile, profile_id: str
) -> None:
    """Derive the bore the declared flow needs, then compare the declared one.

    Replaces a hardcoded 3..150 mm range. The bore follows from continuity:
    Q = A*v, so d = sqrt(4Q / (pi*v)).
    """
    if ctx.nozzle_bore_mm is None:
        b.needs_input(
            "nozzle_bore_mm",
            missing="water_context_v1.nozzle_bore_mm",
            basis="d = sqrt(4Q / (pi*v))",
            message="no nozzle bore was declared to check",
            units="mm",
        )
        return
    if ctx.flow_l_per_min is None or ctx.flow_l_per_min <= 0:
        b.needs_input(
            "nozzle_bore_mm",
            missing="water_context_v1.flow_l_per_min",
            basis="d = sqrt(4Q / (pi*v))",
            message="the required bore is derived from flow, which was not supplied",
            units="mm",
        )
        return
    if profile.jet_velocity_m_s is None or profile.nozzle_bore_tolerance_pct is None:
        b.needs_input(
            "nozzle_bore_mm",
            missing=f"gate_profiles.yaml:{profile_id}.jet_velocity_m_s and "
                    f".nozzle_bore_tolerance_pct",
            basis="d = sqrt(4Q / (pi*v))",
            message="the target jet velocity for this profile has not been supplied",
            units="mm",
        )
        return

    q_m3s = float(ctx.flow_l_per_min) / 60_000.0
    v = float(profile.jet_velocity_m_s)
    required_mm = math.sqrt(4.0 * q_m3s / (math.pi * v)) * 1000.0
    tol = float(profile.nozzle_bore_tolerance_pct) / 100.0
    low, high = required_mm * (1 - tol), required_mm * (1 + tol)
    declared = float(ctx.nozzle_bore_mm)
    b.add(
        "nozzle_bore_mm",
        ok=low <= declared <= high,
        value=round(declared, 2),
        limit=[round(low, 2), round(high, 2)], units="mm",
        basis=f"d = sqrt(4Q/(pi*v)) = {required_mm:.2f} mm from "
              f"water_context_v1.flow_l_per_min and gate_profiles.yaml:"
              f"{profile_id}.jet_velocity_m_s = {v:g} m/s; band from "
              f".nozzle_bore_tolerance_pct = {profile.nozzle_bore_tolerance_pct:g}%",
        message=(
            f"the declared bore must match the bore this flow actually needs "
            f"({required_mm:.1f} mm). Too small chokes the pump; too large and the "
            f"jet collapses"
        ),
        profile_threshold=True,
    )


# ---------------------------------------------------------------------------
# Fabrication gate
# ---------------------------------------------------------------------------

def _module_limit_for_gate(
    max_module: Any,
    provenance: dict[str, Any] | None,
) -> dict[str, float] | None:
    """The per-axis limit this gate may honestly bind against, or None.

    PR-1 (ADR-059), the approved compatibility truth table: a per-axis
    {x,y,z} limit binds as written, wherever it came from. A SCALAR in a
    stored manifest binds as a cubic envelope ONLY when its provenance
    confirms a deliberate Designer/API request (spec_id NULL). A scalar
    from a collapsed Design Spec, or one whose provenance is missing,
    malformed or mismatched, returns None: the caller must report
    needs_input and request a rebuild — NEVER assume cubic.
    """
    if isinstance(max_module, dict):
        try:
            return normalize_module_limit_m(max_module, allow_scalar=False)
        except ValueError:
            return None  # malformed stored limit -> ambiguous, needs_input
    kind = (provenance or {}).get("kind")
    if kind == "cubic_request":
        try:
            return normalize_module_limit_m(max_module, allow_scalar=True)
        except ValueError:
            return None
    return None


def validate_fabrication_gate(
    manifest: dict[str, Any],
    materials: dict[str, Material] | None = None,
    *,
    profile: GateProfile,
    profile_id: str,
    version: int,
    module_limit_provenance: dict[str, Any] | None = None,
) -> LayeredGateReport:
    """Can LuxuryCon's workshop actually make, move and install this?

    Unlike the Phase 6 constraint of the same name, this gate runs on a
    manifest that may CONTAIN limit breaches — a diagnostic build (ADR-034)
    returns geometry plus the breaches, so the operator sees the piece and
    the number that disqualifies it.
    """
    materials = materials if materials is not None else load_materials()
    b = _Builder(FABRICATION_GATE, profile_id, profile, version)
    limits = manifest.get("fabrication_limits") or {}
    max_lift = limits.get("max_lift_kg")
    max_module = limits.get("max_module_m")
    joints = manifest.get("joints") or []

    for e in manifest.get("elements") or []:
        eid = str(e.get("element_id"))
        mass = float(e.get("mass_kg") or 0.0)
        dims = [float(v) for v in e.get("bbox_mm", [])]
        params = e.get("parameters") or {}
        mat = materials.get(str(e.get("material_id")))

        # --- wall floors (moved here from the structural gate) ----------
        if mat is not None:
            for name, wall in _wall_values(params):
                b.add(
                    f"{eid}.{name}",
                    ok=wall >= mat.min_wall_mm, value=wall, limit=mat.min_wall_mm,
                    units="mm",
                    basis=f"config/materials.yaml:{e.get('material_id')}.min_wall_mm",
                    message=f"{name} must meet the {e.get('material_id')} wall floor",
                )

        # --- segmentation: what the workshop actually makes (ADR-056) -----
        # Since slice C2 the lift and envelope questions are about a MODULE,
        # not an element: a 5 m basin no crane could pick ships as nine
        # pieces. `seg` is absent from manifests written before 2026-08-27,
        # and absence is treated as "one module, not measured" — never as
        # zero modules, which would read as a free design.
        seg_all = manifest.get("segmentation") or {}
        seg = (seg_all.get("elements") or {}).get(eid) or {}
        seg_modules = seg.get("modules") or []
        seg_measured = bool(seg_modules)
        module_count = len(seg_modules) if seg_measured else 1
        heaviest = (max(float(m["mass_kg"]) for m in seg_modules)
                    if seg_measured else mass)

        # --- lift mass ---------------------------------------------------
        # FF-A1 (ADR-065): a lift/crane PASS requires the COMPLETE element
        # mass. Unknown armature/allocation can never pass a pick decision
        # on known-geometry mass alone — the check reports needs_input with
        # the real known figure and the missing inputs named.
        el_truth = element_mass_truth(e)
        if max_lift is None:
            b.needs_input(
                f"{eid}.mass_kg",
                missing="Design Spec fabrication.max_lift_kg",
                basis="per-element mass vs the declared workshop lift limit",
                message="element lift mass cannot be gated without a lift limit",
                units="kg",
            )
        elif not el_truth.mass_complete:
            b.needs_input(
                f"{eid}.mass_kg",
                missing="; ".join(el_truth.missing_mass_inputs),
                basis="ADR-065 mass model: pick decisions require the "
                      "COMPLETE mass, per module",
                message=(f"lift cannot be gated: element mass is INCOMPLETE "
                         f"— heaviest module known-geometry mass "
                         f"{heaviest:.1f} kg excludes required inputs"),
                units="kg",
            )
        else:
            picked = ("the whole element" if module_count == 1
                      else f"the heaviest of {module_count} modules")
            b.add(
                f"{eid}.mass_kg",
                ok=heaviest <= float(max_lift), value=round(heaviest, 2),
                limit=float(max_lift), units="kg",
                basis=(f"Design Spec fabrication.max_lift_kg; pick weight is "
                       f"{picked} (element total {mass:.1f} kg)"),
                message="the heaviest single module must be liftable",
            )

        # --- module envelope + split feasibility -------------------------
        # PR-1 (ADR-059): each axis binds on its own limit. The reported
        # binding axis is the greatest utilization ratio extent/limit —
        # never merely the largest absolute dimension — ties x -> y -> z.
        limit_m = (None if max_module is None
                   else _module_limit_for_gate(max_module,
                                               module_limit_provenance))
        if max_module is None:
            b.needs_input(
                f"{eid}.module_bbox_mm",
                missing="Design Spec fabrication.max_module_m",
                basis="per-element bounding box vs the declared module envelope",
                message="element module size cannot be gated without a module limit",
                units="mm",
            )
        elif limit_m is None:
            # A scalar whose provenance is not a confirmed deliberate
            # cubic request: a collapsed Design Spec, or missing/
            # malformed/mismatched provenance. Gating it as cubic would
            # silently re-enforce the loosest axis — the exact defect
            # PR-1 closes — so the only honest verdict is a rebuild.
            spec_limit = (module_limit_provenance or {}).get(
                "spec_max_module_m")
            known = ""
            if isinstance(spec_limit, dict):
                known = (" — its Design Spec declares x "
                         f"{spec_limit.get('x')} / y {spec_limit.get('y')} "
                         f"/ z {spec_limit.get('z')} m")
            b.needs_input(
                f"{eid}.module_bbox_mm",
                missing=("a rebuild of this design with per-axis "
                         "fabrication.max_module_m"),
                basis=("stored limit is a single number that cannot be "
                       "confirmed as a deliberate cubic envelope "
                       f"(provenance: {(module_limit_provenance or {}).get('kind', 'unknown')})"),
                units="mm",
                message=(
                    f"this design's module limit {max_module!r} predates "
                    "per-axis enforcement and its per-axis truth was "
                    "discarded at build time; rebuild once and every axis "
                    "binds on its own number" + known
                ),
            )
        elif dims:
            limit_mm_axes = {a: limit_m[a] * 1000.0 for a in ("x", "y", "z")}
            boxes = ([m["bbox_mm"] for m in seg_modules]
                     if seg_measured else [dims])
            fits_all = all(axes_fit_mm(box, limit_mm_axes) for box in boxes)
            worst_ratio = -1.0
            worst = ("x", 0.0, limit_mm_axes["x"])
            for box in boxes:
                axis, extent, axis_limit = binding_axis_mm(box, limit_mm_axes)
                ratio = extent / axis_limit
                if ratio > worst_ratio:
                    worst_ratio = ratio
                    worst = (axis, extent, axis_limit)
            bind_axis, bind_extent, bind_limit = worst
            b.add(
                f"{eid}.module_bbox_mm",
                ok=fits_all, value=round(bind_extent, 2),
                limit=round(bind_limit, 2), units="mm",
                basis=(f"Design Spec fabrication.max_module_m "
                       f"{format_limit_m(limit_m)}, each axis vs its own "
                       f"limit; shown: binding axis {bind_axis} (greatest "
                       f"extent/limit ratio, ties x->y->z) of "
                       f"{module_count} module(s) (element bbox "
                       f"{dims[0]:.0f} x {dims[1]:.0f} x {dims[2]:.0f} mm)"),
                message="every module must fit the maximum module envelope "
                        "on every axis",
            )
            refusal = seg.get("refusal")
            if not fits_all and not seg_measured:
                # A manifest written before 2026-08-27 carries no
                # segmentation block. The honest answer is not a module
                # count computed from the bbox — that is the predicted
                # number segmentation exists to replace — it is "rebuild
                # this and I will measure it" (LIMITATIONS.md §11).
                b.needs_input(
                    f"{eid}.module_split_count",
                    missing="a rebuild of this design on the current platform",
                    basis="manifest carries no segmentation block",
                    units="modules",
                    message=(
                        f"this element is {bind_extent:.0f} mm on the "
                        f"{bind_axis} axis against a {bind_limit:.0f} mm "
                        "limit, and this manifest predates segmentation, so "
                        "how many modules it splits into has never been "
                        "measured"
                    ),
                )
            elif refusal:
                b.add(
                    f"{eid}.module_split_count",
                    ok=False, value=module_count, limit=1, units="modules",
                    basis=f"segmentation mode {seg.get('mode')!r}",
                    message=refusal,
                )
            elif module_count > 1:
                joint_count = sum(
                    1 for j in joints
                    if str(j.get("child")) == eid or str(j.get("parent")) == eid
                )
                grid = seg.get("grid") or {}
                seam_m = float(seg.get("seam_length_mm") or 0.0) / 1000.0
                b.add(
                    f"{eid}.module_split_count",
                    ok=True, value=module_count, limit=None, units="modules",
                    basis=(f"measured connected solids after an "
                           f"{grid.get('x')} x {grid.get('y')} x "
                           f"{grid.get('z')} planar cut "
                           f"(predicted cells {seg.get('predicted_cells')})"),
                    message=(
                        f"ships as {module_count} modules, heaviest "
                        f"{heaviest:.1f} kg, with {seam_m:.2f} m of seam to "
                        f"join on site; it carries {joint_count} declared "
                        f"element joint(s) as well"
                    ),
                )

        # --- tool access into internal cavities --------------------------
        bore = params.get("bore_mm")
        depth = params.get("height_mm")
        if isinstance(bore, (int, float)) and bore > 0 and isinstance(depth, (int, float)):
            aspect = float(depth) / float(bore)
            if profile.max_bore_aspect_ratio is None:
                b.needs_input(
                    f"{eid}.bore_aspect_ratio",
                    missing=f"gate_profiles.yaml:{profile_id}.max_bore_aspect_ratio",
                    basis="aspect = height_mm / bore_mm",
                    message=f"bore aspect ratio is {aspect:.1f} but has no limit set",
                )
            else:
                b.add(
                    f"{eid}.bore_aspect_ratio",
                    ok=aspect <= profile.max_bore_aspect_ratio,
                    value=round(aspect, 2), limit=profile.max_bore_aspect_ratio,
                    units=None,
                    basis=f"aspect = height_mm / bore_mm; limit from "
                          f"gate_profiles.yaml:{profile_id}.max_bore_aspect_ratio",
                    message=(
                        f"a {float(bore):.0f} mm bore {float(depth):.0f} mm deep; past "
                        f"the limit the tool cannot reach or clear chips"
                    ),
                    profile_threshold=True,
                )

    _rigging_check(b, manifest, profile, profile_id)
    return b.report()


def _rigging_check(
    b: _Builder, manifest: dict[str, Any], profile: GateProfile, profile_id: str
) -> None:
    """One gate-level rigging check, not one per element.

    Rigging is declared by the fabricator; geometry cannot derive it. But
    reporting it per element would pin the whole gate at `needs_input`
    forever and drown the checks that do discriminate. So: report it once,
    and only for the elements actually heavy enough to need it.
    """
    if profile.manual_handling_limit_kg is None:
        b.needs_input(
            "rigging_declared",
            missing=f"gate_profiles.yaml:{profile_id}.manual_handling_limit_kg",
            basis="elements above the manual handling limit require declared rigging",
            message="cannot tell which elements need rigging",
        )
        return

    heavy = [
        (str(e.get("element_id")), float(e.get("mass_kg") or 0.0))
        for e in manifest.get("elements") or []
        if float(e.get("mass_kg") or 0.0) > profile.manual_handling_limit_kg
    ]
    # FF-A1 (ADR-065): "no rigging required" is a MASS claim — it cannot
    # pass while any element's mass is incomplete (its true mass could sit
    # above the limit its known-geometry mass sits below).
    incomplete = [
        (str(e.get("element_id")), t)
        for e in manifest.get("elements") or []
        if not (t := element_mass_truth(e)).mass_complete
    ]
    if incomplete and not heavy:
        eid, t = incomplete[0]
        b.needs_input(
            "rigging_declared",
            missing="; ".join(t.missing_mass_inputs),
            basis=f"gate_profiles.yaml:{profile_id}.manual_handling_limit_kg "
                  f"= {profile.manual_handling_limit_kg:g} kg — the "
                  "no-rigging-needed claim requires COMPLETE masses (ADR-065)",
            message=(f"cannot rule rigging out: {len(incomplete)} element(s) "
                     f"(first: {eid}) carry incomplete mass"),
            units="elements",
        )
        return
    if not heavy:
        b.add(
            "rigging_declared",
            ok=True, value=0, limit=0, units="elements",
            basis=f"gate_profiles.yaml:{profile_id}.manual_handling_limit_kg = "
                  f"{profile.manual_handling_limit_kg:g} kg",
            message="no element exceeds the manual handling limit, so no rigging is required",
        )
        return

    b.needs_input(
        "rigging_declared",
        missing="Design Spec fabrication rigging data (lift point positions and "
                "rated capacity) for "
                + ", ".join(f"{eid} ({mass:.0f} kg)" for eid, mass in sorted(heavy)),
        basis=f"elements above gate_profiles.yaml:{profile_id}."
              f"manual_handling_limit_kg = {profile.manual_handling_limit_kg:g} kg "
              f"cannot be placed by hand",
        message=f"{len(heavy)} element(s) need declared lift points before installation",
        units="elements",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def stored_water_mass_kg(
    manifest: dict[str, Any],
    water: WaterContext | dict[str, Any] | None,
    constants: GateConstants,
) -> float:
    """Mass of water the basins actually hold at the declared operating depth.

    Zero when no operating depth is known — the bearing check then says so
    rather than quietly under-reporting the load.
    """
    ctx = WaterContext.from_any(water)
    if not ctx.has_water or ctx.operating_depth_mm is None:
        return 0.0
    total_l = 0.0
    for e in manifest.get("elements") or []:
        if e.get("primitive") != "basin_round":
            continue
        _, inner_radius, usable_depth = _basin_capacity_l(e.get("parameters") or {})
        depth = min(float(ctx.operating_depth_mm), usable_depth)
        total_l += math.pi * inner_radius * inner_radius * depth / 1_000_000.0
    return total_l / 1000.0 * constants.water_density_kg_per_m3


#: Profile fields intake may override per project (Phase 12). The list is
#: closed on purpose: freeboard, turnover and tool limits stay policy, but
#: SITE facts — where the piece stands — belong to the project, not the
#: profile file.
SITE_OVERRIDABLE = ("site_altitude_m", "design_wind_speed_m_s", "allowable_bearing_kpa")


def validate_layered_gates(
    manifest: dict[str, Any],
    *,
    water: WaterContext | dict[str, Any] | None = None,
    materials: dict[str, Material] | None = None,
    gate_profile_id: str | None = None,
    site_overrides: dict[str, Any] | None = None,
    module_limit_provenance: dict[str, Any] | None = None,
) -> dict[str, LayeredGateReport]:
    """Run every Phase 8 gate under one profile.

    ``site_overrides`` (Phase 12): per-project site facts from the intake,
    applied over the profile. Provenance is preserved two ways — each
    override's source rides in the ``_source`` sub-dict and is recorded as a
    ``site_overrides`` info row on the structural report, and the
    ``signed_off`` semantics are UNCHANGED: an unsigned profile still
    downgrades threshold breaches to warn, whoever supplied the number.
    """
    bundle = load_config_bundle()
    profiles = bundle.gate_profiles
    profile_id = gate_profile_id or DEFAULT_GATE_PROFILE_ID
    profile = profiles.profile(profile_id)
    constants = profiles.constants
    materials = materials if materials is not None else bundle.materials.materials

    applied_overrides: dict[str, Any] = {}
    override_sources: dict[str, str] = {}
    if site_overrides:
        sources = site_overrides.get("_source") or {}
        for field in SITE_OVERRIDABLE:
            if field in site_overrides and site_overrides[field] is not None:
                applied_overrides[field] = float(site_overrides[field])
                override_sources[field] = str(sources.get(field, "operator"))
        if applied_overrides:
            profile = profile.model_copy(update=applied_overrides)
            # An overridden altitude must still be inside the ISA model —
            # fail loudly here, not mid-gate.
            constants.air_density_at_m(profile.site_altitude_m)

    reports = {
        STRUCTURE_GATE: validate_structural_gate(
            manifest, materials, profile=profile, profile_id=profile_id,
            constants=constants, version=profiles.version,
            stored_water_mass_kg=stored_water_mass_kg(manifest, water, constants),
        ),
        HYDRAULICS_GATE: validate_hydraulic_gate(
            manifest, water=water, profile=profile, profile_id=profile_id,
            version=profiles.version, constants=constants,
        ),
        FABRICATION_GATE: validate_fabrication_gate(
            manifest, materials, profile=profile, profile_id=profile_id,
            version=profiles.version,
            module_limit_provenance=module_limit_provenance,
        ),
    }

    if applied_overrides:
        # One honest info row on the structural report: which profile fields
        # this run replaced, with the values and where each came from. A
        # report read a year later must not silently look like a plain
        # profile run.
        reports[STRUCTURE_GATE].checks.insert(0, GateCheck(
            check="site_overrides",
            status="pass",
            on_violation="warn",
            value={
                field: {"value": value, "source": override_sources.get(field)}
                for field, value in applied_overrides.items()
            },
            limit=None,
            units=None,
            basis="intake_v1 site context, applied over "
                  f"gate_profiles.yaml:{profile_id}",
            message=(
                "these profile thresholds were overridden by the project's "
                "intake site context for this run; signed_off semantics are "
                "unchanged"
            ),
        ))
    return reports
