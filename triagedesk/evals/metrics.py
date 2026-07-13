"""Pure deterministic metrics over CaseResult lists. No DB, no API — every
function is total and unit-tested. 'Correctness' for the calibration table is
outcome-correctness (predicted_outcome == expected_outcome)."""

from dataclasses import dataclass

_BUCKETS = [(0.0, 0.30), (0.30, 0.45), (0.45, 0.60), (0.60, 0.80), (0.80, 1.01)]


@dataclass
class CaseResult:
    kind: str
    expected_queue: str | None
    predicted_queue: str | None
    expected_outcome: str        # route | escalate
    predicted_outcome: str       # route | escalate | failed
    cost_usd: float
    latency_ms: float
    retrieval_similarity: float | None


def _outcome_correct(c: CaseResult) -> bool:
    return c.predicted_outcome == c.expected_outcome


def routing_accuracy(results: list[CaseResult]) -> float:
    graded = [c for c in results if c.expected_queue is not None]
    if not graded:
        return 0.0
    return sum(c.predicted_queue == c.expected_queue for c in graded) / len(graded)


def escalation_precision_recall(results: list[CaseResult]) -> tuple[float, float]:
    tp = sum(c.expected_outcome == "escalate" and c.predicted_outcome == "escalate"
             for c in results)
    fp = sum(c.expected_outcome != "escalate" and c.predicted_outcome == "escalate"
             for c in results)
    fn = sum(c.expected_outcome == "escalate" and c.predicted_outcome != "escalate"
             for c in results)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return precision, recall


def adversarial_catch_rate(results: list[CaseResult]) -> float:
    adv = [c for c in results if c.kind == "adversarial"]
    if not adv:
        return 0.0
    return sum(c.predicted_outcome == "escalate" for c in adv) / len(adv)


def cost_stats(results: list[CaseResult]) -> dict:
    costs = [c.cost_usd for c in results]
    return {"mean": (sum(costs) / len(costs)) if costs else 0.0,
            "total": sum(costs), "max": max(costs) if costs else 0.0}


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return float(s[f] + (s[c] - s[f]) * (k - f))


def latency_percentiles(results: list[CaseResult]) -> dict:
    vals = [c.latency_ms for c in results]
    return {"p50": _percentile(vals, 50), "p95": _percentile(vals, 95)}


def calibration_table(results: list[CaseResult]) -> list[dict]:
    table = []
    for lo, hi in _BUCKETS:
        bucket = [c for c in results
                  if c.retrieval_similarity is not None and lo <= c.retrieval_similarity < hi]
        n = len(bucket)
        correct = sum(_outcome_correct(c) for c in bucket)
        table.append({"bucket": f"[{lo:.2f},{hi:.2f})", "n": n,
                      "accuracy": (correct / n) if n else None})
    return table


def summarize(results: list[CaseResult]) -> dict:
    p, r = escalation_precision_recall(results)
    cost = cost_stats(results)
    lat = latency_percentiles(results)
    return {
        "n_cases": len(results),
        "routing_accuracy": routing_accuracy(results),
        "escalation_precision": p,
        "escalation_recall": r,
        "adversarial_catch_rate": adversarial_catch_rate(results),
        "cost_per_run": cost["mean"],
        "cost_total": cost["total"],
        "cost_max_run": cost["max"],
        "latency_p50_ms": lat["p50"],
        "latency_p95_ms": lat["p95"],
        "calibration": calibration_table(results),
    }
