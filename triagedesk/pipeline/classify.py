from triagedesk.llm import structured_call
from triagedesk.prompts import CLASSIFY_SYSTEM, ticket_block
from triagedesk.schemas import ClassifyResult


def run_classify(ticket, tracer, _call=structured_call) -> ClassifyResult:
    with tracer.span("classify") as span:
        result, responses = _call(
            system=CLASSIFY_SYSTEM,
            user=ticket_block(ticket),
            schema=ClassifyResult,
            max_tokens=256,
            temperature=0,  # deterministic classification (Hardening Task 2)
        )
        for r in responses:
            tracer.record_llm_usage(span, r)
        tracer.set_attributes(
            span,
            **{
                "triage.classify.queue": result.queue,
                "triage.classify.category": result.category,
            },
        )
        return result
