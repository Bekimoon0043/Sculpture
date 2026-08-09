# 04 — The first live Council session (Phase 3, step 4)

This runs the full six-agent AI Council on a real brief: real API calls,
real money. **Pre-approved spend: ~$1–2.50.** The hard caps in
`config/budget.yaml` ($5 per session / $25 per day) are enforced BEFORE
every call — the session cannot overspend.

Estimated cost: **≈$1.15** (see PHASE_3_PLAN.md §7), possibly lower — cache
hits now bill at the cheaper class (ADR-022, pricing 2026-08-v3).

## 1. Start the platform

```cmd
docker compose up --build -d
```

(The `--build` picks up the new Council API code.)

## 2. Run one live session

Pick a real but small brief, then:

**cmd.exe** (Command Prompt):

```cmd
curl -X POST http://localhost:8000/api/council/sessions -H "Content-Type: application/json" -d "{\"brief_text\": \"A three-tier basalt fountain for a hotel courtyard in Addis Ababa, 2.6 m basin.\"}"
```

**PowerShell** (where `curl` is an alias for Invoke-WebRequest and the cmd
quoting breaks — use Invoke-RestMethod):

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/council/sessions -ContentType "application/json" -Body '{"brief_text": "A three-tier basalt fountain for a hotel courtyard in Addis Ababa, 2.6 m basin."}'
```

The request stays open for the whole session — **several minutes is
normal** (about 15 provider calls, one after another). When it returns you
get:

```json
{"session_id": "....", "status": "completed"}
```

If it returns HTTP 402 instead, the budget cap stopped the session — the
partial transcript is still saved; send me the `detail` text.

**Slow connection?** Timeouts and connection drops are retried
automatically (3 attempts per call, waits of 10 s then 30 s), and a failed
non-critical agent now DEGRADES the session instead of killing it — a
completed-but-degraded session says so in the UI. To tune: set
`LUXURYFORM_PROVIDER_TIMEOUT_S` / `LUXURYFORM_PROVIDER_MAX_ATTEMPTS` /
`LUXURYFORM_PROVIDER_BACKOFF_BASE_S` in `.env` (see `.env.example`).

## 3. Read the measured cost

**cmd.exe:**

```cmd
curl http://localhost:8000/api/council/sessions/PASTE-SESSION-ID-HERE
```

**PowerShell:**

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/council/sessions/PASTE-SESSION-ID-HERE | ConvertTo-Json -Depth 10
```

Look at `cost_rollup`: `total_cost_usd`, `by_role`, `by_provider`,
`cache_savings_usd`. Or open the UI: http://localhost:5173 → **AI Council**
tab → click the session. Every call card shows provider, tokens (including
cache split), cost and latency.

## 4. Send me the numbers

Copy the whole `cost_rollup` block (or the full JSON) into your reply. I
will report measured-vs-$1.15 per role × provider and recommend any role
reassignment from the data.

## 5. Optional: keep the session as a $0 regression fixture

```cmd
docker compose exec backend python scripts/capture_council_fixture.py PASTE-SESSION-ID-HERE
```

This writes `tests/fixtures/council_session_live_<id>.json`. **Review it
before committing** — it contains the real brief and the models' full
replies.
