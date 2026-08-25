"""Cost per accepted task — what the system actually costs to operate (#79).

WHY NOT COST PER RUN
--------------------
Per-token cost is the number everyone reports and it is misleading here. A
cheaper model that escalates more can raise total cost while lowering cost per
call, because an escalation does not end the work — it moves the work to a
person. The literature on model routing is blunt about this: a model can cost
80% less per call and still lose money if it sends more work to human reviewers.
The honest denominator is *accepted tasks*, and the honest numerator includes
the labour an escalation creates.

TriageDesk can compute this. Most portfolio projects cannot, because they have
no human-review side to price. This one has `review_decisions` and a real queue.

THE ASSUMPTION, STATED UP FRONT
-------------------------------
`review_minutes` and `reviewer_hourly_usd` are assumptions, not measurements.
They drive the entire result — at any plausible wage, labour dwarfs API spend by
two orders of magnitude — so they are carried in the output rather than buried
as constants. Change them and the conclusion changes; that is the point, and
hiding it would make this metric dishonest rather than useful.

Defaults are deliberately conservative: 6 minutes is a fast triage review, and
$30/hour is a modest fully-loaded support-agent rate. Both are *cited estimates,
not measurements from this system* — nothing here has ever been reviewed under
a stopwatch.

WHAT COUNTS AS ACCEPTED
-----------------------
Only `completed` runs. An escalation produced a draft a human must still handle;
a failure produced nothing. Counting either as accepted would flatter the number.
Their cost still lands in the numerator, because it was really spent.
"""

from dataclasses import dataclass

# Fast triage review of a pre-drafted reply. Not measured here — an estimate.
DEFAULT_REVIEW_MINUTES = 6.0
# Modest fully-loaded support-agent rate. Also an estimate.
DEFAULT_REVIEWER_HOURLY_USD = 30.0

_ASSUMPTION_NOTE = (
    "review_minutes and reviewer_hourly_usd are ASSUMPTIONS, not measurements "
    "from this system — no run here has been reviewed under a stopwatch. They "
    "dominate the result (labour exceeds API spend by ~2 orders of magnitude at "
    "any plausible wage), so they are reported alongside every number derived "
    "from them. Substitute your own and the conclusions move accordingly."
)


@dataclass
class RunRecord:
    """One terminal run. `was_reviewed` distinguishes an escalation a human has
    actually actioned from one still sitting in the queue."""
    state: str                 # completed | escalated | failed | running
    total_cost_usd: float
    was_reviewed: bool = False


def unit_economics(
    runs: list[RunRecord],
    review_minutes: float = DEFAULT_REVIEW_MINUTES,
    reviewer_hourly_usd: float = DEFAULT_REVIEWER_HOURLY_USD,
) -> dict:
    """Cost per accepted task, plus the terms it decomposes into.

    `running` rows are dropped: they have no outcome yet, and including them
    would make the metric depend on when you happened to query.
    """
    terminal = [r for r in runs if r.state in ("completed", "escalated", "failed")]

    n_accepted = sum(r.state == "completed" for r in terminal)
    n_escalated = sum(r.state == "escalated" for r in terminal)
    n_failed = sum(r.state == "failed" for r in terminal)
    n_reviewed = sum(r.state == "escalated" and r.was_reviewed for r in terminal)

    api_cost = sum(r.total_cost_usd for r in terminal)
    labour_per_review = (review_minutes / 60.0) * reviewer_hourly_usd
    labour_cost = n_escalated * labour_per_review
    total_cost = api_cost + labour_cost

    n = len(terminal)
    return {
        "n_runs": n,
        "n_accepted": n_accepted,
        "n_escalated": n_escalated,
        "n_failed": n_failed,
        "n_reviewed": n_reviewed,
        "deflection_rate": (n_accepted / n) if n else None,
        "api_cost_usd": api_cost,
        "labour_cost_usd": labour_cost,
        "total_cost_usd": total_cost,
        "api_cost_per_run": (api_cost / n) if n else None,
        # The headline. None when nothing was accepted — an undefined ratio, not
        # a zero, and reporting it as 0 would read as "free" rather than "never
        # succeeded".
        "cost_per_accepted_task": (total_cost / n_accepted) if n_accepted else None,
        "labour_cost_per_escalation": labour_per_review,
        "break_even_deflection_rate": _break_even(
            api_cost / n if n else 0.0, labour_per_review
        ),
        "assumptions": {
            "review_minutes": review_minutes,
            "reviewer_hourly_usd": reviewer_hourly_usd,
            "labour_cost_per_escalation_usd": labour_per_review,
            "_note": _ASSUMPTION_NOTE,
        },
    }


def _break_even(api_cost_per_run: float, labour_per_review: float) -> float | None:
    """Deflection rate at which running the pipeline beats sending everything to
    a human.

    Baseline (no pipeline): every ticket costs one review, `L`.
    With the pipeline: every ticket costs `A` in API spend, and the (1-d) that
    escalate still cost `L` each.

        A + (1 - d)L  <  L      =>      d  >  A / L

    So the break-even deflection rate is just the ratio of a run's API cost to a
    review's labour cost — which is why it is tiny: the pipeline pays for itself
    if it deflects even a small fraction, PROVIDED the escalated drafts do not
    make review slower than it would have been from scratch. That proviso is not
    measured here and is the honest caveat on this number.
    """
    if labour_per_review <= 0:
        return None
    return api_cost_per_run / labour_per_review
