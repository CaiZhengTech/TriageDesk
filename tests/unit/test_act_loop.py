from types import SimpleNamespace

import pytest

from tests.unit.test_precheck_classify import FakeTracer
from triagedesk.llm import PIPELINE_MODEL
from triagedesk.pipeline.act import AgentIncompleteError, ToolFailedError, run_act

TICKET = SimpleNamespace(id=3, subject="Need a dedicated IP",
                         body="Please enable a dedicated IP for my account.")
CLASSIFY = SimpleNamespace(queue="IT Support", category="network")
RETRIEVAL = SimpleNamespace(
    docs=[SimpleNamespace(slug="plans", title="Plans",
                          content="Dedicated IP is Enterprise-only.")],
    top_similarity=0.8, query_embedding=[0.0],
)


def usage():
    return SimpleNamespace(input_tokens=500, output_tokens=100,
                           cache_creation_input_tokens=0, cache_read_input_tokens=0)


def tool_use_block(name, tool_input, block_id="tu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=block_id)


def thinking_block():
    # Every real response carries one of these (tests/fixtures/sdk_tool_use_shapes.json)
    # — included so the `.type == "tool_use"` filter genuinely has non-tool blocks to skip.
    return SimpleNamespace(type="thinking", thinking="reasoning about the ticket...",
                           signature="sig")


def text_block(text="Looking into this now."):
    return SimpleNamespace(type="text", text=text, citations=None)


def response(blocks, stop_reason="tool_use"):
    return SimpleNamespace(content=blocks, stop_reason=stop_reason,
                           model="claude-sonnet-4-6", usage=usage())


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            pytest.fail("act loop called the API more times than scripted")
        return self._responses.pop(0)


def make_client(responses):
    return SimpleNamespace(messages=FakeMessages(responses))


RESOLUTION_CALL = tool_use_block("submit_resolution", {
    "resolution_type": "deny",
    "customer_reply": "Dedicated IP requires the Enterprise plan.",
    "internal_rationale": "customer-3 is on basic; dedicated_ip not covered.",
})


def test_happy_path_lookup_then_resolve():
    client = make_client([
        response([tool_use_block("check_entitlement",
                                 {"customer_ref": "customer-3", "feature": "dedicated_ip"})]),
        response([RESOLUTION_CALL]),
    ])
    outcome = run_act(TICKET, CLASSIFY, RETRIEVAL, FakeTracer(), _client=client)
    assert outcome.resolution.resolution_type == "deny"
    assert outcome.entitlement_denied is True  # basic plan, dedicated_ip => covered False

    first_call = client.messages.calls[0]
    assert first_call["model"] == PIPELINE_MODEL
    assert first_call["max_tokens"] == 4096
    assert first_call["thinking"] == {"type": "adaptive"}
    assert first_call["output_config"] == {"effort": "high"}
    tools = first_call["tools"]
    assert len(tools) == 3
    submit_def = next(t for t in tools if t["name"] == "submit_resolution")
    assert submit_def["strict"] is True


def test_loop_exhaustion_escalates():
    lookup = tool_use_block("lookup_account_status", {"customer_ref": "customer-3"})
    client = make_client([response([lookup])] * 5)
    with pytest.raises(AgentIncompleteError):
        run_act(TICKET, CLASSIFY, RETRIEVAL, FakeTracer(), _client=client)
    assert len(client.messages.calls) == 5  # hard cap


def test_end_turn_without_resolution_is_incomplete():
    client = make_client([response([], stop_reason="end_turn")])
    with pytest.raises(AgentIncompleteError):
        run_act(TICKET, CLASSIFY, RETRIEVAL, FakeTracer(), _client=client)


def test_tool_error_retries_once_then_escalates(monkeypatch):
    from triagedesk.pipeline import act

    calls = {"n": 0}

    def boom(name, tool_input):
        calls["n"] += 1
        raise RuntimeError("simulated tool outage")

    monkeypatch.setattr(act, "execute_tool", boom)
    client = make_client([
        response([tool_use_block("lookup_account_status", {"customer_ref": "customer-3"})]),
    ])
    with pytest.raises(ToolFailedError):
        run_act(TICKET, CLASSIFY, RETRIEVAL, FakeTracer(), _client=client)
    assert calls["n"] == 2  # exactly one retry


def test_parallel_tool_calls_executed_in_one_turn():
    """Mirrors fixture turn0 (tests/fixtures/sdk_tool_use_shapes.json): a single
    response with thinking + text + TWO tool_use blocks. The loop must execute
    both tools and return one tool_result per tool_use_id in a single user
    message on the next turn."""
    lookup = tool_use_block("lookup_account_status", {"customer_ref": "customer-3"},
                            block_id="toolu_01TQ6iSrDjgjhPGL9bdKdd7E")
    entitlement = tool_use_block(
        "check_entitlement",
        {"customer_ref": "customer-3", "feature": "priority_vpn_support"},
        block_id="toolu_01MWSfmhHKudgpnbzBQFDt98",
    )
    turn0 = response([thinking_block(), text_block(), lookup, entitlement])
    client = make_client([turn0, response([RESOLUTION_CALL])])

    outcome = run_act(TICKET, CLASSIFY, RETRIEVAL, FakeTracer(), _client=client)

    assert outcome.resolution.resolution_type == "deny"
    assert outcome.entitlement_denied is True  # basic plan, priority_vpn_support => covered False
    second_call_messages = client.messages.calls[1]["messages"]
    tool_result_msg = second_call_messages[-1]
    assert tool_result_msg["role"] == "user"
    result_ids = {r["tool_use_id"] for r in tool_result_msg["content"]}
    assert result_ids == {lookup.id, entitlement.id}
    assert len(tool_result_msg["content"]) == 2


def test_submit_resolution_with_parallel_entitlement_check(monkeypatch):
    """Adverse-action hardening: submit_resolution and check_entitlement can arrive
    in the same response with submit_resolution FIRST in content order. The loop
    must still execute check_entitlement (never skip it because submit came first)
    so entitlement_denied is set before the outcome is returned."""
    from triagedesk.pipeline import act

    calls = {"n": 0}

    def fake_execute_tool(name, tool_input):
        calls["n"] += 1
        assert name == "check_entitlement"
        return {"customer_ref": "customer-3", "feature": "dedicated_ip",
                "plan": "basic", "covered": False}

    monkeypatch.setattr(act, "execute_tool", fake_execute_tool)

    submit = tool_use_block("submit_resolution", {
        "resolution_type": "solve",
        "customer_reply": "Here's how to resolve your VPN issue.",
        "internal_rationale": "customer-3's VPN issue matches known fix.",
    }, block_id="toolu_submit")
    entitlement = tool_use_block(
        "check_entitlement",
        {"customer_ref": "customer-3", "feature": "dedicated_ip"},
        block_id="toolu_entitlement",
    )
    turn0 = response([thinking_block(), submit, entitlement])
    client = make_client([turn0])

    outcome = run_act(TICKET, CLASSIFY, RETRIEVAL, FakeTracer(), _client=client)

    assert outcome.resolution.resolution_type == "solve"
    assert outcome.entitlement_denied is True
    assert calls["n"] == 1  # entitlement tool was actually executed


def test_max_tokens_truncation_is_incomplete():
    """Mirrors fixture truncation-probe: stop_reason == 'max_tokens' with only
    thinking/text blocks and no tool_use. Must raise AgentIncompleteError, not
    crash on an unhandled stop_reason."""
    truncated = response([thinking_block(), text_block()], stop_reason="max_tokens")
    client = make_client([truncated])
    with pytest.raises(AgentIncompleteError):
        run_act(TICKET, CLASSIFY, RETRIEVAL, FakeTracer(), _client=client)
    assert len(client.messages.calls) == 1
