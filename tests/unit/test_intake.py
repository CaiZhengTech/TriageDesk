"""`POST /api/tickets` — untrusted intake, and the guards that make it safe (#80).

THE THREAT MODEL, AS TESTS
--------------------------
Every other endpoint in this app is safe because it reads a fixed server-side
allowlist: `/api/demo/run` calls `get_demo_ticket` first, so a caller can only
ever name a ticket the operator seeded. Intake deliberately removes that
property — it accepts arbitrary text from outside and dispatches a *paid*
pipeline. That inverts the trust model, so each guard below is a named threat
with a test proving it fires BEFORE any spend.

| Threat | Guard |
|---|---|
| Anyone on the internet drains the budget | shared-secret header, fail-closed when unset |
| One caller floods the queue | per-IP hourly rate limit (shared limiter with the demo) |
| A burst outruns the daily cap | cap re-checked inside the dispatch lock, per-run cost reserved |
| A megabyte body burns input tokens | length bounds on subject and body, enforced by the schema |
| Empty/whitespace ticket wastes a run | non-empty validation |

ORDERING
--------
Two orderings, both verified against live production:

  schema -> auth   FastAPI validates the body while parsing the request, so an
                   oversized payload is a 422 before the handler is entered and
                   before any token comparison. Cheaper, and fine: nothing is
                   persisted and nothing is spent either way.
  auth -> limiter  Asserted below. If the limiter ran first, an unauthenticated
                   flood would burn the per-IP quota a legitimate caller shares
                   -- a denial of service achievable with no credentials.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import triagedesk.app as app_module
from triagedesk.app import MAX_BODY_CHARS, MAX_SUBJECT_CHARS, app
from triagedesk.config import settings
from triagedesk.db import get_db
from triagedesk.models import Run, Ticket

TOKEN = "test-intake-token"
VALID = {"subject": "VPN keeps dropping", "body": "It disconnects every few minutes."}


@pytest.fixture()
def db_session():
    """In-memory SQLite standing in for Postgres, same pattern as
    test_demo_guards.py. The DDL is hand-written rather than
    `Base.metadata.create_all` because `runs.gate_signals` is Postgres JSONB,
    which SQLite cannot compile."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
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
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture()
def client(db_session, monkeypatch):
    """Token configured, pipeline stubbed — no live calls anywhere."""
    monkeypatch.setattr(settings, "intake_token", TOKEN)
    monkeypatch.setattr(app_module, "_execute_inbound_run", lambda run_id: None)

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    app_module._demo_rate_limiter.reset()
    yield TestClient(app)
    app.dependency_overrides.clear()
    app_module._demo_rate_limiter.reset()


def _post(client, body=None, token=TOKEN):
    headers = {"X-Intake-Token": token} if token is not None else {}
    return client.post("/api/tickets", json=body or VALID, headers=headers)


# --- auth: fail closed, and check it FIRST -------------------------------

def test_unset_token_refuses_everything(client, monkeypatch):
    """Fail-closed, matching the review endpoint: an unconfigured secret must
    never mean 'open'. A deploy that forgets the env var gets a dead endpoint,
    not a public one."""
    monkeypatch.setattr(settings, "intake_token", "")
    assert _post(client, token="anything").status_code == 503


def test_wrong_token_is_rejected(client):
    assert _post(client, token="wrong").status_code == 401


def test_missing_header_is_rejected(client):
    assert _post(client, token=None).status_code == 401


def test_rejected_request_creates_no_ticket_and_no_run(client, db_session):
    """The property that matters: a blocked request costs nothing and leaves
    nothing behind."""
    _post(client, token="wrong")
    assert db_session.execute(select(Ticket)).all() == []
    assert db_session.execute(select(Run)).all() == []


def test_auth_is_checked_before_the_rate_limiter(client, monkeypatch):
    """Ordering guard. If the limiter ran first, an unauthenticated flood would
    burn the per-IP quota that a legitimate caller shares — a denial of service
    achievable without credentials."""
    monkeypatch.setattr(settings, "intake_rate_limit_per_hour", 1)
    for _ in range(5):
        assert _post(client, token="wrong").status_code == 401
    assert _post(client).status_code == 202  # quota untouched


# --- input bounds ---------------------------------------------------------

def test_oversized_body_is_rejected_by_the_schema(client):
    resp = _post(client, {"subject": "x", "body": "a" * (MAX_BODY_CHARS + 1)})
    assert resp.status_code == 422


def test_oversized_subject_is_rejected(client):
    resp = _post(client, {"subject": "a" * (MAX_SUBJECT_CHARS + 1), "body": "x"})
    assert resp.status_code == 422


def test_empty_body_is_rejected(client):
    assert _post(client, {"subject": "x", "body": "   "}).status_code == 422


def test_a_body_at_the_limit_is_accepted(client):
    """The bound must not be so tight it rejects a real ticket."""
    resp = _post(client, {"subject": "x", "body": "a" * MAX_BODY_CHARS})
    assert resp.status_code == 202


# --- spend guards ---------------------------------------------------------

def test_rate_limited_caller_gets_429_and_no_run(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "intake_rate_limit_per_hour", 2)
    assert _post(client).status_code == 202
    assert _post(client).status_code == 202
    resp = _post(client)
    assert resp.status_code == 429
    assert resp.json()["reason"] == "rate_limited"
    assert len(db_session.execute(select(Run)).all()) == 2


def test_daily_cap_blocks_before_spending(client, db_session, monkeypatch):
    """Reuses the demo's cap query, so intake and demo traffic share one
    budget — two doors into the same wallet must not each get their own cap."""
    monkeypatch.setattr(app_module, "daily_cap_would_be_exceeded",
                        lambda *a, **k: True)
    resp = _post(client)
    assert resp.status_code == 402
    assert resp.json() == {"paused": True, "reason": "daily_budget_reached"}
    assert db_session.execute(select(Run)).all() == []


def test_capped_request_creates_no_ticket_either(client, db_session, monkeypatch):
    """A cap breach must not leave an orphan ticket row behind — the ticket is
    only persisted once the run is actually dispatched."""
    monkeypatch.setattr(app_module, "daily_cap_would_be_exceeded",
                        lambda *a, **k: True)
    _post(client)
    assert db_session.execute(select(Ticket)).all() == []


# --- the happy path -------------------------------------------------------

def test_accepted_ticket_is_stored_as_inbound(client, db_session):
    resp = _post(client)
    assert resp.status_code == 202
    ticket = db_session.execute(select(Ticket)).scalars().one()
    assert ticket.source == "inbound"      # not 'demo', not 'kaggle'
    assert ticket.subject == VALID["subject"]
    assert ticket.body == VALID["body"]


def test_response_returns_ids_the_caller_can_poll(client, db_session):
    body = _post(client).json()
    run = db_session.execute(select(Run)).scalars().one()
    assert body["run_id"] == str(run.id)
    assert body["ticket_id"] == run.ticket_id
    assert uuid.UUID(body["run_id"])


def test_run_starts_in_running_state_before_execution(client, db_session):
    """202 means accepted, not finished. The row exists immediately so the
    console can poll it — and so the next request's cap check can see it."""
    _post(client)
    run = db_session.execute(select(Run)).scalars().one()
    assert run.state == "running"


def test_inbound_tickets_are_not_exposed_in_the_demo_pool(client, db_session):
    """Containment: the demo pool is a curated allowlist. Untrusted text
    arriving via intake must never become a one-click button for visitors."""
    _post(client)
    pool = client.get("/api/demo/pool").json()
    assert pool["tickets"] == []
