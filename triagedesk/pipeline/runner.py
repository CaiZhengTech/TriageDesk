"""Orchestrates one run: precheck -> classify -> retrieve -> act -> gate.
Every failure mode maps to a terminal state + reason. Spans are already on
disk if anything here crashes (incremental writes in RunTracer)."""

import anthropic

from triagedesk.llm import PIPELINE_MODEL, LLMRefusalError, RepairFailedError
from triagedesk.models import Run, Ticket
from triagedesk.pipeline.act import AgentIncompleteError, ToolFailedError, run_act
from triagedesk.pipeline.classify import run_classify
from triagedesk.pipeline.gate import classification_margin, decide, load_centroids
from triagedesk.pipeline.precheck import run_precheck
from triagedesk.pipeline.retrieve import run_retrieve
from triagedesk.prompts import PROMPT_VERSION
from triagedesk.tracing import (
    BudgetExceededError,
    CostUnknownError,
    RunTracer,
    finish_run,
)


def run_ticket(ticket_id: int, session) -> Run:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise ValueError(f"no ticket {ticket_id}")

    run = Run(ticket_id=ticket.id, state="running",
              prompt_version=PROMPT_VERSION, model=PIPELINE_MODEL)
    session.add(run)
    session.commit()
    tracer = RunTracer(session, run)

    try:
        verdict = run_precheck(ticket, tracer)
        if not verdict.safe:
            finish_run(session, run, "escalated", reason=f"precheck_{verdict.category}")
            return run

        classify_result = run_classify(ticket, tracer)
        retrieval = run_retrieve(ticket, tracer, session)
        outcome = run_act(ticket, classify_result, retrieval, tracer)

        with tracer.span("gate") as span:
            margin = classification_margin(
                retrieval.query_embedding, classify_result.queue, load_centroids()
            )
            decision = decide(
                retrieval_similarity=retrieval.top_similarity,
                margin=margin,
                outcome=outcome,
                entitlement_checked=outcome.entitlement_checked,
            )
            run.gate_signals = decision.signals
            tracer.set_attributes(
                span,
                **{
                    "triage.gate.auto_resolve": decision.auto_resolve,
                    "triage.gate.reason": decision.reason,
                    **decision.signals,
                },
            )

        if decision.auto_resolve:
            finish_run(session, run, "completed", resolution=outcome.resolution)
        else:
            # Rationale still logged on escalation: trace = evidence,
            # LLM rationale = post-hoc context for the reviewer.
            finish_run(session, run, "escalated", reason=decision.reason,
                       resolution=outcome.resolution)

    except (BudgetExceededError, CostUnknownError) as exc:
        finish_run(session, run, "escalated", reason="budget_breach")
        _note(session, run, exc)
    except RepairFailedError as exc:
        finish_run(session, run, "escalated", reason="validation_failed")
        _note(session, run, exc)
    except LLMRefusalError as exc:
        finish_run(session, run, "escalated", reason="llm_refusal")
        _note(session, run, exc)
    except ToolFailedError as exc:
        finish_run(session, run, "escalated", reason="tool_error")
        _note(session, run, exc)
    except AgentIncompleteError as exc:
        finish_run(session, run, "escalated", reason="agent_incomplete")
        _note(session, run, exc)
    except anthropic.APIError as exc:
        finish_run(session, run, "failed", reason=f"api_error:{type(exc).__name__}")
        _note(session, run, exc)
    except Exception as exc:
        finish_run(session, run, "failed", reason=f"unexpected:{type(exc).__name__}")
        _note(session, run, exc)
    return run


def _note(session, run: Run, exc: Exception) -> None:
    run.internal_rationale = f"{type(exc).__name__}: {exc}"
    session.commit()
