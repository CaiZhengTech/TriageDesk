"""The trivial baseline every headline metric must be compared against (#68).

A metric that a one-line `return "escalate"` stub reproduces is not evidence the
pipeline does anything — it is evidence about the golden set's base rate. This
module computes what that stub scores, so the comparison is published rather
than discovered by an interviewer.

The baseline is derived by running synthetic stub results through the REAL
`summarize()`. It is never hand-written: a hand-copied number drifts silently
the moment the golden set or a metric definition changes, which is exactly the
class of staleness that produced #75.
"""

import json
from pathlib import Path

from triagedesk.evals.null_baseline import (
    COLLAPSING_METRICS,
    compare_to_null,
    null_baseline,
    stub_results,
)


def test_stub_covers_the_whole_golden_set():
    """25 cases: 20 representative + 5 adversarial."""
    results = stub_results()
    assert len(results) == 25
    assert sum(c.kind == "adversarial" for c in results) == 5
    assert sum(c.kind == "representative" for c in results) == 20


def test_stub_escalates_everything_and_reports_no_reason():
    """This IS the stub: one branch, no inputs consulted. It cannot name a
    catching layer because it never looked at the ticket."""
    for c in stub_results():
        assert c.predicted_outcome == "escalate"
        assert c.escalation_reason is None
        assert c.predicted_queue is None


def test_baseline_is_derived_through_the_real_summarize():
    """Guards against the numbers being hand-copied and drifting. If the metric
    definitions change, the baseline changes with them automatically."""
    b = null_baseline()
    assert set(b) >= {
        "routing_accuracy", "escalation_precision", "escalation_recall",
        "adversarial_catch_rate", "adversarial_catch_rate_strict",
        "adversarial_escalate_rate", "n_cases",
    }
    assert b["n_cases"] == 25


def test_escalation_recall_collapses_to_the_stub():
    """The stub escalates everything, so it never misses an expected escalation.
    Recall 1.00 is therefore free — it says nothing about the pipeline."""
    assert null_baseline()["escalation_recall"] == 1.0


def test_escalation_precision_is_just_the_base_rate():
    """22 of 25 golden cases expect escalation, so a stub scores 22/25 = 0.88 —
    the corpus's base rate wearing a metric's name."""
    assert null_baseline()["escalation_precision"] == 22 / 25


def test_outcome_only_adversarial_rate_collapses():
    """adversarial_escalate_rate counts any escalation regardless of layer, so
    the stub gets a perfect score."""
    assert null_baseline()["adversarial_escalate_rate"] == 1.0


def test_reason_aware_catch_rates_do_NOT_collapse():
    """The Week-2.5 hardening's actual payoff, and the correction to this
    issue's first framing.

    `adversarial_catch_rate` only counts a case as caught when the observed
    escalation_reason matches the layer that was supposed to catch it. A stub
    has no reason to report, so it scores ZERO — these two metrics genuinely
    distinguish the pipeline from the trivial baseline, and were designed in
    Week 2.5 to close exactly this tautology."""
    b = null_baseline()
    assert b["adversarial_catch_rate"] == 0.0
    assert b["adversarial_catch_rate_strict"] == 0.0


def test_routing_accuracy_does_not_collapse():
    """The stub never predicts a queue, so it cannot route anything correctly."""
    assert null_baseline()["routing_accuracy"] == 0.0


def test_collapsing_metrics_is_exactly_the_set_the_stub_matches():
    """The published list must be derived, not asserted. Every metric named as
    collapsing must actually be one the stub reproduces."""
    b = null_baseline()
    for metric in COLLAPSING_METRICS:
        assert b[metric] > 0.0, f"{metric} listed as collapsing but stub scores 0"


def test_compare_flags_a_metric_that_fails_to_beat_the_null():
    """The assertion the harness needs: a real summary whose headline number
    merely ties the stub is reported as NOT DISTINGUISHING, automatically."""
    verdict = compare_to_null({
        "escalation_recall": 1.0,          # ties the stub
        "escalation_precision": 0.88,      # ties the stub
        "adversarial_catch_rate": 1.0,     # stub scores 0.0 — real signal
        "routing_accuracy": 0.29,          # stub scores 0.0 — real signal
    })
    assert verdict["escalation_recall"]["distinguishing"] is False
    assert verdict["escalation_precision"]["distinguishing"] is False
    assert verdict["adversarial_catch_rate"]["distinguishing"] is True
    assert verdict["routing_accuracy"]["distinguishing"] is True


def test_compare_ignores_metrics_with_no_null_equivalent():
    """Cost and latency have no meaningful stub comparison — a stub that does
    no work is trivially cheapest. Silently skipped rather than reported as a
    win the pipeline 'loses'."""
    verdict = compare_to_null({"cost_per_run": 0.03, "latency_p50_ms": 31000})
    assert verdict == {}


def test_committed_artifact_matches_the_derived_baseline():
    """results/null-baseline.json is published beside the headline numbers, so
    it must not drift from what the code derives. Regenerate with
    `python -m scripts.build_null_baseline`."""
    path = Path("results/null-baseline.json")
    assert path.exists(), "run: python -m scripts.build_null_baseline"
    committed = json.loads(path.read_text())["null_baseline"]
    derived = null_baseline()
    for metric, value in committed.items():
        assert derived[metric] == value, (
            f"{metric}: committed {value} != derived {derived[metric]} — "
            "regenerate results/null-baseline.json"
        )
