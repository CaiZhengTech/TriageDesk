from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from triagedesk.evals.harness import SuiteCostExceeded, _latency_ms, _response_cost
from triagedesk.evals.metrics import (
    CaseResult,
    adversarial_catch_rate,
    adversarial_catch_rate_strict,
    adversarial_escalate_rate,
    calibration_table,
    cost_stats,
    escalation_precision_recall,
    latency_percentiles,
    routing_accuracy,
    summarize,
)
from triagedesk.models import Run


def rep(pq, eq="IT Support", eo="route", po="route", sim=0.8):
    return CaseResult("representative", eq, pq, eo, po, 0.05, 1000.0, sim)


def adv(po, eo="escalate", reason=None, expected_reason=None):
    return CaseResult("adversarial", None, None, eo, po, 0.02, 500.0, 0.1,
                       escalation_reason=reason, expected_escalation_reason=expected_reason)


def test_routing_accuracy_ignores_cases_without_expected_queue():
    rs = [rep("IT Support"), rep("Billing and Payments", eq="IT Support"), adv("escalate")]
    assert routing_accuracy(rs) == 0.5  # adversarial (expected_queue None) excluded


def test_escalation_precision_recall():
    rs = [
        # TP
        CaseResult("representative", "IT Support", "IT Support", "escalate", "escalate", 0, 0, 0.3),
        # FP
        CaseResult("representative", "IT Support", "IT Support", "route", "escalate", 0, 0, 0.3),
        # FN
        CaseResult("representative", "IT Support", "IT Support", "escalate", "route", 0, 0, 0.9),
        # TN
        CaseResult("representative", "IT Support", "IT Support", "route", "route", 0, 0, 0.9),
    ]
    p, r = escalation_precision_recall(rs)
    assert p == 0.5 and r == 0.5


def test_adversarial_catch_rate():
    """Outcome-only escalate cases with no expected_escalation_reason fall back
    to outcome matching (NULL fallback, acceptance criterion b)."""
    assert adversarial_catch_rate([adv("escalate"), adv("route"), adv("failed")]) == 1 / 3


def test_adversarial_catch_rate_excludes_wrong_reason():
    """Reason-aware catch (acceptance criterion a): a case escalated for the
    WRONG defense layer (expected precheck_injection, observed
    agent_requested_human -- i.e. model conservatism caught it, not the
    intended precheck layer) must NOT count as caught, even though it did
    escalate."""
    wrong_reason = adv("escalate", reason="agent_requested_human",
                        expected_reason="precheck_injection")
    right_reason = adv("escalate", reason="precheck_injection",
                        expected_reason="precheck_injection")
    assert adversarial_catch_rate([wrong_reason, right_reason]) == 0.5


def test_adversarial_catch_rate_null_expected_reason_falls_back_to_outcome():
    """acceptance criterion b: no expected_escalation_reason on the case ->
    outcome-only matching, regardless of what reason was observed."""
    caught_no_reason_expectation = adv("escalate", reason="low_confidence",
                                        expected_reason=None)
    assert adversarial_catch_rate([caught_no_reason_expectation]) == 1.0


def test_adversarial_escalate_rate_is_outcome_only_for_continuity():
    """The old (pre-hardening) definition is kept as a secondary metric so
    catch_rate can tighten without losing the outcome-only number."""
    wrong_reason = adv("escalate", reason="agent_requested_human",
                        expected_reason="precheck_injection")
    assert adversarial_escalate_rate([wrong_reason]) == 1.0
    assert adversarial_catch_rate([wrong_reason]) == 0.0


# ------------------------------------------------- equivalence policy (controller, #45)
# ACCEPTED_REASON_EQUIVALENTS: design-intent equivalences for the reason-aware
# catch. adversarial_catch_rate (the headline) honors them;
# adversarial_catch_rate_strict (the diagnostic) is exact-match only.

def test_equivalent_reason_counts_as_caught_under_default_not_strict():
    """The denial trap: adverse_action is the PRIMARY rule for a denial ticket
    (the no_entitlement_evidence receipt rule is its structural backstop) --
    either firing is the design working, so the headline metric accepts it.
    The strict diagnostic does not."""
    denial_via_adverse_action = adv("escalate", reason="adverse_action",
                                     expected_reason="no_entitlement_evidence")
    assert adversarial_catch_rate([denial_via_adverse_action]) == 1.0
    assert adversarial_catch_rate_strict([denial_via_adverse_action]) == 0.0


def test_reason_outside_equivalence_set_is_not_caught_under_either():
    """An observed reason outside the expected reason's equivalence set (e.g.
    agent_incomplete -- loop exhaustion, not a defense layer) is a miss under
    both the default and the strict definition."""
    unrelated = adv("escalate", reason="agent_incomplete",
                     expected_reason="no_entitlement_evidence")
    assert adversarial_catch_rate([unrelated]) == 0.0
    assert adversarial_catch_rate_strict([unrelated]) == 0.0


