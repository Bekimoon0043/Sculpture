"""SQLAlchemy models for the Phase 1 tables that Phase 1 code reads/writes.

Later-phase tables exist in schema.sql (created up-front per approved plan
section D3) and gain ORM models in the phase that populates them — Phase 1
must not pretend to use them (Rule 1: nothing fake).
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    started_at: Mapped[str] = mapped_column(Text)
    ended_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)


class AICallRow(Base):
    __tablename__ = "ai_calls"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("sessions.id"))
    ts: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(Integer)  # uncached input (ADR-022)
    tokens_out: Mapped[int] = mapped_column(Integer)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float)
    cost_usd: Mapped[float] = mapped_column(Float)
    pricing_version: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class BudgetEventRow(Base):
    __tablename__ = "budget_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(Text)
    ts: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text)
    detail: Mapped[str] = mapped_column(Text)


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(Text)
    ts: Mapped[str] = mapped_column(Text)
    job_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    state_json: Mapped[str] = mapped_column(Text)
    halt_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# Phase 2 tables (populated by the geometry API — Phase 2 uses them for real)
# ---------------------------------------------------------------------------


class ProjectRow(Base):
    """Operator-created design project (activated in Phase 15E)."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    brief_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)


class DesignSpecRow(Base):
    """Phase 3 shape — a Council-produced Design Spec bound to its session."""

    __tablename__ = "design_specs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("council_sessions.id"))
    provider: Mapped[str] = mapped_column(Text)
    alternative_no: Mapped[int] = mapped_column(Integer)
    spec_json: Mapped[str] = mapped_column(Text)
    spec_hash: Mapped[str] = mapped_column(Text)
    seed: Mapped[int] = mapped_column(Integer)
    schema_valid: Mapped[int] = mapped_column(Integer)


# ---------------------------------------------------------------------------
# Phase 3 Council tables (populated by the Council orchestrator / replay)
# ---------------------------------------------------------------------------


class CouncilSessionRow(Base):
    __tablename__ = "council_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    brief_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    started_at: Mapped[str] = mapped_column(Text)
    ended_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    pricing_version: Mapped[str] = mapped_column(Text)
    arbiter_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    degraded: Mapped[int] = mapped_column(Integer, default=0)
    # ADR-025: corrected = a bounded re-ask succeeded (self-correction);
    # degraded above = a provider FAILURE left a seat empty/reduced.
    corrected: Mapped[int] = mapped_column(Integer, default=0)
    #: Phase 11/12: what was injected into this session's brief —
    #: {intake_id, precedent_ids, block_chars}. NULL = plain brief.
    context_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class CouncilCallRow(Base):
    __tablename__ = "council_calls"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("council_sessions.id"))
    ts: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    side: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(Integer)  # uncached input (ADR-022)
    tokens_out: Mapped[int] = mapped_column(Integer)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float)
    cost_usd: Mapped[float] = mapped_column(Float)
    pricing_version: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class EngineeringReviewRow(Base):
    __tablename__ = "engineering_reviews"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("council_sessions.id"))
    provider: Mapped[str] = mapped_column(Text)
    side: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text)


class DefectListRow(Base):
    __tablename__ = "defect_lists"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("council_sessions.id"))
    provider: Mapped[str] = mapped_column(Text)
    side: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text)


class ArbiterDecisionRow(Base):
    __tablename__ = "arbiter_decisions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("council_sessions.id"))
    chosen_spec_ids_json: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    disagreement_register_json: Mapped[str] = mapped_column(Text)
    binding: Mapped[int] = mapped_column(Integer, default=1)


class GeneratedProgramRow(Base):
    """Phase 4: one GEOMETRIST-written program per row — including every
    REJECTED attempt with its AST-gate reason (operator order 2026-08-09:
    the rejection catalogue informs the Phase 6 vocabulary widening)."""

    __tablename__ = "generated_programs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str] = mapped_column(Text)
    spec_id: Mapped[str] = mapped_column(Text)
    attempt_no: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    program_text: Mapped[str] = mapped_column(Text)
    program_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifacts_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Phase 6 slice A2: the assembly_manifest_v1 the sandbox returned, when
    #: the program built an assembly. NULL for cascade runs and all history.
    manifest_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class DesignRow(Base):
    __tablename__ = "designs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    spec_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("design_specs.id"), nullable=True
    )
    geometry_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameter_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spec_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    build_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    glb_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("projects.id"), nullable=True
    )
    parent_design_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("designs.id"), nullable=True
    )
    #: Phase 6 slice A2: set when this design was persisted by the
    #: fabrication loop — the passing GEOMETRIST program it came from.
    #: NULL for operator-built designs and all history.
    generated_program_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("generated_programs.id"), nullable=True
    )


class ValidationReportRow(Base):
    __tablename__ = "validation_reports"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    design_id: Mapped[str] = mapped_column(Text, ForeignKey("designs.id"))
    gate_name: Mapped[str] = mapped_column(Text)
    #: Legacy boolean. Phase 8 redefines it as `status == "pass"` — a warn is
    #: NOT a pass, and neither is needs_input. Read `status` for the truth.
    passed: Mapped[int] = mapped_column(Integer)
    #: pass | warn | fail | needs_input (Phase 8). Nullable for rows written
    #: before the patch.
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    numbers_json: Mapped[str] = mapped_column(Text)


class DesignDnaRow(Base):
    """One accepted-design precedent (Phase 11, L8).

    `summary_json` is the full record (request, manifest, validation,
    costing); `tags_json` is the small queryable surface retrieval filters
    on. status: active | archived | deleted (deleted = tombstone: payload
    wiped, identity kept so old sessions that cite it stay coherent)."""

    __tablename__ = "designdna"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    design_id: Mapped[str] = mapped_column(Text, ForeignKey("designs.id"))
    embedding_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class IntakeRow(Base):
    """One brief-intake record (Phase 12, L1).

    `normalized_json` holds intake_v1: every field wrapped with its source
    (operator | parsed | default | unknown) so the UI can show what the
    parser inferred versus what the operator typed, and `unknown` stays
    distinguishable from a defaulted value all the way to the gates."""

    __tablename__ = "intakes"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)
    brief_text: Mapped[str] = mapped_column(Text)
    normalized_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)  # draft | confirmed
    council_session_id: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExportRow(Base):
    __tablename__ = "exports"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    design_id: Mapped[str] = mapped_column(Text, ForeignKey("designs.id"))
    format: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    tool_versions_json: Mapped[str] = mapped_column(Text)
    # Phase 9A: hashes are computed once at export time and read from here
    # afterwards — never re-hashed on a UI poll.
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: included | failed | unavailable | impossible
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[str | None] = mapped_column(Text, nullable=True)


class SchemaMigrationRow(Base):
    __tablename__ = "schema_migrations"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text)
