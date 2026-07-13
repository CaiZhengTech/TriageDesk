from sqlalchemy import select

from scripts.build_golden_set import seed_adversarial_tickets
from tests.conftest import integration
from triagedesk.evals.adversarial import ADVERSARIAL
from triagedesk.models import EvalCase, Ticket


@integration
def test_seed_adversarial_tickets_is_idempotent(test_db):
    # Running the seeder twice must converge to the same pinned ids and row
    # counts, not grow new orphaned ticket rows on every reseed.
    first = seed_adversarial_tickets(test_db)
    for tid, spec in first:
        test_db.add(EvalCase(ticket_id=tid, kind="adversarial",
                              expected_outcome=spec["expected_outcome"],
                              expected_queue=spec["expected_queue"],
                              adversarial_kind=spec["adversarial_kind"],
                              expected_escalation_reason=spec["expected_escalation_reason"],
                              notes=spec["notes"]))
    test_db.commit()

    second = seed_adversarial_tickets(test_db)
    for tid, spec in second:
        test_db.add(EvalCase(ticket_id=tid, kind="adversarial",
                              expected_outcome=spec["expected_outcome"],
                              expected_queue=spec["expected_queue"],
                              adversarial_kind=spec["adversarial_kind"],
                              expected_escalation_reason=spec["expected_escalation_reason"],
                              notes=spec["notes"]))
    test_db.commit()

    assert [tid for tid, _ in first] == [tid for tid, _ in second]

    pinned_ids = [spec["ticket_id"] for spec in ADVERSARIAL]
    tickets = test_db.execute(
        select(Ticket).where(Ticket.id.in_(pinned_ids))
    ).scalars().all()
    eval_cases = test_db.execute(
        select(EvalCase).where(EvalCase.ticket_id.in_(pinned_ids))
    ).scalars().all()

    assert len(tickets) == len(ADVERSARIAL)
    assert len(eval_cases) == len(ADVERSARIAL)
