"""Judge unit tests. Response shapes mirror the structured_output entry of
tests/fixtures/sdk_structured_output_caching.json. No live calls."""
from types import SimpleNamespace

from triagedesk.evals.judge import judge_reply
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
