# DECISIONS.md — Architecture Decision Records, LuxuryForm Studio v1

One entry per significant technical choice. Newest decisions are appended;
decisions are never silently edited (a superseded ADR says so in place).

---

## ADR-001 — SQLite in WAL mode as the platform database

**Status: accepted (Phase 1).**

SQLite with `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON`, one file
at `data/luxuryform.db` (override with `LUXURYFORM_DB`).

**Why:** the platform is local-first and operated by a non-programmer. SQLite
is crash-safe in WAL mode, needs no server, no admin, and backups are "copy
one file". A single writer at a time is sufficient: the job runner serializes
heavy work by design.

**Full schema created up front.** Per the approved plan (§D3), every table —
including later-phase tables (`projects`, `council_sessions`, `design_specs`,
`designs`, `validation_reports`, `critique_rounds`, `designdna`, `exports`) —
is created in `db/schema.sql` NOW, with minimal-but-real columns, so no table
is ever retrofitted mid-flight. Phase 1 code only reads/writes the Phase 1
tables (`sessions`, `ai_calls`, `budget_events`, `jobs`); ORM models for
later tables arrive with the phase that populates them.

---

## ADR-002 — Official provider SDKs; Kimi via Moonshot's OpenAI-compatible endpoint

**Status: accepted (Phase 1).**

Anthropic and OpenAI are called through their official Python SDKs
(`anthropic`, `openai`), each with a 60-second timeout. Kimi (Moonshot AI) is
called through the official `openai` SDK pointed at
`base_url=https://api.moonshot.cn/v1` with `MOONSHOT_API_KEY`, because
Moonshot's API is OpenAI-compatible. One provider interface
(`app/ai/provider.py`) covers all three; every call routes through
`app/ai/call_log.py`. Token counts are always read from the API response's
`usage` object — real numbers, never estimates. If Kimi's vision endpoint
rejects a call, the raw error is surfaced verbatim (Amendment 5) rather than
hidden or silently retried elsewhere.

---

## ADR-003 — Spend caps live in the provider layer (Amendment 2)

**Status: accepted (Phase 1).**

Hard ceilings — `session_cap_usd: $5.00`, `day_cap_usd: $25.00`,
`max_vision_iterations: 6` — are enforced by `core/budget.py` BEFORE any API
call is dispatched, inside the single logged dispatch path
(`ai/call_log.py`). Spend is derived from the `ai_calls` table (single source
of truth), money math is rounded to 6 decimal places, and the day boundary is
the UTC calendar day. On breach (`on_breach: halt_and_report`): the run
halts, a `budget_events` row and a `jobs` row (`status='halted_budget'` with
persisted state JSON) are written, and the reason is reported. The system
never silently continues. `max_vision_iterations` is validated from
`config/budget.yaml` now and enforced when the critique loop is built in
Phase 5. The Phase 1 gate PROVES a cap stops a run, offline, in its section 4.

---

## ADR-004 — The determinism boundary is the Design Spec (Amendment 1)

**Status: accepted (Phase 1).**

Restated verbatim, this is the platform's guarantee:

"Identical Design Spec + identical seed + pinned Docker image = byte-identical
canonical geometry (STEP + parameter set). Brief → Spec is non-deterministic
by nature; every Spec is therefore persisted permanently as the reproducible
unit of record."

Consequences: seeds are centralized (`core/seeds.py`), the Design Spec schema
carries `meta.seed` and an optional `meta.spec_hash`, and no gate ever tests
brief-level reproducibility. (This supersedes objection 5b in the First
Action document; renders remain reproducible within visual tolerance, never
byte-identical — see LIMITATIONS.md.)

---

## ADR-005 — Sandbox isolation level for AI-written geometry code (Amendment 6)

**Status: accepted (Phase 1) — recorded now, built in Phase 4.**

In Phase 4 the GEOMETRIST's generated build123d/CadQuery code will execute
only inside a sandbox with ALL of the following:

- a **separate container** (not the backend container),
- running as a **non-root user**,
- with **no network access**,
- a **read-only filesystem except one scratch mount** for build artifacts,
- explicit **CPU and memory limits**, and
- a **hard wall-clock timeout** after which the sandbox is killed.

Recording the level now fixes the security posture before any AI-written code
ever runs; the Phase 4 gate must demonstrate each property.

---

## ADR-006 — Versioned pricing with effective dates

**Status: accepted (Phase 1).**

`config/pricing.yaml` carries `pricing_version` (currently `2026-07-v1`) and
an `effective_date` per model. Every logged AI call records which pricing
version computed its cost, so a price change never silently rewrites history:
when a provider changes prices the operator updates the file and bumps the
version. A model with no price entry is a hard error — the platform refuses
to guess a price. The file's header instructs the operator to verify prices
against the providers' live price pages before trusting cost figures.

---

## ADR-007 — Bounded vision deltas + two-provider consensus (Phase 5)

**Status: accepted (Phase 1) — recorded now, built in Phase 5.**

The vision critique loop will convert model feedback into parameter deltas,
never prose: each delta must reference a registered primitive parameter path
(e.g. `cascade_01.tier_height_m`), carry a magnitude limit, and require
**two-provider vision consensus** (Anthropic + OpenAI in parallel, Kimi as
fallback) before it is accepted; the Arbiter validates every delta before
re-solve. Anything the vision model says that cannot be expressed as a
bounded delta is recorded as an observation for the operator — not executed.
Loop rounds are hard-capped by `max_vision_iterations` (ADR-003).

---

## ADR-008 — DXF native; ODA File Converter for DWG; no SKP writer

**Status: accepted (Phase 1 ruling 5a).**

- **DXF** is written natively (open-source `ezdxf` covers it fully).
- **DWG** is Autodesk's closed format. We do not write it directly; the
  operator converts DXF → DWG with the free ODA File Converter (one-time
  install, documented in LIMITATIONS.md with exact steps).
- **SKP** (SketchUp) has no working open-source writer, so we do not export
  it. The import path is documented instead: fabricators open our
  STEP/DXF/OBJ directly in SketchUp Pro.

Everything else on the export list (STEP, STL, OBJ, GLB, FBX, USD/USDZ, DAE,
Alembic) is genuinely achievable and arrives with the export phase.

## ADR-009 — No platform fact from training-data recall; live docs only, fetch date recorded

**Status: accepted (Phase 1 correction, operator directive).**

No third-party endpoint, model string, SDK shape, parameter name, or price is
ever written into this codebase from the model's training-data recall. Each is
fetched from the live provider documentation (or verified against the live
API) at the time it is written, and the fetch date and source URL are recorded
next to the value (config comments, docstrings, pricing.yaml sources).

**Why:** this has now caused two real defects in Phase 1 alone:

1. The offline test transports mirrored an *assumed* SDK response shape
   (LIMITATIONS.md §7) — retired only by the live gate run.
2. `kimi_provider.py` hardcoded `https://api.moonshot.cn/v1` from recall; the
   operator's account lives on the global endpoint and the gate returned a
   live 401. The operator verified against the live API:
   `https://api.moonshot.ai/v1` authenticates, and `models.list()` returns
   exactly `kimi-k3, kimi-k2.6, kimi-k2.7-code, kimi-k2.7-code-highspeed` —
   no vision-specific model.

**Applied immediately (2026-08-01):** endpoints moved to
`config/council.yaml`; kimi text+vision model = `kimi-k3` (native image
input); `max_completion_tokens` replaces the deprecated `max_tokens`; kimi-k3
pricing ($3.00 cache-miss input / $15.00 output per 1M) fetched from
`platform.kimi.ai/docs/pricing/chat-k3.md`. Every value carries its source
URL and fetch date.

---

## ADR-010 — Phase 2 geometry stack: build123d kernel, native GLB, trimesh validation, STEP timestamp injection

**Status: accepted (Phase 2, all API facts live-doc sourced 2026-08-01 per ADR-009).**

- **Kernel: build123d 0.11.1** (OpenCASCADE). The tiered-cascade primitive is
  built from solids of revolution (BuildSketch profile in the XZ plane →
  `revolve(..., Axis.Z)`), fused into ONE solid, plumbing bore cut through
  the stack. Watertight BY CONSTRUCTION (Rule 6): no mesh repair anywhere.
- **Lip fillets are drawn INTO the dish profile** as true circular arcs
  (`RadiusArc`), so the revolved lip is an exact toroidal surface — no
  post-hoc 3D `fillet()` call that could fail at parameter extremes. The
  validated ranges in `registry.py` plus hard constraints 3 and 5
  (`lip_fillet_mm < dish_depth_mm/2`, `lip_fillet_mm < basin_wall_mm`)
  guarantee the profile is always drawable.
- **GLB export is build123d's NATIVE `export_gltf(binary=True)`** (live-doc
  signature confirmed 2026-08-01). No trimesh conversion on the export path.
  `linear_deflection` is set to 1.0 mm explicitly: the live-doc default
  0.001 mm would tessellate a 2.6 m fountain into tens of millions of
  triangles and blow the <1M-triangle viewport budget (PHASE2_PLAN §7). STEP
  is the canonical artifact; the GLB is a preview/validation mesh.
- **trimesh (5.0.0) is used for VALIDATION only** — watertight, winding,
  volume, surface area, Euler number, bounds, degenerate faces — with a 2%
  volume cross-check against the exact B-rep volume.
- **STEP determinism (Amendment 1):** the STEP header normally embeds a
  wall-clock timestamp. `export_step(..., *, timestamp=)` (live-doc confirmed
  2026-08-01) lets us inject `datetime(2026,1,1) + timedelta(seconds=seed)`,
  so (spec, seed) → byte-identical STEP. The gate proves this across TWO
  separate processes with both sha256 hashes printed.
- **Schema evolution is honest (SPEC_PHASE2 §2):** a `schema_migrations`
  table records the version; a Phase 1 database file is RENAMED to
  `<name>.phase1-backup.db` on startup (never deleted) and a fresh v2 schema
  is created, because SQLite cannot alter the `designs.spec_id` foreign key
  in place and Phase 2 builds have no council Design Spec yet.
- **[ADD-1] `.gitattributes`** pins LF for text and marks STEP/GLB/etc.
  binary — Windows CRLF conversion at checkout would corrupt the STEP sha256
  determinism proof.
- **[ADD-2] The Phase 2 gate is split:** `scripts/gate_phase2_auto.py`
  (non-interactive, exit 0/1) + `docs/operator/gate_phase2_visual.md`
  (operator eye-check including the [ADD-5] rebuild-time measurement).

## ADR-011 — Layered Docker installs, explicit heavy-transitive pins, operator-selectable package index

