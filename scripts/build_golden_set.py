"""Seed eval_cases: 20 stratified real tickets + 5 authored adversarial.

  set TRIAGEDESK_ENV_FILE=...
  python -m scripts.build_golden_set          # selects, then seeds if expectations exist
  python -m scripts.build_golden_set --select-only   # (re)write golden_expectations.json
  python -m scripts.build_golden_set --reset-history # ALSO deletes eval_results + adversarial
                                                     # runs/spans (eval history — destructive)

Deterministic: same seed -> same 20 tickets, every run. Idempotent: clears
eval_cases (kind="representative"|"adversarial" only -- see below) before
seeding, and re-seeds the 5 adversarial tickets at their pinned ids
(delete-then-reinsert) so repeated runs converge to identical state instead
of growing new rows each time.

Data-loss guard: eval_results is the project's CI eval history and runs/spans
are live trace evidence. Without --reset-history, the seeder refuses to run
(exit 1, DB untouched) if any of that history exists.

Shares eval_cases with the Task 6 calibration pool (issue #11,
scripts/build_calibration_pool.py), whose rows are kind="calibration". The
clearing step above is scoped to kind IN (representative, adversarial) so a
golden reseed -- even with --reset-history -- never deletes the pool's rows
as collateral damage."""

import argparse
import json
import random
from pathlib import Path

from sqlalchemy import delete, select

from triagedesk.db import SessionLocal
from triagedesk.evals.adversarial import ADVERSARIAL
from triagedesk.models import EvalCase, EvalResult, Run, Span, Ticket
from triagedesk.schemas import QUEUES

SEED = 20260712
PER_QUEUE = 2
EXPECTATIONS = Path("triagedesk/evals/golden_expectations.json")


def select_representative(session) -> list[dict]:
    rng = random.Random(SEED)
    chosen: list[dict] = []
    for queue in QUEUES:
        ids = [t.id for t in session.execute(
            select(Ticket).where(Ticket.queue == queue,
                                  Ticket.language == "en",
                                  Ticket.source == "kaggle")
        ).scalars()]
        ids.sort()  # stable order before sampling => reproducible
        if not ids:
            continue
        for tid in rng.sample(ids, min(PER_QUEUE, len(ids))):
            chosen.append({"ticket_id": tid, "expected_queue": queue,
                           "expected_outcome": "REVIEW", "notes": ""})
    return chosen


def cmd_select(session) -> None:
    rows = select_representative(session)
    EXPECTATIONS.write_text(json.dumps(rows, indent=2))
    print(f"wrote {len(rows)} candidates -> {EXPECTATIONS}. "
          f"Set each expected_outcome to route|escalate, then run without --select-only.")


def eval_history_exists(session) -> bool:
    """True if eval_results has rows or runs exist for the adversarial ticket ids."""
    if session.execute(select(EvalResult.id).limit(1)).first() is not None:
        return True
    ids = [spec["ticket_id"] for spec in ADVERSARIAL]
    return session.execute(
        select(Run.id).where(Run.ticket_id.in_(ids)).limit(1)
    ).first() is not None


def seed_adversarial_tickets(session) -> list[tuple[int, dict]]:
    # Idempotent: delete-then-reinsert at each spec's pinned ticket_id (both the
    # ticket row and any eval_cases row referencing it), so repeated runs
    # converge to identical rows instead of minting new ids each time.
    ids = [spec["ticket_id"] for spec in ADVERSARIAL]
    session.execute(delete(EvalCase).where(EvalCase.ticket_id.in_(ids)))
    session.execute(delete(Ticket).where(Ticket.id.in_(ids)))
    session.flush()
    out = []
    for spec in ADVERSARIAL:
        t = Ticket(id=spec["ticket_id"], subject=spec["subject"], body=spec["body"],
                   # queue defaults to General Inquiry for the 4 injection/pii/off_topic/
                   # ambiguous cases (expected_queue=None) — not a graded signal for those
                   # in the Task 4 harness, only the fixed id/account mapping matters here.
                   queue=spec["expected_queue"] or "General Inquiry",
                   language="en", source="adversarial")
        session.add(t)
        out.append((t.id, spec))
    session.flush()
    return out


def seed(session, reset_history: bool = False) -> None:
    data = json.loads(EXPECTATIONS.read_text())
    assert all(r["expected_outcome"] in ("route", "escalate") for r in data), \
        "annotate every representative expected_outcome as route|escalate first"

    if not reset_history:
        if eval_history_exists(session):
            print("eval history exists (eval_results rows and/or runs for adversarial "
                  "tickets); reseeding would orphan/delete it -- rerun with "
                  "--reset-history to accept the loss")
            raise SystemExit(1)
    else:
        # DESTRUCTIVE: erases the CI eval history and adversarial trace evidence.
        ids = [spec["ticket_id"] for spec in ADVERSARIAL]
        run_ids = session.execute(
            select(Run.id).where(Run.ticket_id.in_(ids))).scalars().all()
        if run_ids:
            session.execute(delete(Span).where(Span.run_id.in_(run_ids)))
        session.execute(delete(Run).where(Run.ticket_id.in_(ids)))
        session.execute(delete(EvalResult))

    # Scoped to representative|adversarial: kind="calibration" rows belong to
    # the Task 6 calibration pool (scripts/build_calibration_pool.py), which
    # shares this table purely to anchor judged replies for kappa -- a golden
    # reseed (even --reset-history) must never delete them as collateral
    # damage. See tests/integration/test_build_golden_set.py's audit-finding
    # test for the reproduction.
    session.execute(delete(EvalCase).where(EvalCase.kind.in_(("representative", "adversarial"))))
    for r in data:
        session.add(EvalCase(ticket_id=r["ticket_id"], kind="representative",
                             expected_outcome=r["expected_outcome"],
                             expected_queue=r["expected_queue"],
                             expected_escalation_reason=r.get("escalation_reason"),
                             notes=r.get("notes")))
    for tid, spec in seed_adversarial_tickets(session):
        session.add(EvalCase(ticket_id=tid, kind="adversarial",
                             expected_outcome=spec["expected_outcome"],
                             expected_queue=spec["expected_queue"],
                             adversarial_kind=spec["adversarial_kind"],
                             expected_escalation_reason=spec["expected_escalation_reason"],
                             notes=spec["notes"]))
    session.commit()
    print(f"seeded {len(data)} representative + {len(ADVERSARIAL)} adversarial eval_cases")


def main() -> None:
    ap = argparse.ArgumentParser(prog="build_golden_set")
    ap.add_argument("--select-only", action="store_true")
    ap.add_argument("--reset-history", action="store_true",
                    help="DESTRUCTIVE: also delete eval_results and the adversarial "
                         "tickets' runs/spans (the eval history) before reseeding")
    args = ap.parse_args()
    session = SessionLocal()
    try:
        if args.select_only:
            cmd_select(session)
        else:
            seed(session, reset_history=args.reset_history)
    finally:
        session.close()


if __name__ == "__main__":
    main()
