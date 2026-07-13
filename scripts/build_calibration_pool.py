"""Seed the judge-calibration pool: ~25 real tickets NOT in the golden set,
run them through the live pipeline and judge, so their replies can be blind
labeled alongside the golden set's for Cohen's kappa (issue #11).

  set TRIAGEDESK_ENV_FILE=...
  python -m scripts.build_calibration_pool                # seed + run + judge (LIVE, ~$0.90)
  python -m scripts.build_calibration_pool --seed-only     # only (re)seed eval_cases
  python -m scripts.build_calibration_pool --reset-history # DESTRUCTIVE: also deletes this
                                                            # pool's own eval_results before
                                                            # reseeding (never golden/adversarial)

Hold-out rationale: the golden set MEASURES the pipeline; it must never
TRAIN anything, including judge calibration. Today only 19 judged replies
exist and all of them are golden-set replies -- calibrating the judge on
tickets it is later graded on would contaminate the measurement. This pool
exists purely to lift the independently-labeled sample toward the spec's
40-50 target without recycling a single golden reply.

Every pool eval_cases row is tagged kind="calibration" and is excluded from
every golden-set metric query -- see triagedesk/evals/harness.py's run_suite
(now filters kind != "calibration") and run_pool (the pool's own separate
run-and-judge entry point, tagged with its own eval_run_id). The golden
set's numbers are computed exactly as they were before this pool existed.

expected_outcome is NOT NULL in the schema, but pool cases carry no grading
burden -- they exist only to anchor a judged reply for kappa. Rather than
fabricate a route/escalate guess nobody has verified, the column is set to
the literal sentinel "unlabeled". Nothing ever reads expected_outcome for a
kind="calibration" row (routing_correct/outcome_correct are intentionally
left at their schema defaults by run_pool -- see its docstring).

Deterministic selection: seed 20260713 (DIFFERENT from the golden set's
20260712 in scripts/build_golden_set.py, so the two sampled sets can never
overlap) over sorted ids of English, kaggle-sourced tickets with
id < 90000 (excludes the adversarial reserved range) that are not already a
golden eval_cases ticket_id (kind IN representative, adversarial).
Disjointness from the golden set is asserted, not just hoped for.

Idempotent seeding, same delete-then-reinsert precedent as
scripts/build_golden_set.py: reseeding refuses (exit 1, DB untouched) if
eval_results already reference this pool's own eval_cases, unless
--reset-history is passed -- and even then only this pool's own rows
(scoped by kind="calibration" AND ticket_id-in-pool) are ever touched;
golden/adversarial eval_cases and eval_results are never selected by these
queries."""

import argparse
import random

from sqlalchemy import delete, select

from triagedesk.db import SessionLocal
from triagedesk.evals.harness import run_pool as run_pool_live
from triagedesk.models import EvalCase, EvalResult, Ticket

SEED = 20260713
POOL_SIZE = 25
ADVERSARIAL_RESERVED_ID_FLOOR = 90000


def golden_ticket_ids(session) -> set[int]:
    return set(session.execute(
        select(EvalCase.ticket_id).where(EvalCase.kind.in_(("representative", "adversarial")))
    ).scalars().all())


def select_pool(session) -> list[int]:
    """Deterministic sample of ~POOL_SIZE ticket ids: English, kaggle-sourced,
    below the adversarial reserved range, and never a golden ticket_id."""
    excluded = golden_ticket_ids(session)
    eligible = sorted(
        t.id for t in session.execute(
            select(Ticket).where(
                Ticket.language == "en",
                Ticket.source == "kaggle",
                Ticket.id < ADVERSARIAL_RESERVED_ID_FLOOR,
            )
        ).scalars()
        if t.id not in excluded
    )
    rng = random.Random(SEED)
    chosen = sorted(rng.sample(eligible, min(POOL_SIZE, len(eligible))))
    assert set(chosen).isdisjoint(excluded), \
        "calibration pool must never overlap the golden set (hold-out rule)"
    return chosen


def pool_history_exists(session, ticket_ids: list[int]) -> bool:
    """True if any eval_results row references one of this pool's own
    (kind="calibration") eval_cases rows."""
    case_ids = session.execute(
        select(EvalCase.id).where(EvalCase.ticket_id.in_(ticket_ids),
                                  EvalCase.kind == "calibration")
    ).scalars().all()
    if not case_ids:
        return False
    return session.execute(
        select(EvalResult.id).where(EvalResult.case_id.in_(case_ids)).limit(1)
    ).first() is not None


def seed_pool(session, ticket_ids: list[int], reset_history: bool = False) -> None:
    if not reset_history:
        if pool_history_exists(session, ticket_ids):
            print("calibration pool eval history exists (eval_results reference this "
                  "pool's eval_cases); reseeding would orphan/delete it -- rerun with "
                  "--reset-history to accept the loss")
            raise SystemExit(1)
    else:
        # DESTRUCTIVE, but scoped: only eval_results referencing THIS pool's
        # own eval_cases rows are deleted -- golden/adversarial results are
        # never selected by this query.
        case_ids = session.execute(
            select(EvalCase.id).where(EvalCase.ticket_id.in_(ticket_ids),
                                      EvalCase.kind == "calibration")
        ).scalars().all()
        if case_ids:
            session.execute(delete(EvalResult).where(EvalResult.case_id.in_(case_ids)))

    session.execute(delete(EvalCase).where(EvalCase.ticket_id.in_(ticket_ids),
                                           EvalCase.kind == "calibration"))
    for tid in ticket_ids:
        session.add(EvalCase(
            ticket_id=tid, kind="calibration",
            expected_outcome="unlabeled",  # honest sentinel -- see module docstring
            notes="calibration pool (issue #11): anchors a judged reply for kappa only",
        ))
    session.commit()
    print(f"seeded {len(ticket_ids)} calibration-pool eval_cases")


def main() -> None:
    ap = argparse.ArgumentParser(prog="build_calibration_pool")
    ap.add_argument("--seed-only", action="store_true",
                    help="only (re)seed eval_cases; skip the live pipeline+judge run")
    ap.add_argument("--reset-history", action="store_true",
                    help="DESTRUCTIVE: also delete this pool's own eval_results before "
                         "reseeding (never touches golden/adversarial rows)")
    ap.add_argument("--cost-cap", type=float, default=1.00)
    args = ap.parse_args()

    session = SessionLocal()
    try:
        ticket_ids = select_pool(session)
        seed_pool(session, ticket_ids, reset_history=args.reset_history)
        if args.seed_only:
            return
        summary = run_pool_live(session, cost_cap=args.cost_cap)
        print(f"eval_run {summary['eval_run_id']}: ran {summary['n_run']}, "
              f"judged {summary['n_judged']}, cost ${summary['total_cost']:.4f}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
