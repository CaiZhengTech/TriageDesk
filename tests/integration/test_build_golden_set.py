import json
import uuid

import pytest
from sqlalchemy import select

from scripts.build_golden_set import EXPECTATIONS, seed, seed_adversarial_tickets
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


@integration
def test_reset_history_reseed_never_deletes_calibration_pool_cases(test_db):
    """The calibration pool (issue #11, kind='calibration', see
    scripts/build_calibration_pool.py) shares the eval_cases table with the
    golden set. --reset-history is documented as deleting eval_results plus
    the adversarial tickets' runs/spans -- it must not ALSO sweep up the
    pool's eval_cases rows as undocumented collateral damage. Audit finding
    from Task 6: the reseed's `delete(EvalCase)` was unscoped.

    seed()'s success path needs every golden_expectations.json ticket_id to
    already exist as a real Ticket row (the FK the real dataset normally
    satisfies) -- this test seeds minimal stand-in Ticket rows for each one
    so the reseed can run to completion inside the isolated test branch."""
    expectations = json.loads(EXPECTATIONS.read_text())
    for r in expectations:
        test_db.add(Ticket(id=r["ticket_id"], subject="s", body="b",
                            queue=r["expected_queue"], language="en", source="kaggle"))

    pool_ticket = Ticket(subject="s", body="b", queue="Billing and Payments",
                          language="en", source="kaggle")
    test_db.add(pool_ticket)
    test_db.flush()
    pool_case = EvalCase(ticket_id=pool_ticket.id, kind="calibration",
                          expected_outcome="unlabeled")
    test_db.add(pool_case)
    test_db.commit()

    seed(test_db, reset_history=True)

    surviving = test_db.execute(
        select(EvalCase).where(EvalCase.ticket_id == pool_ticket.id)
    ).scalar_one_or_none()
    assert surviving is not None
    assert surviving.kind == "calibration"
