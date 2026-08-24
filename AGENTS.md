# AGENTS.md — LuxuryForm Studio

> This file is for AI coding agents. Read it at the start of every session, then read `CLAUDE.md`, `DECISIONS.md`, and `LIMITATIONS.md`.

## Project overview

LuxuryForm Studio is a local-first design platform for LuxuryCon (Addis Ababa). It turns a client brief for a sculpture or fountain into fabrication-ready geometry, engineering validation, costed BOMs, renders and exports. The core architectural truth is that **LLMs do not generate geometry** — they write a design program and a `Design Spec`; a deterministic CAD kernel (OpenCASCADE via build123d) executes that program.

Current build status (from `CLAUDE.md`, 2026-08-24):

- **CLOSED:** Phases 1 (provider/budget/audit), 2 (geometry kernel + viewport), 3 (AI Council), 4 (fabrication loop), 6 slice A1 (assembly core), 8/8b (validation gates), 9A (export package), 11 (DesignDNA), 12 (brief intake), 13 slice A (jobs/costs/backup).
- **Auto-gated 2026-08-24:** Phase 9B (Blender render worker, ADR-043) and Phase 5 (vision critique loop). Twelve auto gates now pass, all $0 and offline.
- **Awaiting operator visual gates:** `gate_phase8_visual.md`, `gate_phase9a_visual.md`, `gate_phase11_13a_visual.md`, `gate_phase9b_visual.md`, `gate_phase5_visual.md`.
- **Not started / open:** Phase 6 slices B–D, Phase 10 (vision critique of renders — unblocked now that 9B exists), Phase 13 slices B+.
- Nothing in the project still needs a large download; the Blender tarball was the last one.

Authoritative docs:

- `CLAUDE.md` — non-negotiable engineering rules and operator constraints.
- `DECISIONS.md` — architecture decision record (ADR) and phase reports.
- `LIMITATIONS.md` — current truth table of what is and is not built.
- `PHASE_1_REPORT.md` … `PHASE_9A_REPORT.md`, `PHASE_11_12_13A_REPORT.md` — gate evidence.
- `PHASE_7_COMPLETION_PLAN.md` … `PHASE_13_RECOVERY_HARDENING_PLAN.md` — forward plans.
- `docs/operator/` — plain-language operator guides.

## Technology stack

- **Language/runtime:** Python 3.11 (required `>=3.11,<3.12`), TypeScript/TSX, Node 20.
- **Backend framework:** FastAPI 0.115.6, Uvicorn 0.32.1.
- **Data:** SQLite in WAL mode (`data/luxuryform.db`), SQLAlchemy 2.0.36; startup applies `backend/app/db/schema.sql` plus additive patches idempotently.
- **Validation/config:** Pydantic 2.10.4, pydantic-settings 2.7.0, PyYAML 6.0.2, jsonschema 4.23.0.
- **AI providers:** Anthropic SDK 0.42.0, OpenAI SDK 1.59.3, Kimi via Moonshot OpenAI-compatible endpoint.
- **Geometry kernel:** build123d 0.11.1, cadquery-ocp-novtk 7.9.3.1.1, trimesh 5.0.0, numpy 2.4.6, scipy 1.17.1, scikit-learn 1.9.0, Pillow 11.0.0.
- **Frontend:** React 19.2.8, Vite 8.2.0, three.js 0.185.1.
- **Build/packaging:** setuptools 80.9.0, Docker Compose, `pyproject.toml` (the importable package is `app` and lives under `backend/`).
- **Test runner:** pytest 8.3.4; configured in `pyproject.toml` with `testpaths = ["tests"]`.

## Repository layout

- `backend/app/` — importable package `app`.
  - `api/` — FastAPI routers (`routes_*.py`); mounted in `main.py` under `/api`.
  - `core/` — configuration loading (`config.py`), budget enforcement, seeds, units.
  - `db/` — SQLite database access, schema, models.
  - `ai/` — provider abstraction and call logging; every provider call is logged.
  - `council/` — Phase 3 council orchestrator, prompts, dispatch, replay, and Phase 4 fabrication loop.
  - `geometry/` — Phase 2 kernel: primitives, assembly, exporters, validation gates, and the Phase 4 sandbox (`worker.py`, `ast_gate.py`, `job_runner.py`).
  - `costing/` — cost estimation, BOM and rate-card logic.
  - `dna/` — DesignDNA precedent store.
  - `intake/` — brief intake parser/models.
