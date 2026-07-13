"""Integration tests for the calibration pool builder (issue #11, Task 6).
Mirrors tests/integration/test_build_golden_set.py's conventions: real
SQLAlchemy Core queries against the isolated Neon test branch (test_db),
no live Anthropic calls (run_ticket/judge_run are not exercised here --
that's covered by the run_pool unit tests in tests/unit/test_harness.py)."""
import uuid

import pytest
from sqlalchemy import select

from scripts.build_calibration_pool import (
    pool_history_exists,
    seed_pool,
    select_pool,
)
from tests.conftest import integration
from triagedesk.models import EvalCase, EvalResult, Ticket


def _add_ticket(session, id_, language="en", source="kaggle", queue="Billing and Payments"):
    session.add(Ticket(id=id_, subject="s", body="b", queue=queue,
                       language=language, source=source))


# ------------------------------------------------------------------ select_pool

@integration
def test_select_pool_excludes_golden_ticket_ids_and_is_deterministic(test_db):
    for tid in range(1, 11):
        _add_ticket(test_db, tid)
    test_db.flush()
    # 3 and 7 are golden -- must never appear in the pool
    test_db.add(EvalCase(ticket_id=3, kind="representative", expected_outcome="route"))
    test_db.add(EvalCase(ticket_id=7, kind="adversarial", expected_outcome="escalate"))
    test_db.commit()

    first = select_pool(test_db)
    second = select_pool(test_db)

    assert first == second  # deterministic (seeded RNG)
    assert set(first) == {1, 2, 4, 5, 6, 8, 9, 10}
    assert set(first).isdisjoint({3, 7})
    assert first == sorted(first)


@integration
def test_select_pool_excludes_non_english_and_non_kaggle_tickets(test_db):
    _add_ticket(test_db, 1, language="en", source="kaggle")
    _add_ticket(test_db, 2, language="de", source="kaggle")   # non-English
    _add_ticket(test_db, 3, language="en", source="demo")     # non-kaggle
    test_db.commit()

    chosen = select_pool(test_db)

    assert chosen == [1]


@integration
def test_select_pool_excludes_adversarial_reserved_id_range(test_db):
    _add_ticket(test_db, 1)
    _add_ticket(test_db, 90005, source="adversarial")
    test_db.commit()

    chosen = select_pool(test_db)

    assert chosen == [1]


# ------------------------------------------------------------- pool_history_exists

@integration
def test_pool_history_exists_false_when_no_calibration_cases(test_db):
    assert pool_history_exists(test_db, [1, 2, 3]) is False


@integration
def test_pool_history_exists_true_when_eval_results_reference_pool_case(test_db):
    _add_ticket(test_db, 1)
    test_db.flush()
    case = EvalCase(ticket_id=1, kind="calibration", expected_outcome="unlabeled")
    test_db.add(case)
    test_db.flush()
    test_db.add(EvalResult(eval_run_id=uuid.uuid4(), case_id=case.id, predicted_outcome="route"))
    test_db.commit()

    assert pool_history_exists(test_db, [1]) is True


@integration
def test_pool_history_exists_false_when_case_has_no_results_yet(test_db):
    _add_ticket(test_db, 1)
    test_db.flush()
    test_db.add(EvalCase(ticket_id=1, kind="calibration", expected_outcome="unlabeled"))
    test_db.commit()

    assert pool_history_exists(test_db, [1]) is False


# ------------------------------------------------------------------- seed_pool

@integration
def test_seed_pool_creates_calibration_kind_cases_with_unlabeled_sentinel(test_db):
    _add_ticket(test_db, 1)
    _add_ticket(test_db, 2)
    test_db.commit()

    seed_pool(test_db, [1, 2])

    cases = test_db.execute(
        select(EvalCase).where(EvalCase.ticket_id.in_([1, 2]))
    ).scalars().all()
    assert len(cases) == 2
    assert all(c.kind == "calibration" for c in cases)
    # "unlabeled" is an honest sentinel (schema requires NOT NULL) -- never
    # a fabricated route/escalate guess -- and nothing grades it.
    assert all(c.expected_outcome == "unlabeled" for c in cases)


@integration
def test_seed_pool_is_idempotent_delete_then_reinsert(test_db):
    _add_ticket(test_db, 1)
    test_db.commit()

    seed_pool(test_db, [1])
    first_ids = {c.id for c in test_db.execute(
        select(EvalCase).where(EvalCase.ticket_id == 1)).scalars().all()}

    seed_pool(test_db, [1])
    second = test_db.execute(select(EvalCase).where(EvalCase.ticket_id == 1)).scalars().all()

    assert len(second) == 1  # no duplicate growth
    assert {c.id for c in second} != first_ids  # delete-then-reinsert: new row, same ticket


@integration
def test_seed_pool_never_touches_golden_or_adversarial_rows(test_db):
    _add_ticket(test_db, 1)  # golden
    _add_ticket(test_db, 2)  # pool
    test_db.flush()
    golden_case = EvalCase(ticket_id=1, kind="representative", expected_outcome="route")
    test_db.add(golden_case)
    test_db.commit()
    golden_id = golden_case.id

    seed_pool(test_db, [2])

    surviving_golden = test_db.get(EvalCase, golden_id)
    assert surviving_golden is not None
    assert surviving_golden.kind == "representative"


@integration
def test_seed_pool_refuses_without_reset_flag_when_pool_history_exists(test_db):
    _add_ticket(test_db, 1)
    test_db.flush()
    case = EvalCase(ticket_id=1, kind="calibration", expected_outcome="unlabeled")
    test_db.add(case)
    test_db.flush()
    test_db.add(EvalResult(eval_run_id=uuid.uuid4(), case_id=case.id, predicted_outcome="route"))
    test_db.commit()
    case_id = case.id

    with pytest.raises(SystemExit) as exc:
        seed_pool(test_db, [1])
    assert exc.value.code == 1

    test_db.rollback()
    untouched = test_db.get(EvalCase, case_id)
    assert untouched is not None  # refused before touching anything


@integration
def test_seed_pool_reset_history_deletes_only_this_pools_own_results(test_db):
    _add_ticket(test_db, 1)  # pool ticket, will be reset
    _add_ticket(test_db, 2)  # unrelated golden ticket, must survive
    test_db.flush()
    pool_case = EvalCase(ticket_id=1, kind="calibration", expected_outcome="unlabeled")
    golden_case = EvalCase(ticket_id=2, kind="representative", expected_outcome="route")
    test_db.add_all([pool_case, golden_case])
    test_db.flush()
    pool_result = EvalResult(eval_run_id=uuid.uuid4(), case_id=pool_case.id,
                             predicted_outcome="route")
    golden_result = EvalResult(eval_run_id=uuid.uuid4(), case_id=golden_case.id,
                               predicted_outcome="route")
    test_db.add_all([pool_result, golden_result])
    test_db.commit()
    golden_result_id = golden_result.id

    seed_pool(test_db, [1], reset_history=True)

    # the pool's own old eval_result is gone (case_id no longer exists)
    remaining_case_ids = {c.id for c in test_db.execute(select(EvalCase)).scalars().all()}
    remaining_results = test_db.execute(select(EvalResult)).scalars().all()
    assert all(r.case_id in remaining_case_ids for r in remaining_results)
    # the unrelated golden eval_result was never touched
    assert test_db.get(EvalResult, golden_result_id) is not None
