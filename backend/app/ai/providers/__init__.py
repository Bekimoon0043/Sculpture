"""Concrete AI providers + the factory that wires them from real config."""

from __future__ import annotations

from app.ai.provider import AIProvider
from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.kimi_provider import KimiProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.budget import BudgetEnforcer
from app.core.config import ConfigBundle, Settings
from app.db.database import Database

__all__ = [
    "AIProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "KimiProvider",
    "build_providers",
]


def build_providers(
    settings: Settings,
    config: ConfigBundle,
    db: Database,
    budget: BudgetEnforcer | None = None,
) -> dict[str, AIProvider]:
    """Build all three providers from settings + council.yaml model defaults.

    Providers without an API key are still returned — their calls fail
    honestly with ProviderError("provider not configured") before any network,
    which is what the gate reports on.
    """
    models = config.council.model_defaults
    return {
        "anthropic": AnthropicProvider(
            settings.anthropic_api_key,
            text_model=models["anthropic"].text,
            vision_model=models["anthropic"].vision,
            db=db,
            pricing=config.pricing,
            budget=budget,
        ),
        "openai": OpenAIProvider(
            settings.openai_api_key,
            text_model=models["openai"].text,
            vision_model=models["openai"].vision,
            db=db,
            pricing=config.pricing,
            budget=budget,
        ),
        "kimi": KimiProvider(
            settings.moonshot_api_key,
            text_model=models["kimi"].text,
            vision_model=models["kimi"].vision,
            db=db,
            pricing=config.pricing,
            budget=budget,
        ),
    }
