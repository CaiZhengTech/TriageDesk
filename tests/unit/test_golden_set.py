from triagedesk.evals.adversarial import ADVERSARIAL


def test_five_adversarial_kinds_present():
    kinds = {a["adversarial_kind"] for a in ADVERSARIAL}
    assert kinds == {"injection", "pii", "off_topic", "ambiguous", "entitlement_denial"}


def test_every_adversarial_expects_escalation():
    assert all(a["expected_outcome"] == "escalate" for a in ADVERSARIAL)


def test_entitlement_trap_is_soft_denial():
    trap = next(a for a in ADVERSARIAL if a["adversarial_kind"] == "entitlement_denial")
    assert trap["expected_escalation_reason"] == "no_entitlement_evidence"
    assert "Basic plan" in trap["body"]  # tempts a solve+embedded-denial without a check
