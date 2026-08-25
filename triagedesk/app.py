import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from triagedesk.config import settings
from triagedesk.console_queries import get_run_detail, list_review_queue, list_runs
from triagedesk.db import SessionLocal, get_db
from triagedesk.demo import (
    RateLimiter,
    _dispatch_lock,
    daily_cap_would_be_exceeded,
    get_demo_ticket,
    list_demo_pool,
)
from triagedesk.logging_setup import configure_json_logging
from triagedesk.models import ReviewDecision, Run, Ticket
from triagedesk.pipeline.runner import create_run, execute_run

app = FastAPI(title="TriageDesk")

# One rate limiter per process (see triagedesk/demo.py's RateLimiter docstring
# for the documented single-instance limitation).
_demo_rate_limiter = RateLimiter()

if settings.log_json:
    configure_json_logging()

# CORS is fail-closed: an empty cors_origins means NO cross-origin access, so the
# cleanest way to express that is to not register the middleware at all rather than
# add it with an empty allow_origins list. No wildcard is ever used. The console's
# requests are JSON POSTs carrying a custom auth header, so the preflight needs both
# that header and Content-Type explicitly allowed.
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["X-Admin-Token", "Content-Type"],
    )
else:
    # Fail-closed is correct, but it used to fail SILENTLY, and the resulting
    # symptom points nowhere near the cause: server-rendered pages load fine
    # (Next fetches from the server, no CORS involved) while every browser-side
    # call — the demo Run button, expanding a trace — dies with a generic
    # "couldn't reach the API". Cost a live debugging session; say it loudly.
    logging.getLogger("triagedesk").warning(
        "CORS_ORIGINS is unset: no CORSMiddleware registered. Server-rendered "
        "pages will work, but every browser-side fetch will be blocked. Set "
        "CORS_ORIGINS to the console origin (e.g. https://<app>.vercel.app)."
    )


class ReviewDecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    note: str


class DemoRunIn(BaseModel):
    ticket_id: int


# Bounds on untrusted input. Generous enough for a real support ticket (the
# Kaggle corpus tops out around 4KB) but far below anything that could burn a
# meaningful number of input tokens. Enforced by the schema, so an oversized
# body is a 422 before any handler code runs -- and before any spend.
MAX_SUBJECT_CHARS = 300
MAX_BODY_CHARS = 8000


class TicketIn(BaseModel):
    """An inbound ticket from outside the system. Every field is untrusted."""

    subject: str = Field(min_length=1, max_length=MAX_SUBJECT_CHARS)
    body: str = Field(min_length=1, max_length=MAX_BODY_CHARS)

    @field_validator("subject", "body")
    @classmethod
    def _not_only_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty or whitespace-only")
        return v


@app.get("/health")
def health() -> dict:
    """Liveness, plus the two config facts whose absence is invisible from the
    outside. `cors_configured` false is the single most likely cause of a
    console that renders but whose buttons do nothing; `admin_token_configured`
    false means every review POST fails closed with 503."""
    return {
        "status": "ok",
        "cors_configured": bool(_cors_origins),
        "admin_token_configured": bool(settings.admin_token),
    }


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> dict:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "body": ticket.body,
        "queue": ticket.queue,
        "language": ticket.language,
        "source": ticket.source,
    }


