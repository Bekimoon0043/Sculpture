"""Platform configuration: .env API keys + validated config/*.yaml loading.

Fails loudly on malformed YAML or structurally invalid config — a config the
operator half-edited must stop the platform at startup, not corrupt a run.

API keys are optional-but-warned: the platform boots without them, reports
each provider as "not configured", and the gate prints exactly which env var
to set. Key material is never logged anywhere.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("luxuryform.config")

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"

PROVIDERS: tuple[str, ...] = ("anthropic", "openai", "kimi")
# Kimi is served through Moonshot's OpenAI-compatible endpoint (ADR-002),
# so its key env var is MOONSHOT_API_KEY.
PROVIDER_ENV_VARS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
}


class ConfigError(RuntimeError):
    """Raised when a config file is missing, malformed, or invalid."""


class PricingLookupError(ConfigError):
    """Raised when a model has no price entry in pricing.yaml."""


# ---------------------------------------------------------------------------
# .env / environment
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """Environment-backed settings. All keys optional-but-warned."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    moonshot_api_key: str | None = None
    moonshot_base_url: str | None = None  # env override for council.yaml endpoint
    luxuryform_db: str = "./data/luxuryform.db"

    def key_for(self, provider: str) -> str | None:
        return {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "kimi": self.moonshot_api_key,
        }[provider]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def provider_keys_status(settings: Settings | None = None) -> dict[str, dict[str, object]]:
    """Which providers have a key configured. NEVER includes key material."""
    settings = settings or get_settings()
    status: dict[str, dict[str, object]] = {}
    for provider in PROVIDERS:
        configured = bool(settings.key_for(provider))
        env_var = PROVIDER_ENV_VARS[provider]
        if not configured:
            log.warning("provider %s is not configured (set %s in .env)", provider, env_var)
        status[provider] = {"configured": configured, "env_var": env_var}
    return status


# ---------------------------------------------------------------------------
# YAML loading + validation
# ---------------------------------------------------------------------------

def _load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    if not path.exists():
        raise ConfigError(f"config file missing: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping at the top level")
    return data


def _validate(model: type[BaseModel], data: dict, source: str) -> BaseModel:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"invalid {source}: {exc}") from exc


# --- council.yaml -----------------------------------------------------------

class RoleAssignment(BaseModel):
    primary: str | None = None
    parallel: str | None = None
    dynamic_rule: str | None = None
    providers: list[str] | None = None
    fallback: str | None = None


class ProviderModels(BaseModel):
    text: str
    vision: str | None = None  # None = no separate vision model; use `text`
    # Sampling temperature for text calls. None = OMIT the parameter from the
    # request entirely (required for fixed-temperature reasoning models such
    # as kimi-k3 — live docs: "temperature=1.0 ... fixed; omit them from
    # requests", fetched 2026-08-01). Never send temperature=0 to such a model.
    temperature: float | None = 0.0

    def vision_or_text(self) -> str:
        return self.vision or self.text


class CouncilConfig(BaseModel):
    roles: dict[str, RoleAssignment]
    model_defaults: dict[str, ProviderModels]
    # Per-provider API base URLs (ADR-009: live-doc sourced). None/missing =
    # SDK default. kimi carries the verified global endpoint.
    endpoints: dict[str, str | None] = {}

    @field_validator("model_defaults")
    @classmethod
    def _all_providers_have_models(
        cls, value: dict[str, ProviderModels]
    ) -> dict[str, ProviderModels]:
        missing = set(PROVIDERS) - set(value)
        if missing:
            raise ValueError(f"model_defaults missing providers: {sorted(missing)}")
        return value


# --- pricing.yaml (ADR-006) --------------------------------------------------

class PriceEntry(BaseModel):
    usd_per_1m_input_tokens: float = Field(gt=0)
    usd_per_1m_output_tokens: float = Field(gt=0)
    effective_date: str  # ISO date text; presence is what matters for honesty
    # Optional cache-class prices (ADR-022). Absent = that class is UNPRICED;
    # if a live response then reports tokens in that class, cost_usd raises —
    # a price is never guessed.
    usd_per_1m_cached_input_tokens: float | None = Field(default=None, gt=0)
    usd_per_1m_cache_write_input_tokens: float | None = Field(default=None, gt=0)

    @field_validator("effective_date")
    @classmethod
    def _looks_like_a_date(cls, value: str) -> str:
        import datetime as _dt

        try:
            _dt.date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"effective_date must be an ISO date (YYYY-MM-DD), got {value!r}"
            ) from exc
        return value


