"""Brief intake — L1 typed contexts (Phase 12).

Every field is wrapped with its PROVENANCE:

    operator  the operator typed or confirmed it
    parsed    the AI parser extracted it from the brief (with the quote)
    default   nobody chose it; it is the shipped default
    unknown   nobody knows it — and that is recorded, not papered over

The wrapper is the honesty mechanism end to end: a defaulted freeze risk
that nobody checked is not the same as a confirmed one, and `unknown`
propagates to the Phase 8 gates as `needs_input` instead of quietly becoming
a number. Free-form dicts are what made the hydraulic gate inert for a
whole phase; typed contexts with explicit units (Rule 6) are the fix, and
intake is where they are born.
"""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

Source = Literal["operator", "parsed", "default", "unknown"]

T = TypeVar("T")


class Sourced(BaseModel, Generic[T]):
    """One value plus where it came from.

    `quote` is the brief sentence the parser extracted from — shown in the
    UI so the operator can check the parser's work against the client's own
    words instead of trusting it.
    """

    value: T | None = None
    source: Source = "unknown"
    quote: str | None = None

    @classmethod
    def unknown(cls) -> "Sourced[T]":
        return cls(value=None, source="unknown")

    @classmethod
    def default(cls, value: T) -> "Sourced[T]":
        return cls(value=value, source="default")

    def known(self) -> bool:
        return self.source != "unknown" and self.value is not None


class ProjectSection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    project_type: Sourced[str] = Field(default_factory=Sourced.unknown)
    name: Sourced[str] = Field(default_factory=Sourced.unknown)
    setting: Sourced[str] = Field(default_factory=Sourced.unknown)  # public | private


class SiteSection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    city: Sourced[str] = Field(default_factory=Sourced.unknown)
    country: Sourced[str] = Field(default_factory=Sourced.unknown)
    indoor: Sourced[bool] = Field(default_factory=Sourced.unknown)
    altitude_m: Sourced[float] = Field(default_factory=Sourced.unknown)
    #: 3-second gust at the piece's height. The operator supplies it from
    #: the local wind map or the project engineer — intake is the honest
    #: channel for it, per-project, instead of editing gate_profiles.yaml.
    design_wind_speed_m_s: Sourced[float] = Field(default_factory=Sourced.unknown)
    allowable_bearing_kpa: Sourced[float] = Field(default_factory=Sourced.unknown)
    freeze_risk: Sourced[bool] = Field(default_factory=Sourced.unknown)
    dust_exposure: Sourced[str] = Field(default_factory=Sourced.unknown)
    water_available: Sourced[bool] = Field(default_factory=Sourced.unknown)
    access_notes: Sourced[str] = Field(default_factory=Sourced.unknown)


class DimensionsSection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    height_m: Sourced[float] = Field(default_factory=Sourced.unknown)
    footprint_m: Sourced[float] = Field(default_factory=Sourced.unknown)


class WaterSection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    has_water: Sourced[bool] = Field(default_factory=Sourced.unknown)
    flow_l_per_min: Sourced[float] = Field(default_factory=Sourced.unknown)
    operating_depth_mm: Sourced[float] = Field(default_factory=Sourced.unknown)
    nozzle_bore_mm: Sourced[float] = Field(default_factory=Sourced.unknown)
    recirculating: Sourced[bool] = Field(default_factory=Sourced.unknown)
    behavior: Sourced[str] = Field(default_factory=Sourced.unknown)  # jet | cascade | still...


class MaterialsSection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    preferred: Sourced[list[str]] = Field(default_factory=Sourced.unknown)
    forbidden: Sourced[list[str]] = Field(default_factory=Sourced.unknown)


class CultureSection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    inspiration: Sourced[str] = Field(default_factory=Sourced.unknown)
    motifs: Sourced[str] = Field(default_factory=Sourced.unknown)
    forbidden_motifs: Sourced[str] = Field(default_factory=Sourced.unknown)
    brand_tone: Sourced[str] = Field(default_factory=Sourced.unknown)


class BudgetSection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    currency: Sourced[str] = Field(default_factory=Sourced.unknown)
    amount_min: Sourced[float] = Field(default_factory=Sourced.unknown)
    amount_max: Sourced[float] = Field(default_factory=Sourced.unknown)
    contingency_pct: Sourced[float] = Field(default_factory=Sourced.unknown)
    deadline: Sourced[str] = Field(default_factory=Sourced.unknown)


