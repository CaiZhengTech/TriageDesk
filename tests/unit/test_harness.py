"""Harness judge-gating tests. Live-run finding: eval_run b58804d6 judged 0 of
25 cases because the gate was `run.state == "completed"`, but almost every run
escalates by design (adverse-action rule, entitlement-evidence rule, model
conservatism) -- the judge grades reply quality/grounding, which is orthogonal
to the gate's auto-send decision, so it must fire on ANY drafted reply. No
live calls: run_ticket and judge_run are monkeypatched fakes."""
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from triagedesk.evals.harness import run_pool, run_suite
from triagedesk.models import EvalCase, Span


class FakeCaseQuery:
    """Fake for session.query(EvalCase).filter(...).order_by(...).all() --
    DB-level filtering is trusted SQLAlchemy (same convention as
    test_calibration.py's FakeQuery): .filter() is a no-op passthrough, the
    fake just returns whatever the test pre-loaded."""
    def __init__(self, cases):
        self.cases = cases

    def filter(self, *args, **kwargs):
        return self

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


def make_case(case_id, ticket_id, kind="representative", expected_escalation_reason=None):
    return SimpleNamespace(
        id=case_id, ticket_id=ticket_id, kind=kind,
        expected_outcome="escalate", expected_queue="IT Support",
        expected_escalation_reason=expected_escalation_reason,
    )