**Status: accepted (2026-08-02, in response to the operator's mirror test and two failed builds from Addis Ababa).**

- **Context.** The operator's line sustains ~320 kB/s from PyPI. The Phase 2
  dependency set (~450 MB, dominated by the ~300 MB cadquery-ocp-novtk
  wheel) ran as ONE pip transaction; a single drop lost everything. The
  build failed twice at ~21 minutes.
- **Layered installs.** The Dockerfile installs dependencies in separate
  RUN layers, heaviest and most stable first: (1) cadquery-ocp-novtk,
  (2) numpy/scipy/scikit-learn, (3) build123d/trimesh, (4) Phase 1 deps,
  (5) the app itself with `--no-deps`. Docker's layer cache protects
  completed layers, so a dropped connection costs one layer, not the build.
- **Explicit heavy-transitive pins.** cadquery-ocp-novtk, numpy, scipy and
  scikit-learn are hard requirements of build123d 0.11.1 (live PyPI
  metadata, 2026-08-02), previously resolved unpinned at build time. They
  are now pinned in pyproject.toml (7.9.3.1.1 / 2.4.6 / 1.17.1 / 1.9.0),
  so builds are reproducible across dates. `tests/test_docker_pins.py`
  enforces that Dockerfile layer pins and pyproject pins stay identical.
- **scipy / scikit-learn cannot be dropped.** They are upstream HARD
  requirements, not extras and not ours (we import neither). Source-verified
  in the build123d 0.11.1 wheel (2026-08-02): scipy is used in core
  topology (`scipy.optimize.minimize/minimize_scalar`,
  `scipy.spatial.ConvexHull/Voronoi` in `topology/one_d.py`,
  `objects_curve.py`, `objects_part.py`, `operations_sketch.py`);
  scikit-learn only in `brep_from_stl.py` (`DBSCAN`, STL→B-rep
  reconstruction — a path we never call). Dropping them means dropping
  build123d, which ADR-010 settled.
- **PIP_INDEX_URL build arg** (default `https://pypi.org/simple`), exposed
  through docker-compose.yml, lets the operator point elsewhere without
  editing the Dockerfile.
- **No mirror is recommended in operator docs.** The operator's live test
  (Addis Ababa, 2026-08-02): the Tsinghua TUNA mirror returned "from
  versions: none" for numpy==2.4.6 after 124 s, while pypi.org succeeded at
  ~320 kB/s. A sandbox-side observation (TUNA fast from the build sandbox)
  did NOT transfer to the operator's location — mirror reachability and
  coverage are location- and version-specific. (Note: TUNA's own simple
  index listed numpy 2.4.6 when re-checked from the sandbox the same day —
  likely sync lag or a stale edge. Either way, the operator's result
  stands: default index is pypi.org.)
- **Open question for Phase 5: prebuilt image via registry** (pull instead
  of build — pulls resume at layer granularity; pip transactions do not).
  Recommendation delivered to the operator 2026-08-02; implementation
  deferred until they rule on it. Phase 5 adds Blender, making local builds
  still heavier.

## ADR-012 — System GL/X11 libraries for OCCT, apt layer position, build-time kernel smoke test

**Status: accepted (2026-08-02, in response to the operator's backend crash: `ImportError: libGL.so.1` in a restart loop — the pinned image had a real gap the build sandbox masked).**

**Distro scope (added 2026-08-02, see ADR-014):** this entry's package facts were verified against **bookworm**; the backend image turned out to resolve to **trixie**, so its apt package set is SUPERSEDED by ADR-014 (minimal mesa-free set). The .so audit method, the layer-position constraint, and the build-time smoke-test contract stand.

- **Root cause.** `python:3.11-slim` (Debian bookworm) ships no OpenGL/X11
  stack, but the cadquery-ocp-novtk wheel's OCCT toolkit libraries link
  `libGL.so.1` and `libX11.so.6` even fully headless. The build sandbox had
  these preinstalled, so every sandbox verification passed while the
  operator's clean image crashed at `import OCP`.
- **The audit (ADR-009-compliant, not recall).** Every `.so` in the
  cadquery-ocp-novtk 7.9.3.1.1 wheel was inspected with `readelf -d`:
  69 files, 11 external sonames. Only TWO are absent from the slim image:
  `libGL.so.1` (proven by the operator's crash) and `libX11.so.6`
  (needed by `libTKOpenGl` and `libTKService`; no X11 exists in slim).
  The wheel bundles its own gomp/fontconfig/freetype/freeimage/uuid.
  Everything else (`libc`, `libm`, `libdl`, `libpthread`, `libgcc_s`,
  `libstdc++`, `libz`, `libexpat`) is present — loader-order evidence:
  `OCP.OCP.so` directly NEEDs `libstdc++.so.6`/`libgcc_s.so.1`, and the
  loader reached `libGL.so.1`, which sits deeper in the dependency order.
- **Packages (live bookworm main index, fetched 2026-08-02).** Install
  `libgl1 libglx-mesa0 libx11-6` with `--no-install-recommends` and
  `rm -rf /var/lib/apt/lists/*` in the same RUN. Operator correction
  recorded: `libgl1-mesa-glx` in bookworm is a *transitional dummy
  package* (33 KB, Depends: libgl1, libglx-mesa0) — not literally removed
  from the index, but equally not the real library. The operator's
  directive to use `libgl1` + `libglx-mesa0` was correct and stands.
- **Layer position is a hard constraint (operator, 2026-08-02).** The apt
  RUN sits AFTER the four pip layers and BEFORE `COPY pyproject.toml`:
  editing system packages must never invalidate the ~400 MB of cached pip
  downloads on the operator's 320 kB/s line. libGL is needed at import
  time, not install time, so the late position is technically sound.
- **Build-time smoke test.** A `RUN python -c "import build123d; ...Box..."`
  layer imports the kernel and builds a trivial solid (volume asserted)
  during the image build. A backend that cannot import its own kernel now
  fails the BUILD, not at runtime in a restart loop.
- **Regression-proofed.** `tests/test_docker_pins.py` now also asserts:
  the three package names in the apt line, `libgl1-mesa-glx` absent,
  `--no-install-recommends`, lists cleanup, apt-layer position between the
  last pip layer and the first COPY, and smoke-test existence/position.
  74/74 tests pass (2026-08-02).
- **Determinism note.** The canonical STEP sha256 (`e1a59fa6…`) is
  unaffected: no Python dependency changed. The cross-environment hash
  comparison is still pending the operator's successful rebuild.

## ADR-013 — Frontend node_modules at image build time, layered, with build-time vite check

**Status: accepted (2026-08-02, in response to the operator's frontend failure: `npm error Exit handler never called` → `vite: not found` at container start, repeated across attempts; both containers down).**

- **Root cause.** The frontend service ran `npm ci` at CONTAINER START via
  `sh -c "npm ci && npm run dev"` with the source bind-mounted — no layer
  caching, no protection. A killed npm (the operator's connection drops;
  "Exit handler never called" is npm's own failure mode when its process
  dies mid-install) left a partial node_modules with no vite binary, and
  the container restart-looped. The same class of mistake ADR-011 fixed on
  the Python side, still present on the JavaScript side.
- **Memory is NOT the constraint (measured, not assumed).** A cold-cache
  `npm ci` of the 64-package lockfile peaked at **427 MB RSS total**
  (node 20.20.2 / npm 11.18.0, 2026-08-02) — ~10% of the operator's 4 GB
  Docker cap. No cap increase needed. The kill was network, not OOM.
- **frontend/Dockerfile (new).** `node:20-bookworm-slim`; npm resilience
  config via env (`NPM_CONFIG_FETCH_RETRIES=5`, retry min/max timeouts
  15 s/120 s, fetch timeout 600 s — keys verified DIRECTLY on npm 10.8.2,
  the image's npm version, via `npm config ls -l` + env round-trip test;
  see ADR-014); layers:
  (1) package.json + package-lock.json, (2) `npm ci --no-audit --no-fund`
  behind a BuildKit cache mount (`--mount=type=cache,target=/root/.npm`)
  so tarballs survive FAILED builds and retries resume instead of
  restarting, (3) build-time check `test -x node_modules/.bin/vite &&
  vite --version` — an image that cannot start its dev server fails the
  BUILD, (4) source last. CMD passes `--host 0.0.0.0` (the operator's
  earlier host-binding concern was retracted; binding is now explicit in
  the image).
- **frontend/.dockerignore (new).** `node_modules/` and `dist/` — a
  corrupt host-side node_modules (left by the old start-time installs)
  must never be COPYed over the image's good one. Operator doc instructs
  one-time deletion of `frontend\node_modules`.
- **docker-compose.yml.** The frontend service now `build: ./frontend`;
  the bind mount and the start-time `npm ci` command are gone.
- **Regression-proofed.** `tests/test_frontend_image.py` (5 tests) locks:
  layer order, flags, retry config, vite check position, .dockerignore,
  and the compose service shape. 79/79 tests pass (2026-08-02).

## ADR-014 — Distro pinning and per-distro facts; minimal mesa-free GL set; npm 10.8.2 verification

**Status: accepted (2026-08-02, in response to three operator corrections: apt-layer OOM at libllvm19; the two images run DIFFERENT Debian releases; npm config evidence must cover 10.8.2 specifically).**

- **Distro facts are per-image from now on.** Backend:
  `python:3.11-slim-trixie` — **trixie** (Debian 13). Frontend:
  `node:20-bookworm-slim` — **bookworm** (Debian 12). The floating
  `python:3.11-slim` tag silently moved bookworm → trixie, which made the
  bookworm-scoped verification in ADR-012 inapplicable to the backend
  (operator's apt output proved trixie: `libllvm19` exists only in the
  trixie main index — bookworm has libllvm15; verified 2026-08-02). The
  backend base tag is now suite-pinned, removing the drift class. Every
  ADR fact that is distro-specific names its distro.
- **The apt-layer OOM — the package set WAS the fix (operator right).**
  On trixie, `apt-get install libgl1` hard-pulls libglx0 → libglx-mesa0 →
  mesa-libgallium + libgl1-mesa-dri → **libllvm19**: 49 packages, 53.5 MB
  download, ~222 MB installed (libllvm19 alone 123.7 MB installed).
  Computed from the live trixie main index, 2026-08-02. None of it is
  needed: the kernel never creates a GL context (headless STEP/GLB
  export); the loader only needs `libGL.so.1` + `libX11.so.6` resolvable.
- **Minimal set (7 packages, 1.5 MB download):** `libgl1 libglvnd0
  libx11-6 libx11-data libxcb1 libxau6 libxdmcp6`, installed via
  `apt-get download` + `dpkg --force-depends -i` in a scratch dir. File
  contents verified by listing the trixie debs themselves: libgl1 ships
  `/usr/lib/x86_64-linux-gnu/libGL.so.1`, libglvnd0 ships
  `libGLdispatch.so.0` (2026-08-02). `--force-depends` skips libgl1's
  package-level hard dep on libglx0 — a GLX-functionality dependency, not
  a link dependency (libGL.so.1 NEEDs only libGLdispatch/libdl/libc).
  Recorded tradeoff: dpkg's database shows an unmet dependency afterwards;
  irrelevant in a purpose-built image and a small price for −220 MB.
- **Smoke test extended to the export paths.** The build-time smoke layer
  now also runs `export_step` and `export_gltf(binary=True)` and checks
  the outputs (size + glTF magic) — direct proof, at every build, that the
  minimal GL set suffices for every code path the app uses.
- **npm config keys verified on 10.8.2 specifically (frontend image's
  npm).** npm 10.8.2 was installed in the sandbox and interrogated:
  `npm config ls -l` lists `fetch-retries` (default 2),
  `fetch-retry-mintimeout` (10000), `fetch-retry-maxtimeout` (60000),
  `fetch-timeout` (300000); an env round-trip
  (`NPM_CONFIG_FETCH_RETRIES=5 NPM_CONFIG_FETCH_TIMEOUT=600000 ...` →
  `npm config get`) returned the set values verbatim. The frontend
  Dockerfile comment now cites 10.8.2, not "stable since npm 8".
- **Corrections to earlier ADR entries:** ADR-012's package facts were
  verified against **bookworm** — they apply to the *frontend* image's
  distro, and are superseded for the backend by this ADR (notably: on
  **trixie**, `libgl1-mesa-glx` is genuinely ABSENT from the index, as the
  operator originally said; on **bookworm** it exists as a transitional
  dummy). ADR-013's npm claims are now backed by direct 10.8.2
  verification; its npm-ci memory measurement (427 MB) was taken under
  npm 11.18.0 and remains valid for the 4 GB question by a ~9x margin.
- **Regression-proofed:** tests assert the suite-pinned FROM line, the
  exact minimal package set, the banned mesa/llvm packages, the
  force-depends install, layer position, and the extended smoke test.
  80/80 tests pass (2026-08-02).

## ADR-015 — npm 10.8.2 zero-exit crash: honest-exit upgrade, same-RUN verification, bounded retry

**Status: accepted (2026-08-02, in response to the operator's frontend build: `npm error Exit handler never called!` at 534.8s followed by `#12 DONE 534.9s` — npm crashed AND exited 0, so the layer lied about success; only the vite check caught it).**

- **Tracker evidence (live npm/cli via GitHub API, 2026-08-02 — not
  recall).** "Exit handler never called" is a catch-all crash class with
  202 tracker hits, reproduced on node 20/22/23/24/25, alpine AND slim
  images, npm ci AND npm install, package-independent, and still OPEN on
  npm 11.6.2 (#8766) and 11.8.0 (#9728). Maintainers close duplicates
  pointing at the "can arise for a number of reasons" wiki — there is no
  fixed-in version for the crash itself. driehle's repro on `node:20-slim`
  (#8931) matches the operator's symptom exactly, including the layer
  marking DONE after the error.
- **The exit-code lie IS fixed — after 10.8.2.** npm/cli#7674 ("fix:
  always set exit code if exiting uncleanly") merged 2024-07-29; npm
  10.8.2 released 2024-07-10. The image's bundled npm predates the fix.
  Signal handling improved further in npm/cli#8429 (merged 2025-07-15).
- **Decision: upgrade npm inside the image to npm@11.19.0** — the newest
  release whose engines accept node 20 (`^20.17.0 || >=22.9.0`; npm 12.0.2
  requires `^22.22.2 || ^24.15.0 || >=26.0.0` — incompatible with
  node:20-bookworm-slim; live npm registry, 2026-08-02). This buys an
  HONEST exit code, not a cure. The upgrade layer self-verifies
  (`npm --version | grep -q '^11.19.0$'`) because it runs on the buggy
  10.8.2 and could itself zero-exit crash.
- **Rejected alternatives, with evidence.** Moving to node:22 — the crash
  is reported on 22/23/24/25 images; churn without benefit. `npm install`
  instead of `npm ci` — both crash (#8974, #8766); ci keeps lockfile
  fidelity. The BuildKit cache mount — NOT implicated: driehle's
  exact-symptom repro uses no mount and the bug class predates BuildKit
  mounts by years; kept because it makes retries cheap. Isolation toggle
  for the operator: delete the `--mount=type=cache,target=/root/.npm \`
  line once and rebuild — documented in the Dockerfile comment.
- **The actual guarantee is verification in the SAME RUN** (operator
  constraint: "a layer that lies about success is worse than one that
  fails"). The npm ci layer now: retries up to 3 times on nonzero exit
  (each retry reuses the cached tarballs), then `test -n "$ok"` (three
  strikes), `npm ls --depth=0` (catches a PARTIAL tree from a zero-exit
  crash mid-reify — vite can exist while siblings are missing), and
  `test -x node_modules/.bin/vite && vite --version` (catches the lie).
  Both failure modes were exercised against a fake crashing npm in the
  sandbox: retry-then-succeed passes; zero-exit lie fails the layer.
- **Backend independence.** The frontend build failing in parallel had
  CANCELED the backend's GL layer before it could be tested. The auto gate
  needs only the backend; operator doc now carries the backend-only
  commands (`docker compose build backend` / `up -d backend`), so the
  determinism proof is never again blocked by a frontend defect.
- **Regression-proofed:** tests lock the pinned npm upgrade + self-verify,
  same-RUN retry + `npm ls` + vite checks, flags, layer order. 11/11
  image-structure tests pass (2026-08-02); no runtime code changed.


## ADR-016 — libGLX miss: audit-method correction, 8-package set, pool downloads with sha256 pins, dpkg guard

**Status:** accepted (2026-08-02). **Scope:** backend image, distro TRIXIE.
Supersedes the ADR-014 7-package set and the apt-get download mechanism.

**Incident (operator build log, 2026-08-02):** the build-time smoke test
(ADR-012) caught `ImportError: libGLX.so.0: cannot open shared object file`
— at build, not in a restart loop; the design did its job. But it disproved
the ADR-014 audit, which had shipped a 7-package set without `libglx0` on
the reasoning that "`libgl1`'s dep on `libglx0` is GLX functionality, not a
link dependency — libGL.so.1 NEEDs only libGLdispatch/libdl/libc."

**Root cause of the audit miss — two method failures, both corrected:**

1. **readelf -d alone is insufficient for dlopen/dispatch-resolved
   libraries.** libGL.so.1 resolves libGLX.so.0 through the glvnd dispatch
   layer at RUNTIME, so libGLX.so.0 appears in libGL.so.1's string table,
   not as a DT_NEEDED entry — readelf -d structurally cannot see it
   (operator's diagnosis, confirmed by strings scan of the real trixie
   libGL.so.1.7.0, 2026-08-02). Corrected audit method: readelf -d +
   strings scan of every relevant library for `lib*.so` candidates +
   dpkg-deb content listing + readelf of the EXTRACTED real libraries.
   Applied to the full chain (glvnd libs + the OCP wheel's libTKOpenGl and
   libTKService): no further hidden sonames found — no libEGL, no mesa
   sonames in any strings table.
2. **dpkg's "dependency problems, but configuring anyway" is a FAILURE
   signal, not noise.** The ADR-014 layer's own dpkg output had named the
   exact missing package ("libgl1 depends on libglx0") and it was treated
   as benign. The GL layer now greps its dpkg log and FAILS THE BUILD on
   any "depends on" complaint outside a one-entry allowlist.

**The vendor question (operator's instruction), answered with evidence:**
does `libglx0` require a GLX vendor (`libglx-mesa0`) for the soname to
resolve? NO. readelf of the real trixie `libGLX.so.0.0.0` (extracted from
`libglx0_1.7.0-1+b2_amd64.deb`): NEEDED = libGLdispatch.so.0, libX11.so.6,
libc.so.6 — nothing else. glvnd only dlopens a vendor library when an
application actually creates a GL context; the kernel is headless
(STEP/GLB export) and never creates one. `libglx-mesa0` stays out, and it
is the ONLY dpkg complaint the guard allowlists — with this justification
recorded, not silence.

**The corrected set — reported to the operator BEFORE rebuild:**
8 packages — libgl1 1.7.0-1+b2 (0.09 MB deb / 0.64 MB installed),
libglvnd0 1.7.0-1+b2 (0.05 / 0.72), libglx0 1.7.0-1+b2 (0.03 / 0.16),
libx11-6 2:1.8.12-1 (0.82 / 1.60), libx11-data 2:1.8.12-1 (0.34 / 1.54),
libxcb1 1.17.0-2+b1 (0.14 / 0.29), libxau6 1:1.0.11-1 (0.02 / 0.04),
libxdmcp6 1:1.1.5-1 (0.03 / 0.06). **Total: 8 packages, 1.53 MB download,
5.04 MB installed** (live trixie main index, 2026-08-02). Versus the mesa
chain apt would have pulled: 49 packages / 53.5 MB / ~222 MB installed.
Static self-containment proof: every NEEDED of every .so shipped by the 8
packages resolves within the set + glibc — verified by extracting all 8
debs and resolving the full NEEDED closure (2026-08-02).

**Index-fetch elimination (operator's second instruction):** `apt-get
update` had fetched the full 9.6 MB trixie index at 16 kB/s — 10m26s —
before downloading 1.5 MB of packages, on every cache miss of the layer.
The layer now pulls the 8 debs STRAIGHT from the trixie pool
(`http://deb.debian.org/debian/pool/main/...`, exact pool paths from the
live index) using python (slim ships no curl/wget). No index is fetched at
all. Each deb is pinned by sha256 recorded from the live index AND
re-verified against the actual downloaded bytes (all 8 match, 2026-08-02);
`sha256sum -c` runs before dpkg, so a single flipped byte fails the layer
loudly — strictly stronger integrity than apt's download path. (Note for
the record: a first attempt to transcribe the 8 hashes into this file from
summary notes corrupted the tails — caught instantly by `sha256sum -c`
against the real debs, then regenerated from computed file bytes
cross-checked against the index. The check works; never transcribe hashes
by hand.)

**Build-time guards, in order, all in the same RUN:** (1) sha256sum -c —
integrity; (2) dpkg hard-failure propagation (exit code captured, log
printed, nonzero fails); (3) dpkg-complaint guard — any "depends on" line
not naming libglx-mesa0 fails the build; (4) `ls` glob check that the OCP
wheel's TK libs exist (a silent no-match glob must not skip the next
check); (5) ldd over libGL.so.1, libGLX.so.0, libX11.so.6 AND
`cadquery_ocp_novtk.libs/libTK*.so*` — zero "not found" tolerated, a
dynamic re-proof of the static audit against the very libraries that
failed. Guard logic was exercised in the sandbox on fabricated logs:
allowlisted-only complaint passes, unexpected complaint fails, clean ldd
passes, "not found" fails. Layer 6 (import + BREP + STEP + GLB smoke)
remains as the final end-to-end proof.

**Position unchanged:** after the four pip layers, before the first COPY
(operator constraint, ADR-012) — system-package edits never invalidate the
~400 MB of cached pip downloads.

**Regression-proofed:** tests lock the 8-package set, no-apt-get rule,
8 sha256 pins, sha256sum/dpkg/ldd guards and allowlist, banned-package
absence from the download list, layer position, and smoke-test ordering.

**Guard v2 — check STATE, not complaint text (operator correction,
2026-08-03).** The v1 guard failed the layer on the operator's rebuild
even though all 8 debs installed and configured correctly. Verbatim cause:
dpkg configures `./*.deb` alphabetically, so `libgl1` is configured BEFORE
`libglx0`, and dpkg prints "libgl1:amd64 depends on libglx0 (=
1.7.0-1+b2)." with NO "however: Package ... is not installed" clause — a
configuration-ORDER artifact, not a missing package. The genuinely-missing
case looks different: "libglx0:amd64 depends on libglx-mesa0; however:
Package libglx-mesa0 is not installed." This is the second time dpkg prose
parsing misled in opposite directions: treating it as noise shipped a
missing libGLX.so.0 (this ADR's incident); treating all of it as failure
blocked a working set. The guard is replaced with STATE assertions —
`dpkg-query -W -f='${Status}'` must equal "install ok installed" for all 8
packages (loop prints `GL-LAYER STATE FAIL: <pkg>` and exits 1 otherwise)
— plus the only prose rule that means genuinely-missing: "is not
installed", allowlisting libglx-mesa0 only. The ldd "not found" check
(the real proof) and the Layer 6 smoke test (the end-to-end proof) are
unchanged. Verified against the operator's verbatim build log: the new
rule PASSES it; a mutated log adding "Package libfoo0 is not installed."
FAILS loudly; the state loop passes an all-ii stub and fails loudly naming
the package on a config-files stub.

**Audit v3 — base-image contents VERIFIED, not assumed (operator's ldd
guard, 2026-08-03).** The ldd guard caught a real miss the prose-era
audit had marked "present" by reasoning from python stdlib requirements:
`libexpat.so.1 => not found` (x14) against the OCP libTK*.so libraries.
Root cause of the wrong claim: the original crash's loader-order evidence
only proved the sonames of the libs loaded on THAT import path; the
libexpat consumer was not among them. The consumer is the wheel's BUNDLED
libfontconfig (the only one of the 69 wheel .so files that NEEDs
libexpat.so.1); 14 TK libs chain to it via TKService — hence x14.
libexpat1 was never in the base image: the operator's earlier apt log
listed it among the mesa chain's NEW packages, so it would have arrived
as a side effect of the 49-package chain — trimming to 8 exposed the gap.
**Method upgrade:** every soname the audit marks "present" is now verified
against the ACTUAL base-image contents — the debuerreotype
`rootfs.manifest` for debian:trixie-slim (epoch 1783900800, Debian 13.6,
78 packages, fetched via GitHub API 2026-08-03) plus the
docker-library/python `3.11/slim-trixie/Dockerfile` (runtime adds only
ca-certificates/netbase/tzdata; all build deps purged — consistent with
libexpat1's absence). Manifest-verified providers: libc6 2.41
(libc/libm/libdl/libpthread/librt/ld-linux), libgcc-s1 (libgcc_s.so.1),
libstdc++6 (libstdc++.so.6), zlib1g (libz.so.1) — each additionally
mapped through the live trixie Contents-amd64 index. Full wheel re-audit
(cp311 manylinux_2_31 wheel, all 69 .so): 79 NEEDED sonames, 11 external —
libGL.so.1/libX11.so.6 (pinned debs), libexpat.so.1 (pinned deb, NEW),
the eight glibc-family + libgcc_s/libstdc++/libz sonames (manifest-
verified base). Strings-scan leftovers dispositioned: unmangled copies of
bundled names (auditwheel patched NEEDED — zero dlopen symbols in
fontconfig, benign), libgomp's libnuma/libmemkind (one dlopen symbol —
optional NUMA support, degrades gracefully when absent), glvnd's
libGLX_mesa.so.0 (only dlopened at GL-context creation — never happens
headless). No further hidden sonames. **The corrected set: 9 packages —
libgl1, libglvnd0, libglx0, libx11-6, libx11-data, libxcb1, libxau6,
libxdmcp6, libexpat1 2.7.1-2 (0.10 MB deb / 0.39 MB installed, sha256
f875f566…3344, Pre-Depends libc6 only, verified against the live trixie
index and the actual deb bytes) — 1,635,412 bytes (1.64 MB) download,
5,565 KiB (5.43 MB) installed, reported to the operator BEFORE rebuild.**
The ldd guard stays permanently (operator instruction) and now covers ALL
wheel libs (`cadquery_ocp_novtk.libs/*.so*`, not just libTK*) — direct
coverage of the bundled fontconfig class of consumer. 9-deb closure
proven: every NEEDED of every .so shipped by the set resolves within the
set + manifest-verified libc6.

## ADR-017 — deb.debian.org unreachable on operator route: mirror-ARG (Plan A) and Docker Hub donor multi-stage (Plan B)

**Status:** accepted (2026-08-03). **Scope:** backend image build.

**Incident:** deb.debian.org is connection-RESET on the operator's route —
not slow, actively reset (4 in-container attempts + host curl with 20
retries). Meanwhile PyPI works at 1.5 MB/s and Docker Hub pulls fine.

**Plan A — `DEB_POOL_URL` build ARG (default deb.debian.org).** The pool
base URL in Layer 5 is now operator-overridable without editing the
Dockerfile (`docker compose build --build-arg DEB_POOL_URL=...`, or the
compose env passthrough). The 9 sha256 pins make the mirror PURE
TRANSPORT: any mirror may serve the bytes; one wrong byte fails the build
loudly at `sha256sum -c`. The only requirement on a mirror is that it
carries the exact pinned versions. Verified end-to-end in the sandbox:
the one-liner reads the env var, downloads from an alternate base, and
sha256-verifies; a wrong-bytes base fails loudly. Live caveat finding
(2026-08-03): TUNA's pool carried 8/9 pinned versions — the libexpat1
path 404'd on some CDN nodes while TUNA's own dists index still listed
2.7.1-2 (pool/index skew on mirror edges; the file had downloaded fine
from the same URL hours earlier). Mirrors can rotate pool versions out
from under exact pins; the failure is always LOUD (404 or sha256
mismatch names the file), never silent. Fallback candidate for
exact-version archival: snapshot.debian.org date-scoped pool URLs
(reachability on the operator's route untested).

**Plan B — `Dockerfile.donor` multi-stage (Docker Hub as transport).** If
no Debian mirror works: `FROM ${GL_DONOR_IMAGE} AS gldonor`, then one
BuildKit-mount RUN copies the 9 soname families (with symlinks, `cp -a`,
plus X11 locale data if present) into the final python:3.11-slim-trixie
stage. deb.debian.org is never contacted. Guards identical in kind and
position to the main Dockerfile: loud `DONOR MISSING: <pattern>` failure
on an incomplete donor (logic exercised against fake donor trees —
complete passes with symlinks preserved, incomplete fails naming the
pattern), post-copy `test -e` state check per soname, ldconfig, the same
ldd "not found" guard over system libs + all wheel libs (including
libexpat.so.1 directly), and the byte-identical Layer 6 smoke test. Copy
logic is parameter-equivalent to the tested script. glibc compatibility
for Ubuntu-based donors (jammy 2.35 / noble 2.39 → trixie 2.41) is
backward-safe and re-proven by the ldd guard + smoke inside the final
image.
**Donor contents are UNVERIFIED from the build sandbox** (Docker Hub
auth/registry unreachable there — ADR-009 forbids asserting them from
recall). The Dockerfile header carries the one-line donor-selection
command (verified: prints MISSING per absent soname, or
CHECK-DONE-ALL-PRESENT) and a prioritized candidate list marked as
reasoning: eclipse-temurin:21-jdk-noble, eclipse-temurin:17-jdk-jammy,
python:3.11-trixie, nvidia/opengl:1.2-glvnd-runtime-ubuntu22.04 (partial:
GL only). **Integrity in this path anchors on the donor image, not deb
sha256** — after first successful pull the operator pins
GL_DONOR_IMAGE by digest (`docker images --digests`) and records it here.
Compose gains `dockerfile: ${BACKEND_DOCKERFILE:-Dockerfile}` and a
GL_DONOR_IMAGE passthrough; the main Dockerfile is unchanged in behavior
when the ARGs are unset. Pip-layer pin consistency tests now cover both
Dockerfiles; structure tests lock the donor stage, copy set, loud
failure, guards, and layer order. 13/13 image-structure tests pass.

---

## ADR-017 v2 — cache regression fix + Plan A 404 root cause + permanent snapshot default (2026-08-03)

**Operator report:** Plan A build failed with HTTP 404 on the DEFAULT pool
URL, and the four pip layers re-downloaded (~13 min of a 738 s build)
despite being cached before commit bb0ee53. Two defects, both mine.

**Defect 1 — cache invalidation (operator's diagnosis, correct).** Docker's
cache key for every RUN implicitly includes all ARG variables in scope
(RUNs see them as environment). Declaring `ARG DEB_POOL_URL` above the pip
layers put a new in-scope variable over all four, invalidating ~400 MB of
cached downloads. Fix: DEB_POOL_URL is now declared immediately above Layer
5 (the only layer that uses it), below the pip layers. PIP_INDEX_URL stays
above the pip layers — the pip layers themselves use it and its value is
unchanged, so it enters their cache key identically to the cached build.
Structure test now asserts: DEB_POOL_URL index > last pip layer index, <
GL layer index; PIP_INDEX_URL index < first pip layer index.

**Defect 2 — the 404 was NOT version rotation. It was a wrong pool path,
mine.** Live probe (2026-08-03): 8/9 files exist on deb.debian.org right
now; the 404 was `libe/libexpat/libexpat1_2.7.1-2_amd64.deb`. The expat
SOURCE package is `expat`, so the pool directory is `e/expat/`, not
`libe/libexpat/`. Corrected path serves 200 on deb.debian.org, on the
snapshot, and on TUNA (0.3 s probe) — the earlier "TUNA pool skew" finding
is retracted: it was the same mis-path. **Method correction recorded:
pool paths are derived from the source package name and verified by live
probe, never assumed from the binary package name.** The 8 glvnd/X11 paths
probe 200 as written.

**Rotation hardening — default is now a dated snapshot.** Live pools rotate
superseded versions; this stage has now been bitten twice in two days (once
by path, once by genuine rotation risk on mirrors). snapshot.debian.org
keeps every historical version permanently. New default
`DEB_POOL_URL=https://snapshot.debian.org/archive/debian/20260803T082142Z/pool/main/`
— **all 9 files at that timestamp verified byte-exact (full GETs) against
the existing sha256 pins; pins unchanged.** Compose default updated to
match. Any mirror remains usable via the ARG (pure transport under the
pins).

**Failing-URL print (operator requirement).** The download one-liner now
prints `GL-LAYER download: <full URL>` (flushed) immediately before each
fetch; on failure the shell appends `GL-LAYER DOWNLOAD FAILED — the failing
URL is the last 'GL-LAYER download:' line above` and exits 1. Verified both
directions against a local file:// pool tree: success path downloads 9
debs / 1,635,412 bytes with every URL printed and `sha256sum -c` 9/9 OK;
missing-file path exits 1 with the failing URL as the last download line.
Bonus on the operator's line: per-file progress instead of a silent stage.

Plan B (Dockerfile.donor) is untouched by v2 — the operator is building it
in parallel; its ARG GL_DONOR_IMAGE sits before the first FROM where it is
not in scope for final-stage RUNs, so it has no cache effect on the pip
layers.

---

## ADR-018 — HYBRID Plan B: pinned python:3.11-trixie donor + local GL debs (2026-08-03)

**Operator donor check, verbatim, against python:3.11-trixie:**
PRESENT: libX11.so.6, libxcb.so.1, libXau.so.6, libXdmcp.so.6,
libexpat.so.1 — MISSING: libGL.so.1, libGLX.so.0, libGLdispatch.so.0 (no
libGL* files at all). The operator already holds the three GL debs from an
earlier partial fetch (sizes match our verified bytes:
89,504 / 51,960 / 34,892).

**Decision: new `Dockerfile.hybrid`, the recommended Plan B.** Two proven
sources, zero deb.debian.org contact:

1. Five libraries (X11 family + expat) copied from
   `python:3.11-trixie@sha256:c7220863385ee39fb6d822da81f4469d0cd33ff893d92ce94105e5c3f4b95fe2`
   (operator-pulled, pinned by digest — the integrity anchor for this
   source, recorded here per the ADR-017 rule). **This is the strongest
   donor available: the SAME Debian trixie release AND the SAME python
   image line as the backend base — zero cross-distro glibc mixing, the
   one weakness of the generic donor variant (Ubuntu-based donors).**
   Copy via BuildKit mount + `cp -a` (soname symlinks preserved), X11
   locale data included when present.
2. The GL trio as LOCAL debs in `./debs/` (build context), sha256-verified
   in-layer against the SAME three pins as the main Dockerfile's Layer 5 —
   proven, not trusted because they came from the operator's disk. Missing
   folder → Docker's COPY error; incomplete folder → `GL DEBS MISSING:
   <file>` naming all three and pointing at the documented fetch commands
   (snapshot URLs in docs/operator/01_starting_the_platform.md). `debs/`
   added to `.gitignore` (binaries live on the operator's machine, never
   in git). `.dockerignore` deliberately does NOT exclude it — the build
   needs it in context.

**Guarantees unchanged:** dpkg state loop (trio), per-soname `test -e`
state check (all 8), ldconfig, ldd guard (all 8 sonames full-path + every
wheel lib), byte-identical Layer 6 smoke test, same layer order. Verified
in sandbox both directions: complete donor + real debs → LAYER-PASS with
symlinks preserved and X11 data copied; missing deb → GL DEBS MISSING
naming the file; corrupted deb (one appended byte) → sha256 FAILED;
missing donor lib → DONOR MISSING: libexpat.so.1*. All RUN lines bash -n
clean. No ARG sits above the pip layers except PIP_INDEX_URL (used by the
pip layers themselves, value unchanged) — the donor needs no ARG at all
because it is pinned by digest in the FROM. Structure test
`test_hybrid_dockerfile_structure` locks all of it; pin-consistency and
heavy-layer tests now cover all three Dockerfiles. 14/14 image-structure
tests.

Dockerfile.donor (generic, ARG-selectable donor) is kept as the fallback
for the case the pinned hybrid donor ever fails its check; docs present
hybrid as recommended and donor as fallback. Compose needs no functional
change (BACKEND_DOCKERFILE passthrough); comments updated.

---

## ADR-019 — sandbox npm mirror leaked into the committed lockfile (2026-08-04)

**Operator build failure, verbatim:** `npm error network request to
https://npm.mirrors.msh.team/vite/-/vite-8.2.0.tgz failed — reason:
getaddrinfo ENOTFOUND npm.mirrors.msh.team`.

**Root cause, mine.** `frontend/package-lock.json` was generated inside
the build sandbox, whose npm is configured with an internal mirror
registry. npm bakes the serving registry into every `resolved` URL, and
`npm ci` follows `resolved` verbatim — so all 64 tarball URLs pointed at
a host that exists only inside the sandbox. The frontend Dockerfile
itself was clean (no registry override, no .npmrc); the poison was
entirely in the committed lockfile.

**Fix:** every `resolved` host rewritten to `registry.npmjs.org` (path
layout identical: `/<name>/-/<file>.tgz`). **Integrity is unaffected:**
the lockfile's `integrity` fields are sha512 CONTENT hashes, independent
of where bytes come from — npm verifies them after download regardless.
Proven, not reasoned: vite-8.2.0.tgz (570,075 B) and three-0.185.1.tgz
(5,320,348 B) fetched live from registry.npmjs.org on 2026-08-04 both
hash byte-exact to the lockfile's integrity values. JSON re-validated.
New test `test_lockfile_resolved_urls_use_public_npmjs` asserts every
resolved host is registry.npmjs.org — the leak can never be committed
again.

**Method correction (standing):** any machine-generated manifest
committed from a sandbox must be audited for sandbox-specific hosts
before shipping — lockfiles (npm `resolved`, pip `--index-url` in
requirements files, poetry/pdm sources) inherit the generating
environment's registry config. This is the registry-host equivalent of
ADR-009: sandbox state is not portable state.

**STANDING RULE (operator directive, 2026-08-04, verbatim):** no host,
URL, mirror or registry from the build sandbox environment ever reaches
a committed file. Cost so far: three separate multi-hour operator
blocks. The only permitted mention of a sandbox host is as incident
history inside this log (as deb.debian.org's reset and the mirror
outages are recorded) — never as a functional endpoint.

**Version verification against the LIVE public registry (2026-08-04,
operator requirement — checked, not assumed).** package.json uses EXACT
pins (no ranges), and every operator-named version exists on
registry.npmjs.org with dist.integrity byte-identical to the lockfile:

| package | pinned | on public npm | integrity == lock |
|---|---|---|---|
| vite | 8.2.0 | yes | yes |
| react | 19.2.8 | yes | yes |
| three | 0.185.1 | yes | yes |
| rolldown | 1.2.1 | yes | yes |
| typescript | 5.9.3 | yes | yes |

The internal mirror had served identical bytes and versions — the ONLY
difference regeneration produces is the host, which the rewrite already
corrected. No silent version drift; nothing to surface beyond the host.

**Full-repo host audit (2026-08-04, every tracked file, every URL + raw
IP sweep).** Sandbox-specific hosts: npm.mirrors.msh.team was the ONLY
one, lockfile-only, now zero hits (`grep -c msh.team
frontend/package-lock.json` = 0; its single remaining mention is this
incident record). Everything else is one of: canonical public endpoints
(registry.npmjs.org, pypi.org, snapshot.debian.org, api.moonshot.ai/.cn
and console hosts for the provider keys — Phase-1-gated); documentation
references (docker.com, opendesign.com, provider consoles); placeholders
(your.mirror, address); schema identifiers never fetched
(luxuryform.internal, json-schema.org); lockfile funding metadata never
fetched (github.com/sponsors, opencollective, tidelift); compose/docs
networking (localhost, backend). Raw-IP sweep: no private IPs — the
regex hits were version strings (npm 10.8.2, 10.6.0).

**Operator impact:** `docker compose build frontend` — the lockfile
change re-keys layer 1 (manifest COPY), so layer 2's `npm ci` re-runs
against registry.npmjs.org. That is the intended and necessary cost; the
BuildKit npm cache mount still bounds a mid-ci connection drop to
seconds on retry.

---

## ADR-020 — empty viewport: OCCT exports GLB in METRES; camera now frames from the bounding box (2026-08-04)

**Operator report:** POST /build 200, latest.glb 200 (640.69 kB,
gltf-binary), validation PASS with real numbers, rebuild timer correct,
console clean — yet an empty grid at every zoom. One WebGL warning:
"drawArraysInstanced: Drawing to a destination rect smaller than the
viewport rect."

**Root cause (source-verified, not assumed).** build123d 0.11.1's
export_gltf → `_create_xde` calls
`XCAFDoc_DocumentTool.SetLengthUnit_s(doc, 1 / UNITS_PER_METER[unit])`
(exporters3d.py, wheel read directly), and OCCT's RWGltf_CafWriter writes
glTF in the spec unit — **metres** (glTF 2.0 §coordinate-system-and-units,
referenced in the build123d source). The 2600 mm cascade therefore
arrives **2.6 units wide**. The viewport camera was hardcoded for
millimetres (position ~5,650 units out, 6,000-unit grid): the model was
added to the scene and rendered every time — as a sub-pixel speck.
Consistent with every symptom, including the timer firing (the load
callback did run).

**Fix — nothing assumes units (operator instruction #1, Phase-6-proof).**
New `frontend/src/viewport/framing.ts`: `frameCameraToObject` measures
the loaded model's Box3 and derives EVERYTHING from it — orbit target =
bbox centre; camera distance fits the bounding sphere to 70% of the
shorter view dimension (aspect-corrected); near = radius/1000,
far = distance + 50·radius; degenerate loads fall back to a unit region
instead of NaN planes. Grid rebuilt per load at 6·radius, parked just
under `box.min.y`; sun + sun.target repositioned relative to the centre.
Post-load `console.info` logs scene children count, bbox size/centre,
camera distance and near/far (operator ask #2 — proof, per load).
Lights existed all along (ask #3: hemisphere + directional present; the
model was invisible from scale, not darkness). Renderer sizing now
follows the CONTAINER via ResizeObserver + one post-layout pass (ask #5
— the destination-rect warning: the canvas was sized once, pre-layout).

**Verified with real three.js 0.185.1 in node** (framing.ts transpiled
by tsc from the committed source, not a copy): 11/11 assertions — the
actual incident case (2.6-unit model: sphere fully inside frustum, fills
70.0% of view height, near/far sane), the 1000× mm case (scale
independence), off-centre model (target == centre, view direction dot =
1.000000), empty group (finite planes), narrow 0.5 aspect (no horizontal
clip). Plus full `tsc --noEmit` (0 errors) and `vite build` (success)
against the real dependency set.

**UI defects (operator screenshot):** (a) material select overflowed its
fixed 110px grid track onto the unit label — track now `auto`
(fits-content); (b) validation verdict column clipped at the right edge —
numbers now `nowrap` and the panel scrolls horizontally instead of
clipping; `scrollbar-gutter: stable` stops scrollbar appearance shifting
the panels.

**Gate update:** gate_phase2_visual.md §3 now REQUIRES the model framed
to fill the view on load with no zooming/panning (fail = write down
exactly what you see); §2 notes an empty grid is normal before the first
build. New `tests/test_viewport_framing.py` locks the framing module,
the load-path logging, the CSS fixes, and the gate requirement.
20/20 structure tests.

---

## Record — Phase 2 closure addendum (2026-08-04, operator-confirmed)

Not a decision — two open items from the Phase 2 gate closed from data:

1. **Cross-machine determinism (Amendment 1) — PROVEN.** The operator's
   gate §2 printed STEP sha256 run A and run B, both
   `e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13` —
   identical to the sandbox canonical. Byte-identical STEP is now proven
   same-machine (both machines) and cross-machine. Recorded in
   PHASE_2_REPORT.md.
2. **tiers=4 volume delta (319,324,176 vs 340,426,916.278 mm3) —
   explained, not a defect.** The operator's gate session had
   basin_diameter_mm=2400 (left over from the constraint test), not the
   2600 default. Smaller basin, less material. No reconciliation needed.

Phase 2 is CLOSED with zero open items. Phase 3 plan approved by the
operator as written (PHASE_3_PLAN.md), including the split gate
(fixture mode = $0 offline replay; --live mode only on operator
command) and the ≈$1.15 session estimate, which will be checked against
the MEASURED figure after the first live session.

---

## ADR-021 — Phase 3 pre-code provider re-verification (ADR-009 fetches, 2026-08-07)

Operator order before any Phase 3 provider-touching code: re-fetch every
provider detail live, record fetch dates, re-verify pricing. The build
sandbox holds NO provider API keys (they live with the operator), so
account-specific checks are scripted for the operator to run
(`scripts/live_verify_providers.py`) — nothing about them is claimed here.

**Pricing re-verification (pricing_version bumped 2026-08-v1 → 2026-08-v2):**

- **anthropic** — FIRST-PARTY
  `platform.claude.com/docs/en/about-claude/pricing`, fetched 2026-08-07:
  Claude Sonnet 4.5 = $3 / $15 per MTok, UNCHANGED. (Context: current
  generation is Sonnet 5 at intro $2/$10 through 2026-08-31, then $3/$15;
  `claude-sonnet-4-5` remains listed and served.)
- **openai** — first-party `platform.openai.com/docs/pricing`, fetched
  2026-08-07: the current chat table lists the gpt-5.x generation;
  **gpt-4o does not appear on it**. GPT-4o $2.50 / $10 (cached $1.25)
  corroborated by three independent dated trackers (aipricing.guru synced
  2026-08-07; pricepertoken 2026-08-06; valueaddvc 2026-06-21). Account
  availability is settled by the operator-run `models.list()`, not assumed.
- **kimi** — FIRST-PARTY `platform.kimi.ai/docs/pricing/chat-k3.md`,
  fetched 2026-08-07: kimi-k3 $0.30 cache-hit / $3.00 cache-miss input,
  $15.00 output, context 1,048,576 — UNCHANGED since the 2026-08-01 fetch.
  We bill input at cache-miss (conservative).

**SDK shapes / parameters:**

- **kimi-k3** — Model Parameter Reference
  (`platform.kimi.ai/docs/api/models-overview`, page updated 2026-08-04,
  fetched 2026-08-07): temperature fixed at 1.0, "do not pass explicitly";
  `reasoning_effort` top-level field (`low`/`high`/`max`, default `max`).
  Our council.yaml handling (temperature null = omit) matches the doc.
- **kimi text response shape** — chat quickstart
  (`platform.kimi.ai/docs/api/chat-completion`, fetched 2026-08-07):
  OpenAI-compatible; text at `choices[0].message.content`, usage at
  `usage.prompt_tokens` / `usage.completion_tokens` — the shape our
  InjectedOpenAITransport assumes. DOC-VERIFIED; a live kimi text call is
  still pending (no key in the sandbox) — see LIMITATIONS §7 and the
  operator script. If the live dump differs, the offline transports are
  updated to match reality before the first live Council session.
- **anthropic / openai SDK shapes** — already LIVE-verified by the
  operator's Phase 1 gate (2026-08-01: text and vision passed on both) —
  stronger evidence than docs; not re-fetched.

**models.list() per provider** — requires the operator's keys; scripted
(`scripts/live_verify_providers.py`, exact commands in
`docs/operator/03_provider_verification.md`). NOT claimed done.

---

## ADR-022 — Cache-token classes are priced separately (2026-08-07)

**Context.** The operator's live_verify_providers.py run (2026-08-07) showed
usage fields the offline mocks did not model: kimi returns
`usage.cached_tokens` (cache-hit subset of `prompt_tokens`), anthropic
returns `cache_creation_input_tokens` / `cache_read_input_tokens`. Cache-hit
input bills far below the miss rate — kimi-k3 $0.30 vs $3.00 per MTok (10x);
anthropic Sonnet 4.5 read $0.30, 5m write $3.75 vs $3.00 base. Billing all
input at the miss rate overstates every session cost; with six Council
agents sharing one brief, cache hits are likely.

**Decision.** Input is split into three classes end-to-end:

1. **Providers normalise at the boundary** (`RawResult`): `tokens_in` is
   always the UNCACHED input count. kimi subtracts `usage.cached_tokens`
   from `usage.prompt_tokens` (cached is a subset — verified shape);
   anthropic's `input_tokens` already excludes both cache classes (no
   subtraction). `cached_input_tokens` = cache-read class;
   `cache_write_input_tokens` = anthropic cache-creation (no OpenAI-
   compatible write class exists). A kimi shape anomaly
   (cached > prompt) raises — never guesses.
2. **PricingConfig.cost_usd** prices each class at its own rate. If a live
   response reports tokens in a class with no configured price, it raises
   PricingLookupError — a price is never guessed. call_log still persists
   the ai_calls audit row for the (already billed) call with the failure
   recorded, then raises ProviderError (Rule 8: a billed call never
   vanishes from the log).
3. **pricing.yaml 2026-08-v3** — cache-class prices are FIRST-PARTY,
   fetched 2026-08-07: anthropic read $0.30 / 5m write $3.75
   (platform.claude.com/docs/en/about-claude/pricing); kimi hit $0.30
   (platform.kimi.ai/docs/pricing/chat-k3.md). **openai gpt-4o is
   deliberately NOT split**: its cached rate ($1.25) is corroborated only
   by third-party trackers (gpt-4o is absent from the current first-party
   pricing table), so openai_provider bills all input at the verified full
   rate — conservative; real cost can only be lower. Revisit when
   first-party-verified.
4. **Persistence:** ai_calls and council_calls gained
   cached_input_tokens / cache_write_input_tokens (schema v3, DEFAULT 0 —
   folded into v3 before any operator deployment of v3, so no v4 migration
   is needed).
5. **Offline transports updated** to carry the live-verified usage fields
   (conftest.py), with new tests proving the split math, the loud-failure
   paths, and audit persistence (tests/test_cache_pricing.py, 7 tests).

**Consequences.** Session cost estimates drop materially when cache hits
occur (10x cheaper hit input on kimi; 0.1x on anthropic reads). The
pre-dispatch ESTIMATE still bills all input at the miss rate (conservative
cap check). The $1.15 session estimate will be re-measured against the
first live session (step 4) with the split in force.

---

## ADR-023 — Startup schema patches + audited retries + degraded sessions (2026-08-07)

**Context.** The first live Council session (operator run, 2026-08-07)
failed with no money spent, exposing two defects and one doc bug:

1. **Schema migration missing.** The operator's luxuryform.db was created
   under the EARLIER v3 (before the ADR-022 cache columns) and persisted in
   a Docker volume. Editing schema.sql never alters an existing database —
   the claim that folding columns into v3 "before any v3 deployment" avoided
   migration was WRONG: an earlier v3 file already existed in the wild. The
   session crashed mid-run: "table ai_calls has no column named
   cached_input_tokens".
2. **One timeout killed the session.** kimi (researcher) timed out at
   220,923 ms — that number itself revealed the openai SDK's hidden internal
   retry loop (3 attempts x 60 s + backoff), invisible to ai_calls. The
   operator's connection is slow and unreliable; a 15-call sequential
   session where any single timeout aborts everything is not viable.
3. Doc 04 used cmd curl syntax that breaks in PowerShell.

**Decision.**

1. **Additive column patches at startup** (database.py): a declarative
   `_ADDITIVE_COLUMN_PATCHES` map; on init_db, missing mapped columns are
   added via ALTER TABLE (idempotent, recorded in a new schema_patches
   table). A `_verify_no_drift()` pass then compares every ORM-mapped
   column against the live file and raises SchemaDriftError with the
   operator remedy (back up, delete, restart) if a mismatch is NOT
   auto-patchable. Drift surfaces at STARTUP, never mid-session after
   billed calls.
2. **Audited retries** (call_log.py): transient failures (timeout /
   connection class names — covers both SDKs and httpx) are retried up to
   `LUXURYFORM_PROVIDER_MAX_ATTEMPTS` (default 3) with exponential backoff
   (`LUXURYFORM_PROVIDER_BACKOFF_BASE_S`, default 10 s → 10, 30). The error
   row records the full retry history. Non-transient errors are never
   retried. **SDK-internal retries are disabled (max_retries=0)** so no
   attempt is ever hidden from the audit log. Per-attempt timeout is
   `LUXURYFORM_PROVIDER_TIMEOUT_S` (default 300 s — kimi-k3 generating
   8192 tokens on a slow line legitimately exceeds 60 s).
3. **Degraded sessions** (orchestrator.py): a failed NON-CRITICAL call
   (researcher either side, geometrist, engineer, critic, any designer
   alternative) is caught, persisted as an error council_calls row, and the
   session continues with `degraded=1` and honest placeholder text in
   downstream prompts ("(researcher unavailable — provider failures; ...)").
   Designer call failures shrink the candidate pool; <3 valid specs still
   aborts. **The Arbiter is never optional** — without a binding decision
   there is no session outcome. **BudgetHalt is never degraded** — it
   always halts.
4. Doc 04 carries cmd.exe AND PowerShell (Invoke-RestMethod) variants.

**Verification.** tests/test_schema_patches.py (3: ALTER patch with data
preserved + recorded; idempotent; loud drift), tests/test_retry_and_
degradation.py (7: retry-then-succeed, exhaustion with audit, no retry on
4xx, env-configurable attempts, researcher outage → degraded completion,
engineer parallel outage → degraded with primary kept, BudgetHalt on an
optional call still halts). 117 passed, 7 skipped.

---

## ADR-024 — Cache-break prompts + anthropic cache_control (2026-08-07)

**Context.** The first live session (32e1c68f) measured cache savings of
$0.000690 — effectively zero, against an expectation that six agents
sharing one brief would hit cache. Diagnosis, verified against first-party
docs (platform.claude.com/docs/en/build-with-claude/prompt-caching, fetched
2026-08-07):

1. **anthropic caches NOTHING without an explicit cache_control marker** —
   we never sent one. Cache writes bill 1.25x, reads 0.1x, 5-minute TTL,
   prefix must be byte-identical, minimum cacheable prefix ~1024 tokens.
2. **kimi/openai cache prefixes automatically**, but our prompts were
   role-specific from the FIRST word — no two calls shared a long prefix.
   The observed $0.00069 corresponds to ~255 cached kimi tokens (brief-level
   overlap only).

**Decision.** Council prompts are restructured STATIC-PREFIX-FIRST with a
cache-break sentinel (`CACHE_BREAK`, an inert HTML comment, defined in
app/ai/provider.py):

- designer: instructions + JSON_ONLY + schema (~2.9k tokens — over the
  minimum) + brief + research form the shared prefix; only "ALTERNATIVE N"
  sits after the break. Per provider, call 1 writes the cache, calls 2-3
  read it at 0.1x.
- geometrist/engineer/critic/arbiter share one _session_context prefix
  (brief + candidates digest) before the break; role instructions and
  per-call extras (geometrist notes, engineering review, defect list)
  after. This block is likely UNDER anthropic's 1024-token minimum — it may
  not engage; the designer prefix is the one that matters (designer = 58%
  of session spend).
- anthropic_provider splits at the sentinel and sends the prefix as a text
  block with cache_control={"type": "ephemeral"}; no sentinel -> unchanged
  behavior. kimi/openai send the same text (their caching is automatic;
  the reordering is what helps them).

**Measurement.** Cache token fields persist per call (ADR-022), so the next
live session's rollup shows cache_savings_usd and per-call
cached_input_tokens — engagement is measured, not assumed.

## Designer-spend options (data: session 32e1c68f, 2026-08-07)

Designer = $0.4879 of $0.8438 (58%). Bounds from the rollups: openai's
TOTAL across all its roles was $0.1066, so openai-designer <= $0.1066 and
anthropic-designer >= $0.3813 (3 calls, ~$0.127 each).

- **Option A — 2 alternatives x 2 providers:** designer ~= $0.325,
  saves ~$0.163/session. Keeps dual-provider generation. Config-only
  change if the orchestrator's alternative count becomes configurable.
- **Option B — 3 alternatives, openai alone; cross-review shifts:**
  designer ~= $0.107, saves ~$0.38/session (~45%). Requires: engineer
  primary swapped to anthropic (strongest reviewer is then never the
  producer), critic already lands on kimi under the dynamic rule, arbiter
  unchanged. Small orchestrator change (skip parallel when parallel ==
  primary). Risk: correlated generation failure modes from one provider —
  partially offset by independent engineer + critic review before the
  binding Arbiter decision.
- **Recommendation:** Option B with the engineer swap, decided by the
  operator before Phase 5 multiplies sessions. Per-call latency data will
  refine it (kimi slowness noted by the operator; anthropic and kimi are
  comparable per call, ~$0.08; openai ~$0.018).
- **OPERATOR DECISION (2026-08-09): Option B REJECTED — keep 3 alternatives
  x 2 providers.** Verbatim reasoning: "The designer is where this
  platform's differentiator lives. The master order made dual-provider
  designers decision-critical so two models produce genuinely different
  design thinking and disagreement surfaces rather than averaging away.
  Option B collapses that to one model's imagination with a review chair.
  $0.38 a session is not worth narrowing the creative range on a platform
  whose selling point is imagination plus correctness. Revisit only if
  session volume makes cost actually bite." The dual-provider designer
  table is FROZEN unless session volume changes the economics.
- **OPERATOR DECISION (2026-08-09): researcher primary kimi -> openai
  APPROVED** (Q4). kimi stays parallel — under ADR-023 its failures
  degrade gracefully, so the unreliable provider sits in optional seats
  only. Rest of the role table held until the post-ADR-024 cache
  measurement. Applied in config/council.yaml 2026-08-09.

## ADR-025 — Session health flags: degraded vs corrected (2026-08-09)

**Trigger (operator, 2026-08-09):** live session 32e1c68f wore the
**degraded** badge with ZERO failed calls — no error rows, no timeout, no
outage. Code reading found the cause: `_resolve_critic_providers` flagged
`degraded=1` whenever the never-a-producer rule left the critic with one
provider. With the static designer pair (anthropic‖openai) the critic
primary (openai) is ALWAYS a producer, so EVERY healthy session flagged
degraded — the badge was meaningless, and the operator rightly said they
must be able to trust it.

**Decision — two flags with disjoint meanings:**

- **degraded** = a provider FAILURE left a role seat empty or reduced
  (optional-call failure, researcher outage, designer call failure).
  Something the Council needed did not run. Action-worthy.
- **corrected** = a bounded re-ask SUCCEEDED (designer or Arbiter first
  reply failed validation, retry produced valid output). The Council did
  its job and corrected itself. Informational, no action needed.
- The critic's single-provider coverage under the never-a-producer rule is
  the rule WORKING AS DESIGNED — logged, visible in the call list, and
  flagged as NEITHER.

**Schema:** `council_sessions.corrected INTEGER NOT NULL DEFAULT 0`, added
to schema.sql AND to the ADR-023 additive patch registry — the operator's
live database is ALTERed at next startup, data preserved, patch recorded
in schema_patches (proven in tests/test_schema_patches.py against a
script matching their real pre-patch database).

**Comment correction (visible history):** the old schema comment said
"degraded = ran without parallel comparison"; the happy-path test even
asserted `degraded == 1` "by design". Both corrected; PHASE_3_REPORT.md
carries a strikethrough correction note.

## ADR-026 — Phase 4 fabrication loop: contract, sandbox, repair (2026-08-09)

Operator-approved plan (PHASE_4_PLAN.md) with three operator additions:
separate first-attempt/per-round success rates; every rejected program
persisted with its AST reason; geometrist_code as its own rollup role.

1. **Program contract** `build(spec) -> (solid, params_dict, seed)`. The
   runner owns export (deterministic STEP timestamp from the seed —
   Amendment 1 carries forward); generated code never writes files.
2. **Vocabulary**: one primitive, `registry.cascade_fountain(params,
   seed)`, living in registry.py so the prompt surface is GENERATED from
   the live registry (cannot drift; Phase 6 widens it by editing
   registry.py). registry.py carries a security note: its public surface
   is reachable by sandboxed AI code — keep it benign.
3. **AST gate before the sandbox** (operator: "the right belt-and-braces"):
   import whitelist {registry, build123d, math}; banned calls (open/eval/
   exec/getattr/…/export_*); no dunder attribute access; must define
   build(spec). Rejection reasons are human-readable, persisted, and fed
   back as the repair digest.
4. **Sandbox = ADR-005 realized as a docker-compose service** (geo-worker):
   non-root, network_mode none, read-only fs + tmpfs, one scratch bind
   mount, cpus 1.0, mem_limit 2g, hard timeout 120s enforced by the worker
   watcher via subprocess timeout. The backend queues jobs on the scratch
   mount and NEVER executes generated code — tests use a scripted runner
   that executes nothing either.
5. **Bounded repair**: 3 attempts; every failure class (provider call, AST
   rejection, sandbox error, validation failure) becomes the next round's
   error digest; exhaustion reported honestly with all rows persisted.
   Provider failure during fabrication is a failed ATTEMPT (ADR-023
   optional-call semantics), not a crash.
6. **Provider**: geometrist primary (anthropic) writes code; parallel seat
   unused in Phase 4.


## ADR-027 — Material-derived fabrication envelopes + full-history repair (2026-08-10)

First LIVE Phase 4 fabrication (operator-run, monumental basalt brief,
2.6 m basin) failed 3/3 and exposed two real defects plus one gate bug.
This ADR records the fixes and their basis.

**Defect A — registry ranges were demo envelopes, not engineering
reality.** The cascade ranges were set for the Phase 2 demo: basin_wall_mm
capped at 100, dish_depth_mm at 300. The Council designed a buildable
monumental basalt fountain (180 mm wall, 420 mm dish) and the vocabulary
could not express it — first-attempt pass rate 0.0 with an empty AST
catalogue, i.e. the model wrote legal code and the RANGES rejected it.

Fix: ranges now derive from the MATERIAL, per operator directive ("derive
the ranges from engineering reality per material, not from demo defaults").

1. **Per-material wall envelopes in materials.yaml** — every material gains
   `max_wall_mm` beside `min_wall_mm`; hard constraint 2 now enforces BOTH
   directions with real numbers:
   - stainless_316l_sheet: 3..20 mm (sheet forming/welding envelope; beyond
     20 mm is plate machining, and the stock-sheet size stops applying)
   - basalt_slab: 20..250 mm (monumental carved stone; 250 ceiling is
     mass-driven — a 250 mm wall ring on the largest registry basin, 6 m
     dia x 0.9 m, is ~11.0 t, at the edge of handling; the live brief's
     180 mm wall on 2.6 m x 0.45 m is ~1.7 t, routine crane work)
   - cast_concrete_c35_45: 75..300 mm (beyond 300 mm is a mass pour
     needing thermal control, not shell casting)
   - bronze_cast: 6..40 mm (thicker sections risk shrinkage porosity;
     real work is cored, not solid)
   BASIS HONESTY (ADR-009): these are WORKSHOP envelopes set by the
   fabricator — the operator — and are tunable in materials.yaml. They are
   NOT citations of an external standard and no standard was fetched to
   set them. The mass arithmetic above is computed, not recalled.
2. **Platform envelope widened**: registry basin_wall_mm static range
   3..300 (max over all materials), dish_depth_mm 40..600 (hard
   constraint 6, spacing >= depth, still binds).
3. **Prompt surface carries the envelopes**: registry_surface() now lists
   every material's wall envelope, generated from live materials.yaml —
   the geometrist sees both the per-parameter [min..max] and the
   per-material envelope before writing values.

**Defect B — repair loop carried only the LAST failure digest.** Live run:
attempt 1 failed wall=180, attempt 2 failed dish=420, attempt 3 repeated
attempt 1's wall=180 exactly — 3 attempts gave 2. Fix (operator
directive): fabricate_spec accumulates the FULL failure history, oldest
first; every repair prompt carries every prior attempt's digest and states
explicitly that a previously-failed value must NOT be repeated. Locked by
test_repair_prompt_carries_full_failure_history.

**Defect C — gate crash.** gate_phase4_auto.py imported the tests package
but only put backend/ on sys.path; inside the container (cwd /app) the
repo root was missing. One-line fix + comment.

Phase 4 remains IN PROGRESS until the operator re-runs the live gate.


## ADR-028 — Scratch mount parity, basename artifacts, honest collection failure, real round-trip gate (2026-08-10)

First SUCCESSFUL live fabrication (attempt 1 rc=1 genuine build failure,
attempt 2 rc=0 built — the bounded repair loop worked end to end) crashed
at artifact COLLECTION with an unhandled 500. Operator diagnosis:
mount mismatch, not a build failure.

**Root cause.** The backend mounted only ./data:/app/data and resolved
scratch as /app/data/geo_scratch; the geo-worker mounted the same host dir
at /scratch. result.json (readable via the shared host dir) carried
WORKER-side absolute artifact paths (/scratch/<job>/artifact.step) —
meaningless inside the backend container, so shutil.copyfile raised
FileNotFoundError. Attempt 1 had artifacts=null, which is why only the
successful attempt crashed.

**Fixes (operator-directed, three parts).**

1. **Mount parity, stated explicitly.** docker-compose.yml now binds
   ./data/geo_scratch to /scratch on BOTH services and sets
   LUXURYFORM_GEO_SCRATCH=/scratch on both; comments name the host path
   per service. scratch_dir() treats the env var as the exact directory.
2. **Basename artifacts + verified visibility.** job_runner writes artifact
   BASENAMES into result.json (never container-side paths); the backend
   resolves them against its own view of the job dir and VERIFIES every
   file exists before reporting success. A claimed-success result whose
   files are not visible returns an honest error naming the mount
   mismatch; a non-basename path is refused outright. A copy failure in
   fabricate_spec persists a collection_failed attempt row with the reason
   and feeds the repair history — never an unhandled exception.
3. **The gate now tests the thing that broke.** The worker answers probe
   jobs (job.json {"probe": true}, no code) inline with its hostname+pid.
   New gate section 4 queues a probe and asserts the answer came from a
   DIFFERENT container — the backend provably READ a file the worker
   WROTE. Hard check inside docker; SKIP with instructions on host dev.
   Section 3 statically asserts mount parity so the compose file cannot
   silently drift again.

Regression locks: _resolve_artifacts (basenames/missing/absolute-refusal),
collection_failed persistence + repair continuation, worker probe pickup +
inline answer, plus a live smoke (real worker subprocess answered a
probe_scratch round trip). 149 tests, both auto gates PASS.

## ADR-029 — Zero-clearance tangency, material fall-gap floors, prompt solving order (2026-08-17)

The Phase 4 live gate failed three times. The last of those runs reached
attempt 3, built a real solid, exported STEP and GLB, collected them
correctly (ADR-028 held) — and failed validation on `watertight: False`.
This ADR records the cause, the fix, and three defects found alongside it.

**Root cause — a tangency singularity the constraint system permitted.**
The geometrist set `min_clearance_mm = 0.0`, reasoning in its own comments:
"min_clearance_mm <= 0. Use 0 (minimum allowed)." The brief fixes the basin
at 2.6 m; with a 180 mm wall and a 2240 mm widest dish, constraint 1
(`basin >= widest + 2*wall + clearance`) is satisfied EXACTLY at equality
with clearance 0 — and at equality the widest dish rim is tangent to the
basin inner wall. The fused solid carries coincident surfaces and meshes
non-watertight. The registry declared `min_clearance_mm` with `"min": 0`,
so the one degenerate value in the space was reachable, and constraint 1
cannot catch it because it is satisfied *at* the singularity.

**Measured, not reasoned (the threshold sweep).** Rebuilt offline through
the real `validate_mesh` path, monumental massing, basin 2600:

```
gap(mm)  widest   watertight   volume_mm3
  0.0    2240.0     False      3169987070     <- reproduces the live failure
  0.5    2239.5     True       3169071696
  1.0    2239.0     True       3168156539
 20.0    2220.0     True       3133537726
```

Volume 3169987070 matches the live run's 3169987069.696 — the failure was
reproduced exactly, not approximated. The CAD threshold is therefore *any*
positive clearance: zero is a knife-edge singularity, not a gradual
degradation. Consequence for how the floors are set: they are chosen from
FABRICATION reality and carry an enormous margin over the CAD threshold,
rather than being tuned down to it.

**Fix 1 — per-material fall-gap floors (materials.yaml).** Every material
gains `min_clearance_mm`; new hard constraint 7 enforces it with real
numbers in both the diametral and the radial figure. Registry static floor
becomes 20 (the smallest material floor — the union, exactly as ADR-027 did
for walls), so 0 is unreachable through any material.

- stainless_316l_sheet 20 mm (10 radial) — parts finished before assembly;
  clears weld bead (~4 mm proud) plus springback, passes a hose/brush
- bronze_cast 20 mm (10 radial) — cast and chased before assembly
- basalt_slab 40 mm (20 radial) — two carved faces bound this gap, each
  with a few mm of carving tolerance; admits a brush once installed
- cast_concrete_c35_45 50 mm (25 radial) — coarsest tolerance in the
  library; formwork deflects and aggregate bulges the face

BASIS HONESTY (ADR-009, same status as ADR-027's wall envelopes): these are
WORKSHOP values set by the fabricator — the operator — and tunable in
materials.yaml. They are NOT citations of an external standard and no
standard was fetched. The threshold arithmetic above is computed.

**UNIT CONVENTION recorded because it caused the defect:**
`min_clearance_mm` is DIAMETRAL — it is subtracted from a diameter, so the
physical radial gap is HALF of it. The parameter note said "free water/fall
gap", which reads as radial. Both the note and the prompt now say so.

**Fix 2 — the prompt teaches the solving ORDER, and this is what actually
worked.** A floor alone would only have converted a validation failure into
a constraint failure — the model would still have driven the clearance down
and burned attempts. `registry_surface()` now states the diametral
convention, names the tangency consequence in the failure's own words, and
gives the order to solve in: when the brief fixes the basin, constraint 1
binds the DISHES, so size `widest_dish <= basin - 2*wall - clearance` and
choose the tier geometry under it. The next live run's program followed
that instruction verbatim ("Solve constraint 1 for dish sizing...", "100.0
# Well above the 40 mm floor") and passed on ATTEMPT 1 — against 3 failed
attempts for the same spec before it.

**Fix 3 — success_rates counted specs, not runs.** A "fabrication unit" was
`(session_id, spec_id)`, so every re-run of the same spec after a fix
collapsed into one unit. On the real data that reported
`first_attempt_pass_rate: 1.0` when three earlier runs of that spec had
failed outright — the metric flattered itself exactly where the operator's
2026-08-09 order says it must warn. Units are now RUNS, recovered without a
schema change: attempt_no restarts at 1 per `fabricate_spec` call, so within
one (session, spec) ordered by created_at a new run begins wherever
attempt_no does not increase. True figures are in PHASE_4_REPORT.md.

**Fix 4 — result.json is published atomically.** The backend polls for the
file's EXISTENCE and parses it immediately; both writers created it empty
and filled it afterwards, so a poll landing mid-write reads a truncated file
and raises JSONDecodeError inside the fabrication loop. Both
`worker._write_result` and `job_runner._write_result` now write a temp
sibling and `os.replace`. The queue side of this handshake had always been
correct (the worker requires job.json, which the backend writes last); the
answer side never was. Not observed in production — found by inspection,
fixed before it could bite on a slower disk.

**Method note for future work — never judge watertightness from a raw GLB
load.** `trimesh.load(...)` reports EVERY build non-watertight, including
the Phase 2 canonical one: the exporter writes one mesh patch per B-rep face
with duplicated seam vertices. Only `validate_mesh`, which merge_vertices()
first, gives a meaningful answer. A first version of the ADR-029 regression
test measured raw and "found" a defect in known-good geometry.

**Regression locks:** constraint 7 with real numbers per material; the
registry floor; the exact live-failure parameter set refused before the
sandbox; a build AT basalt's floor proven watertight through the real
validator; the tangency case re-measured as still failing (with the volume
pinned, so a kernel change that invalidates this ADR's basis is loud); the
prompt surface asserted to carry the convention, the consequence and the
solving order; runs-not-specs rate counting; atomic publication observed at
the write, not read from the source. 178 tests pass; Phase 2 and Phase 4
auto gates PASS; the Phase 2 canonical STEP sha256 e1a59fa6… is unchanged.

## ADR-031 — Costing layer: derived drivers, traced lines, four statuses (2026-08-17)

Operator instruction: wire up costing from the supplied rates, with costs
derived from validation numbers the platform already computes, multi-currency
dated FX, every line tracing to a formula and a source rate, never an invented
rate, and a budget constraint that is real rather than advisory.

**The rates were not supplied.** `config/costing.yaml` was unmodified from
HEAD with all 33 entries null. Reported immediately rather than worked around.
The engine was built anyway: the null card is the ideal fixture for the
never-guess rule, and rates are data while the engine is code.

**1. Drivers are read, never re-measured.** `costing/drivers.py` takes a
`ValidationReport` and unit-converts it. The package contains no geometry, so
a cost can never disagree with the validation numbers already signed off.
Costing a design whose validation FAILED raises — putting a price on geometry
the platform has already refused is worse than declining to quote.

**2. Four line statuses, deliberately not three.** `computed`,
`missing_rate`, `not_computable`, `not_applicable`. The distinction that earns
its keep is **missing_rate vs not_computable**: the first is a number the
OPERATOR supplies, the second is machinery WE have not built. Collapsing them
would hand the operator homework that is ours. The rendered BOM prints them
under literal headings "YOU SUPPLY" and "WE BUILD".

**3. Two of the five named drivers do not exist.** The operator named mass,
surface area, module count, seam length and crane pick weight. Mass, surface
area and pick weight come straight from the validation report. Module count
and seam length do not exist until the solid is segmented against
`fabrication.max_module_m` (Phase 6). They are `None` with a stated reason,
never `0` — zero would silently price a segmented job as needing no modules
and having no seams.

**4. Count-priced materials are refused, not divided.** The template quotes
basalt `per: slab` and 316L `per: sheet`. A slab count requires nesting into
`stock_size_mm`, which requires segmentation, so the line refuses rather than
dividing mass by a nominal slab. The blocker names the fix: quote per kg or
per m3 and the line computes today. This is the highest-value thing for the
operator to know before filling the card in, because material purchase is the
largest line on the BOM.

**5. No total from partial costs.** A BOM with any `missing_rate` or
`not_computable` line produces NO total — not a subtotal labelled as one.
Untraceable totals are exactly what the operator says they cannot defend.

**6. FX must be dated to be usable.** An `fx_rates` entry with a rate but no
`as_of` is MISSING, not usable — the same anti-stale-data rule
`pricing_version` enforces. Every converted line prints the rate and its date.

**7. The budget constraint binds at the BOM boundary — placement recorded.**
The operator asked for "the same treatment as the basin_diameter hard
constraint". Same TREATMENT: it refuses, carries real numbers, cannot be
ignored (`BudgetViolation` mirrors `ConstraintViolation`; the API returns 422
like a geometry violation). Different PLACEMENT, for three practical reasons:
`registry.validate_params` runs inside the ADR-005 sandbox, which has no
network and no rate card; the GEOMETRIST has no rates in its prompt, so a cost
rejection would burn its three bounded repair attempts guessing at an
arithmetic it cannot perform — the exact failure ADR-029 measured; and a cost
depends on the finished validated solid, which does not exist until after the
build the constraint would gate. So an over-budget design is refused at the
BOM boundary and cannot be exported as a quote. Putting it inside the geometry
loop as well needs rates in the sandbox and in the prompt first — a deliberate
decision, not a line-move.

**8. An incomplete BOM's budget check is `not_performed`, never `pass`.** The
most dangerous silent failure available here is declaring a design affordable
because most of its costs were never computed. Locked by test.

**Verification:** 195 tests pass (17 new). `scripts/gate_costing_auto.py`
PASSES at $0, printing the rate-card state, drivers taken from the Phase 4
live-gate design (mass 3,432.476 kg, surface 42.9542 m2), a fully traced line
set against a TEST rate card, the honest incomplete BOM against the REPO card,
and the budget refusal with real numbers. `GET /api/costing/bom/{design_id}`
verified against a real persisted design.

---

## ADR-030 — The registry becomes the ceiling on geometric capability (2026-08-20)

**Status: accepted.** (Numbering note, per this log's own honesty rule: the
number 030 was RESERVED when the operator ordered this trade on 2026-08-17
and the draft was recorded in PHASE_6_PLAN.md §4; ADR-031 was written the
same day for the costing layer, so this entry lands after 031 in file order.
Nothing was removed — the gap was a reservation, now filled.)

Enforced in Phase 6 slice A1: `ALLOWED_IMPORT_ROOTS` in
`ast_gate.py` is now `{registry, math}` — **`build123d` is dropped from the
AST whitelist.** AI-written code can only reach geometry the registry
exposes. The model can never reach for a kernel operation we have not
deliberately published.

**What we buy:** every constraint becomes enforceable rather than advisory,
every boolean is performed by trusted code (`registry.assemble`), and the
failure class measured in ADR-029 — the model reasoning itself into a
geometric singularity — cannot be constructed directly.

**What we give up:** novel form is gated on a registry edit. If a brief
needs a shape the library does not have, the platform cannot improvise it,
and the answer is a new primitive with its own envelopes and tests — a
deliberate act with a gate, not an emergent one.

**The operator accepts this ceiling knowingly (ordered 2026-08-17).** A
future decision to widen it should be made against this record: the
question to ask then is not "is build123d safe?" but "are we willing to
make the constraint system advisory again?" — because that, and not
sandbox escape, is what widening costs. The sandbox (ADR-005) remains the
real security boundary either way; this trade is about correctness.

Locked by: `test_whitelist_roots_documented`,
`test_build123d_import_rejected_adr030`, gate_phase6a1_auto §2. The
GEOMETRIST program contract text was updated in the same commit (a prompt
promising an import the gate rejects would burn repair attempts).

---

## ADR-032 — Phase 6 slice A1: primitive library core + assembler (2026-08-20)

**Envelope sheet signed.** The operator accepted
`PHASE_6_SLICE_A_ENVELOPES.md` AS DRAFTED (2026-08-20, "restore and go to
slice"). All Part 2/3 values are now in force in materials.yaml and the
primitive registries; they remain WORKSHOP values, tunable in config, not
standard citations (ADR-027/029 status). The sheet's own least-sure flag
stands in the file: concrete's ±5 mm per-face tolerance (joint_overlap_mm
15) — if the formwork is better, the floor comes down in materials.yaml.

**1. Material model gains the Part-2 floors.** `joint_overlap_mm` (basalt
10 / concrete 15 / bronze 5 / 316L 3), `min_feature_mm` and
`min_internal_radius_mm` per material. 316L's two floors are the literal
string `"wall"` — a FORMULA (floor = the part's wall thickness), because a
constant would be wrong across the 3–20 mm sheet envelope; read through
`Material.min_feature_floor_mm(wall)` / `min_internal_radius_floor_mm(wall)`.
The feature/radius floors are recorded and config-validated now; the
parameters they bound arrive with slices B (rim treatments) and C (arrays)
— stated in materials.yaml rather than silently dormant.

**2. Registry restructure.** `backend/app/geometry/primitives/` — one
module per primitive (`cascade`, `basin_round`, `plinth`,
`sculptural_column`), a shared protocol in `primitives/base.py`
(PARAMETERS / validate / build / anchors / joint capabilities), and
`PRIMITIVES` (id → module) as the single registry dict. The cascade
BUILDER moved unchanged; its parameter registry moved with it;
`registry.py` is now the facade: PRIMITIVES + `assemble()` +
`cascade_fountain()` + the compat re-exports every existing import path
uses. build123d imports inside primitive modules are lazy — the registry
stays importable without the geometry stack, as before.

**3. Per-member walls (sheet Part 5).** `tiered_cascade` gains
`column_wall_mm`, default DERIVED = `basin_wall_mm`; hard constraint 4 is
now `column_diameter_mm >= bore + 2*column_wall_mm`. Geometry reads the
new parameter ONLY through constraint 4, so defaults build bit-identical
solids — **proven, not asserted: gate §3 rebuilds the canonical cascade
and gets the Phase 2 STEP sha256 `e1a59fa6…` byte-for-byte.** This closes
the column half of LIMITATIONS §9's first bullet; the dishes still share
`basin_wall_mm` with the basin (they are drawn from the same profile
family), recorded there.

**4. The assembler (`assembly.py`, surfaced as `registry.assemble`).** The
generated program DECLARES an assembly plan (elements + typed joints:
`stack_on`, `concentric_insert`); trusted code computes every placement
and performs every boolean. Enforced with real numbers: overlap floors per
material with cross-material MAX (constraint 9); insert seat/fit against
the parent's declared `min_clearance_mm` (DIAMETRAL, ADR-029 convention);
punch-through refusal; per-joint interference PROVEN (intersection volume
> 0) before the fuse; canonical fuse order (sorted element_id); B-rep
body_count == 1; volume conservation (members − declared intersections =
fused, tol 0.2%) so undeclared overlap cannot hide.

**5. A failure class found during slice A1, before it could bite: joints
meeting THROUGH an intermediate element.** In a coaxial plinth → basin →
column stack, the column inserted into the basin floor reaches the PLINTH
when floor_mm < (stack overlap + insert overlap): one millimetre decides
between undeclared interference and EXACT TANGENCY — the ADR-029 knife
edge, invisible to every per-joint check. The assembler now checks every
NON-joined pair: intersection volume > 0 → refused as undeclared
interference naming both elements; distance == 0 with volume 0 → refused
as tangent contact citing ADR-029 and the fix (thicken the middle
element's floor or reduce overlaps). `distance_to` behaviour verified
against the installed build123d 0.11.1 (tangent boxes: distance 0.0,
intersection volume 0.0), not recalled.

**6. Computed handling limits (plan §5) — the dead spec fields become
load-bearing.** `assemble(..., fabrication={max_lift_kg, max_module_m})`
checks per-element mass (exact B-rep volume × the element's OWN material
density) and bounding box. The refusal message carries both numbers and,
for a solid element, names HOLLOWING as the lever — the signed sheet's
§4.2 example runs live in the gate: the 1.0 × 1.0 m solid basalt plinth
(2,120.6 kg) is refused by a 2,000 kg crane and the same plinth at a
180 mm wall (1,252.0 kg) passes.

**7. Assembly validation (`validate_assembly` + mesh body_count).**
`ValidationReport` gains `body_count` (None for pre-A1 persisted rows;
every new measurement fills it, passed requires 1) — a watertight mesh of
TWO closed bodies was the phase's most dangerous silent failure (plan
§8.5) and is now caught at both B-rep and mesh level.
`AssemblyValidationReport` carries per-element masses from the manifest
(a fused mesh has no single material — one mass_kg would be fiction for
mixed materials) and cross-checks mesh volume against the exact fused
B-rep volume (2%).

**Verification (see also ADR-033 for a test-hermeticity incident found
during this slice's full-suite run).** 45 new tests (test_primitives.py,
test_assembly.py);
`scripts/gate_phase6a1_auto.py` PASSES at $0: signed envelopes printed,
ADR-030 enforcement, the canonical hash byte-identical, an eight-case
refusal battery with real numbers, the three-primitive gate composition
watertight (body_count 1 both levels, conservation delta 0.0000%), and
byte-identical assembly STEP across two separate processes
(`529014af…`). Slice A2 (spec→plan mapping, two-tier prompt surface,
primitive-agnostic API/frontend, DB manifest persistence) is next; the
operator-facing visual gate arrives there, where there is something to
look at.

---

## ADR-033 — Test hermeticity: key env vars are forced EMPTY, never deleted (2026-08-20)

**Incident, reported honestly (Rule 12).** During slice A1's full-suite
run, executed with the repo bind-mounted into the backend image
(`docker run -v <repo>:/repo -w /repo`), the "hermetic" test fixture
deleted the three provider key env vars — but pydantic-settings reads a
`.env` FILE from the working directory as a fallback when the env var is
absent. The repo root contains the operator's real `.env`, so the
providers were CONFIGURED inside the suite, and
`test_live_run_without_keys_fails_honestly` — a test whose purpose is to
prove the no-keys failure path — POSTed a real Council session that could
DISPATCH REAL PROVIDER CALLS. The test failed (it expected the honest
500), which is how the leak surfaced. A follow-up single-test repro was
killed ~6 minutes in once the cause was understood.

**Spend exposure.** The suite's session ran against a fresh temp database,
so the ADR-003 caps ($5 session / $25 day) were enforced but with full
headroom, and the audit rows died with the container — the local audit
trail is GONE (the exact failure mode Rule 8 exists to prevent, here in a
context nobody had classed as spend-capable). Bounded worst case: one full
Council session (~$0.84 at Phase 3 measured rates) plus a partial second
from the killed repro. **The provider consoles are the only source of
truth; the operator has been asked to check all three for calls in the
suite's window (2026-08-20, ~09:35–10:10 EAT).**

**Why the baked-image runs never hit this:** `.dockerignore` excludes
`.env`, so `/app` has no dotenv file and compose-injected env vars were
genuinely removed by delenv. The leak needed cwd == a repo checkout — the
exact environment of local dev loops and of any future CI checkout. This
is the ADR-019 class again: environment state (here, dotenv fallback
semantics) silently crossing a boundary it was assumed not to cross.

**Fix (standing rule).** The autouse `_hermetic_env` fixture and the
council no-keys test now SET the three key vars to the EMPTY STRING
instead of deleting them: an env var, even empty, takes precedence over
the `.env` file in pydantic-settings, and an empty key is falsy at the
`call_log` pre-dispatch check, so every provider path resolves to the
honest "not configured" ProviderError BEFORE any network traffic —
regardless of cwd, mounts, or what `.env` exists. The fixture also clears
the `get_settings` lru_cache on entry AND exit. Verified: the previously
failing test now passes from the mounted repo checkout with the real
`.env` present; `provider_keys_status` reports configured=False on empty
keys (bool("") is False).

**Standing rule for future tests:** a test that must simulate a missing
credential sets it to empty; `delenv` is never sufficient in a
pydantic-settings codebase. Never assume a test is offline because the
environment variables are gone.

---

## ADR-034 — Diagnostic build mode: a workshop-limit breach returns geometry (2026-08-21)

**Status:** accepted, implemented in Phase 8.

### Context

`assemble()` raised `ConstraintViolation` for `mass > max_lift_kg` and
`bbox > max_module_m` *before* returning a manifest. Two consequences:

1. The operator got a 422 and nothing to look at. He could not see the piece
   that was too heavy, only a sentence saying it was.
2. The Phase 8 fabrication gate could never fail in the live API path — the
   build 422'd first, so no fabrication report was ever written for a
   failing design. The gate re-checked numbers that had already passed by
   construction, and only "failed" against hand-built dicts in tests. Phase 8
   was duplicating a Phase 6 constraint rather than adding a layer.

### Decision

`assemble(..., strict: bool = True)`.

* `strict=True` — unchanged behaviour. A limit breach raises. **The AI
  fabrication loop keeps this.** Generated code that produces an unbuildable
  part must be refused, not discussed.
* `strict=False` — the operator-facing API. Geometry is built and returned;
  limit breaches ride out in `manifest["fabrication_limit_violations"]` and
  become failing rows in the Phase 8 fabrication gate.

The distinction is **only** about declared workshop limits. Geometric and
material prerequisites — unknown primitive, undeclared interference, wall
outside the material envelope — still raise in both modes, because without
them there is no solid to look at.

### Consequences

* The operator sees a 1550 kg basin in the viewport *and* the row that says
  `basin_01.mass_kg 1550.02 limit 50.0 FAIL`.
* The fabrication gate becomes a real layer with a reachable failure path.
* Signed Phase 6 behaviour is preserved for every existing caller: `strict`
  defaults to `True`, so only the new API route opted in.

---

## ADR-035 — Byte-canonicalization: two exporters were non-deterministic (2026-08-21)

**Status:** accepted, implemented in Phase 9A.

### Context

Proving the LUXEXCHANGE package reproducible surfaced two defects that had
nothing to do with geometry, one of them a live breach of Rule 5.

**STEP — OpenCASCADE's process-global occurrence counter.** Exporting the
same solid twice inside one Python process gives:

```
-#224 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('1','=>[0:1:1:2]','',#5,#27,$);
+#224 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('2','=>[0:1:1:2]','',#5,#27,$);
```

OCCT numbers occurrences from a counter that lives for the life of the
**process**, not the file. Every gate to date ran one build per process, so
the counter was always at 1 and this went unseen for four phases. In the
long-running backend it means two builds of the same Design Spec produce two
different `geometry_hash` values — a visible breach of the determinism
guarantee, found 2026-08-21.

**DXF — random GUIDs and wall clocks.** ezdxf writes `$FINGERPRINTGUID` and
`$VERSIONGUID` as fresh random GUIDs on every save, plus `$TDCREATE` /
`$TDUPDATE` Julian timestamps and a `<version> @ <ISO>` marker.

**A third, in the drawing itself.** OCCT returns section faces in an order
that varies between runs — the same set, a different sequence. The DXF
writer emits entities in the order given, so the drawing bytes moved even
though the drawing was identical.

### Decision

`backend/app/geometry/canonicalize.py`, applied inside `export_step` and the
DXF writer. **Metadata only — never a coordinate, never a topology
reference.**

* STEP: renumber `NEXT_ASSEMBLY_USAGE_OCCURRENCE` ids sequentially from 1 in
  order of appearance. Ids stay unique within the file, which is all they
  are for.
* DXF: replace both GUIDs and every group-40 time variable with values
  derived from the seed.
* Drawing shapes are sorted on a geometry-derived key (world bbox, then
  area, then length) before being written.

### Why this does not invalidate the canonical hash

A file exported first in a fresh process already had `'1'`, so
canonicalization is a no-op on it. The Phase 2 canonical STEP sha256
`e1a59fa6…` — proven cross-machine 2026-08-04 — still reproduces
byte-for-byte, asserted by `scripts/gate_phase6a1_auto.py` section 3, which
was re-run after this change and passed.

### Consequences

* Rule 5 now holds inside a long-running process, not only across fresh ones.
* The determinism guarantee extends from the canonical STEP to the whole
  delivered package.
* Anything OCCT or ezdxf adds in a future version could reintroduce this.
  `scripts/gate_phase9a_auto.py` exports twice and compares, so a regression
  fails the gate rather than reaching a fabricator.

---

## ADR-036 — Four validation statuses; `needs_input` is not a warning (2026-08-21)

**Status:** accepted, implemented in Phase 8.

### Context

The Phase 8 foundation slice had three statuses, and `warn` was doing two
incompatible jobs: *"we checked and it is marginal"* and *"we could not
check at all"*. Worse, `LayeredGateReport.passed` was defined as
`status != "fail"`, which flowed through `ValidationReportRow.passed` and
the API to `ValidationPanel`, where the header rendered
`validation.passed ? "PASS" : "FAIL"`.

**A design warned on every layer displayed a green PASS badge** — precisely
what that phase's own gate criteria forbade. In the real flow nothing
populated the water context, so the hydraulic gate *always* returned that
warning: every design ever built showed PASS for hydraulics that had never
been evaluated.

`severity` was also assigned `"fail"` when a check failed and `"info"` when
it passed — a restatement of the outcome, not a property of the check. There
was no way to express "this is a warn-level check and it was violated".

### Decision

Four statuses, rolled up worst-first: **`fail` > `needs_input` > `warn` >
`pass`**.

* `needs_input` — the check could not be evaluated. Never a pass, never a
  warning. The row names the missing field and where to get it.
* `passed` is redefined as `status == "pass"`, everywhere: model property,
  `validation_reports.passed` column, API `passed`, UI badge.
* `GateCheck` separates **policy** (`on_violation`, declared up front) from
  **outcome** (`status`).
* Every check carries `basis` — the provenance of its limit. Rule 11 becomes
  structural rather than aspirational: an empty basis fails the test suite.
* Non-finite values are sanitised to `None` on construction. `json.dumps`
  emits bare `Infinity`, which is not valid JSON and would break any strict
  parser reading a persisted report or a shipped package.

`config/gate_profiles.yaml` carries the thresholds, versioned, each with its
arithmetic or its source of judgement recorded — following the precedent set
by `materials.yaml` (ADR-027/029/032): operator-set, tunable, **not**
citations of an external standard.

### The `signed_off` switch

Site and policy thresholds — design wind speed, allowable bearing pressure,
overturning safety factor — ship **empty**. No honest default exists: a
presumed bearing pressure varies by more than ten times between soft clay
and rock, and inventing one would be exactly the fabrication Rule 2 forbids.

While a profile has `signed_off: false`, every gate still runs and reports
real measured numbers, but a breach of one of *that profile's* thresholds
reports `warn` instead of `fail`. Nothing is blocked on a number nobody has
approved. Material and Design Spec limits are always binding — they were
signed when they were entered.

### Consequences

* `structure_static_v1` is renamed so nobody reads it as FEA, and gains
  overturning and ground-bearing checks — the two that decide whether a
  monument is safe where it stands.
* Wind pressure uses ISA density at the site altitude. Addis Ababa at 2355 m
  is ~0.97 kg/m3 against 1.225 at sea level: using sea level would overstate
  every wind moment LuxuryCon produces in its own city by about 26%.
* The centre-of-mass check now weights real per-element mass centroids
  against a world-space footprint. The previous version weighted *placement
  origins*, and since every element the system produces sits at x=0,y=0 it
  computed exactly 0.0 for every design ever built — a check that could not
  discriminate. `gate_phase8_auto.py` section 5 now shows a built fountain at
  safety factor 24.9 and an 8 m mast on the same base at 0.698.
* Hydraulic limits are derived, not hardcoded. The nozzle bore comes from
  continuity, `d = sqrt(4Q/(pi*v))`, replacing a literal `3..150 mm` range.
* Phase 8 cannot fully close until Phase 12 supplies water and site context
  from brief intake. `needs_input` is accepted as a legitimate terminal
  status for that layer, with a Phase 8b re-gate after Phase 12.

---

## ADR-037 — Export is a job; the package is reproducible and self-verifying (2026-08-21)

**Status:** accepted, implemented in Phase 9A.

### Context

The Phase 9 foundation slice had `GET /latest/luxexchange.zip` **write files
to disk and insert database rows on every request**. Measured 2026-08-21:
three downloads produced nine export rows, and three different ZIPs.

```
download 0  bytes 27563  sha 8f7e03bd…
download 1  bytes 27564  sha 621ae78c…
download 2  bytes 27564  sha 4ee43b15…
export rows: [('GLB', 3), ('LUXEXCHANGE', 3), ('STEP', 3)]
```

The slice's own gate said "the package can be re-opened and its hashes
verified". Nothing verified anything, no checksum file existed, and the
manifest carried no digest of itself.

It also reported eight formats as "not implemented" that the running image
could already write. Probed live (ADR-009): build123d 0.11.1 has
`export_stl`, `export_brep`, `ExportDXF`, `ExportSVG`; trimesh 5.0.0 writes
obj/ply/dae/3mf; ezdxf 1.4.4 is installed. Under-claiming misinforms the
operator about what he can send a fabricator today.

### Decision

**Export is a POST that creates a job.** `GET` reads status and serves
artifacts, never mutates. `exports` gains `sha256`, `bytes`, `duration_ms`,
`status`, `error`, `job_id` and a **unique index on (design_id, format)**
with upsert. Hashes are computed once at export time, not on every UI poll.
The job reuses the existing generic `JobRow` with `job_type="export"` — the
first real consumer of the job model Phase 13 must harden, so Phase 13
inherits a working example instead of a retrofit.

**Ten formats, four statuses.** `included` / `failed` / `unavailable` /
`impossible`, mirroring the costing layer's four line statuses (ADR-031).
A missing *optional* library reports `unavailable` naming the pip package —
not `failed`, which would send the operator hunting a bug that is really a
one-line install. One exporter throwing never aborts the package.

DWG and SKP are `impossible`, and `README_DWG_SKP.txt` **travels inside the
package** rather than linking to `LIMITATIONS.md`, so a fabricator reading it
offline still learns what to do.

**The package is byte-reproducible.** Fixed seed-derived entry timestamps,
sorted names, pinned compression level, pinned `create_system`. Provenance is
keyed to the *design*, not the export run — using the export wall clock would
make the bytes differ for a reason that has nothing to do with the design;
when the export ran is recorded on the job row, where a timestamp belongs.

**The package verifies itself, without us.** `CHECKSUMS.sha256` covers every
content file; `content_digest` is the sha256 of that file, recorded in
`provenance.json` (which is excluded from the checksum set, avoiding
circularity and keeping the digest stable across hosts).
`verify_luxexchange.py` ships **inside the ZIP** and imports only the
standard library. A checksum that only this repository can verify is
decoration, not integrity.

**Manifest paths are relative to the package.** An absolute host path would
make the digest depend on where the file was written, and would ship the
operator's filesystem layout to whoever receives it.

### Consequences

* Ten formats produced today at zero bandwidth cost, against two before.
* The DXF is a real drawing: a true plan section plus a hidden-line front
  elevation, laid out side by side on PLAN / ELEVATION / HIDDEN layers.
* Rule 5 extends from the canonical STEP to the deliverable.
* Phase 9B (Blender render worker) remains the only part needing a download,
  in its own image so a failed pull cannot invalidate the expensive OCCT
  layer. Phase 9A closes without it.

---

## ADR-038 — DesignDNA: the package digest is the precedent's identity (2026-08-22)

**Status:** accepted, implemented in Phase 11.

### Context

Phase 11 needed an identity key for an accepted design. The obvious
candidate was the geometry hash (`step_sha256`), which Rule 5 already
guarantees is stable for a given spec and seed.

It is the wrong key. Two designs can share a STEP byte-for-byte and still be
materially different precedents: a different material, a different gate
profile, a different validation outcome, a different BOM. A geometry hash
cannot tell them apart, so a memory keyed on it would silently collapse
distinct precedents into one.

### Decision

A precedent keys on the LUXEXCHANGE **`content_digest`** (ADR-037), which
covers geometry + Design Spec + validation reports + BOM together.

The consequence is the useful part: **a design must have an export package
before it can be accepted.** A precedent is the accepted *deliverable*, not
a half-finished shape, and this enforces the pipeline order
(build → validate → export → accept) instead of letting unfinished work into
the house memory.

Two further invariants:

* **Acceptance is an event with an author.** `accepted_by` and
  `acceptance_note` are required and non-empty. A precedent that cannot say
  who accepted it and why is not auditable, and it will be injected into
  paid Council prompts for years.
* **A failing design cannot be accepted.** If the validation rollup is
  `fail`, acceptance is refused. Memory must not teach from work that did
  not pass.

### Retrieval is explainable before it is clever

Deterministic AND-matching over measured tags, with a named reason per
matched field:

    material basalt_slab · water design · height 2.4 m within 1.20-3.60 m

No embeddings. The operator has no coding background and must be able to see
WHY a precedent surfaced and argue with it when it is wrong; an
unexplainable similarity score cannot be debugged. Local embedding search
stays available as a later additive slice (Rule 7 forbids sending project
data anywhere), but it is not the first answer.

### Injection is quarantined

Precedents enter a Council prompt inside a delimited block that states their
numbers describe PRIOR work and explicitly forbids copying a dimension over
one stated in the brief. Without that framing the Council copies a
precedent's 2.4 m basin into a brief that asked for 1.2 m. Injection is
capped at three precedents per session.

### Archive and delete are different operations

* `archive` hides from retrieval, keeps the record — old sessions that cite
  it stay coherent.
* `delete` wipes the payload and leaves a **tombstone** carrying the id, so
  a session that cited it reports "precedent deleted" rather than dangling.

Treating these as one flow, as the original plan did, loses one guarantee or
the other.

---

## ADR-039 — Intake: every field carries its provenance (2026-08-22)

**Status:** accepted, implemented in Phase 12.

### Context

The Phase 8 hydraulic gate was inert for an entire phase because nothing
populated its water context, and its inputs were free-form `dict | None`
fields with no schema. The review named the fix: typed contexts, born at
intake.

But typing alone is not enough. A value of `15.0` in a form tells you
nothing about whether the operator chose it, an AI read it out of the brief,
it is a shipped default nobody looked at, or it is simply absent.

### Decision

Every intake field is a `Sourced[T]`: a value plus a **source** — one of
`operator | parsed | default | unknown` — plus, for parsed fields, the exact
brief sentence it came from.

This is the honesty mechanism end to end:

* `unknown` is distinguishable from `default`. A defaulted freeze risk that
  nobody checked is not a confirmed one.
* `unknown` propagates to the Phase 8 gates as `needs_input`, never as a
  guessed number that quietly passes.
* the operator can check the parser against the client's own words, because
  the quote travels with the value.

**The parser fills the form; it never decides.** A field sourced `operator`
is never overwritten by a machine. The parser also cannot invent fields
outside the schema, cannot coerce a type, and is instructed to OMIT anything
the brief does not state rather than guess it.

### Requirements are ranked by what a gap blocks

Not all gaps are equal, so they are tiered: 1 blocks geometry, 2 blocks a
validation gate, 3 blocks costing, 4 affects design quality only. Tiers 1
and 2 must be answered before paid Council calls; 3 and 4 may stay unknown
with the downstream consequence stated on screen.

Applicability is part of it: an indoor piece is never asked for a wind
speed, because there is no wind case to feed.

### Site facts belong to the project, not the profile

`site_altitude_m`, `design_wind_speed_m_s` and `allowable_bearing_kpa` are
facts about where a specific piece stands. They are supplied per project
through the intake and applied OVER the gate profile
(`validate_layered_gates(site_overrides=...)`), with two guarantees:

* the structural report gains a `site_overrides` row naming every replaced
  threshold, its value AND its source, so a report read a year later never
  looks like a plain profile run;
* `signed_off` semantics are unchanged — an unsigned profile still
  downgrades threshold breaches to `warn`, whoever supplied the number.

The overturning safety factor is deliberately NOT overridable: it is a
policy value a structural engineer signs, not a site measurement.

### This closes Phase 8b

With a confirmed intake, the hydraulic gate reaches a real
pass/warn/fail verdict and the structural gate computes real wind pressure
and bearing — with no hand-injected context and no profile edit. Proven by
`scripts/gate_phase8b_auto.py`.

---

## ADR-040 — Two ledgers must agree, and the UI shows the disagreement (2026-08-22)

**Status:** accepted, implemented in Phase 13 slice A.

### Context

Rule 8 requires every AI call to be auditable. The system already logged
calls two ways: per call in `ai_calls`, and as a running total on the
session row maintained by the budget enforcer.

A cost dashboard that sums one of those books and displays the number proves
nothing — it is one record agreeing with itself.

### Decision

`/api/ops/costs` **reconciles** the two books and reports the result as a
first-class finding, not a footnote. Agreement is evidence; disagreement
names the session ids and the nature of the gap. The status bar carries a
LEDGER MISMATCH badge on every screen when the books disagree.

Failed calls are reported on their own line. A provider that billed a failed
attempt still cost money, and a flaky connection must not read as work done.

### Failure classes decide the next action

A job failure records one of four classes — `transient`, `resource`,
`input`, `defect` — because grouping everything as "error" leaves the
operator with nothing to do. Only transient failures should be retried:
retrying a defect burns money and hides the bug; retrying an input error
burns money and can never succeed.

### Restore must prove itself

Backup uses SQLite's online backup API, never a file copy of a live database
(which snapshots a torn WAL state and corrupts silently).

Restore then **proves** itself two ways: table row counts against the
manifest written at backup time, and — the strong one — re-running the
LUXEXCHANGE package's own shipped stdlib verifier (ADR-037) against the
newest restored package. "The files are there" is not a restore proof; a
package that re-verifies is.

A corrupt archive produces a named finding, not a traceback. The operator
reads that output to decide whether to trust a restore, so it must be
readable.

---

## ADR-041 — The pipeline is the interface (2026-08-22)

**Status:** accepted, implemented alongside Phases 11-13a.

### Context

The UI had grown to a flat row of tabs — Cascade viewport, Assembly, AI
Council — with new phases each wanting another. A tab row says what screens
exist. It does not say what the operator should do next, which is the actual
question in front of someone running a job.

### Decision

The product is one workflow: **brief → council → build → validate → export →
accept**. The shell makes that the primary navigation: a persistent stepper
across the top, with the tool views (Cascade, Operations) grouped
separately, so "where am I in the job" is never confused with "which tool".

Three rules:

1. **Every step state is DERIVED, never stored.** A stored flag drifts out of
   sync with reality and starts lying; the stepper reads the same data the
   panels read. `Validate` shows FAIL because the rollup says fail, not
   because something set a flag.
2. **Colour never carries meaning alone.** Each step shows a glyph
   (`✓ ! ● ○`) and a text detail, so the state survives a screenshot and a
   colour-blind reader.
3. **The numbers that must never require a click live in a status bar:**
   backend reachability (polled, so it is true even when idle), the loaded
   design, its validation rollup, total spend, ledger health, precedent
   count.

CSS moved to role-named design tokens (`--bg-panel`, `--ok`,
`--danger`, `--info`) so a surface is restyled once rather than by hunting
hex codes. `needs_input` keeps its own colour, distinct from warn — the
distinction ADR-036 established in the data must survive into the pixels.


---

## ADR-042 — Phase 5: render worker + bounded vision critique (2026-08-22)

**Status:** accepted. Critique loop implemented 2026-08-22. The render worker
this ADR assumes did NOT exist on that date — it was designed here and built
on 2026-08-24 under ADR-043, which also records where reality differed from
the design below (STEP vs GLB, and the consensus tolerance in point 4).

### Context

Phase 5 closes the render → vision-critique → bounded-delta loop from ADR-007.
The loop is bounded by `max_vision_iterations` from `config/budget.yaml`, uses
two-provider consensus (Anthropic + OpenAI, Kimi as tiebreaker only), and
anneals the permitted delta magnitude each round to prevent oscillation.

### Decision

1. **Render worker is a separate container** mirroring the geo-worker shape:
   non-root, no network, read-only filesystem except a dedicated scratch mount,
   CPU and memory limits.  It runs headless Blender 4.5.12 LTS via
   `blender -b -P render_scene.py`, not `bpy` as a Python module, because the
   standalone Blender distribution is already fetched and pinned.
2. **Backend only orchestrates.**  `app.render.queue` writes job manifests to
   `/scratch` and polls for `result.json`, exactly like `app.council.fabricate`.
   The backend never renders itself.
3. **Vision deltas are strict JSON.**  The prompt requires a single JSON object
   with `observations` (prose that cannot be a delta) and `deltas` (each with
   `parameter_path`, `direction`, `magnitude`, `unit`).  Anything not matching
   the schema is recorded as an observation.
4. **Consensus requires both providers to agree** on the same parameter path,
   same direction, and magnitude within relative tolerance.  Disagreement is
   resolved by Kimi as a tiebreaker only, per `council.yaml`.
5. **Annealing.**  Round 1 permits up to 10% of a parameter's validated range;
   each subsequent round halves the limit.  This converts a loop that can
   oscillate into one that converges.
6. **Objective score.**  "Measurably improves" is scored from geometry facts
   the platform already computes (constraint margin, mass vs handling limit,
   silhouette stability across ortho views), not from the panel's own
   subjective score, so a model cannot grade its own homework.

### Consequences

- The live loop needs the render-worker container to be running; the auto gate
  exercises the loop offline with scripted render fixtures.
- Cycles CPU is the only renderer; EEVEE is explicitly out of scope because it
  requires a GL context and the operator has no dedicated GPU.
- The operator visual gate verifies three real rounds on their own machine,
  with before/after renders and logged deltas.


---

## ADR-043 — Phase 9B: the render worker as actually built (2026-08-24)

**Status:** accepted, implemented and gated 2026-08-24
(`gate_phase9b_auto.py` PASS).

### Context

ADR-042 specified the render worker; it did not exist. Blender 4.5.12 LTS had
been fetched and extracted on the host, and a first attempt at the container
had failed partway: `debs.txt` listed 57 packages whose pool paths were partly
invented (mesa under `libg/libglvnd/`, a `t/tfonts-ubuntu/` directory that does
not exist, epochs like `1%3a19.1.7` written into filenames that never carry
them), `sums.txt` was never produced, and the fetch died on the fourth package.
This ADR records what the working worker actually does and where it departs
from ADR-042.

### Decisions

1. **Seventeen debs, derived empirically, and no mesa.** Extract Blender in a
   bare `python:3.11-slim-trixie`, read `ldd`'s nine missing sonames, resolve
   those to packages, let apt compute the closure against the same dated
   snapshot the backend pins, and take the real pool paths from
   `apt-get install --print-uris`. Then install, confirm `ldd` reports nothing
   missing, and render an actual PNG.

   apt's full closure pulls `libgl1-mesa-dri` → `mesa-libgallium` →
   `libllvm19` → `libz3-4`, roughly 45 MB, for a GLX *vendor* that is only
   dlopened when a real GLX context is created. A headless Cycles CPU render
   never creates one; `libGL.so.1` only has to load. Dropped, exactly as the
   backend does at ADR-017, with `dpkg -i --force-depends`.

   The rule from ADR-009 applies to distro packages too: every path here came
   from a live resolver against the pinned snapshot, none from recall.

2. **The worker renders GLB, not STEP.** ADR-042 assumed the STEP artifact.
   Blender has no STEP importer, and this image deliberately carries no OCCT —
   that is the backend's stack, and putting it here would rebuild the thing the
   separate image exists to avoid. The GLB the viewport already uses
   (`app.geometry.exporters.export_glb`) is Blender's best-supported import
   path, so `RenderJob.input_step` became `input_mesh` and the API renders
   `design.glb_path`.

3. **The handoff is basename-only, in both directions.** The geo-worker's
   ADR-028 trick — same host dir at the same in-container path, so absolute
   paths cross verbatim — is unavailable here: `/scratch` on the backend is
   already the geo-worker's mount, so the backend sees the render scratch at
   `/render_scratch` and the worker at `/scratch`. Every filename in
   `job.json` and `result.json` is therefore a basename that each side
   resolves against its own view of the job directory. `submit()` stages the
   mesh into the job directory, which also pins the job to the geometry as it
   was at submit time.

4. **Extraction uses Python's lzma, not `tar -xJf`.** The base image ships GNU
   tar but no `xz` binary, and tar shells out to xz for `.tar.xz`. Adding
   `xz-utils` would mean an eighteenth pinned deb carried solely for build
   time. `tarfile.open(..., "r:xz")` is already in the image and preserves the
   symlinked sonames Blender's bundled libraries depend on.

5. **Clay render, pinned colour management, fixed threads and seed.** Every
   part gets one neutral matte material: the critique judges proportion,
   silhouette and composition, and colour or material realism gives the model
   things to comment on that the geometry pipeline cannot act on. The view
   transform is set to AgX by name rather than inherited — Blender's default
   changed from Filmic to AgX between releases, and a silent shift in tone at
   the next version bump would read to the loop as the design having changed.
   Cycles threads are pinned rather than AUTO for the same reason: on AUTO the
   image depends on how busy the host was, and two rounds stop being
   comparable.

   Light energies were tuned against measured renders. The first values put
   the subject at a mean luminance of 211–236 of 255 — not clipped, but with
   too little headroom to separate a lit face from a highlight, which is the
   separation the critique reads proportion from. They now land at 154–188.

6. **The gate refuses to accept "four files exist".** The likeliest failure
   here is four plausible-looking frames of nothing. `gate_phase9b_auto.py`
   builds a known solid through the production exporter, then asserts real
   tonal variation per view, a plausible subject share of the frame, six
   distinct view pairs, and the bounding box Blender actually received.

   That last check earned itself twice on the day it was written. Built with
   trimesh's own Scene export, the model arrived rotated onto its side; built
   with metre-valued numbers, it arrived 1000× too small (build123d is in
   millimetres and `export_gltf` converts to metres). Both rendered as
   perfectly competent pictures — the camera rig frames whatever it is given.
   Neither would have been caught by eye, and only the numeric assertion
   distinguishes them.

7. **Consensus tolerance is 0.20, not the 0.05 ADR-042 point 4 implied.** Two
   models proposing +0.030 m and +0.032 m on a tier height are 2 mm apart and
   6.25% apart relatively, and were being scored as disagreeing — so the loop
   accepted nothing in the common case. Consensus asks whether two independent
   models found the same problem and the same direction, not whether they agree
   to two significant figures, which is not something a language model's
   magnitude estimate can honestly deliver. Widening is safe because magnitude
   is not trusted from the model anyway: whatever survives is clamped to the
   annealed step limit derived from the parameter's validated range. The model
   chooses the direction; the engineering envelope chooses how far. The agreed
   magnitude is now the smaller of the two proposals rather than the first
   provider's, which is both conservative and symmetric — previously, swapping
   the provider order silently changed the design.

### Consequences

- `docker compose --profile render up -d render-worker` is required for live
  renders; the service sits behind a profile so a plain `docker compose up -d`
  on a machine that has not fetched the 360 MB tarball still starts the
  backend rather than failing the whole command.
- The Blender tarball and its extracted tree are host-side build inputs and are
  gitignored; `debs.txt` and `sums.txt` are committed, so the image is
  reproducible from the repo plus one resumable download.
- Measured on the operator's i7-8550U with 2 threads: four views at 256²/16
  samples in ~29 s, four at 512²/32 samples in ~2 min. The critique loop's
  per-round render cost is minutes, not seconds, which is what
  `max_vision_iterations` has to be sized against.

## ADR-044 — Phase 14: the Designer Workspace (2026-08-24)

### Context

Through Phase 13 the UI could drive the pipeline but not really *design* in
it: the assembly was a hardcoded three-element demo, the viewport was one
fused, unselectable body, and judging two ideas against each other meant
rebuilding and remembering. The operator's directive for this phase: move
from "the system can build a design" to "a designer can shape, judge,
compare, and refine a design with confidence."

### Decision

1. **The document is the request.** The workspace edits a design document
   whose shape IS the assembly build request (elements + joints +
   fabrication + seed + gate profile). Undo/redo is a snapshot stack over
   that document. There is no second representation to drift.

2. **Build-to-see, kept visible.** The viewport renders the last BUILT
   geometry, never a browser-side approximation of unbuilt edits. Editing
   marks the workspace dirty ("UNBUILT CHANGES"); *Build & validate* is the
   only bridge from document to pixels. This is Rule 5 as UI: the kernel
   draws; the browser edits the program the kernel will receive. A
   consequence accepted deliberately: no live preview while dragging a
   parameter — every build is a full OCCT fuse plus gate run (seconds on
   the operator's machine), and pretending otherwise would mean a second,
   untrusted geometry path.

3. **Selection comes from a per-element scene GLB, not from the fused
   artifact.** `assemble()` already places every element's solid before
   fusing; `return_solids=True` now exposes them (a keyword addition — the
   Phase 6 two-tuple return is unchanged, proven by the gate). A new
   `scene.glb` is written at build time next to `assembly.glb`: same
   geometry, same tessellation constants, one glTF node per element, node
   name == element_id. Composition goes through trimesh (an existing
   dependency); build123d/XCAF label export was NOT used because its node
   naming behaviour is undocumented for our version and ADR-009 forbids
   trusting recalled behaviour — the gate instead parses the emitted binary
   and asserts the node names match, so the property is proven per run.
   `assembly.glb`, STEP, and their hashes are byte-for-byte unaffected;
   scene.glb sits outside the determinism contract exactly as the fused GLB
   always has.

4. **Old designs regenerate their scene lazily.** GET
   `/{design_id}/scene.glb` rebuilds a missing scene.glb from the stored
   request (deterministic, cached to disk, no DB write). A config drift
   that makes an old design unbuildable returns 409 with the real
   violations rather than a fake file.

5. **Per-design reads and a design list.** `/{design_id}.glb`,
   `/{design_id}/manifest`, `/designs` — history restore and side-by-side
   compare need designs that are no longer "latest". The history strip's
   truth is the server list; thumbnails are real viewport screenshots taken
   when that geometry was on screen, cached per-browser in localStorage,
   with a schematic placeholder when absent — a thumbnail is never
   synthesised from anything but a rendered frame.

6. **Appearance is explicitly a UI concern.** materials.yaml carries
   engineering numbers only; the swatch colours live in the frontend
   (`appearance.ts`), are labelled "identification only", and unknown
   material ids get a hash-derived hue so two new materials never share a
   swatch silently. The honest appearance channel remains the Phase 9B
   render, reachable from the toolbar.

7. **Duplicate places the copy beside its source** (stack_on: x_offset by
   the source's BUILT bbox width + 100 mm), because a copy in the same
   place is an undeclared interference the assembler rightly refuses. A
   concentric_insert copy cannot be offset — the joint model has no slot —
   so the UI says that instead of letting the build fail mysteriously.

### Consequences

- Backend: `docker compose up --build -d` after pulling this commit (both
  backend and frontend images changed).
- `gate_phase14_auto.py` runs its geometry/API sections in the backend
  container and its frontend build section on the host
  (`--frontend-only`); each run states plainly which sections it covered.
- The AssemblyPanel is retired; the Cascade tool remains as the legacy
  single-primitive path.
- No element rotation exists anywhere in the model (joints + translation
  only) — a workspace gesture for it would have nothing to send.


---

## ADR-045 — Phase 9B.5: Blender-tier export, and what a live critique run proved (2026-08-24)

**Status:** accepted, implemented and gated 2026-08-24. Extends ADR-043.

### Part 1 — USD, USDZ, FBX and Alembic are now produced

These four were the last formats the export package could not write; nothing
else in the stack produces them and Blender does. The render worker gained a
second job kind, `convert`, alongside `render`:

- `docker/render/convert_scene.py` imports the GLB and exports every requested
  format in ONE Blender launch. It is separate from `render_scene.py` because
  rendering builds a camera rig, lights and a ground plane that must never be
  baked into a delivered FBX.
- The world is dropped before export. `export_textures=False` alone was not
  enough: the USD exporter bakes Blender's default grey world to a one-pixel
  HDR in a `textures/` folder beside the file, which would ship to a
  fabricator as a file they did not ask for.
- `_blender_writer` in export_formats.py converts every requested
  Blender-tier format in one worker round trip, sharing the result through a
  mutable cache in the export context. Four formats otherwise mean four
  Blender launches — or, when the worker is down, four separate 20-second
  pickup timeouts.
- `ExportUnavailable` was added so a missing render worker reports
  `unavailable` with the exact command that fixes it, rather than `failed`.
  Overloading `ImportError` for this was tried first and was wrong: the
  existing optional-dependency path only recognises module-name messages, so
  the operator saw a raw `ImportError` string and would have gone hunting a
  bug that is really one command.

### Part 2 — they are produced but NOT sealed into the package

Measured, two conversions of the same GLB: USDZ differs by 2 bytes, FBX by 27,
ABC by 1. Embedded creation timestamps — the zip directory, the FBX header,
Alembic's metadata. USD matched, but comes off the same toolchain, so the whole
tier is marked non-deterministic rather than trusting one lucky format.
Byte-patching those fields was rejected: the offsets are undocumented and
version-specific, so it would work until a Blender upgrade moved them and then
silently produce corrupt files.

`FormatSpec.deterministic` now records this, and the LUXEXCHANGE packager
produces such a file and offers it for download but does NOT put it in the ZIP.

**Excluding it from the content digest is not sufficient, and that mistake was
made first.** The digest is only a field; Phase 13a compares the package BYTES.
A non-deterministic file inside the ZIP changes the ZIP whether or not its hash
feeds the digest.

**The same trap has a second floor.** Having removed the bytes, the per-build
sha256 was recorded in `provenance.json` — which is excluded from the digest,
and still a file INSIDE the ZIP. The package bytes changed again. Per-build
facts about these formats live on the `exports` database row, which is the only
place outside the reproducible deliverable. Nothing that varies between two
builds of the same design may appear anywhere inside the package.

The manifest gains `omitted_non_reproducible` (format names only) and per-entry
`in_package` / `excluded_reason`, so a fabricator reading it learns the format
exists and why it is absent, instead of assuming the export failed.

This regression was introduced and caught the same day: it surfaced in a
full-suite run against an image built from the work-in-progress (2026-08-24),
failing `gate_phase9a` §3 and `gate_phase13a` §3, and was fixed before either
gate was allowed to stay red.

### Part 3 — the consensus magnitude gate was destroying real agreement

The first LIVE critique run (2026-08-24, run 5994e1a8ea8e, $0.039, three
rounds against Claude Sonnet 4.5 and GPT-4o) applied ZERO deltas. The models
were not failing to agree — the loop was discarding their agreement.

Round 1, both providers independently: "make the basin taller". Anthropic
+50 mm, OpenAI +30 mm on `b_basin.height_mm`. Same parameter, same direction,
reached independently. The magnitude tolerance threw it away because 50 and 30
are 40% apart.

Consensus asks whether two independent models saw the same problem and the same
direction of fix. It cannot ask them to agree on a number: a magnitude out of a
vision model is an impression, not a measurement. And it need not, because the
number is not used — the smaller of the two proposals is taken and then clamped
to `_annealing_limit`, derived from the parameter's validated engineering range.
The model chooses the direction; the envelope chooses how far.

`DELTA_AGREEMENT_TOLERANCE` is now `None` (no magnitude gate); callers may still
pass a float. **Only a live run could have found this** — the $0 gate's fixture
has both providers proposing nearly the same number, so it never exercised the
case.

Re-run with the gate removed (run 57d90665dcf2, $0.042916, three rounds): 5
agreed deltas, all 5 applied, plinth height 350→535 mm, top diameter
1400→1470 mm, basin height 300→277.5 mm. In round 3 both models independently
proposed `a_plinth.top_diameter_mm increase 200`.

### Part 4 — the prompt has to name the parameter paths

Two further live findings, both fixed in `vision_critique_prompt`:

- The schema example used `tier_height_m` in metres while the real parameters
  are `b_basin.diameter_mm` in millimetres. The example anchors harder than the
  spec summary does.
- GPT-4o returned `a_plinth_taper_deg` — underscores for the dot separator.
  Correctly discarded, and a wasted round.

The prompt now lists the exact allowed paths with their current values and
validated ranges, states the unit once, and describes the image as one contact
sheet of four labelled views rather than "four rendered views" — which is what
is actually sent (see Part 5).

### Part 5 — four views go as one contact sheet

`AIProvider.vision()` takes one image, and that path carries the ADR-005/Rule 8
machinery: the pre-dispatch budget check that raises BudgetHalt before any
network traffic, real cost from real tokens, and the `ai_calls` audit row.
Widening it to a list would have meant reworking per-provider image token
accounting to reach the same place.

Compositing is also better for the task. Every judgement the critique makes —
is the bowl too wide FOR the plinth, does the elevation agree with the plan — is
comparative. A model shown four separate images must recall three of them; shown
a contact sheet it can look. It is cheaper too: one image at 2x linear size
costs far fewer tokens than four at 1x, each carrying its own fixed overhead.
Both providers are shown the SAME sheet — consensus between two models looking
at two different pictures is not consensus.

### Consequences

- Live critique costs about $0.0143 per round for two providers at 320px/16
  samples. Rendering, not the API, is the expensive half — `measure_render.py`
  exists to size `max_vision_iterations` against wall clock.
- The four Blender formats are downloadable but never inside LUXEXCHANGE. If a
  future toolchain makes them byte-stable, flipping `deterministic=True` is the
  whole change.

## ADR-046 — Phase 14b: the Blender-derived interaction layer (2026-08-24)

### Context

The operator's directive: audit every workspace window, then make the tool
feel familiar to designers who know Blender. The audit table is in
`PHASE_14B_BLENDER_UX_PLAN.md`; this records the decisions that will look
deliberate-or-wrong in a year.

### Decision

1. **Adopt Blender's navigation and outliner vocabulary, not its transform
   vocabulary.** Views (1/3/7, 5 ortho, `.`/Home framing, axis gizmo),
   visibility (H, Alt+H, / solo), outliner rename (F2 / double-click),
   Shift+D duplicate, T/N rail toggles, `?` keymap card. G/R/S do NOT
   exist: the placement model is joints + parameters (ADR-044), and a grab
   key that silently edited joint offsets would blur the one honest
   editing path. The keymap card says this out loud.
2. **Keymap deviations from Blender, with reasons:** top-row digits as
   well as numpad (the operator's laptop has no numpad); opposite views on
   Shift+digit rather than Ctrl+digit (Ctrl+digit is browser tab
   switching and cannot be reliably intercepted); LMB-drag still orbits
   alongside MMB (browser users' habit; Blender users' MMB both work).
3. **Two cameras, one truth.** The perspective camera remains the sole
   pose authority; the orthographic twin mirrors it on every sync, and
   ortho zoom is folded back into perspective distance on toggle so the
   model never jumps size. Framing, saved views and snapshots all act on
   the perspective pose (a view saved in ortho loses only its zoom —
   LIMITATIONS §18).
4. **The gizmo and hint line are DOM, not scene objects** — positioned per
   frame from the camera quaternion. No second scene, no render-target
   cost on an iGPU; and the hint line doubles as Blender's status-bar
   mouse legend, which is the single cheapest discoverability feature the
   audit found missing.
5. **Rename re-points joints atomically** in the document reducer, and
   UI state (selection, hide/solo) remaps only when the rename validates —
   the same rules checked in both places so a rejected rename is a no-op
   everywhere. A renamed element reads "unbuilt" until the next build
   because the scene GLB still carries the old node name; the honest state,
   not a cosmetic patch-over.

### Consequences

- UI-only: no backend files changed, so the container gate suite is
  untouched; `gate_phase14_auto.py --frontend-only` covers the compile and
  `gate_phase14b_visual.md` covers the behaviour.
- The workspace keyboard map is inert unless the Designer view is active —
  it must never swallow keys under the Brief or Council forms.

## ADR-047 - Phase 15A: visual hierarchy before more capability (2026-08-24)

### Context

Phase 14 added the requested tools, but every tool became permanent chrome:
Library above Scene, Inspector above Checks above Export, a full-width history
strip, and a toolbar containing editing, building, rendering, exporting and
navigation. The result was functionally complete and visually unfocused.

### Decision

1. **The viewport owns the workspace.** Rails narrow to 220/330 px and Recent
   Builds starts collapsed. Both rails retain keyboard toggles and gain visible
   controls.
2. **Frequency determines permanence.** Scene remains visible; the occasional
   primitive catalog becomes an Add palette. Design, Checks and Output become
   mutually exclusive right-rail tabs.
3. **Build is the primary command.** Render and Export move to Output. Viewport
   tools use one pinned icon system (`lucide-react==1.34.0`, live npm registry
   checked 2026-08-24) rather than operating-system-dependent emoji glyphs.
4. **Do not claim lineage before it exists.** The global newest-design list is
   labelled Recent Builds, not Variants. Slice E will restore the variant name
   only for records with explicit project and parent relationships.
5. **Borrow interactions, not another product's identity.** Existing familiar
   navigation keys remain, but the keymap is named Workspace shortcuts rather
   than advertising a Blender-style product model LuxuryForm does not have.

### Consequences

- Frontend only; geometry and persistence contracts are unchanged.
- Phase 14's frontend gate remains the auto gate for this slice and passes.
- Pixel judgement remains a visual gate because no browser is connected in the
  agent environment.

## ADR-048 - Phase 15B: presentation may interpret names, never limits (2026-08-24)

### Decision

1. The primitive registry remains authoritative for parameter existence,
   type, unit, default, range and engineering note. A frontend presentation
   layer may supply a human label, group and prominence only.
2. Unknown future parameters always fall back to a generated label and the
   Advanced group. Presentation metadata can never hide a registry field.
3. Form, water/service and material controls are primary. Construction fields
   are disclosed as Advanced because they are necessary but not the first
   question a designer asks while judging silhouette.
4. Validation leads with the worst authoritative status and its non-pass rows.
   Full measured tables remain available in the same panel; simplification may
   change reading order, never suppress evidence.
5. The LUXEXCHANGE package is the primary output. Individual formats are
   secondary, still grouped by exact CAD versus triangulated mesh and still
   show unavailable/impossible formats honestly.

### Consequences

- Frontend only; no range or geometry semantics changed.
- The presentation map is deliberately incomplete and fallback-safe.
- Existing Phase 14 frontend gate passes.

## ADR-049 - Phase 15C: a draft is real CAD without a build claim (2026-08-24)

### Context

Phase 14 showed the last full build after every edit. That protected the
validation contract, but made proportion work blind until the operator paid
the full STEP, gate and persistence cost. A browser-side approximation would
be faster but would violate the product's central CAD truth.

### Decision

1. Draft preview calls the same `assemble(..., strict=False)` path as a full
   assembly and exports its named solids to a temporary GLB. It does not export
   STEP, run layered validation, or write designs and validation reports.
2. Draft responses carry a content hash, measured build duration and element
   count. These are provenance and timing facts, not acceptance evidence.
3. The client waits 550 ms after the last edit, aborts the prior request and
   ignores any response whose sequence or request JSON is no longer current.
4. The viewport labels draft geometry as CAD-derived and unvalidated. Render,
   fabrication package and individual exports remain blocked until a canonical
   full build matches the document.
5. Preview files live only in an OS temporary directory for the duration of the
   request. Project history is therefore still a history of intentional full
   builds, not every slider movement.

### Consequences

- Designers can judge form before committing a full validation build without
  introducing a second geometry implementation.
- The route is intentionally CPU-heavy. The gate assembly took about 4.7
  seconds on the operator-class machine; debounce limits churn but does not
  promise real-time sculpting.
- `gate_phase15_auto.py` proves named CAD nodes, zero preview persistence,
  stable request hashing, unchanged deterministic STEP output and frontend
  production compilation.

## ADR-050 - Phase 15D: separate form judgement from technical inspection (2026-08-24)

### Decision

1. Studio and Technical are presentation modes over the same loaded CAD scene.
   Studio uses a neutral ground, ACES tone mapping, one bounded shadow light and
   a measured 1.7 m staff. Technical uses the adaptive grid and flatter light.
2. The ground, light and shadow camera derive from model bounds. The staff is
   fixed at 1.7 scene units because the GLB unit contract converts metres on
   import; it is a dimension reference, not a decorative human silhouette.
3. The Add palette previews one focused primitive at a time through the Phase
   15C kernel route. Starting every registry primitive concurrently would turn
   opening a palette into several seconds of avoidable CPU contention.
4. A/B cameras mirror orbit changes. The comparison also loads both immutable
   build requests and lists changed values, because silhouette alone cannot
   explain which design decision produced it.
5. Studio lighting and identification tints remain viewport aids. Only the
   Phase 9B Blender output may be described as a material or presentation
   render.

### Consequences

- Designers can switch quickly between proportion judgement and exact working
  inspection without changing the design or rebuilding geometry.
- `gate_phase15_auto.py` builds every primitive currently returned by the live
  registry as a named GLB and proves the operation remains non-persistent.
- Shadows add one 1024 px map only in Studio mode; Technical mode and its
  common editing loop retain the lower GPU cost.

## ADR-051 - Phase 15E: projects scope variants; parents record branches (2026-08-24)

### Context

The schema has carried an unused `projects` table since Phase 1, while every
assembly build lived in one newest-first global list. Calling that list
Variants would be false: restoring an older build and editing it recorded no
relationship to its source.

### Decision

1. Activate the existing projects table instead of creating a competing model.
   Project names are operator-authored; status is `open` or `archived`.
2. Add nullable `project_id` and self-referencing `parent_design_id` columns to
   designs through the idempotent startup patch system. NULL means Ungrouped or
   root, preserving all old rows without inference.
3. A parent must be an assembly build with exactly the same project ID as its
   child. Unknown, archived and cross-project relationships fail before CAD
   generation.
4. Project and parent are provenance, not geometry inputs. They stay outside
   `assembly_request_v1` and its spec hash, preserving deterministic STEP for
   identical design parameters.
5. The workspace scopes history to one project. Building from the active design
   records that design as parent; reopening an ancestor before Build creates a
   branch rather than rewriting history.

### Consequences

- Existing records appear under Ungrouped and remain fully usable.
- Project lists and parent lookups are indexed additively.
- Lineage is explicit but the UI remains a compact horizontal tray, not a full
  graph editor. That honest display limit remains documented.

## ADR-052 - Phase 6 slice A2: one persistence path from fabrication to design (2026-08-26)

### Context

A passing assembly fabrication produced sandbox artifacts and a
`generated_programs` row — and nothing else. The design was invisible to the
Designer, the Phase 8 gates and the Phase 9A exporter: "viewable and
exportable", the operator's Phase 6 gate, had no path from the fabrication
loop. Meanwhile the operator API already had a complete persistence path
(`post_assembly_build`), and duplicating it for fabrication would create the
project's most dangerous silent failure: the same geometry existing under
two spec hashes — one per code path — breaking ADR-038's
digest-is-identity rule without any screen looking wrong.

### Decision

1. **One shared helper.** The post-`assemble()` body of the API build route
   is extracted into `persist_assembly_design(...)`; the API route and the
   fabrication bridge both call it. spec_hash, canonical payload and STEP
   bytes are identical whichever door a design came through — asserted, not
   assumed, in `gate_phase6a2_auto.py` §4.
2. **The bridge REBUILDS in trusted code** from the sandbox's
   `assembly_manifest_v1` (which carries every element's validated
   parameters and every joint), rather than copying sandbox artifacts.
   Cost: a few seconds of duplicate OCCT work per passing fabrication.
   Bought: the per-element solids for the pickable scene GLB, the layered
   validation gates run and persisted, and export through the one proven
   path. The sandbox's own STEP sha256 is recorded alongside
   (`sandbox_step_sha256`) so cross-image determinism drift is visible in
   the stored record, never silently absorbed.
3. **Lineage in both directions, additively.** `designs` gains
   `generated_program_id`; `generated_programs` gains `manifest_json`
   (stored for every attempt that returned a manifest — forensics for
   failures, lineage for passes). ADR-023 startup patches; all history
   stays NULL and loads.
4. **A bridge failure is honest and loud.** The fabrication still passed
   (the sandbox artifacts exist), so the program row stays `passed`; the
   missing design record is stated in `artifacts_json.design_bridge_error`
   and the outcome's `design_id` stays null. Order matters and is a
   recorded lesson: the program row commits BEFORE the bridge because the
   design's FK points at it — the first live test run failed exactly there.
5. **Two-tier prompt surface** (plan §3): index always, parameter tables
   only for the primitives the spec names, selection computed in code.
   Measured at four primitives: 11,267 chars full → 8,144 chars for a
   3-primitive spec (~28% smaller). The saving is modest today; the
   structure is what matters — it is in place before slices B–D triple the
   vocabulary, and unknown/legacy names fall back to the full surface so
   cascade fabrications are unchanged. The ADR-024 static prefix now
   varies per spec but is byte-identical across attempts of one run
   (gated), which is where cache hits actually pay.

### Consequences

- A passing assembly fabrication is immediately viewable in the Designer
  (under Ungrouped), checkable, and exportable — the operator's gate is
  now reachable live (`gate_phase6_visual.md`).
- Cascade fabrications are untouched: no design row, NULL manifest_json.
- Mixed-material costing is still NOT reconciled — moved from A2 to the
  costing tie-off (W-7) with the rate card work; LIMITATIONS §11 says so.

## ADR-053 - stack_on requires a real seat: the bearing floor (2026-08-26)

### Context

Found in the operator's live use, from their screenshots: design `a3006a42`
stacked a ⌀2,000 mm basin on a hollow ⌀2,200/102 mm plinth. The plinth's
inner mouth is ⌀1,996, so the 1,550 kg basin bears on a **2 mm-wide annular
lip of basalt**. Every existing check passed — the joint's intersection
volume was positive (125,538 mm³, exactly the 2 mm × 10 mm rim ring), the
fuse was watertight, body_count 1, volume conservation clean. ADR-029's
lesson was applied to the overlap DEPTH but never to the seat WIDTH:
interference proves the fuse, not the bearing. A 2 mm lip is inside the
±3 mm per-face tolerance the operator signed for basalt — the workshop can
erase it entirely, and under load it spalls.

### Decision

1. **A stack_on child must land on a radial bearing at least the material
   joint floor wide** — the SAME signed §2.1 numbers (basalt 10 / concrete
   15 / bronze 5 / 316L 3 mm, cross-material MAX). Rationale identical to
   the overlap floor: a seat narrower than the tolerance stack cannot be
   guaranteed to exist in the fabricated part. No new number was invented
   (Rule 11: the bound derives from signed arithmetic).
2. Each primitive now states its joint-plane geometry: `base_annulus_mm`
   (its footprint) and `stack_top_annulus_mm` (its stackable top face,
   None where CAN_PARENT_STACK is False). The assembler computes the
   worst-angle supported width — the parent's outer edge closes in by the
   lateral offset; a hollow parent's mouth reaches in by it — and refuses
   below the floor with the full arithmetic and the levers (thicken the
   parent wall, adjust a diameter, reduce the offset, make the parent
   solid).
3. **A side effect, recorded because a gate needle changed:** the A1
   battery's "floating body" case (a column hanging over a hollow
   plinth's mouth) is now refused EARLIER by this check (a negative seat)
   instead of by the late B-rep interference proof. The gate and test
   needles were updated to the new message — the protection did not
   weaken, the refusal moved left; the B-rep interference proof stays in
   the assembler as the construction-level backstop.
4. Prompt surface gains hard constraint "Assembly G" so the GEOMETRIST is
   told, not gated blind.

### Consequences

- Design `a3006a42` (and any persisted design like it) is NOT retro-
  flagged; it will be refused on its next rebuild with the numbers and
  the fix (at ⌀2,000 on ⌀2,200, a plinth wall >= 110 mm gives the 10 mm
  seat). LIMITATIONS §11 records this.
- Geometry of passing builds is unchanged — no hash moves; gates 6a1,
  6a2 and the canonical `e1a59fa6…` all re-verified PASS.
- The hollow plinth remains an open tube (A1 design, unchanged). Whether
  it should grow a closed top face is a separate operator ruling — it
  would change STEP bytes and is deliberately not bundled into this fix.

## ADR-054 - Phase 6 slice B: rim treatments in the profile, hydraulics from the spec (2026-08-26)

### Context

The plan (approved 2026-08-26): weir/coping/pool-edge as PROFILE
modifiers on `basin_round` — never post-hoc booleans (the ADR-010
argument) — and a nozzle-ring fixture whose numbers come from
`hydraulic_network`, with the signed §2.2/§2.3 floors (min feature, min
internal radius) finally load-bearing.

### Decisions

1. **Treatments are alternative rim cross-sections of the ONE closed
   revolved profile** (Polyline + RadiusArc, the cascade lip pattern).
   `rim_treatment: none` draws the inherited six-point profile —
   byte-identity pinned in the gate against the sha captured BEFORE the
   first profile edit (`6038d26f…`).
2. **A physics correction to the approved plan, made openly:** the plan
   derived `weir_depth_mm` = rim elevation − weir-node elevation. For a
   360° revolved basin that is incoherent — water cannot pass a rim
   ridge higher than the crest, so the crest IS the wall top. Built
   instead: the mapper VERIFIES the weir node's elevation equals the
   crest elevation within 5 mm survey tolerance (refusing with both
   numbers), and the treatment shapes the crest — internal crest arc
   (floor = signed min_internal_radius; 316L formula), flat land
   (wall + drip − crest radius >= signed min_feature), and a square drip
   lip (floor max(3, joint_overlap/3) — derived from the signed overlap
   arithmetic since per-face tolerance is not stored; ceiling wall/3;
   judgement, correctable). A partial-arc NOTCH weir breaks axisymmetry
   and is deliberately out (LIMITATIONS §11), not smuggled in as a cut.
3. **Never a silent hydraulic default.** A weir rim without a weir node
   is refused as invention; nozzle bores and counts come verbatim from
   the nozzle nodes (one bore size per basin in slice B; mixed bores
   refused naming the values). Direct API/Designer builds may set
   treatments and fixtures explicitly — the operator's deliberate act;
   the spec path enforces the network.
4. **Fixtures are cut by trusted code, locally, before placement and
   fuse** — element masses, the scene GLB and volume conservation all
   see the bored solid; the stone web between holes and to the wall is
   a projecting FEATURE and must clear the signed min_feature floor
   (arithmetic printed in every refusal); a cut that splits the floor is
   refused via solids count. The manifest records each fixture with the
   measured removed volume.
5. **The honest seat follows the rim** (ADR-053 composition):
   `stack_top_annulus_mm` reflects the lip, cap or bullnose, so the
   bearing check sees the treated rim, not the plain one. Coping adds
   its thickness to the element height and anchors.

### Consequences

- Gate: `gate_phase6b_auto.py` PASS at $0 — canonical guards
  (`e1a59fa6…`, A1 `529014af…`, default basin `6038d26f…`), treatment
  battery, spec-wiring refusals, exact bore-volume arithmetic
  (59,992 mm³ measured vs expected), two-process determinism
  (`07dcd723…`, PIDs printed). One gate-authoring lesson recorded: the
  first run pinned a hand-copied A1 plan (missing taper, wrong seed) and
  failed its own §1 — the gate now IMPORTS the canonical plan from
  `_assembly_build_once.py` so it cannot drift.
- The operator's B-7 ruling (hollow plinth cap) was NOT given at
  approval; the plinth stays an open tube and B-7 stays open.
- Slice B limits recorded in LIMITATIONS §11: 360° crests only, one
  bore size per basin, basin_round-only hosts.

## ADR-055 - Phase 6 slice C1: extrusion and array masses (2026-08-26)

### Context

The plan (approved 2026-08-26): six new masses — basin_rect,
stepped_monolith, water_wall, torus_ring, blade_fin_array,
lotus_petal_array — taking the registry from four primitives to ten.
The engineering risk to retire: an array is N boolean fuses in ONE
element, where fuse-order nondeterminism would quietly end Amendment 1.
Capabilities verified against the INSTALLED build123d 0.11.1 on
2026-08-26 (`PolarLocations`, `extrude`, `Rot`, `Torus`, `Cylinder`,
`Box`, `Pos` — live import, not recall; ADR-009).

### Decisions

1. **Extrusion joins revolution as a watertight-by-construction path**:
   `extrude_closed_profile` beside the revolve helper, same argument.
   Internal booleans stay on the proven pattern (cavity/bore cuts with
   overshoot).
2. **Arrays fuse in INDEX order, engaged, and clear the tangency band.**
   Each blade/petal is sunk into its hub by the material joint floor
   (ADR-029: touching is not joining), and adjacent elements must either
   GAP >= the feature floor (tool access) or OVERLAP >= the joint floor
   (a real fuse) — the near-tangent band between is refused with the
   arithmetic (`check_array_spacing`). Petals may overlap deliberately;
   a lotus does.
3. **Non-circular footprints report conservative seats** (ADR-053
   extension): rect masses expose their INSCRIBED circle — a false
   refusal is loud, an overstated seat would be the silent failure. The
   torus exposes `base_annulus_at_overlap_mm`: line contact un-sunk, a
   real chord 2·sqrt(d·(minor − d)) when sunk, held to the joint floor.
   Consequence, recorded: basin_rect and the sculptural masses are NOT
   stack parents in C1 (a circular seat model on a rect rim would lie).
4. **The lens petal is arcs, not splines** (sagitta arithmetic; width <
   length or the arcs close into a circle) — free-form stays in slice D.
   The initial plan bound (width < length/2) was an arithmetic error
   caught by the first test run and corrected to the true degeneracy.
5. **water_wall carries the ADR-054 crest linearly** (extruded, so the
   360° axisymmetry limit does not apply); its thickness floor is 3x the
   vessel-wall floor — the slice's weakest number, flagged as judgement
   at approval and unchallenged. No notch weir was built: the ruling was
   asked twice and not given.
6. Envelope table as approved (plan §5) — signed by the plan approval,
   including: rect corner radius >= the §2.3 internal-radius floor
   (316L formula), step inset >= the §2.1 joint floor, blade/petal
   thickness >= the §2.2 feature floor, torus major >= 2x minor.

### Consequences

- Gate `gate_phase6c_auto.py` PASS at $0: the three canonical hashes
  unmoved; six masses built with printed volumes; every floor refused
  with real numbers; THE GATE C COMPOSITION — a 24-blade array inside a
  3-primitive assembly — body_count 1 at B-rep and mesh, volume
  conservation 0.0000%, byte-identical STEP `956436c1…` across PIDs 313
  and 323; the torus chord (87.2 mm at the 10 mm floor) and the
  inscribed-circle seat proven; a 2,494.8 kg monolith refused by a
  2,000 kg crane.
- Segmentation was REMOVED from this slice's scope (plan §8.1): it is
  costing-driver work and moves to its own C2 slice beside the costing
  tie-off. NEXT.md corrected.
- One prior test's registry snapshot (exactly-four) updated to
  subset-plus-protocol; the exact-ten assertion lives in test_slice_c.

### Two older gates corrected — with the operator's ruling, not quietly

Widening the registry broke two earlier gates. Both were reported red
BEFORE any edit, and the first was changed only on the operator's
explicit instruction (2026-08-26). Neither correction weakened a check:

1. **`gate_phase6a1_auto` §1** asserted the registry held EXACTLY the
   four A1 primitives. Its intent was "A1's four are registered with
   their signed envelopes", not "the library is frozen" — the approved
   plan and `primitives/__init__` both say slices B-D widen the dict.
   Now a SUBSET check (`missing = expected - got`), and it reports which
   A1 primitive is missing if one ever disappears. The exact-set
   assertion lives in the NEWEST slice's gate — 6c asserts the ten
   today, slice D's will assert thirteen.
2. **`gate_phase6a2_auto` §6** proved "an unknown primitive is refused"
   using `water_wall` as the example unknown — which slice C1 made real,
   so the platform correctly ACCEPTED it and the gate failed. The check
   is right; its example must simply name something outside the live
   registry. Now `basin_spline` (a slice-D primitive, genuinely not
   built). It will move again when slice D lands — that is the check
   working, and the comment in the gate says so.

**The standing lesson:** a gate that pins the exact contents of a
deliberately growing registry, or that hard-codes an "unknown" name the
roadmap will later make known, has a built-in expiry. Frozen-set
assertions belong to the newest slice's gate; older gates assert what
their own slice made true.

