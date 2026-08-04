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


def _logical_lines(text: str) -> list[str]:
    """Comment-stripped, backslash-joined logical instruction lines."""
    import re
    return _instructions(re.sub(r"\\\n", " ", text)).splitlines()


def test_manifests_copied_before_npm_ci_before_source():
    text = _instructions(_frontend_dockerfile())
    copy_pkg = text.index("COPY package.json package-lock.json ./")
    npm_ci = text.index("npm ci")
    copy_src = text.index("COPY . .")
    assert copy_pkg < npm_ci < copy_src, (
        "layer order must be: manifests -> npm ci -> source, so source "
        "edits never invalidate the dependency layer"
    )


def test_npm_upgraded_to_honest_exit_code_version():
    """ADR-015: the bundled npm 10.8.2 exits 0 after crashing ("Exit handler
    never called!"), so the build layer lies DONE. npm/cli#7674 fixed the
    exit code after 10.8.2; npm@11.19.0 is the newest whose engines accept
    node 20 (npm 12 requires node >=22.22.2). The upgrade layer must exist,
    be pinned, and self-verify."""
    lines = _logical_lines(_frontend_dockerfile())
    upgrade = [l for l in lines if "npm install -g" in l]
    assert upgrade, "no npm upgrade layer (ADR-015)"
    assert "npm@11.19.0" in upgrade[0], "npm upgrade must be pinned to 11.19.0"
    assert "npm --version" in upgrade[0] and "grep" in upgrade[0], (
        "npm upgrade layer must self-verify the installed version (it runs "
        "on the buggy npm 10.8.2 and could itself zero-exit crash)"
    )
    ci_pos = next(i for i, l in enumerate(lines) if "npm ci" in l)
    assert lines.index(upgrade[0]) < ci_pos, "npm upgrade must precede npm ci"


def test_npm_ci_flags_retry_and_same_run_verification():
    """ADR-013/015: the npm ci RUN must (a) use --no-audit/--no-fund,
    (b) retry on nonzero exit, and (c) verify the result IN THE SAME RUN,
    so a zero-exit npm crash can never mark the layer DONE."""
    raw = _frontend_dockerfile()
    lines = _logical_lines(raw)
    ci_line = next(l for l in lines if "npm ci" in l)
    assert "--no-audit" in ci_line and "--no-fund" in ci_line, (
        "npm ci must skip audit/fund registry round-trips (failure surface)"
    )
    assert "for attempt in" in ci_line, "npm ci must be wrapped in a retry loop"
    assert "npm ls --depth=0" in ci_line, (
        "same RUN must verify tree completeness (zero-exit crash mid-reify "
        "can leave a partial node_modules that still contains vite)"
    )
    assert "test -x node_modules/.bin/vite" in ci_line, (
        "vite existence check must be in the SAME RUN as npm ci — a layer "
        "that lies about success is worse than one that fails (operator, "
        "2026-08-02)"
    )
    for var in ("NPM_CONFIG_FETCH_RETRIES", "NPM_CONFIG_FETCH_TIMEOUT"):
        assert var in raw, f"{var} not set in frontend/Dockerfile"


def test_build_time_vite_check():
    lines = _logical_lines(_frontend_dockerfile())
    ci_line = next(l for l in lines if "npm ci" in l)
    check_pos = ci_line.find("test -x node_modules/.bin/vite")
    assert check_pos != -1, (
        "no build-time vite existence check in the npm ci RUN — a frontend "
        "image that cannot start its dev server must fail at build time"
    )
    assert ci_line.index("npm ci") < check_pos, "vite check must follow npm ci"
    assert "vite --version" in ci_line[check_pos:], (
        "the check must also EXECUTE vite --version, not only test -x"
    )


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


def test_lockfile_resolved_urls_use_public_npmjs():
    """ADR-019: the lockfile was generated inside a build sandbox whose npm
    registry was an internal mirror (npm.mirrors.msh.team); that host was
    baked into every `resolved` URL and does not exist outside the sandbox
    — the operator's npm ci died with ENOTFOUND (2026-08-04). `npm ci`
    follows `resolved` verbatim, so every resolved host must be the public
    registry. Integrity hashes are content hashes and are mirror-
    independent, so the rewritten URLs are still fully verified by npm."""
    import json
    import re
    lock = (ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8")
    hosts = set(re.findall(r'"resolved":\s*"https?://([^/"]+)', lock))
    assert hosts, "lockfile must carry resolved URLs (npm ci fetches them)"
    assert hosts == {"registry.npmjs.org"}, (
        f"resolved URLs must all use registry.npmjs.org — a sandbox-internal "
        f"mirror host leaks into the committed lockfile and breaks any "
        f"machine outside the sandbox; found: {sorted(hosts)}"
    )
    data = json.loads(lock)  # must stay valid JSON after any rewrite
    assert data["packages"], "lockfile packages section must be non-empty"
