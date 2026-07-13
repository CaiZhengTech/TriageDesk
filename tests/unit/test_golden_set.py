import json
from pathlib import Path

from triagedesk.evals.adversarial import ADVERSARIAL
from triagedesk.tools import PLAN_ENTITLEMENTS

SEED_ACCOUNTS = json.loads(
    (Path(__file__).parents[2] / "triagedesk" / "seed_accounts.json").read_text()
)


def test_five_adversarial_kinds_present():
    kinds = {a["adversarial_kind"] for a in ADVERSARIAL}
    assert kinds == {"injection", "pii", "off_topic", "ambiguous", "entitlement_denial"}


def test_every_adversarial_expects_escalation():
    assert all(a["expected_outcome"] == "escalate" for a in ADVERSARIAL)


def test_entitlement_trap_is_soft_denial():
    trap = next(a for a in ADVERSARIAL if a["adversarial_kind"] == "entitlement_denial")
    assert trap["expected_escalation_reason"] == "no_entitlement_evidence"
    assert "Basic plan" in trap["body"]  # tempts a solve+embedded-denial without a check


def test_every_adversarial_spec_has_a_pinned_ticket_id():
    # Ids must be fixed (not left to autoincrement) so the id -> account
    # mapping (ticket.id % 12) is stable across reseeds, and reserved well
    # above the ~12k-row Kaggle+demo dataset so they never collide.
    for spec in ADVERSARIAL:
        assert "ticket_id" in spec, f"{spec['adversarial_kind']} spec has no pinned ticket_id"
        assert spec["ticket_id"] >= 90000

    ids = [spec["ticket_id"] for spec in ADVERSARIAL]
    assert len(ids) == len(set(ids)), "pinned ticket_ids must be unique"


def test_entitlement_trap_ticket_id_resolves_to_an_unentitled_basic_account():
    # The act loop derives customer_ref as f"customer-{ticket.id % 12}"
    # (triagedesk/tools.py). The trap only works if that account is on a
    # plan that genuinely does NOT include the requested feature -- otherwise
    # the "trap" is just a legitimate grant.
    trap = next(a for a in ADVERSARIAL if a["adversarial_kind"] == "entitlement_denial")
    customer_ref = f"customer-{trap['ticket_id'] % 12}"
    account = SEED_ACCOUNTS[customer_ref]

    assert account["plan"] == "basic"
    assert "priority_vpn_support" not in PLAN_ENTITLEMENTS[account["plan"]]
