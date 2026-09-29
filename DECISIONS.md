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

## ADR-056 - Phase 6 slice C2: segmentation, and the drivers it feeds (2026-08-27)

### Context

NEXT.md W-3b: split-line planes against `fabrication.max_module_m` ->
modules -> seams -> per-module BOM lines, to unlock the three costing
lines that had no DRIVER (LIMITATIONS §10). Until this slice, an element
wider than the declared module limit was REFUSED: a 5 m basalt basin is
11,346 kg as one piece, no crane in Addis picks it, and the platform's
answer was no.

Kernel capability verified live against the INSTALLED build123d 0.11.1
on 2026-08-27 (`split(objects, bisect_by=Plane, keep=Keep.BOTH)`,
`Keep.BOTH`, `Face.normal_at`, `Face.area`, `Shape.faces/vertices/edges`
— live import and a real cut, not recall; ADR-009). `to_tuple()` is
deprecated in that version and is not used.

### Decisions

1. **Segmentation is a real cut, and every number is measured off the
   pieces.** No count is derived from a bounding box. The module COUNT is
   the number of connected solids after cutting, never `n_x*n_y*n_z` —
   proven necessary: a hollow plinth on a 3x3x2 grid predicts 18 modules
   and truly yields **16**, because the centre cells are bore. A
   predicted count overstates both the crane picks and the seams, and
   does it silently.

2. **The limits move from the ELEMENT to the MODULE.** `max_lift_kg` and
   `max_module_m` now bind on what the workshop actually makes. This is a
   deliberate widening: designs that were refused now build. The refusal
   did not disappear — it moved to the shapes where a saw plane genuinely
   cannot produce modules, and to modules that are still over a limit
   after cutting. With no `max_module_m` declared nothing is cut and each
   element is its own module, which is exactly the pre-C2 behaviour: the
   platform will not invent the limit it would have cut to.

3. **Primitives declare `SEGMENTATION_MODE`**, beside `CAN_PARENT_STACK`
   and `CAN_PARENT_INSERT`. `planar_grid` for the eight continuous
   masses; `discrete_array` for `blade_fin_array` and
   `lotus_petal_array`, which are REFUSED BY NAME rather than fragmented.
   Measured, and the reason the mode exists: a 24-blade array at a 0.8 m
   limit produces **25 solids from a 3x3 grid, lightest 0.9 kg against a
   heaviest of 2,685.7 kg** — chopped-off blade tips, not fabricable
   pieces. Their real decomposition is hub + N blades; that is a later
   slice, and it is in LIMITATIONS §11 as a named gap, not built badly.

4. **A seam is an INTERFACE, counted once.** Four quarters of a basin
   share four interfaces, not the eight cut faces they carry between
   them. The two halves are paired by (centre, area) at micrometre
   precision, since OCCT cuts both from the same plane. A face present on
   only one side is a pre-existing face lying in the cut plane, not a
   seam; it is excluded, and the count of such faces is reported so the
   coincidence is visible rather than silent. Both the RUN and the bedded
   AREA are measured, and the rate's own `per` unit decides which drives
   the line — a welded 316L seam is billed per metre, a bedded basalt
   joint per square metre. The platform never picks for the workshop.

5. **A joint seam is the CONTACT footprint, not the child's outline.**
   The first implementation sectioned the child at the contact plane and
   reported, for a 5 m basin on a hollow 2.2 m plinth, `pi x 5000 =
   15.708 m` of joint where the two solids only meet over the plinth's
   top annulus, `pi x (2200+1800) = 12.566 m`. Caught by running the real
   route, not by a test that agreed with the code. It is now measured on
   the overlap solid the joint proof already computes — the same
   intersection, so the two can never disagree about whether two elements
   touch. Measuring the real face also makes the bedded area exact rather
   than inferred from volume/overlap, which is right for a prismatic
   overlap and wrong for a tapered one.

6. **Determinism is claimed only where it holds.** Same input, same code
   path, two separate processes: byte-identical, and the gate proves it.
   Plane ORDER is a different question, and the honest answer is
   measured: cutting z-y-x gave a module extent of 1666.6666666666677 mm
   where x-y-z gave 1666.6666666666667 mm. The connected components are
   the same and every engineering number agrees to better than 1e-9
   relative, but OCCT's split is not bit-exact under reordering, so
   order-independence is asserted as a geometric identity and not as
   byte-identity. Amendment 1 is untouched either way: segmentation cuts
   COPIES to measure them and never touches the fused solid the STEP is
   exported from. All four canonical hashes re-proven unmoved.

7. **Nothing wall-clock goes in the manifest.** The first
   implementation put a per-element `duration_ms` in the segmentation
   block. The manifest is SEALED INTO the LUXEXCHANGE package, so the
   package content digest changed on every export and Phase 9A's
   reproducibility guarantee (ADR-035/037) silently died. Caught by the
   existing `test_export_package_is_reproducible_and_self_verifying` on
   2026-08-27 — two digests that should have matched and did not. Timing
   is now read off the SegmentResult object; the gate asserts the
   manifest block carries no `duration_ms` at all. Every other number in
   the block is rounded to 6 dp (a nanometre, a microgram — orders below
   the finest tolerance in materials.yaml), so trivial float jitter
   cannot move a digest either.

### The defect this slice had to fix first

`GET /api/costing/bom/{design_id}` returned **HTTP 500 for every assembly
design in the database** — verified against the live backend on all four
`assembly_built` designs before any code was written. Costing has been
unreachable for assemblies since Phase 7A and nothing recorded it.

The first diagnosis was wrong and is recorded because the correction
matters: it looked like row selection (an assembly stores four validation
rows and the newest is a Phase 8 layered report). Selecting by gate name
did not fix it. The real cause is deeper: **an assembly does not produce a
`ValidationReport` at all.** It produces an `AssemblyValidationReport`,
which deliberately carries no `material_id` and no single `mass_kg` —
"a fused mesh has no single material, so a single mass_kg would be fiction
for mixed-material assemblies" (validate.py, Phase 6 A1). Costing was
written for the Phase 2 single-solid shape and had never met the other
one. Three report shapes share the `validation_reports` table; the route
now maps gate name to report class explicitly.

`gate_costing_auto.py` never caught this because it builds BOMs from a
synthetic report and never goes through the route. The new gate's §9 does.

### Consequences

- **Full roster 2026-08-27: 17 of the 18 `gate_*_auto.py` scripts PASS,
  0 FAIL.** The eighteenth, `gate_phase9b_auto`, was NOT run: it requires
  the render-worker container UP, and this run deliberately held it down.
  `gate_phase14_auto` was run in both halves (container `geometry` and
  host `--frontend-only`), both exit 0.
- **The full pytest suite has NOT had a clean run on this code, and that
  is recorded here rather than glossed.** `432 passed, 1 failed in
  796.34s`; the failure is
  `test_export_package.py::test_package_manifest_is_honest_about_what_is_missing`,
  asserting `statuses["USD"] == "unavailable"` and getting `"included"`.
  That is the known D-9 condition — five export tests assume the render
  worker is DOWN — and NOT a defect in this slice: the test does not
  touch segmentation, costing or the manifest block C2 added. The worker
  was verified down before the run and was started externally at 08:12:30,
  about ten minutes into a run that began ~08:02:12. A repeat on
  `tests/test_export_package.py` alone (`1 failed, 18 passed in 236.81s`)
  was contaminated the same way at 12:25:36. **No gate and no test was
  edited to accommodate this** — D-9 stays open in NEXT.md and the honest
  status of the suite on this code is 432 of 433 with one environment-
  dependent failure outstanding.
- Gate `gate_phase6c2_auto.py` PASS at $0, offline: four canonical hashes
  unmoved; conservation 0.0000000000% on a 9-module cut; every module
  inside both limits; 18-predicted/16-measured proven; the quartered
  basin's seam area (4 x 457,500 mm2) and perimeter (4 x 6,400 mm)
  asserted against hand arithmetic with 4 interfaces not 8; byte-identical
  segmentation across two PIDs; the array refused by name; both costing
  lines moved from `not_computable` to `missing_rate`; the route returning
  200 with the same mass the manifest measured.
- **`config/costing.yaml` -> `2026-08-v2`.** Six new nulls: a per-material
  `seam` rate (4) and `install.truck_payload_kg` + `install.modules_per_trip`
  (2). The rate card goes **33 -> 39** entries. B-3 grows by six, and that
  is the price of two lines becoming real.
- **`crane_pick_kg` stops meaning "the whole fountain"** — the last bullet
  of LIMITATIONS §10 is discharged.
- **`material_purchase` is NOT unlocked**, contrary to W-3b's wording. A
  slab count needs a stock THICKNESS that `materials.yaml` does not carry,
  and a sheet count needs a curved shell unrolled onto flat stock, which
  the kernel does not do for a doubly-curved revolve. The blocker text now
  names those two instead of blaming segmentation. Quoting basalt per m3
  or per kg still makes the largest BOM line compute immediately.
- **Mixed-material assemblies are refused for costing** with HTTP 409
  naming every material and its elements, rather than priced at whichever
  material reached the report first. Per-element costing stays W-7.
- Two older tests AND one older gate asserted the contract this slice
  deliberately changed. All three were reported red BEFORE any edit and
  rewritten to assert the NEW truth; none was weakened:
  `test_max_module_refused_before_segmentation_exists`; a gate row
  predicting `ceil(5000/2000) = 3` modules; and **`gate_phase6a1_auto`
  §4**, whose check was literally labelled "element bigger than
  max_module_m (segmentation is slice C)" and asserted the string "slice
  C" in the refusal. A1's real intent — "a declared workshop limit is
  enforced, with real numbers" — is still true, so the check now uses the
  refusal A1's own semantics preserve exactly (over the crane limit with
  NO module limit declared, which still refuses with the §4.2 hollowing
  arithmetic) plus a second case proving the refusal did not merely
  vanish (a `discrete_array` shape planar cuts cannot segment). **This is
  the third time D-10 has bitten** — a gate that pins behaviour a later
  slice is scheduled to change has a built-in expiry, and the phrase
  "segmentation is slice C" sitting inside an assertion was the tell.
- A pre-C2 manifest with an oversized element now yields `needs_input`
  asking for a rebuild rather than a predicted count.

### Judgement values, flagged so the operator knows which to correct

1. **Axis-aligned planar grid, not radial.** The weakest decision here. A
   round basin split three ways becomes a 3x3 waffle; a stone mason might
   cut radial pie segments. Chosen because it is the only pattern that
   works for every shape in the library (walls, rect basins, monoliths)
   and because it is exactly measurable. Radial segmentation for
   axisymmetric vessels needs the operator's ruling on how the yard
   actually cuts, and is proposed as its own slice.
2. **Even spacing, not maximum-size-first.** Even spacing minimises the
   heaviest module, and the heaviest module is what binds against both
   limits. A workshop buying fixed stock may prefer full slabs plus a
   remnant.
3. **`MAX_PREDICTED_CELLS = 256`.** A guard against a runaway limit (a 6 m
   basin at 0.1 m predicts 60x60x9 cells and would hang the build), sized
   against the 25-solid case measured at 0.92 s. A ceiling, not an
   engineering bound; refused loudly with the arithmetic.
4. **No invented sliver floor.** Deliberately absent: every `planar_grid`
   shape measured produced sane module masses, and the fragment problem is
   confined to the two array primitives, which are refused by mode. A
   module too small to be real will be VISIBLE in the printed masses
   rather than hidden behind a threshold nobody derived.

---

## ADR-057 - PR-0: both render-worker states are first-class, and the package digest ignores them (2026-08-27)

### Context

Production v1 program, slice PR-0 (approved 2026-08-27). Debt D-9: six
tests hard-coded the render worker being DOWN
(`assert status == "unavailable"`) and failed with it running, so "full
suite green" was only true in one worker state -- while the Phase 9A GATE
had accepted both states since ADR-045. Debt D-9b, the deeper defect the
flaky sixth test exposed: two exports of one design during a worker-up run
sealed DIFFERENT content digests, because the LUXEXCHANGE manifest
recorded each Blender-tier format's runtime status (`included` vs
`unavailable`), and on a loaded 4-core box a conversion can land in one
export and time out in the other. The package digest -- the number that
identifies a design -- followed the render worker's uptime.

### Decisions

1. **The sealed manifest describes THE PACKAGE, not the runtime.** A
   non-reproducible format (registry flag `deterministic: False` --
   USD/USDZ/FBX/ABC, ADR-045) is never sealed into the ZIP, so the truth
   about the package is constant. Its manifest entry is now built from
   the format SPEC alone: status `excluded`, no path, no sha256, no byte
   count, no duration, a fixed `excluded_reason`, `in_package: false`.
   Nothing taken from the runtime result may enter the digest-covered
   manifest. `omitted_non_reproducible` always lists ALL non-reproducible
   formats, not just the ones this build happened to produce.

2. **Live availability stays on the per-run surfaces.** The exports table
   rows and the exports API still report `unavailable` (worker down,
   reason naming the compose command) or `included` (worker up,
   downloadable individually) -- per ADR-045, unchanged. The status
   vocabulary `excluded` exists only inside the sealed manifest.

3. **Tests assert per worker state, never assume one.** The six D-9
   tests now branch on the observed state and assert the honest contract
   in each: down means `unavailable` naming the render worker; up means
   `included` with real bytes and a 64-char sha256; `failed` is never
   acceptable; mixed results across the four formats are legal (a loaded
   box can time out one conversion). The byte-identity test compares
   only formats the registry declares deterministic, with a floor
   assertion (STEP/DXF/STL/BREP must be in the set) so the filter cannot
   hollow the test.

4. **The digest property is gated at $0 with no worker.** A new
   regression test packages one design twice -- once with worker-down
   results, once with the Blender-tier results rewritten to the exact
   shape a live conversion produces -- and asserts byte-identical
   packages, digest included. The D-9b failure mode cannot reappear
   silently in either worker state.

### Consequences

- The suite is required to pass with the render worker up AND down; both
  runs are recorded in PRODUCTION_V1_REPORT.md (PR-0).
- A package sealed after this change has a different content digest than
  one sealed before it for the same design (four manifest entries changed
  shape). Historic packages remain verifiable by their own shipped
  verifier; a new export of an old design re-seals with the new manifest.
  The Phase 9A within-run reproducibility guarantee is unchanged and now
  also holds ACROSS worker states.
- Container-state hygiene, learned from the contaminated runs behind
  D-9b: suite and gate evidence records the worker state before AND after
  the run (docker inspect of State.Status and State.StartedAt), and a
  worker that must stay down is REMOVED (docker compose rm -sf
  render-worker), not merely stopped -- a removed container offers no
  Start button in Docker Desktop to click by accident.

---

## ADR-058 - PR-3: the platform answers on loopback only (2026-08-27)

### Context

Production v1 program, slice PR-3 (approved with amendments 2026-08-27).
docker-compose.yml published the backend (8000) and frontend (5173) with
the two-part `"8000:8000"` form, which Docker binds to every host
interface and punches through the Windows firewall with its own rule.
The API carries NO authentication of any kind, so anyone on the
operator's LAN could read every design and Council transcript and invoke
the endpoints that dispatch PAID provider calls. The frontend reaches
the backend over compose-network DNS (`VITE_API_TARGET=
http://backend:8000`), never through a host port, so host-side binding
cannot affect the UI.

### Decisions

