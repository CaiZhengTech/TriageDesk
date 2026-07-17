"""Unit tests for the runs read API (list + detail) — console_queries.py + the
/api/runs routes. No live DB: an in-memory SQLite session stands in for Postgres.
JSONB columns (runs.gate_signals, spans.attributes) are created here as JSON —
SQLite has no JSONB — the ORM classes in triagedesk.models are used unmodified.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from triagedesk.app import app
from triagedesk.console_queries import _duration_ms
from triagedesk.db import get_db
from triagedesk.models import Run, Span, Ticket


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE tickets (
                id INTEGER PRIMARY KEY,
                subject TEXT, body TEXT, queue VARCHAR(64),
                ticket_type VARCHAR(32), priority VARCHAR(16),
                language VARCHAR(8), source VARCHAR(16), created_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE runs (
                id CHAR(32) PRIMARY KEY,
                ticket_id INTEGER, state VARCHAR(16), escalation_reason VARCHAR(64),
                prompt_version VARCHAR(32), model VARCHAR(64), total_cost_usd FLOAT,
                gate_signals JSON, final_reply TEXT, internal_rationale TEXT,
                created_at TIMESTAMP, finished_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE spans (
                id INTEGER PRIMARY KEY,
                run_id CHAR(32), name VARCHAR(32), status VARCHAR(16),
                started_at TIMESTAMP, ended_at TIMESTAMP, attributes JSON, cost_usd FLOAT
            )
        """))
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


def _make_ticket(db_session, ticket_id=1, subject="My VPN keeps disconnecting"):
    ticket = Ticket(
        id=ticket_id, subject=subject, body="body", queue="IT Support",
        language="en", source="demo",
    )
    db_session.add(ticket)
    db_session.commit()
    return ticket


def _make_run(db_session, ticket_id, **overrides):
    defaults = dict(
        id=uuid.uuid4(),
        ticket_id=ticket_id,
        state="completed",
        prompt_version="v1",
        model="claude-sonnet-4-6",
        total_cost_usd=0.01,
        created_at=datetime(2026, 1, 1, 12, 0, 0),  # naive, matches server-default behavior
        finished_at=None,
    )
    defaults.update(overrides)
    run = Run(**defaults)
    db_session.add(run)
    db_session.commit()
    return run


# (a) list returns newest-first with computed latency_ms and a failed run present with its reason
def test_list_runs_newest_first_with_latency_and_failed_run_visible(db_session, client):
    _make_ticket(db_session)
    older = _make_run(
        db_session, ticket_id=1,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        finished_at=datetime(2026, 1, 1, 12, 0, 5, tzinfo=UTC),
        state="completed",
    )
    newer = _make_run(
        db_session, ticket_id=1,
        created_at=datetime(2026, 1, 1, 13, 0, 0),
        finished_at=None,
        state="failed",
        escalation_reason="budget_breach",
    )

    resp = client.get("/api/runs")

    assert resp.status_code == 200
    body = resp.json()
    assert [r["id"] for r in body["runs"]] == [str(newer.id), str(older.id)]

    older_row = next(r for r in body["runs"] if r["id"] == str(older.id))
    assert older_row["latency_ms"] == pytest.approx(5000.0)

    failed_row = next(r for r in body["runs"] if r["id"] == str(newer.id))
    assert failed_row["state"] == "failed"
    assert failed_row["escalation_reason"] == "budget_breach"
    assert failed_row["latency_ms"] is None


# (b) tz normalization: naive created_at + aware finished_at subtract without raising
def test_duration_ms_normalizes_naive_and_aware_datetimes():
    created = datetime(2026, 1, 1, 12, 0, 0)  # naive
    finished = datetime(2026, 1, 1, 12, 0, 3, tzinfo=UTC)  # aware

    assert _duration_ms(created, finished) == pytest.approx(3000.0)


def test_duration_ms_is_none_when_finished_at_missing():
    assert _duration_ms(datetime(2026, 1, 1, 12, 0, 0), None) is None


# (c) detail 404 on missing; 422 on non-UUID
def test_get_run_detail_404_on_missing_id(client):
    resp = client.get(f"/api/runs/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_run_detail_422_on_non_uuid_id(client):
    resp = client.get("/api/runs/not-a-uuid")
    assert resp.status_code == 422


# (d) detail spans ordered with token/cost fields extracted
def test_get_run_detail_spans_ordered_with_tokens_and_cost(db_session, client):
    _make_ticket(db_session)
    run = _make_run(db_session, ticket_id=1)

    span_last = Span(
        run_id=run.id, name="gate", status="ok",
        started_at=datetime(2026, 1, 1, 12, 0, 3, tzinfo=UTC),
        ended_at=datetime(2026, 1, 1, 12, 0, 4, tzinfo=UTC),
        attributes={}, cost_usd=0.0,
    )
    span_first = Span(
        run_id=run.id, name="precheck", status="ok",
        started_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        ended_at=datetime(2026, 1, 1, 12, 0, 1, tzinfo=UTC),
        attributes={
            "gen_ai.usage.input_tokens": 100,
            "gen_ai.usage.output_tokens": 20,
        },
        cost_usd=0.002,
    )
    db_session.add_all([span_last, span_first])
    db_session.commit()

    resp = client.get(f"/api/runs/{run.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert [s["name"] for s in body["spans"]] == ["precheck", "gate"]
    first = body["spans"][0]
    assert first["input_tokens"] == 100
    assert first["output_tokens"] == 20
    assert first["cost_usd"] == pytest.approx(0.002)
    assert first["duration_ms"] == pytest.approx(1000.0)
    last = body["spans"][1]
    assert last["input_tokens"] is None
    assert last["output_tokens"] is None


# (e) list pagination (total independent of limit)
def test_list_runs_pagination_total_independent_of_limit(db_session, client):
    _make_ticket(db_session)
    for i in range(3):
        _make_run(
            db_session, ticket_id=1,
            created_at=datetime(2026, 1, 1, 12, i, 0),
        )

    resp = client.get("/api/runs?limit=1&offset=0")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["runs"]) == 1
    assert body["total"] == 3
