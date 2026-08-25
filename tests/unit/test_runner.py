from types import SimpleNamespace

import anthropic
import httpx
import pytest

from triagedesk.llm import LLMRefusalError, RepairFailedError
from triagedesk.pipeline import runner
from triagedesk.pipeline.act import ActOutcome, AgentIncompleteError, ToolFailedError
from triagedesk.schemas import ClassifyResult, PrecheckVerdict, Resolution
from triagedesk.tracing import BudgetExceededError, CostUnknownError

TICKET = SimpleNamespace(id=3, subject="My VPN keeps disconnecting",
                         body="Client demo at 3pm and my VPN drops every few minutes.")


class FakeSession:
    """No real DB — get() returns the fixed ticket, add/commit are no-ops."""

    def __init__(self, ticket=TICKET):
        self.ticket = ticket
        self.added = []

    def get(self, model, id):
        return self.ticket

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass


def resolution(rtype="solve"):
    return Resolution(resolution_type=rtype, customer_reply="reply", internal_rationale="why")


def outcome(rtype="solve", denied=False, checked=True):
    return ActOutcome(resolution=resolution(rtype), entitlement_denied=denied,
                       entitlement_checked=checked)


def patch_happy_stages(monkeypatch, *, act_outcome=None, top_similarity=0.8, margin=0.3):
    """Wire precheck/classify/retrieve/act to fakes and pin the gate's
    external classification-margin signal (centroid math is gate.py's own
    concern, already covered by test_gate.py)."""
    monkeypatch.setattr(runner, "run_precheck",
                         lambda ticket, tracer: PrecheckVerdict(safe=True))
    monkeypatch.setattr(runner, "run_classify",
                         lambda ticket, tracer: ClassifyResult(queue="IT Support", category="vpn"))
    monkeypatch.setattr(runner, "run_retrieve",
                         lambda ticket, tracer, session: SimpleNamespace(
                             docs=[], top_similarity=top_similarity, query_embedding=[0.0]))
    monkeypatch.setattr(runner, "run_act",
                         lambda ticket, classify_result, retrieval, tracer: (
                             act_outcome or outcome()))
    monkeypatch.setattr(runner, "classification_margin", lambda *a, **k: margin)
    monkeypatch.setattr(runner, "load_centroids", lambda: {})


def test_precheck_unsafe_escalates_without_running_later_stages(monkeypatch):
    monkeypatch.setattr(runner, "run_precheck",
                         lambda ticket, tracer: PrecheckVerdict(safe=False, category="injection"))

    def boom(*a, **k):
        pytest.fail("classify must not run after an unsafe precheck")

    monkeypatch.setattr(runner, "run_classify", boom)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "escalated"
    assert run.escalation_reason == "precheck_injection"


def test_confident_solve_completes(monkeypatch):
    patch_happy_stages(monkeypatch, act_outcome=outcome("solve"),
                       top_similarity=0.8, margin=0.3)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "completed"
    assert run.escalation_reason is None
    assert run.final_reply == "reply"


def test_low_confidence_escalates(monkeypatch):
    patch_happy_stages(monkeypatch, act_outcome=outcome("solve"),
                       top_similarity=0.1, margin=0.3)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "escalated"
    assert run.escalation_reason == "low_confidence"


def test_adverse_action_never_auto_resolves(monkeypatch):
    patch_happy_stages(monkeypatch, act_outcome=outcome("deny"),
                       top_similarity=0.99, margin=0.9)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "escalated"
    assert run.escalation_reason == "adverse_action"


def test_agent_requested_human_escalates(monkeypatch):
    patch_happy_stages(monkeypatch, act_outcome=outcome("needs_human"),
                       top_similarity=0.99, margin=0.9)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "escalated"
    assert run.escalation_reason == "agent_requested_human"


def test_solve_granting_a_gated_feature_without_evidence_escalates(monkeypatch):
    """The soft-denial shape the rule exists for: the reply promises a
    plan-gated feature with no check_entitlement receipt behind it. Scoped to
    gated features in #69 — see the sibling test for the informational case."""
    promise = ActOutcome(
        resolution=Resolution(resolution_type="solve",
                              customer_reply="No problem — I've enabled API access for you.",
                              internal_rationale="i"),
        entitlement_denied=False, entitlement_checked=False)
    patch_happy_stages(monkeypatch, act_outcome=promise,
                       top_similarity=0.8, margin=0.3)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "escalated"
    assert run.escalation_reason == "no_entitlement_evidence"


def test_informational_solve_auto_resolves_without_an_entitlement_check(monkeypatch):
    """The 80011 case, end to end through the runner: the ticket implicates no
    plan-gated feature, so there is no receipt to demand and a KB-grounded
    answer completes instead of escalating."""
    informational = ActOutcome(
        resolution=Resolution(resolution_type="solve",
                              customer_reply="Use the self-service unlock link to get back in.",
                              internal_rationale="i"),
        entitlement_denied=False, entitlement_checked=False)
    session = FakeSession(SimpleNamespace(
        id=3, subject="Locked out after too many password attempts",
        body="I mistyped my password a few times and now the portal says I am locked."))
    patch_happy_stages(monkeypatch, act_outcome=informational,
                       top_similarity=0.8, margin=0.3)
    run = runner.run_ticket(3, session)
    assert run.state == "completed"
    assert run.escalation_reason is None


