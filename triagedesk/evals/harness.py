"""Runs the golden set through the real pipeline, records eval_results, and
returns (eval_run_id, summary). LIVE: calls runner.run_ticket per case (and,
with_judge, the judge per completed reply). Suite-level $1 cap on top of the
per-run $0.10 cap — fail closed.

The judge import (triagedesk.evals.judge) is deferred to the point of use
(inside the with_judge branch, not at module or function top) so
`run_suite(..., with_judge=False)` never pays for it.
"""

import uuid
from datetime import UTC

from triagedesk.evals.metrics import CaseResult, summarize
from triagedesk.models import EvalCase, EvalResult, Run, Span
from triagedesk.pipeline.runner import run_ticket

SUITE_COST_CAP_USD = 1.00


class SuiteCostExceeded(Exception):
    pass


_STATE_TO_OUTCOME = {"completed": "route", "escalated": "escalate", "failed": "failed"}


def _classify_queue(session, run_id) -> str | None:
    span = session.query(Span).filter_by(run_id=run_id, name="classify").first()
    if span is None:
        return None
    return (span.attributes or {}).get("triage.classify.queue")


def _as_utc(dt):
    """Normalize a datetime to UTC. Naive datetimes are assumed to be UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _latency_ms(run: Run) -> float:
    if run.finished_at and run.created_at:
        return (_as_utc(run.finished_at) - _as_utc(run.created_at)).total_seconds() * 1000.0
    return 0.0


def run_suite(session, *, cost_cap: float = SUITE_COST_CAP_USD, with_judge: bool = True):
    eval_run_id = uuid.uuid4()
    cases = session.query(EvalCase).order_by(EvalCase.id).all()
    total_cost = 0.0
    case_results: list[CaseResult] = []

    for case in cases:
        run = run_ticket(case.ticket_id, session)  # LIVE
        total_cost += run.total_cost_usd or 0.0
        if total_cost > cost_cap:
            raise SuiteCostExceeded(f"suite cost ${total_cost:.4f} exceeds cap ${cost_cap}")

        predicted_outcome = _STATE_TO_OUTCOME[run.state]
        predicted_queue = _classify_queue(session, run.id)
        signals = run.gate_signals or {}
        cr = CaseResult(
            kind=case.kind, expected_queue=case.expected_queue,
            predicted_queue=predicted_queue, expected_outcome=case.expected_outcome,
            predicted_outcome=predicted_outcome, cost_usd=run.total_cost_usd or 0.0,
            latency_ms=_latency_ms(run),
            retrieval_similarity=signals.get("retrieval_similarity"),
        )
        case_results.append(cr)

        result = EvalResult(
            eval_run_id=eval_run_id, case_id=case.id, run_id=run.id,
            predicted_queue=predicted_queue, predicted_outcome=predicted_outcome,
            escalation_reason=run.escalation_reason, cost_usd=cr.cost_usd,
            latency_ms=cr.latency_ms, retrieval_similarity=signals.get("retrieval_similarity"),
            classification_margin=signals.get("classification_margin"),
            routing_correct=(predicted_queue == case.expected_queue
                             if case.expected_queue else None),
            outcome_correct=(predicted_outcome == case.expected_outcome),
        )

        if with_judge and run.state == "completed" and run.final_reply:
            from triagedesk.evals.judge import judge_run  # local import: judge is Task 5

            verdict, responses = judge_run(session, case, run)  # LIVE
            total_cost += sum(_response_cost(r) for r in responses)
            if total_cost > cost_cap:
                raise SuiteCostExceeded(f"suite cost ${total_cost:.4f} exceeds cap ${cost_cap}")
            result.judge_verdict = verdict.verdict
            result.judge_reason = verdict.reason
            result.judge_rule_triggered = verdict.rule_triggered

        session.add(result)
        session.commit()

    return eval_run_id, summarize(case_results)


def _response_cost(response) -> float:
    """Cost of one raw API response (a judge call). Fail closed, same rule as
    the per-run cap in tracing.py: an uncomputable cost is a cap breach, not
    $0 — silently zeroing it would under-count the suite's cost cap."""
    from triagedesk.tracing import CostUnknownError, compute_cost
    try:
        return compute_cost(getattr(response, "model", ""), response.usage)
    except CostUnknownError as exc:
        raise SuiteCostExceeded(
            f"judge response cost unknown ({exc}) — failing closed as a cap breach"
        ) from exc