@app.get("/api/runs")
def api_list_runs(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    return list_runs(db, limit=limit, offset=offset)


@app.get("/api/runs/{run_id}")
def api_get_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    detail = get_run_detail(db, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="run not found")
    return detail


@app.get("/api/review-queue")
def api_review_queue(db: Session = Depends(get_db)) -> dict:
    return list_review_queue(db)


@app.post("/api/review/{run_id}", status_code=201)
def api_post_review(
    run_id: uuid.UUID,
    body: ReviewDecisionIn,
    x_admin_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    # Fail closed: an unset admin token must never mean open, regardless of
    # what header the caller sends.
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="admin token not configured")
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="invalid admin token")

    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    existing = db.execute(
        select(ReviewDecision).where(ReviewDecision.run_id == run_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="run already has a decision")

    decision = ReviewDecision(run_id=run_id, decision=body.decision, note=body.note)
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return {"id": decision.id}


@app.get("/api/demo/pool")
def api_demo_pool(db: Session = Depends(get_db)) -> dict:
    return list_demo_pool(db)


@app.post("/api/demo/run", status_code=202)
def api_demo_run(
    body: DemoRunIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    # Three guards, all evaluated BEFORE the pipeline runs — a blocked
    # request must never spend money (docs/week-3-console/PLAN.md's "before
    # spending" semantics for Task 7).
    ticket = get_demo_ticket(db, body.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not in demo pool")

    # Serialize the guards AND the run-row creation: creating the row inside
    # the lock makes the new run visible (state='running') to the next
    # request's cap pre-check, which reserves the per-run cap for it — the
    # background-dispatch replacement for the old serialized-execution
    # guarantee (bounded overspend -> zero). Issue #58 moved execution out of
    # the request so the console can poll the run id and watch it live; a
    # 202 that blocked to completion was never really a 202.
    with _dispatch_lock:
        host = request.client.host if request.client else "unknown"
        if not _demo_rate_limiter.check(
            host, datetime.now(UTC), settings.demo_rate_limit_per_hour
        ):
            return JSONResponse(
                status_code=429, content={"paused": False, "reason": "rate_limited"}
            )

        if daily_cap_would_be_exceeded(
            db, datetime.now(UTC), settings.demo_daily_cap_usd, settings.cost_cap_usd
        ):
            return JSONResponse(
                status_code=402,
                content={"paused": True, "reason": "daily_budget_reached"},
            )

        run = create_run(body.ticket_id, db)

    background_tasks.add_task(_execute_demo_run, run.id)
    return {"run_id": str(run.id)}


@app.post("/api/tickets", status_code=202)
def api_intake(
    body: TicketIn,
    request: Request,
    background_tasks: BackgroundTasks,
    x_intake_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Accept a ticket from outside the system and run it through the pipeline.

    THIS IS THE ONLY ENDPOINT THAT ACCEPTS UNTRUSTED TEXT AND SPENDS MONEY.
    Everywhere else is safe because it reads a fixed server-side allowlist --
    `/api/demo/run` calls `get_demo_ticket` first, so a caller can only name a
    ticket the operator seeded. Intake removes that property deliberately, which
    is the point (the pre-check stage exists to screen untrusted input and had
    never seen any) and also the risk. Hence the guards, in this order:

      1. shared secret, fail-closed when unset
      2. per-IP rate limit -- AFTER auth, so an unauthenticated flood cannot
         burn a legitimate caller's quota
      3. daily spend cap, re-checked inside the dispatch lock
      4. length bounds, enforced by TicketIn before this function is entered

    Nothing is persisted and nothing is spent until every guard passes: the
    ticket row is created inside the lock alongside the run, so a blocked
    request leaves no orphan rows behind.
    """
    # 1. Auth first. An unset token means 503, never open -- same fail-closed
    #    rule as the review endpoint.
    if not settings.intake_token:
        raise HTTPException(status_code=503, detail="intake token not configured")
    if x_intake_token != settings.intake_token:
        raise HTTPException(status_code=401, detail="invalid intake token")

    with _dispatch_lock:
        host = request.client.host if request.client else "unknown"
        # 2. Rate limit. Shares the demo's limiter: one caller should not get a
        #    fresh quota just by switching doors.
        if not _demo_rate_limiter.check(
            host, datetime.now(UTC), settings.intake_rate_limit_per_hour
        ):
            return JSONResponse(
                status_code=429, content={"paused": False, "reason": "rate_limited"}
            )

        # 3. Daily cap. Also shared with the demo -- two doors, one wallet.
        if daily_cap_would_be_exceeded(
            db, datetime.now(UTC), settings.demo_daily_cap_usd, settings.cost_cap_usd
        ):
            return JSONResponse(
                status_code=402,
                content={"paused": True, "reason": "daily_budget_reached"},
            )

        # source='inbound' keeps untrusted text out of the curated demo pool
        # (which filters on source='demo'), so an inbound ticket can never
        # become a one-click button for a visitor.
        ticket = Ticket(subject=body.subject, body=body.body,
                        queue="General Inquiry", language="en", source="inbound")
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        run = create_run(ticket.id, db)

    background_tasks.add_task(_execute_inbound_run, run.id)
    return {"run_id": str(run.id), "ticket_id": ticket.id}


def _execute_inbound_run(run_id) -> None:
    """Background half of intake dispatch. Same shape as the demo's: the
    request-scoped session dies with the response, so this opens its own."""
    session = SessionLocal()
    try:
        run = session.get(Run, run_id)
        if run is None:
            return
        execute_run(run, session)
    finally:
        session.close()


def _execute_demo_run(run_id) -> None:
    """Background half of the demo dispatch. The request-scoped session dies
    with the response, so this opens its own; execute_run's internal handlers
    map every failure to a terminal state, so a run can't be left 'running'
    unless the process itself dies mid-run."""
    session = SessionLocal()
    try:
        run = session.get(Run, run_id)
        if run is None:
            return
        execute_run(run, session)
    finally:
        session.close()