def test_budget_exceeded_maps_to_escalated_budget_breach(monkeypatch):
    monkeypatch.setattr(runner, "run_precheck",
                         lambda ticket, tracer: PrecheckVerdict(safe=True))

    def boom(ticket, tracer):
        raise BudgetExceededError("run cost exceeds cap")

    monkeypatch.setattr(runner, "run_classify", boom)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "escalated"
    assert run.escalation_reason == "budget_breach"
    assert "BudgetExceededError" in run.internal_rationale


def test_cost_unknown_maps_to_escalated_budget_breach(monkeypatch):
    monkeypatch.setattr(runner, "run_precheck",
                         lambda ticket, tracer: PrecheckVerdict(safe=True))

    def boom(ticket, tracer):
        raise CostUnknownError("response missing model/usage")

    monkeypatch.setattr(runner, "run_classify", boom)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "escalated"
    assert run.escalation_reason == "budget_breach"
    assert "CostUnknownError" in run.internal_rationale


def test_repair_failed_maps_to_escalated_validation_failed(monkeypatch):
    def boom(ticket, tracer):
        raise RepairFailedError("structured output failed validation twice")

    monkeypatch.setattr(runner, "run_precheck", boom)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "escalated"
    assert run.escalation_reason == "validation_failed"


def test_llm_refusal_maps_to_escalated_llm_refusal(monkeypatch):
    def boom(ticket, tracer):
        raise LLMRefusalError("model refused the request")

    monkeypatch.setattr(runner, "run_precheck", boom)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "escalated"
    assert run.escalation_reason == "llm_refusal"


def test_tool_failed_maps_to_escalated_tool_error(monkeypatch):
    monkeypatch.setattr(runner, "run_precheck",
                         lambda ticket, tracer: PrecheckVerdict(safe=True))
    monkeypatch.setattr(runner, "run_classify",
                         lambda ticket, tracer: ClassifyResult(queue="IT Support", category="vpn"))
    monkeypatch.setattr(runner, "run_retrieve",
                         lambda ticket, tracer, session: SimpleNamespace(
                             docs=[], top_similarity=0.8, query_embedding=[0.0]))

    def boom(ticket, classify_result, retrieval, tracer):
        raise ToolFailedError("lookup_account_status failed twice")

    monkeypatch.setattr(runner, "run_act", boom)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "escalated"
    assert run.escalation_reason == "tool_error"


def test_agent_incomplete_maps_to_escalated_agent_incomplete(monkeypatch):
    monkeypatch.setattr(runner, "run_precheck",
                         lambda ticket, tracer: PrecheckVerdict(safe=True))
    monkeypatch.setattr(runner, "run_classify",
                         lambda ticket, tracer: ClassifyResult(queue="IT Support", category="vpn"))
    monkeypatch.setattr(runner, "run_retrieve",
                         lambda ticket, tracer, session: SimpleNamespace(
                             docs=[], top_similarity=0.8, query_embedding=[0.0]))

    def boom(ticket, classify_result, retrieval, tracer):
        raise AgentIncompleteError("no resolution after 5 iterations")

    monkeypatch.setattr(runner, "run_act", boom)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "escalated"
    assert run.escalation_reason == "agent_incomplete"


def test_anthropic_api_error_maps_to_failed(monkeypatch):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

    def boom(ticket, tracer):
        raise anthropic.APIConnectionError(request=request)

    monkeypatch.setattr(runner, "run_precheck", boom)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "failed"
    assert run.escalation_reason.startswith("api_error:")


def test_unexpected_exception_maps_to_failed(monkeypatch):
    def boom(ticket, tracer):
        raise RuntimeError("boom")

    monkeypatch.setattr(runner, "run_precheck", boom)
    run = runner.run_ticket(3, FakeSession())
    assert run.state == "failed"
    assert run.escalation_reason == "unexpected:RuntimeError"
    assert "RuntimeError" in run.internal_rationale


# --- provider errors must not be labelled "unexpected" (#81) ---------------

def test_embedding_rate_limit_is_recorded_as_an_api_error_not_unexpected(monkeypatch):
    """Real production defect. Four inbound runs died with
    `unexpected:RateLimitError` after Voyage's free-tier ceiling, because the
    runner only recognised `anthropic.APIError` and Voyage raises its own
    exception hierarchy.

    A provider rate limit is the most EXPECTED failure a hosted pipeline has.
    Labelling it `unexpected:` sends whoever reads the trace hunting for a bug
    that isn't there — the trace is the product here, so a misleading reason is
    a real defect, not cosmetics."""
    import voyageai.error as voyage_error

    monkeypatch.setattr(runner, "run_precheck",
                        lambda ticket, tracer: PrecheckVerdict(safe=True))
    monkeypatch.setattr(runner, "run_classify",
                        lambda ticket, tracer: ClassifyResult(queue="IT Support",
                                                              category="vpn"))

    def rate_limited(ticket, tracer, session):
        raise voyage_error.RateLimitError("3 RPM and 10K TPM")

    monkeypatch.setattr(runner, "run_retrieve", rate_limited)

    run = runner.run_ticket(3, FakeSession())

    assert run.state == "failed"
    assert run.escalation_reason == "api_error:RateLimitError"
    assert "unexpected" not in run.escalation_reason
