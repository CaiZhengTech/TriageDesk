"""Demo-abuse protection (issue #16): the seeded ticket pool, the per-IP rate
limiter, and the daily spend-cap check. All three guard `POST /api/demo/run`
in `triagedesk/app.py` and run BEFORE the pipeline is invoked — a blocked
request must never call `run_ticket`.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from triagedesk.models import Run, Ticket


def list_demo_pool(db: Session) -> dict:
    """Seeded pool only (`tickets.source == 'demo'`) — the pool is the only
    ticket source the demo ever exposes; no free-text ticket entry anywhere."""
    rows = db.execute(
        select(Ticket.id, Ticket.subject)
        .where(Ticket.source == "demo")
        .order_by(Ticket.id)
    ).all()
    return {"tickets": [{"id": r.id, "subject": r.subject} for r in rows]}


def get_demo_ticket(db: Session, ticket_id: int) -> Ticket | None:
    """The pool-only rule: a ticket id only counts if it exists AND is
    `source == 'demo'` — a real (kaggle) ticket id must 404 here too."""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.source != "demo":
        return None
    return ticket


class RateLimiter:
    """In-memory fixed-window per-IP rate limiter.

    Single-instance limitation (documented, not fixed this week): state lives
    in a process-local dict, so a multi-instance deploy would let each
    instance track its own window independently — a caller could get roughly
    `limit * instance_count` requests through per hour instead of `limit`.
    Fine for a single-replica Railway demo deploy; a real fix would move this
    state to a shared store (e.g. Redis) behind the same `check()` interface.

    `now` is always passed in by the caller (never read from `time.time()` /
    `datetime.now()` internally) so tests can drive window resets with a fake
    clock instead of sleeping.
    """

    def __init__(self) -> None:
        self._windows: dict[str, tuple[int, datetime]] = {}

    def check(self, key: str, now: datetime, limit: int) -> bool:
        """True (and records the attempt) if `key` is still under `limit` for
        the current hour-long window starting at its first request; False if
        the window's count has already reached `limit`."""
        count, window_start = self._windows.get(key, (0, now))
        if now - window_start >= timedelta(hours=1):
            count, window_start = 0, now
        if count >= limit:
            self._windows[key] = (count, window_start)
            return False
        self._windows[key] = (count + 1, window_start)
        return True

    def reset(self) -> None:
        """Test-only escape hatch: wipes all tracked windows so route tests
        sharing TestClient's fixed host don't leak state between cases."""
        self._windows.clear()


def _utc_day_window(now: datetime) -> tuple[datetime, datetime]:
    """[day_start, day_end) as NAIVE datetimes, matching how `runs.created_at`
    is actually stored (server-default -> timezone-naive, but written as UTC
    by convention — see docs/00-spec/DATA-SCHEMA.md). `now` may be naive or
    aware; normalized to naive UTC first so the comparison lines up with the
    column directly instead of comparing an aware value against a naive one
    (the same tz mismatch console_queries.py's latency calc had to guard)."""
    naive_now = now.astimezone(UTC).replace(tzinfo=None) if now.tzinfo else now
    day_start = naive_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start, day_start + timedelta(days=1)


def daily_cap_would_be_exceeded(
    db: Session, now: datetime, daily_cap_usd: float, per_run_cost_cap_usd: float
) -> bool:
    """True if today's (UTC) demo spend plus one more run at the per-run cost
    cap would exceed `daily_cap_usd`.

    A pre-check against the `runs` table, not a post-hoc counter — no
    dedicated counter table, per the plan. Fail closed: if the sum can't be
    computed (query raises), treat it as a breach rather than let a demo run
    through with unknown cost exposure.
    """
    day_start, day_end = _utc_day_window(now)
    try:
        spent = db.scalar(
            select(func.coalesce(func.sum(Run.total_cost_usd), 0.0)).where(
                Run.created_at >= day_start, Run.created_at < day_end
            )
        )
    except Exception:
        return True
    if spent is None:
        return True
    return spent + per_run_cost_cap_usd > daily_cap_usd
