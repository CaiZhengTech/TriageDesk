"""Read-only queries for the console API.

All reads for the ops console go through here, taking a `Session` — no ORM
queries inline in routes (see docs/00-spec/DATA-SCHEMA.md for the schema and
its gotchas, in particular the `created_at`/`finished_at` timezone mismatch).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from triagedesk.models import ReviewDecision, Run, Span, Ticket


def _to_naive_utc(dt: datetime) -> datetime:
    """Aware -> naive UTC. Naive datetimes pass through (already assumed UTC)."""
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _duration_ms(start: datetime | None, end: datetime | None) -> float | None:
    """Milliseconds between two timestamps.

    `runs.created_at` is timezone-naive (server default) while `runs.finished_at`
    is timezone-aware (set in Python) — subtracting them directly raises
    TypeError. Normalize both to naive UTC first.
    """
    if start is None or end is None:
        return None
    delta = _to_naive_utc(end) - _to_naive_utc(start)
    return delta.total_seconds() * 1000


def _run_summary(run: Run, ticket_subject: str) -> dict:
    return {
        "id": str(run.id),
        "ticket_id": run.ticket_id,
        "ticket_subject": ticket_subject,
        "state": run.state,
        "escalation_reason": run.escalation_reason,
        "total_cost_usd": run.total_cost_usd,
        "latency_ms": _duration_ms(run.created_at, run.finished_at),
        "model": run.model,
        "created_at": run.created_at.isoformat(),
    }


def list_runs(db: Session, limit: int = 50, offset: int = 0) -> dict:
    """Newest-first run list. `total` is the full row count, independent of `limit`."""
    total = db.scalar(select(func.count()).select_from(Run))
    rows = db.execute(
        select(Run, Ticket.subject)
        .join(Ticket, Run.ticket_id == Ticket.id)
        .order_by(Run.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "runs": [_run_summary(run, subject) for run, subject in rows],
        "total": total,
    }


def list_review_queue(db: Session) -> dict:
    """Escalated runs with no review decision yet, oldest first (the human inbox).

    No filter on `escalation_reason` — adverse-action escalations appear like any
    other escalated run (the adverse-action rule requires it, it does not exempt it).
    """
    decided_run_ids = select(ReviewDecision.run_id)
    rows = db.execute(
        select(Run, Ticket.subject)
        .join(Ticket, Run.ticket_id == Ticket.id)
        .where(Run.state == "escalated", Run.id.not_in(decided_run_ids))
        .order_by(Run.created_at.asc())
    ).all()
    items = []
    for run, subject in rows:
        item = _run_summary(run, subject)
        item["internal_rationale"] = run.internal_rationale
        item["final_reply"] = run.final_reply
        items.append(item)
    return {"items": items, "total": len(items)}


def _span_summary(span: Span) -> dict:
    attrs = span.attributes or {}
    return {
        "name": span.name,
        "status": span.status,
        "duration_ms": _duration_ms(span.started_at, span.ended_at),
        "input_tokens": attrs.get("gen_ai.usage.input_tokens"),
        "output_tokens": attrs.get("gen_ai.usage.output_tokens"),
        "cost_usd": span.cost_usd,
        "attributes": attrs,
    }


def get_run_detail(db: Session, run_id: uuid.UUID) -> dict | None:
    """Full run detail: summary fields + reply/rationale/gate signals + ordered spans.

    Returns None if `run_id` doesn't exist — the route turns that into a 404.
    """
    run = db.get(Run, run_id)
    if run is None:
        return None
    ticket = db.get(Ticket, run.ticket_id)
    spans = db.execute(
        select(Span).where(Span.run_id == run_id).order_by(Span.started_at)
    ).scalars().all()

    detail = _run_summary(run, ticket.subject)
    detail.update({
        "final_reply": run.final_reply,
        "internal_rationale": run.internal_rationale,
        "gate_signals": run.gate_signals,
        "spans": [_span_summary(s) for s in spans],
    })
    return detail
