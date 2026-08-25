"""Load English tickets from the Kaggle CSV into the tickets table.

Usage (from project root):
  python -m scripts.ingest_tickets [--limit N] [--csv PATH] [--reingest]

NOT IDEMPOTENT BY DEFAULT, AND THAT MATTERS (issue #61 postmortem)
------------------------------------------------------------------
Ticket ids are auto-increment, so ids are the INSERTION ORDER of the rows
surviving the filter below. `triagedesk/evals/golden_expectations.json` names
tickets by id. Running this twice therefore does not merely duplicate rows: the
second pass appends a whole second copy at ids 11923+, and anything that samples
`source='kaggle'` afterwards (notably scripts/build_calibration_pool.py) draws
from a pool that is half phantoms.

That happened for real while seeding the eval branch: bootstrap failed partway,
was re-run with --force, and the calibration pool ended up with 14 of 25 cases
pointing at duplicate rows. So this script now refuses to run against a table
that already has Kaggle tickets, unless you pass --reingest.
"""

import argparse
import csv

from sqlalchemy import func, select

from triagedesk.db import SessionLocal
from triagedesk.models import Ticket

DEFAULT_CSV = "data/customer-support-tickets/dataset-tickets-multi-lang-4-20k.csv"
BATCH = 1000


def row_to_ticket(row: dict) -> Ticket | None:
    if row.get("language") != "en":
        return None
    subject = (row.get("subject") or "").strip()
    body = (row.get("body") or "").strip()
    if not body:
        return None
    return Ticket(
        subject=subject or "(no subject)",
        body=body,
        queue=row["queue"],
        ticket_type=row.get("type") or None,
        priority=row.get("priority") or None,
        language="en",
        source="kaggle",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--reingest", action="store_true",
                        help="ingest even though kaggle tickets already exist "
                             "(appends a second copy at new ids -- see the "
                             "module docstring before using this)")
    args = parser.parse_args()

    session = SessionLocal()
    existing = session.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.source == "kaggle")
    )
    if existing and not args.reingest:
        session.close()
        print(f"{existing} kaggle tickets already present -- refusing to ingest "
              f"again, because a second pass appends duplicates at new ids and "
              f"silently corrupts anything that samples source='kaggle' "
              f"(golden set, calibration pool). Pass --reingest to override.")
        raise SystemExit(1)
    inserted = 0
    with open(args.csv, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ticket = row_to_ticket(row)
            if ticket is None:
                continue
            session.add(ticket)
            inserted += 1
            if inserted % BATCH == 0:
                session.commit()
                print(f"  {inserted} inserted...")
            if args.limit and inserted >= args.limit:
                break
    session.commit()
    session.close()
    print(f"Done: {inserted} tickets inserted.")


if __name__ == "__main__":
    main()