- `config/` — YAML config: `council.yaml`, `pricing.yaml`, `budget.yaml`, `materials.yaml`, `costing.yaml`, `gate_profiles.yaml`. Loaded and validated at startup.
- `schemas/design_spec_v1.json` — AI-to-CAD contract, served at `GET /api/schema/design-spec`.
- `scripts/` — phase gates (`gate_phase*.py`), helper scripts, and one-off builders. Entry points are normally run inside the backend container.
- `tests/` — pytest suite; hermetic (no network, no real API keys).
- `frontend/` — React + Vite + three.js viewport.
- `data/` — SQLite DB, exported artifacts, `geo_scratch/` shared with the sandbox worker. Gitignored.
- `docker/` — render worker assets.
- `hub/` — status panel files for the AI-Team-Hub.
- `debs/` — optional local GL `.deb` files for the hybrid Docker build. Gitignored.

There is **no root `package.json`**; the Node manifest is `frontend/package.json`.

## Build and run commands

Primary path is Docker Compose on Windows:

```bat
copy .env.example .env
REM paste your three API keys into .env

docker compose up --build -d
```

- Backend API: http://localhost:8000/api/health
- Viewport UI: http://localhost:5173
- Audit logs: http://localhost:8000/api/logs/calls and `/api/logs/budget`

Useful operator commands:

```bat
docker compose logs -f backend
docker compose down
docker compose up -d
```

Backend Dockerfile variants (set in shell before building):

```bat
set BACKEND_DOCKERFILE=Dockerfile.hybrid
docker compose build backend
docker compose up -d backend
```

- `Dockerfile.hybrid` — recommended Plan B; uses a pinned donor image plus local `./debs/` for the GL libraries.
- `Dockerfile.donor` — fallback; copies the 9 system libraries from any donor image.
- `Dockerfile` — default; downloads the 9 pinned Debian debs from a dated snapshot.

See `docs/operator/01_starting_the_platform.md` and `docs/operator/02_docker_path_setup.md`.

Frontend local build (no root `package.json`; use the `frontend/` directory):

```bat
cd frontend
npm ci
npm run build
npm run preview
```

