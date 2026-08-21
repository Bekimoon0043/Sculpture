# PHASE_11_DESIGNDNA_PLAN.md - L8 DesignDNA Precedent Memory (2026-08-21)

Phase 11 makes accepted designs searchable and reusable as precedent.

## Current State

- The database has references to a `designdna` concept in decisions.
- No accepted-design precedent workflow is built.
- No retrieval path injects precedent into new Council sessions.

## Build Scope

- Accepted-design action that writes a DesignDNA record.
- Store:
  - brief summary.
  - Design Spec.
  - assembly manifest.
  - validation report.
  - render thumbnails.
  - export manifest.
  - material and scale metadata.
  - climate, culture, and budget tags.
  - cost summary.
  - geometry fingerprint.
- Retrieval by project type, material, size, climate, culture cues, budget
  band, validation profile, and geometry fingerprint.
- Precedent injection into Council prompts with explicit provenance.
- Archive/delete flow for operator control.
- Rule: only accepted designs enter DesignDNA by default.

## Gate

Phase 11 closes when:

- Accepting a design creates one retrievable precedent.
- A later brief retrieves relevant precedents with visible match reasons.
- The Council can use precedent context without copying unsupported claims.
- Archived precedents disappear from normal retrieval.
- Tests cover create, retrieve, inject, archive, and delete behavior.

---

## Design corrections — review 2026-08-21

### R1 — The identity key already exists; do not invent one

"Geometry fingerprint" is ambiguous. Use the two hashes the system already
produces:

- `step_sha256` — identical geometry, byte-exact (Rule 5 guarantees it).
- `content_digest` from the LUXEXCHANGE package (Phase 9A.2) — identical
  *deliverable*, covering geometry, spec, validation and BOM together.

Precedents dedupe on `content_digest`. Two designs whose STEP matches but
whose material or validation profile differs are different precedents, and
`content_digest` separates them where `step_sha256` would not.

### R2 — "Validation profile" is a Phase 8 dependency, not a free-text tag

The retrieval key `validation_profile` only exists once Phase 8 C3 ships
`gate_profiles.yaml`. Until then this field has nothing behind it. Phase 11
must not start before Phase 8 C3/C7, or the key becomes an unvalidated string
that silently never matches.

Store the full rollup alongside it: `overall_status` plus per-gate status. A
precedent that passed with three warnings is materially different from a clean
pass, and a Council prompt that cannot tell them apart will propose the warned
geometry as proven.

### R3 — Acceptance is an event with an author and a reason

`accepted_at`, `accepted_by`, `acceptance_note`. Rule 12: a precedent that
cannot say who accepted it and why is not auditable, and it will be injected
into paid Council prompts for years.

### R4 — Retrieval must be explainable before it is clever

Start with deterministic structured matching over the tags, returning a
per-field match reason ("same material, same profile, 0.8× scale"). Do not
start with embeddings. An operator with no coding background needs to see
*why* a precedent surfaced; an unexplainable similarity score is unauditable
and cannot be debugged when it retrieves something wrong.

Embedding search over brief text is a later, additive slice — and if it is
added, it must run locally (Rule 7: no project data leaves the machine).

### R5 — Injection must be quarantined and attributed

Injected precedent enters the Council prompt in a clearly delimited block
marked as prior work, with its `design_id` and acceptance note, and an explicit
instruction that its numbers are precedent rather than requirements. Without
that, precedent contaminates the spec: the Council copies a 2.4 m basin into a
brief that asked for 1.2 m because the precedent said so.

Cap the number of injected precedents and record the token cost of injection
separately in `ai_calls`, so the operator can see what precedent memory costs
per session.

### R6 — Archive and delete are different operations

`archive` hides from retrieval and keeps the record, so old sessions that cite
it stay coherent. `delete` removes it, and must therefore leave a tombstone
with the id so a session that cited it reports "precedent deleted" rather than
a dangling reference. The current plan treats these as one flow; they are not.

### Revised gate additions

- Two designs with identical STEP but different materials produce two
  precedents, not one.
- A retrieval result names the matched fields and their values.
- An archived precedent is absent from retrieval and still resolvable by id
  from an old session.
- A deleted precedent leaves a tombstone and no old session errors.
- Injection cost appears as its own logged token count.
