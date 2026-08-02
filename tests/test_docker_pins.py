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


def dockerfile_pins(name: str = "Dockerfile") -> dict[str, str]:
    text = (ROOT / name).read_text(encoding="utf-8")
    text = re.sub(r"\\\n", " ", text)  # join backslash continuation lines
    pins = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("RUN pip install"):
            continue
        for m in PIN_RE.finditer(line):
            name2 = m.group(1).lower().replace("_", "-")
            pins[name2] = m.group(2)
    return pins


def test_dockerfile_pins_match_pyproject():
    pp = pyproject_pins()
    for dockerfile in ("Dockerfile", "Dockerfile.donor"):
        df = dockerfile_pins(dockerfile)
        missing_in_docker = {k: v for k, v in pp.items() if k not in df}
        missing_in_pyproject = {k: v for k, v in df.items() if k not in pp}
        version_mismatch = {
            k: (pp[k], df[k]) for k in pp if k in df and pp[k] != df[k]
        }
        assert not missing_in_docker, (
            f"[{dockerfile}] pinned in pyproject.toml but not installed: "
            f"{missing_in_docker}"
        )
        assert not missing_in_pyproject, (
            f"[{dockerfile}] installed but not pinned in pyproject.toml: "
            f"{missing_in_pyproject}"
        )
        assert not version_mismatch, (
            f"[{dockerfile}] version mismatch (pyproject, {dockerfile}): "
            f"{version_mismatch}"
        )


