"""Judge unit tests. Response shapes mirror the structured_output entry of
tests/fixtures/sdk_structured_output_caching.json. No live calls."""
from types import SimpleNamespace

import pytest

from triagedesk.evals.judge import judge_reply, judge_run
from triagedesk.schemas import JudgeVerdict


def fake_response(payload_json):
    return SimpleNamespace(
        stop_reason="end_turn", model="claude-sonnet-4-6",
        content=[SimpleNamespace(type="text", text=payload_json)],
        usage=SimpleNamespace(input_tokens=300, output_tokens=40,
                              cache_creation_input_tokens=0, cache_read_input_tokens=0),
    )


class FakeMessages:
    def __init__(self, resp):
        self.resp = resp
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.resp


def make_client(resp):
    return SimpleNamespace(messages=FakeMessages(resp))


def test_judge_returns_structured_verdict_at_temperature_zero():
    payload = JudgeVerdict(verdict="pass", reason="steps match the KB doc",
                           rule_triggered=None).model_dump_json()
    client = make_client(fake_response(payload))
    from triagedesk.llm import structured_call

    def call(**kw):
        return structured_call(_client=client, **kw)

    verdict, responses = judge_reply(
        ticket_subject="VPN drops", ticket_body="my vpn keeps dropping",
        kb_docs=[SimpleNamespace(slug="vpn", title="VPN", content="Restart the client.")],
        customer_reply="Please restart your VPN client.", _call=call)
    assert isinstance(verdict, JudgeVerdict)
    assert verdict.verdict == "pass"
    assert client.messages.calls[0]["temperature"] == 0    # pinned temp 0
    assert client.messages.calls[0]["model"] == "claude-sonnet-4-6"


def test_judge_can_abstain():
    payload = JudgeVerdict(verdict="needs_review", reason="reply cites no doc",
                           rule_triggered="grounding").model_dump_json()
    client = make_client(fake_response(payload))
    from triagedesk.llm import structured_call
    verdict, _ = judge_reply(
        ticket_subject="s", ticket_body="b", kb_docs=[], customer_reply="hi",
        _call=lambda **kw: structured_call(_client=client, **kw))
    assert verdict.verdict == "needs_review"
    assert verdict.rule_triggered == "grounding"


# --------------------------------------------- tool-evidence (Hardening Task 2)

def test_judge_reply_prompt_includes_account_facts_block_when_context_given():
    """The tool-blindness fix: 7/7 Week-2 calibration "hallucinations" the
    judge flagged were true CRM/tool-derived facts, because the judge only
    ever saw the KB. account_context, when given, must be rendered as a
    clearly-delimited <account_facts> block."""
    payload = JudgeVerdict(verdict="pass", reason="grounded in account facts",
                           rule_triggered=None).model_dump_json()
    client = make_client(fake_response(payload))
    from triagedesk.llm import structured_call
    verdict, _ = judge_reply(
        ticket_subject="s", ticket_body="b", kb_docs=[], customer_reply="hi",
        account_context="Customer customer-3: status=active, plan=basic.",
        _call=lambda **kw: structured_call(_client=client, **kw))
    prompt = client.messages.calls[0]["messages"][0]["content"]
    assert "<account_facts>" in prompt
    assert "</account_facts>" in prompt
    assert "customer-3" in prompt
    assert verdict.verdict == "pass"


def test_judge_reply_prompt_omits_account_facts_block_when_none():
    """account_context defaults to None -- e.g. an unresolvable customer_ref
    -- and must not leave a stray/empty <account_facts> block in the prompt."""
    payload = JudgeVerdict(verdict="pass", reason="ok", rule_triggered=None).model_dump_json()
    client = make_client(fake_response(payload))
    from triagedesk.llm import structured_call
    judge_reply(
        ticket_subject="s", ticket_body="b", kb_docs=[], customer_reply="hi",
        _call=lambda **kw: structured_call(_client=client, **kw))
    prompt = client.messages.calls[0]["messages"][0]["content"]
    assert "<account_facts>" not in prompt