1. **Host publishes bind `127.0.0.1` — the 3-part form — for every
   service.** The container-INTERNAL binds stay `0.0.0.0` (uvicorn's
   `--host`, Vite's `--host` in the frontend Dockerfile CMD): those are
   what the publish and the compose network connect to, and narrowing
   them would break both. The distinction is recorded here because
   "bind loopback" applied to the wrong layer would look like the same
   fix and quietly break the platform instead.

2. **A standing gate, `gate_pr3_auto.py`, keeps it true.** Two explicit
   sections: STATIC (in the backend container, with the HOST's live
   compose file piped in over stdin — the image's baked build-time copy
   is refused by name, because asserting a snapshot could pass while the
   governing file regressed; every `ports` entry must be 3-part
   `127.0.0.1`; the two sandboxes must stay `network_mode: none` with no
   ports; the frontend must target `http://backend:8000` by service
   name) and LIVE (on the
   host — `/api/health` must return its real healthy JSON and :5173 the
   LuxuryForm frontend on loopback, and every non-loopback IPv4 on the
   machine must REFUSE TCP connects to 8000 and 5173). A section that
   cannot run reports NOT RUN with the command to run it elsewhere and
   never supports a full-gate PASS; with no non-loopback address the LAN
   sub-check reports NOT RUN rather than passing vacuously. The gate is
   in the roster because a binding regression is otherwise perfectly
   silent: the operator's localhost experience is identical while the
   LAN quietly regains access.

3. **No authentication is built, and no LAN-enable path ships.** For one
   operator on one machine, loopback makes auth redundant; a token
   bolted on now would be theatre. Deliberately, there is no override
   file, no documented command and no switch to re-open the network —
   LAN/remote access may return only as part of a future authenticated
   deployment slice (LIMITATIONS §19, docs/operator/11_network_privacy.md).

### Stated limits

- The gate sees docker-compose.yml and the live sockets. A manual
  `docker run -p` outside compose bypasses both the file and (until the
  next live run) the check.
- The live section proves refusal from this machine's own non-loopback
  addresses; the operator's phone test (gate_pr3_visual.md) is the
  independent off-machine confirmation.
- Judgement values: the live connect timeout (2.0 s) and the positive
  loopback checks' startup deadline (60 s, retry every 3 s) — both affect
  gate runtime only, never correctness. The deadline exists because a
  roster run straight after `docker compose up --build -d` hit the
  backend mid-recreate twice (docker-proxy accepts, then closes:
  RemoteDisconnected) while the same URL answered healthy seconds later;
  a service that cannot become healthy in 60 s on this machine is broken,
  not booting, and the gate still fails loudly then.

### Consequences

- The Phase 2 canonical STEP hash `e1a59fa6…` is untouched — no
  geometry-adjacent code changed; the roster re-run re-proves it.
- Anything OFF this machine that reached the API stops working by
  design. No such consumer was found (the Hub generator and all scripts
  run locally); if one exists, it surfaces at the visual gate.
- CLAUDE.md's roster is 19 scripts; the roster is the glob
  `scripts\gate_*_auto.py`, enumerated and run explicitly by sessions —
  nothing runs it automatically.

---

## ADR-059 - PR-1: max_module_m binds per axis; history is flagged, never re-judged (2026-08-28)

### Context

Production v1 program, slice PR-1 (approved with amendments 2026-08-28).
The Design Spec has ALWAYS required `fabrication.max_module_m` as
`{x, y, z}` (design_spec_v1.json), and `spec_mapper.py` collapsed it with
`max(values)` — the LOOSEST axis became the limit for all three, so every
spec-path design since slice C2 was under-enforced on its two tighter
axes. Three enforcement sites each flattened axis identity with `max()`
over extents (the assembler's pre-cut decision and post-cut check, and
the fabrication gate's `widest`); converting any subset would leave a
breach on the tight axis reading as a pass. The GEOMETRIST prompt
additionally instructed generated code to pass the raw spec dict, which
raised `TypeError` at `float(max_module_m)` — the prompt and the mapper
disagreed about the type.

### Decisions

1. **One shared per-axis vocabulary in the kernel** (`segmentation.py`):
   `normalize_module_limit_m` (exactly the keys x/y/z; booleans,
   non-numerics, non-finite, zero and negative values refused by name),
   `axes_fit_mm` (every extent vs ITS OWN limit), `binding_axis_mm`
   (Amendment 5: greatest utilization ratio extent/limit — never the
   largest absolute dimension — ties broken deterministically x->y->z),
   `format_limit_m`. All three enforcement sites use these helpers and
   can no longer diverge. `segment_solid` takes per-axis mm only —
   scalar-to-cubic lives at one boundary, never in the kernel.

2. **Two input contracts, kept distinct (Amendment 3).**
   `fabrication_limits_from_spec` is Design-Spec-only: it preserves the
   `{x,y,z}` object (validated) and REFUSES a scalar — a scalar there is
   a malformed spec. `assemble()` is the single compatibility boundary:
   a Designer/API scalar deliberately means a CUBIC envelope and is
   normalized to `{x:s, y:s, z:s}`; anything malformed raises
   `ConstraintViolation` before any geometry (the routes map it to a
   structured HTTP 422 — Amendment 4). The stored REQUEST keeps the
   shape the client sent; the manifest's `fabrication_limits` stores the
   normalized dict, which the fabricate bridge round-trips.

3. **The compatibility truth table (Amendments 1 + 2), enforced live at
   the API and gated:**
   - spec_id NULL + scalar -> deliberate cubic; valid.
   - spec_id NULL + {x,y,z} -> deliberate per-axis; valid.
   - spec_id SET + {x,y,z} -> corrected spec build; valid.
   - spec_id SET + scalar -> collapsed-spec history; needs_input,
     rebuild required. The original axes are recovered via
     designs.spec_id -> design_specs.spec_json and VERIFIED
     (max(x,y,z) must equal the stored scalar); recovery is named in
     the message.
   - Missing, malformed or mismatched provenance -> needs_input;
     NEVER assumed cubic.
   `GET .../manifest` carries a live `module_limit_provenance` block
   (computed on read, never stored); geometry-REBUILDING operations
   (export/package rebuild, scene.glb regeneration) refuse with HTTP
   409 and ONE exact next action; existing artifacts stay viewable.
   The fabrication gate takes `module_limit_provenance` and emits the
   needs_input rebuild row for any scalar it cannot confirm as cubic.

4. **The gate row stays scalar-shaped.** `value`/`limit` carry the
   BINDING axis's extent and limit (the row's ok is all-axes-fit); the
   basis names every axis and the binding axis explicitly. The wire
   format, the UI table and the finite-number walk are untouched.

### Consequences

- The required proof holds and is gated (`gate_pr1_auto.py`, roster
  script 20): a 2.4 x 2.4 x 2.2 m envelope CUTS a 2,300 mm-tall basin
  that fits x/y, and the same solid under the old collapsed value ships
  whole — the printed difference IS the closed defect.
- The four canonical STEP hashes are unmoved (no canonical build passes
  fabrication; segmentation cuts copies after the fuse) — re-asserted by
  the gate, not assumed.
- New manifests store `max_module_m` (and the segmentation block's
  `max_module_mm`) as dicts; historical manifests are never rewritten.
- Per-axis binding is CONSERVATIVE: module rotation for transport is not
  modelled, so a module that could legally lie on its side may be
  refused (LIMITATIONS §11).
- The old collapse test (`test_..._scalarizes_module_box`) and every
  scalar call site were reported red before rewriting; every measured
  number in the 6c2 gate is unchanged because a cube of the same side is
  the identical cut.
- Deferred to PR-5, per Amendment 7: `run_vision_critique.py`'s
  wrong-level `max_lift_kg` lookup (silent 1000 kg default) is repaired
  together with the scorer's total-mass-vs-module contract — fixing only
  the lookup would leave the scorer semantically wrong while appearing
  repaired. Also PR-5's: the prompt's remaining "per element" wording.

---

## ADR-060 - Free-form amorphous sculpture is a Production v1 release-blocking capability (owner ruling, 2026-08-28)

### Context

Binding product feedback from the company owner, 2026-08-28:
complicated amorphous, organic, mesh-like sculpture design is a PRIMARY
product requirement — not an optional post-v1 feature. The recent live
workflow demonstration (Council session fc41df05, 15 calls, $0.6778;
fabrication passed after 3 attempts and created design a772c648) proved
the brief → spec → geometry WORKFLOW but did not prove this GEOMETRY
CAPABILITY: everything the platform can generate today is
revolve/extrude/array solids from the ten-primitive registry.
Polygon-mesh EXPORT (GLB/STL/OBJ of solids the kernel already built)
exists and is not the same thing as amorphous design GENERATION.

### Decisions (the owner's ruling, recorded)

1. **Phase 6 slice D moves from "deliberately OUTSIDE Production v1" to
   a RELEASE-BLOCKING Production v1 capability.** NEXT.md's outside
   list is corrected in the same commit as this ADR.
2. **Sequence:** PR-2 close → PR-2.5 (a dedicated /lf-next
   discovery/acceptance plan) → approved PR-2.5 implementation
   slice(s) → free-form gates and close → PR-4. **PR-4 must NOT start
   merely because the PR-2.5 plan was approved** — it waits until the
   free-form capability is built, gated, committed and pushed, unless
   the operator explicitly changes that ruling. Hard spend caps (PR-2)
   remain next and are not expanded by this ruling; nothing free-form
   is implemented during PR-2.
3. **No representation is preselected.** The discovery must compare, on
   the evidence of the B-11 reference designs and fabrication
   processes: (a) controlled OpenCASCADE BREP loft/sweep/spline
   construction; (b) deterministic procedural/implicit or mesh-native
   construction; (c) human-authored reference-mesh import or fitting.
   The existing slice-D list (basin_elliptical, basin_spline,
   spline_loft_mass) is a hypothesis, not the requirement. Whether
   STEP/BREP is mandatory or a deterministic watertight mesh is the
   correct manufacturing artifact is a discovery QUESTION decided by
   the reference designs and fabrication processes; **any change to
   STEP as the canonical artifact requires an explicit architectural
   ruling — never an assumption.**
4. **The core architectural rule survives unchanged:** an LLM writes a
   constrained design specification/program that a deterministic
   kernel executes. The LLM may never emit unchecked vertices,
   whatever representation the discovery selects.
5. **The eventual acceptance gate** must prove the full chain on
   free-form geometry: real brief → Council alternatives →
   deterministic watertight free-form geometry → validation →
   segmentation → render → export. **PR-9's final acceptance gate
   gains a MANDATORY fourth positive end-to-end project** — a
   genuinely amorphous sculpture; PR-2.5 determines the exact fixture
   and manufacturing route.
6. **D-11 (radial segmentation) and D-12 (array hub+blade
   decomposition) are discovery CANDIDATES, not automatic
   dependencies** — either is promoted only when a reference design
   and fabrication method prove it is required.
7. **New operator input blocker B-11** (NEXT.md §1): 3–5 reference
   designs, intended materials/fabrication processes, and whether
   manual sculpting controls are required. The PR-2.5 discovery plan
   cannot be approved without at least the reference designs; nothing
   is invented in their place.

### Consequences

- Recorded in a docs-only commit ahead of PR-2's closure, at the
  owner's instruction, so no concurrent session follows the obsolete
  queue while PR-2 is in flight. No production code, container, test
  or gate changed.
- NEXT.md (header, §0 table, B-11, PR-2.5 entry, PR-9 entry, outside
  list, D-11/D-12), LIMITATIONS.md (Phase 6 entry) and
  PRODUCTION_V1_REPORT.md (program header) updated in the same commit.
- The Phase 2 canonical STEP hash `e1a59fa6…` is untouched — this
  commit changes four Markdown files and nothing else.

---

## ADR-061 - PR-2: spend caps enforce by atomic reservation, fail closed (2026-08-28)

### Context

Production v1 slice PR-2, approved 2026-08-28 with eleven mandatory
technical amendments and two rulings (fabrication spend accumulates
across re-POSTs of one (session, spec); `session_cap_usd` renamed
`run_cap_usd`). ADR-003's cap was real but raceable: an unlocked
read-then-compare (`pre_dispatch_check`) ran two SELECT sums and the
spend row landed only after the response, so two concurrent dispatches —
a Council POST in a uvicorn thread and the critique script in a separate
process on the same SQLite file — could both pass with $24.99 spent. The
estimate it checked (chars/4 + a flat 1100 vision-token allowance) was
not an upper bound, a crash between dispatch and the `ai_calls` insert
made real spend invisible forever, `build_providers(budget=None)` allowed
silently uncapped construction, `scripts/live_verify_providers.py` spent
outside the fence entirely, and Amendment 1's "logical run" had no
identity: fabrication pooled into the council session's $5 and a
restarted critique run minted a fresh id.

### Decisions

1. **Reservation, not check-then-call.** Before EVERY physical provider
   attempt, `BudgetEnforcer.reserve()` takes one `BEGIN IMMEDIATE`
   transaction on a dedicated raw SQLite connection (busy_timeout
   5000 ms — judgement value; the shared engine also gains the pragma):
   scope check/create, safety-lock check, both cap sums, hold insert —
   or, on refusal, the ADR-003 evidence rows (`budget_events` +
   `jobs(status='halted_budget')`) — commit as one atomic unit, then
   `BudgetHalt` raises. SQLite's single writer serializes reservers
   across threads AND processes; the gate proves both races.
2. **Two tables, one column, three unique/partial indexes — all
   additive.** `spend_scopes` (open | closed | **halted**, sticky),
   `spend_reservations` (held | settled | **uncertain**; INTEGER
   micro-USD), `spend_safety_locks`, `ai_calls.reservation_id`, and
   unique partial indexes making the reservation↔call link 1:1 in BOTH
   directions at the schema level; settlement and recovery assert it
   again in-band. Correlation is exact-id only — never a timestamp.
3. **Settlement is one transaction.** The `ai_calls` insert, the
   reservation settlement and the `sessions.total_cost_usd` fold commit
   together, so no crash leaves a partial state and gate 13a's
   two-ledger reconciliation holds at every boundary. Day spend =
   SUM(`ai_calls` 'ok' rows for the day, Decimal-converted per row) +
   SUM(bounds of held/uncertain holds taken that day): `ai_calls`
   remains ADR-003's single source of settled truth, pre-PR-2 history
   stays counted, nothing double-counts. Run spend is the same aggregate
   per scope. The day a hold was TAKEN binds (matching the existing
   pre-dispatch `ts` convention); worst-case midnight carry is bounded
   by in-flight holds.
4. **Integer micro-USD.** Ledger money is INTEGER µUSD; conversions go
   through `Decimal(str(value))` with explicit HALF-UP rounding
   (bounds: CEILING — a bound never rounds down). round(x, 6) is µUSD
   precision, so settled amounts convert losslessly; the gate proves a
   1000-row sum exact where float summation drifts.
5. **The bound is the mandated context-window fallback, for every
   provider.** Checked 2026-08-28 on each model's first-party page: NONE
   of the three documents per-message framing overhead, so no
   prompt-based formula has all its components proven and none ships.
   bound = context_window_tokens x max(input, cache-write rate) +
   max_tokens x output rate, ceiling-rounded. Context windows fetched
   first-party 2026-08-28 and recorded with sources in pricing.yaml
   (`2026-08-v4`): claude-sonnet-4-5 200,000 / gpt-4o 128,000 /
   kimi-k3 1,048,576. Billed input — text and images — is context
   tokens by definition, so one bound covers both call kinds. The
   anthropic 1h cache-write class ($6) is unreachable (no code path
   sends a ttl); 5m write ($3.75) is the priced maximum. **Stated
   consequence:** a kimi-k3 call holds $3.268608 while in flight, so it
   refuses once a $5 run has less headroom than that — fail-closed by
   order, revisit only with first-party framing documentation. B-4
   (price truth) stays open; the gpt-4o prices remain tracker-only.
6. **Fail closed, everywhere.** No first-party documentation proves any
   provider error class non-billing (silence is not proof), so EVERY
   failed physical attempt goes `uncertain` and keeps consuming its full
   bound; a `released` status deliberately does not exist. Each physical
   attempt has its own reservation AND its own audited `ai_calls` row
   (the old ADR-023 caveat — retry history discarded on success — is
   gone); a retry that no longer fits under a cap halts mid-sequence. A
   pricing failure after a billed call, an actual cost above the
   reserved bound, or a ledger mismatch found at startup engages a
   PERSISTED safety lock (provider/model, or GLOBAL for mismatches) and
   halts the scope; matching dispatch refuses until
   `scripts/spend_admin.py` resolves it with a mandatory audited reason.
   Startup recovery classifies surviving holds `uncertain` (settlement
   atomicity makes any other surviving state impossible), never deletes,
   and `resolve-hold` moves one to `reconciled` at the console-verified
   amount — its own status, because such a hold has no 'ok' `ai_calls`
   row: both cap sums count it at the verified amount and the two-book
   assertion exempts it. (Caught in-slice: the first cut marked it
   `settled`, which the reconciler then flagged as a mismatch — a
   global lock at the next startup — and whose nonzero amount vanished
   from the day sum; red-first tests and gate §5 now pin both.)
   ADR-033's lesson (the consoles are the only truth for a dead call)
   is now a first-class workflow. **The spend truth model, explicit on
   every operator surface:** (1) ordinary settled provider spend comes
   from `ai_calls` 'ok' rows; (2) manually reconciled ORPHAN spend
   comes from `spend_reservations.status='reconciled'` — never a
   fabricated call row; (3) displayed and cap totals are their
   non-overlapping union (`/api/ops/costs`: `total_usd = ai_calls_usd +
   reconciled_usd`, with `reconciled_unmatched_spend` rows and a live
   `reconciled_double_counts` finding; `/api/logs/budget` lists the same
   rows). The `sessions` ledger stays ai_calls-derived, so the Phase 13A
   ai_calls<->sessions reconciliation keeps its original meaning.
7. **Logical-run identities (Amendment 1 + rulings).** Council: the
   session uuid IS the scope. Fabrication: uuid5 over the FULL
   `fabrication:{session_id}:{spec_id}` (never truncated prefixes — an
   8-char collision would merge two $5 ledgers); every re-POST reopens
   the same scope and the spend ACCUMULATES until PR-7B's durable
   controls (operator ruling). Critique: a restart resumes the latest
   OPEN scope for the plan digest; a closed scope is never resumed — a
   new run gets a fresh full UUID. Intake: uuid5 over the full intake
   id, so re-parses accumulate. `closed` scopes reopen on legitimate
   re-dispatch; `halted` never reopens automatically.
8. **No fence-sitting paths.** `call_log.execute()` refuses to dispatch
   with no enforcer; `build_providers` requires one;
   `live_verify_providers.py` keeps its raw-SDK shape-dump purpose but
   every metered call now reserves, settles and logs through the real
   ledger into the operator's real database. `FabricateRequest.
   max_attempts` gains a structural ceiling (10 — judgement value).
   `/api/logs/budget` shows open holds and active locks.

### Stated limits

- The $25/day cap is per DATABASE FILE, not per machine (ADR-033: a temp
  DB grants full headroom) — LIMITATIONS §20; the hermetic-env standing
  rule is the guard for tests.
- The context-window fallback over-reserves by design; the cost is
  early refusals (kimi above), never overspend.
- Judgement values, flagged: busy_timeout 5000 ms; max_attempts ceiling
  10; the /api/logs/budget hold/lock list caps at 100 rows (display
  only).

### Consequences

- `gate_pr2_auto.py` joins the roster (script 21) — sections in its
  header; `gate_pr2_visual.md` is the operator's eye gate and asks
  whether $5/$25 remain the intended ceilings.
- `pricing.yaml` -> `2026-08-v4` (context windows + sources);
  `budget.yaml` renamed key; `docs/operator/01/04/05/09/10` updated to
  the run-cap vocabulary; frontend rollup renames `run_cap_usd`.
- The Phase 2 canonical STEP hash `e1a59fa6…` is untouched — no
  geometry-adjacent code changed; the roster re-run re-proves it.
- **CLOSED 2026-09-01:** operator visual gate signed PASS (verbatim in
  `PRODUCTION_V1_REPORT.md`). Ruling: **$5/run and $25/day RETAINED**;
  the kimi fail-closed retry consequence explicitly acknowledged. The
  two accidental live-data designs (`76595edb…`, `313e5d20…`) are
  preserved by explicit ruling; their cleanup is a separate operator
  decision.

## ADR-062 - The owner's 30-system scope becomes SCOPE.md; the audit baseline is bfa5a77 (2026-09-01)

### Context

Every report since Phase 1 cited `SCOPE.md` as authority while it never
existed (B-6). The owner's complete 30-system scope - systems, weights,
0-5 rubric, gates G0-G10, traceability test, AquaFlow boundary, outputs
inventory - was supplied 2026-08-28 in a working session and lived only
in that session's transcript. The 2026-09-01 Master Scope Development
Audit (five read-only domain agents + lead adjudication, $0, no
containers) scored the repository at `bfa5a77` against it.

### Decisions (owner rulings, 2026-09-01, binding)

1. **`SCOPE.md` reproduces the owner's scope verbatim** (encoding
   normalized only), preserves the 112-vs-"100%" weight contradiction
   with an annotation instead of silently correcting it, and normalizes
   every percentage by 112. It becomes owner-authoritative only when the
   owner countersigns `gate_scope_audit_visual.md`; future scope changes
   require an explicit owner ruling recorded as an ADR.
2. **Milestone names, used consistently everywhere:** Milestone A -
   Free-form Sculpture Demonstrator; Milestone B - Internal
   Fabrication-Geometry Beta; Milestone C - Production v1. "Production
   v1" means the complete threshold: normalized >= 80% AND every
   safety-critical system >= 4/5. The approved PR-0..PR-9 program
   delivers Milestone B and must not be described as Production v1.
   (`PRODUCTION_V1_REPORT.md` keeps its filename as a historical record.)
3. **LF-103A is the first implementation slice after the audit closes,
   before PR-2.5:** FAILED validation never produces a clean fabrication
   package; NEEDS_INPUT may produce only an explicitly watermarked
   PRE-FABRICATION package carrying `ENGINEERING_WARRANT.txt` naming
   unresolved checks and required professional inputs; a package must
   never appear production-ready while thresholds are unsigned; viewing
   and diagnostic exports are preserved. LF-103A does NOT wait for
   LF-102's engineer-approved threshold values.
4. **Score re-rulings applied before freezing the audit:** Parametric
   Geometry 4->3 (the primary amorphous requirement is absent, ADR-060),
   Panelization 3->2 (segmentation is not panelization; no per-module
   manufacturing CAD), Optimization 2->1 (the objective never steers; no
   persistence, no API). Final: raw 35.4/112 = 31.6/100, reconciled
   against 27.68% (earlier, unattributable per-system), 34.6%
   (2026-08-28 in-chat audit) and 33.9% (pre-ruling). Executive
   summaries say "approximately one-third complete", never a falsely
   precise promise.
5. **Evidence quality:** every scorecard row carries score, confidence,
   direct evidence, missing end-to-end proof, required professional
   input, and next dependency. `gate_scope_audit_auto.py` (roster
   script 22) verifies referenced files and quoted symbols/substrings -
   never line numbers - and recomputes the weighted total from the
   table. The audit baseline `bfa5a77` is recorded in the document and
   asserted by the gate.
6. **The owner's 6m->8m traceability test is preserved as supplied and
   marked unrunnable** under the current primitive envelope (tallest
   primitive caps at 6000 mm); a stacked-assembly test replaces it
   without rewriting the owner's request.
7. **No publication.** The audit names internal security and
   production-readiness gaps; it is not to be published or shared as a
   page. A presentation-safe boss report is a separate future slice.

### What this buys / gives up

Buys: one yardstick for every future slice, honest milestone language,
and the earliest possible close of the most dangerous behaviour found
(a failed design shipping a clean package). Gives up: the flattering
score - 31.6/100 replaces every rosier number in circulation - and the
"Production v1" label for the current program, which is now Milestone B.

### Evidence

`DEVELOPMENT_AUDIT.md` (baseline bfa5a77): scorecard with per-row
evidence, G0-G10 enforcement map, new-defect register D-13..D-23,
reconciliation table. Lead-verified anchors: null thresholds +
signed_off:false in `config/gate_profiles.yaml`; no gate branch in
`post_design_exports`; `LayeredGateReport.blocking` dead code; zero
aquaflow/cogninet/dmx hits repo-wide.

**CLOSED 2026-09-01:** `gate_scope_audit_auto.py` PASS (weights sum 112,
30 rows, weighted total recomputed from the table, 24 evidence anchors
verified by quoted symbols) + the owner's countersignature, recorded
verbatim in `gate_scope_audit_visual.md`. `SCOPE.md` is now
owner-authoritative. The owner's binding closing line: "Nothing in this
audit is authorization to claim the platform is presently
production-ready."

## ADR-063 - LF-103A: the export boundary enforces the gate verdict (2026-09-01)

### Context

The Master Scope audit (ADR-062) proved a design whose gates FAILED
sealed the same clean-looking LUXEXCHANGE package as a passing one; the
gate system's own blocking primitive (`LayeredGateReport.blocking`) had
zero call sites; and no profile being signed meant nothing could fail
AND failing would not have blocked. Owner rulings (plan + amendments +
final conditions, 2026-09-01) shaped the slice.

### Decisions

1. **Three-class verdict from PERSISTED evidence only**
   (`backend/app/geometry/package_class.py` - a geometry-layer module,
   importable by builder and routers without cycles). REFUSED = any gate
   fail. CLEAN = all pass AND every layered report snapshot-signed
   (`profile_signed_off`) AND one coherent basis (same `gate_profile_id`
   and `gate_profiles_version`) AND a shared `validation_basis` run
   identity AND the sealed STEP's sha256 equals the design's persisted
   `geometry_hash`. Everything else - unsigned, warn, needs_input,
   missing/empty/mixed/duplicate-ambiguous evidence - is
   PRE-FABRICATION, the fail-closed default. The classifier NEVER
   re-reads `gate_profiles.yaml`: re-reading would launder old verdicts
   the moment `signed_off` flips. Duplicates resolve `created_at DESC,
   id DESC`; mesh evidence accepts exactly one row - `assembly_mesh`
   preferred, legacy `mesh` as alias.
2. **CLEAN is builder/test-only until D-24 closes** (final condition 1,
   option B): no persisted row carries a `validation_basis`, so
   production classification structurally cannot return CLEAN. The
   branch is written now and proven with signed fixtures; **LF-102 must
   not make CLEAN reachable until a shared validation-run identity is
   persisted with every report of one validation operation (debt
   D-24).**
3. **Enforcement at the seal AND the route.** `build_luxexchange_package`
   itself raises `PackageRefused` on REFUSED (only path to
   `PackageBuilder.seal`; `app.main` maps it to HTTP 409 as defence in
   depth). The export POST classifies BEFORE the geometry rebuild and
   refuses with the failing checks' real numbers; the ADR-059
   ambiguous-rebuild 409 deliberately still fires first.
4. **Every downloadable geometry attachment is classified** (final
   condition 2): fabrication-capable formats (STEP/BREP/STL/DXF/SVG -
   raw STEP is fabrication-capable, never a viewing artifact) refuse for
   FAILED designs, on the ExportRow route AND `/latest.step`;
   PRE-FABRICATION downloads carry a marked Content-Disposition
   filename and an `X-Package-Class` header with canonical bytes
   untouched; FAILED mesh downloads serve marked
   DIAGNOSTIC-NOT-FOR-FABRICATION; only the inline viewport/scene
   stream is unmarked. The Phase 2 cascade STEP shares the marking
   helper.
5. **Marking is names, never bytes.** In-archive entry basenames gain
   `.PRE-FABRICATION.`; the zip keeps its on-disk name
   `luxexchange_v1.zip` (a rename breaks six call sites incl. a silent
   false-green in backup restore-verify) while the download filename
   carries the class. DXF/SVG gain a printed
   "PRE-FABRICATION - NOT FOR CONSTRUCTION" notice (deterministic ezdxf
   TEXT entity on layer PREFAB_NOTICE / SVG text element, both derived
   from the drawing bbox) - the only formats where a visual in-format
   watermark genuinely exists. No STEP-header claim is made: build123d
   header support is unverified (ADR-009) and any in-writer mark would
   break the Phase 2 canonical hash. `e1a59fa6...` is untouched;
   packages remain byte-reproducible per (design, seed, class).
6. **ENGINEERING_WARRANT.txt** seals into every PRE-FABRICATION package:
   deterministic bytes (sorted persisted check rows, no clock/uuid),
   every non-pass check with value/limit/basis/message, and the owning
   professional from a documented deterministic role map (B-8
   vocabulary; unknown mappings say "qualified professional review
   required" - never an invented discipline; final condition 5).
7. **Historical packages fail closed as LEGACY_UNCLASSIFIED** (final
   condition 3): only the sealed enum {clean, pre_fabrication} is
   accepted; missing/invalid/unreadable manifests refuse download with
   the one exact re-export action; bytes on disk are never rewritten;
   re-sealing is the operator's deliberate POST (the ADR-057 precedent).
   All 13 packages on disk today are LEGACY_UNCLASSIFIED until re-sealed;
   every current design classifies PRE-FABRICATION.

### What this buys / gives up

Buys: a fabricator can no longer receive a failed or unproven design
that looks fabrication-ready - at the package, at every CAD download,
and after extraction. Gives up: old zips stop downloading until
re-sealed (deliberate, loud, with the action named); the sealed manifest
shape changed, so re-exports of old designs get new digests (ADR-057
precedent) - the stored DNA precedent `8c8829bc...` will not dedupe
against a re-export (recorded, not silent).

### Evidence

Red-first on the pristine image: `test_package_class.py` collection
error (module absent) + `test_export_boundary.py` 9 failed / 1 passed -
verbatim in the LF-103A build record. Green: 39/39 new tests, 109/109
across all affected suites, `gate_lf103a_auto.py` PASS (9 sections incl.
hermeticity: real DB sha unchanged, 95 real export files untouched),
`gate_phase9a_auto.py` PASS with the class assertion. Judgement values,
flagged: the marking strings, notice layer/text size, role-map wording.

### Post-build full-roster + suite evidence (2026-09-01 → 02)

The session driving the runs closed mid-sequence; a read-only recovery
audit on 2026-09-02 re-established the chain before anything was
re-run: HEAD `e7d4617`, nothing staged, the 21-path LF-103A working
tree byte-identical to backend image `9fe4c4328116` (12/12 sha256
matches, host vs container, for every touched backend/scripts/tests
file), no surviving pytest/gate process on host or in the container,
and both orphaned background runs completed with their outputs intact
(docker events corroborate every exec start/exit and the worker
create at 13:54:54Z).

All on final image `9fe4c4328116`, $0, offline, no AI call:

- **Stage 1 (2026-09-01, render worker REMOVED — listing empty before
  and after):** full suite `514 passed, 2 warnings in 993.23s
  (0:16:33)`; then the 20-script in-container roster
  (phase2/3/4/5/6a1/6a2/6b/6c/6c2/costing/8/8b/9a/11/13a/14/15 + pr1 +
  pr2 + lf103a) plus `gate_pr3_auto.py --static --stdin`, all 21
  `exit=0`, `worker-after-roster: []`; `gate_phase14_auto.py
  --frontend-only` PASS on the host (typecheck + production build).
- **Stage 2 (worker restored 2026-09-01T13:54:54Z, pinned `Up 43
  seconds` before the suite):** full suite `514 passed, 2 warnings in
  59808.04s (16:36:48)` — the wall clock was inflated by overnight
  host suspension while the orphaned exec ran on after the session
  died; valid functional evidence, not performance evidence: pytest's
  own count is the verdict, and the worker stayed up throughout. Then
  `gate_phase9b_auto` exit=0, worker still up after,
  `image-after: 9fe4c4328116`.
- **2026-09-02, recovery session, re-proven first-hand:**
  `gate_pr3_auto.py --live` PASS (loopback 8000/5173 serve the real
  services; all four LAN-address probes refused) and
  `gate_scope_audit_auto.py` PASS.

That is the complete 23-script roster green in its required states and
the suite green in BOTH worker states, on the image the uncommitted
tree hashes to.

### Close (2026-09-02)

The operator personally completed all four visual steps and signed
PASS, dated 2026-09-02 — recorded verbatim in `gate_lf103a_visual.md`,
including the eight-point confirmation (FAILED geometry viewable but
refused fabrication-capable export; amber PRE-FABRICATION package;
marked zip and in-archive filenames; correct ENGINEERING_WARRANT.txt;
the printed NOT-FOR-CONSTRUCTION notice; classified standalone CAD
downloads; legacy package refused with its on-disk hash unchanged;
`gate_lf103a_auto.py` PASS). A first sign-off sent earlier that day,
before the steps were performed, was withdrawn by the operator and
never recorded. Slice closed as one commit on `main`. Next in queue:
PR-2.5 free-form discovery, blocked on B-11.

## ADR-064 - PR-2.5 free-form discovery: execution model, evidence rules, owner rulings (2026-09-02)

### Context

The owner supplied the B-11 references on 2026-09-02 (16 images +
`REFERENCE_ANALYSIS.md`), ruled on materials/scale/controls/fidelity,
approved the discovery plan v2 with nine binding amendments, and issued
six final execution clarifications. This ADR records every decision with
a real trade-off; the probe evidence itself lives in
`PR2_5_FREEFORM_DISCOVERY.md`.

### Owner rulings (recorded)

1. **Materials**: the free-form capability must cover **welded 316L
   plate over an internal armature** AND **cast GRC / white concrete**.
2. **Scale**: primary references validate at **monumental 3.5-5.0 m**
   (owner-ruling tag; NOT measured from any image).
3. **Controls**: **brief-driven generation plus parameter/control-point
   editing** in the Designer; no full manual sculpting in v1.
4. **Fidelity**: acceptance = **silhouette + topology** (void count,
   crossings, twist direction, proportions), not surface-exact match.
5. **Reference images stay local**: not committed, not pushed, not
   baked into any image until the owner explicitly confirms repository
   privacy AND permission for every image (gitignore + dockerignore
   entries; committed record = `reference_manifest.json` + the text
   analysis).
6. **B-11b (mesh/lattice ground truth) stays OPEN and
   release-blocking** for any mesh-capability claim and for
   Production v1; none of the 16 images defines it and nothing is
   invented in its place.

### Decisions

1. **ADR-005 interpretation for AI-authored probes** (owner amendment
   3): every module that CONSTRUCTS geometry
   (`scripts/probes/probe_freeform_*.py`, `gen_import_fixture.py`) runs
   ONLY in the geo-worker sandbox, launched from the host by
   `scripts/run_pr25_discovery.py` as
   `docker compose run --rm -T --no-deps geo-worker python
   /scratch/pr25_discovery/probes/<probe> ...` - the scripts are copied
   into the scratch mount exactly like fabrication-loop jobs, so the
   pinned image is never rebuilt to run them. The service definition
   supplies network none / user 1000:1000 / read-only fs / cpus 1.0 /
   mem 2 GB; the hard timeout the worker's watcher normally enforces is
   supplied HOST-SIDE (subprocess timeout + `docker rm -f`). The
   backend container runs only ANALYSIS of produced artifacts
   (`validate_freeform.py`, `annotate_views.py` - they open files,
   never construct design geometry) and never orchestrates Docker.
   Unit tests exercise analysis functions against literal numeric
   fixtures (a hand-written tetrahedron); no test constructs kernel
   geometry. Trade-off: two copies of probe sources exist at run time
   (repo + scratch); the orchestrator re-copies from the repo on every
   run so the repo stays canonical.
2. **Discovery artifacts live in `data/geo_scratch/pr25_discovery/`**
   (+ render jobs under `data/render_scratch/pr25_*`). The sandbox has
   exactly one writable mount, so the dedicated discovery directory
   must live inside it; it never touches the DB or `data/exports`, the
   orchestrator wipes ONLY these two discovery areas at start (clean
   rerun from a fresh checkout), and the evidence is preserved until
   the operator signs `gate_pr25_discovery_visual.md`. Controlled
   cleanup after close: delete the two `pr25_*` areas; generated
   binary artifacts are NOT committed.
3. **Split gate semantics** (owner amendments 1/5/7):
   `gate_pr25_discovery_auto.py` (roster script 24) always runs its
   repo-reproducible sections; artifact sections and the
   operator-local reference-image section SKIP LOUDLY when their
   inputs are absent instead of failing another checkout; the git
   drift check runs only under `--host-drift` on the host because the
   image carries no `.git`. Trade-off: after post-close cleanup the
   roster covers only the repo sections - every run prints exactly
   which sections ran and which were skipped, so coverage is always
   visible.
4. **Determinism contract for probe artifacts**: STEP bytes (via the
   Phase 2 `export_step` + `step_timestamp_for(20260902)`) and the
   canonical OBJ writer (`%.6f`, fixed order, LF, ASCII) are
   contractual and must be byte-identical across two separate sandbox
   processes. **GLB is viewing-only and non-contractual** - measured
   2026-09-02 on the installed stack: build123d `export_gltf` writes
   METRES and per-face primitives, so a valid fused solid loads as ~10
   unwelded bodies (`watertight False`). The validator therefore
   tessellates the imported STEP itself (1.0 mm deflection, exact-merge
   weld) and checks in millimetres end to end.
5. **Independent validation stack** (owner amendment 5): OCC
   BRepCheck_Analyzer; OCC BRepAlgoAPI_Check with self-interference
   testing - the binding's usable call pattern is discovered at
   runtime and RECORDED (`ctor(shape, testSE=True, testSI=True)` on
   this image), never assumed from recall (ADR-009); kernel-vs-
   tessellation volume cross-check (REL_VOL_TOL = 2 %, a printed
   probe-only-judgement value); trimesh watertight/winding checks;
   boundary/non-manifold edge count computed networkx-free (the image
   deliberately lacks networkx, D-7 - `trimesh.repair.broken_faces`
   is unusable); duplicate-face detection; Euler-characteristic genus;
   minimum-thickness sampling at <= 200 deterministic vertex samples
   (`max_sphere`) -- WHICH IS UNAVAILABLE on the pinned image
   (trimesh.proximity.thickness needs the absent `rtree`; measured
   2026-09-02) and therefore degrades to a recorded `thickness_error`,
   never a silent number; restoring it is an implementation-slice
   dependency decision. OCC's BRepAlgoAPI_Check can also return
   IsValid=False with HasErrors=False -- an INDETERMINATE verdict that
   fails closed under its own honest label. A DELIBERATELY
   self-crossing sweep must be refused by this stack (or by the kernel
   at construction); the gate fails loudly otherwise.
6. **Renders reuse the Phase 9B protocol untouched**: job dirs in
   `data/render_scratch/pr25_*` with `job.json`
   (ortho_front/ortho_side/perspective_3q, 768 px, 24 samples, 90 s
   budget - probe-only-judgement values), rendered by the running
   worker; captions (fixture, approach, GLB hash, pass) are stamped
   UNDER the PNGs by Pillow in the backend (render pixels untouched)
   because the clay renderer deliberately draws no text. PNG bytes are
   not determinism-gated (ADR-045 precedent).
7. **Provenance vocabulary is the owner's six tags** - owner-ruling,
   measured-from-dimensioned-reference, image-derived-estimate,
   materials.yaml, probe-only-judgement, FABRICATOR-INPUT-REQUIRED -
   and the tests/gate enforce both the tags and the ABSENCE of the
   struck invented numbers (GRC density/wall guesses, armature
   percentage, the 560 kg example, "crane-trivial").
8. **Scope guards**: no file under `backend/app/`, `config/` or
   `schemas/` changes in this slice; the audit score does not move on
   probe results; LIMITATIONS 22 carries the exact sentence "kernel
   feasibility probed; no user-facing free-form capability
   implemented".

### Library facts verified against the installed stack (2026-09-02)

build123d 0.11.1: `sweep(sections, path, multisection, is_frenet, ...)`,
`loft(sections, ruled, ...)`, `Spline(*pts, periodic=...)`,
`Shape.tessellate(tolerance, angular_tolerance)`, `Shape.is_valid` is a
PROPERTY (calling it is the bug the smoke run caught), `export_gltf`
writes metres. trimesh 5.0.0: `is_watertight`, `is_winding_consistent`,
`body_count`, `euler_number`, `proximity.thickness(...,
method='max_sphere')`; `repair.broken_faces` requires the absent
networkx. OCP: `BRepCheck_Analyzer`; `BRepAlgoAPI_Check` accepts
`(shape, True, True)` and reports self-interference. All signatures
read via `inspect` inside the backend container, not from recall.

### Evidence

Red-first on pristine image `9fe4c4328116`: pytest
"file or directory not found: tests/test_pr25_discovery_assets.py" and
gate "can't open file '/app/scripts/gate_pr25_discovery_auto.py'"
(exit 2). Post-build evidence: `PR2_5_FREEFORM_DISCOVERY.md` (capability
matrix + verbatim failures),
`data/geo_scratch/pr25_discovery/summary.json`, the gate transcript and
test runs recorded in the loop docs at close.

**Operator-found red, 2026-09-03 (recorded honestly):** after the first
in-container rebuild, `test_watertight_tetrahedron_is_clean` FAILED --
obtained `volume_mm3: 166666.667`, expected `166666.66666666666` at
`rel=1e-9`. The defect was in the TEST, not the validator: the
validator's deterministic 3-decimal contract
(`round(float(mesh.volume), 3)`) is intentional and stands; the test
compared the unrounded analytic value at a tolerance tighter than the
rounding error. Fix: the test now asserts the rounded contract exactly
(`== round(100.0 ** 3 / 6.0, 3)`). Production validation was not
weakened; only the test and this evidence record changed.

### Close (2026-09-03) -- a DISCOVERY result, not capability

The operator walked `gate_pr25_discovery_visual.md` with independent
review and ruled: Step 1 YES, **Step 2 NO** (the probe forms are NOT
reference-faithful -- five per-reference findings recorded verbatim in
the sign-off), Step 3 YES, Step 4 YES; **BREP-first APPROVED WITH
CONDITIONS; acceptance gate design CHANGED** (eight owner conditions,
integrated into the report); **STEP canonical for the 316L family
CONFIRMED**. An earlier draft of the gate document wrongly implied the
in-container run verifies the local images; the operator caught it and
it was corrected before the walk (the host run carries that section).

Definitive /lf-gate evidence on image `52209e4a6eea` (start == end):
540 tests passed in BOTH worker states (worker removed: 1013.06 s;
worker up: 597.63 s), all 21 in-container roster scripts exit 0,
PR-3 static AND live PASS, Phase 9B + scope audit + Phase 14 frontend
PASS, PR-2.5 host gate 217/217 with zero skipped sections, $0, no
providers. Commit scope verified: exactly 20 paths (5 modified + 15
new); no JPG staged or tracked -- all 16 reference images remain
local, ignored and unpublished; probe/render evidence preserved on
disk pending the operator's post-close cleanup ruling.

**Reference-faithful geometry and user-facing free-form capability
remain UNBUILT.** Next: the free-form implementation slice via
/lf-next under the changed acceptance gate; its operator dependencies
are B-11b and the fabricator inputs.

## ADR-065 - FF-A1: incomplete-mass truth + production free-form validation (2026-09-03)

### Context

The FF-A/FF-A1+FF-A2 split was approved 2026-09-03 with eight binding
corrections plus one clerical correction (this ADR's accounting must
include `package_class.classify_reports`). FF-A1 is an INTERNAL
truth-foundation slice: it creates no user-facing incomplete-mass or
free-form capability and claims none — the model is exercised through
integration fixtures and a shim test primitive; the operator-visible
demonstration belongs to FF-A2.

### Decisions

1. **The mass model** (`app.geometry.mass_model`). `MassTruth`
   {mass_complete, known_geometry_mass_kg, missing_mass_inputs};
   `total_mass_kg` is a PROPERTY: the known figure when complete, None
   — never zero — when not. Unknown, malformed or inconsistent block
   data fails closed as incomplete with the defect named. Absent mass
   fields mean complete ONLY for manifests composed entirely of the
   frozen `LEGACY_COMPLETE_MASS_PRIMITIVES` ten — a PERMANENT
   versioning seam (it must never grow; growing it would change how old
   evidence is read; it is deliberately not a D-10 expiry). Every
   non-legacy primitive persists an explicit block.
2. **Digest policy**: `mass_model` and `required_validation_gates` are
   emitted only when they carry information. Byte-identical forever:
   manifests, packages, digests and re-exports of all-legacy designs
   (gate section 6 proved all 67 stored manifests legacy-clean and the
   real DB byte-identical). Legitimately new bytes: only future
   incomplete-capable/integrity-requiring designs.
3. **Applicability snapshot**: primitives may declare
   `REQUIRES_FREEFORM_INTEGRITY`/`INCOMPLETE_MASS_INPUTS`; `assemble()`
   persists `required_validation_gates` into the manifest; export
   classification reads ONLY that persisted snapshot (never the live
   registry/config — the ADR-063 no-laundering rule extended).
4. **`freeform_integrity_v1`** (`app.geometry.freeform_validation`) —
   the ADR-064 stack as reviewed production code (analyzer,
   self-interference with the INDETERMINATE IsValid=False/
   HasErrors=False verdict failing closed as needs_input, tessellation
   watertight/winding/edge/duplicate checks, 2 % volume cross-check,
   body count, genus; NO thickness check — rtree absent, LIMITATIONS
   22). NOT an import of the discovery probe. Row written by
   `persist_assembly_design` in the same validation operation and
   table as every layered row, duplicate-resolved by the same
   `created_at DESC, id DESC` rule, sharing the same structural run
   linkage AND the same D-24 identity gap — CLEAN stays unreachable.
5. **REFUSED ruling** (owner, 2026-09-03): for an applicable design a
   MISSING, FAILED or INDETERMINATE `freeform_integrity_v1` row —
   or an unknown/malformed required name — refuses export outright
   (`classify_reports(..., required_validation_gates=...)`; both
   callers pass the persisted snapshot). Deliberately harsher than
   PRE-FABRICATION marking: possibly self-intersecting CAD does not
   leave the building watermarked. Non-applicable legacy designs are
   untouched by construction. When a required row PASSED but the
   design is otherwise unproven, the package seals PRE-FABRICATION and
   the warrant carries the row's verdict; refusals never reach a
   warrant because no package exists.
6. **The null/fail-closed consumer contract**: total None never zero;
   the known figure only ever shown with its basis; structural
   centroid/overturning/bearing, fabrication lift/crane and the
   no-rigging-needed claim -> needs_input naming
   `missing_mass_inputs`; costing/BOM/quote -> `IncompleteMassError`
   -> structured HTTP 409 `incomplete_mass` (not_computable); DNA tags
   carry null + `mass_complete`; the critique handling component
   contributes nothing on incomplete mass (D-14 unchanged otherwise);
   API and frontend types accept null. There is NO input contract that
   makes mass-dependent checks pass on a partial mass — the complete
   armature contract (mass + centroid + per-module allocation, or a
   documented conservative worst case) is FF-A2 design work.
7. **Census** (gate section 1): an AST walk (string keys, attributes,
   names, args, keywords for mass_kg/total_mass_kg/crane_pick_kg/
   known_geometry_mass_kg) resolved to module::symbol against this
   audited allowlist — 28 consumer symbols found, all listed, each
   with a behavioral test or an audited no-change story:
   `mass_model::*` (the model);
   `assembly::assemble` (emits truth; legacy byte-identical),
   `assembly::build_segmentation` + `segmentation::_module_record` /
   `segment_solid` / `SegmentResult` (module masses are
   geometry-known; completeness gating lives in the fabrication gate);
   `validate::ElementReport`/`ValidationReport` (cascade = legacy
   complete), `validate::AssemblyValidationReport`/`validate_assembly`
   /`validate_mesh` (total row carries the labeled composite, None
   handled); `gates::_mass_centroid`/`validate_structural_gate`/
   `validate_fabrication_gate`/`_rigging_check`/`stored_water_mass_kg`
   (needs_input paths); `freeform_validation::run_freeform_integrity`;
   `costing.drivers::*` (IncompleteMassError), `costing.bom::*` +
   `costing.report::render_bom` (consume CostDrivers, which cannot
   exist for incomplete mass); `dna.store::derive_tags`/
   `precedent_block` (null + honest text); `critique::objective_score`;
   `council.prompts::*` (guidance text; PR-5 scope);
   `routes_assembly::persist_assembly_design`/`list_designs` (summary
   null + mass_model passthrough); `routes_costing::*` (409 mapping);
   `luxexchange::build_luxexchange_package` (seals the manifest
   wholesale; classification input); **`package_class::classify_reports`
   (+ `KNOWN_REQUIRED_GATES`, `_missing_row`) — the clerical
   correction: its persisted-applicability handling changed as
   decision 5.** Frontend consumers (typed, typecheck-proven; no test
   runner exists): `api/client.ts::MassModel/ManifestElement/
   DesignManifestResponse/PrecedentTags` (null unions),
   `workspace/InspectorPanel.tsx` (incomplete label; the "real mass"
   phrase removed), `panels/LibraryPanel.tsx` (null guard);
   `HistoryStrip`/`CompareView`/`DesignerWorkspace` already null-safe.
8. **Scope guards**: no new primitive, no registry change, no schema
   change, `e1a59fa6...` untouched; FF-A2 returns through /lf-next.

### What this buys / gives up

Buys: the platform cannot present a partial mass as a real one on any
surface, and free-form geometry has a production integrity layer that
export obeys before any free-form primitive exists. Gives up: the
sealed-manifest shape will change for FUTURE incomplete-capable
designs (new digests for them only — the ADR-057 precedent); costing
refuses rather than partially prices (deliberate); the critique
handling term goes neutral on incomplete mass rather than pretending.

### Evidence

Red-first on pristine `52209e4a6eea`: pytest "file or directory not
found: tests/test_mass_model.py" (exit 4) and gate "can't open file
'/app/scripts/gate_ffa1_auto.py'" (exit 2).

**Development run (image `a0948d1c5466` — evidence of the build
process, NOT the definitive chain; the gate's census fix reached the
container via docker cp)**: 51/51 new tests; gate PASS 35/35 after
the census caught four consumers the first allowlist draft missed
(render_bom, build_segmentation, _module_record, ValidationReport —
audited and added, never suppressed); then the full suite FAILED
honestly — 7 failed / 584 passed: the first drivers incompleteness
check failed closed on element-less manifests, the minimal legacy
shape costing has always accepted ("IncompleteMassError ... manifest
has no elements"). Fix: the incompleteness signals are a null
persisted report total or incomplete ELEMENTS; an element-less
manifest is judged by its report total (which came from a legacy
complete-mass manifest).

**Gate correction during /lf-gate (2026-09-04, operator-approved — the
fifth D-10-class instance):** the definitive roster run surfaced a real
FAIL in `gate_pr25_discovery_auto.py --host-drift` section 12 — it
asserted "backend/app, config, schemas untouched vs HEAD" against the
LIVE working tree, and FF-A1's ten legitimate uncommitted backend edits
tripped it. A slice-scoped promise had been written into a permanent
gate. Corrected per binding ruling: section 12 now pins the discovery
close commit `5cb0af3e2445c09b7426037fb8d02104be1ffeae` by FULL hash
(failure to resolve FAILS the check) and asserts that THAT COMMIT
changed no backend/app, config or schemas paths — the permanent
historical truth the section always meant; the timeless
no-reference-JPG-tracked check is unchanged; no production code was
touched by the correction. Recorded under D-10 in NEXT.md. Post-correction reruns (final image
`704fefba74fa`, which supersedes `2a317019b5b3` only by baking this
gate correction + documentation; the operator ruled the two-worker
suite evidence remains valid): host `--host-drift` PASS 218/218 zero
skipped (218, not 217 — the mandated commit-resolves verification is
its own check); in-container normal mode PASS 198 with only the
by-design operator-local-images skip; `gate_ffa1_auto.py` — the FIRST
run in the rebuild chain FAILED 1 of 35 with the failing check line
NOT captured (the chain kept only a 3-line tail; an orchestration
capture defect, recorded honestly), then THREE consecutive clean PASS
35/35 runs on the same image, including a backend-restart attempt and
an exact-sequence recreation+pr25-first attempt that both failed to
reproduce it. Probable cause — the first boot of a freshly built
image settling the DB (idempotent schema patches / WAL checkpoint)
while section 8 fingerprinted it — is DIAGNOSIS, not evidence.
Operational lesson: let the backend settle after a rebuild before the
first hermeticity-fingerprinting gate run, and never truncate gate
output in an evidence chain.

### Close (2026-09-04)

Preconditions met: authoritative in-container `gate_ffa1_auto.py`
PASS 35/35 zero skipped (three consecutive reproductions on final
image `704fefba74fa`); the operator walked and signed
`gate_ffa1_visual.md` YES/YES/YES on 2026-09-04 — with the honest
caveat, preserved verbatim in the sign-off, that Step 2's two
content-digest strings arrived as unfilled template placeholders and
byte identity rests on the operator's YES plus gate section 6's
independent machine evidence. Full /lf-gate chain: 591 tests passed
in BOTH worker states, all 22 hermetic roster scripts + PR-3
static/live + 9B + scope audit + Phase 14 frontend green; the PR-2.5
host-drift FAIL and its corrected 218/218 PASS, the out-of-contract
host gate_ffa1 invocation error, and the uncaptured 1/35 first-run
transient are all preserved above exactly as they happened. No
reference JPG staged or tracked; no probe/render artifact committed.
Closed as one commit on `main`. Next: FF-A2 (the ref-08 primitive)
via `/lf-next`; FF-A1's foundation stays dormant until it ships.

**Definitive run (final image `4ff126586ec3`, rebuilt from the final
working tree, identical at start and end; no docker-cp anywhere)**:
51/51 focused tests (`51 passed, 2 warnings in 41.63s`);
`gate_ffa1_auto.py` PASS — all 35 checks, zero skipped sections (67
real designs legacy-clean, real DB byte-identical, 20-attempt
impossible-PASS proof, torus_ring genus 1 with volume cross-diff
0.083 %); full regression suite `591 passed, 3 warnings in 649.71s
(0:10:49)` (540 pre-slice + 51 new). Frontend
`gate_phase14_auto.py --frontend-only` PASS (typecheck + production
build). $0 throughout; no providers.


## ADR-066 - FF-A2: freeform_loop, the first free-form primitive (2026-09-04)

### Context

FF-A2 was planned via /lf-next through four operator rounds (v1 -> 7
amendments -> v3 measurement record -> v4 final corrections), approved
2026-09-04 with binding conditions (bands unchanged; wall 6-20 with
3 mm embedment and >= 3 mm ligament; thin interface plate, never a
structural-foundation claim; honest stop on any construction/topology/
wall/fidelity failure; PRE-FABRICATION only; $0). Mid-build the
approved tube-annulus construction FAILED development (evidence below);
the owner ruled Option A: replace it with the hollow-lens + walled-
window-bore construction (short delta approved same day, with three
clarifications: the bore_center_height_fraction rename; the MEASURED
BRepExtrema bore-to-cavity distance is authoritative, >= wall - 0.5 mm
or FAIL, with no exact-clearance-by-construction claim; exact defaults
and ranges recorded in PARAMETERS, this ADR and the gate transcript).

### Decisions

1. **Construction (owner delta, as built):** OUTER lens = one loft
   along the straight vertical spine (2 tip vertices + 21 ellipse
   stations; width/depth from a deterministic sin^0.8 profile warped to
   the waist fraction; per-station y-offset = bow; per-station rotation
   = twist). CAVITY = inner lens (sections drawn in by wall_mm, tips
   pulled to the 2xwall profile crossing) minus the clearance cylinder
   (bore + wall + 2 mm liner allowance, full-through). M = OUTER -
   CAVITY - bore cylinder + interface plate (thickness = wall_mm,
   embedment exactly 3 mm). Both lens tips are TRUNCATED wall_mm short
   of the point - [arith] a formed 316L tip cannot be sharper than
   min_internal_radius = wall, and the loft-to-vertex apex tessellates
   degenerately (measured: 4 boundary/non-manifold edges; a blunting
   sphere fused onto the degenerate cone fails silently at 2 solids).
2. **The 2 mm bore-liner allowance [J, measured]:** growing an
   ellipse's semi-axes by wall_mm is NOT a parallel offset; the +wall
   corridor measured a 5.236 mm liner vs the 5.5 mm threshold, so the
   corridor is bore + wall + 2 mm and the AUTHORITATIVE clearance is
   the measured bore_to_cavity_mm (window-tube faces to the whole
   cavity component, one BRepExtrema call): 7.978 mm at the defaults;
   the fabrication gate FAILS below wall - 0.5 (owner clarification 2).
3. **Parameters (owner clarification 3 - exact values):** height_mm
   4250 [3500-5000, owner]; width_mm 2569 [1680-3600, img x owner];
   depth_mm 900 [300-1800, J - not image-measurable, stated];
   wall_mm 6 [6-20, arith embedment+ligament / mat]; section_twist_deg
   20 [-90..90, J; direction landmark img]; wobble_mm 150 [+/-1250 and
   <= 0.25 x height, J/owner]; plan_skew_ratio 0.15 [img +0.1466;
   -0.30..0.30] = the bore's horizontal offset fraction (changed
   meaning, approved); bore_width_mm 1110 [200-2000, img 0.4337xW];
   bore_height_mm 1290 [200-2500, img aspect 0.864];
   bore_center_height_fraction 0.485 [0.25-0.75, img 0.4854];
   waist_height_fraction 0.45 [0.25-0.65, J]; base_plate_diameter_mm
   600 [150-1500; floor = tip landing chord + 2x20 weld margin,
   derived]; material_id stainless_316l_sheet ONLY. REMOVED (tube-
   specific): taper_ratio, section_major_mm, section_minor_mm.
   Constants: N_STATIONS 21 [J], PROFILE_EXPONENT 0.8 [J],
   BORE_LINER_EXTRA_MM 2.0 [J measured], truncation = wall [arith].
   316L-only is ENFORCED, not assumed: validate() refuses every other
   material_id by name as an UNBUILT process; 316L is the SELECTED
   PROTOTYPE MANUFACTURING HYPOTHESIS (owner ruling - the photograph
   proves no material).
4. **Topology contract enforced in production:**
   freeform_validation.run_freeform_integrity gained an optional
   expected-topology comparison (per-boundary-component census:
   edge-connected face components of the welded tessellation, per-
   component Euler/genus, cavities = negative signed volume under
   consistent winding - networkx/scipy-free). The primitive declares
   EXPECTED_TOPOLOGY {1 solid, 1 through-opening, 2 boundary
   components, 1 sealed cavity, genus [1,1], euler [0,0], 0 extras};
   assemble() persists it (single-applicable-primitive designs only)
   and the persist hook passes THE SNAPSHOT, never the live registry;
   any mismatch FAILS => REFUSED for applicable designs (ADR-065 d.5).
   Without a declared contract the census is informational (FF-A1
   rows unchanged).
5. **Wall truth rows (fabrication gate):** geometric_wall_measurement
   (calibrated brepextrema_v1; PASS only when the controls-proven
   method measures min >= max(3 mm floor, wall - tol) AND max <= wall
   + tol with junction exceedances itemized, tol = max(0.5 mm, 5%);
   else needs_input - a 3.1 mm shell can never pass on the floor
   alone); fabrication_wall_approval (ALWAYS needs_input - nominal
   gauge is not engineering approval); forming_radius_mm (ALWAYS
   needs_input, FABRICATOR-INPUT-REQUIRED); bore_to_cavity_clearance
   (measured, FAIL below wall - 0.5). All four ride into the warrant
   only while unresolved; the passing integrity verdict seals into
   validation/freeform_integrity_v1.json, never the warrant.
6. **Registry widening + the approved subset conversions:** PRIMITIVES
   10 -> 11; gate_phase6c_auto.py:157 and test_slice_c.py:33 convert
   exact-ten to ten-is-a-subset per the recorded 2026-08-26 convention;
   the exact-eleven assertion lives in gate_ffa2_auto.py (roster
   script 26). The frozen LEGACY_COMPLETE_MASS_PRIMITIVES ten is
   untouched (permanent seam, ADR-065). The D-10 pre-widening sweep
   found exactly those two exact-set sites; gate_phase6a1 was already
   subset.
7. **Fidelity instrumentation:** projection_metrics() rasterizes the
   tessellation's front view (10 mm grid, deterministic) and measures
   the six committed ref08_landmarks.json bands from geometry - pixel
   comparison is never an auto-gate check. W/H + through-opening
   preservation are HARD validate() constraints; the other bands are
   fixture-fidelity checks in gate_ffa2_auto section 5, asserted
   verbatim and never adjusted.

8. **The mesh gate learns sealed cavities from the snapshot
   (2026-09-05):** the first full chain run FAILED honestly —
   `assembly_mesh: FAIL, body_count=2`: the Phase 2 mesh contract has
   always demanded ONE mesh body, and a sealed hollow shell
   legitimately tessellates as two closed surfaces (outer + cavity),
   which cascaded into costing/export/warrant/determinism failures.
   Fix: `validate_assembly` holds `body_count` to the PERSISTED
   `expected_topology.boundary_components` when the manifest declares
   one (exactly 2 for the lens — a tightening) and to exactly 1
   otherwise (legacy behaviour byte-unchanged; stored rows and legacy
   re-exports untouched because export reads persisted rows).
9. **Integrity tessellation refined (1.0 mm, 0.1 rad) -> (0.5 mm,
   0.05 rad) (2026-09-05):** the 5.0 m thin shell measured a 2.4-2.5 %
   kernel-vs-mesh volume gap that did NOT converge with deflection
   alone — measurement located the artifact in the ANGULAR tolerance
   (0.1 rad = ~0.6 mm sagitta at R 500 mm, dominating on curved
   shells). At the finer instrument the default lens agrees to 0.23 %
   and the 5.0 m envelope to 0.02 % (measured at 0.25/0.03).
   Strictly finer in both knobs — harder to fool; REL_VOL_TOL stays
   0.02. Cost: integrity runs slower on monumental shells.
10. **No predictive fold guard — loud build refusals instead
   (measured, 2026-09-05):** a section-extent/spine-curvature guard
   (0.75) was tried and DISPROVEN: it refused a proven-buildable
   combination (ratio 0.85 at 3.5 m) while missing real kernel
   failures (ratio 0.57 at 5.0 m — the cliff does not follow that
   arithmetic). Removed. Instead, every construction stage's checks
   raise a deterministic ConstraintViolation refusal (HTTP 422) with
   the real stage numbers when the kernel's robustness cliff bites
   (large twisted thin shells; silent no-op booleans measured at
   5000x3200 with twist -90 at bow 600-900, and at waist fraction
   0.25), and the measured cliff combinations are PINNED as refusal
   tests so any future image that moves the cliff says so loudly.
   Trade-off: some in-range extreme combinations refuse at build
   rather than being predicted at validate() — recorded in
   LIMITATIONS 22.

### What this buys / gives up

Buys: the first user-reachable free-form primitive, earned under the
changed eight-condition acceptance gate, with FF-A1's whole truth
foundation ACTIVE for the first time (incomplete mass, integrity-gated
export, PRE-FABRICATION-only). Gives up: the lens surface is a lofted
approximation whose real wall varies (measured, never claimed); the
global wall minimum sits at the truncated tips and reports needs_input
- the wall claim stays unearned until a professional rules the gauge;
one fidelity band (rim_ratio) is measured against a landmark whose
operational basis is under owner review (Evidence, below).

### Development evidence - the FAILED tube-annulus construction (preserved per owner ruling; NOT capability)

Red-first on pristine image 704fefba74fa: pytest exit 4 (four test
files not found), gate exit 2 (script absent), registry 10 without
freeform_loop. The originally-approved tube-annulus (butt-joined
half-loft loop) then failed development, all measured in-container
2026-09-04: 11-section half-lofts NECK on the strongly 3-D path (one
half 5.088e8 mm3 vs ~1.7e9 expected; loft interpolates sections with
no path); open multisection sweep REFUSED
(BRepOffsetAPI_MakePipeShell MakeSolid StdFail_NotDone, then
Standard_TypeMismatch - the ADR-064 PipeShell family); 3-section
segments COLLAPSE (1.6e3 mm3, invalid); 40 ruled segments BREACH the
cavity (1 boundary component, genus 3); 60 seal it (2 components,
genus [1,1]) but the wall pinches to a measured 1.032 mm at the
high-curvature shoulder (t=0.100) and does NOT improve with density
(0.904 at n=100, 0.917 at n=140 - an intrinsic near-fold pinch, not
chord sag); true-offset inner wires mis-rule against the outer
ellipses and BREACH (genus 16); the kernel 3-D solid offset REFUSES
on the C0 seams (both corner kinds); the reduced-axes station defect
measured 5.183 mm at a 600/200 station. The fidelity sweep (wobble
300-800, twist 30-90, sections 300-560, taper 0-0.45) measured
void_aspect 0.39-0.43 vs [0.69, 1.03], rim 1.24-1.57, offset ~0 - and
the projection argument (wobble moves limbs in DEPTH, which a front
projection flattens) plus the width identity made the aspect band
arithmetically unreachable for ANY tube parameterization. Reported;
the owner ruled Option A (this construction).

### Evidence - hollow-lens development runs (image 704fefba74fa via docker cp; the definitive chain on the rebuilt image is recorded below when run)

Defaults: build 31-38 s, one valid solid, 1.066e8 mm3 (~853 kg total
modeled 316L incl. the 13.6 kg plate at 8000 kg/m3); integrity PASS
with the full topology contract (2 components, genus [1,1], 1 sealed
cavity, volume cross-check 0.010-0.017); bore_to_cavity 7.978 mm PASS;
wall min 1.666 / max 5.998 => geometric_wall_measurement needs_input
(honest - the minimum sits at the truncated tips); fidelity measured:
W/H 0.6061 PASS, void_width_fraction 0.4319 PASS, void_aspect 0.8605
PASS, void_centroid 0.4839 PASS, void_offset 0.1496 PASS, rim_ratio
0.6358 FAIL vs [1.6, 2.4] - with rims left/right/apex 1100/340/1730 mm
against the photograph's own 1104/351/1774 mm under the same
instrument: the geometry matches the reference to ~1-3% on every rim;
the recorded 110px/55px ratio-2.0 landmark pair mixes a silhouette rim
with a 3-D scoop band that no projection measure reproduces (the
reference itself scores ~0.64 under the committed operational
definition). The band is NOT weakened; the discrepancy is reported
for an owner ruling.

### Definitive evidence (2026-09-05, rebuilt image bd85f7d13fb7 — no
### docker cp anywhere in this chain; 8 key files verified sha-identical
### between the working tree and the baked image; image identical at
### start and end of every run)

Focused tests: 81 passed, 0 failed in 2379.71s (0:39:39) across
test_freeform_loop (loop contract), test_wall_measurement (controls
calibration + gate rule), test_freeform_topology (7-combination matrix
+ 3 pinned kernel-cliff refusals + mechanism tests) and
test_freeform_chain (real API end to end). An earlier dev run recorded
64173s wall-clock (17:49:33) — suspension-inflated overnight, the
known environment class; functional evidence only.

gate_ffa2_auto.py (roster script 26): **FAIL — 1 of 60 checks, all 8
sections run, zero skipped** — the single failure is the standing
fidelity question: rim_ratio measured 0.6416 vs band [1.6, 2.4].
Everything else green, highlights: two-process STEP determinism
pid=138 vs pid=148, both sha256
c4136aec8495d4b715d2f2218759397560b18e9b263c26c314d31d4ad1d30842;
topology contract [1,1]/2 components/1 sealed cavity PASS;
authoritative bore-to-cavity clearance 7.978 mm PASS; wall min 1.666 /
max 7.999 => geometric_wall_measurement needs_input (honest);
fidelity: W/H 0.6061, void_width 0.428, void_aspect 0.8527,
void_centroid 0.4834, void_offset 0.149 — five of six bands PASS;
REFUSED on missing/failed/indeterminate rows (three 409s);
PRE-FABRICATION sealed with the passing integrity verdict in
validation/freeform_integrity_v1.json and an unresolved-only warrant;
segmentation analysis volume-conserved to 0.000000%, over-envelope
raised loudly; hermeticity: real DB byte-identical, data/exports
unchanged, no JPG in the tree. (Capture note: the orchestration line
printed exit 0 because the gate ran through a tee pipe — the pipe
exit is an artifact of the capture; the verdict is the transcript
banner: FAIL 1 of 60.)

gate_ffa1_auto.py on the same image: PASS — all 35 checks, zero
skipped (the census found no new unlisted mass consumers in FF-A2).

The rim_ratio question, precisely: under the committed operational
instrument (widest side rim at the void-centroid row / apex-column
band) the built geometry measures rims left/right/apex within ~1-3%
of the reference photograph itself (1100/340/1730 mm vs the photo
1104/351/1774 mm), and the photo scores ~0.64 on the same instrument
— but the approved band [1.6, 2.4] encodes the 110px/55px pixel pair
whose 55px apex reading is a 3-D surface-scoop feature no projection
can reproduce. The band was NOT touched; the gate FAILS honestly; the
ruling on the landmark's operational basis is the owner s.

11. **The rim_ratio ruling (owner option (a), 2026-09-05):** the band
   was re-derived from the reference image under the SAME deterministic
   projection instrument, with the acquisition and every raw number
   recorded in ref08_landmarks.json: segmentation = mean(R,G,B) >= 160
   AND max channel difference <= 20 inside a recorded 13-vertex ROI
   polygon (excluding the bright facade rail that merges with the
   sculpture s upper-right edge), binary closing 3x3 x1, largest
   4-connected component; native 1280x959 pixel raster, y down, single
   below-left perspective camera; image sha256 bfe1662b... Metric
   renamed **projected_side_to_apex_band_ratio** and made continuous:
   numerator = wider of the left/right rims at the void-centroid ROW
   (122/67 px), denominator = occupied run from the silhouette top at
   the void-centroid COLUMN (139 px at image-x 735; the retired
   topmost-pixel column was discontinuous — it missed the void on the
   reference and hit it on the geometry). **Exact reference result
   122/139 = 0.877698; band = +/-20% = [0.7022, 1.0532].** The
   geometry measures 0.9167 under the same definition — within 4.5% of
   the reference. HISTORY PRESERVED, not rewritten: the original
   110 px/55 px = 2.0 landmark and its [1.6, 2.4] band stand in
   ref08_landmarks.json as rim_ratio_HISTORICAL, and the definitive
   1-of-60 gate FAIL of 2026-09-05 above stands as recorded — the 55 px
   reading measured the reference s 3-D concave surface scoop, a
   feature invisible to any front projection and therefore incompatible
   with the automatic metric. The scoop and rim shaping remain a
   SEPARATE MANDATORY visual-gate comparison (gate_ffa2_visual.md
   Question 1b); passing the projection metric claims nothing about
   them. No other fidelity band changed.

### Definitive post-ruling evidence (2026-09-05, rebuilt image
### 8cb914b6e200 — key files sha-verified into the bake; image
### identical at start and end; runs completed before an operator
### machine sleep, verified intact after wake)

Focused tests: 81 passed, 0 failed in 2461.94s (0:41:01).
gate_ffa2_auto.py: **PASS — all 63 checks, all 8 sections, zero
skipped, exit 0** — incl. the re-derived
projected_side_to_apex_band_ratio measured 0.925 on the definitive
image vs band [0.7022, 1.0532] (the 0.9167 figure earlier in decision
11 was the pre-rebuild dev measurement; the definitive value is
0.925), the three history-preservation checks (band-from-exact-
instrument, rim_ratio_HISTORICAL intact, no-3D-scoop-claim), and
two-process STEP determinism pid 62/72 both sha256 c4136aec8495... —
IDENTICAL to the pre-ruling hash: the ruling changed measurement and
documentation, not one byte of geometry. gate_ffa1_auto.py: PASS
35/35, exit 0. Host scope audit: PASS, exit 0.

### D-10 instance six (2026-09-07, operator-ruled correction)

During the FF-A2 /lf-gate stage-1 run (image 8cb914b6e200, suite 672
passed in the worker-removed state), gate_ffa1_auto.py FAILED 1 of 35,
verbatim: FAIL [6] every stored manifest is legacy-clean (72 checked)
-- [(70b12dd3-de56-4eae-9ad8-214718d7a872, new keys present)]. The
design is the OPERATOR S first real freeform_loop, persisted
2026-09-07 05:40:29 during the FF-A2 visual walk — its mass_model /
required_validation_gates / expected_topology keys are exactly what
ADR-065 decision 2 calls legitimately new bytes. The section had
encoded an FF-A1-era truth (no primitive could emit the keys) as a
permanent assertion — the sixth D-10 instance. Operator-ruled
correction (production behavior untouched, design untouched, FAIL
preserved): section 6 now asserts the timeless form — every ALL-LEGACY
manifest (elements within the frozen ten) is legacy-clean and
byte-compatible; a manifest carrying the new keys must contain a
non-legacy primitive AND every non-legacy design must explicitly carry
mass_model + required_validation_gates (no silent validation bypass);
legacy/non-legacy counts printed. An earlier same-day stage-1 attempt
(06:00-06:23Z) died at 54%% of the suite when the Docker Desktop
engine crashed (500s on the docker socket, likely sleep-cycle
fallout); it produced no gate verdicts and is recorded as
infrastructure, not evidence.

### Close (2026-09-07)

Preconditions met: gate_ffa2_auto.py PASS — all 63 checks, zero
skipped — on the definitive chain, and the operator personally signed
gate_ffa2_visual.md on 2026-09-07: Question 1 YES (the freeform_loop
appearance is correct and acceptable; the apparent left/right opening
difference accepted as viewing-orientation dependent), Question 1b
(the 3-D apex scoop and rim shaping, the separate mandatory
comparison) ACCEPTABLE, Questions 2 and 3 YES. A 570-second render
timeout during the walk is preserved as operational finding D-25 —
the verdict stands on viewport inspection, which the gate permits.

Definitive /lf-gate chain, ONE final image 044446e54c0e (identical at
start and end, 07:37-09:35Z 2026-09-07; corrected gate_ffa1 sha
f56afbc40817 verified host==container): suite **672 passed in BOTH
worker states** (worker REMOVED via rm -sf, pinned, 2746.79s; worker
UP, pinned Up-Less-than-a-second -> Up-48-minutes, 2828.09s); all 23
in-container roster gates exit 0 incl. gate_ffa2 63/63, corrected
gate_ffa1 36/36 (71 all-legacy + 1 non-legacy printed), lf103a, pr25
normal 198/198 with only the by-design operator-local skip, pr1, pr2
and the 17 phase gates; PR-3 static (stdin) + live both PASS;
gate_phase9b PASS; Phase 14 geometry (container) + frontend (host)
PASS; scope audit PASS; pr25 --host-drift 218/218 zero skipped. /usr/bin/bash
throughout; no providers; no downloads. An earlier stage-1 attempt
(06:00Z) was voided by a Docker Desktop engine crash and recorded as
infrastructure. No reference JPG tracked (committed record:
reference_manifest.json, REFERENCE_ANALYSIS.md, ref08_landmarks.json
— text only); no generated probe/render artifact committed. Closed as
one commit on main. Next: /lf-next picks the queue (PR-4 is next in
the approved order now that the free-form capability exists,
ADR-060); FF-A2 does not start it.


## ADR-067 - PR-4: transport trips are loaded, never bounded (2026-09-07)

**Decision.** Replace the transport line's trip count — until now
`max(ceil(mass/payload), ceil(modules/per_trip))`, a LOWER BOUND
presented as a trip count — with a real loading of the trucks:
first-fit-decreasing over the measured per-module masses (heaviest
module first, ties broken by module id ascending, each module on the
first trip with room under BOTH the payload and the bed count, every
comparison unrounded via `math.fsum`). The BOM line describes the result
only as **"a deterministic conservative feasible allocation"** (operator
amendment 3, binding) — never as minimal or optimal, because
first-fit-decreasing can use more trips than the cleverest packing and
the platform does not claim what it did not prove. Every trip prints its
module IDs, masses, load and remaining capacity on both limits; a module
over the payload refuses the line naming the module and both numbers;
no valid allocation → `not_computable`, never a count.

**The failure case that killed the old formula, preserved verbatim:**
four modules of 6,000 kg at a 10,000 kg payload and 4 per bed. Old line:
`max(ceil(24000/10000)=3, ceil(4/4)=1) = 3 trip(s)`. Reality: no two 6 t
modules share a 10 t truck — four trips. The bound understated the
count, and a BOM that understates trucks understates the quote and puts
an illegal load on the road. `gate_pr4_auto.py` section 3 prints both
numbers side by side forever.

**What it buys.** The first cost line whose quantity is a proven
feasible plan rather than arithmetic; per-trip evidence the operator can
check by hand; refusals that name the module (the crane analogue of
ADR-056's heaviest-module pick).

**What it gives up / new machinery.**
* `CostDrivers` gains `module_masses_kg` — (id, mass) per module, id =
  `<element>#<index>`, read STRAIGHT off the manifest's segmentation
  elements block (one measurement path, ADR-056 discipline). A manifest
  whose module count disagrees with its per-module records reports the
  masses unavailable and the line refuses — no partial load is priced.
* Conservation guard: the module masses must agree with the validation
  report's total within **0.1 % [J]** (`MODULE_MASS_AGREEMENT_PCT`,
  judgement value, deliberately tighter than segmentation's own
  volume-conservation band so a bookkeeping defect cannot hide inside a
  legitimate measurement band) — else `not_computable` with both sums.
