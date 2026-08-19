"""Rebuild an empty database from nothing but this repository (issue #64).

  set TRIAGEDESK_ENV_FILE=...
  python -m scripts.bootstrap --dry-run     # print the plan, touch nothing
  python -m scripts.bootstrap               # run it (refuses on a non-empty DB)
  python -m scripts.bootstrap --force       # run it against a database with data

Neon's free tier expires idle branches. In August 2026 both the `prod` and `test`
branches were garbage-collected and the entire database went with them — schema,
11,922 tickets, the KB embeddings, the eval cases, and every run. Recovering it
was archaeology because the steps lived in a session log rather than in code.

This script is the answer to that: one command, no API spend beyond KB embeddings,
that takes an empty Postgres to a fully seeded TriageDesk. The next expiry should
cost ten minutes, not an afternoon.

WHAT IT DOES NOT DO
-------------------
It does not recreate run history. Traces are the record of real executions and
re-running the pipeline costs real money (~3c/run), so that stays an explicit,
separate decision — see `scripts/smoke.py` for a single run, or the eval CLI for
the golden suite. A freshly bootstrapped console is correct but empty, which the
landing page now degrades gracefully to show (issue #60).
"""

import argparse
import subprocess
import sys

from sqlalchemy import func, select

from triagedesk.db import SessionLocal, engine
from triagedesk.models import Ticket

# Ordered, and the order is load-bearing:
#   migrations  -> creates the tables AND the pgvector extension
#   ingest      -> Kaggle tickets take auto-increment ids 1..11922, so this must
#                  run before anything that references a ticket id
#   embed_kb    -> retrieval has nothing to search without it
#   demo pool   -> pinned ids above the ingest range; the public demo reads these
#   golden set  -> its expectations file references ids from the ingest step
#   calibration -> shares eval_cases with the golden set; seed-only, no spend
STEPS: list[tuple[str, list[str], str]] = [
    ("migrations", [sys.executable, "-m", "alembic", "upgrade", "head"],
     "creates the 7 tables and the pgvector extension"),
    ("kaggle tickets", [sys.executable, "-m", "scripts.ingest_tickets"],
     "11,922 English tickets; deterministic, ids 1..11922"),
    ("kb embeddings", [sys.executable, "-m", "scripts.embed_kb"],
     "15 authored KB docs -> Voyage embeddings (small non-Anthropic cost)"),
    ("demo pool", [sys.executable, "-m", "scripts.seed_demo_pool"],
     "the public demo's tickets, pinned ids from triagedesk/demo_pool.py"),
    ("golden set", [sys.executable, "-m", "scripts.build_golden_set"],
     "20 representative + 5 adversarial eval_cases"),
    ("calibration pool", [sys.executable, "-m", "scripts.build_calibration_pool",
                          "--seed-only"],
     "25 held-out eval_cases; seeding only, no live run"),
]


def database_is_empty(session) -> bool:
    return session.scalar(select(func.count()).select_from(Ticket)) == 0


def main() -> None:
    ap = argparse.ArgumentParser(prog="bootstrap")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and exit without touching the database")
    ap.add_argument("--force", action="store_true",
                    help="proceed even if the database already contains tickets")
    args = ap.parse_args()

    print("Bootstrap plan:")
    for i, (name, cmd, why) in enumerate(STEPS, 1):
        print(f"  {i}. {name:<17} {why}")
        print(f"     $ {' '.join(cmd[2:]) if cmd[1] == '-m' else ' '.join(cmd)}")
    print()

    if args.dry_run:
        print("--dry-run: nothing executed.")
        return

    if engine is None:
        raise SystemExit("DATABASE_URL is not configured — nothing to bootstrap.")
    print(f"target: {engine.url.host}/{engine.url.database}")

    # Fail closed on the one mistake that actually hurts: pointing this at a
    # database that already has data. Every step below is individually idempotent
    # or guarded, but running the whole sequence against production by accident
    # should take more than a typo.
    session = SessionLocal()
    try:
        if not database_is_empty(session) and not args.force:
            raise SystemExit(
                "database already contains tickets — bootstrap is for empty "
                "databases. Re-run with --force if you really mean it."
            )
    finally:
        session.close()

    for i, (name, cmd, _) in enumerate(STEPS, 1):
        print(f"\n=== {i}/{len(STEPS)}: {name} ===")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise SystemExit(
                f"step {i} ({name}) failed with exit code {result.returncode}; "
                f"stopping. Fix it and re-run — the completed steps are idempotent."
            )

    print("\nBootstrap complete. The database has schema, tickets, KB embeddings, "
          "the demo pool, and the eval cases.")
    print("Run history is intentionally NOT recreated — that costs real API spend. "
          "Use scripts/smoke.py for one live run.")


if __name__ == "__main__":
    main()
