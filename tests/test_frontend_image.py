"""Frontend image structure checks (ADR-013).

The frontend previously ran `npm ci` at every container start over the
operator's unreliable connection — no caching, no layer protection; a killed
npm left node_modules without vite and the container restart-looping
(2026-08-02). These tests lock in the fix: node_modules installed at image
build time, in layers, with a build-time vite existence check, and a
compose service that builds the image instead of re-installing at start.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _frontend_dockerfile() -> str:
    path = ROOT / "frontend" / "Dockerfile"
    assert path.exists(), "frontend/Dockerfile missing (ADR-013)"
    return path.read_text(encoding="utf-8")


def _instructions(text: str) -> str:
    """Dockerfile/YAML text with comment lines removed, so structural
    assertions match instructions, not prose."""
    return "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("#")
    )


def test_manifests_copied_before_npm_ci_before_source():
    text = _instructions(_frontend_dockerfile())
    copy_pkg = text.index("COPY package.json package-lock.json ./")
    npm_ci = text.index("npm ci")
    copy_src = text.index("COPY . .")
    assert copy_pkg < npm_ci < copy_src, (
        "layer order must be: manifests -> npm ci -> source, so source "
        "edits never invalidate the dependency layer"
    )


def test_npm_ci_flags_and_retry_config():
    raw = _frontend_dockerfile()
    text = _instructions(raw)
    ci_line = next(l for l in text.splitlines() if "npm ci" in l)
    assert "--no-audit" in ci_line and "--no-fund" in ci_line, (
        "npm ci must skip audit/fund registry round-trips (failure surface)"
    )
    for var in ("NPM_CONFIG_FETCH_RETRIES", "NPM_CONFIG_FETCH_TIMEOUT"):
        assert var in raw, f"{var} not set in frontend/Dockerfile"


def test_build_time_vite_check():
    text = _instructions(_frontend_dockerfile())
    check_pos = text.find("test -x node_modules/.bin/vite")
    assert check_pos != -1, (
        "no build-time vite existence check — a frontend image that cannot "
        "start its dev server must fail at build time (ADR-013)"
    )
    assert text.index("npm ci") < check_pos, "vite check must follow npm ci"


def test_host_node_modules_cannot_shadow_image():
    dockerignore = ROOT / "frontend" / ".dockerignore"
    assert dockerignore.exists(), (
        "frontend/.dockerignore missing — a corrupt host-side node_modules "
        "would be COPYed over the image's good one"
    )
    assert "node_modules/" in dockerignore.read_text(encoding="utf-8")


def test_compose_frontend_builds_image_no_start_time_install():
    compose = _instructions((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    frontend_section = compose.split("frontend:")[1]
    assert "build: ./frontend" in frontend_section, (
        "frontend service must build frontend/Dockerfile"
    )
    assert "npm ci" not in frontend_section, (
        "npm ci must not run at container start (ADR-013)"
    )
    assert "./frontend:/app" not in frontend_section, (
        "no bind mount over /app — it would shadow the image's node_modules"
    )
