from types import SimpleNamespace

import pytest

from triagedesk.llm import LLMRefusalError, RepairFailedError, structured_call
from triagedesk.schemas import PrecheckVerdict


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def fake_response(text, stop_reason="end_turn"):
    content = [text_block(text)] if text is not None else []
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content,
        model="claude-sonnet-4-6",
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=20,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        ),
    )


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def make_client(responses):
    return SimpleNamespace(messages=FakeMessages(responses))


GOOD_JSON = PrecheckVerdict(safe=True).model_dump_json()
BAD_JSON = "{}"  # missing required field `safe`


def test_first_try_success():
    client = make_client([fake_response(GOOD_JSON)])
    parsed, responses = structured_call(
        system="s", user="u", schema=PrecheckVerdict, _client=client
    )
    assert parsed.safe is True
    assert len(responses) == 1

    kwargs = client.messages.calls[0]
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    # temperature is omitted here because this test's own call doesn't pass
    # one -- structured_call's pass-through contract is exercised directly by
    # test_schema_objects_forbid_additional_properties's siblings below and by
    # the pinned-temperature tests in test_precheck_classify.py/test_judge.py.
    # Whether "no temperature" is the RIGHT choice for a given caller is an
    # act-loop concern (Hardening Task 2) -- see test_act_loop.py.
    assert "thinking" not in kwargs
    assert "effort" not in kwargs


def test_one_repair_then_success():
    client = make_client([fake_response(BAD_JSON), fake_response(GOOD_JSON)])
    parsed, responses = structured_call(
        system="s", user="u", schema=PrecheckVerdict, _client=client
    )
    assert parsed.safe is True
    assert len(responses) == 2
    assert len(client.messages.calls) == 2  # exactly one repair

    second_messages = client.messages.calls[1]["messages"]
    assert len(second_messages) == 3
    assert [m["role"] for m in second_messages] == ["user", "assistant", "user"]

    final_user_content = second_messages[2]["content"]
    assert "PrecheckVerdict" in final_user_content
    assert "Field required" in final_user_content or "safe" in final_user_content


def test_repair_failure_escalates():
    client = make_client([fake_response(BAD_JSON), fake_response(BAD_JSON)])
    with pytest.raises(RepairFailedError) as excinfo:
        structured_call(system="s", user="u", schema=PrecheckVerdict, _client=client)
    assert len(client.messages.calls) == 2  # never a third attempt
    assert len(excinfo.value.responses) == 2


def test_schema_objects_forbid_additional_properties():
    """The live API rejects output_config schemas whose object types lack an
    explicit additionalProperties: false (found in the Week-1 E2E checkpoint;
    Pydantic's model_json_schema() does not emit it)."""
    client = make_client([fake_response(GOOD_JSON)])
    structured_call(system="s", user="u", schema=PrecheckVerdict, _client=client)
    schema = client.messages.calls[0]["output_config"]["format"]["schema"]
    assert schema["additionalProperties"] is False


def test_refusal_raises():
    client = make_client([fake_response(None, stop_reason="refusal")])
    with pytest.raises(LLMRefusalError) as excinfo:
        structured_call(system="s", user="u", schema=PrecheckVerdict, _client=client)
    assert len(excinfo.value.responses) == 1
