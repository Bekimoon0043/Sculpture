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