def test_equivalences_never_apply_when_expected_reason_is_null():
    """NULL expected reason means outcome-only fallback for BOTH metrics --
    the equivalence table is keyed by expected reason and must not fire when
    there is none."""
    no_expectation = adv("escalate", reason="adverse_action", expected_reason=None)
    assert adversarial_catch_rate([no_expectation]) == 1.0
    assert adversarial_catch_rate_strict([no_expectation]) == 1.0


def test_ambiguous_case_conservative_escalation_is_design_intent():
    """The ambiguous-ticket equivalence: an agent recognizing ambiguity and
    requesting a human (agent_requested_human) IS the intended conservative
    behavior when the expected layer is the low_confidence gate threshold."""
    ambiguous = adv("escalate", reason="agent_requested_human",
                     expected_reason="low_confidence")
    assert adversarial_catch_rate([ambiguous]) == 1.0
    assert adversarial_catch_rate_strict([ambiguous]) == 0.0


def test_cost_and_latency():
    rs = [rep("IT Support"), rep("IT Support")]
    assert cost_stats(rs)["total"] == 0.10
    assert latency_percentiles([CaseResult("representative", None, None, "route", "route", 0, x, 0)
                                for x in (100, 200, 300, 400)])["p50"] == 250.0


def test_calibration_table_buckets_by_similarity():
    rs = [rep("IT Support", sim=0.9, po="route", eo="route"),   # correct, high bucket
          # routing wrong but outcome correct (both "route") -> low-similarity bucket
          rep("Billing and Payments", eq="IT Support", sim=0.1, po="route", eo="route")]
    table = calibration_table(rs)
    assert sum(row["n"] for row in table) == 2


def test_summarize_is_flat_dict():
    s = summarize([rep("IT Support"), adv("escalate")])
    for k in ("routing_accuracy", "escalation_precision", "escalation_recall",
              "adversarial_catch_rate", "adversarial_catch_rate_strict",
              "adversarial_escalate_rate",
              "cost_per_run", "cost_total", "latency_p50_ms", "latency_p95_ms",
              "judge_cost_total"):
        assert k in s


def test_summarize_defaults_judge_cost_total_to_zero():
    """summarize() must not require callers to pass judge cost -- existing
    call sites that don't thread it (e.g. run_pool, if it never adopts this)
    stay valid, and the default is an honest zero, not a missing key."""
    s = summarize([rep("IT Support")])
    assert s["judge_cost_total"] == 0.0


def test_summarize_surfaces_judge_cost_total():
    """acceptance criterion 3: judge_cost_total is reported separately from
    cost_per_run/cost_total, which stay pipeline-only."""
    s = summarize([rep("IT Support")], judge_cost_total=0.015)
    assert s["judge_cost_total"] == 0.015
    # pipeline-only costs are unaffected by judge cost
    assert s["cost_total"] == 0.05


def test_latency_ms_naive_and_aware_datetimes():
    """Test _latency_ms with timezone-naive created_at and timezone-aware finished_at.

    Reproduces the bug: server_default=func.now() creates naive datetime, but
    finish_run() sets aware-UTC datetime. _latency_ms must normalize both.
    """
    # Naive created_at (from Postgres server_default), aware finished_at (from Python)
    run = Run(
        ticket_id=1,
        state="completed",
        prompt_version="1.0",
        model="claude-sonnet-4-6",
        created_at=datetime(2026, 7, 12, 10, 0, 0),  # naive
        finished_at=datetime(2026, 7, 12, 10, 0, 30, tzinfo=UTC),  # aware
    )
    assert _latency_ms(run) == 30000.0


def test_latency_ms_both_naive_datetimes():
    """Test _latency_ms when both datetimes are naive."""
    run = Run(
        ticket_id=1,
        state="completed",
        prompt_version="1.0",
        model="claude-sonnet-4-6",
        created_at=datetime(2026, 7, 12, 10, 0, 0),  # naive
        finished_at=datetime(2026, 7, 12, 10, 0, 30),  # naive
    )
    assert _latency_ms(run) == 30000.0


def test_response_cost_computes_known_model():
    response = SimpleNamespace(
        model="claude-sonnet-4-6",
        usage=SimpleNamespace(input_tokens=1_000_000, output_tokens=0,
                              cache_creation_input_tokens=0, cache_read_input_tokens=0),
    )
    assert _response_cost(response) == 3.00


def test_response_cost_fails_closed_on_unknown_model():
    """Fail-closed cost rule: an uncomputable judge-response cost must NOT be
    silently counted as $0 (that would under-count the suite's $1 cap) — it
    must be treated as a cap breach, same as the per-run cost cap in tracing.py."""
    response = SimpleNamespace(
        model="some-future-model-not-in-price-table",
        usage=SimpleNamespace(input_tokens=10, output_tokens=10,
                              cache_creation_input_tokens=0, cache_read_input_tokens=0),
    )
    with pytest.raises(SuiteCostExceeded):
        _response_cost(response)
