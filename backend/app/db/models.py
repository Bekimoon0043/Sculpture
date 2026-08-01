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
    """Minimal mapping — Phase 2 does not populate projects (Phase 3 does);
    the mapper exists because design_specs -> projects is a FK chain that
    SQLAlchemy must resolve."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    brief_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)


class DesignSpecRow(Base):
    """Minimal mapping — no council Design Spec exists in Phase 2; the mapper
    exists so designs.spec_id's foreign key resolves."""

    __tablename__ = "design_specs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("projects.id"))
    spec_json: Mapped[str] = mapped_column(Text)
    spec_hash: Mapped[str] = mapped_column(Text)
    seed: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(Text)


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
