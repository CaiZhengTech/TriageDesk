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


# --- reproducibility of the representative half (issue #64) ---------------
#
# The Neon free-tier branches expired and took the database with them. Two golden
# cases (12027, 11964) turned out to have been hand-inserted above the Kaggle id
# range, so they could not be rebuilt from the repo and had to be replaced. These
# tests fail loudly if that ever becomes true again.

EXPECTATIONS = json.loads(
    (Path(__file__).parents[2] / "triagedesk" / "evals" /
     "golden_expectations.json").read_text()
)


def _ingested_tickets():
    """Replay ingest_tickets' filter over the source CSV. Ticket ids are the
    1-based insertion order of the surviving rows, so index i is id i+1."""
    import csv

    from scripts.ingest_tickets import DEFAULT_CSV, row_to_ticket

    out = []
    with open(DEFAULT_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ticket = row_to_ticket(row)
            if ticket is not None:
                out.append(ticket)
    return out


def test_every_representative_case_is_rebuildable_from_the_repo():
    """Each golden ticket must be one the ingest script actually recreates, at the
    same id, in the same queue. A case that only exists because someone inserted a
    row by hand is unrecoverable the moment the database is."""
    tickets = _ingested_tickets()
    problems = []
    for row in EXPECTATIONS:
        tid = row["ticket_id"]
        if tid > len(tickets):
            problems.append(f"id {tid} is above the ingest range ({len(tickets)})")
            continue
        actual = tickets[tid - 1].queue
        if actual != row["expected_queue"]:
            problems.append(
                f"id {tid}: expected_queue {row['expected_queue']!r} but the ingest "
                f"produces {actual!r}"
            )
    assert not problems, "golden set is not reproducible:\n  " + "\n  ".join(problems)


def test_outcome_balance_is_preserved():
    """Escalation precision is only measurable against cases that SHOULD route.
    If the route cases erode to zero, 'escalation recall 1.0' becomes a tautology
    again — the exact complaint the Week-2.5 council raised."""
    outcomes = [r["expected_outcome"] for r in EXPECTATIONS]
    assert len(EXPECTATIONS) == 20
    assert outcomes.count("route") == 3
    assert outcomes.count("escalate") == 17
