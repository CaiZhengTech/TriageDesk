"""judge_backfill unit tests (selection/skip/persist logic). No live calls --
judge_run is monkeypatched. Reuses fake-session patterns from test_harness.py
and test_judge.py."""
import uuid
from types import SimpleNamespace

import pytest

from triagedesk.evals.harness import JUDGE_BACKFILL_COST_CAP, SuiteCostExceeded, judge_backfill
from triagedesk.models import EvalCase, EvalResult, Run


class FakeResultQuery:
    """Fake for session.query(EvalResult).filter(...).all() -- the DB-level
    filter (eval_run_id match, judge_verdict IS NULL) is trusted SQLAlchemy;
    the fake returns whatever the test pre-selected as already matching."""
    def __init__(self, results):
        self.results = results

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.results


class FakeSession:
    def __init__(self, results, runs=None, cases=None):
        self.results = results
        self.runs = {r.id: r for r in (runs or [])}
        self.cases = {c.id: c for c in (cases or [])}
        self.committed = 0

    def query(self, model):
        if model is EvalResult:
            return FakeResultQuery(self.results)
        raise AssertionError(f"unexpected query for {model}")

    def get(self, model, id_):
        if model is Run:
            return self.runs.get(id_)
        if model is EvalCase:
            return self.cases.get(id_)
        return None

    def add(self, obj):
        pass

    def commit(self):
        self.committed += 1


def make_result(result_id, run_id, case_id=1):
    return SimpleNamespace(
        id=result_id, eval_run_id=uuid.uuid4(), case_id=case_id, run_id=run_id,
        judge_verdict=None, judge_reason=None, judge_rule_triggered=None,
    )


def make_run(run_id, final_reply):
    return SimpleNamespace(id=run_id, final_reply=final_reply)


def make_case(case_id=1):
    return SimpleNamespace(id=case_id, ticket_id=101)


def fake_judge_run_factory(verdict="pass", reason="grounded", rule=None, responses=None):
    def fake_judge_run(session, case, run):
        verdict_obj = SimpleNamespace(verdict=verdict, reason=reason, rule_triggered=rule)
        return verdict_obj, (responses or [])
    return fake_judge_run


def test_judges_rows_with_null_verdict_and_final_reply(monkeypatch):
    run_id = uuid.uuid4()
    result = make_result(1, run_id)
    session = FakeSession([result], runs=[make_run(run_id, "Please restart your VPN.")],
                          cases=[make_case()])
    monkeypatch.setattr("triagedesk.evals.judge.judge_run",
                        fake_judge_run_factory(verdict="pass", reason="grounded"))

    summary = judge_backfill(session, uuid.uuid4())

    assert summary["n_judged"] == 1
    assert summary["verdict_counts"] == {"pass": 1}
    assert result.judge_verdict == "pass"
    assert result.judge_reason == "grounded"


def test_skips_row_with_no_final_reply(monkeypatch):
    run_id = uuid.uuid4()
    result = make_result(1, run_id)
    session = FakeSession([result], runs=[make_run(run_id, None)], cases=[make_case()])
    calls = []

    def fake_judge_run(s, c, r):
        calls.append(1)
        return SimpleNamespace(verdict="pass", reason="", rule_triggered=None), []

    monkeypatch.setattr("triagedesk.evals.judge.judge_run", fake_judge_run)

    summary = judge_backfill(session, uuid.uuid4())

    assert calls == []
    assert summary["n_judged"] == 0
    assert result.judge_verdict is None


def test_skips_row_with_missing_run(monkeypatch):
    """run_id points to a run that no longer resolves -- skip, don't crash."""
    result = make_result(1, run_id=uuid.uuid4())
    session = FakeSession([result], runs=[], cases=[make_case()])
    calls = []

    def fake_judge_run(s, c, r):
        calls.append(1)
        return SimpleNamespace(verdict="pass", reason="", rule_triggered=None), []

    monkeypatch.setattr("triagedesk.evals.judge.judge_run", fake_judge_run)

    summary = judge_backfill(session, uuid.uuid4())

    assert calls == []
    assert summary["n_judged"] == 0


def test_idempotent_already_judged_rows_excluded_by_query():
    """The DB query itself excludes judge_verdict IS NOT NULL rows -- a
    session that returns none (because everything is already judged) must
    judge nothing and cost nothing."""
    session = FakeSession([])

    summary = judge_backfill(session, uuid.uuid4())

    assert summary == {"n_judged": 0, "verdict_counts": {}, "total_cost": 0.0}


def test_persists_all_three_judge_fields(monkeypatch):
    run_id = uuid.uuid4()
    result = make_result(1, run_id)
    session = FakeSession([result], runs=[make_run(run_id, "reply")], cases=[make_case()])
    monkeypatch.setattr(
        "triagedesk.evals.judge.judge_run",
        fake_judge_run_factory(verdict="needs_review", reason="ambiguous", rule="grounding"),
    )

    judge_backfill(session, uuid.uuid4())

    assert result.judge_verdict == "needs_review"
    assert result.judge_reason == "ambiguous"
    assert result.judge_rule_triggered == "grounding"


def test_counts_multiple_verdicts(monkeypatch):
    run_a, run_b = uuid.uuid4(), uuid.uuid4()
    result_a = make_result(1, run_a)
    result_b = make_result(2, run_b)
    session = FakeSession(
        [result_a, result_b],
        runs=[make_run(run_a, "reply a"), make_run(run_b, "reply b")],
        cases=[make_case()],
    )
    verdicts = iter(["pass", "fail"])

    def fake_judge_run(s, c, r):
        return SimpleNamespace(verdict=next(verdicts), reason="", rule_triggered=None), []

    monkeypatch.setattr("triagedesk.evals.judge.judge_run", fake_judge_run)

    summary = judge_backfill(session, uuid.uuid4())

    assert summary["n_judged"] == 2
    assert summary["verdict_counts"] == {"pass": 1, "fail": 1}


def test_respects_cost_cap(monkeypatch):
    """A judge response too expensive for the cap raises SuiteCostExceeded --
    same fail-closed idiom as run_suite's cost cap."""
    run_id = uuid.uuid4()
    result = make_result(1, run_id)
    session = FakeSession([result], runs=[make_run(run_id, "reply")], cases=[make_case()])

    expensive_response = SimpleNamespace(
        model="claude-sonnet-4-6",
        usage=SimpleNamespace(input_tokens=1_000_000, output_tokens=0,
                              cache_creation_input_tokens=0, cache_read_input_tokens=0),
    )

    def fake_judge_run(s, c, r):
        return SimpleNamespace(verdict="pass", reason="", rule_triggered=None), [expensive_response]

    monkeypatch.setattr("triagedesk.evals.judge.judge_run", fake_judge_run)

    with pytest.raises(SuiteCostExceeded):
        judge_backfill(session, uuid.uuid4(), cost_cap=0.01)


def test_default_cost_cap_is_fifty_cents():
    assert JUDGE_BACKFILL_COST_CAP == 0.50
