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


def _no_comments(text: str) -> str:
    return "\n".join(
        l for l in text.splitlines() if not l.strip().startswith("#")
    )


def test_base_image_suite_pinned():
    """ADR-014: the floating `python:3.11-slim` tag silently moved bookworm
    -> trixie and invalidated bookworm-verified package facts. The suite
    must be explicit so distro-specific verification always applies."""
    text = _no_comments((ROOT / "Dockerfile").read_text(encoding="utf-8"))
    from_line = next(l for l in text.splitlines() if l.startswith("FROM "))
    assert from_line.strip() == "FROM python:3.11-slim-trixie", (
        f"base image must pin the Debian suite, got: {from_line.strip()}"
    )


def test_system_gl_libraries_minimal_set_and_positioned():
    """ADR-014 (backend distro TRIXIE): the kernel needs only libGL.so.1 and
    libX11.so.6 resolvable — it never creates a GL context. The full mesa
    chain (libglx-mesa0 -> mesa-libgallium -> libgl1-mesa-dri -> libllvm19,
    ~222 MB installed) OOM-killed the operator's build. The layer must
    install ONLY the 7 minimal packages via download + dpkg --force-depends,
    after the pip layers and before the first COPY."""
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    code = _no_comments(text)
    dl_pos = code.index("apt-get download")
    dl_region = code[dl_pos:dl_pos + 300]
    for pkg in ("libgl1", "libglvnd0", "libx11-6", "libx11-data",
                "libxcb1", "libxau6", "libxdmcp6"):
        assert pkg in dl_region, f"{pkg} missing from minimal GL package set"
    for banned in ("libglx-mesa0", "mesa-libgallium", "libgl1-mesa-dri",
                   "libllvm19", "libgl1-mesa-glx"):
        assert banned not in dl_region, (
            f"{banned} must not be installed — mesa/llvm chain OOM-killed "
            "the operator's build (ADR-014)"
        )
    assert "dpkg --force-depends" in code[dl_pos:dl_pos + 500]
    assert "rm -rf /tmp/glx /var/lib/apt/lists/*" in code
    pip_last = code.index("pytest==")           # last pip layer (Phase 1 deps)
    copy_pos = code.index("COPY pyproject.toml")
    assert pip_last < dl_pos < copy_pos, (
        "apt layer must be AFTER the pip layers and BEFORE 'COPY "
        "pyproject.toml' (layer-cache protection, operator constraint)"
    )


def test_build_time_kernel_smoke_test():
    """ADR-012/ADR-014: the image must fail at BUILD time if the kernel
    cannot import, build a trivial solid, AND exercise both export paths
    (STEP + GLB) — the GLB export is what makes the minimal mesa-free GL
    package set provably sufficient. Smoke must sit after pip and apt."""
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    code = _no_comments(text)
    smoke_pos = code.find('RUN python -c "import build123d')
    assert smoke_pos != -1, "no build-time kernel smoke test in Dockerfile"
    region = code[smoke_pos:smoke_pos + 600]
    assert "Box" in region, "smoke test must build a trivial solid"
    assert "export_step" in region and "export_gltf" in region, (
        "smoke test must exercise BOTH export paths (STEP + GLB) to prove "
        "the minimal GL set suffices (ADR-014)"
    )
    assert code.index("build123d==") < smoke_pos, "smoke test before pip layer"
    assert code.index("apt-get download") < smoke_pos, "smoke test before apt layer"