* Independent invariant gate (`verify_allocation`, also run by
  `gate_pr4_auto.py` on the printed result): every module id on exactly
  one trip; loads fsum exactly to the input masses; every load ≤ payload
  and every bed count respected. A wrong allocation fails LOUDLY.
* Input safeguards (operator ruling, verbatim): empty/duplicate module
  ids, non-finite or non-positive masses, invalid payloads and
  non-positive/non-integral bed counts are rejected
  (`AllocationInputError`); rounding is display-only.
* The `binding: weight|bed space` key and the old formula text are gone
  from the line contract; `tests/test_costing.py`'s transport tests were
  updated to the NEW contract (spec-driven, listed in the PR-4 build
  evidence) and `_segmented_manifest` now carries the per-element module
  records real manifests have carried since slice C2.
* Rotation is still not modelled (LIMITATIONS §10 note stands), and the
  fleet is uniform: ONE payload, ONE bed count for the whole job.

**Digest ruling (operator, 2026-09-07, explicit).** The LUXEXCHANGE
package seals `costing/bom.json` (`luxexchange.py`), so **re-exporting an
old design may produce a new package digest solely because the BOM
transport representation and wording changed. Existing sealed packages
are never rewritten; geometry, manifest and validation bytes remain
unchanged.** Approved as a legitimately-new-bytes case in the ADR-057
precedent class; it narrows ADR-065's "re-exports of all-legacy designs
byte-identical" claim to the non-BOM package members from this slice on.
The Phase 2 canonical STEP hash `e1a59fa6…` is unaffected — PR-4
contains zero geometry.

