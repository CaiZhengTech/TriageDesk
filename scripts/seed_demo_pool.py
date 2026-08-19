"""Seed the public demo's ticket pool from `triagedesk/demo_pool.py` (issue #64).

  set TRIAGEDESK_ENV_FILE=...
  python -m scripts.seed_demo_pool                  # seed / re-seed the pool
  python -m scripts.seed_demo_pool --reset-history  # DESTRUCTIVE: also drop their runs

The pool used to exist only as hand-made rows in a Neon dev branch, propagated to
prod by copy-on-write branching. When the free-tier branches expired it was gone,
and nothing in the repo could rebuild it. This script closes that gap: the ticket
text lives in `triagedesk/demo_pool.py` and this replays it into any database.

Idempotent, using the same delete-then-reinsert-at-pinned-ids precedent as
`seed_adversarial_tickets()` in scripts/build_golden_set.py, so repeated runs
converge to identical rows instead of minting new ids each time.

Data-loss guard, also mirroring build_golden_set: a demo ticket's runs are real
trace evidence and are what the console displays. Deleting the ticket would orphan
them, so without --reset-history the script refuses (exit 1, DB untouched) when any
run exists for a pooled ticket.
"""

import argparse

from sqlalchemy import delete, select

from triagedesk.db import SessionLocal
from triagedesk.demo_pool import DEMO_POOL
from triagedesk.models import Run, Span, Ticket
from triagedesk.tools import customer_ref_for

POOL_IDS = [spec["ticket_id"] for spec in DEMO_POOL]


def runs_exist(session) -> bool:
    return session.execute(
        select(Run.id).where(Run.ticket_id.in_(POOL_IDS)).limit(1)
    ).first() is not None


def _verify_customer_mapping() -> None:
    """`customer_ref_for` is `id % 12`, so an id decides which account — and which
    PLAN — the act loop reads. A pinned id that drifts off its intended customer
    still runs fine and silently tests a different scenario, which is the failure
    this check exists to make loud. Also asserted in tests/unit/test_demo_pool.py;
    repeated here because seeding writes to a real database."""
    for spec in DEMO_POOL:
        ticket = Ticket(id=spec["ticket_id"])
        actual = customer_ref_for(ticket)
        if actual != spec["expected_customer_ref"]:
            raise SystemExit(
                f"id {spec['ticket_id']} maps to {actual}, but "
                f"{spec['subject']!r} needs {spec['expected_customer_ref']} — "
                f"fix the pinned id in triagedesk/demo_pool.py"
            )


def seed(session, reset_history: bool = False) -> None:
    _verify_customer_mapping()

    if runs_exist(session):
        if not reset_history:
            print(
                "runs exist for demo-pool tickets; reseeding would orphan that "
                "trace evidence -- rerun with --reset-history to accept the loss"
            )
            raise SystemExit(1)
        run_ids = session.execute(
            select(Run.id).where(Run.ticket_id.in_(POOL_IDS))
        ).scalars().all()
        session.execute(delete(Span).where(Span.run_id.in_(run_ids)))
        session.execute(delete(Run).where(Run.ticket_id.in_(POOL_IDS)))

    session.execute(delete(Ticket).where(Ticket.id.in_(POOL_IDS)))
    session.flush()

    for spec in DEMO_POOL:
        session.add(Ticket(
            id=spec["ticket_id"],
            subject=spec["subject"],
            body=spec["body"],
            queue=spec["queue"],
            language="en",
            source="demo",  # the pool-only rule in triagedesk/demo.py keys off this
        ))
    session.commit()

    auto = sum(1 for s in DEMO_POOL if s["expected_gate_outcome"] == "auto_resolve")
    print(f"seeded {len(DEMO_POOL)} demo-pool tickets "
          f"({auto} intended to auto-resolve, {len(DEMO_POOL) - auto} to escalate)")


def main() -> None:
    ap = argparse.ArgumentParser(prog="seed_demo_pool")
    ap.add_argument("--reset-history", action="store_true",
                    help="DESTRUCTIVE: also delete the pooled tickets' runs/spans")
    args = ap.parse_args()
    session = SessionLocal()
    try:
        seed(session, reset_history=args.reset_history)
    finally:
        session.close()


if __name__ == "__main__":
    main()
