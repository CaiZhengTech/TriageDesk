"""SQLAlchemy models — the source of truth for the database schema.

Human-readable reference (tables, enum vocabularies, gotchas, example queries):
docs/00-spec/DATA-SCHEMA.md. Keep it in sync when this file changes; schema changes
go through an Alembic migration.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBED_DIMS = 1024

RUN_STATES = ("running", "completed", "escalated", "failed")


class Base(DeclarativeBase):
    pass


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    queue: Mapped[str] = mapped_column(String(64))  # ground-truth label from dataset
    ticket_type: Mapped[str | None] = mapped_column(String(32))
    priority: Mapped[str | None] = mapped_column(String(16))
    language: Mapped[str] = mapped_column(String(8), default="en")
    source: Mapped[str] = mapped_column(String(16), default="kaggle")  # kaggle | demo
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    state: Mapped[str] = mapped_column(String(16), default="running")
    escalation_reason: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    total_cost_usd: Mapped[float] = mapped_column(default=0.0)
    gate_signals: Mapped[dict | None] = mapped_column(JSONB)
    final_reply: Mapped[str | None] = mapped_column(Text)
    internal_rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column()


class Span(Base):
    __tablename__ = "spans"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"))
    name: Mapped[str] = mapped_column(String(32))  # precheck|classify|retrieve|act|gate
    status: Mapped[str] = mapped_column(String(16), default="started")  # started|ok|error
    started_at: Mapped[datetime] = mapped_column()
    ended_at: Mapped[datetime | None] = mapped_column()
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)  # gen_ai.* keys
    cost_usd: Mapped[float] = mapped_column(default=0.0)


class KbDoc(Base):
    __tablename__ = "kb_docs"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIMS))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    kind: Mapped[str] = mapped_column(String(16))            # representative | adversarial
    expected_outcome: Mapped[str] = mapped_column(String(16))  # route | escalate
    expected_queue: Mapped[str | None] = mapped_column(String(64))     # ground-truth category
    # injection|pii|off_topic|ambiguous|entitlement_denial
    adversarial_kind: Mapped[str | None] = mapped_column(String(24))
    expected_escalation_reason: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), unique=True)
    decision: Mapped[str] = mapped_column(String(8))  # approve | reject
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class EvalResult(Base):
    __tablename__ = "eval_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    eval_run_id: Mapped[uuid.UUID] = mapped_column(Uuid)     # groups one suite execution
    case_id: Mapped[int] = mapped_column(ForeignKey("eval_cases.id"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    predicted_queue: Mapped[str | None] = mapped_column(String(64))
    predicted_outcome: Mapped[str] = mapped_column(String(16))   # route | escalate | failed
    escalation_reason: Mapped[str | None] = mapped_column(String(64))
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    latency_ms: Mapped[float] = mapped_column(default=0.0)
    retrieval_similarity: Mapped[float | None] = mapped_column()
    classification_margin: Mapped[float | None] = mapped_column()
    routing_correct: Mapped[bool | None] = mapped_column()
    outcome_correct: Mapped[bool] = mapped_column(default=False)
    judge_verdict: Mapped[str | None] = mapped_column(String(16))       # pass|fail|needs_review
    judge_reason: Mapped[str | None] = mapped_column(Text)
    judge_rule_triggered: Mapped[str | None] = mapped_column(String(32))
    human_label: Mapped[str | None] = mapped_column(String(16))  # Task 6: pass|fail|needs_review
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
