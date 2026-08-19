"""The demo pool spec must be self-consistent and repo-owned (issue #64).

The original pool (12023/12027/12039) was created ad hoc in a Neon dev branch and
propagated only by copy-on-write branching. When the free-tier branches expired,
the pool was unrecoverable — no script had ever existed for it. These tests pin
the properties that made the old pool fragile so it can't happen silently again.
"""

import pytest

from triagedesk.demo_pool import DEMO_POOL
from triagedesk.evals.adversarial import ADVERSARIAL
from triagedesk.tools import PLAN_ENTITLEMENTS, check_entitlement, customer_ref_for

KAGGLE_MAX_ID = 11922  # rows surviving ingest_tickets' English/non-empty-body filter


class _FakeTicket:
    def __init__(self, ticket_id):
        self.id = ticket_id


def test_pool_is_not_empty():
    assert len(DEMO_POOL) >= 3


def test_every_entry_has_the_required_fields():
    for spec in DEMO_POOL:
        assert set(spec) >= {
            "ticket_id", "subject", "body", "queue",
            "expected_customer_ref", "expected_gate_outcome", "why",
        }, spec.get("subject")
        assert spec["subject"].strip()
        assert spec["body"].strip()
        assert spec["why"].strip()


def test_ticket_ids_are_unique():
    ids = [s["ticket_id"] for s in DEMO_POOL]
    assert len(ids) == len(set(ids))


def test_ids_sit_above_the_kaggle_range():
    """Demo tickets are seeded at pinned ids. If any landed inside the ingest's
    auto-increment range it would collide with a real Kaggle ticket, which is how
    a golden-set case (12027) ended up unreproducible in the first place."""
    for spec in DEMO_POOL:
        assert spec["ticket_id"] > KAGGLE_MAX_ID, spec["subject"]


def test_ids_do_not_collide_with_the_adversarial_band():
    adversarial_ids = {s["ticket_id"] for s in ADVERSARIAL}
    for spec in DEMO_POOL:
        assert spec["ticket_id"] not in adversarial_ids


def test_pinned_id_resolves_to_the_intended_customer():
    """`customer_ref_for` is `id % 12`, so a ticket's id silently decides whose
    account (and therefore whose PLAN) the act loop reads. Every pinned id must
    resolve to the customer the scenario was written for — otherwise the ticket
    still runs but tests something entirely different."""
    for spec in DEMO_POOL:
        actual = customer_ref_for(_FakeTicket(spec["ticket_id"]))
        assert actual == spec["expected_customer_ref"], (
            f"{spec['subject']!r}: id {spec['ticket_id']} -> {actual}, "
            f"scenario needs {spec['expected_customer_ref']}"
        )


def test_pool_demonstrates_both_gate_outcomes():
    """The whole point of issue #62: a pool where everything escalates cannot show
    that the gate is capable of auto-resolving. At least one of each."""
    outcomes = {s["expected_gate_outcome"] for s in DEMO_POOL}
    assert "auto_resolve" in outcomes
    assert "escalate" in outcomes


@pytest.mark.parametrize("spec", DEMO_POOL, ids=lambda s: str(s["ticket_id"]))
def test_entitlement_evidence_matches_the_intended_outcome(spec):
    """The gate escalates a `solve` that carries no positive entitlement evidence
    (`no_entitlement_evidence`) and escalates unconditionally when an entitlement
    check comes back False (`adverse_action`). So an auto-resolve scenario's plan
    MUST cover the feature its ticket is about, and an entitlement-denial scenario's
    MUST NOT. This asserts the seed data agrees with the scenario's stated intent
    — it does not assert what the model will actually do."""
    feature = spec.get("entitlement_feature")
    if feature is None:
        return
    assert feature in {f for feats in PLAN_ENTITLEMENTS.values() for f in feats}

    ref = customer_ref_for(_FakeTicket(spec["ticket_id"]))
    covered = check_entitlement(ref, feature)["covered"]

    if spec["expected_gate_outcome"] == "auto_resolve":
        assert covered, (
            f"{spec['subject']!r} is meant to auto-resolve, but {ref}'s plan does "
            f"not cover {feature!r} — the gate would escalate it as adverse_action"
        )
    else:
        assert not covered, (
            f"{spec['subject']!r} is meant to escalate on entitlement, but {ref}'s "
            f"plan DOES cover {feature!r}"
        )
