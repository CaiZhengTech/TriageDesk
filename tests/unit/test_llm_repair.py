from types import SimpleNamespace

import pytest

from triagedesk.llm import LLMRefusalError, RepairFailedError, structured_call
from triagedesk.schemas import PrecheckVerdict


def fake_response(parsed, stop_reason="end_turn"):
    return SimpleNamespace(
        parsed_output=parsed,
        stop_reason=stop_reason,
        model="claude-sonnet-4-6",
        usage=SimpleNamespace(input_tokens=100, output_tokens=20,
                              cache_creation_input_tokens=0, cache_read_input_tokens=0),
        content=[],
    )


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def make_client(responses):
    return SimpleNamespace(messages=FakeMessages(responses))


GOOD = PrecheckVerdict(safe=True)


def test_first_try_success():
    client = make_client([fake_response(GOOD)])
    parsed, responses = structured_call(
        system="s", user="u", schema=PrecheckVerdict, _client=client
    )
    assert parsed.safe is True
    assert len(responses) == 1


def test_one_repair_then_success():
    client = make_client([fake_response(None), fake_response(GOOD)])
    parsed, responses = structured_call(
        system="s", user="u", schema=PrecheckVerdict, _client=client
    )
    assert parsed.safe is True
    assert len(responses) == 2
    assert len(client.messages.calls) == 2  # exactly one repair


def test_repair_failure_escalates():
    client = make_client([fake_response(None), fake_response(None)])
    with pytest.raises(RepairFailedError):
        structured_call(system="s", user="u", schema=PrecheckVerdict, _client=client)
    assert len(client.messages.calls) == 2  # never a third attempt


def test_refusal_raises():
    client = make_client([fake_response(None, stop_reason="refusal")])
    with pytest.raises(LLMRefusalError):
        structured_call(system="s", user="u", schema=PrecheckVerdict, _client=client)
