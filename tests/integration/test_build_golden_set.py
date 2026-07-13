import uuid

import pytest
from sqlalchemy import select

from scripts.build_golden_set import seed, seed_adversarial_tickets
from tests.conftest import integration
from triagedesk.evals.adversarial import ADVERSARIAL
from triagedesk.models import EvalCase, EvalResult, Run, Ticket


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


@integration
def test_seed_refuses_when_adversarial_runs_exist(test_db):
    # A run against an adversarial ticket is live trace evidence; the no-flag
    # path must exit 1 without touching the DB.
    seeded = seed_adversarial_tickets(test_db)
    tid = seeded[0][0]
    run = Run(ticket_id=tid, state="escalated", prompt_version="1.0",
              model="claude-sonnet-4-6")
    test_db.add(run)
    test_db.commit()

    with pytest.raises(SystemExit) as exc:
        seed(test_db)
    assert exc.value.code == 1

    test_db.rollback()
    assert test_db.execute(
        select(Run).where(Run.ticket_id == tid)).scalars().all()


@integration
def test_seed_refuses_when_eval_results_exist(test_db):
    # eval_results is the CI eval history (issue #9); the no-flag path must
    # exit 1 without deleting it.
    seeded = seed_adversarial_tickets(test_db)
    tid = seeded[0][0]
    case = EvalCase(ticket_id=tid, kind="adversarial", expected_outcome="escalate")
    test_db.add(case)
    test_db.flush()
    test_db.add(EvalResult(eval_run_id=uuid.uuid4(), case_id=case.id,
                           predicted_outcome="escalate"))
    test_db.commit()

    with pytest.raises(SystemExit) as exc:
        seed(test_db)
    assert exc.value.code == 1

    test_db.rollback()
    assert test_db.execute(select(EvalResult)).scalars().all()
