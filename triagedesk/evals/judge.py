"""LLM-as-judge (secondary signal). Pinned claude-sonnet-4-6, temperature 0,
structured {verdict, reason, rule_triggered}, three labels incl. needs_review.
Judges ONLY reply quality vs KB grounding — never routing/escalation (those are
deterministic). Its reason/rule_triggered are debugging aids, never ground truth
and never fed to the gate.

Hardening Task 2 (issue #45) fixes the judge's tool-blindness: Week 2
calibration (kappa 0.279) root-caused 7/7 flagged "hallucinations" to be true
CRM/tool-derived facts the agent legitimately used from
`lookup_account_status`/`check_entitlement` — the judge only ever saw the KB,
so it graded genuine tool evidence as invented. `judge_run` now reconstructs
those same facts from the simulated CRM (`customer_ref_for` + seed data +
`PLAN_ENTITLEMENTS` — the exact deterministic inputs `triagedesk/tools.py`'s
real tool implementations read) and passes them to `judge_reply` as
`account_context`, rendered as a `<account_facts>` block the judge is told to
treat as legitimate grounding. JUDGE_PROMPT_VERSION is bumped so the
calibration report can never conflate pre/post-fix kappa numbers."""

from triagedesk.llm import structured_call
from triagedesk.models import KbDoc, Span
from triagedesk.schemas import JudgeVerdict
from triagedesk.tools import PLAN_ENTITLEMENTS, customer_ref_for, lookup_account_status

JUDGE_PROMPT_VERSION = "2"

JUDGE_SYSTEM = """\
You grade a support agent's drafted customer reply against the knowledge-base
articles it was given, plus any verified account facts supplied below (these
come from the agent's own CRM/entitlement tool calls, not from the model —
treat them as ground truth, not as claims to verify). You are a debugging aid,
not an authority — your verdict never overrides the deterministic metrics.

Rubric (cite the ONE most-violated rule in rule_triggered when failing):
- grounding: every concrete step/claim in the reply must come from the KB
  articles or the verified account facts below. Invented steps, policies, or
  numbers => fail.
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
                account_context: str | None = None, _call=structured_call):
    account_block = (
        f"\n\n<account_facts>\n{account_context}\n</account_facts>"
        if account_context is not None else ""
    )
    user = (
        f"<ticket>\nSubject: {ticket_subject}\n\n{ticket_body}\n</ticket>\n\n"
        f"<kb>\n{_kb_block(kb_docs)}\n</kb>"
        f"{account_block}\n\n"
        f"<agent_reply>\n{customer_reply}\n</agent_reply>"
    )
    return _call(system=JUDGE_SYSTEM, user=user, schema=JudgeVerdict,
                 max_tokens=512, temperature=0)


def _account_facts_block(ticket) -> str | None:
    """Reconstruct the verified CRM facts for `ticket`'s simulated customer,
    using the exact same deterministic inputs the agent's own
    lookup_account_status/check_entitlement tool calls read
    (triagedesk/tools.py) -- so the judge sees what the agent legitimately
    saw, not a re-derivation that could drift from it. Returns None (no
    account_facts block) when the ticket can't resolve to a customer_ref --
    e.g. it has no `id` (some judge_run fixtures/callers predate this) or the
    id maps to an unknown seed account -- rather than crash the judge call
    over a missing side fact."""
    try:
        ref = customer_ref_for(ticket)
        account = lookup_account_status(ref)
    except (AttributeError, KeyError):
        return None
    entitlements = ", ".join(sorted(PLAN_ENTITLEMENTS.get(account["plan"], set())))
    return (
        f"Customer {account['customer_ref']}: status={account['status']}, "
        f"plan={account['plan']}.\nPlan entitlements: {entitlements}."
    )


def judge_run(session, case, run, _call=structured_call):
    """DB adapter for the harness: reconstruct the ticket + retrieved KB for `run`
    and judge its final_reply. Uses the retrieve span's recorded doc slugs so the
    judge sees exactly what the agent saw, plus the verified account facts (see
    _account_facts_block) so it isn't tool-blind."""
    if not run.final_reply:
        raise ValueError(
            f"Cannot judge run {run.id}: no customer-facing reply to grade. "
            "Run must have completed successfully with a customer reply."
        )
    ticket = run.ticket if getattr(run, "ticket", None) else None
    from triagedesk.models import Ticket
    if ticket is None:
        ticket = session.get(Ticket, case.ticket_id)
    retrieve_span = session.query(Span).filter_by(run_id=run.id, name="retrieve").first()
    slugs = (retrieve_span.attributes or {}).get("retrieval.doc_slugs", []) if retrieve_span else []
    kb_docs = (session.query(KbDoc).filter(KbDoc.slug.in_(slugs)).all() if slugs else [])
    account_context = _account_facts_block(ticket)
    return judge_reply(ticket_subject=ticket.subject, ticket_body=ticket.body,
                       kb_docs=kb_docs, customer_reply=run.final_reply,
                       account_context=account_context, _call=_call)
