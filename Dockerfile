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

# Layer 5: the system libraries the OCCT kernel needs at import time —
# nothing more (ADR-014/ADR-016, backend distro TRIXIE).
#
# METHOD CORRECTION (ADR-016): readelf -d alone is INSUFFICIENT for this
# audit. The 7-package set it produced missed libGLX.so.0: libGL.so.1
# resolves it through the glvnd dispatch layer at RUNTIME, so it appears in
# libGL.so.1's string table, not as a DT_NEEDED entry (operator build log,
# 2026-08-02: ImportError: libGLX.so.0 — caught by the smoke test below, at
# build, not in a restart loop). dpkg had also named the exact miss —
# "dependency problems, but configuring anyway: libgl1 depends on libglx0"
# — and it was wrongly treated as benign. Corrected audit method:
# readelf -d + strings scan for lib*.so candidates + dpkg-deb content
# listing + readelf of the EXTRACTED real libraries.
#
# THE PACKAGE SET IS THE MEMORY FIX: `apt-get install libgl1` on trixie
# hard-pulls libglx0 -> libglx-mesa0 -> mesa-libgallium + libgl1-mesa-dri
# -> libllvm19: 49 packages, 53.5 MB download, ~222 MB installed — dpkg
# unpacking libllvm19 (123.7 MB installed) is what the OOM killer hit
# (operator build log, 2026-08-02). None of it is needed: the kernel never
# creates a GL context (headless STEP/GLB export only); the loader only
# needs the sonames resolvable. libGLX.so.0.0.0 itself NEEDs ONLY
# libGLdispatch.so.0, libX11.so.6, libc.so.6 (readelf of the real trixie
# deb, 2026-08-02) — a GLX vendor (libglx-mesa0) is only dlopened when an
# application creates a GL context, which never happens here.
#
# THE SET — 8 packages, 1.53 MB download, 5.04 MB installed (verified
# against the live trixie main index AND against the actual deb bytes,
# 2026-08-02): libgl1, libglvnd0, libglx0, libx11-6, libx11-data, libxcb1,
# libxau6, libxdmcp6. Every NEEDED of every .so in the set resolves within
# the set + glibc — statically proven.
#
# NO apt-get update: the debs are pulled straight from the trixie pool by
# python (slim has no curl/wget), each pinned by sha256 recorded from the
# live index and re-verified against file bytes. This eliminates the
# multi-minute full-index fetch the operator measured (9.6 MB at 16 kB/s =
# 10m26s, before 1.5 MB of packages) and is STRONGER integrity than apt:
# a single flipped byte anywhere fails the layer loudly.
# INSTALL VERIFICATION — STATE, NOT PROSE (ADR-016 v2, operator correction
# 2026-08-03): the first guard parsed dpkg's complaint TEXT and false-
# positived on a configuration-ORDER artifact: dpkg configures ./*.deb
# alphabetically, so libgl1 is configured before libglx0, and dpkg prints
# "libgl1 depends on libglx0" with NO "however: Package ... is not
# installed" clause — an ordering note, not a missing package (operator's
# verbatim log: all 8 packages configured fine). Prose parsing has now
# misled twice in opposite directions — ignoring it shipped a missing
# libGLX.so.0; over-reading it blocked a working set. So the layer asserts
# STATE: dpkg-query Status == "install ok installed" for all 8 packages.
# The only retained log rule targets the one phrase that means genuinely-
# missing — "is not installed" — allowlisting libglx-mesa0 (the deliberate,
# justified skip above).
# ldd GUARD: after install, ldd over the system libs AND the OCP wheel's
# TK libraries must show zero "not found" — a dynamic re-proof of the
# static audit, at build time.
# POSITION IS DELIBERATE: after the pip layers, so system-package edits
# never invalidate the ~400 MB of cached downloads (needed at import time,
# not install time).
RUN python -c "import urllib.request, pathlib; base='http://deb.debian.org/debian/pool/main/'; pkgs=['libg/libglvnd/libgl1_1.7.0-1+b2_amd64.deb','libg/libglvnd/libglvnd0_1.7.0-1+b2_amd64.deb','libg/libglvnd/libglx0_1.7.0-1+b2_amd64.deb','libx/libx11/libx11-6_1.8.12-1_amd64.deb','libx/libx11/libx11-data_1.8.12-1_all.deb','libx/libxcb/libxcb1_1.17.0-2+b1_amd64.deb','libx/libxau/libxau6_1.0.11-1_amd64.deb','libx/libxdmcp/libxdmcp6_1.1.5-1_amd64.deb']; d=pathlib.Path('/tmp/gl'); d.mkdir(); [urllib.request.urlretrieve(base+p, d/p.split('/')[-1]) for p in pkgs]; print('GL-LAYER: downloaded', len(pkgs), 'debs,', sum(f.stat().st_size for f in d.glob('*.deb')), 'bytes')" \
    && cd /tmp/gl \
    && echo "87fa2f6e5abaed4ed385fac879c8dd735af719ee2300222d901793c66e041678  libgl1_1.7.0-1+b2_amd64.deb" > sums.txt \
    && echo "887f74008166549ce9e100c906aa937e95d6e5ce1c8d86efe8c95fd953359b9c  libglvnd0_1.7.0-1+b2_amd64.deb" >> sums.txt \
    && echo "2721fdca0fe3bd963cb39482eabc253af52b88f4a7f6dbb69e475549daf5af3b  libglx0_1.7.0-1+b2_amd64.deb" >> sums.txt \
    && echo "b5a3fd3bf8c8fd0364bfb9bea00dcba7fc301229bd02dded084632d31f5b0fb3  libx11-6_1.8.12-1_amd64.deb" >> sums.txt \
    && echo "c54f87069888f80ba4da586da6147d74c7598ccdd8b90906dbc4271fa414c738  libx11-data_1.8.12-1_all.deb" >> sums.txt \
    && echo "5c222a72d11b866447da31693254f738430726e3e065a384e82687b2fd2f978b  libxcb1_1.17.0-2+b1_amd64.deb" >> sums.txt \
    && echo "689a9f0e0ba3e2c65431f864871e303ee904de69dd28abfc462663fae030227f  libxau6_1.0.11-1_amd64.deb" >> sums.txt \
    && echo "0740dc760916b2008b45417a42a8fd7dd5de370fb57d31373f15034cda8acf0b  libxdmcp6_1.1.5-1_amd64.deb" >> sums.txt \
    && sha256sum -c sums.txt \
    && (dpkg --force-depends -i ./*.deb > dpkg.log 2>&1; rc=$?; cat dpkg.log; test $rc -eq 0) \
    && ! grep 'is not installed' dpkg.log | grep -v 'libglx-mesa0' \
    && for p in libgl1 libglvnd0 libglx0 libx11-6 libx11-data libxcb1 libxau6 libxdmcp6; do test "$(dpkg-query -W -f='${Status}' $p)" = "install ok installed" || { echo "GL-LAYER STATE FAIL: $p is not installed-ok"; exit 1; }; done \
    && ls /usr/local/lib/python3.11/site-packages/cadquery_ocp_novtk.libs/libTK*.so* > /dev/null \
    && ! ldd /usr/lib/x86_64-linux-gnu/libGL.so.1 /usr/lib/x86_64-linux-gnu/libGLX.so.0 /usr/lib/x86_64-linux-gnu/libX11.so.6 /usr/local/lib/python3.11/site-packages/cadquery_ocp_novtk.libs/libTK*.so* | grep 'not found' \
    && cd / && rm -rf /tmp/gl

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
