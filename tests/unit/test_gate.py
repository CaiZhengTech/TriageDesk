from triagedesk.pipeline.act import ActOutcome
from triagedesk.pipeline.gate import classification_margin, decide
from triagedesk.schemas import Resolution


def res(rtype):
    return Resolution(resolution_type=rtype, customer_reply="r", internal_rationale="i")


def outcome(rtype="solve", denied=False):
    return ActOutcome(resolution=res(rtype), entitlement_denied=denied)


CENTROIDS = {"IT Support": [1.0, 0.0], "Billing and Payments": [0.0, 1.0]}


def test_margin_positive_when_near_predicted_centroid():
    m = classification_margin([0.9, 0.1], "IT Support", CENTROIDS)
    assert m > 0.5


def test_margin_negative_when_nearer_another_centroid():
    m = classification_margin([0.1, 0.9], "IT Support", CENTROIDS)
    assert m < 0


def test_confident_solve_auto_resolves():
    d = decide(retrieval_similarity=0.8, margin=0.3, outcome=outcome("solve"))
    assert d.auto_resolve is True
    assert d.signals == {"retrieval_similarity": 0.8, "classification_margin": 0.3}


def test_low_similarity_escalates():
    d = decide(retrieval_similarity=0.2, margin=0.3, outcome=outcome("solve"))
    assert d.auto_resolve is False
    assert d.reason == "low_confidence"


def test_low_margin_escalates():
    d = decide(retrieval_similarity=0.8, margin=0.0, outcome=outcome("solve"))
    assert d.auto_resolve is False
    assert d.reason == "low_confidence"


def test_deny_always_escalates_even_when_confident():
    d = decide(retrieval_similarity=0.99, margin=0.9, outcome=outcome("deny"))
    assert d.auto_resolve is False
    assert d.reason == "adverse_action"


def test_entitlement_denial_always_escalates():
    d = decide(retrieval_similarity=0.99, margin=0.9, outcome=outcome("solve", denied=True))
    assert d.auto_resolve is False
    assert d.reason == "adverse_action"


def test_needs_human_escalates():
    d = decide(retrieval_similarity=0.99, margin=0.9, outcome=outcome("needs_human"))
    assert d.auto_resolve is False
    assert d.reason == "agent_requested_human"
