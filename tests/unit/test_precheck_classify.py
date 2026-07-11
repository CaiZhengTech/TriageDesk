from types import SimpleNamespace

from triagedesk.pipeline.classify import run_classify
from triagedesk.pipeline.precheck import run_precheck
from triagedesk.schemas import ClassifyResult, PrecheckVerdict

TICKET = SimpleNamespace(
    id=1, subject="My VPN keeps disconnecting",
    body="Client demo at 3pm and my VPN drops every few minutes.",
)


class FakeSpan:
    def __init__(self):
        self.attributes = {}


class FakeTracer:
    def __init__(self):
        self.spans = []
        self.usage_calls = []

    def span(self, name):
        from contextlib import contextmanager

        @contextmanager
        def cm():
            s = FakeSpan()
            self.spans.append((name, s))
            yield s

        return cm()

    def record_llm_usage(self, span, response):
        span.attributes["recorded"] = True
        self.usage_calls.append((span, response))

    def set_attributes(self, span, **attrs):
        span.attributes.update(attrs)


def fake_call_returning(parsed):
    def _call(**kwargs):
        return parsed, [SimpleNamespace(model="claude-sonnet-4-6", usage=None)]

    return _call


def test_precheck_safe_ticket():
    tracer = FakeTracer()
    verdict = run_precheck(TICKET, tracer, _call=fake_call_returning(PrecheckVerdict(safe=True)))
    assert verdict.safe is True
    assert tracer.spans[0][0] == "precheck"
    assert tracer.spans[0][1].attributes["triage.precheck.safe"] is True
    assert len(tracer.usage_calls) == 1


def test_precheck_injection_flagged():
    tracer = FakeTracer()
    verdict = run_precheck(
        TICKET, tracer,
        _call=fake_call_returning(
            PrecheckVerdict(safe=False, category="injection", reason="prompt override attempt")
        ),
    )
    assert verdict.safe is False
    assert verdict.category == "injection"


def test_classify_records_queue():
    tracer = FakeTracer()
    result = run_classify(
        TICKET, tracer,
        _call=fake_call_returning(ClassifyResult(queue="IT Support", category="vpn")),
    )
    assert result.queue == "IT Support"
    assert tracer.spans[0][1].attributes["triage.classify.queue"] == "IT Support"


def test_classify_records_usage_for_every_response():
    tracer = FakeTracer()

    def _call_multi_response(**kwargs):
        parsed = ClassifyResult(queue="IT Support", category="vpn")
        responses = [
            SimpleNamespace(model="claude-sonnet-4-6", usage=None),
            SimpleNamespace(model="claude-sonnet-4-6", usage=None),
        ]
        return parsed, responses

    result = run_classify(TICKET, tracer, _call=_call_multi_response)
    assert result.queue == "IT Support"
    assert result.category == "vpn"
    assert len(tracer.usage_calls) == 2
