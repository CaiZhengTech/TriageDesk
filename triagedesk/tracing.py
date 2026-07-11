"""Span writer, run state machine, and fail-closed cost accounting.

Spans are written incrementally: the row is inserted (and committed) when a
stage starts, and updated when it ends — a crash mid-run leaves partial
evidence in the DB. Attribute keys follow OTel GenAI semantic conventions
(gen_ai.*) but live in a Postgres JSONB column; no OTel exporter (deliberate cut).
"""

from contextlib import contextmanager
from datetime import UTC, datetime

from triagedesk.config import settings
from triagedesk.models import RUN_STATES, Run, Span

# USD per 1M tokens. Adding a model here is a deliberate, reviewed act —
# anything absent fails closed.
PRICES_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,  # 1.25x input
        "cache_read": 0.30,   # 0.1x input
    },
}


class CostUnknownError(Exception):
    """Cost could not be computed — treated as a budget breach (fail closed)."""


class BudgetExceededError(Exception):
    pass


class InvalidTransitionError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


def compute_cost(model: str, usage) -> float:
    prices = PRICES_PER_MTOK.get(model)
    if prices is None:
        raise CostUnknownError(f"no price entry for model {model!r}")
    inp = getattr(usage, "input_tokens", None)
    out = getattr(usage, "output_tokens", None)
    if inp is None or out is None:
        raise CostUnknownError(f"usage missing token counts: {usage!r}")
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (
        inp * prices["input"]
        + out * prices["output"]
        + cache_write * prices["cache_write"]
        + cache_read * prices["cache_read"]
    ) / 1_000_000


def finish_run(session, run: Run, state: str, reason: str | None = None, resolution=None) -> None:
    if run.state != "running":
        raise InvalidTransitionError(f"run already terminal: {run.state}")
    if state not in RUN_STATES or state == "running":
        raise InvalidTransitionError(f"illegal target state: {state}")
    run.state = state
    run.escalation_reason = reason
    run.finished_at = _utcnow()
    if resolution is not None:
        run.final_reply = resolution.customer_reply
        run.internal_rationale = resolution.internal_rationale
    session.commit()


class RunTracer:
    def __init__(self, session, run: Run):
        self.session = session
        self.run = run

    @contextmanager
    def span(self, name: str):
        s = Span(run_id=self.run.id, name=name, status="started",
                 started_at=_utcnow(), attributes={})
        self.session.add(s)
        self.session.commit()  # incremental write: exists before the stage runs
        try:
            yield s
            if s.status == "started":
                s.status = "ok"
        except Exception:
            s.status = "error"
            raise
        finally:
            s.ended_at = _utcnow()
            self.session.commit()

    def set_attributes(self, span: Span, **attrs) -> None:
        span.attributes = {**(span.attributes or {}), **attrs}
        self.session.commit()

    def record_llm_usage(self, span: Span, response) -> None:
        """Record gen_ai.* usage attrs and enforce the cost cap. Fail closed."""
        cost = compute_cost(response.model, response.usage)  # raises CostUnknownError
        span.cost_usd = (span.cost_usd or 0.0) + cost
        prev = span.attributes or {}
        span.attributes = {
            **prev,
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": self.run.model,
            "gen_ai.response.model": response.model,
            "gen_ai.usage.input_tokens": (prev.get("gen_ai.usage.input_tokens", 0)
                                          + response.usage.input_tokens),
            "gen_ai.usage.output_tokens": (prev.get("gen_ai.usage.output_tokens", 0)
                                           + response.usage.output_tokens),
        }
        self.run.total_cost_usd = (self.run.total_cost_usd or 0.0) + cost
        self.session.commit()
        if self.run.total_cost_usd > settings.cost_cap_usd:
            raise BudgetExceededError(
                f"run cost ${self.run.total_cost_usd:.4f} exceeds cap ${settings.cost_cap_usd}"
            )
