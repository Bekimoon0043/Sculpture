# PHASE_11_12_13A_REPORT.md — DesignDNA, Brief Intake, Operations

**Auto gates: PASS, 2026-08-22.**
`gate_phase11_auto.py` · `gate_phase8b_auto.py` · `gate_phase13a_auto.py` —
all exit 0, at $0, with no network and no provider keys.
**Visual gate: pending operator** — `gate_phase11_13a_visual.md`.

ADRs: **ADR-038** (precedent identity), **ADR-039** (intake provenance),
**ADR-040** (ledger reconciliation), **ADR-041** (the pipeline is the
interface).

---

## What closed, and the one thing it unblocked

Three phases shipped together because they form one loop: a brief becomes
typed context, the context makes validation real, and the finished
deliverable becomes memory for the next brief.

The most important result is not any of the three. It is that **Phase 8's
open dependency is now closed.**

Phase 8 shipped with its hydraulic gate permanently reporting `needs_input`,
because nothing populated the water context. That was honest but inert — the
gate had never evaluated a fountain. `gate_phase8b_auto.py` now proves the
chain end to end with **no hand-injected context and no profile edit**:

```
[3/4] THE RE-GATE — intake context reaches the gates
  ok  hydraulics reaches a real verdict from the intake  — status warn
  ok  the nozzle bore was derived and judged  — declared 20.0 mm, band [15.45, 25.75]
  ok  freeboard was measured  — 90.0 mm
  ok  ground bearing EVALUATES from the intake's site fact  — 4.84 kPa vs 150.0 allowable
  ok  wind pressure computed from the intake's wind + altitude  — 436.97 Pa
  ok  overturning is COMPUTED; only the engineer's policy factor remains
```

That last line is the honest boundary. Overturning is now *calculated* from
the operator's wind speed and site altitude, and the real safety factor
appears in the message — but the **required** factor stays `needs_input`,
because it is a policy value a structural engineer signs, not a site
measurement. Making it intake-overridable would have let the software sign
an engineering decision. It does not.

---

## Phase 12 — brief intake (ADR-039)

### Every field carries where it came from

A value of `15.0` in a form tells you nothing about whether the operator
chose it, an AI read it from the brief, it is an unexamined default, or it
is simply absent. So every intake field is a `Sourced[T]`: value + source
(`operator | parsed | default | unknown`) + the brief sentence a parsed
value came from.

This is the honesty chain end to end. `unknown` is structurally distinct
from `default`, and it propagates to the gates as `needs_input` rather than
becoming a guessed number that quietly passes.

### The parser fills the form; it never decides

- A field sourced `operator` is **never** overwritten by the machine.
- The parser cannot invent fields outside the schema, cannot coerce a type,
  and is instructed to OMIT anything the brief does not state.
- Every parsed value travels with its quote, so the operator can check the
  parser against the client's own words.

Tested: given both, `merge_parsed` keeps the operator's 2.4 m over the
parser's 9.9 m and reports `{applied: 1, kept_operator: 1, dropped: 0}`.

### Requirements ranked by what they block

Tier 1 blocks geometry, tier 2 blocks a validation gate, tier 3 blocks
costing, tier 4 affects design quality. Tiers 1–2 must be answered before
paid Council calls; 3–4 may stay unknown with the consequence stated.

Applicability is enforced: an indoor piece is never asked for a wind speed.

### Site facts belong to the project

`site_altitude_m`, `design_wind_speed_m_s` and `allowable_bearing_kpa` are
supplied per project and applied over the gate profile. The structural
report gains a `site_overrides` row naming every replaced threshold, its
value **and its source** — so a report read a year later never looks like a
plain profile run. `signed_off` semantics are unchanged.

---

## Phase 11 — DesignDNA (ADR-038)

### Identity is the package digest, not the geometry hash

Two designs can share a STEP byte-for-byte and still be different
precedents: different material, different profile, different BOM. Keying on
`step_sha256` would silently collapse them. Precedents key on the
LUXEXCHANGE `content_digest`, which covers geometry + spec + validation +
BOM together.

The consequence is the useful part: **a design must be exported before it
can be accepted.** A precedent is the accepted deliverable, not a
half-finished shape, and this enforces the pipeline order.

Also enforced: acceptance requires an author and a reason (a precedent that
cannot say why it was good is not knowledge), the same deliverable cannot be
accepted twice, and a design whose validation rolls up to `fail` cannot be
accepted at all.

### Retrieval explains itself

Deterministic AND-matching with a named reason per matched field:

