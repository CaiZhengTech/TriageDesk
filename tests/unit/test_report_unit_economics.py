"""The DB->metric adapter for cost per accepted task (#79).

The arithmetic is covered in test_unit_economics.py. What this file pins is the
translation from database rows, where the interesting mistakes live: joining
review_decisions wrong, or letting in-flight runs skew a metric depending on
when you happened to query.
"""

from types import SimpleNamespace
from uuid import uuid4

from scripts.report_unit_economics import load_runs


class _FakeSession:
    """Returns the two SELECTs load_runs issues, in order: review_decision
    run_ids, then run rows."""

    def __init__(self, reviewed_ids, run_rows):
        self._returns = [
            [(r,) for r in reviewed_ids],
            run_rows,
        ]

    def execute(self, _stmt):
        return SimpleNamespace(all=lambda: self._returns.pop(0))


def test_marks_only_runs_that_have_a_review_decision():
    a, b = uuid4(), uuid4()
    runs = load_runs(_FakeSession(
        reviewed_ids=[a],
        run_rows=[(a, "escalated", 0.03), (b, "escalated", 0.04)],
    ))
    by_reviewed = {r.was_reviewed for r in runs}
    assert by_reviewed == {True, False}
    assert next(r for r in runs if r.was_reviewed).total_cost_usd == 0.03


def test_null_cost_is_treated_as_zero_not_a_crash():
    """A run that died before recording cost has total_cost_usd NULL. It should
    contribute zero spend, not raise -- the #71 outage produced exactly these
    rows (failed at precheck, cost never written)."""
    runs = load_runs(_FakeSession([], [(uuid4(), "failed", None)]))
    assert runs[0].total_cost_usd == 0.0


def test_running_rows_are_passed_through_for_the_metric_to_drop():
    """load_runs does not filter; unit_economics() owns the terminal-state rule
    so there is exactly one place that decides what counts."""
    runs = load_runs(_FakeSession([], [(uuid4(), "running", 0.01)]))
    assert [r.state for r in runs] == ["running"]
