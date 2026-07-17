"""Unit tests for demo-abuse protection (issue #16): the pool endpoint, the
in-memory rate limiter, the daily spend-cap query, and the four
`POST /api/demo/run` response branches. No live DB, no live Anthropic calls —
an in-memory SQLite session stands in for Postgres (same pattern as
test_console_api.py) and `run_ticket` is always monkeypatched.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import triagedesk.app as app_module
from triagedesk.app import app
from triagedesk.config import settings
from triagedesk.db import get_db
from triagedesk.demo import RateLimiter, daily_cap_would_be_exceeded
from triagedesk.models import Run, Ticket

# --- RateLimiter: pure unit tests, fake clock injected (no time.time()) ---

def test_rate_limiter_allows_up_to_limit_then_blocks():
    limiter = RateLimiter()
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    assert limiter.check("1.2.3.4", now, limit=2) is True
    assert limiter.check("1.2.3.4", now, limit=2) is True
    assert limiter.check("1.2.3.4", now, limit=2) is False


def test_rate_limiter_resets_after_window_via_fake_clock():
    limiter = RateLimiter()
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    assert limiter.check("1.2.3.4", t0, limit=1) is True
    assert limiter.check("1.2.3.4", t0, limit=1) is False

    just_before_reset = t0 + timedelta(hours=1) - timedelta(seconds=1)
    assert limiter.check("1.2.3.4", just_before_reset, limit=1) is False

    after_reset = t0 + timedelta(hours=1)
    assert limiter.check("1.2.3.4", after_reset, limit=1) is True


def test_rate_limiter_tracks_keys_independently():
    limiter = RateLimiter()
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    assert limiter.check("1.2.3.4", now, limit=1) is True
    assert limiter.check("5.6.7.8", now, limit=1) is True
    assert limiter.check("1.2.3.4", now, limit=1) is False


# --- daily_cap_would_be_exceeded: tz-explicit UTC day window ---

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
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_ticket(db_session, ticket_id=1, source="demo", subject="My VPN keeps disconnecting"):
    ticket = Ticket(
        id=ticket_id, subject=subject, body="body", queue="IT Support",
        language="en", source=source,
    )
    db_session.add(ticket)
    db_session.commit()
    return ticket


def _make_run(db_session, ticket_id, created_at, total_cost_usd, state="completed"):
    run = Run(
        id=uuid.uuid4(), ticket_id=ticket_id, state=state,
        prompt_version="v1", model="claude-sonnet-4-6",
        total_cost_usd=total_cost_usd, created_at=created_at,
    )
    db_session.add(run)
    db_session.commit()
    return run


def test_daily_cap_sums_only_todays_utc_runs_and_flags_breach(db_session):
    _make_ticket(db_session)
    # Today: 0.95 spent already. Per-run cap 0.10 would push it to 1.05 > 1.00 cap.
    _make_run(
        db_session, ticket_id=1,
        created_at=datetime(2026, 1, 2, 3, 0, 0), total_cost_usd=0.95,
    )
    # Yesterday's spend must not count toward today's window.
    _make_run(
        db_session, ticket_id=1,
        created_at=datetime(2026, 1, 1, 23, 59, 0), total_cost_usd=0.90,
    )

    now = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)

    assert daily_cap_would_be_exceeded(
        db_session, now, daily_cap_usd=1.00, per_run_cost_cap_usd=0.10
    ) is True


def test_daily_cap_under_budget_is_not_a_breach(db_session):
    _make_ticket(db_session)
    _make_run(
        db_session, ticket_id=1,
        created_at=datetime(2026, 1, 2, 3, 0, 0), total_cost_usd=0.10,
    )

    now = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)

    assert daily_cap_would_be_exceeded(
        db_session, now, daily_cap_usd=1.00, per_run_cost_cap_usd=0.10
    ) is False


def test_daily_cap_no_runs_today_is_not_a_breach(db_session):
    _make_ticket(db_session)

    now = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)

    assert daily_cap_would_be_exceeded(
        db_session, now, daily_cap_usd=1.00, per_run_cost_cap_usd=0.10
    ) is False


def test_daily_cap_fails_closed_when_sum_cannot_be_computed():
    class ExplodingSession:
        def scalar(self, *_args, **_kwargs):
            raise RuntimeError("db unavailable")

    now = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)

    assert daily_cap_would_be_exceeded(
        ExplodingSession(), now, daily_cap_usd=1.00, per_run_cost_cap_usd=0.10
    ) is True


# --- Route-level: the four POST /api/demo/run branches, "before spending" ---

@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    app_module._demo_rate_limiter.reset()
    yield TestClient(app)
    app.dependency_overrides.clear()
    app_module._demo_rate_limiter.reset()


def test_demo_pool_returns_only_demo_source_tickets(db_session, client):
    _make_ticket(db_session, ticket_id=1, source="demo", subject="VPN drops")
    _make_ticket(db_session, ticket_id=2, source="kaggle", subject="A real dataset ticket")

    resp = client.get("/api/demo/pool")

    assert resp.status_code == 200
    body = resp.json()
    assert body["tickets"] == [{"id": 1, "subject": "VPN drops"}]


def test_demo_run_404_when_ticket_not_in_pool(db_session, client, monkeypatch):
    _make_ticket(db_session, ticket_id=1, source="kaggle")  # exists, but not source='demo'
    called = {"n": 0}

    def fake_run_ticket(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(app_module, "run_ticket", fake_run_ticket)

    resp = client.post("/api/demo/run", json={"ticket_id": 1})

    assert resp.status_code == 404
    assert called["n"] == 0

    resp_missing = client.post("/api/demo/run", json={"ticket_id": 999})
    assert resp_missing.status_code == 404
    assert called["n"] == 0


def test_demo_run_429_when_rate_limited(db_session, client, monkeypatch):
    _make_ticket(db_session, ticket_id=1, source="demo")
    monkeypatch.setattr(settings, "demo_rate_limit_per_hour", 1)
    fake_run = Run(
        id=uuid.uuid4(), ticket_id=1, state="completed",
        prompt_version="v1", model="claude-sonnet-4-6", total_cost_usd=0.03,
    )
    called = {"n": 0}

    def fake_run_ticket(*a, **k):
        called["n"] += 1
        return fake_run

    monkeypatch.setattr(app_module, "run_ticket", fake_run_ticket)

    first = client.post("/api/demo/run", json={"ticket_id": 1})
    assert first.status_code == 202
    assert called["n"] == 1

    second = client.post("/api/demo/run", json={"ticket_id": 1})
    assert second.status_code == 429
    assert second.json() == {"paused": False, "reason": "rate_limited"}
    assert called["n"] == 1  # not called again


def test_demo_run_402_when_daily_cap_reached(db_session, client, monkeypatch):
    _make_ticket(db_session, ticket_id=1, source="demo")
    monkeypatch.setattr(settings, "demo_daily_cap_usd", 1.00)
    monkeypatch.setattr(settings, "cost_cap_usd", 0.10)
    _make_run(
        db_session, ticket_id=1,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        total_cost_usd=0.95,
    )
    called = {"n": 0}

    def fake_run_ticket(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(app_module, "run_ticket", fake_run_ticket)

    resp = client.post("/api/demo/run", json={"ticket_id": 1})

    assert resp.status_code == 402
    assert resp.json() == {"paused": True, "reason": "daily_budget_reached"}
    assert called["n"] == 0


def test_demo_run_202_dispatches_pipeline_and_returns_run_id(db_session, client, monkeypatch):
    _make_ticket(db_session, ticket_id=1, source="demo")
    fake_run = Run(
        id=uuid.uuid4(), ticket_id=1, state="completed",
        prompt_version="v1", model="claude-sonnet-4-6", total_cost_usd=0.03,
    )
    calls = []

    def fake_run_ticket(ticket_id, session):
        calls.append(ticket_id)
        return fake_run

    monkeypatch.setattr(app_module, "run_ticket", fake_run_ticket)

    resp = client.post("/api/demo/run", json={"ticket_id": 1})

    assert resp.status_code == 202
    assert resp.json() == {"run_id": str(fake_run.id)}
    assert calls == [1]
