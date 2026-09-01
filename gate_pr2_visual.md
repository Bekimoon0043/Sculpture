# gate_pr2_visual.md — PR-2, the operator's eye gate

**Cost: $0.** Nothing here spends money. No AI call is made.

**Before you start**: the rebuild for this slice already happened on
2026-08-28 and produced the recorded final image `09ff920ccbbb` — it is
the current `luxuryform-backend:latest`. Do **not** rebuild now: docs
changed after that build and the backend image bakes in the whole repo,
so `--build` would mint a new image id and break the recorded evidence
identity. Just start the backend:

```powershell
docker compose up -d backend
```

---

## What changed, in one sentence

Until now, two things spending money at the same moment could each check
the books, both see room, and together sail past your caps; now nothing
may call a provider without first writing an IOU into the database under
a lock only one writer can hold — so the $25/day and the $5-per-run
ceilings cannot be jointly exceeded, a crash can never lose money
invisibly, and anything uncertain stays counted against the cap until
**you** clear it by hand.

## 1. The budget page shows the new machinery

```powershell
Invoke-RestMethod http://localhost:8000/api/logs/budget | ConvertTo-Json -Depth 5
```

**Check by eye:**

- [ ] `caps` says **`run_cap_usd: 5`** (the $5 is per logical run now —
      one Council run, one fabrication run with all its repairs, one
      critique run with all its rounds), and `day_cap_usd: 25`.
- [ ] The reply has **`open_holds`** and **`active_safety_locks`**
      sections (normally both empty — money currently held mid-call, and
      provider locks that refuse spending until you resolve them).
- [ ] The reply also has a **`reconciled_unmatched_spend`** section
      (normally empty — orphan spend you reconciled by hand from a
      provider console; it counts against the caps but has no call row).

## 2. The config file says what it means

Open `config\budget.yaml` in Notepad:

- [ ] The first cap is named **`run_cap_usd`** and its comment says "per
      LOGICAL paid run" — the old name `session_cap_usd` is gone.
- [ ] The values are **`run_cap_usd: 5.00`** and **`day_cap_usd: 25.00`**
      — the same ceilings the sign-off below asks you to confirm.

## 3. Run the auto gate and read its verdict

```powershell
docker compose exec backend python scripts/gate_pr2_auto.py
```

- [ ] It ends **PASS**, and section [2] shows *exactly one of two
      simultaneous reservers passed*, and section [3] shows two separate
      processes together landing exactly $0.005 of holds under a $0.005
      cap — never a cent over.
- [ ] The other sections say what they prove as they pass: [1] every
      reservation bound is exact to the micro-USD; [4] a failed retry
      attempt stays counted at its **full** bound (fail closed) and the
      safety lock refuses the next matching dispatch; [5] a dead hold
      recovers as `uncertain`, resolving it demands a reason, and a
      nonzero reconciliation keeps counting against the day cap; [7] the
      budget page and the Operations total carry reconciled orphan
      spend explicitly.

## 4. The one consequence you should decide on — kimi's reservation size

No provider documents its message overhead, so every reservation uses the
mandated conservative fallback: the model's **full context window** priced
at its highest input rate, plus the requested output. The real bounds are:

| provider / model | held per call (at 8,192 output tokens) |
|---|---|
| anthropic / claude-sonnet-4-5 | **$0.872880** |
| openai / gpt-4o | **$0.401920** |
| kimi / kimi-k3 | **$3.268608** |

The hold is released to the real cost (usually cents) the moment each
call finishes — but **while a kimi call is in flight it needs $3.27 of
free headroom**, so a kimi call late in a $5 run will be refused even
though its real cost would be cents. That is the fail-closed design
working as ordered, not a defect.

- [ ] I understand the kimi consequence. If it ever blocks real work I
      will raise `run_cap_usd` in `config\budget.yaml` deliberately
      (or say the word and a first-party-documented tighter bound can be
      revisited) — nothing will be loosened silently.

## 5. When something needs your hand

If a call dies uncertainly, a price lookup fails after a billed call, or
a bound is ever exceeded, spending locks itself and this command shows
what is waiting for you (it never spends):

```powershell
docker compose exec backend python scripts/spend_admin.py list
```

- [ ] Run it now — it should report `(none)` for locks, halted scopes and
      uncertain holds.

---

## Sign-off

```
Date: 2026-09-01
Started on the recorded final image (no rebuild):      yes
Step 1 — caps + holds/locks + reconciled on the page:  yes
Step 2 — budget.yaml renamed and commented:            yes
Step 3 — auto gate PASS with both race proofs:         yes
Step 4 — kimi $3.27-per-call holding cost understood:  yes
Step 5 — spend_admin list shows (none) everywhere:     yes

Are $5/run and $25/day still the ceilings you want? YES — retained.
(They live in config\budget.yaml; changing them is one line + restart.)

Notes: Operator sign-off, verbatim: "Operations ledgers reconcile. No
provider calls occurred during the unexplained 2026-08-31 container
window. The latest legitimate paid activity is my 2026-08-28
Council/fabrication demonstration. Budget API exposes run_cap_usd,
day_cap_usd, open_holds, active_safety_locks and
reconciled_unmatched_spend. open_holds, active_safety_locks and
reconciled_unmatched_spend are empty. config/budget.yaml uses
run_cap_usd; session_cap_usd is absent. gate_pr2_auto.py PASS.
spend_admin.py list shows no unresolved entries. I approve retaining $5
per logical run and $25 per UTC day. I understand that an uncertain
Kimi attempt can prevent an automatic retry within the same $5 run."
The two accidental live-data designs (76595edb…, 313e5d20…) are
preserved by explicit ruling; their cleanup is a separate operator
decision, not part of PR-2.
```
