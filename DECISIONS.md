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