**Evidence.** `tests/test_transport_allocation.py` (red first — the
suite failed on the missing module before `transport.py` existed) +
updated `tests/test_costing.py`; `scripts/gate_pr4_auto.py` (roster 27),
9 sections, $0, offline, real rate card sha256-identical before/after;
`gate_pr4_visual.md` for the operator's eye. The real
`config/costing.yaml` transport entries remain null and the operator's.

### D-10 instance seven — the FF-A1 census guard caught PR-4 (2026-09-07)

The definitive PR-4 /lf-gate chain FAILED at `gate_ffa1_auto.py`, stage 1,
gate 22 of 25. Preserved verbatim, never erased:

```
[1 AST consumer census (ADR-065 allowlist)]
  FAIL [1] every mass consumer is on the ADR-065 allowlist --
       app.costing.transport::NoFeasibleAllocation reads ['mass_kg'];
       app.costing.transport::TripAllocation reads ['total_mass_kg'];
       app.costing.transport::allocate_trips reads ['total_mass_kg']
      consumers found: 31 (allowlist entries: 29)
...
FAIL -- 1 of 36 checks failed.
```

**This is the guard working, not a defect.** ADR-065 section 1 statically
scans all of `backend/app` for code reading mass-named keys and refuses
anything not on the audited allowlist. PR-4's new `app.costing.transport`
is a genuinely new mass consumer — `NoFeasibleAllocation.mass_kg`,
`TripAllocation.total_mass_kg`, and `allocate_trips`' fsum of the module
masses — and the allowlist, written before PR-4 existed, had never
audited it. The seventh time a correct guard has met legitimate new code
(D-10); the first time the FF-A1 census specifically has.

