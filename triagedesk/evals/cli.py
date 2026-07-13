"""  python -m triagedesk.evals.cli run [--no-judge] [--cost-cap 1.0] [--ci]

Runs the golden set live, prints the summary, persists eval_results. --ci
loads results/eval-baseline.json and exits non-zero on any breach (Task 7)."""

import argparse
import json
from pathlib import Path

from triagedesk.db import SessionLocal
from triagedesk.evals.harness import SuiteCostExceeded, run_suite

BASELINE = Path("results/eval-baseline.json")


def _print_summary(summary: dict) -> None:
    print(json.dumps({k: v for k, v in summary.items() if k != "calibration"}, indent=2))
    print("\ncalibration (retrieval_similarity bucket -> outcome accuracy):")
    for row in summary["calibration"]:
        print(f"  {row['bucket']:<14} n={row['n']:<3} acc={row['accuracy']}")


def cmd_run(args) -> None:
    session = SessionLocal()
    try:
        try:
            eval_run_id, summary = run_suite(
                session, cost_cap=args.cost_cap, with_judge=not args.no_judge)
        except SuiteCostExceeded as exc:
            raise SystemExit(f"COST CAP BREACH: {exc}") from exc
        print(f"eval_run {eval_run_id}")
        _print_summary(summary)
        if args.ci:
            _assert_baseline(summary)
    finally:
        session.close()


def _assert_baseline(summary: dict) -> None:
    b = json.loads(BASELINE.read_text())
    failures = []
    for key, floor in b.get("min", {}).items():
        if summary[key] < floor:
            failures.append(f"{key}={summary[key]:.3f} < min {floor}")
    for key, ceil in b.get("max", {}).items():
        if summary[key] > ceil:
            failures.append(f"{key}={summary[key]:.3f} > max {ceil}")
    for key, spec in b.get("tolerance", {}).items():   # judge metrics: |x-target|<=band
        if abs(summary[key] - spec["target"]) > spec["band"]:
            failures.append(f"{key}={summary[key]:.3f} outside {spec['target']}±{spec['band']}")
    if failures:
        raise SystemExit("EVAL GATE FAILED:\n  " + "\n  ".join(failures))
    print("\nEVAL GATE PASSED")


def main() -> None:
    ap = argparse.ArgumentParser(prog="triagedesk-evals")
    sub = ap.add_subparsers(required=True)
    p = sub.add_parser("run")
    p.add_argument("--no-judge", action="store_true")
    p.add_argument("--cost-cap", type=float, default=1.00)
    p.add_argument("--ci", action="store_true")
    p.set_defaults(func=cmd_run)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