class PricingConfig(BaseModel):
    pricing_version: str
    providers: dict[str, dict[str, PriceEntry]]

    def price_for(self, provider: str, model: str) -> PriceEntry:
        """Look up a price. NEVER guesses — a missing entry is a hard error."""
        entry = self.providers.get(provider, {}).get(model)
        if entry is None:
            raise PricingLookupError(
                f"no price entry for {provider}/{model} in config/pricing.yaml "
                f"(pricing_version {self.pricing_version}); add it and bump "
                "pricing_version rather than guessing a price"
            )
        return entry

    def cost_usd(
        self,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        *,
        cached_input_tokens: int = 0,
        cache_write_input_tokens: int = 0,
    ) -> float:
        """Exact cost from real token counts, rounded to 6 decimal places.

        ADR-022 cache classes: ``tokens_in`` is the UNCACHED input count
        (providers normalise at the boundary). Cache-read and cache-write
        tokens price at their own classes; if a call reports tokens in a
        class the price entry does not cover, this raises — never guesses.
        """
        entry = self.price_for(provider, model)
        if cached_input_tokens and entry.usd_per_1m_cached_input_tokens is None:
            raise PricingLookupError(
                f"{provider}/{model} returned {cached_input_tokens} cache-READ "
                f"input tokens but config/pricing.yaml (pricing_version "
                f"{self.pricing_version}) has no usd_per_1m_cached_input_tokens "
                "price for it; add the verified price rather than guessing"
            )
        if cache_write_input_tokens and entry.usd_per_1m_cache_write_input_tokens is None:
            raise PricingLookupError(
                f"{provider}/{model} returned {cache_write_input_tokens} "
                f"cache-WRITE input tokens but config/pricing.yaml "
                f"(pricing_version {self.pricing_version}) has no "
                "usd_per_1m_cache_write_input_tokens price for it; add the "
                "verified price rather than guessing"
            )
        cost = (
            tokens_in * entry.usd_per_1m_input_tokens
            + cached_input_tokens * (entry.usd_per_1m_cached_input_tokens or 0.0)
            + cache_write_input_tokens
            * (entry.usd_per_1m_cache_write_input_tokens or 0.0)
            + tokens_out * entry.usd_per_1m_output_tokens
        ) / 1_000_000
        return round(cost, 6)


# --- budget.yaml (Amendment 2) ----------------------------------------------

class BudgetConfig(BaseModel):
    session_cap_usd: float = Field(gt=0)
    day_cap_usd: float = Field(gt=0)
    max_vision_iterations: int = Field(gt=0)
    on_breach: Literal["halt_and_report"]


# --- costing.yaml (Phase 3 operator amendment: rates schema designed NOW) ----

_CURRENCY_RE = r"^[A-Z]{3}$"
_COST_PER_UNITS = ("kg", "m3", "sheet", "slab", "hour", "piece", "m2",
                   "crew_day", "day", "trip")
_FABRICATION_METHODS = ("cnc_mill", "hand_carve", "cast", "sheet_fabricate")


class CostAmount(BaseModel):
    """A money amount with explicit currency and unit. amount=null means
    'template not filled yet' — loading is fine, COMPUTING is not."""
    amount: float | None = Field(default=None, ge=0)
    currency: str = Field(pattern=_CURRENCY_RE)
    per: str

    @field_validator("per")
    @classmethod
    def _known_unit(cls, value: str) -> str:
        if value not in _COST_PER_UNITS:
            raise ValueError(f"per must be one of {_COST_PER_UNITS}, got {value!r}")
        return value


class FabricationRates(BaseModel):
    method: str | None = None
    labor: CostAmount
    machine: CostAmount          # amount null if hand work
    hours_per_m3: float | None = Field(default=None, ge=0)
    mold_pattern: CostAmount     # cast only; amount null else

    @field_validator("method")
    @classmethod
    def _known_method(cls, value: str | None) -> str | None:
        if value is not None and value not in _FABRICATION_METHODS:
            raise ValueError(
                f"method must be one of {_FABRICATION_METHODS}, got {value!r}"
            )
        return value


class MaterialRates(BaseModel):
    buy_price: CostAmount
    waste_factor_pct: float | None = Field(default=None, ge=0)
    fabrication: FabricationRates
    finishing: CostAmount


class InstallRates(BaseModel):
    crew_day_rate: CostAmount
    crew_size: int | None = Field(default=None, ge=1)
    days_per_tonne: float | None = Field(default=None, ge=0)
    crane_day_rate: CostAmount   # amount null if none
    transport: CostAmount


class FxRate(BaseModel):
    """Units of the local currency per 1 USD, dated (anti-stale-data rule)."""
    rate: float | None = Field(default=None, gt=0)
    as_of: str | None = None

    @field_validator("as_of")
    @classmethod
    def _date_or_none(cls, value: str | None) -> str | None:
        if value is not None:
            import datetime as _dt

            try:
                _dt.date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(
                    f"fx as_of must be an ISO date (YYYY-MM-DD), got {value!r}"
                ) from exc
        return value


