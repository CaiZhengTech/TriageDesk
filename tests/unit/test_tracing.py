from types import SimpleNamespace

import pytest

from triagedesk.models import Run
from triagedesk.tracing import (
    BudgetExceededError,
    CostUnknownError,
    InvalidTransitionError,
    compute_cost,
    finish_run,
)


def usage(inp, out):
    return SimpleNamespace(
        input_tokens=inp,
        output_tokens=out,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


class FakeSession:
    def add(self, obj): ...
    def commit(self): ...


def test_compute_cost_sonnet():
    # 1000 in @ $3/M + 1000 out @ $15/M = 0.003 + 0.015
    assert compute_cost("claude-sonnet-4-6", usage(1000, 1000)) == pytest.approx(0.018)


def test_unknown_model_fails_closed():
    with pytest.raises(CostUnknownError):
        compute_cost("mystery-model-9000", usage(10, 10))


def test_missing_usage_fails_closed():
    with pytest.raises(CostUnknownError):
        compute_cost("claude-sonnet-4-6", SimpleNamespace(input_tokens=None, output_tokens=5))


def test_finish_run_sets_terminal_state():
    run = Run(state="running", prompt_version="w1-v1", model="claude-sonnet-4-6", ticket_id=1)
    finish_run(FakeSession(), run, "escalated", reason="low_confidence")
    assert run.state == "escalated"
    assert run.escalation_reason == "low_confidence"
    assert run.finished_at is not None


def test_finish_run_rejects_double_transition():
    run = Run(state="completed", prompt_version="w1-v1", model="claude-sonnet-4-6", ticket_id=1)
    with pytest.raises(InvalidTransitionError):
        finish_run(FakeSession(), run, "failed")


def test_finish_run_rejects_bogus_state():
    run = Run(state="running", prompt_version="w1-v1", model="claude-sonnet-4-6", ticket_id=1)
    with pytest.raises(InvalidTransitionError):
        finish_run(FakeSession(), run, "paused")


def test_budget_breach_raises(monkeypatch):
    from triagedesk import tracing
    from triagedesk.models import Span

    monkeypatch.setattr(tracing.settings, "cost_cap_usd", 0.01)
    run = Run(state="running", prompt_version="w1-v1", model="claude-sonnet-4-6",
              ticket_id=1, total_cost_usd=0.0)
    tracer = tracing.RunTracer(FakeSession(), run)
    span = Span(run_id=run.id, name="act", started_at=None, attributes={})
    response = SimpleNamespace(model="claude-sonnet-4-6", usage=usage(2000, 2000))
    with pytest.raises(BudgetExceededError):
        tracer.record_llm_usage(span, response)  # $0.036 > $0.01 cap


def test_budget_accumulates_across_calls(monkeypatch):
    from triagedesk import tracing
    from triagedesk.models import Span

    monkeypatch.setattr(tracing.settings, "cost_cap_usd", 0.03)
    run = Run(state="running", prompt_version="w1-v1", model="claude-sonnet-4-6",
              ticket_id=1, total_cost_usd=0.0)
    tracer = tracing.RunTracer(FakeSession(), run)

    # First call: $0.018, under cap of $0.03 — should not raise
    span1 = Span(run_id=run.id, name="act", started_at=None, attributes={})
    response1 = SimpleNamespace(model="claude-sonnet-4-6", usage=usage(1000, 1000))
    tracer.record_llm_usage(span1, response1)
    assert run.total_cost_usd == pytest.approx(0.018)

    # Second call: another $0.018, total $0.036 > $0.03 cap — should raise
    span2 = Span(run_id=run.id, name="act", started_at=None, attributes={})
    response2 = SimpleNamespace(model="claude-sonnet-4-6", usage=usage(1000, 1000))
    with pytest.raises(BudgetExceededError):
        tracer.record_llm_usage(span2, response2)
    assert run.total_cost_usd == pytest.approx(0.036)
