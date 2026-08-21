# PHASE_13_RECOVERY_HARDENING_PLAN.md - Jobs, Recovery, And Operator Trust (2026-08-21)

Phase 13 makes the system dependable during long local runs.

## Current State

- Provider calls and fabrication attempts are logged.
- Long render, critique, export, and acceptance jobs do not have a complete
  resumable runner.
- Operator recovery docs are incomplete for later phases.

## Build Scope

- Resumable job runner with checkpointed steps:
  - intake.
  - Council.
  - fabrication.
  - validation.
  - render.
  - vision critique.
  - export.
  - DesignDNA acceptance.
- Idempotent job restart by job id.
- Kill-and-resume gate scripts.
- Local backup and restore command for database and artifacts.
- Cost dashboard covering Council, fabrication, render, critique, export, and
  retries.
- Status UI for current job, last completed checkpoint, last error, and next
  action.
- Operator docs for common failure recovery.

## Gate

Phase 13 closes when:

- Killing the backend during a long job does not lose accepted artifacts.
- The job can resume from the last completed checkpoint.
- Every paid provider call remains auditable after restart.
- Backup and restore are tested on a fresh local checkout.
- The operator can see what failed and what to do next.

---

## Design corrections — review 2026-08-21

### R1 — Do not build the job model here; harden the one Phase 9 ships

`JobRow` already exists (`backend/app/db/models.py`) with
`job_type / status / state_json / halt_reason`. Phase 9A.3 makes it a real
consumer for export jobs, and Phase 9B adds render jobs.

If Phase 13 designs a job runner from scratch, it retrofits two live
subsystems. Instead: **Phase 9A.3 sets the contract, Phase 13 hardens it.**
The instruction to whoever builds 9A.3 is that its job shape is the one every
later phase inherits, so it must carry checkpoints from the first commit even
though export barely needs them.

`job_runner.py` is *not* that runner — it is the ADR-005 sandbox executor for
AI-written programs and must stay single-purpose. Name the new one differently
to prevent the confusion.

### R2 — Checkpoint at the artifact boundary, not on a timer

A checkpoint is only meaningful where a durable artifact exists: STEP written,
GLB written, validation persisted, each render PNG written, each critique round
persisted, each export format written, package sealed. Resume means "skip the
steps whose artifact exists and whose hash matches", which is a design the
system can already support because every artifact is hashed.

That also gives idempotent restart for free: re-running a job with all
artifacts present is a no-op that returns the same result.

### R3 — Resumption must distinguish four failure classes

Grouping every failure as "error" leaves the operator with no next action:

| class | example | correct action |
| --- | --- | --- |
| transient | provider timeout, connection reset | auto-retry with backoff |
| resource | Docker OOM, disk full | stop, tell the operator what to free |
| input | invalid spec, unknown primitive | stop, name the field |
| defect | exception in our own code | stop, capture traceback, do not retry |

Only transient failures retry. Auto-retrying a defect burns money and hides the
bug; auto-retrying an input error burns money and never succeeds. The status
screen names the class and the next action, which is what "the operator can see
what to do next" has to mean.

### R4 — Backup must be verifiable, and restore must be tested against a real package

Backup covers `luxuryform.db` plus `data/designs` and `data/exports`. Restore
is proven by running `verify_luxexchange.py` (Phase 9A.3) from a restored
package on a fresh checkout — that verifier already exists for this purpose, so
Phase 13 gets a real restore proof instead of "the files are there".

The database backup must be a `sqlite3` online backup, not a file copy of a
database with an open connection.

### R5 — The cost dashboard must reconcile, not merely display

Sum `ai_calls` by phase and session and reconcile against `budget_events`. A
dashboard that adds up its own numbers proves nothing; one that reconciles two
independent records catches a lost or double-counted call. Rule 8 asks for
auditable, and auditable means two records that must agree.

Include the retry cost as its own line — R3's transient retries spend real
money, and an operator who cannot see retry spend cannot tell a flaky
connection from a runaway loop.

### R6 — Kill-and-resume must be tested per phase, not once

One kill test proves one code path. The gate script kills at each checkpoint
boundary in turn — mid-fabrication, mid-render, mid-critique, mid-export,
mid-seal — and asserts resume produces an identical final `content_digest`.
That last assertion is the strong one: resume must be byte-equivalent to an
uninterrupted run, which is exactly the guarantee Phase 9A.2's reproducible
package makes checkable.

### Revised gate additions

- Killing at each checkpoint boundary and resuming yields the same
  `content_digest` as an uninterrupted run.
- A simulated transient failure retries; a simulated defect does not, and
  reports its traceback.
- Restoring from backup on a fresh checkout passes `verify_luxexchange.py`.
- The cost dashboard reconciles `ai_calls` against `budget_events` and shows a
  separate retry line.
- The status screen names the failure class and one concrete next action.
