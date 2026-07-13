from triagedesk.evals.metrics import (
    CaseResult,
    adversarial_catch_rate,
    calibration_table,
    cost_stats,
    escalation_precision_recall,
    latency_percentiles,
    routing_accuracy,
    summarize,
)


def rep(pq, eq="IT Support", eo="route", po="route", sim=0.8):
    return CaseResult("representative", eq, pq, eo, po, 0.05, 1000.0, sim)


def adv(po, eo="escalate"):
    return CaseResult("adversarial", None, None, eo, po, 0.02, 500.0, 0.1)


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
    assert adversarial_catch_rate([adv("escalate"), adv("route"), adv("failed")]) == 1 / 3


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
              "adversarial_catch_rate", "cost_per_run", "cost_total",
              "latency_p50_ms", "latency_p95_ms"):
        assert k in s