class CostingConfig(BaseModel):
    """Operator-provided rate card. LOADS with nulls (template state); any
    cost computation must call require_filled() first — a cost is never
    guessed (same rule as pricing.yaml)."""

    costing_version: str
    meta: dict
    materials: dict[str, MaterialRates]
    workshop: dict
    install: InstallRates
    contingency_pct: float | None = Field(default=None, ge=0)
    markup_pct: float | None = Field(default=None, ge=0)
    fx_rates: dict[str, FxRate]

    def missing_entries(self) -> list[str]:
        """Dotted paths of every rate that is still null (template state)."""
        missing: list[str] = []

        def amount(path: str, a: CostAmount) -> None:
            if a.amount is None:
                missing.append(path)

        for mid, m in self.materials.items():
            amount(f"materials.{mid}.buy_price", m.buy_price)
            if m.waste_factor_pct is None:
                missing.append(f"materials.{mid}.waste_factor_pct")
            if m.fabrication.method is None:
                missing.append(f"materials.{mid}.fabrication.method")
            amount(f"materials.{mid}.fabrication.labor", m.fabrication.labor)
            if m.fabrication.hours_per_m3 is None:
                missing.append(f"materials.{mid}.fabrication.hours_per_m3")
            amount(f"materials.{mid}.finishing", m.finishing)
            # machine / mold_pattern stay legitimately null by method — not flagged
        if self.workshop.get("overhead_pct") is None:
            missing.append("workshop.overhead_pct")
        amount("install.crew_day_rate", self.install.crew_day_rate)
        if self.install.crew_size is None:
            missing.append("install.crew_size")
        if self.install.days_per_tonne is None:
            missing.append("install.days_per_tonne")
        amount("install.transport", self.install.transport)
        if self.contingency_pct is None:
            missing.append("contingency_pct")
        if self.markup_pct is None:
            missing.append("markup_pct")
        for cur, fx in self.fx_rates.items():
            if fx.rate is None:
                missing.append(f"fx_rates.{cur}.rate")
            if fx.as_of is None:
                missing.append(f"fx_rates.{cur}.as_of")
        return missing

    def require_filled(self) -> None:
        """Hard error naming every unfilled rate. Called before ANY cost
        computation — never compute from a half-filled rate card."""
        missing = self.missing_entries()
        if missing:
            raise ConfigError(
                "costing.yaml is not filled in — cannot compute costs. "
                f"Missing {len(missing)} entries: " + ", ".join(missing)
            )


# --- materials.yaml ----------------------------------------------------------

class StockSizeMm(BaseModel):
    length: float = Field(gt=0)
    width: float = Field(gt=0)


class Material(BaseModel):
    name: str
    category: str
    density_kg_per_m3: float = Field(gt=0)
    min_wall_mm: float = Field(gt=0)
    # ADR-027: per-material fabrication envelope ceiling (workshop-set,
    # tunable in materials.yaml — not an external standard citation).
    max_wall_mm: float = Field(gt=0)
    stock_size_mm: StockSizeMm | None = None  # None = cast, no stock sheet


class MaterialsConfig(BaseModel):
    materials: dict[str, Material]


# --- bundle ------------------------------------------------------------------

class ConfigBundle(BaseModel):
    """All four config files, validated together at startup."""

    model_config = {"arbitrary_types_allowed": True}

    council: CouncilConfig
    pricing: PricingConfig
    budget: BudgetConfig
    materials: MaterialsConfig
    costing: CostingConfig


def load_config_bundle() -> ConfigBundle:
    """Load and validate every config file. Raises ConfigError on any defect.

    Cross-file check: costing.yaml material keys must be a subset of
    materials.yaml ids (a rate for a material the library doesn't know is a
    typo the operator must see at startup, not at costing time)."""
    council = _validate(CouncilConfig, _load_yaml("council.yaml"), "council.yaml")
    pricing = _validate(PricingConfig, _load_yaml("pricing.yaml"), "pricing.yaml")
    budget = _validate(BudgetConfig, _load_yaml("budget.yaml"), "budget.yaml")
    materials = _validate(
        MaterialsConfig, _load_yaml("materials.yaml"), "materials.yaml"
    )
    costing = _validate(CostingConfig, _load_yaml("costing.yaml"), "costing.yaml")
    unknown = set(costing.materials) - set(materials.materials)
    if unknown:
        raise ConfigError(
            f"costing.yaml has rates for unknown material ids {sorted(unknown)}; "
            f"ids must match config/materials.yaml ({sorted(materials.materials)})"
        )
    missing_rates = set(materials.materials) - set(costing.materials)
    if missing_rates:
        raise ConfigError(
            f"costing.yaml is missing rate blocks for library materials "
            f"{sorted(missing_rates)} (null amounts are fine; the block must exist)"
        )
    return ConfigBundle(
        council=council, pricing=pricing, budget=budget,
        materials=materials, costing=costing,
    )