Backend editable install outside Docker (requires Python 3.11):

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -e .
pytest
```

## Test commands

Inside Docker (recommended, matches the production image):

```bat
docker compose exec backend pytest
docker compose exec backend pytest tests/test_docker_pins.py -v
```

Outside Docker (Python 3.11, editable install):

```bat
pytest
```

The suite is hermetic: `tests/conftest.py` scrubs API keys and `LUXURYFORM_DB`, uses a temp DB, and loads the real `config/*.yaml`. It does not hit the network. Hand-constructed SDK transports are injected only in tests; production always builds real clients.

Phase auto gates (run inside the backend container; offline / $0 except Phase 1):

```bat
docker compose exec backend python scripts/gate_phase1.py
docker compose exec backend python scripts/gate_phase2_auto.py
docker compose exec backend python scripts/gate_phase3_auto.py
docker compose exec backend python scripts/gate_phase4_auto.py
docker compose exec backend python scripts/gate_phase6a1_auto.py
docker compose exec backend python scripts/gate_costing_auto.py
docker compose exec backend python scripts/gate_phase8_auto.py
docker compose exec backend python scripts/gate_phase8b_auto.py
docker compose exec backend python scripts/gate_phase9a_auto.py
docker compose exec backend python scripts/gate_phase11_auto.py
docker compose exec backend python scripts/gate_phase13a_auto.py
```

Each gate exits `0` on PASS and `1` on FAIL, prints a numbered transcript, and is idempotent/safe to re-run.

## Code style and conventions

Adopted from `CLAUDE.md`:

1. **No stubs, mocks, placeholders, or `TODO` in committed code.** If a module exists, it works and has a test. Tests may use hand-constructed mocks, but production never simulates an API response.
2. **No fabricated capability.** If something cannot be done, add it to `LIMITATIONS.md` and build the real alternative.
3. **Every phase ends at a hard acceptance gate** — an auto gate script plus a visual gate markdown.
4. **Vertical slice first.** Depth before breadth.
5. **Determinism from the Design Spec onward.** Identical spec + seed + pinned image → byte-identical STEP. Brief→Spec is non-deterministic; gates do not test brief-level reproducibility.
6. **Metric, SI, explicit units.** A unitless number is a bug.
7. **Local-first.** No project data leaves the machine except logged AI API calls.
8. **Every AI call logged** — model, prompt, response, tokens, latency, cost, pricing version — to `ai_calls` / `council_calls`.
9. **ADR-009:** no endpoint, model string, SDK shape or price from training-data recall; fetch live provider docs and record the date.
10. **ADR-005:** AI-written code executes ONLY in the `geo-worker` sandbox — separate container, non-root, no network, read-only filesystem except `/scratch`, CPU and memory limits, hard timeout. Never in tests, never in a gate, never in the backend container.
11. **Parameter ranges derive from material and engineering arithmetic**, per material, with reasoning recorded. Not from visual intuition.
12. **Report failures honestly and immediately.** A truthful failure report beats a fake pass.

Additional implementation norms:

- Config loading fails loudly on malformed YAML or invalid values (`app.core.config.ConfigError`).
- Use `from __future__ import annotations` at the top of Python files.
- Use `pathlib.Path`; repo root is derived in `backend/app/core/config.py`.
- Make units explicit in variable names (`_mm`, `_kg`, `_m_s`, `_kpa`).

## Security considerations

- **API keys:** stored only in `.env` (gitignored). Key material is never logged. `app.core.config.provider_keys_status()` returns only configured/not-configured status plus the env var name.
- **Sandboxed code execution:** `geo-worker` runs AI-generated CAD programs. It shares the backend image but runs as `user 1000:1000`, `network_mode: "none"`, `read_only: true`, tmpfs `/tmp`, CPU 1.0, mem 2 GB, with a hard timeout per job. It watches `/scratch` (`./data/geo_scratch` on the host) for queued jobs.
- **Spend caps:** `config/budget.yaml` enforces `$5` session and `$25` day ceilings before every provider call. On breach the system halts, persists its state, and reports.
- **Audit trail:** every provider call is persisted in SQLite with full prompt/response/token/cost metadata. Council sessions and fabrication attempts are fully traceable.
- **Local-first data:** the SQLite DB and exports live in `./data/`. No external persistence is used.
- **AI-written code safety:** `ast_gate.py` rejects illegal AST constructs before a job is queued; the worker executes only whitelisted CAD code. Do not bypass the worker to run generated geometry code in the backend or tests.
- **Dependency integrity:** Python packages and Debian debs are pinned by exact version and sha256; `tests/test_docker_pins.py` enforces that Dockerfile pins match `pyproject.toml` and that the GL layer stays minimal.

## Deployment process

- The platform is intended to run on the operator's Windows machine via Docker Desktop/WSL2.
- `docker-compose.yml` defines three services: `backend` (port 8000), `geo-worker` (no ports, sandbox), and `frontend` (port 5173).
- `backend` and `geo-worker` share `./data/geo_scratch` mounted at `/scratch`; the backend writes job manifests and the worker reads them.
- `backend` mounts `./data` to `/app/data` for the database and exports.
- Database path is controlled by `LUXURYFORM_DB` (default `./data/luxuryform.db`); in Docker it is `/app/data/luxuryform.db`.
- `VITE_API_TARGET` inside Docker points to `http://backend:8000`; on a bare host it falls back to `http://localhost:8000` in `frontend/vite.config.ts`.

## Working method for agents

Before writing new code:

1. Read `CLAUDE.md`, `DECISIONS.md`, `LIMITATIONS.md`, and the relevant `PHASE_*_REPORT.md` / `PHASE_*_PLAN.md`.
2. Propose the plan (structure, schema, ordering, risks) and wait for operator approval.
3. Commit per gate with a clear message; keep docs and phase reports current in the same commit.
4. After any `backend/` change, tell the operator to rebuild with `docker compose up --build -d`.
5. Run the relevant auto gate(s) and, if applicable, update the visual gate markdown.
6. Never claim a gate passes without showing the command and its real output.
