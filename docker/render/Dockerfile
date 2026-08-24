# Dockerfile — render worker (Phase 9B)
#
# ==========================================================================
# WHY THIS IS A SEPARATE IMAGE, NOT A LAYER ON THE BACKEND
# ==========================================================================
# The backend image carries the OCCT / build123d stack that cost repeated
# multi-hour rebuilds on a ~320 kB/s link (ADR-017/018). Two rules follow:
#
#   1. Blender must NEVER be added to Dockerfile (the backend). A RUN above
#      the OCCT layer invalidates it on every touch.
#   2. This image must NOT be `FROM luxuryform-backend` either. The backend
#      image is rebuilt constantly during development; basing on it would
#      invalidate the 360 MB Blender layer every single time.
#
# So it bases on python:3.11-slim-trixie — the same base the backend uses,
# already in the local cache, and never rebuilt. The Blender layer then only
# invalidates when the pinned Blender version changes.
#
# ==========================================================================
# THE TARBALL IS FETCHED ON THE HOST, NOT HERE
# ==========================================================================
# `scripts/fetch_blender.sh` downloads it with `curl -C -` so a dropped
# connection RESUMES instead of restarting 360 MB. A `RUN curl` inside the
# build cannot resume across a failed build — the layer is discarded — which
# on this connection is the difference between minutes and an evening.
#
# The build context is this directory alone (docker-compose sets
# `context: ./docker/render`), so the tarball is never shipped as context to
# the backend or frontend builds.
#
# Blender 4.5.12 LTS. Version, URL and sha256 taken from the official
# release index and blender.org/download/lts, FETCHED 2026-08-22 (ADR-009 —
# never from recall). 4.2 LTS was rejected: blender.org lists it under
# "Previous LTS Releases" as of that date, i.e. no longer maintained.

FROM python:3.11-slim-trixie

# ---------------------------------------------------------------------------
# System libraries Blender links at startup, even with -b (headless).
#
# Same sha256-pinned snapshot pattern as the backend (ADR-017): the mirror is
# PURE TRANSPORT — one wrong byte fails the build loudly at `sha256sum -c`
# rather than producing a subtly broken image. Pins recorded 2026-08-22.
#
# The set was determined EMPIRICALLY (run blender, read what ldd reports
# missing), not from a documentation list that may be stale.
# ---------------------------------------------------------------------------
ARG DEB_POOL_URL=https://snapshot.debian.org/archive/debian/20260803T082142Z/pool/main/

COPY debs.txt sums.txt /tmp/gl/
RUN cd /tmp/gl \
    && python -c "import urllib.request, pathlib, os, sys; \
base=os.environ['DEB_POOL_URL'].rstrip('/')+'/'; \
pkgs=[l.strip() for l in open('debs.txt') if l.strip() and not l.startswith('#')]; \
[(print('DEB:', base+p, flush=True), urllib.request.urlretrieve(base+p, p.split('/')[-1])) for p in pkgs]; \
print('downloaded', len(pkgs), 'debs')" \
    && sha256sum -c sums.txt \
    && dpkg -i --force-depends *.deb \
    && rm -rf /tmp/gl /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Blender itself. Extract and delete the tarball in ONE layer so the 360 MB
# archive never lands in the image.
#
# Extraction goes through extract_blender.py, not `tar -xJf`: this base image
# ships GNU tar but no `xz` binary, and tar shells out to xz for .tar.xz.
# Python's stdlib lzma is already present, so the deb list stays at exactly
# the set the RENDERER needs and gains nothing carried only for build time.
#
# Stripped after extraction:
#   datafiles/locale  — UI translations; a headless renderer has no UI.
# Nothing else is removed: the addons and scripts trees are what `-b` loads,
# and trimming them to save disk is how a renderer breaks six months later.
# ---------------------------------------------------------------------------
ARG BLENDER_VERSION=4.5.12
ARG BLENDER_SHA256=95e3a2dfedba3bd32ca54fc355eac6b15a11986954ccb02815a07535d0120a25

COPY blender-${BLENDER_VERSION}-linux-x64.tar.xz /tmp/blender.tar.xz
COPY extract_blender.py /tmp/extract_blender.py
RUN echo "${BLENDER_SHA256}  /tmp/blender.tar.xz" | sha256sum -c - \
    && python /tmp/extract_blender.py /tmp/blender.tar.xz /opt/blender \
    && rm -f /tmp/blender.tar.xz /tmp/extract_blender.py \
    && rm -rf /opt/blender/${BLENDER_VERSION%.*}/datafiles/locale \
    && ln -s /opt/blender/blender /usr/local/bin/blender \
    && blender --version

# The worker itself: stdlib + the render script. No pip install, so this
# image needs nothing from PyPI and cannot be broken by an index outage.
COPY render_worker.py /app/render_worker.py
COPY render_scene.py /app/render_scene.py

# ADR-005 shape, reused: the worker runs non-root with no network and a
# read-only filesystem except the scratch mount. Blender is not AI-written
# code, so ADR-005 does not strictly compel this — it is reused because the
# pattern is proven here and a render job has no business reaching the
# network.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin render \
    && mkdir -p /scratch && chown render:render /scratch

ENV LUXURYFORM_RENDER_SCRATCH=/scratch \
    BLENDER_BIN=/usr/local/bin/blender \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
USER render
CMD ["python", "/app/render_worker.py", "/scratch"]
