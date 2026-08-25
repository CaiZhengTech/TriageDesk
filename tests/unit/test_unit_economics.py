"""Cost per accepted task — the metric the literature insists on (#79).

Per-token cost is misleading when a cheaper model sends more work to humans:
a model can cost 80% less per call and still lose money if it triples the
escalation rate. The honest denominator is *accepted tasks*, and the honest
numerator includes the labour an escalation creates.

TriageDesk can compute this because it has a real review queue — most
portfolio projects cannot. These tests pin the arithmetic and, more
importantly, pin the honesty properties: the labour rate is an ASSUMPTION and
must be carried in the output, never buried as a constant.
"""

import pytest

from triagedesk.evals.unit_economics import (
    DEFAULT_REVIEW_MINUTES,
    DEFAULT_REVIEWER_HOURLY_USD,
    RunRecord,
    unit_economics,
)


def _run(state, cost, reviewed=False):
    return RunRecord(state=state, total_cost_usd=cost, was_reviewed=reviewed)


def test_no_runs_is_not_a_division_by_zero():
    e = unit_economics([])
    assert e["n_runs"] == 0
    assert e["cost_per_accepted_task"] is None
    assert e["api_cost_per_run"] is None


def test_autoresolve_only_costs_just_api_spend():
    """Nothing escalated, so no labour. Cost per accepted task == API cost."""
    e = unit_economics([_run("completed", 0.03), _run("completed", 0.05)])
    assert e["n_accepted"] == 2
    assert e["labour_cost_usd"] == 0.0
    assert e["cost_per_accepted_task"] == pytest.approx(0.04)


def test_escalations_add_labour_at_the_stated_rate():
    """One auto-resolve + one escalation. The escalation costs API spend AND a
    reviewer's time; both land in the numerator, but only the auto-resolve
    counts as accepted."""
    e = unit_economics(
        [_run("completed", 0.03), _run("escalated", 0.03)],
        review_minutes=6.0,
        reviewer_hourly_usd=30.0,
    )
    assert e["n_accepted"] == 1
    assert e["n_escalated"] == 1
    assert e["labour_cost_usd"] == pytest.approx(3.0)   # 6 min at $30/h
    assert e["total_cost_usd"] == pytest.approx(3.06)
    assert e["cost_per_accepted_task"] == pytest.approx(3.06)


def test_labour_dominates_and_that_is_the_point():
    """The finding this metric exists to surface: at any plausible wage, one
    escalation costs two orders of magnitude more than one API call. Optimizing
    per-token cost while ignoring escalation rate optimizes the wrong term.

    At the defaults a review is $3.00 against ~$0.03 of API spend, so the ratio
    is ~100x. Asserted as a floor of 50x rather than a point value: the claim is
    "labour dwarfs tokens", which must survive someone plausibly re-estimating
    the wage or the review time, not just these exact constants."""
    e = unit_economics([_run("escalated", 0.03)] * 10,
                       review_minutes=6.0, reviewer_hourly_usd=30.0)
    assert e["labour_cost_usd"] >= 50 * e["api_cost_usd"]


def test_failed_runs_are_neither_accepted_nor_free():
    """A failed run produced no answer, so it cannot be 'accepted' — but it may
    still have spent money before failing, and that spend is real. Counting it
    as accepted would flatter the metric; ignoring its cost would too."""
    e = unit_economics([_run("completed", 0.03), _run("failed", 0.01)])
    assert e["n_accepted"] == 1
    assert e["n_failed"] == 1
    assert e["api_cost_usd"] == pytest.approx(0.04)
    assert e["cost_per_accepted_task"] == pytest.approx(0.04)


def test_running_runs_are_excluded_entirely():
    """A run still in flight has no outcome yet. Including it would make the
    metric depend on when you happened to query."""
    e = unit_economics([_run("completed", 0.03), _run("running", 0.01)])
    assert e["n_runs"] == 1
    assert e["api_cost_usd"] == pytest.approx(0.03)


def test_assumptions_are_carried_in_the_output():
    """The honesty property. The labour rate is an assumption that drives the
    entire result, so it must travel with the number rather than hiding in a
    constant someone has to go read."""
    e = unit_economics([_run("completed", 0.03)],
                       review_minutes=9.0, reviewer_hourly_usd=42.0)
    assert e["assumptions"]["review_minutes"] == 9.0
    assert e["assumptions"]["reviewer_hourly_usd"] == 42.0
    assert "assumption" in e["assumptions"]["_note"].lower()


def test_defaults_are_declared_not_invented_silently():
    e = unit_economics([_run("completed", 0.03)])
    assert e["assumptions"]["review_minutes"] == DEFAULT_REVIEW_MINUTES
    assert e["assumptions"]["reviewer_hourly_usd"] == DEFAULT_REVIEWER_HOURLY_USD


def test_deflection_rate_is_reported_and_bounded():
    e = unit_economics([_run("completed", 0.03)] * 3 + [_run("escalated", 0.03)])
    assert e["deflection_rate"] == pytest.approx(0.75)


def test_break_even_deflection_is_reported():
    """The decision-useful number: what fraction must auto-resolve before the
    system is cheaper than sending every ticket to a human."""
    e = unit_economics([_run("completed", 0.03), _run("escalated", 0.03)],
                       review_minutes=6.0, reviewer_hourly_usd=30.0)
    assert 0.0 < e["break_even_deflection_rate"] < 0.05


def test_reviewed_escalations_are_counted_separately():
    """`was_reviewed` distinguishes escalations a human actually actioned from
    ones still sitting in the queue. Both cost labour eventually; only the
    reviewed ones have provably cost it yet."""
    e = unit_economics([_run("escalated", 0.03, reviewed=True),
                        _run("escalated", 0.03, reviewed=False)])
    assert e["n_escalated"] == 2
    assert e["n_reviewed"] == 1
