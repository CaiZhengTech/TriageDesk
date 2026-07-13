"""Harness judge-gating tests. Live-run finding: eval_run b58804d6 judged 0 of
25 cases because the gate was `run.state == "completed"`, but almost every run
escalates by design (adverse-action rule, entitlement-evidence rule, model
conservatism) -- the judge grades reply quality/grounding, which is orthogonal
to the gate's auto-send decision, so it must fire on ANY drafted reply. No
live calls: run_ticket and judge_run are monkeypatched fakes."""
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from triagedesk.evals.harness import run_suite
from triagedesk.models import EvalCase, Span


class FakeCaseQuery:
    """Fake for session.query(EvalCase).order_by(...).all()."""
    def __init__(self, cases):
        self.cases = cases

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.cases


class FakeSpanQuery:
    """Fake for session.query(Span).filter_by(...).first() -- no classify span
    recorded for these fakes, so _classify_queue returns None."""
    def filter_by(self, **kwargs):
        return self

    def first(self):
        return None


class FakeSession:
    def __init__(self, cases):
        self.cases = cases
        self.added = []

    def query(self, model):
        if model is EvalCase:
            return FakeCaseQuery(self.cases)
        if model is Span:
            return FakeSpanQuery()
        raise AssertionError(f"unexpected query for {model}")

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass


def make_case(case_id, ticket_id):
    return SimpleNamespace(
        id=case_id, ticket_id=ticket_id, kind="representative",
        expected_outcome="escalate", expected_queue="IT Support",
    )


def make_run(state, final_reply):
    return SimpleNamespace(
        id=uuid.uuid4(), state=state, total_cost_usd=0.01,
        gate_signals={"retrieval_similarity": 0.4}, final_reply=final_reply,
        escalation_reason="low_confidence" if state == "escalated" else None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
    )


def fake_judge_verdict():
    return SimpleNamespace(verdict="pass", reason="grounded", rule_triggered=None)


def test_escalated_run_with_final_reply_is_judged(monkeypatch):
    """An escalated run with a drafted reply is exactly what a human reviewer
    reads -- it must be judged even though the gate did not auto-send it."""
    case = make_case(1, 101)
    run = make_run("escalated", "Please restart your VPN client.")
    session = FakeSession([case])

    monkeypatch.setattr(
        "triagedesk.evals.harness.run_ticket", lambda ticket_id, s: run
    )
    judge_calls = []

    def fake_judge_run(s, c, r):
        judge_calls.append((c, r))
        return fake_judge_verdict(), []

    monkeypatch.setattr("triagedesk.evals.judge.judge_run", fake_judge_run)

    run_suite(session, with_judge=True)

    assert len(judge_calls) == 1
    result = session.added[0]
    assert result.judge_verdict == "pass"
    assert result.judge_reason == "grounded"


def test_run_with_no_final_reply_is_not_judged(monkeypatch):
    """A failed run typically has no drafted reply -- nothing for a human
    reviewer to read, so nothing for the judge to grade."""
    case = make_case(2, 102)
    run = make_run("failed", None)
    session = FakeSession([case])

    monkeypatch.setattr(
        "triagedesk.evals.harness.run_ticket", lambda ticket_id, s: run
    )
    judge_calls = []

    def fake_judge_run(s, c, r):
        judge_calls.append((c, r))
        return fake_judge_verdict(), []

    monkeypatch.setattr("triagedesk.evals.judge.judge_run", fake_judge_run)

    run_suite(session, with_judge=True)

    assert judge_calls == []
    result = session.added[0]
    assert result.judge_verdict is None
