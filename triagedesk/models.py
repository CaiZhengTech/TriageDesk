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