**The audit, and why the exemption is honest.** The allocator is pure
arithmetic over `(module id, mass)` pairs handed to it by
`bom.transport()`. It opens no manifest, no validation report and no
database, and it never judges whether a mass is COMPLETE. Every path
that reaches it runs `drivers_for_assembly` first, which raises
`IncompleteMassError` before a single per-module mass is read —
**incomplete mass is refused UPSTREAM of allocation**, proven
behaviourally by `gate_pr4_auto.py` section 7e (`incomplete mass raises
before allocation`) and by `gate_ffa1_auto.py` section 2, not asserted
here. The allocator therefore cannot be the place an incomplete figure
leaks into a price.

**Operator ruling 2026-09-07:** admit the module as THREE EXACT SYMBOLS —
`("app.costing.transport", "NoFeasibleAllocation")`,
`("app.costing.transport", "TripAllocation")`,
`("app.costing.transport", "allocate_trips")` — deliberately NOT the
`("app.costing.transport", "*")` wildcard this session proposed, so any
future symbol added to that module must be audited on its own merits
rather than inheriting the exemption. Allowlist entries 29 -> 32;
consumers found 31. Nothing else in the gate changed; the check itself
is no weaker (a 32nd unaudited consumer still fails it), and design
70b12dd3 and every other section were left untouched.

