"""Shared pytest fixtures.

Every test gets a FRESH temporary SQLite database (schema applied) and the
REAL config files from the repo (config/*.yaml) — no fake config. Tests are
hermetic: provider API keys and LUXURYFORM_DB are scrubbed from the
environment so the suite passes with no keys and no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))  # works even without pip install -e

from app.core.config import (  # noqa: E402
    ConfigBundle,
    Settings,
    load_config_bundle,
)
from app.db.database import Database  # noqa: E402


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    """No API keys, no DB override — the suite never touches the network."""
    for var in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "MOONSHOT_API_KEY",
        "LUXURYFORM_DB",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture()
def settings() -> Settings:
    # _env_file=None: never read a real .env the operator may have created.
    return Settings(_env_file=None)


@pytest.fixture()
def config() -> ConfigBundle:
    return load_config_bundle()


@pytest.fixture()
def db(tmp_path) -> Database:
    database = Database(tmp_path / "test.db")
    database.init_db()
    return database


# ---------------------------------------------------------------------------
# Injected SDK transports — hand-constructed fakes. Stated plainly:
# these ARE mocks that pretend to be a provider's SDK client. They are
# legitimate test infrastructure, but they are mocks, and we call them that.
#
# They are HAND-CONSTRUCTED, not recorded: no real API response was ever
# captured to build them. They mirror the SDK response shape AS ASSUMED
# (content blocks / choices / usage), not as verified. If a real SDK shape
# differs, this suite passes while production fails — see LIMITATIONS.md.
# That assumption is retired only by the live gate run with real API keys.
#
# What they DO prove: the real production code path around the SDK call —
# estimate -> BudgetEnforcer.pre_dispatch_check -> dispatch -> real token/cost
# math from pricing.yaml -> ai_calls persistence. Production always builds
# real SDK clients; a transport can only be injected by a test.
# ---------------------------------------------------------------------------

from types import SimpleNamespace  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "scripts"))  # noqa: E402
import make_test_image  # noqa: E402


class InjectedAnthropicTransport:
    """Hand-constructed mock of anthropic.Anthropic:
    .messages.create(**kwargs) -> object shaped like the assumed Message."""

    def __init__(self, text: str, input_tokens: int, output_tokens: int,
                 error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._error = error
        self._response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(
                input_tokens=input_tokens, output_tokens=output_tokens
            ),
        )
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


class InjectedOpenAITransport:
    """Hand-constructed mock of openai.OpenAI (also used for Kimi, which is
    OpenAI-compatible): .chat.completions.create(**kwargs) -> assumed shape."""

    def __init__(self, text: str, input_tokens: int, output_tokens: int,
                 error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._error = error
        self._response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
            usage=SimpleNamespace(
                prompt_tokens=input_tokens, completion_tokens=output_tokens
            ),
        )
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


@pytest.fixture()
def anthropic_transport():
    return InjectedAnthropicTransport


@pytest.fixture()
def openai_transport():
    return InjectedOpenAITransport


@pytest.fixture()
def test_image(tmp_path) -> Path:
    """The real deterministic gate test image, generated into a temp dir."""
    return make_test_image.generate(tmp_path / "gate_test_image.png")
