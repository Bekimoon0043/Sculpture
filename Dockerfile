# ADR-014: the Debian suite is PINNED. The floating `python:3.11-slim` tag
# silently moved bookworm -> trixie, which invalidated bookworm-verified
# package facts (operator correction, 2026-08-02). Backend distro: TRIXIE.
# (Frontend image: node:20-bookworm-slim — BOOKWORM. Different distros;
# package facts are verified per-distro, never assumed shared.)
FROM python:3.11-slim-trixie

WORKDIR /app

# Operator-selectable package index (default: PyPI). Override at build time
# without editing this file:
#   docker compose build --build-arg PIP_INDEX_URL=https://your.mirror/simple
# No mirror is recommended in operator docs: mirror coverage varies by
# location and package version (operator mirror test, Addis Ababa,
# 2026-08-02 — a mirror that works in one place failed there).
ARG PIP_INDEX_URL=https://pypi.org/simple

# Layered installs, heaviest and most stable first, so Docker's layer cache
# protects completed downloads: a dropped connection now costs ONE layer,
# not the whole build (the operator's single-transaction build failed twice
# at ~21 minutes on a ~320 kB/s line, 2026-08-01/02).
# If a build drops mid-layer, simply re-run the same command — finished
# layers are NOT downloaded again.
#
# Pins here MUST match pyproject.toml exactly — enforced by
# tests/test_docker_pins.py.

# Layer 1: OCCT kernel (~300 MB wheel — the long pole)
RUN pip install --no-cache-dir --retries 10 --timeout 120 \
    --index-url ${PIP_INDEX_URL} \
    cadquery-ocp-novtk==7.9.3.1.1

# Layer 2: scientific stack (hard requirements of build123d 0.11.1, ~100 MB)
RUN pip install --no-cache-dir --retries 10 --timeout 120 \
    --index-url ${PIP_INDEX_URL} \
    numpy==2.4.6 scipy==1.17.1 scikit-learn==1.9.0

# Layer 3: geometry kernel + mesh validation (plus build123d's remaining
# small deps: sympy, ipython, ezdxf, lib3mf, etc.)
RUN pip install --no-cache-dir --retries 10 --timeout 120 \
    --index-url ${PIP_INDEX_URL} \
    build123d==0.11.1 trimesh==5.0.0

# Layer 4: Phase 1 backend deps
RUN pip install --no-cache-dir --retries 10 --timeout 120 \
    --index-url ${PIP_INDEX_URL} \
    fastapi==0.115.6 "uvicorn[standard]==0.32.1" sqlalchemy==2.0.36 \
    pydantic==2.10.4 pydantic-settings==2.7.0 pyyaml==6.0.2 httpx==0.28.1 \
    anthropic==0.42.0 openai==1.59.3 pillow==11.0.0 jsonschema==4.23.0 \
    pytest==8.3.4

# Layer 5: the TWO system libraries the OCCT kernel needs at import time —
# nothing more (ADR-014, backend distro TRIXIE).
# Audit of all 69 .so files in the cadquery-ocp-novtk 7.9.3.1.1 wheel
# (readelf NEEDED, 2026-08-02): exactly two sonames are absent from the
# slim image — libGL.so.1 and libX11.so.6. The wheel bundles its own
# gomp/fontconfig/freetype; libc/libm/libdl/libpthread/libgcc_s/libstdc++/
# libz/libexpat are already present (loader-order evidence from the
# operator's libGL crash).
# THE PACKAGE SET IS THE MEMORY FIX: `apt-get install libgl1` on trixie
# hard-pulls libglx0 -> libglx-mesa0 -> mesa-libgallium + libgl1-mesa-dri
# -> libllvm19: 49 packages, 53.5 MB download, ~222 MB installed — dpkg
# unpacking libllvm19 (123.7 MB installed) is what the OOM killer hit
# (operator build log, 2026-08-02). None of it is needed: the kernel never
# creates a GL context (headless STEP/GLB export only); the loader only
# needs the two sonames resolvable. So we install ONLY the packages whose
# FILES provide them (verified against the live trixie main index and by
# listing the debs' contents, 2026-08-02): libGL.so.1 <- libgl1, its link
# dep libGLdispatch.so.0 <- libglvnd0, libX11.so.6 <- libx11-6 (+ its file
# deps libxcb1/libxau6/libxdmcp6 + libx11-data). 7 packages, 1.5 MB total.
# dpkg --force-depends: libgl1's package-level hard dep on libglx0 is a
# GLX-functionality dependency, not a link dependency — libGL.so.1 NEEDs
# only libGLdispatch/libdl/libc. The smoke layer below proves the full
# import + BREP + STEP + GLB path works without the mesa backend.
# POSITION IS DELIBERATE: after the pip layers, so system-package edits
# never invalidate the ~400 MB of cached downloads (needed at import time,
# not install time).
RUN mkdir /tmp/glx && cd /tmp/glx \
    && apt-get update \
    && apt-get download libgl1 libglvnd0 libx11-6 libx11-data libxcb1 libxau6 libxdmcp6 \
    && dpkg --force-depends -i ./*.deb \
    && cd / && rm -rf /tmp/glx /var/lib/apt/lists/*

# Layer 6: build-time smoke test — import the kernel, build a trivial
# solid, and exercise BOTH export paths (STEP and GLB) HERE. A backend that
# cannot import its own kernel fails the BUILD now, not at runtime in a
# restart loop (operator incident, 2026-08-02). This also proves the
# minimal GL package set above is sufficient for every path the app uses.
RUN python -c "import build123d; from build123d import Box, export_step, export_gltf; s = Box(10, 10, 10); assert abs(s.volume - 1000.0) < 1e-6; export_step(s, '/tmp/smoke.step'); export_gltf(s, '/tmp/smoke.glb', binary=True); import os; assert os.path.getsize('/tmp/smoke.step') > 1000 and open('/tmp/smoke.glb','rb').read(4) == b'glTF'; print('SMOKE OK: build123d', build123d.__version__, 'import + BREP + STEP + GLB')"

# Layer 7: the app itself (deps already installed above)
COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir --no-deps -e .
COPY . .

ENV LUXURYFORM_DB=/app/data/luxuryform.db
VOLUME /app/data
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
