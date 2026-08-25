"""Cost per accepted task, computed from real run history (#79).

  set TRIAGEDESK_ENV_FILE=...
  python -m scripts.report_unit_economics
  python -m scripts.report_unit_economics --review-minutes 10 --hourly 45

$0 and read-only: aggregates rows already in `runs` and `review_decisions`.
No API calls, no writes.

The labour rate is an ASSUMPTION and dominates the result, so the flags exist to
make disagreeing with it cheap. Try your own numbers -- that is the point of
exposing them rather than hard-coding one answer.
"""

import argparse
import json

from sqlalchemy import select

from triagedesk.db import SessionLocal
from triagedesk.evals.unit_economics import (
    DEFAULT_REVIEW_MINUTES,
    DEFAULT_REVIEWER_HOURLY_USD,
    RunRecord,
    unit_economics,
)
from triagedesk.models import ReviewDecision, Run


def load_runs(session) -> list[RunRecord]:
    reviewed = {
        r for (r,) in session.execute(select(ReviewDecision.run_id)).all()
    }
    rows = session.execute(select(Run.id, Run.state, Run.total_cost_usd)).all()
    return [
        RunRecord(state=state, total_cost_usd=cost or 0.0, was_reviewed=rid in reviewed)
        for rid, state, cost in rows
    ]


def main() -> None:
    ap = argparse.ArgumentParser(prog="report_unit_economics")
    ap.add_argument("--review-minutes", type=float, default=DEFAULT_REVIEW_MINUTES)
    ap.add_argument("--hourly", type=float, default=DEFAULT_REVIEWER_HOURLY_USD)
    ap.add_argument("--json", action="store_true", help="emit raw JSON")
    args = ap.parse_args()

    session = SessionLocal()
    try:
        runs = load_runs(session)
    finally:
        session.close()

    e = unit_economics(runs, review_minutes=args.review_minutes,
                       reviewer_hourly_usd=args.hourly)
    if args.json:
        print(json.dumps(e, indent=2))
        return

    print(f"UNIT ECONOMICS  ({e['n_runs']} terminal runs)")
    print(f"  accepted (auto-resolved)  {e['n_accepted']}")
    print(f"  escalated to a human      {e['n_escalated']}  "
          f"({e['n_reviewed']} actually reviewed so far)")
    print(f"  failed                    {e['n_failed']}")
    if e["deflection_rate"] is not None:
        print(f"  deflection rate           {e['deflection_rate']:.1%}")
    print()
    print(f"  API spend                 ${e['api_cost_usd']:.4f}")
    print(f"  human review labour       ${e['labour_cost_usd']:.2f}   "
          f"(assumed: {args.review_minutes:g} min @ ${args.hourly:g}/h "
          f"= ${e['labour_cost_per_escalation']:.2f}/escalation)")
    print(f"  TOTAL                     ${e['total_cost_usd']:.2f}")
    print()
    if e["cost_per_accepted_task"] is None:
        print("  cost per accepted task    n/a (nothing auto-resolved)")
    else:
        print(f"  cost per accepted task    ${e['cost_per_accepted_task']:.2f}")
    if e["api_cost_per_run"] is not None:
        print(f"  (api cost per run alone   ${e['api_cost_per_run']:.4f})")
    if e["break_even_deflection_rate"] is not None:
        print(f"  break-even deflection     {e['break_even_deflection_rate']:.2%} "
              f"-- above this the pipeline beats all-human")
    print()
    print("  " + e["assumptions"]["_note"].replace(". ", ".\n  "))


if __name__ == "__main__":
    main()