**Recovery protocol (operator-approved, 2026-09-07)** — used instead of
repeating the full two-hour chain, because the correction touches only a
gate script and evidence documents: hash `backend/app`, `frontend/src`,
`tests`, `config`, `schemas`, the dependency files and every Dockerfile
BEFORE the correction; change only the census gate and the evidence
docs; rebuild; rerun the corrected FF-A1 gate; rerun the whole roster on
the final image; RETAIN the already-completed worker-removed suite
result (707 passed) because the production and test bytes are proven
unchanged; then one full suite with the render worker restored, Phase 9B
and all host gates. Any differing production/test/config/build hash
abandons the protocol and restarts the complete chain. The reused and
the new evidence are reported separately in PHASE_6_REPORT.md.

### Close (2026-09-08)

Preconditions met: `gate_pr4_auto.py` PASS (9 sections, rate card
sha256-identical `4eb861d0…` before and after) and the operator signed
`gate_pr4_visual.md` on 2026-09-07 — all four steps YES, recorded
verbatim in that file (auto gate PASS; the 3-versus-4 disproof and
per-trip loading confirmed by hand; a real design's transport line
`[RATE MISSING]` naming `install.truck_payload_kg` with no invented
trip count; all three costing entries still null, hashes identical).

Definitive two-worker-state evidence, ONE final image `a8a6f3218ba8`
(created 2026-09-07T12:13:41Z by the recovery rebuild, identical at
chain end 2026-09-08T07:19:58Z; PR-4 source and both gate scripts
verified host==container by sha256; backend source is not
bind-mounted): the first chain's worker-REMOVED suite **707 passed
(3158.46s)** RETAINED under the operator-approved hash-proven recovery
protocol (15 production/test/config/schema/build hashes identical
before and after the census correction; only `gate_ffa1_auto.py`
changed, `f56afbc40817` → `7aff70d6d53e`); corrected `gate_ffa1_auto`
**36/36** (31 consumer symbols found, all listed; allowlist 32; 79
all-legacy + 1 non-legacy manifests); all 25 in-container roster gates
exit 0 incl. `gate_ffa2` 63/63, `gate_pr4`, `gate_pr3 --static`;
worker-UP suite **707 passed (3317.11s)** with the worker pinned `Up 1
second` → `Up 56 minutes`; `gate_phase9b` PASS; host gates `gate_pr3
--live`, `gate_scope_audit`, `gate_phase14 --frontend-only`,
`gate_pr25 --host-drift` 218/218 all PASS. A live HTTP smoke build of
`freeform_loop` on the running image (HTTP 200, 577,884-byte glTF)
confirmed the platform was left testable. $0 throughout; no providers;
no downloads; nothing generated or private enters the commit. Closed as
one commit on main. Next per the approved order: PR-5 via /lf-next;
PR-7A's parallel branch (`parallel/pr7a`, operator-authorized) may now
rebase onto this commit — PR-4 does not start either.


## ADR-068 - PR-5: one story about lifting — AI contract, gate bases, scorer and documents repaired (2026-09-08)

**Decision.** Every surface that describes lifting and module limits says
what the fabrication gate has MEASURED since slice C2 (ADR-056) and PR-1
(ADR-059): the crane picks the **heaviest module after segmentation** and
`max_module_m` binds **per axis**. Three sentences of the GEOMETRIST
contract (`prompts.py`: "bind per element", "per-element … fabrication
limit evidence", "Assembly F … checked per element") now say so, and the
test that pinned the retired wording (`tests/test_cascade.py`) pins the
new wording and asserts the retired tokens ABSENT (assembled at runtime).
The two `needs_input` bases in `validate_fabrication_gate` that still read
"per-element mass" / "per-element bounding box" now name the heaviest
module with its real kg and the per-axis envelope. Line-number citations
in NEXT.md had all drifted (284/332 → 287/296/336; 876/897 → 1051/1089):
the loop cites by SYMBOL from here on.

**The scorer (operator clarifications 1–3, binding).**
`objective_score()` no longer grades a design's "handling" by its WHOLE
mass, and no longer invents a lift limit: the pre-PR-5
`run_vision_critique.py` read a top-level `max_lift_kg` that no manifest
has and silently scored EVERY design against `1000.0` kg — a live-money
code path, preserved here as the defect it was. Now
`facts_from_manifest()` reads the same fields the gate reads
(`fabrication_limits.max_lift_kg`, `segmentation.heaviest_module_kg`)
and states its basis explicitly: `measured_heaviest_module` only when
`assembly_mass_truth` proves the mass model COMPLETE; a legacy
unsegmented total is a pick weight only for a SINGLE complete element
(`single_complete_element`); a multi-element unsegmented design, an
incomplete mass, a missing lift limit, or a bare total with no basis is
`unavailable`. Unavailable is GENUINE: the handling component is None,
the composite `objective_score()` is None with the reason recorded
(`objective_score_detail()` exposes every component), and
`score_delta()` returns None rather than reading an unavailable score as
improvement or deterioration. Two gates that used the old dict shape
were updated because clarification 1 forbids what they did:
`gate_ffa1_auto` §2 compared an incomplete-mass score `<` a real one;
`gate_phase5_auto` §5 scored a bare total. D-14 (the scorer does not
STEER the loop) stays open and separate.

**Documents (clarification 4).** Historical statements are preserved
verbatim with a prominent dated correction placed beside them, never
rewritten: `PHASE_6_REPORT.md`'s heading "PHASE 6 GATE: PASS" (the
slices' AUTO gates passed; the phase's own closing condition — the live
operator gate — is still pending, so the phase is NOT closed);
`PHASE_11_12_13A_REPORT.md` "Phase 9B and Phase 10 are untouched" (true
on 2026-08-22, false from 2026-08-24). `LIMITATIONS.md` §11 "mapper
covers the four primitives" struck (it covers ten; the one it does not is
`freeform_loop` — FF-A3's starting fact) and §12 "segmentation is Phase 6
slice C" struck (C2 built it). Operator doc 07 shows the heaviest-module
row, the per-axis envelope and the two by-design NEEDS INPUT rows.

**The D-10 sweep (clarification 5).** `gate_pr5_auto.py` §5 AST-scans
every roster gate for equalities against a set/frozenset literal or
`len(...) == int` whose operand names a GROWTH collection (registry,
legacy mass set, declared inputs, import whitelist, rate-card entries,
reference manifest); each hit must carry a `D-10-frozen:` marker whose
reason is ≥ 8 words, cites an ADR/record/ruling, and is not a generic
"intentional" — no module-wide exemption exists; structural equalities
(a sha256 is 64 chars, determinism needs two processes) are LISTED as
reviewed, never hidden. Three checks were converted to timeless forms
(each a gate edit under this approval): `gate_phase6a2`'s "unknown
primitive" example was the literal `basin_spline` (expiring the day
slice D builds it) → a name derived at run time and proven absent from
the live registry; `gate_scope_audit` §5's order check by FIRST
OCCURRENCE anywhere in NEXT.md (D-10 instance four) → by entry position
inside the work-queue section; `gate_phase6c2` §8's `missing_entries()
== 39` (expiring the moment the operator fills one rate) → the six C2
paths exist by name, count printed. `tests/test_freeform_loop.py`'s
duplicate `len(PRIMITIVES) == 11` became a subset check — the exact set
lives only in `gate_ffa2` (ADR-066). Ten growth literals now carry real
reasons (ADR-066 exact-eleven; ADR-065 frozen legacy ten; ADR-066's
three declared inputs; ADR-030 import ceiling; the fixed B-11 reference
record, five sites).

**What it gives up.** The GEOMETRIST prompt changed by three sentences
without a live run to watch the model read them ($0 by ruling; the pin
is offline) — recorded, not hidden. The critique scorer's contract
changed shape: callers that pass a bare `total_mass_kg` now get None.
The ADR-065 census correctly flagged the two new scorer symbols
(`facts_from_manifest`, `objective_score_detail` — both mention
`total_mass_kg`), listed as exact symbols with their audit, per the PR-4
ruling; a wildcard was not used.

**D-26 (clarification 6).** `gate_pr5_auto.py` fingerprints the real
DB+WAL only after the live backend answers `/api/health` ok AND two
consecutive identical fingerprints — a condition, bounded at 60 s and
failing loudly, never an arbitrary sleep; every manifest it scores is
temporary in-memory data.

**Evidence (build, 2026-09-08).** Focused suite 132 passed on image
`f1b2d5ece31c`; definitive `gate_pr5_auto.py` PASS (49 checks) on
`0d1be7cea13b` with host==container sha256 for the gate and
`critique.py`; a mutation probe loosening the single-complete-element
rule failed exactly the clarification-2 test and nothing else; every
edited roster gate rerun green (ffa1 36/36 with the two new census
symbols, phase5, 6a2, 6c2, ffa2 63/63, pr25 198/198, costing, pr4,
scope audit on the host: "LF-103A (entry 5) before PR-2.5 (entry 6) —
44 queue entries scanned"). The gate's own first run FAILED 5 of 54 on
the author's defects (recorded in PRODUCTION_V1_REPORT.md), then PASSED.
Verbatim scorer transcript and the sweep tally (8 growth literals all
justified, 25 structural reviewed) in PRODUCTION_V1_REPORT.md. Visual
gate `gate_pr5_visual.md` pending; not closed.

### Close (2026-09-08)

Preconditions met: `gate_pr5_auto.py` PASS (49 checks) and the operator
signed `gate_pr5_visual.md` on 2026-09-08 — all six steps YES, recorded
verbatim in that file, with the real design `621d7497…` reading the
basin pick weight as the heaviest of 9 modules, 1,472.19 kg versus an
11,346.1 kg element total.

Definitive chain under the operator's risk-based protocol, ONE image
`753490ced0af` (identical at start, stage 1 and end, 12:39–14:17Z):
26 of 26 PR-5 files host==container by sha256; 132 focused tests +
`gate_pr5_auto` 49/49; the full suite ONCE with the render worker
REMOVED — **720 passed (3246.54s)** — with PR-4's 707 two-state run
retained as the unchanged baseline because PR-5 touched no rendering or
packaging code; all 28 roster gates in their required states (25
hermetic worker-removed, `gate_phase9b` worker-up pinned, `gate_pr3`
static via stdin + live on the host, `gate_scope_audit`,
`gate_phase14 --frontend-only`, `gate_pr25 --host-drift` 218/218);
compose state and image pinned at every boundary; nothing failed, so no
code or gate was touched. $0 throughout; no providers; no downloads.
Closed as one commit on main. Next per the operator's stated priority:
**FF-A3 — a typed brief / Council request selecting and parameterizing
`freeform_loop` honestly** — via /lf-next (its measured starting fact:
the fabrication-time PRIMITIVE INDEX already offers `freeform_loop`
while no brief, Council prompt or `spec_mapper` alias can request it);
PR-7A's parallel branch (ADR-069 reserved) rebases onto this commit.
PR-5 starts neither.
[Correction 2026-09-09, owner ruling: an unmerged parked branch cannot
reserve an ADR number — ADR-069 is FF-A3's below; PR-7A is renumbered
if resumed. The sentence above is preserved as written.]

## ADR-069 - FF-A3: a typed brief can ask for the ref-08 loop — honestly (2026-09-09)

**Context.** After FF-A2 the fabrication-time PRIMITIVE INDEX listed
`freeform_loop`, but nothing upstream could ask for it: the Designer
prompt named the lens without its parameters, `spec_mapper._ALIASES`
had no entry for it, the schema forced every design — a dry sculpture
included — to invent a two-node pipe network, and the schema's own
`primitive` description named three primitives that never existed
(`nozzle_ring`, `lotus_array`, `spline_loft`), text pasted verbatim into
every paid Designer call. The owner approved the FF-A3 plan on
2026-09-09 including hydraulic schema change B, with nine binding
corrections recorded here.

**Owner corrections (binding, recorded).** (1) PR-7A stays parked at
its local commit `1292e6c` — no reset, rebase, merge, push, tests or
container use. (2) This slice takes **ADR-069**, the next number on
main: an unmerged parked branch cannot reserve an ADR number; PR-7A is
renumbered if resumed. (3) `freeform_loop.PARAMETERS` holds **12 scalar
geometry parameters plus `material_id` = 13 registry keys** — never
"twelve total". (4) The schema no longer says every numeric parameter is
a dimension object: dimensional values are `{value, unit}`; ratios,
fractions, counts and enumerations are PLAIN scalars; no fake ratio unit
was added; the gate proves a plain ratio schema-valid and every ratio
carrying any unit refused. (5) Schema change B is exact: a dry design
(`water.has_water` PRESENT and `false`) may carry empty `nodes`/`edges`;
a wet design keeps 2 nodes and 1 edge; an ABSENT `has_water` never
matches the dry branch — positive, negative and absent-guard tests
exist. (6) Synthetic hand-authored Council alternatives prove replay
and pipeline compatibility only — not that an AI selected the primitive
from prose; that sentence appears in the fixture note, the generator,
the gate, the visual gate, LIMITATIONS, NEXT and README. (7) The visual
gate types and confirms the brief through the existing Brief tab; the
claim "typed brief → Council selection → sculpture" is NOT made or
closed until one real live Council + fabrication demonstration has been
separately cost-approved, run and recorded — the build approval
authorizes no provider spend. (8) The optional fixture loader accepts
an enumerated DISCOVERED basename only; absolute paths, separators and
traversal are refused before any path is joined. (9) The rank-1 spec
states all 12 scalars plus `material_id` explicitly; silent registry
defaults never masquerade as Council parameterization.

**Decisions.**

1. **The Designer vocabulary is generated, never typed.**
   `prompts.primitive_index_surface()` prints, per primitive, every
   registry key with the spec-level names that reach it (from
   `spec_mapper.spec_aliases_for()`), unit, `[min..max]` and default, and
   honesty lines derived from the module's own declarations
   (`SUPPORTED_MATERIAL`, `INCOMPLETE_MASS_INPUTS`,
   `REQUIRES_FREEFORM_INTEGRITY`). ADR-026's anti-drift property is
   preserved: widening the registry changes the prompt automatically.
   Trade-off: the static Designer prefix grows for every session (the
   gate prints the size); it is still one cache prefix per session
   (ADR-024).
2. **"Valid Design Spec" now means registry-valid.**
   `orchestrator._validate_live_primitives()` runs the live-id check,
   then `assembly_plan_from_spec()`, then each primitive's own
   `validate()` (parameter arithmetic, no geometry). A refusal becomes a
   bounded re-ask carrying the registry's real text; ANY other exception
   is also an error — never a silent pass. This applies to every
   primitive, not only the lens (a lens-only rule would be a new D-10
   special case). Consequence found at once: the suite's canonical
   `valid_example_spec()` put a nozzle node on `column_01`, which the
   slice-B mapper (ADR-054) has refused since 2026-08-26 — every scripted
   Council test had been persisting a spec fabrication would refuse. The
   fixture now drills the nozzle ring into `basin_01`; the check was not
   loosened.
3. **The mapper covers eleven; ratios are plain numbers.**
   `_ALIASES["freeform_loop"]` reaches all 13 keys; `_dimension_to_number`
   REFUSES a `{value, unit}` object on `_ratio`/`_fraction` targets
   (before FF-A3 a ratio in metres was silently multiplied by 1000 and a
   wrong unit passed through — the most dangerous silent failure in the
   mapper); a `parameters.material_id` contradicting the element's is
   refused rather than overwritten. Count/enumeration targets keep the
   old behaviour — recorded as D-27, not fixed here.
4. **Schema change B + descriptions.** Top-level `if/then/else`: the dry
   branch requires `water` present, `has_water` present and `const
   false`; `then` sets `minItems: 0`; `else` keeps 2/1 — so an absent
   `has_water` falls to the wet minimums. The `primitive` description
   cites the LIVE PRIMITIVE INDEX and names no id; the `parameters`
   description states the dimension/plain-scalar rule and that omitted
   parameters are registry defaults, not design decisions. The Phase 2
   canonical STEP `e1a59fa6…` is untouched (schema governs spec
   validation, not geometry). No registry, config, primitive or kernel
   change.
5. **Fixtures.** `intake_ffa3_v1.json` (operator-typed fields, no parser)
   and `council_session_ffa3_v1.json`, SYNTHETIC: `make_ffa3_fixture.py`
   composes the brief with the route's own `summary_block` (round-tripped
   through the wire format exactly as the API does), generates every
   PROMPT with the real builders, derives providers from `council.yaml`
   and the critic from the ADR-025 never-a-producer rule, validates every
   spec against schema + registry + mapper + `validate()`, and its
   `--check` mode (run by the gate and a test) fails loudly the day a
   builder or the schema changes. The RESPONSES are hand-authored and say
   so in their first bracket; token counts are `len(text)//4`; the dollar
   figure replay recomputes was never spent. Rank 1 is the FF-A2
   acceptance lens (seed 8) so its STEP must equal FF-A2's.