class IntakeV1(BaseModel):
    """The whole normalized intake. schema field kept off pydantic's name."""

    model_config = ConfigDict(populate_by_name=True)

    schema_id: str = Field(default="intake_v1", serialization_alias="schema")
    project: ProjectSection = Field(default_factory=ProjectSection)
    site: SiteSection = Field(default_factory=SiteSection)
    dimensions: DimensionsSection = Field(default_factory=DimensionsSection)
    water: WaterSection = Field(default_factory=WaterSection)
    materials: MaterialsSection = Field(default_factory=MaterialsSection)
    culture: CultureSection = Field(default_factory=CultureSection)
    budget: BudgetSection = Field(default_factory=BudgetSection)

    def dump_wire(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# Requirement tiers (plan R5) — ranked by what a gap BLOCKS
# ---------------------------------------------------------------------------

#: tier -> [(section, field, why it matters)]. Tiers 1 and 2 must be known
#: before Council spend; 3 and 4 may proceed as `unknown` with the
#: downstream consequence stated.
REQUIREMENT_TIERS: dict[int, list[tuple[str, str, str]]] = {
    1: [  # blocks geometry
        ("project", "project_type", "the Council cannot design without knowing what this is"),
        ("dimensions", "height_m", "massing needs an overall height"),
        ("dimensions", "footprint_m", "massing needs a footprint"),
    ],
    2: [  # blocks a validation gate
        ("site", "indoor", "indoor/outdoor decides the wind load case"),
        ("water", "has_water", "hydraulic validation reports needs_input without it"),
        ("site", "design_wind_speed_m_s", "overturning cannot be evaluated without it (outdoor)"),
    ],
    3: [  # blocks costing
        ("budget", "currency", "costing reports in an unstated currency otherwise"),
        ("budget", "amount_max", "the budget check cannot bind without a ceiling"),
    ],
    4: [  # affects design quality only
        ("culture", "inspiration", "the Council designs generically without it"),
        ("materials", "preferred", "material choice falls back to the library default"),
    ],
}

TIER_LABELS = {
    1: "blocks geometry",
    2: "blocks a validation gate",
    3: "blocks costing",
    4: "affects design quality",
}


def _field(intake: IntakeV1, section: str, name: str) -> Sourced[Any]:
    return getattr(getattr(intake, section), name)


def readiness(intake: IntakeV1) -> dict[str, Any]:
    """Which required fields are still unknown, ranked by consequence.

    A field only counts against readiness when it APPLIES: wind speed is
    tier-2 for an outdoor piece and irrelevant indoors; water details only
    matter once has_water is true.
    """
    missing: dict[str, list[dict[str, str]]] = {}
    for tier, fields in REQUIREMENT_TIERS.items():
        rows: list[dict[str, str]] = []
        for section, name, why in fields:
            f = _field(intake, section, name)
            if f.known():
                continue
            # Applicability rules — asking for irrelevant data is noise.
            if (section, name) == ("site", "design_wind_speed_m_s"):
                indoor = intake.site.indoor
                if indoor.known() and indoor.value is True:
                    continue  # sheltered: no wind case to feed
            rows.append({"field": f"{section}.{name}", "why": why})
        if rows:
            missing[str(tier)] = rows
    blocked = any(t in missing for t in ("1", "2"))
    return {
        "ready_for_council": not blocked,
        "missing_by_tier": missing,
        "tier_labels": {str(k): v for k, v in TIER_LABELS.items()},
        "note": (
            "tiers 1 and 2 must be answered before paid Council calls; "
            "tiers 3 and 4 may stay unknown, and the affected layer will "
            "report it honestly"
        ),
    }


# ---------------------------------------------------------------------------
# Converters — intake feeds the rest of the platform
# ---------------------------------------------------------------------------

def to_water_context(intake: IntakeV1) -> dict[str, Any]:
    """The exact water_context_v1 shape the Phase 8 hydraulic gate consumes.

    `unknown` maps to None so the gate reports needs_input — never a guess.
    """
    w = intake.water
    return {
        "has_water": w.has_water.value if w.has_water.known() else None,
        "flow_l_per_min": w.flow_l_per_min.value if w.flow_l_per_min.known() else None,
        "operating_depth_mm": (
            w.operating_depth_mm.value if w.operating_depth_mm.known() else None
        ),
        "nozzle_bore_mm": w.nozzle_bore_mm.value if w.nozzle_bore_mm.known() else None,
        "recirculating": w.recirculating.value if w.recirculating.known() else None,
    }


def to_site_overrides(intake: IntakeV1) -> dict[str, Any]:
    """Per-project structural inputs, applied OVER the gate profile.

    Only known values appear; the gate's `basis` strings then record the
    intake (and its source) as the provenance, and `signed_off` semantics
    are unchanged — an unsigned profile still downgrades breaches to warn.
    """
    out: dict[str, Any] = {}
    site = intake.site
    if site.altitude_m.known():
        out["site_altitude_m"] = float(site.altitude_m.value)
    if site.design_wind_speed_m_s.known():
        out["design_wind_speed_m_s"] = float(site.design_wind_speed_m_s.value)
    if site.indoor.known() and site.indoor.value is True:
        # Sheltered: the wind case is genuinely zero, whatever else says.
        out["design_wind_speed_m_s"] = 0.0
    if site.allowable_bearing_kpa.known():
        out["allowable_bearing_kpa"] = float(site.allowable_bearing_kpa.value)
    if out:
        out["_source"] = {
            "site_altitude_m": site.altitude_m.source,
            "design_wind_speed_m_s": site.design_wind_speed_m_s.source,
            "allowable_bearing_kpa": site.allowable_bearing_kpa.source,
        }
    return out


def to_dna_filters(intake: IntakeV1) -> dict[str, Any]:
    """Retrieval keys for DesignDNA precedent search (Phase 11 R2)."""
    filters: dict[str, Any] = {}
    if intake.water.has_water.known():
        filters["has_water"] = bool(intake.water.has_water.value)
    if intake.dimensions.height_m.known():
        filters["height_m"] = float(intake.dimensions.height_m.value)
    preferred = intake.materials.preferred
    if preferred.known() and preferred.value:
        filters["material"] = str(preferred.value[0])
    return filters


def summary_block(intake: IntakeV1, intake_id: str) -> str:
    """The normalized intake as a delimited Council prompt block.

    The Council receives structure, not only prose (the Phase 12 gate
    criterion). Unknown fields are listed AS unknown — the Council must not
    invent a budget the client never stated.
    """
    def fmt(f: Sourced[Any], unit: str = "") -> str:
        if not f.known():
            return "UNKNOWN"
        return f"{f.value}{unit} ({f.source})"

    lines = [
        f"=== BEGIN NORMALIZED INTAKE {intake_id} ===",
        "Structured client intake. (operator) = confirmed by the operator;",
        "(parsed) = extracted from the brief; UNKNOWN = genuinely not stated —",
        "do not invent a value for an UNKNOWN field.",
        "",
        f"project type: {fmt(intake.project.project_type)}"
        f" | setting: {fmt(intake.project.setting)}",
        f"site: {fmt(intake.site.city)}, {fmt(intake.site.country)}"
        f" | indoor: {fmt(intake.site.indoor)}"
        f" | altitude: {fmt(intake.site.altitude_m, ' m')}",
        f"wind (3s gust): {fmt(intake.site.design_wind_speed_m_s, ' m/s')}"
        f" | freeze risk: {fmt(intake.site.freeze_risk)}"
        f" | water available on site: {fmt(intake.site.water_available)}",
        f"overall height: {fmt(intake.dimensions.height_m, ' m')}"
        f" | footprint: {fmt(intake.dimensions.footprint_m, ' m')}",
        f"water design: {fmt(intake.water.has_water)}"
        f" | behaviour: {fmt(intake.water.behavior)}"
        f" | flow: {fmt(intake.water.flow_l_per_min, ' L/min')}",
        f"materials preferred: {fmt(intake.materials.preferred)}"
        f" | forbidden: {fmt(intake.materials.forbidden)}",
        f"culture/inspiration: {fmt(intake.culture.inspiration)}"
        f" | motifs: {fmt(intake.culture.motifs)}"
        f" | forbidden motifs: {fmt(intake.culture.forbidden_motifs)}",
        f"budget: {fmt(intake.budget.amount_min)}–{fmt(intake.budget.amount_max)}"
        f" {fmt(intake.budget.currency)}"
        f" | contingency: {fmt(intake.budget.contingency_pct, ' %')}"
        f" | deadline: {fmt(intake.budget.deadline)}",
        "=== END NORMALIZED INTAKE ===",
    ]
    return "\n".join(lines)
