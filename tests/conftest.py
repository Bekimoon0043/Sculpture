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
# Recorded SDK transports — TEST INFRASTRUCTURE, NOT PRODUCTION FAKERY.
#
# These stubs stand in for the anthropic/openai SDK *client objects* so the
# offline suite can exercise the REAL production code path (estimate -> cap
# check -> dispatch -> real cost math -> DB logging) without network or keys.
# The response objects mirror the exact attribute shape the SDKs return
# (content blocks / choices / usage). Production code never sees these:
# providers build real SDK clients unless a client is injected by a test.
# ---------------------------------------------------------------------------

from types import SimpleNamespace  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "scripts"))  # noqa: E402
import make_test_image  # noqa: E402


class RecordedAnthropicTransport:
    """Mimics anthropic.Anthropic: .messages.create(**kwargs) -> Message-like."""

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


class RecordedOpenAITransport:
    """Mimics openai.OpenAI: .chat.completions.create(**kwargs) -> response."""

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
    return RecordedAnthropicTransport


@pytest.fixture()
def openai_transport():
    return RecordedOpenAITransport


@pytest.fixture()
def test_image(tmp_path) -> Path:
    """The real deterministic gate test image, generated into a temp dir."""
    return make_test_image.generate(tmp_path / "gate_test_image.png")