def test_judge_run_builds_account_facts_deterministically_from_the_simulated_crm():
    """judge_run must reconstruct EXACTLY what the agent's own tools saw:
    customer_ref_for(ticket) -> lookup_account_status(ref) + plan
    entitlements from PLAN_ENTITLEMENTS. ticket.id=3 -> customer-3 Dana
    Fuentes, active, basic plan (triagedesk/seed_accounts.json +
    triagedesk/tools.py::PLAN_ENTITLEMENTS) -- the project's canonical
    "Dana's VPN ticket" example."""
    ticket = SimpleNamespace(id=3, subject="VPN keeps disconnecting",
                             body="Client demo at 3pm.")
    session = FakeSession(ticket=ticket, spans=[], kb_docs=[])
    case = SimpleNamespace(ticket_id=3)
    run = SimpleNamespace(id="run-uuid-dana",
                          final_reply="Please restart your VPN client.", ticket=ticket)
    payload = JudgeVerdict(verdict="pass", reason="grounded in account facts",
                           rule_triggered=None).model_dump_json()
    client = make_client(fake_response(payload))
    from triagedesk.llm import structured_call

    def call(**kw):
        return structured_call(_client=client, **kw)

    verdict, _ = judge_run(session, case, run, _call=call)
    prompt = client.messages.calls[0]["messages"][0]["content"]
    assert "<account_facts>" in prompt
    assert "customer-3" in prompt
    assert "active" in prompt
    assert "basic" in prompt
    assert "standard_support" in prompt  # basic-plan entitlement, from PLAN_ENTITLEMENTS
    assert verdict.verdict == "pass"


def test_judge_run_omits_account_facts_when_ticket_has_no_id():
    """Existing judge_run fixtures build tickets without an `id` (only
    subject/body) -- customer_ref_for(ticket) would raise AttributeError.
    Must degrade to no account context, not crash the judge call."""
    ticket = SimpleNamespace(subject="VPN issue", body="my vpn drops")
    session = FakeSession(ticket=ticket, spans=[], kb_docs=[])
    case = SimpleNamespace(ticket_id=1)
    run = SimpleNamespace(id="run-uuid", final_reply="Please restart your VPN client.",
                          ticket=ticket)
    payload = JudgeVerdict(verdict="pass", reason="ok", rule_triggered=None).model_dump_json()
    client = make_client(fake_response(payload))
    from triagedesk.llm import structured_call

    def call(**kw):
        return structured_call(_client=client, **kw)

    judge_run(session, case, run, _call=call)
    prompt = client.messages.calls[0]["messages"][0]["content"]
    assert "<account_facts>" not in prompt


def test_judge_prompt_version_is_bumped_for_the_tool_evidence_fix():
    """Task 2 resolution: bumping this constant is how pre/post-fix kappas
    are kept from being conflated in the calibration report header."""
    from triagedesk.evals.judge import JUDGE_PROMPT_VERSION
    assert JUDGE_PROMPT_VERSION == "2"


# judge_run tests

class FakeQueryFilter:
    """Fake SQLAlchemy filter().all() chain."""
    def __init__(self, items):
        self.items = items

    def filter(self, *args):
        # For KbDoc.slug.in_(slugs) filters
        return self

    def all(self):
        return self.items


class FakeQuery:
    """Fake SQLAlchemy query() interface."""
    def __init__(self, items):
        self.items = items

    def filter_by(self, **kwargs):
        # For Span lookups
        return FakeQueryResult(self.items)

    def filter(self, *args):
        # For KbDoc lookups
        return FakeQueryFilter(self.items)


class FakeQueryResult:
    """Fake result of filter_by()."""
    def __init__(self, items):
        self.items = items

    def first(self):
        return self.items[0] if self.items else None


class FakeSession:
    """Fake SQLAlchemy session for testing judge_run."""
    def __init__(self, ticket=None, spans=None, kb_docs=None):
        self.ticket = ticket
        self.spans = spans or []
        self.kb_docs = kb_docs or []

    def get(self, model_class, id_):
        # Return the ticket if requested
        if self.ticket:
            return self.ticket
        return None

    def query(self, model_class):
        from triagedesk.models import KbDoc, Span
        if model_class == Span:
            return FakeQuery(self.spans)
        elif model_class == KbDoc:
            return FakeQuery(self.kb_docs)
        return FakeQuery([])


def test_judge_run_raises_on_no_final_reply():
    """Test that judge_run raises ValueError when run.final_reply is None."""
    session = FakeSession()
    case = SimpleNamespace(ticket_id=1)
    run = SimpleNamespace(
        id="run-uuid-123",
        final_reply=None,
        ticket=SimpleNamespace(subject="Test", body="Body")
    )
    with pytest.raises(ValueError, match="Cannot judge run.*no customer-facing reply"):
        judge_run(session, case, run)