def make_run(state, final_reply, total_cost_usd=0.01, escalation_reason=None):
    return SimpleNamespace(
        id=uuid.uuid4(), state=state, total_cost_usd=total_cost_usd,
        gate_signals={"retrieval_similarity": 0.4}, final_reply=final_reply,
        escalation_reason=(escalation_reason
                            or ("low_confidence" if state == "escalated" else None)),
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


# --------------------------------------------------------------------- run_pool
# run_pool is the calibration pool's (issue #11) counterpart to run_suite:
# same run-then-judge shape, but scoped to kind="calibration" cases and kept
# deliberately separate so a pool run never feeds into the golden summary.

def test_run_pool_only_queries_calibration_kind_cases(monkeypatch):
    """FakeCaseQuery.filter() is a no-op (DB-level filtering is trusted
    SQLAlchemy, per the module convention) -- this test locks in that
    run_pool calls .filter() at all, not that the fake enforces it. The
    real-DB proof lives in the integration test for the exclusion rule."""
    case = make_case(1, 201, kind="calibration")
    run = make_run("completed", "Refund issued.")
    session = FakeSession([case])
    monkeypatch.setattr("triagedesk.evals.harness.run_ticket", lambda tid, s: run)
    monkeypatch.setattr(
        "triagedesk.evals.judge.judge_run",
        lambda s, c, r: (fake_judge_verdict(), []),
    )

    summary = run_pool(session)

    assert summary["n_run"] == 1
    assert summary["n_judged"] == 1
    result = session.added[0]
    assert result.case_id == 1
    assert result.judge_verdict == "pass"


def test_run_pool_tags_results_with_a_fresh_eval_run_id(monkeypatch):
    """Pool results are tagged to their own eval_run_id, distinct from any
    golden-set run_suite() call, so provenance is unambiguous."""
    case1, case2 = make_case(1, 201, kind="calibration"), make_case(2, 202, kind="calibration")
    session = FakeSession([case1, case2])

    def fake_run_ticket(ticket_id, s):
        return make_run("completed", f"reply for {ticket_id}")

    monkeypatch.setattr("triagedesk.evals.harness.run_ticket", fake_run_ticket)
    monkeypatch.setattr(
        "triagedesk.evals.judge.judge_run",
        lambda s, c, r: (fake_judge_verdict(), []),
    )

    summary = run_pool(session)

    eval_run_ids = {r.eval_run_id for r in session.added}
    assert eval_run_ids == {summary["eval_run_id"]}
    assert len(eval_run_ids) == 1


def test_run_pool_skips_judging_when_no_final_reply(monkeypatch):
    case = make_case(1, 201, kind="calibration")
    run = make_run("failed", None)
    session = FakeSession([case])
    monkeypatch.setattr("triagedesk.evals.harness.run_ticket", lambda tid, s: run)
    judge_calls = []

    def fake_judge_run(s, c, r):
        judge_calls.append((c, r))
        return fake_judge_verdict(), []

    monkeypatch.setattr("triagedesk.evals.judge.judge_run", fake_judge_run)

    summary = run_pool(session)

    assert judge_calls == []
    assert summary["n_judged"] == 0
    result = session.added[0]
    assert result.judge_verdict is None


# --------------------------------------------------------- metric integrity (issue #45)
# Hardening Task 1: reason-aware adversarial catch, cost-cap pre-check, judge
# cost clarity. See docs/week-2-evals/HARDENING-PLAN.md Task 1.

def test_run_suite_carries_escalation_reason_into_summary(monkeypatch):
    """An adversarial case escalated for the WRONG reason (expected
    precheck_injection, observed agent_requested_human -- model conservatism
    caught it, not the intended precheck layer) must not count toward the
    reason-aware adversarial_catch_rate, even though it did escalate."""
    case = make_case(1, 101, kind="adversarial",
                      expected_escalation_reason="precheck_injection")
    run = make_run("escalated", "I can't help with that, escalating to a human.",
                    escalation_reason="agent_requested_human")
    session = FakeSession([case])
    monkeypatch.setattr("triagedesk.evals.harness.run_ticket", lambda tid, s: run)

    _, summary = run_suite(session, with_judge=False)

    assert summary["adversarial_catch_rate"] == 0.0
    assert summary["adversarial_escalate_rate"] == 1.0


def test_run_suite_cap_precheck_stops_before_dispatching_breaching_case(monkeypatch):
    """acceptance criterion 2: the cap is a ceiling, not a tripwire. 3 cases,
    each costing exactly PER_RUN_CAP; cost_cap is set so case 3 would breach
    it if dispatched -- the pre-check must raise BEFORE run_ticket is called
    for case 3, not after (the existing post-hoc check stays as a backstop
    for costs that aren't known in advance)."""
    from triagedesk.evals.harness import PER_RUN_CAP, SuiteCostExceeded

    cases = [make_case(i, 100 + i) for i in (1, 2, 3)]
    session = FakeSession(cases)
    dispatched = []

    def fake_run_ticket(ticket_id, s):
        dispatched.append(ticket_id)
        return make_run("completed", None, total_cost_usd=PER_RUN_CAP)

    monkeypatch.setattr("triagedesk.evals.harness.run_ticket", fake_run_ticket)

    # After 2 cases: total_cost == 2 * PER_RUN_CAP. Before case 3:
    # total_cost + PER_RUN_CAP == 3 * PER_RUN_CAP, which must exceed cap.
    cap = 2 * PER_RUN_CAP + (PER_RUN_CAP / 2)

    with pytest.raises(SuiteCostExceeded):
        run_suite(session, cost_cap=cap, with_judge=False)

    assert dispatched == [101, 102]  # case 3's ticket_id (103) never dispatched


def test_run_suite_surfaces_judge_cost_total_in_summary(monkeypatch):
    """acceptance criterion 3: judge call cost (currently only accumulated
    into the cap-check variable) must surface in the summary, separate from
    pipeline-only cost_per_run/cost_total."""
    case = make_case(1, 101)
    run = make_run("completed", "Refund issued.", total_cost_usd=0.01)
    session = FakeSession([case])
    monkeypatch.setattr("triagedesk.evals.harness.run_ticket", lambda tid, s: run)

    judge_response = SimpleNamespace(
        model="claude-sonnet-4-6",
        usage=SimpleNamespace(input_tokens=1000, output_tokens=100,
                              cache_creation_input_tokens=0, cache_read_input_tokens=0),
    )
    monkeypatch.setattr(
        "triagedesk.evals.judge.judge_run",
        lambda s, c, r: (fake_judge_verdict(), [judge_response]),
    )

    _, summary = run_suite(session, with_judge=True)

    expected_judge_cost = 1000 * 3.00 / 1_000_000 + 100 * 15.00 / 1_000_000
    assert summary["judge_cost_total"] == pytest.approx(expected_judge_cost)
    assert summary["cost_total"] == pytest.approx(0.01)  # pipeline-only, unaffected


def test_run_pool_respects_cost_cap(monkeypatch):
    from triagedesk.evals.harness import SuiteCostExceeded

    case = make_case(1, 201, kind="calibration")
    expensive_run = SimpleNamespace(
        id=uuid.uuid4(), state="completed", total_cost_usd=5.00,
        gate_signals={}, final_reply="reply",
        escalation_reason=None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
    )
    session = FakeSession([case])
    monkeypatch.setattr("triagedesk.evals.harness.run_ticket", lambda tid, s: expensive_run)

    with pytest.raises(SuiteCostExceeded):
        run_pool(session, cost_cap=0.10)
