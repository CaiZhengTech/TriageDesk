import json
from pathlib import Path

import pytest

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
# range, so they could not be rebuilt and had to be replaced. These tests fail
# loudly if that ever becomes true again.
#
# Two layers, deliberately. The source CSV is a ~19 MB CC-BY-NC HuggingFace dataset
# clone that is gitignored and absent in CI, so the deep check can only run where
# the data is. The cheap invariant below catches the exact failure mode without it
# and therefore runs everywhere — which matters, because a guard that only runs on
# one laptop is the same class of problem as seed data that only exists on one.

EXPECTATIONS = json.loads(
    (Path(__file__).parents[2] / "triagedesk" / "evals" /
     "golden_expectations.json").read_text()
)

# Rows surviving ingest_tickets' English/non-empty-body filter over the pinned
# dataset revision. Asserted against the real CSV by the deep check below.
KAGGLE_INGEST_ROWS = 11922


def test_no_representative_case_sits_above_the_ingest_range():
    """The cheap invariant, and the one that actually failed in August 2026: a
    golden id above the ingest range cannot have come from the dataset, so it was
    inserted by hand and dies with the database. Needs no CSV, so it runs in CI."""
    strays = [r["ticket_id"] for r in EXPECTATIONS
              if r["ticket_id"] > KAGGLE_INGEST_ROWS]
    assert not strays, (
        f"golden ids {strays} are above the ingest range ({KAGGLE_INGEST_ROWS}) — "
        "hand-inserted cases cannot be rebuilt; see docs/week-4-launch/reports/"
        "task-db-rebuild.md"
    )


def _ingested_tickets():
    """Replay ingest_tickets' filter over the source CSV. Ticket ids are the
    1-based insertion order of the surviving rows, so index i is id i+1."""
    import csv

    from scripts.ingest_tickets import DEFAULT_CSV, row_to_ticket

    if not Path(DEFAULT_CSV).exists():
        pytest.skip(
            f"{DEFAULT_CSV} not present (gitignored CC-BY-NC dataset clone). "
            "Clone https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets "
            "into data/customer-support-tickets to run the deep check."
        )

    out = []
    with open(DEFAULT_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ticket = row_to_ticket(row)
            if ticket is not None:
                out.append(ticket)
    return out


def test_every_representative_case_is_rebuildable_from_the_dataset():
    """The deep check: each golden ticket must be one the ingest actually recreates,
    at the same id, in the same queue. Skipped where the dataset clone is absent."""
    tickets = _ingested_tickets()
    assert len(tickets) == KAGGLE_INGEST_ROWS, (
        f"the pinned dataset revision now yields {len(tickets)} rows, not "
        f"{KAGGLE_INGEST_ROWS} — every golden ticket id has shifted"
    )
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