6. **Kernel cliff, recorded not hidden.** Three of the six alternatives
   first written for the fixture passed the primitive's `validate()` and
   were REFUSED at build by the ADR-066 stage checks: the exact mirror of
   the acceptance lens (twist −20°, skew −0.15) — "inner lens produced 1
   solids, volume −326316588654.8 mm³, expected one positive solid";
   4800 × 2700 × 1000, wall 8, twist −25°, bow 200, skew −0.12 —
   "cavity collapsed or split: clearance corridor left 1 solids, volume
   −27648.4 mm³"; 3600 × 2200 × 800, wall 6, twist −35°, bow −100, skew
   −0.20 — "clearance corridor left 2 solids". Each refusal is loud and
   deterministic; the replacements that build are the sets now in the
   fixture (listed under Evidence). That `validate()` accepts what the
   kernel refuses remains the recorded FF-A2 limitation (no predictive
   fold guard, by measurement).
7. **Demo loader.** `POST /api/council/demo-session` takes
   `{"fixture": <basename>}` matched against `^council_session_[a-z0-9_]{1,64}$`
   AND the discovered files; the response carries the fixture's own
   `synthetic` flag and, for a synthetic one, the words "never spent".
   D-2 (a synthetic session in the real DB looks completed with a dollar
   figure) is not widened silently: the loader's note and the visual
   gate say what the figure is.

**What it gives up.** The Designer prompt changed shape and length
without a live run to watch a model read it — $0 by ruling; the live
demonstration is the visual gate's Step 6 under its own approval. The
boundary check adds up to two paid re-asks per alternative when a
designer writes a spec the registry refuses; that is cheaper than the
fabrication call that used to discover it. The fixture is pinned to
today's prompt builders and schema: any change to either must
regenerate it (loud, by design).

**Evidence (build, 2026-09-09).** The three replacements for the refused
variants (decision 6): openai alt 1 — 4250 × 2569 × 900, wall 6, twist
+20°, bow −150, skew −0.15, window 1110 × 1290, centre 0.485, waist
0.45, plate 600; anthropic alt 2 — 4800 × 2700 × 1000, wall 8, twist
+20°, bow 200, skew 0.12, window 1200 × 1400, centre 0.5, waist 0.5,
plate 700; openai alt 3 — 3600 × 2200 × 800, wall 6, twist +25°, bow
100, skew 0.15, window 900 × 1050, centre 0.46, waist 0.42, plate 600.
All six fixture alternatives build through the kernel (85.4 / 38.5 /
22.0 / 34.1 / 53.4 / 38.8 s, one module each). Focused suite 155 passed
(302.75 s). Host gates: scope audit PASS; PR-2.5 `--host-drift`
218/218. Definitive `gate_ffa3_auto.py` on image `0d4180d2b8d7`
(09:46:18Z → 09:53:44Z): **55/55, exit 0**, first run and definitive
run both green without any gate edit; 12 of 12 FF-A3 files host ==
container by sha256; the rank-1 Council spec's STEP
`f3ccb95345d8534b…` equals the FF-A2 acceptance fixture's STEP built in
a second process (pids 167 / 185); replayed fixture cost recomputed
$0.20223 and never spent; real DB `a0e7225c322a` and WAL
`e3b0c44298fc` identical before and after. Verbatim transcript in
`PRODUCTION_V1_REPORT.md`. Same image, same chain: nine affected roster
gates green (`phase3`, `phase4`, `6a2`, `6b`, `pr1`, `13a`, `ffa2`
63/63, `pr5` with the sweep listing the new gate's six structural
equalities as reviewed, `ffa1` 36/36 with 32 consumers — no new mass
consumer), then the full suite **737 passed (6202.65 s)** with the
render worker up at both ends (720 + 17 new). Visual gate
`gate_ffa3_visual.md` pending; Step 6 (live Council + fabrication) is a
separate cost approval; not closed.

### Step 6 attempted and NOT ACHIEVED (2026-09-14) + owner ruling

The operator authorized ONE live Council session and ONE fabrication
attempt under the platform's standard $5.00 run cap, after a projection
this session computed from the real FF-A3 prompts (expected actual
$0.99) and the cap-safe reservation bounds (openai $0.4019, anthropic
$0.8729, **kimi $3.2686**). The session ran 46 s and halted:
researcher/primary on openai succeeded ($0.007725, 490 in / 650 out);
researcher/parallel on kimi FAILED with a transient `Connection error.`;
its reservation went UNCERTAIN at the full $3.268608 bound (ADR-061
failing closed — no first-party proof exists that a failed attempt was
not billed); the ADR-023 retry's own reservation was then refused
($3.276333 spent + $3.268608 bound > $5.00 run cap) and the session
finalized `halted_budget` with **zero Design Specs and zero arbiter
decisions**. Session `2a7d3e5b-2b78-42f6-9479-637f0e1feaa6`;
`budget_events` `b162e615…` `cap_breach`. Real money billed: $0.007725;
$3.284036 counted against the $25 day cap; no safety lock engaged. The
fabrication attempt was NOT run (the authorization said stop on any
provider failure). **The Council never reached the Designer stage, so
it neither selected nor declined `freeform_loop`: the demonstration did
not reach the question.** Nothing was rerun, no prompt was touched, no
selection was coerced.

**Owner ruling, 2026-09-14 (binding):** no second Step 6 attempt now; no
`council.yaml` change, no removal of kimi, no weakening of fail-closed
accounting, no increase to the permanent $5 / $25 caps; **Step 6 remains
NOT ACHIEVED and is NEVER marked PASS**; the halted session is
preserved and **real Council selection of `freeform_loop` remains
UNPROVEN**; FF-A3 may pass its formal gates and close **only** as
*"typed-brief/Council contract implemented and fixture-gated; live
end-to-end selection blocked by D-28 and not claimed"*; **D-28 becomes
the next separate, rollbackable slice**, planned via `/lf-next` and not
started until FF-A3 closes and its plan is approved, with the goal of a
fail-closed reservation computed from the real serialized request
envelope + configured maximum output + a proven conservative margin
(context size an absolute ceiling, never an assumed billable request),
ADR-009 first-party documentation fetched and recorded, and tests for
retries, uncertain holds, multibyte prompts, maximum output and
reservation-underflow safety; reservation
`9077e77a-95ec-4633-b4be-c5a07ad4f74f` is **NOT reconciled** until the
operator reports the Moonshot/Kimi console for 2026-09-14 08:22–08:23
UTC.

### Definitive chain (2026-09-14) — risk-based, accepted with Phase 9B FAILING

Image `sha256:772e352a34ea…`, identical start and end; 20/20 files host
== image; suite **737 passed** worker-REMOVED (PR-4's two-state baseline
retained — FF-A3 changes no rendering or packaging code); **25/25**
in-container gates incl. `gate_ffa3_auto` **55/55**; PR-3 static via
stdin; scope audit, Phase 14 frontend, PR-2.5 host-drift 218/218 and
PR-3 live all PASS. **`gate_phase9b_auto.py` FAILED TWICE and is NOT
recorded as passing**: invocation 1 timed out at its fixed 300 s wait
while the render succeeded 15 s later; the one authorized rerun reached
section 5 and timed out at its fixed 20 s conversion wait while that
conversion completed 4 s later. Measured cause, timed in the worker
container: the worker rescans the whole scratch mount every poll —
**1,904 directories, 8.89 s per scan** — so pickup latency scales with
the backlog. The operator accepted the chain under the risk-based
exception on five recorded grounds (no rendering/conversion/packaging/
worker code changed; the previous closed Phase 9B PASS remains the
regression baseline for those unchanged bytes; both pieces of work did
complete, only late; the measured scan cost is the cause; FF-A3's own
gate and every other gate passed) and opened **D-29** (linked to D-1):
the fix must avoid per-poll full rescans and provide bounded, indexed or
event-driven pickup plus safe retention/reaping — raising timeouts is
not acceptable. **This chain must never be described as "all gates
green."** No scratch artifact was deleted, moved or modified.


## ADR-070 - D-28: an honest reservation bound — the real request envelope, never the whole context window (2026-09-15)

**Decision.** A TEXT request's reservation bound is derived from the
request that will actually be sent, never from the model's entire unused
context window (the ADR-061 fallback, kept only as the absolute ceiling):

    input_tokens_bound = min(context_window, utf8_bytes(request) + 256)
    bound_usd          = input_tokens_bound x highest input rate
                       + max_tokens x output rate   (ceiling micro-USD)

The 256-token framing margin is the owner's amendment of 2026-09-14: a
conservative JUDGEMENT value, recorded as such on every hold — openai
documents 3 tokens per message plus reply priming (an estimate),
anthropic bills no system-added tokens, and moonshot documents nothing
about framing, so it is **not first-party proof for anthropic or kimi**.
The assumption is self-policed two ways instead of trusted: (1) at
settlement, billed input tokens above the recorded `input_tokens_bound`,
or output tokens above `max_tokens`, engage a `ceiling_violated`
provider/model safety lock and halt the scope **even when the DOLLARS
still fit** — a bound that lands under the real cost must fail closed,
never silently absorb; money above the bound still engages
`bound_exceeded` first, exactly one lock per settlement. (2) at every
startup, `envelope_census` re-checks EVERY settled text call in history
against prompt-bytes + margin (pre-D-28 rows measured against the
ADR-061 ceiling they actually held) and engages a GLOBAL lock on the
first falsification, via `reconcile_spend_books` in the operator
surfaces. VISION requests stay on the ADR-061 window bound unchanged —
ADR-070 changes text requests only. The pricing values, context windows
and `$5` run / `$25` day caps are untouched (`pricing_version`
unchanged); no `council.yaml` change; kimi is not removed; the
fail-closed accounting is not weakened — the owner ruling of 2026-09-14
is honoured on every point.

**Why.** Measured on 2026-09-14 (ADR-069): one dropped kimi connection
held $3.268608 — 65% of the $5 run cap — because the reservation was the
whole 1,048,576-token context window. The FF-A3 Step 6 retry was refused
by the cap and the live demonstration died on infrastructure, not on
anything a model did. Under the envelope bound the same ~2.1 kB
researcher prompt holds for **under $0.20**, and the uncertain hold plus
one retry fits under $5 with room to spare (pinned in
`test_d28_envelope_bound.py`).

**Mechanics.** Every provider builds its request envelope through ONE
builder (`_build_text_request`) whose output is what the SDK is called
with — the priced envelope IS the sent envelope, asserted field-for-field
for all three providers, with ≥ 64 bytes of non-content headroom pinned.
Multibyte prompts bind by UTF-8 BYTES, never characters (a byte-vs-char
bound is a real underflow: 8,000 CJK characters are 24,000 bytes). The
derivation (`envelope_bound_usd_micro` in `app.ai.call_log`) needs a
first-party `context_window_tokens` still — absent, it raises
`PricingLookupError` rather than assume. The arithmetic behind every
hold is persisted as JSON on `spend_reservations.bound_basis` (additive
startup-patched column, schema_patches recorded; pre-D-28 NULL rows
reach both operator surfaces labelled `PRE_D28_FORMULA`, never guessed)
and `spend_admin.py census` reports it READ-ONLY (byte-identical DB
pinned before/after). Retries, exhaustion and startup recovery keep
every uncertain hold at its own envelope bound with its basis intact.

**Verification (recorded honestly).** New hermetic suite
`tests/test_d28_envelope_bound.py` (37 tests, $0, injected transports)
plus updates to `tests/test_spend_reservations.py`; 61 targeted tests
pass. The host Docker engine did not start on the build machine
(2026-09-15), so the definitive in-container run of the FULL suite and
the roster is DEFERRED: the suite and `gate_pr2_auto.py` were run on a
host Python 3.12 venv (editable install, `--ignore-requires-python` —
the production pin stays `>=3.11,<3.12`), and three tests needed
platform fixes the container will also accept: a missing
`bound_basis_for_display` import in `routes_ops.py` (the actual defect),
a census-fixture prompt lengthened so its tokens-per-byte ratio is
strictly below 1 as the assertion documents, and the float-drift
preamble rewritten to `0.1 + 0.2` because Python 3.12's compensated
`sum()` makes the original 3.11-era `1e-6 x 1000` demonstration exactly
exact (gh-100425). The in-container suite + full roster re-run is the
first action when the engine is back; this chain is NOT claimed as the
definitive gate chain. Reservation `9077e77a-…` remains UNCERTAIN and
unreconciled, owner-pending, exactly as ruled.

**Consequences.** Live Council sessions no longer risk the cap on one
dropped connection; FF-A3 Step 6 (real Council selection of
`freeform_loop`) is UNBLOCKED for a separately cost-approved retry —
ADR-069's binding status stands until that retry is run and recorded.
The ADR-061 ceiling function is retained verbatim as the ceiling the
envelope bound can never exceed.


## ADR-071 - MS-A1: perforated_screen — the first mesh-class primitive, honestly scoped (2026-09-16)

**Owner ruling.** 2026-09-15, in the session that adopted this slice:
"approve everything yourself, build everything yourself, use what you
think makes us reach free-form/mesh capability faster, and give me the
capability" — recorded as the delegation under which this slice ran,
$0, no live provider calls.

