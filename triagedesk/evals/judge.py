"""LLM-as-judge (secondary signal). Pinned claude-sonnet-4-6, temperature 0,
structured {verdict, reason, rule_triggered}, three labels incl. needs_review.
Judges ONLY reply quality vs KB grounding — never routing/escalation (those are
deterministic). Its reason/rule_triggered are debugging aids, never ground truth
and never fed to the gate."""

from triagedesk.llm import structured_call
from triagedesk.models import KbDoc, Span
from triagedesk.schemas import JudgeVerdict

JUDGE_SYSTEM = """\
You grade a support agent's drafted customer reply against the knowledge-base
articles it was given. You are a debugging aid, not an authority — your verdict
never overrides the deterministic metrics.

Rubric (cite the ONE most-violated rule in rule_triggered when failing):
- grounding: every concrete step/claim in the reply must come from the KB
  articles below. Invented steps, policies, or numbers => fail.
- helpfulness: the reply actually addresses the ticket, with concrete steps.
- tone: professional, no over-promising (no refunds/credits/plan changes).

Return:
- verdict: "pass" (grounded, helpful, appropriate), "fail" (a rule is clearly
  violated), or "needs_review" (genuinely ambiguous — abstain rather than guess).
- reason: one sentence.
- rule_triggered: "grounding" | "helpfulness" | "tone" | null."""


def _kb_block(kb_docs) -> str:
    if not kb_docs:
        return "(no KB articles were retrieved)"
    return "\n\n".join(
        f"<kb_article slug=\"{d.slug}\">\n# {d.title}\n{d.content}\n</kb_article>"
        for d in kb_docs
    )


def judge_reply(*, ticket_subject, ticket_body, kb_docs, customer_reply,
                _call=structured_call):
    user = (
        f"<ticket>\nSubject: {ticket_subject}\n\n{ticket_body}\n</ticket>\n\n"
        f"<kb>\n{_kb_block(kb_docs)}\n</kb>\n\n"
        f"<agent_reply>\n{customer_reply}\n</agent_reply>"
    )
    return _call(system=JUDGE_SYSTEM, user=user, schema=JudgeVerdict,
                 max_tokens=512, temperature=0)


def judge_run(session, case, run):
    """DB adapter for the harness: reconstruct the ticket + retrieved KB for `run`
    and judge its final_reply. Uses the retrieve span's recorded doc slugs so the
    judge sees exactly what the agent saw."""
    ticket = run.ticket if getattr(run, "ticket", None) else None
    from triagedesk.models import Ticket
    if ticket is None:
        ticket = session.get(Ticket, case.ticket_id)
    retrieve_span = session.query(Span).filter_by(run_id=run.id, name="retrieve").first()
    slugs = (retrieve_span.attributes or {}).get("retrieval.doc_slugs", []) if retrieve_span else []
    kb_docs = (session.query(KbDoc).filter(KbDoc.slug.in_(slugs)).all() if slugs else [])
    return judge_reply(ticket_subject=ticket.subject, ticket_body=ticket.body,
                       kb_docs=kb_docs, customer_reply=run.final_reply)
