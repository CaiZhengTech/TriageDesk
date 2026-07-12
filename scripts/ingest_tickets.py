"""Load English tickets from the Kaggle CSV into the tickets table.

Usage (from project root): python -m scripts.ingest_tickets [--limit N] [--csv PATH]
"""

import argparse
import csv

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
    args = parser.parse_args()

    session = SessionLocal()
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