def test_judge_run_raises_on_empty_final_reply():
    """Test that judge_run raises ValueError when run.final_reply is empty string."""
    session = FakeSession()
    case = SimpleNamespace(ticket_id=1)
    run = SimpleNamespace(
        id="run-uuid-456",
        final_reply="",
        ticket=SimpleNamespace(subject="Test", body="Body")
    )
    with pytest.raises(ValueError, match="Cannot judge run.*no customer-facing reply"):
        judge_run(session, case, run)


def test_judge_run_no_retrieve_span():
    """Test that judge_run works with no retrieve span (empty kb_docs)."""
    ticket = SimpleNamespace(subject="VPN issue", body="my vpn drops")
    session = FakeSession(ticket=ticket, spans=[])
    case = SimpleNamespace(ticket_id=1)
    run = SimpleNamespace(
        id="run-uuid-789",
        final_reply="Please restart your VPN client.",
        ticket=ticket
    )
    payload = JudgeVerdict(verdict="pass", reason="no KB retrieved but reply is generic",
                           rule_triggered=None).model_dump_json()
    client = make_client(fake_response(payload))
    from triagedesk.llm import structured_call

    def call(**kw):
        return structured_call(_client=client, **kw)

    verdict, _ = judge_run(session, case, run, _call=call)
    assert isinstance(verdict, JudgeVerdict)
    # Verify that the call was made with empty kb_docs
    call_kwargs = client.messages.calls[0]
    assert "(no KB articles were retrieved)" in call_kwargs["messages"][0]["content"]


def test_judge_run_empty_slugs_list():
    """Test that judge_run works when retrieve span has empty slugs list."""
    ticket = SimpleNamespace(subject="Test", body="test body")
    retrieve_span = SimpleNamespace(
        id=1, run_id="run-uuid", name="retrieve",
        attributes={"retrieval.doc_slugs": []}
    )
    session = FakeSession(ticket=ticket, spans=[retrieve_span])
    case = SimpleNamespace(ticket_id=1)
    run = SimpleNamespace(
        id="run-uuid",
        final_reply="Help is on the way.",
        ticket=ticket
    )
    payload = JudgeVerdict(verdict="needs_review", reason="no articles retrieved",
                           rule_triggered="grounding").model_dump_json()
    client = make_client(fake_response(payload))
    from triagedesk.llm import structured_call

    def call(**kw):
        return structured_call(_client=client, **kw)

    verdict, _ = judge_run(session, case, run, _call=call)
    assert isinstance(verdict, JudgeVerdict)


def test_judge_run_happy_path_with_kb_docs():
    """Test that judge_run retrieves and passes KB docs from slugs."""
    ticket = SimpleNamespace(subject="Restart VPN", body="vpn connection lost")
    kb_doc_1 = SimpleNamespace(
        id=1, slug="vpn-restart", title="VPN Restart",
        content="Step 1: Open VPN app. Step 2: Click Restart."
    )
    kb_doc_2 = SimpleNamespace(
        id=2, slug="vpn-faq", title="VPN FAQ",
        content="Q: Why does VPN drop? A: Network issue."
    )
    retrieve_span = SimpleNamespace(
        id=1, run_id="run-uuid", name="retrieve",
        attributes={"retrieval.doc_slugs": ["vpn-restart", "vpn-faq"]}
    )
    session = FakeSession(ticket=ticket, spans=[retrieve_span],
                          kb_docs=[kb_doc_1, kb_doc_2])
    case = SimpleNamespace(ticket_id=1)
    run = SimpleNamespace(
        id="run-uuid",
        final_reply="Please restart your VPN app and check your network.",
        ticket=ticket
    )
    payload = JudgeVerdict(verdict="pass", reason="reply matches KB guidance",
                           rule_triggered=None).model_dump_json()
    client = make_client(fake_response(payload))
    from triagedesk.llm import structured_call

    def call(**kw):
        return structured_call(_client=client, **kw)

    verdict, _ = judge_run(session, case, run, _call=call)
    assert isinstance(verdict, JudgeVerdict)
    assert verdict.verdict == "pass"
    # Verify both KB docs appear in the prompt
    call_kwargs = client.messages.calls[0]
    prompt = call_kwargs["messages"][0]["content"]
    assert "vpn-restart" in prompt
    assert "vpn-faq" in prompt
