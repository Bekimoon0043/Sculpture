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
    vision: str


class CouncilConfig(BaseModel):
    roles: dict[str, RoleAssignment]
    model_defaults: dict[str, ProviderModels]

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
        self, provider: str, model: str, tokens_in: int, tokens_out: int
    ) -> float:
        """Exact cost from real token counts, rounded to 6 decimal places."""
        entry = self.price_for(provider, model)
        cost = (
            tokens_in * entry.usd_per_1m_input_tokens
            + tokens_out * entry.usd_per_1m_output_tokens
        ) / 1_000_000
        return round(cost, 6)


# --- budget.yaml (Amendment 2) ----------------------------------------------

class BudgetConfig(BaseModel):
    session_cap_usd: float = Field(gt=0)
    day_cap_usd: float = Field(gt=0)
    max_vision_iterations: int = Field(gt=0)
    on_breach: Literal["halt_and_report"]


# --- materials.yaml ----------------------------------------------------------

class StockSizeMm(BaseModel):
    length: float = Field(gt=0)
    width: float = Field(gt=0)


class Material(BaseModel):
    name: str
    category: str
    density_kg_per_m3: float = Field(gt=0)
    min_wall_mm: float = Field(gt=0)
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


def load_config_bundle() -> ConfigBundle:
    """Load and validate every config file. Raises ConfigError on any defect."""
    return ConfigBundle(
        council=_validate(CouncilConfig, _load_yaml("council.yaml"), "council.yaml"),
        pricing=_validate(PricingConfig, _load_yaml("pricing.yaml"), "pricing.yaml"),
        budget=_validate(BudgetConfig, _load_yaml("budget.yaml"), "budget.yaml"),
        materials=_validate(
            MaterialsConfig, _load_yaml("materials.yaml"), "materials.yaml"
        ),
    )
