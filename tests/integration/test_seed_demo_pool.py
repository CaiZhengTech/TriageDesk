import uuid

import pytest
from sqlalchemy import select

from scripts.seed_demo_pool import POOL_IDS, seed
from tests.conftest import integration
from triagedesk.demo import list_demo_pool
from triagedesk.demo_pool import DEMO_POOL
from triagedesk.models import Run, Ticket


@integration
def test_seeding_is_idempotent(test_db):
    # The failure this guards: a reseeder that inserts instead of converging
    # grows duplicate pool rows on every deploy, and the demo's <select> fills
    # with repeats. Same delete-then-reinsert precedent as the adversarial seeder.
    seed(test_db)
    first = test_db.execute(
        select(Ticket.id).where(Ticket.id.in_(POOL_IDS)).order_by(Ticket.id)
    ).scalars().all()

    seed(test_db)
    second = test_db.execute(
        select(Ticket.id).where(Ticket.id.in_(POOL_IDS)).order_by(Ticket.id)
    ).scalars().all()

    assert first == second == sorted(POOL_IDS)
    assert len(second) == len(DEMO_POOL)


@integration
def test_seeded_tickets_are_visible_to_the_demo_pool_query(test_db):
    # triagedesk/demo.py's pool-only rule keys off source == 'demo'. If the
    # seeder wrote any other source the tickets would exist but the demo would
    # 404 on every one of them.
    seed(test_db)
    pool = list_demo_pool(test_db)

    assert {t["id"] for t in pool["tickets"]} == set(POOL_IDS)
    for ticket in test_db.execute(
        select(Ticket).where(Ticket.id.in_(POOL_IDS))
    ).scalars():
        assert ticket.source == "demo"


@integration
def test_reseeding_refuses_when_runs_exist(test_db):
    # A pooled ticket's runs are the trace evidence the console displays.
    # Deleting the ticket would orphan them, so the seeder must fail closed
    # rather than silently destroy history — mirroring build_golden_set's guard.
    seed(test_db)
    test_db.add(Run(id=uuid.uuid4(), ticket_id=POOL_IDS[0], state="escalated",
                    prompt_version="test", model="test"))
    test_db.commit()

    with pytest.raises(SystemExit):
        seed(test_db)

    # DB untouched: the ticket and its run both survive the refusal.
    assert test_db.get(Ticket, POOL_IDS[0]) is not None
    assert test_db.execute(
        select(Run).where(Run.ticket_id == POOL_IDS[0])
    ).scalars().all()


@integration
def test_reset_history_clears_runs_and_reseeds(test_db):
    seed(test_db)
    test_db.add(Run(id=uuid.uuid4(), ticket_id=POOL_IDS[0], state="escalated",
                    prompt_version="test", model="test"))
    test_db.commit()

    seed(test_db, reset_history=True)

    assert test_db.execute(
        select(Run).where(Run.ticket_id.in_(POOL_IDS))
    ).scalars().all() == []
    assert test_db.execute(
        select(Ticket.id).where(Ticket.id.in_(POOL_IDS))
    ).scalars().all() != []
