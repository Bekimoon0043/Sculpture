# LuxuryForm Studio v1 — frontend image (React + Vite + three.js viewport)
# ADR-013: node_modules is installed at IMAGE BUILD time, in cache-protected
# layers — the same treatment as the Python side. Previously `npm ci` ran at
# every container start over the operator's unreliable connection with no
# layer caching; a killed npm ("Exit handler never called", 2026-08-02) left
# node_modules without vite and the container in a restart loop.
FROM node:20-bookworm-slim

WORKDIR /app

# npm resilience on unreliable connections. Config keys verified against
# `npm config ls -l` (npm 11.18.0, 2026-08-02, ADR-009); the names are
# stable since npm 8, so the npm 10.x bundled in node:20-bookworm-slim
# accepts them. --no-audit/--no-fund skip extra registry round-trips that
# only add failure surface.
ENV NPM_CONFIG_FETCH_RETRIES=5 \
    NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=15000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000 \
    NPM_CONFIG_FETCH_TIMEOUT=600000

# Layer 1: dependency manifests ONLY — layers 1-2 rebuild exclusively when
# the lockfile changes, never when source changes.
COPY package.json package-lock.json ./

# Layer 2: npm ci. The BuildKit cache mount persists downloaded tarballs
# ACROSS builds, so a connection drop mid-ci costs seconds on retry, not a
# full re-download. Measured: 64 packages, 31 MB of tarballs, 120 MB
# node_modules, peak RSS 427 MB cold-cache (2026-08-02) — fits a 4 GB
# Docker cap with ~9x headroom.
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

# Layer 3: build-time check — the dev server executable must exist NOW.
# A frontend image that cannot start its own dev server fails the BUILD,
# not at runtime in a restart loop (mirrors the backend kernel smoke test).
RUN test -x node_modules/.bin/vite && node_modules/.bin/vite --version

# Layer 4: application source. node_modules/dist on the host are excluded
# via .dockerignore so a stale host copy can never shadow layer 2's.
COPY . .

EXPOSE 5173

# package.json dev script is plain "vite"; the host binding is passed here
# so the dev server is reachable outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
