"""Seed eval_cases: 20 stratified real tickets + 5 authored adversarial.

  set TRIAGEDESK_ENV_FILE=...
  python -m scripts.build_golden_set          # selects, then seeds if expectations exist
  python -m scripts.build_golden_set --select-only   # (re)write golden_expectations.json

Deterministic: same seed -> same 20 tickets, every run. Idempotent: clears
eval_cases before seeding, and re-seeds the 5 adversarial tickets at their
pinned ids (delete-then-reinsert) so repeated runs converge to identical
state instead of growing new rows each time."""

import argparse
import json
import random
from pathlib import Path

from sqlalchemy import delete, select

from triagedesk.db import SessionLocal
from triagedesk.evals.adversarial import ADVERSARIAL
from triagedesk.models import EvalCase, Ticket
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


def seed(session) -> None:
    data = json.loads(EXPECTATIONS.read_text())
    assert all(r["expected_outcome"] in ("route", "escalate") for r in data), \
        "annotate every representative expected_outcome as route|escalate first"

    session.execute(delete(EvalCase))
    for r in data:
        session.add(EvalCase(ticket_id=r["ticket_id"], kind="representative",
                             expected_outcome=r["expected_outcome"],
                             expected_queue=r["expected_queue"], notes=r.get("notes")))
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
    args = ap.parse_args()
    session = SessionLocal()
    try:
        if args.select_only:
            cmd_select(session)
        else:
            seed(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
