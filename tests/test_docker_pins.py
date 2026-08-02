"""Pin-consistency check: Dockerfile pip layers vs pyproject.toml (ADR-011).

The Dockerfile installs pinned packages in separate RUN layers so Docker's
cache protects completed downloads on the operator's unreliable connection.
Those pins duplicate pyproject.toml by design (layers need explicit version
arguments), so this test makes the duplication safe: every pinned
requirement in pyproject.toml must appear in a Dockerfile pip layer with
the SAME version, and vice versa. If either file is edited without the
other, this test fails instead of silently diverging.
"""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PIN_RE = re.compile(r'([A-Za-z0-9_\-\[\]]+)==([A-Za-z0-9.\*]+)')


def pyproject_pins() -> dict[str, str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    reqs = list(data["project"]["dependencies"])
    reqs += data["project"].get("optional-dependencies", {}).get("dev", [])
    pins = {}
    for r in reqs:
        m = PIN_RE.search(r)
        assert m, f"unpinned requirement in pyproject.toml: {r!r}"
        name = m.group(1).lower().replace("_", "-")
        pins[name] = m.group(2)
    return pins


def dockerfile_pins() -> dict[str, str]:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    text = re.sub(r"\\\n", " ", text)  # join backslash continuation lines
    pins = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("RUN pip install"):
            continue
        for m in PIN_RE.finditer(line):
            name = m.group(1).lower().replace("_", "-")
            pins[name] = m.group(2)
    return pins


def test_dockerfile_pins_match_pyproject():
    pp = pyproject_pins()
    df = dockerfile_pins()
    missing_in_docker = {k: v for k, v in pp.items() if k not in df}
    missing_in_pyproject = {k: v for k, v in df.items() if k not in pp}
    version_mismatch = {
        k: (pp[k], df[k]) for k in pp if k in df and pp[k] != df[k]
    }
    assert not missing_in_docker, (
        f"pinned in pyproject.toml but not installed by any Dockerfile layer: "
        f"{missing_in_docker}"
    )
    assert not missing_in_pyproject, (
        f"installed by Dockerfile but not pinned in pyproject.toml: "
        f"{missing_in_pyproject}"
    )
    assert not version_mismatch, (
        f"version mismatch pyproject vs Dockerfile (pyproject, Dockerfile): "
        f"{version_mismatch}"
    )


def test_heavy_transitives_pinned_first_layers():
    """cadquery-ocp-novtk must be installed in an earlier RUN layer than
    build123d, or the layer-cache protection is pointless (ADR-011)."""
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ocp_pos = text.index("cadquery-ocp-novtk==")
    b123d_pos = text.index("build123d==")
    assert ocp_pos < b123d_pos, (
        "cadquery-ocp-novtk must be installed BEFORE build123d in the "
        "Dockerfile (heaviest, most stable layer first)"
    )


def test_system_gl_libraries_present_and_positioned( ):
    """ADR-012: python:3.11-slim lacks libGL.so.1 and libX11.so.6, which the
    OCCT kernel needs at import time (operator backend crash, 2026-08-02).
    The apt layer MUST sit after the pip layers and before the first COPY,
    so system-package edits never invalidate the heavy cached downloads."""
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    apt_pos = text.index("apt-get install")
    apt_line_region = text[apt_pos:apt_pos + 300]
    for pkg in ("libgl1", "libglx-mesa0", "libx11-6"):
        assert pkg in apt_line_region, f"{pkg} missing from apt-get install"
    assert "libgl1-mesa-glx" not in apt_line_region, (
        "libgl1-mesa-glx is a transitional dummy in bookworm — use libgl1 "
        "and libglx-mesa0 directly (ADR-012)"
    )
    assert "--no-install-recommends" in apt_line_region
    assert "rm -rf /var/lib/apt/lists/*" in text[apt_pos:apt_pos + 500]
    pip_last = text.index("pytest==")           # last pip layer (Phase 1 deps)
    copy_pos = text.index("COPY pyproject.toml")
    assert pip_last < apt_pos < copy_pos, (
        "apt layer must be AFTER the pip layers and BEFORE 'COPY "
        "pyproject.toml' (layer-cache protection, operator constraint)"
    )


def test_build_time_kernel_smoke_test():
    """ADR-012: the image must fail at BUILD time if the geometry kernel
    cannot import and build a trivial solid — not in a runtime restart
    loop. The smoke RUN must sit after both the pip layers and the apt
    layer it depends on."""
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    smoke_pos = text.find('RUN python -c "import build123d')
    assert smoke_pos != -1, "no build-time kernel smoke test in Dockerfile"
    assert "Box" in text[smoke_pos:smoke_pos + 400], (
        "smoke test must build a trivial solid, not just import"
    )
    assert text.index("build123d==") < smoke_pos, "smoke test before pip layer"
    assert text.index("apt-get install") < smoke_pos, "smoke test before apt layer"
