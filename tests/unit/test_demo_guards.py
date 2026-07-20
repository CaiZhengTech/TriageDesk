"""Unit tests for demo-abuse protection (issue #16): the pool endpoint, the
in-memory rate limiter, the daily spend-cap query, and the four
`POST /api/demo/run` response branches. No live DB, no live Anthropic calls —
an in-memory SQLite session stands in for Postgres (same pattern as
test_console_api.py) and `run_ticket` is always monkeypatched.
"""

import threading
import time
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


def test_daily_cap_reserves_per_run_cap_for_inflight_running_runs(db_session):
    """Background dispatch (issue #58) means a running run's cost is not yet
    committed — the pre-check must reserve the per-run cap for each one, or N
    concurrent demo runs could all pass the check (the TOCTOU the dispatch
    lock used to close by serializing execution)."""
    _make_ticket(db_session)
    # Committed spend 0.85 + one in-flight run (reserve 0.10) + this run's
    # 0.10 = 1.05 > 1.00 -> breach.
    _make_run(
        db_session, ticket_id=1,
        created_at=datetime(2026, 1, 2, 3, 0, 0), total_cost_usd=0.85,
    )
    _make_run(
        db_session, ticket_id=1,
        created_at=datetime(2026, 1, 2, 11, 0, 0), total_cost_usd=0.0,
        state="running",
    )

    now = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)

    assert daily_cap_would_be_exceeded(
        db_session, now, daily_cap_usd=1.00, per_run_cost_cap_usd=0.10
    ) is True

    # Without the in-flight run the same numbers fit: 0.85 + 0.10 <= 1.00.
    db_session.query(Run).filter(Run.state == "running").delete()
    db_session.commit()
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

    def fake_execute(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(app_module, "_execute_demo_run", fake_execute)

    resp = client.post("/api/demo/run", json={"ticket_id": 1})

    assert resp.status_code == 404
    assert called["n"] == 0
    assert db_session.query(Run).count() == 0  # no run row either

    resp_missing = client.post("/api/demo/run", json={"ticket_id": 999})
    assert resp_missing.status_code == 404
    assert called["n"] == 0


def test_demo_run_429_when_rate_limited(db_session, client, monkeypatch):
    _make_ticket(db_session, ticket_id=1, source="demo")
    monkeypatch.setattr(settings, "demo_rate_limit_per_hour", 1)
    called = {"n": 0}

    def fake_execute(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(app_module, "_execute_demo_run", fake_execute)

    first = client.post("/api/demo/run", json={"ticket_id": 1})
    assert first.status_code == 202
    assert called["n"] == 1

    second = client.post("/api/demo/run", json={"ticket_id": 1})
    assert second.status_code == 429
    assert second.json() == {"paused": False, "reason": "rate_limited"}
    assert called["n"] == 1  # not dispatched again
    assert db_session.query(Run).count() == 1  # and no second run row


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

    def fake_execute(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(app_module, "_execute_demo_run", fake_execute)

    resp = client.post("/api/demo/run", json={"ticket_id": 1})

    assert resp.status_code == 402
    assert resp.json() == {"paused": True, "reason": "daily_budget_reached"}
    assert called["n"] == 0
    assert db_session.query(Run).count() == 1  # only the pre-existing run


def test_demo_run_202_returns_running_run_id_before_execution(db_session, client, monkeypatch):
    """Issue #58: the endpoint must create the run row and hand back its id
    IMMEDIATELY (state='running'), executing the pipeline afterward — the
    console polls that id to light the pipeline live. A synchronous endpoint
    would return only after the terminal state, and the live view could
    never be live."""
    _make_ticket(db_session, ticket_id=1, source="demo")
    seen = {}

    def fake_execute(run_id):
        # State AT DISPATCH TIME must already be committed as 'running'.
        run = db_session.get(Run, run_id)
        seen["run_id"] = run_id
        seen["state_at_dispatch"] = run.state if run else None

    monkeypatch.setattr(app_module, "_execute_demo_run", fake_execute)

    resp = client.post("/api/demo/run", json={"ticket_id": 1})

    assert resp.status_code == 202
    body = resp.json()
    assert body["run_id"] == str(seen["run_id"])
    assert seen["state_at_dispatch"] == "running"


def test_execute_demo_run_uses_its_own_session_and_runs_pipeline(db_session, monkeypatch):
    """The request-scoped session dies with the response; the background
    executor must open its own and hand the run to execute_run."""
    _make_ticket(db_session, ticket_id=1, source="demo")
    run = _make_run(
        db_session, ticket_id=1,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        total_cost_usd=0.0, state="running",
    )
    calls = {}

    def fake_session_factory():
        return db_session

    def fake_execute_run(run_arg, session_arg):
        calls["run_id"] = run_arg.id
        calls["session"] = session_arg
        return run_arg

    monkeypatch.setattr(app_module, "SessionLocal", fake_session_factory)
    monkeypatch.setattr(app_module, "execute_run", fake_execute_run)
    # db_session must survive the executor's finally-close for later asserts.
    monkeypatch.setattr(db_session, "close", lambda: None)

    app_module._execute_demo_run(run.id)

    assert calls["run_id"] == run.id
    assert calls["session"] is db_session


# --- Concurrency: cap TOCTOU (Important finding, PR #55 review) ---

def test_concurrent_demo_runs_serialized_cap_rechecked(tmp_path, monkeypatch):
    """Two concurrent POSTs must not both pass the cap pre-check off the same
    stale read. `_dispatch_lock` (triagedesk/demo.py) serializes the guard
    chain + run-row creation (execution is a background task since issue #58;
    the in-flight reserve in `daily_cap_would_be_exceeded` covers the running
    run's not-yet-committed cost). A call-counting fake proves
    that re-evaluation, without needing a real DB write in between: if the
    lock didn't serialize the two requests, both calls could race in before
    either wrote a count, and the multiset assertion below would fail.

    Uses a file-backed SQLite DB (own engine, own `get_db` override — one
    fresh Session per request, matching production's real `get_db` in
    triagedesk/db.py) instead of the other tests' shared in-memory
    `db_session`. The shared fixture's `StaticPool` in-memory DB is pinned to
    one physical connection, so two threads genuinely using it at once (not
    just holding separate Session objects) intermittently corrupted read
    state — an artifact of that test double, not of the fix under test. A
    file-backed DB gives each Session its own real connection, closer to how
    Postgres actually behaves here.
    """
    db_path = tmp_path / "concurrent_demo.sqlite3"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
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
    session_factory = sessionmaker(bind=engine)
    seed_session = session_factory()
    _make_ticket(seed_session, ticket_id=1, source="demo")
    seed_session.close()

    def _override():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    # Background executor is a no-op here: this test is about the guard
    # chain's serialization, and the real one would open the process-level
    # SessionLocal (a live DB) from a unit test.
    monkeypatch.setattr(app_module, "_execute_demo_run", lambda run_id: None)

    # Cap not yet reached for the first caller to reach this check under the
    # lock; reached for the second. Deliberately unsynchronized read-sleep-write
    # (not a real fix, just a wide TOCTOU window) so this only comes out
    # correct if callers are serialized end-to-end by `_dispatch_lock` —
    # without the lock, two threads could both read `seen=0` during the sleep
    # and both return "not exceeded", which would fail the assertion below.
    calls = {"n": 0}

    def fake_cap_check(*_a, **_k):
        seen = calls["n"]
        time.sleep(0.05)
        calls["n"] = seen + 1
        return seen > 0

    monkeypatch.setattr(app_module, "daily_cap_would_be_exceeded", fake_cap_check)

    app.dependency_overrides[get_db] = _override
    app_module._demo_rate_limiter.reset()
    client = TestClient(app)

    results: list[int] = []
    results_lock = threading.Lock()

    def _post():
        resp = client.post("/api/demo/run", json={"ticket_id": 1})
        with results_lock:
            results.append(resp.status_code)

    try:
        threads = [threading.Thread(target=_post) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        app.dependency_overrides.clear()
        app_module._demo_rate_limiter.reset()

    assert sorted(results) == [202, 402]
