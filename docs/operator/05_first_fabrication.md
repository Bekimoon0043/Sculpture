# 05 — Your first live fabrication (Phase 4)

Prerequisite: a completed council session (you have one — `32e1c68f`).
Every step is copy-paste. cmd.exe AND PowerShell variants given (curl is an
alias for Invoke-WebRequest in PowerShell — the syntax differs).

## 1. Rebuild and start the stack WITH the sandbox worker

The geo-worker is a new container. It shares the backend image, so the
build is one command:

```cmd
docker compose up --build -d
```

```powershell
docker compose up --build -d
```

Check the worker is up:

```cmd
docker compose ps geo-worker
```

You want `running`. Its logs should say `geo-worker watching /scratch`.

On startup the backend patches your existing database (adds the
`generated_programs` table and the `corrected` column — automatic, your
history is preserved).

## 2. Run the $0 half of the Phase 4 gate

```cmd
docker compose exec backend python scripts/gate_phase4_auto.py
```

You want `VERDICT: PASS` at the end. This spends nothing — it proves the
loop with scripted stand-ins.

## 3. Fabricate for real (real API calls, real money)

This fabricates the Arbiter's FIRST-RANKED spec from your live session.
One attempt is one `geometrist_code` call; the repair bound is 3 attempts.
Typical cost: cents, hard-capped by the same $5 session cap.

cmd.exe:

```cmd
curl -s -X POST http://localhost:8000/api/council/sessions/32e1c68f/fabricate -H "Content-Type: application/json" -d "{}"
```

PowerShell:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/council/sessions/32e1c68f/fabricate -Method Post -Body '{}' -ContentType 'application/json' | ConvertTo-Json -Depth 10
```

The request stays open while the loop runs (each sandbox build takes up to
2 minutes; 3 attempts worst case). The response tells you:

- `success: true/false`
- `attempts`: how many rounds it took
- `final_status`: passed | ast_rejected | exec_failed | validation_failed
- `artifacts`: where the STEP and GLB landed
  (`data/fabrications/<session>/<program>/`)
- `validation`: the Phase 2 validation report with REAL numbers

If your line drops mid-call, nothing is lost: every attempt is persisted;
just re-run the command.

To fabricate a DIFFERENT spec from the six, pass its id:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/council/sessions/32e1c68f/fabricate -Method Post -Body '{"spec_id":"<full-spec-id>"}' -ContentType 'application/json'
```

## 4. Then the visual half

Open `docs/operator/gate_phase4_visual.md` and check every box.

## Slow-connection tuning

Same knobs as doc 04: `LUXURYFORM_PROVIDER_TIMEOUT_S` (default 300),
`LUXURYFORM_PROVIDER_MAX_ATTEMPTS` (default 3) in `.env`. A provider
failure during fabrication is a failed ATTEMPT (fed into repair), not a
crash — the loop is ADR-023-compliant.

## What a repair round knows (2026-08-10 fix)

Every repair prompt carries the FULL failure history of all prior
attempts, oldest first, and tells the model that a previously-failed value
must NOT be repeated. Wall thickness is validated against the selected
material's envelope in `config/materials.yaml` (`min_wall_mm` ..
`max_wall_mm` — ADR-027, workshop envelopes you can tune); the prompt the
geometrist sees lists those envelopes next to the parameter ranges.

## What to send back

The fabrication response JSON (paste it). That is the gate evidence:
attempts, statuses, costs, and the validation numbers.
