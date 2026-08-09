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
