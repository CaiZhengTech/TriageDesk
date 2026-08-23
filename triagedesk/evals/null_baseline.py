"""What a one-line `return "escalate"` stub scores on the golden set (#68).

WHY THIS EXISTS
---------------
The golden set is 22 expected-escalate / 3 expected-route. On that distribution
several headline metrics are reproduced exactly by a stub that ignores its input
and escalates everything — they measure the corpus's base rate, not the
pipeline. Publishing the baseline beside every metric is the difference between
a number and a claim, and it is far better stated by the author than discovered
by an interviewer.

DERIVED, NEVER HAND-WRITTEN
---------------------------
The baseline runs synthetic stub results through the SAME `summarize()` the real
harness uses. A hand-copied number drifts silently the moment the golden set or
a metric definition changes — precisely the staleness class that produced #75.

WHAT THE STUB IS
----------------
One branch, no inputs consulted:

    def triage(ticket):
        return "escalate"

It therefore reports **no escalation_reason** (it never looked at the ticket, so
it cannot name a catching layer) and **no predicted_queue**. That detail is
load-bearing — see below.

THE CORRECTION TO THIS ISSUE'S FIRST FRAMING
--------------------------------------------
The initial analysis claimed the design-intent adversarial catch rate collapsed
to the stub too. It does not. `adversarial_catch_rate` is reason-aware: a case
counts as caught only when the observed escalation_reason matches the layer that
was supposed to catch it. A reasonless stub scores **0.00** on both catch rates.

That is the Week-2.5 hardening working as designed — `_caught_by_intended_layer`
exists specifically to close the "tautology of conservatism", and it does. The
honest headline is narrower and more interesting than the original claim: *two*
escalation metrics collapse, and the metric built to prevent that does prevent it.
"""

import json
from pathlib import Path

from triagedesk.evals.adversarial import ADVERSARIAL
from triagedesk.evals.metrics import CaseResult, summarize

EXPECTATIONS = Path("triagedesk/evals/golden_expectations.json")

# Metrics an always-escalate stub reproduces. DERIVED, not asserted — a test
# checks every name here actually scores above zero for the stub, so the list
# cannot rot into a claim nobody re-checked.
COLLAPSING_METRICS = (
    "escalation_recall",
    "escalation_precision",
    "adversarial_escalate_rate",
)

# Metrics with no meaningful stub comparison: a stub that does no work is
# trivially the cheapest and fastest, so "the pipeline loses on cost" is not a
# finding. Skipped rather than reported.
_NO_NULL_EQUIVALENT = (
    "cost_per_run", "cost_total", "cost_max_run", "judge_cost_total",
    "latency_p50_ms", "latency_p95_ms", "n_cases", "calibration",
)


def stub_results(expectations_path: Path = EXPECTATIONS) -> list[CaseResult]:
    """The golden set as an always-escalate stub would answer it.

    Expected fields come from the real golden set; predicted fields are what a
    stub produces: escalate, no reason, no queue.
    """
    rows = json.loads(expectations_path.read_text())
    results = [
        CaseResult(
            kind="representative",
            expected_queue=r["expected_queue"],
            predicted_queue=None,               # a stub routes nothing
            expected_outcome=r["expected_outcome"],
            predicted_outcome="escalate",       # ...it just escalates
            cost_usd=0.0,
            latency_ms=0.0,
            retrieval_similarity=None,
            escalation_reason=None,             # ...and cannot say why
            expected_escalation_reason=r.get("escalation_reason"),
        )
        for r in rows
    ]
    results += [
        CaseResult(
            kind="adversarial",
            expected_queue=spec["expected_queue"],
            predicted_queue=None,
            expected_outcome=spec["expected_outcome"],
            predicted_outcome="escalate",
            cost_usd=0.0,
            latency_ms=0.0,
            retrieval_similarity=None,
            escalation_reason=None,
            expected_escalation_reason=spec["expected_escalation_reason"],
        )
        for spec in ADVERSARIAL
    ]
    return results


def null_baseline(expectations_path: Path = EXPECTATIONS) -> dict:
    """Full metric summary for the stub, via the real `summarize()`."""
    return summarize(stub_results(expectations_path))


def compare_to_null(summary: dict, baseline: dict | None = None) -> dict:
    """For each comparable metric: the real score, the stub's, and whether the
    real one actually beats it.

    `distinguishing=False` means the metric is reproduced by a stub and should
    not be published as evidence about the pipeline without that context. It is
    not a failure — `escalation_recall` 1.00 is still true, it just isn't
    *informative* on this corpus.
    """
    base = baseline if baseline is not None else null_baseline()
    out = {}
    for metric, value in summary.items():
        if metric in _NO_NULL_EQUIVALENT or metric not in base:
            continue
        if not isinstance(value, int | float):
            continue
        null_value = base[metric]
        out[metric] = {
            "value": value,
            "null_baseline": null_value,
            "distinguishing": value > null_value,
        }
    return out


def format_comparison(summary: dict, baseline: dict | None = None) -> str:
    """Human-readable table for CI logs and suite reports."""
    verdict = compare_to_null(summary, baseline)
    if not verdict:
        return "(no metrics with a null-baseline equivalent)"
    lines = [
        f"  {'metric':<32} {'value':>8} {'null':>8}  verdict",
        f"  {'-' * 32} {'-' * 8} {'-' * 8}  {'-' * 30}",
    ]
    for metric, v in sorted(verdict.items()):
        mark = "beats null" if v["distinguishing"] else "NOT DISTINGUISHING"
        lines.append(
            f"  {metric:<32} {v['value']:>8.3f} {v['null_baseline']:>8.3f}  {mark}"
        )
    return "\n".join(lines)