```
f250d74e -> ['material basalt_slab', 'water design']
```

No embeddings. The operator has no coding background and must be able to see
*why* a precedent surfaced and argue with it when it is wrong; an
unexplainable similarity score cannot be debugged.

### Injection is quarantined

Precedents enter a Council prompt in a delimited block stating their numbers
describe PRIOR work, with an explicit instruction never to copy a dimension
over one stated in the brief. Without that framing the Council copies a
precedent's 2.4 m basin into a brief that asked for 1.2 m. Capped at three.

### Archive and delete are different

Archive hides from retrieval and keeps the record, so old sessions that cite
it stay coherent. Delete wipes the payload and leaves a **tombstone** with
the id, so a citing session reports "precedent deleted" rather than
dangling. The original plan treated these as one flow; that loses one
guarantee or the other.

---

## Phase 13 slice A — operations (ADR-040)

### Two ledgers, reconciled

Every provider call is logged twice by different code: per call, and as a
session running total. A dashboard that sums one book proves nothing.
`/api/ops/costs` **reconciles** them and reports disagreement as a named
finding with the session ids, surfaced as a LEDGER MISMATCH badge in the
status bar on every screen.

Live against the operator's own database: `$1.1706` across 28 real calls,
reconciled clean.

Failed calls get their own line — a provider that billed a failed attempt
still cost money, and a flaky connection must not read as work done.

### Failure classes decide the next action

`transient` retry · `resource` free space · `input` fix the request ·
`defect` our bug, do not retry. Grouping everything as "error" leaves the
operator with nothing to do.

### Restore proves itself

Backup uses SQLite's online backup API — never a file copy of a live
database, which snapshots a torn WAL and corrupts silently. Restore then
verifies two ways: table row counts against the backup manifest, and
re-running the **LUXEXCHANGE package's own shipped stdlib verifier** against
the restored package.

"The files are there" is not a restore proof. A package that re-verifies is.

Two findings came out of building this:

- A corrupted archive originally produced a **traceback** instead of a
  report. The operator reads that output to decide whether to trust a
  restore, so it now produces a named finding.
- Writing the reconciliation test revealed that a truly *orphaned* AI call
  is impossible in a healthy database — the foreign key forbids it. The
  endpoint's no-ledger branch remains as defense for restored or older files
  where `PRAGMA foreign_keys` was off, and the test now says so.

---

## The UI (ADR-041)

The tab row became a **pipeline**: Brief → Council → Build → Validate →
Export → Library, with Cascade and Operations grouped separately as tools.
A tab row says what screens exist; it does not say what to do next.

Three rules held throughout:

1. **Every step state is derived, never stored.** A stored flag drifts and
   starts lying. The stepper reads the same data the panels read.
2. **Colour never carries meaning alone.** Every state has a glyph and a
   text detail, so it survives a screenshot and a colour-blind reader.
3. **The numbers that must never require a click live in a status bar** —
   including a polled backend heartbeat, so the connection indicator is true
   even when the operator is idle.

CSS moved to role-named design tokens. `needs_input` keeps its own colour,
distinct from warn: the distinction ADR-036 established in the data now
survives into the pixels.

---

## Evidence

```
full suite            351 passed        (was 315; +36 new)
gate_phase2_auto      PASS   gate_phase8_auto     PASS
gate_phase3_auto      PASS   gate_phase8b_auto    PASS   <- new
gate_phase4_auto      PASS   gate_phase9a_auto    PASS
gate_phase6a1_auto    PASS   gate_phase11_auto    PASS   <- new
gate_costing_auto     PASS   gate_phase13a_auto   PASS   <- new
tsc --noEmit          clean
vite build            clean
```

Verified live against the running stack: intake created → confirmed →
assembly built with intake context → package exported → accepted as
precedent → retrieved by explained search.

---

## What is NOT built

**No visual verification was possible here.** Markup is checked by
server-rendering every component state and reading the HTML, plus a
production build and typecheck. Nobody has looked at the pixels — which is
what `gate_phase11_13a_visual.md` is for.

**Phase 13 is one slice, not the phase.** There is no resumable job runner:
export jobs record checkpoints and re-running is byte-equivalent, but
nothing resumes a killed job. Long Council and fabrication runs remain
all-or-nothing.

**Phase 9B and Phase 10 are untouched.** The Blender render worker is the
only remaining piece needing a download, and the vision critique loop is
blocked behind it.

Full scope limits: `LIMITATIONS.md` §14 (DesignDNA), §15 (intake), §16
(operations), §17 (UI).
