"""cache_control breakpoints on the stable prefixes (act-loop system + tools,
structured_call system). Shapes mirror tests/fixtures/sdk_structured_output_caching.json."""
from types import SimpleNamespace

from tests.unit.test_act_loop import (
    CLASSIFY,
    RESOLUTION_CALL,
    RETRIEVAL,
    TICKET,
    make_client,
    response,
)
from tests.unit.test_precheck_classify import FakeTracer
from triagedesk.llm import structured_call
from triagedesk.pipeline.act import run_act
from triagedesk.schemas import PrecheckVerdict
from triagedesk.tools import TOOL_DEFS


def test_submit_resolution_carries_cache_breakpoint():
    assert TOOL_DEFS[-1]["name"] == "submit_resolution"
    assert TOOL_DEFS[-1]["cache_control"] == {"type": "ephemeral"}


def test_act_loop_sends_cached_system_block():
    client = make_client([response([RESOLUTION_CALL])])
    run_act(TICKET, CLASSIFY, RETRIEVAL, FakeTracer(), _client=client)
    system = client.messages.calls[0]["system"]
    assert isinstance(system, list)
    assert system[-1]["cache_control"] == {"type": "ephemeral"}
    tools = client.messages.calls[0]["tools"]
    assert tools[-1]["cache_control"] == {"type": "ephemeral"}


def test_structured_call_sends_cached_system_block():
    good = PrecheckVerdict(safe=True).model_dump_json()
    resp = SimpleNamespace(
        stop_reason="end_turn", model="claude-sonnet-4-6",
        content=[SimpleNamespace(type="text", text=good)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5,
                              cache_creation_input_tokens=0, cache_read_input_tokens=0),
    )
    client = SimpleNamespace(messages=SimpleNamespace(
        create=lambda **k: setattr(client, "last", k) or resp))
    structured_call(system="s", user="u", schema=PrecheckVerdict, _client=client)
    system = client.last["system"]
    assert isinstance(system, list)
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert system[0]["text"] == "s"
