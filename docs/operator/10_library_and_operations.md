# Library and Operations

Phase 11 (DesignDNA) and Phase 13 slice A (jobs, spend, backup).

---

# Library — the house memory

Every design LuxuryCon accepts becomes a **precedent**: a searchable record
of what was built, how it validated, what it cost, and why you accepted it.

## Accepting a design

**Library** tab → *Accept the current design*. You supply two things:

- **Accepted by** — who signed off
- **Why is this design good?** — one sentence

That sentence is not decoration. Future Council sessions read it. A precedent
that cannot say why it was good is not knowledge, so both fields are
required.

### You must export first

A precedent is the accepted **deliverable**, not a half-finished shape. So
the export package must exist before you can accept, and the platform
enforces it — try to accept early and it tells you to build the package.

That also gives every precedent a real identity: the package **content
digest**, which covers geometry + spec + validation + BOM together. Two
designs with identical STEP but different materials are correctly two
different precedents.

The same deliverable cannot be accepted twice. Accept is idempotent per
package, not per click.

### A failing design cannot be accepted

If validation rolls up to FAIL, acceptance is refused. Memory should not
teach the Council from work that did not pass.

## Searching

Fill any combination of material, water, and note text, then **Search**.

Two things make this trustworthy:

**It is an AND filter, not a fuzzy score.** Every criterion you set must
match. Nothing surfaces "because it seemed similar".

**Every hit says why it matched**, field by field:

```
material basalt_slab · water design · height 2.4 m within 1.20–3.60 m of requested 2.4 m
```

There are deliberately no embeddings here. You must be able to see why a
precedent surfaced, and debug it when it retrieves the wrong thing. An
unexplainable similarity score cannot be argued with.

## How precedents reach the Council

When you run a Council session with precedents enabled, matching precedents
are injected as a **delimited, quarantined block** that says plainly:

> These are designs LuxuryCon previously accepted and delivered. Their
> numbers describe PRIOR projects, NOT requirements for this brief. Never
> copy a dimension from a precedent over one stated in the brief.

That framing is load-bearing. Without it the Council copies a precedent's
2.4 m basin into a brief that asked for 1.2 m. At most three precedents are
injected per session, so memory never drowns the actual brief.

## Archive vs delete — different operations

**Archive** hides a precedent from search but keeps the record. Old sessions
that cite it stay coherent. Use this when a design is superseded.

**Delete** wipes the content but leaves a **tombstone** carrying the id. A
session that cited it reports "precedent deleted" instead of breaking. It
cannot be undone, so the UI asks first.

---

# Operations — jobs, spend, backup

**Operations** tab.

## Spend, and why it is reconciled

Every provider call is logged twice, by different code at different moments:
once **per call** (`ai_calls`) and once as a **session running total**.

The reconciliation card compares them.

- **Ledgers reconcile** — the two books agree to the cent. That agreement is
  evidence the accounting is intact.
- **Ledger mismatch** — they disagree, and the card names the sessions.

A dashboard that adds up its own numbers proves nothing. One that reconciles
two independent records catches a lost or double-counted call. A mismatch is
also shown in the status bar at the bottom of every screen.

Failed calls get their own line. A provider that billed a failed attempt
still cost money, and a flaky connection must never read as work done.

## Jobs

Every export runs as a job with a recorded checkpoint. Failures carry a
**class**, because the class decides your next action:

| class | what to do |
| --- | --- |
| **transient** | retryable — a timeout or dropped connection |
| **resource** | free disk or memory, then retry |
| **input** | the request is invalid — fix it; retrying will not help |
| **defect** | our bug — report it, do not retry |

## Backup and restore

Backs up the database and every design artifact.

```powershell
docker compose exec backend python scripts/backup_restore.py backup --out data/backups/luxuryform-backup.zip
```

The database is copied with SQLite's **online backup** — safe to run while
the backend is working. A plain file copy of a live database snapshots a torn
write and corrupts silently.

To restore into a fresh folder:

```powershell
docker compose exec backend python scripts/backup_restore.py restore --archive data/backups/luxuryform-backup.zip --into data/restored
```

Restore **refuses to merge over existing data** — it wants an empty target,
so a restore can never half-overwrite your live store.

### The restore proves itself

Restore does not just unpack. It:

1. compares every table's row count against the manifest written at backup time
2. re-runs the **LUXEXCHANGE package's own shipped verifier** against the
   newest restored package

```
RESTORE VERIFICATION PASSED
  package  : artifacts/exports/<id>/luxexchange_v1.zip re-verified OK
  tables checked: 10
```

"The files are there" is not a restore proof. A package that re-verifies is.

Note (LF-103A, 2026-09-01): a restored package sealed before 2026-09-01
still re-verifies here — the verifier checks integrity, not class — but it
will refuse to DOWNLOAD from the API as `LEGACY_UNCLASSIFIED` until you
re-export the design once. That refusal is deliberate: an old zip carries
no `package_class`, so the platform will not serve it as if it were a
clean fabrication package.
If the archive is corrupt you get a named finding, not a stack trace.

Check an existing restore at any time:

```powershell
docker compose exec backend python scripts/backup_restore.py verify --dir data/restored
```

## Running the gates

```powershell
docker compose exec backend python scripts/gate_phase11_auto.py
docker compose exec backend python scripts/gate_phase13a_auto.py
docker compose exec backend python scripts/gate_phase8b_auto.py
```

All three run at $0 with no internet.
