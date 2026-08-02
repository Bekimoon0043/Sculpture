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
