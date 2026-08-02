# LuxuryForm Studio v1 — frontend image (React + Vite + three.js viewport)
# ADR-013: node_modules is installed at IMAGE BUILD time, in cache-protected
# layers — the same treatment as the Python side. Previously `npm ci` ran at
# every container start over the operator's unreliable connection with no
# layer caching; a killed npm ("Exit handler never called", 2026-08-02) left
# node_modules without vite and the container in a restart loop.
# ADR-015: npm 10.8.2 itself is buggy (zero-exit crash) — see layer 0.
FROM node:20-bookworm-slim

WORKDIR /app

# npm resilience on unreliable connections. Config keys verified DIRECTLY
# on npm 10.8.2 — the version bundled in this image (operator's build log,
# 2026-08-02) — via `npm config ls -l` and an env-var round-trip test, and
# re-verified on npm 11.19.0 (ADR-009/ADR-014/ADR-015).
ENV NPM_CONFIG_FETCH_RETRIES=5 \
    NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=15000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000 \
    NPM_CONFIG_FETCH_TIMEOUT=600000

# Layer 0: npm itself (ADR-015). The bundled npm 10.8.2 contains the UNFIXED
# zero-exit crash: on a long network stall it prints "npm error Exit handler
# never called!" and exits 0 — the build layer then lies DONE with an
# incomplete node_modules (operator build log 2026-08-02; driehle's repro on
# node:20-slim, npm/cli#8931). Evidence from the live npm/cli tracker
# (2026-08-02): the exit-code bug was fixed in npm/cli#7674 ("always set
# exit code if exiting uncleanly", merged 2024-07-29 — AFTER 10.8.2's
# release), signal handling improved in npm/cli#8429; the underlying crash
# class is NOT fixed anywhere (still open on npm 11.6.2/11.8.0, #8766/#9728;
# npm 12.0.2 exists but requires node ^22.22.2 — incompatible with this
# node-20 image; live npm registry, 2026-08-02). So this upgrade buys an
# HONEST exit code, not a cure — the verification in layer 2 is the actual
# guarantee. npm@11.19.0 = newest whose engines accept node 20
# (^20.17.0 || >=22.9.0, live registry 2026-08-02). The version assertion
# keeps this layer honest too.
RUN npm install -g --no-audit --no-fund npm@11.19.0 \
    && npm --version | grep -q '^11.19.0$'

# Layer 1: dependency manifests ONLY — layers 1-2 rebuild exclusively when
# the lockfile changes, never when source changes.
COPY package.json package-lock.json ./

# Layer 2: npm ci, bounded retry, same-RUN verification (ADR-013/015).
# The BuildKit cache mount persists downloaded tarballs ACROSS builds, so a
# connection drop mid-ci costs seconds on retry. (Tracker evidence says the
# exit-handler bug occurs WITHOUT cache mounts too — driehle's repro has
# none — so the mount is not implicated; to isolate it anyway, delete the
# --mount line once and rebuild.)
# Verification, in the SAME RUN so a zero-exit npm crash can never mark the
# layer DONE (operator constraint, 2026-08-02):
#   - bounded retry absorbs transient stalls (each retry reuses the cache)
#   - `test -n "$ok"` catches three nonzero failures
#   - `npm ls --depth=0` catches a PARTIAL tree (zero-exit crash mid-reify)
#   - `test -x .../vite && vite --version` catches the zero-exit lie
# Both failure modes exercised against a fake crashing npm (2026-08-02).
RUN --mount=type=cache,target=/root/.npm \
    ok=""; \
    for attempt in 1 2 3; do \
      echo "npm ci attempt $attempt of 3"; \
      npm ci --no-audit --no-fund && { ok=1; break; }; \
      echo "npm ci attempt $attempt exited nonzero — retrying in 20s"; \
      sleep 20; \
    done; \
    test -n "$ok"; \
    npm ls --depth=0 > /dev/null; \
    test -x node_modules/.bin/vite && node_modules/.bin/vite --version

# Layer 3: application source. node_modules/dist on the host are excluded
# via .dockerignore so a stale host copy can never shadow layer 2's.
COPY . .

EXPOSE 5173

# package.json dev script is plain "vite"; the host binding is passed here
# so the dev server is reachable outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