**Decision.** The registry widens 11 → 12 with `perforated_screen`: a
flat or single-curved 316L sheet with a deterministic grid of
through-holes (circle or hexagon across-flats) — the **perforated-skin
class** of mesh-look sculpture. It is built on the proven B-rep route
(ADR-064's BREP-first recommendation): every hole cutter is fused into
ONE compound tool and removed in a SINGLE boolean subtract; the result
runs the whole production integrity stack (FF-A1) and exports like any
other primitive. **It is NOT an open wire lattice, and this ADR claims
no lattice capability: B-11b stays OPEN and release-blocking until the
owner supplies a real mesh/lattice reference — none of the 16 supplied
references shows one, exactly as recorded.**

**The signed floors (every refusal carries the real computed numbers).**
Material: `stainless_316l_sheet` ONLY (the perforated-sheet prototype
hypothesis, same class as freeform_loop's 316L ruling). Ligament =
`hole_pitch − hole_size` ≥ `sheet_thickness` (a cut feature cannot be
thinner than the sheet — the materials.yaml `min_feature = wall`
formula, not a new constant). `hole_size ≥ sheet_thickness` (same
floor). Edge margin ≥ sheet_thickness; the grid must fit each span with
its margin, axis named. Total holes ≤ **1500** — a measured
build/render-load bound (D-25: dense free-form tessellation already
times out Blender renders on this hardware), refusal prints nx/ny/total.
Curved panels: radius ≥ 5 × sheet_thickness (recorded as a rolled-sheet
forming JUDGEMENT value) and at most a 270° wrap, arc length binding
stock length 3000 / height binding stock width 1500 — read from
`material.stock_size_mm`, never hardcoded. Mass is COMPLETE (volume ×
8000 kg/m³; no armature — unlike freeform_loop the screen carries no
hidden structure). Wind/overturning checks conservatively ignore the
porosity (silhouette basis) — recorded as conservative, never credited.

**Measured.** The default fixture (1400 × 900, pitch 40, Ø20, t=6; 748
holes) builds deterministically — two-process STEP sha256 pinned in
`tests/test_perforated_screen.py`. A realistic 2000 × 1200 panel
(pitch 40; **1421 holes**) builds in **17.8 s**, far under the 120 s
sandbox timeout. Integrity fixtures use a 42-hole grid because the
FF-A1 self-interference census is quadratic in face count (a 748-hole
run did not finish in 10 minutes); watertightness/topology is
count-independent. Assembly proven end-to-end: 316L plinth +
`stack_on` screen → ONE fused body; a basalt parent refuses honestly
(3.0 mm seat < 10 mm joint floor, pinned). Export classification for
the reference assembly: **PRE_FABRICATION** (complete mass, rate card
unconfigured — 8 lines `missing_rate`, no total, exactly the honest
BOM truth).

**Roster consequences (D-10 discipline).** The exact registry set lives
in exactly ONE roster gate and moved eleven → twelve in
`gate_ffa2_auto.py §1` with a dated D-10-frozen reason; `gate_pr5_auto`
§5's sweep token follows the literal rename (`expected_eleven` →
`expected_twelve`). New roster script 30, `gate_msa1_auto.py`
(54/54): registry set, refusal truth, two-process determinism,
integrity + genus, build-time bound, end-to-end mass/BOM/export on a
throwaway DB, mapper/Designer reachability (8 keys, 19 aliases, no
dangles), the non-316L Designer-boundary negative, and hermeticity.
**One host-honesty fix rides along:** the FF-A2/FF-A3 "no reference
JPG" checks now fail on TRACKED jpgs only — the operator-local set is
gitignored by owner policy (ADR-064), and the old form could never pass
on the host where those files exist; the security property (a reference
never ships in the image) is "untracked", which the new check proves.
The FF-A3 council fixture regenerated via its designed maintenance path
(`make_ffa3_fixture.py`; tokens_in 5150 → 5358) — the prompt surface
now carries the twelfth primitive, drift-guard updated, nothing
weakened.

**Verification (recorded honestly).** `gate_msa1_auto.py` 54/54;
`gate_ffa2_auto.py`, `gate_pr5_auto.py`, `gate_ffa1_auto.py`,
`gate_ffa3_auto.py` re-run and PASS on the host venv; targeted pytest
(119 passed: the new file, freeform_loop, spec_mapper, slice b/c,
FF-A3). The host Docker engine is still down, so the definitive
in-container full-suite + full-roster chain remains DEFERRED to engine
recovery — the same recorded caveat as ADR-070; the host chain
(full suite green; affected gates green) is the standing evidence and
is NOT claimed as the definitive container chain.

**Update, same day (environmental incident, not a code defect).** The
operator's C: drive hit 100% (373 MB free) during the closing full
suite: 21 failed + 3 errors, EVERY one traced to
`sqlite3.OperationalError: database or disk is full` or STEP-write
failure — temp DBs could not be created and exporters could not write.
After freeing what this session safely could (pip cache, its own stale
%TEMP% artifacts — ~520 MB), all 24 affected tests re-ran green
(36 passed, 9 min 39 s). The full-suite green for the MS-A1 tree is
thus: run evidence pre-incident + the re-verified subset; a fresh
complete full-suite run on this disk is NOT safe to claim (520 MB
headroom) and the definitive in-container chain is deferred anyway.
The operator should free disk space — the geo_scratch/render_scratch
reaping is D-29/D-1 and awaits an owner instruction; nothing was
deleted beyond this session's own garbage.

**Deferred / NOT claimed.** Open-lattice/mesh-native geometry (B-11b —
owner reference required; procedural meshes still have no boolean
machinery, per the PR-2.5 probes). Perforated screens in materials
other than 316L. Porosity-credited wind loading. Hole grids beyond the
1500 cap (needs the D-25 render/mesh decision first). FF-A3 Step 6

## ADR-073 - ENV-1: the build moves to a new machine; the deferred in-container chain runs and finds three expired gate literals (2026-09-28)

**Context.** ADR-070/071/072 each closed with the same recorded caveat:
"host Docker engine down — definitive in-container suite + roster
re-run DEFERRED to engine recovery." On 2026-09-25 the repository was
checked out on a DIFFERENT machine (Lenovo 83JJ, i7-13650HX, 24 GB,
RTX 4060 laptop GPU, Windows 11 Pro zh-CN, user `Lenovo`; repo path
`C:\Users\burook\luxuryform`, remote `Bekimoon0043/Sculpture`). The
machine had Docker Desktop installed but no virtualization: Windows'
`VirtualMachinePlatform` and `Microsoft-Windows-Subsystem-Linux`
features were disabled and `HypervisorPresent=False`. A bare reinstall
of Docker Desktop (2026-09-25 → 09-28) could not fix that.

**Environment repairs (operator-approved via UAC, none touching the
repo).** (1) `dism /online /enable-feature` for both features + restart
→ `HypervisorPresent=True`, `wsl --status` "Default Version: 2", engine
29.8.0 up. (2) `icacls … /grant Lenovo:(OI)(CI)F /T` on the repo (owned
by Administrators; `compose up` failed `mkdir …\data: Access is denied`)
→ 433 files, 0 failures. (3) Python 3.11.9 user-scope (winget) for the
four host-side gate sections. (4) `frontend/npm ci` via the npmmirror
registry for `gate_phase14 --frontend-only`.

**Transport ruling (Dockerfile untouched).** pip against
`files.pythonhosted.org` measured **31 kB/s** here; the 67.6 MB OCCT
wheel timed out at pip's 120 s read-timeout on the first build. Three
PyPI mirrors were probed for the EXACT pinned wheel: ustc 570 kB/s,
tsinghua 1,060 kB/s, aliyun 512 kB/s. The build used the Dockerfile's
own `PIP_INDEX_URL` build-arg (`https://pypi.tuna.tsinghua.edu.cn/simple`);
every wheel is version-pinned and hash-checked by pip, so the mirror is
pure transport (same reasoning as ADR-017's deb mirror). Layer 3/13
completed in 53 s; `SMOKE OK: build123d 0.11.1`; 9 GL debs `sha256sum -c`
PASS. Recorded as a machine-local operator fact, not a default.

**Decision — what the chain found and what changed (four files, all
gate/test scaffolding, zero production code, zero config, zero schema;
canonical STEP `e1a59fa6…` untouched by construction):**

1. `tests/test_costing_config.py::test_costing_material_keys_match_materials_yaml`
   pinned the material registry as exactly four ids. SC-A1 (ADR-072)
   added `stainless_316l_cast`; SC-A1's targeted host run never reached
   this file. **D-10 instance eight.** Fixed: five ids with a
   `D-10-frozen:` reason citing ADR-072.
2. `scripts/gate_phase6c2_auto.py` — PR-5's own D-10 conversion still
   asserted `len(c2_paths) == 6` (4 materials × seam + 2 install paths).
   Five materials make seven. **D-10 instance nine.** Fixed to the
   timeless form `len(raw["materials"]) + 2`, count printed.
3. `scripts/gate_pr5_auto.py` §5 keyed its 6c2-conversion needle on the
   label text "carries the six slice-C2 paths"; needle follows the new
   label and a new check asserts `len(c2_paths) == 6` is absent.
4. `scripts/gate_phase14_auto.py` frontend section: `subprocess.run(…,
   text=True)` decodes with the HOST locale codec — GBK on this zh-CN
   Windows — and Vite's UTF-8 output raised `UnicodeDecodeError` in the
   reader thread, leaving `proc.stdout = None` and crashing the gate
   before any verdict. Fixed: `encoding="utf-8", errors="replace"`,
   None-safe tail. Not reachable on the previous en-US host.

**Verification (definitive in-container chain, this machine).**
Baseline on pristine `9e96582` image `f8abc47dc092`: suite **832 passed,
1 failed** (item 1, verbatim in this ADR's evidence), 26:42. After the
fixes, final image **`68fbab78e83c`** identical at roster start and end:
**29/29 in-container roster gates exit 0** (`gate_costing`, `ffa1` 36/36,
`ffa2` 63/63, `ffa3` 55/55, `lf103a`, `msa1` 54/54, `phase11`, `13a`,
`14` geometry, `15`, `2`, `3`, `4`, `5`, `6a1`, `6a2`, `6b`, `6c`, `6c2`,
`8`, `8b`, `9a`, `pr1`, `pr2`, `pr25_discovery` 63/63, `pr4`, `pr5`,
`sca1` 63/63, `scope_audit`) + `gate_pr3 --static --stdin`; host gates
`gate_pr3 --live` PASS, `gate_scope_audit` PASS, `gate_pr25_discovery
--host-drift` 66/66 (artifact + reference sections skipped loudly — the
operator-local set is NOT on this machine), `gate_phase14
--frontend-only` PASS. **Recorded honestly:** in the first post-fix
roster pass `gate_ffa3_auto` §9 FAILED (health `ReadTimeout` 11 polls,
WAL never quiesced in 60 s) while the backend sat at 151 % CPU / 3 GB
directly after `gate_ffa2`'s 334 s run; the identical gate on the
identical image PASSED 55/55 minutes later (0 polls, 1 poll). This is
D-26's hazard family (a fixed duration standing in for a condition),
recorded as **D-26b** in NEXT.md, not silently re-run away. Full suite
on the final image `68fbab78e83c`, worker-REMOVED (no render-worker
image exists on this machine), image identical before and after:
**`833 passed, 4 warnings in 4154.05s (1:09:14)`, exit 0** — the 1:09
against the baseline's 0:26 is the suite sharing the backend's CPU with
the roster pass that ran ahead of it in the same chain; no test timed
out. `gate_phase9b_auto` NOT run (render worker not built on this machine —
its Blender image is a deliberate deferred download; D-29 unchanged).

**Not claimed.** No new capability. `data/` on this machine is EMPTY:
the previous machine's designs, the 1,902 preserved scratch directories
(D-29), the uncertain reservation `9077e77a…`, and the 16 operator-local
reference images exist only there until the operator copies them.
`CLAUDE.md`'s environment section is corrected in this commit; the old
laptop's constraints stand as history.

**Spend.** $0. No provider call.

(real AI selection of ANY primitive from prose) — unblocked by D-28
(ADR-070) but still not run; the Designer index now OFFERS
perforated_screen, nothing more.


## ADR-072 - SC-A1: crescent_ring — the crescent-moon sculpture primitive (2026-09-16)

**Owner ruling.** 2026-09-16: the operator supplied a reference photo
(mirror-polished stainless crescent, 1.9 m H × 2.0 m L × 0.4 m W, with
organic liquid forms inside on a black base) and directed: "make it
create this sculpture" — continuing the 2026-09-15 delegation to build
autonomously.

**Decision.** The registry widens 12 → 13 with `crescent_ring`: a
vertical partial-torus crescent — a circular (or vertically elliptical)
tube section revolved about the torus axis by `arc_span_deg`, oriented
into the XZ plane, centreline centre at z = R + radial semi-axis so the
tube's lowest point rests exactly at z = 0 (the locked origin
convention; an arc that misses azimuth 270° would float and is REFUSED
by the nadir rule, naming the arc numbers). Parameters:
`centerline_radius_mm` (400–1500), `tube_diameter_mm` (80–500),
`arc_span_deg` (90–330), `gap_azimuth_deg` (0–360, deterministic
placement), optional `tube_depth_oval_mm` vertical squash, and
`material_id` restricted to a NEW material — `stainless_316l_cast`
(welded & mirror-polished 316L, density 8000, wall envelope 3–500 mm,
PROVISIONAL fabricator-set values, commented FABRICATOR-INPUT like
freeform_loop's) — or `stainless_316l_sheet`. The tube diameter binds
the CHOSEN material's wall envelope with real numbers. `height` is
DERIVED (2·R + tube), never a parameter: a spec carrying a `height` key
is refused naming that relationship (`_DERIVED_REFUSALS` in the
mapper).

**Scoped OUT, honestly.** The reference's ORGANIC LIQUID FORMS (the
drip column and the pool) are hand-sculpted free-form — that class does
not exist in the kernel (beyond even freeform_loop) and is NOT claimed
by this slice. The crescent + base plate reproduces the sculpture's
silhouette; the interior organic forms remain a future free-form slice.

**Measured (photo replica: R=800, tube=350, span=300, gap=0, cast).**
1950 mm tall × 1950 mm long × 350 mm deep, min.Z = 0 — the reference's
"2.0 m" is the same extent at photo precision. Volume agrees with
analytic torus-segment theory to ~1e-15; two-process STEP sha256 pinned
(`920d1caaa01a…`); warm build 0.03 s. Assembly proven: 316L-cast plinth
+ stack_on crescent → ONE fused watertight body, 5938 kg total,
mass_model COMPLETE, export class PRE_FABRICATION with the honest
rate-incomplete BOM (9 lines, 8 missing_rate). A basalt parent refuses
at the 10 mm joint floor.

**Roster consequences (D-10 discipline).** Exact set moved 12 → 13 in
`gate_ffa2_auto §1` and `gate_msa1_auto §1` (dated D-10-frozen lines);
`gate_pr5_auto` GROWTH_TOKENS follows `expected_twelve` →
`expected_thirteen`; new roster script 31 `gate_sca1_auto.py` (63/63):
registry set, refusal truth (material/envelope/oval/span/nadir),
two-process determinism, integrity + theory volume, demo-dimension
fidelity pins, end-to-end mass/BOM/export on a throwaway DB,
mapper/Designer reachability + the derived-height negative, the
non-316L boundary negative, hermeticity. The FF-A3 council fixture
regenerated via its designed maintenance path (Designer tokens_in
5358 → 5509 — the prompt surface now lists the thirteenth primitive).

**Verification (host chain, container engine still down — deferred,
same recorded caveat as ADR-070/071).** `gate_sca1_auto` 63/63;
`gate_msa1_auto` 54/54; `gate_ffa2_auto` 63/63; `gate_pr5_auto` PASS
(live backend); `gate_ffa1_auto` 36/36; `gate_ffa3_auto` 55/55 (after
the fixture regen); 40 new tests in `tests/test_crescent_ring.py`;
142 targeted tests passed. NOT claimed: a fresh full-suite run (C: disk
headroom remains ~0.5 GB — see ADR-071's incident) and the definitive
in-container chain.

## ADR-074 - PR-6: per-element costing, one-owned joints, confirmed budgets bind (2026-09-28)

**Owner approval.** The operator approved the `/lf-next` PR-6 plan on
2026-09-28. Binding requirements: one trusted measurement path per
material for volume/mass/exposed finishing area/fabrication/purchase/split
seams; cross-material joints billed once to an explicit owner; shared
crane/transport/install once at assembly level; confirmed intake budget
bound to the BOM; incomplete costing structurally unable to render a total
or quote; operator rate-card and provider-price worksheets delivered. $0.

**Decision 1 — the manifest is the single measurement boundary.** Existing
assembly manifests already carried each element's BREP volume/mass and each
split/joint seam's measured run/face. They did NOT carry per-element skin
area; only the fused mesh report carried total surface area. Proportional
allocation would silently spread one element's area over another material,
and re-measuring inside costing would create a second geometry path. PR-6
therefore adds deterministic `surface_area_mm2 = sum(face.area)` while the
element's real BREP is already in memory in `assembly.py`. Costing only
reads the persisted number. Exposed finishing area is that element's skin
minus every measured joint-contact face touching it. A historical manifest
without the new key reports finishing `not_computable` with one rebuild
action; it never apportions the fused total.

**Byte/determinism consequence.** Canonical STEP geometry and the Phase 2
hash `e1a59fa6…` are untouched: no primitive, parameter, placement, fusion
or exporter arithmetic changed. Manifests and LUXEXCHANGE packages for
designs REBUILT after PR-6 gain deterministic per-element
`surface_area_mm2`, so their package digest may change for that stated
reason. Sealed old packages are never rewritten. The single-material route
continues to call the existing `build_bom`; its serialized BOM emits no
PR-6 `elements`/`joints` keys, preserving its pre-PR-6 shape.

**Decision 2 — fabrication per element, installation once.**
`drivers_per_element()` returns typed `ElementDrivers` and `JointDrivers`
from the persisted manifest. `build_assembly_bom()` runs the existing
material-purchase/fabrication/mould/split-seam arithmetic independently for
each element, with line ids `<element>/<line>`, then adds joint lines and
one shared install block. Crane uses the assembly's measured heaviest
module; crew uses total assembly mass; transport uses the complete measured
module-mass tuple. No shared line is emitted per element.

**Decision 3 — cross-material joints have one owner or no money.**
`config/costing.yaml` v3 adds `joints.cross_material_owner`, deliberately
null in the shipped card because this is a LuxuryCon commercial rule, not
engineering arithmetic. Allowed values:

- `parent` — the element joined onto owns the seam;
- `child` — the joined-on child owns it;
- `stronger_rate` — the higher seam rate owns it, but only when both rates
  have the same currency/unit; ties go to parent and say so.

Null or incomparable inputs produce one `missing_rate` line naming the
exact path and bill NEITHER side. Same-material joints always use that
material's seam rate without consulting the cross-material rule. The gate
pins the disproof: a 3 m joint at 300 + 100 ETB/m would be 1,200 ETB if both
sides were charged; parent ownership correctly bills 300 ETB once.

**Decision 4 — confirmed intake budget precedence and export boundary.** A
confirmed intake's `budget.amount_max` + currency binds automatically when
the design's persisted request carries its `intake_id`. A draft never
binds. An explicit BOM query parameter overrides the intake and both paths
print their source/detail. An incomplete BOM returns `not_performed`, never
PASS. A completed BOM over the confirmed ceiling raises HTTP 422 at the
export/package route BEFORE a JobRow, geometry rebuild, export file,
ExportRow or package is written. The sealed BOM carries the budget result.
This closes D-19; `test_confirmed_over_budget_design_writes_no_export_or_package`
proves the no-write boundary with a real persisted design and arbitrary
in-memory test rates.

**Rate-card truth.** `costing_version` is `2026-09-v3`. The required-null
census is **47**, not the queued 39 or planned 46: five materials × seven
required fields = 35, plus 12 shared/install/commercial/FX entries including
the new owner rule. Conditional machine/mould/crane nulls are not counted
when genuinely not applicable. The exact list and B-4 first-party pricing
worksheet ship in `docs/operator/12_rate_card_checklist.md`; no rate or
provider price is invented. With the real card blank, no client-ready total
exists (B-3 remains release-blocking).

**API/report/package surfaces.** Mixed-material `/api/costing/bom/{id}` now
returns HTTP 200, `drivers.materials`, typed element/joint evidence and
element-prefixed lines; the retired 409 contract in the permanent Phase 6C2
gate is replaced. Text output groups each element/material, then JOINTS,
then `INSTALL (shared — once for the whole assembly)`. The package seals the
same BOM; DesignDNA's read-only costing path remains non-enforcing so it can
record an honest unavailable reason rather than throwing a workflow error.

**Gates/tests.** New roster script 32 `gate_pr6_auto.py`: 10 sections / 43
checks, real kernel + API on a throwaway DB, real rate card/DB/exports
fingerprinted, $0, no provider. `gate_pr6_visual.md` closes D-20 but remains
operator-pending. New `tests/test_costing_per_element.py`: 24 focused tests;
export-boundary regression in `tests/test_export_boundary.py`. Focused
evidence before final chain: 115 costing/mass/transport tests PASS; 95
assembly/API/segmentation tests PASS; 76 PR-6 + export-boundary tests PASS;
affected permanent gates PASS on image `e5e5b4ecfa22`: PR-6 43/43, costing,
Phase 6C2, PR-4, PR-5, LF-103A, Phase 9A and scope audit.

**Definitive chain (2026-09-28/29), pinned image `e5e5b4ecfa22`, identical at
roster start and end, every command at $0 offline with no provider call and no
AI-written code executed:** full in-container roster **29/29 gates PASS, 0
failures**, run one gate at a time on the running stack (FF-A3 ordered before
FF-A2 because D-26b records that `gate_ffa3` §9 can fail on a 60 s health/WAL
wait immediately after `gate_ffa2`'s 334 s run — a fixed duration guarding a
condition; hazard recorded, not fixed); host modes **PR-3 `--static` PASS,
PR-3 `--live` PASS (loopback + LAN), `gate_scope_audit_auto` PASS,
`gate_pr25_discovery_auto --host-drift` 66/66 PASS,
`gate_phase14_auto --frontend-only` PASS**; full pytest suite **860 passed, 4
warnings in 1589.18 s (0:26:29), exit 0 with `geo-worker` UP** and **860
passed in 1642.17 s (0:27:22) with `geo-worker` REMOVED** (that run's exit
code was not captured — see the PR-6 section of `PRODUCTION_V1_REPORT.md`). The `geo-worker`-UP run is deliberately NOT
labelled the project's "worker-UP" state: that state includes the render
worker, whose (large) Blender image has not been built on this machine, so
`gate_phase9b_auto.py` is **NOT RUN** and must never be recorded as PASS.
Verbatim evidence, the retired-409 contract story and the rate-card census:
the PR-6 section of `PRODUCTION_V1_REPORT.md`.

**Status / not claimed.** BUILT + AUTO-GATED, visual PENDING — PR-6 is not
closed until the operator walks `gate_pr6_visual.md`. No client-ready quote
is claimed while B-3's 47 entries are null. No frontend costing screen is
claimed (D-23 remains for PR-7B/B-10). `gate_phase9b_auto.py` is not part of
this slice and remains **NOT RUN** on this machine: the render-worker
(Blender) image has not been built here — a large download deliberately
deferred pending the operator's decision recorded under B-12 — and an unrun
gate is never reported as PASS. B-12 itself is a separate item: this
machine's `data/` directory is still empty.
