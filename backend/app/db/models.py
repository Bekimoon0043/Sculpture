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
    tokens_in: Mapped[int] = mapped_column(Integer)
    tokens_out: Mapped[int] = mapped_column(Integer)
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
    """Minimal mapping — projects is not populated yet (the Phase 3 Council
    keys design_specs on council_sessions, not projects; project grouping
    arrives with the project-management phase)."""

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
    tokens_in: Mapped[int] = mapped_column(Integer)
    tokens_out: Mapped[int] = mapped_column(Integer)
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


class ValidationReportRow(Base):
    __tablename__ = "validation_reports"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    design_id: Mapped[str] = mapped_column(Text, ForeignKey("designs.id"))
    gate_name: Mapped[str] = mapped_column(Text)
    passed: Mapped[int] = mapped_column(Integer)
    numbers_json: Mapped[str] = mapped_column(Text)


class SchemaMigrationRow(Base):
    __tablename__ = "schema_migrations"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text)
