---
description: Diagnose a failure from the real error and logs — never from recall
argument-hint: [paste the verbatim error]
---

Something broke:

$ARGUMENTS

Diagnose it from the actual error and the actual logs. **Do not guess and do not
write a fix from recall.**

Work in this order:

1. **Restate the error precisely** — which command, which file, which line, and
   what the real values were versus the expected ones. If any of that is missing
   from what was pasted, ask for it or go and get it before theorising.
2. **Read the logs**, do not infer them:
   ```
   docker compose logs backend --tail 200
   docker compose logs frontend --tail 100
   docker compose ps
   ```
   For a sandbox failure, also read the job's scratch directory under
   `data/geo_scratch/` — the generated program and its result are both there.
   For an AI-call failure, read the `ai_calls` table
   (`http://localhost:8000/api/logs/calls`) — the full prompt and full response
   are logged, so the actual exchange is available, not a reconstruction.
3. **ADR-009 applies to every diagnosis.** If a third-party endpoint, model
   string, SDK shape, parameter name or price is anywhere near the failure,
   fetch the live provider or library docs and record the fetch date. Three
   multi-hour failures in this project came from trusting recall here.
4. **Separate what you have proven from what you suspect.** Say which is which,
   in those words. A confident wrong diagnosis costs more than an honest
   "I do not know yet, here is what I would run to find out".
5. **Show the operator what you found before you change anything.** Then propose
   the smallest fix that addresses the actual cause, and say what it does not
   fix.

If it is an environment failure rather than a code failure — a download that
died, a reset connection, a Docker layer that will not build — say so plainly.
The operator's connection runs at roughly 320 kB/s and drops; anything that
downloads must retry, resume, and be cached in its own Docker layer. That has
cost more time on this project than any code defect.