def test_heavy_transitives_pinned_first_layers():
    """cadquery-ocp-novtk must be installed in an earlier RUN layer than
    build123d, or the layer-cache protection is pointless (ADR-011)."""
    for dockerfile in ("Dockerfile", "Dockerfile.donor"):
        text = (ROOT / dockerfile).read_text(encoding="utf-8")
        ocp_pos = text.index("cadquery-ocp-novtk==")
        b123d_pos = text.index("build123d==")
        assert ocp_pos < b123d_pos, (
            f"[{dockerfile}] cadquery-ocp-novtk must be installed BEFORE "
            "build123d (heaviest, most stable layer first)"
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
    """ADR-014/ADR-016 (backend distro TRIXIE): the kernel needs only the
    GL/X11 sonames resolvable — it never creates a GL context. The full
    mesa chain (libglx-mesa0 -> mesa-libgallium -> libgl1-mesa-dri ->
    libllvm19, ~222 MB installed) OOM-killed the operator's build.
    ADR-016: the readelf-only audit missed libGLX.so.0 (runtime-resolved
    through glvnd, invisible to readelf -d), so libglx0 is in the set;
    debs are pulled straight from the trixie pool (NO apt-get update —
    the operator measured a 10m26s full-index fetch), pinned by sha256,
    installed via dpkg --force-depends with a guard that fails the build
    on any unexpected "depends on" complaint, and re-proven by ldd."""
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    code = _no_comments(text)
    joined = re.sub(r"\\\n", " ", code)  # logical lines
    gl_line = next(
        (l for l in joined.splitlines()
         if l.startswith('RUN python -c "import urllib.request')),
        None,
    )
    assert gl_line, "GL layer must download debs directly (no apt-get update)"
    # the 9-package minimal set (ADR-016: libglx0 added — the readelf-only
    # audit missed libGLX.so.0; dpkg had named it and was ignored.
    # libexpat1 added — base-image contents were assumed, not verified;
    # the wheel's bundled fontconfig NEEDs libexpat.so.1 and it is NOT in
    # python:3.11-slim-trixie. It would have arrived as a mesa-chain side
    # effect, which is why trimming exposed it — operator ldd guard,
    # 2026-08-03)
    for pkg in ("libgl1_", "libglvnd0_", "libglx0_", "libx11-6_",
                "libx11-data_", "libxcb1_", "libxau6_", "libxdmcp6_",
                "libexpat1_"):
        assert pkg in gl_line, f"{pkg} missing from minimal GL package set"
    # banned packages must not be DOWNLOADED (trailing _ matches the .deb
    # filename form, so the grep-allowlist mention of libglx-mesa0 below
    # does not false-positive here)
    for banned in ("libglx-mesa0_", "mesa-libgallium", "libgl1-mesa-dri",
                   "libllvm19", "libgl1-mesa-glx"):
        assert banned not in gl_line, (
            f"{banned} must not be installed — mesa/llvm chain OOM-killed "
            "the operator's build (ADR-014)"
        )
    # no apt index fetch anywhere in the image build (ADR-016: the 10m26s
    # full-index fetch the operator measured is eliminated)
    assert "apt-get" not in code, "apt-get must not appear — debs come from the pool with sha256 pins"
    # Plan A (ADR-017): pool base URL is a build ARG with the deb.debian.org
    # default; the download one-liner must read it from the environment —
    # sha256 pins make any mirror pure transport
    assert "ARG DEB_POOL_URL=http://deb.debian.org/debian/pool/main/" in code
    assert "os.environ['DEB_POOL_URL']" in gl_line, (
        "pool URL must come from the DEB_POOL_URL build ARG (ADR-017)"
    )
    # integrity: every deb pinned by sha256 (9 hashes), verified before install
    assert "sha256sum -c sums.txt" in gl_line
    hashes = re.findall(r"\b[0-9a-f]{64}\b", gl_line)
    assert len(hashes) == 9, f"expected 9 sha256 deb pins, found {len(hashes)}"
    # install verification = STATE, not prose (ADR-016 v2, operator
    # correction 2026-08-03): parsing "depends on" complaint text false-
    # positived on a configuration-ORDER artifact (dpkg configures ./*.deb
    # alphabetically — libgl1 before libglx0 — so a bare "depends on" with
    # no "however: Package X is not installed" is an ordering note). The
    # layer must assert dpkg-query Status for all 8 packages; the only
    # retained prose rule targets "is not installed" (genuinely missing),
    # allowlisting the one deliberate skip (libglx-mesa0).
    assert "dpkg --force-depends" in gl_line
    assert "grep 'depends on'" not in gl_line, (
        "the v1 prose guard false-positived on ordering artifacts — "
        "replaced by state checks (ADR-016 v2)"
    )
    assert "dpkg-query -W -f='${Status}' $p" in gl_line
    assert '"install ok installed"' in gl_line
    loop_seg = "libgl1" + gl_line.split("for p in libgl1", 1)[1].split("; do", 1)[0]
    assert loop_seg.split() == [
        "libgl1", "libglvnd0", "libglx0", "libx11-6", "libx11-data",
        "libxcb1", "libxau6", "libxdmcp6", "libexpat1",
    ], "state loop must assert all 9 GL/expat packages"
    assert "grep 'is not installed' dpkg.log" in gl_line
    assert "grep -v 'libglx-mesa0'" in gl_line, (
        "only libglx-mesa0 may be allowlisted (deliberate, justified skip)"
    )
    # ldd re-proof: zero unresolved sonames across system libs + OCP TK libs
    assert "ldd" in gl_line and "'not found'" in gl_line
    assert "cadquery_ocp_novtk.libs" in gl_line, (
        "ldd must also cover the OCP wheel's TK libraries (the libs that "
        "actually failed to load, ADR-016)"
    )
    assert "rm -rf /tmp/gl" in gl_line
    # position: after the pip layers, before the first COPY
    gl_pos = code.index('RUN python -c "import urllib.request')
    pip_last = code.index("pytest==")           # last pip layer (Phase 1 deps)
    copy_pos = code.index("COPY pyproject.toml")
    assert pip_last < gl_pos < copy_pos, (
        "GL layer must be AFTER the pip layers and BEFORE 'COPY "
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
    assert code.index('RUN python -c "import urllib.request') < smoke_pos, (
        "smoke test before GL layer"
    )


def test_donor_dockerfile_structure():
    """Plan B (ADR-017): Dockerfile.donor transports the 9 system libraries
    from a Docker Hub donor image (no deb.debian.org contact). It must be a
    multi-stage build with a selectable donor, copy all 9 soname families
    with symlinks, fail loudly on an incomplete donor, and keep the same
    guarantees (state check, ldd guard over system + wheel libs, identical
    smoke test, suite-pinned final base, same layer order)."""
    text = (ROOT / "Dockerfile.donor").read_text(encoding="utf-8")
    code = _no_comments(text)
    joined = re.sub(r"\\\n", " ", code)
    assert "ARG GL_DONOR_IMAGE=" in code, "donor image must be a build ARG"
    assert "FROM ${GL_DONOR_IMAGE} AS gldonor" in code
    assert "FROM python:3.11-slim-trixie" in code, (
        "final stage base must stay suite-pinned (ADR-014)"
    )
    copy_line = next(
        (l for l in joined.splitlines() if l.startswith("RUN --mount=from=gldonor")),
        None,
    )
    assert copy_line, "donor copy layer must mount the donor stage"
    for pat in ("libGL.so.1*", "libGLX.so.0*", "libGLdispatch.so.0*",
                "libX11.so.6*", "libxcb.so.1*", "libXau.so.6*",
                "libXdmcp.so.6*", "libexpat.so.1*"):
        assert pat in copy_line, f"donor copy must include {pat}"
    assert "cp -a" in copy_line, "symlinks must be preserved (cp -a)"
    assert "DONOR MISSING" in copy_line and "exit 1" in copy_line, (
        "an incomplete donor must fail the build loudly, naming the pattern"
    )
    assert "ldconfig" in copy_line
    # state check: every soname resolvable after copy (test -e follows links)
    for s in ("libGL.so.1", "libGLX.so.0", "libGLdispatch.so.0", "libX11.so.6",
              "libxcb.so.1", "libXau.so.6", "libXdmcp.so.6", "libexpat.so.1"):
        assert f"/usr/lib/x86_64-linux-gnu/{s}" in copy_line, (
            f"post-copy state check must cover {s}"
        )
    # same ldd guarantee as the main Dockerfile, incl. wheel libs + expat
    assert "ldd" in copy_line and "'not found'" in copy_line
    assert "cadquery_ocp_novtk.libs/*.so*" in copy_line
    assert "libexpat.so.1" in copy_line.split("ldd", 1)[1], (
        "ldd must directly cover libexpat.so.1 (the ADR-016 v3 miss)"
    )
    # identical smoke test to the main Dockerfile
    smoke = 'RUN python -c "import build123d; from build123d import Box, export_step, export_gltf'
    assert smoke in code, "donor variant must keep the build-time smoke test"
    # layer order: pip layers -> donor copy -> smoke -> first COPY
    assert code.index("build123d==") < code.index("RUN --mount=from=gldonor")
    assert code.index("RUN --mount=from=gldonor") < code.index(smoke)
    assert code.index(smoke) < code.index("COPY pyproject.toml")


def test_compose_backend_dockerfile_switch_and_args():
    """ADR-017: compose must allow switching the backend Dockerfile
    (Plan B) and pass through DEB_POOL_URL (Plan A) and GL_DONOR_IMAGE
    (Plan B) without editing any file."""
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    code = _no_comments(text)
    assert "dockerfile: ${BACKEND_DOCKERFILE:-Dockerfile}" in code, (
        "backend build must default to Dockerfile and allow the donor "
        "variant via BACKEND_DOCKERFILE"
    )
    assert "DEB_POOL_URL: ${DEB_POOL_URL:-http://deb.debian.org/debian/pool/main/}" in code
    assert "GL_DONOR_IMAGE: ${GL_DONOR_IMAGE:-" in code
