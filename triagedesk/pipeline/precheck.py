from triagedesk.llm import structured_call
from triagedesk.prompts import PRECHECK_SYSTEM, ticket_block
from triagedesk.schemas import PrecheckVerdict


def run_precheck(ticket, tracer, _call=structured_call) -> PrecheckVerdict:
    with tracer.span("precheck") as span:
        verdict, responses = _call(
            system=PRECHECK_SYSTEM,
            user=ticket_block(ticket),
            schema=PrecheckVerdict,
            max_tokens=256,
            temperature=0,  # deterministic safety classification (Hardening Task 2)
        )
        for r in responses:
            tracer.record_llm_usage(span, r)
        tracer.set_attributes(
            span,
            **{
                "triage.precheck.safe": verdict.safe,
                "triage.precheck.category": verdict.category,
                "triage.precheck.reason": verdict.reason,
            },
        )
        return verdict
