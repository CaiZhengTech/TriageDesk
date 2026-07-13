"""  python -m triagedesk.evals.cli run [--no-judge] [--cost-cap 1.0] [--ci]
  python -m triagedesk.evals.cli judge --eval-run <uuid> [--cost-cap 0.50]
  python -m triagedesk.evals.cli label-export [--out judge_labels.csv]
  python -m triagedesk.evals.cli label-import <csv>
  python -m triagedesk.evals.cli calibrate

Runs the golden set live, prints the summary, persists eval_results. --ci
loads results/eval-baseline.json and exits non-zero on any breach (Task 7).
`judge` backfills judge verdicts onto an existing eval_run's results (judge
calls only -- no re-running the pipeline). `label-export`/`label-import`/
`calibrate` are the Task 6 judge-calibration flow: export a blind CSV (no
judge_verdict) for a human to label, import the human_label column back,
then compute Cohen's kappa between human_label and judge_verdict -- no
live calls in any of the three."""

import argparse
import json
import uuid
from pathlib import Path

from triagedesk.db import SessionLocal
from triagedesk.evals.harness import (
    JUDGE_BACKFILL_COST_CAP,
    SuiteCostExceeded,
    judge_backfill,
    run_suite,
)

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


def cmd_judge(args) -> None:
    session = SessionLocal()
    try:
        try:
            summary = judge_backfill(
                session, uuid.UUID(args.eval_run), cost_cap=args.cost_cap)
        except SuiteCostExceeded as exc:
            raise SystemExit(f"COST CAP BREACH: {exc}") from exc
        print(f"judged {summary['n_judged']} run(s)")
        print(f"verdicts: {summary['verdict_counts']}")
        print(f"total cost: ${summary['total_cost']:.4f}")
    finally:
        session.close()


def _render_calibration_md(rep: dict) -> str:
    kappa_line = (
        f"- **Cohen's kappa: {rep['kappa']:.3f}**\n"
        if rep["kappa"] is not None
        else f"- **Cohen's kappa: undefined** -- {rep['kappa_undefined_reason']}\n"
    )
    raw_line = (
        f"- Raw agreement: **{rep['raw_agreement']:.3f}**\n"
        if rep["raw_agreement"] is not None
        else "- Raw agreement: n/a (no labeled pairs)\n"
    )
    confusion_rows = "\n".join(
        f"| {h} | {c['pass']} | {c['fail']} | {c['needs_review']} |"
        for h, c in rep["confusion"].items()
    ) or "| (no rows) | - | - | - |"
    if rep["disagreements"]:
        disagree_rows = "\n".join(
            f"| {d['result_id']} | {d['human_label']} | {d['judge_verdict']} | "
            f"{(d['judge_reason'] or '').replace('|', '/')} |"
            for d in rep["disagreements"]
        )
    else:
        disagree_rows = "| - | - | - | (none) |"
    return (
        "# Judge calibration\n\n"
        f"- Labels compared (solo): **{rep['n']}**\n"
        f"{raw_line}"
        f"{kappa_line}\n"
        "Blind solo labeling; friend labels (chore #19) merged if they arrive.\n"
        "Judge = claude-sonnet-4-6 @ temperature 0. Verdicts are debugging aids,\n"
        "never ground truth.\n\n"
        "## Confusion matrix (rows = human, cols = judge)\n\n"
        "| human \\ judge | pass | fail | needs_review |\n"
        "|---|---|---|---|\n"
        f"{confusion_rows}\n\n"
        "## Disagreements (judge vs human)\n\n"
        "Where the LLM judge diverged from human judgment -- the highest-value\n"
        "artifact of this calibration pass.\n\n"
        "| result_id | human_label | judge_verdict | judge_reason |\n"
        "|---|---|---|---|\n"
        f"{disagree_rows}\n"
    )


def cmd_label_export(args) -> None:
    from triagedesk.evals.calibration import export_labels
    session = SessionLocal()
    try:
        n = export_labels(session, args.out)
        print(f"exported {n} rows -> {args.out} (label human_label as pass|fail|needs_review)")
    finally:
        session.close()


def cmd_label_import(args) -> None:
    from triagedesk.evals.calibration import import_labels
    session = SessionLocal()
    try:
        print(f"imported {import_labels(session, args.csv)} human labels")
    finally:
        session.close()


def cmd_calibrate(args) -> None:
    from triagedesk.evals.calibration import compute_kappa_report
    session = SessionLocal()
    try:
        rep = compute_kappa_report(session)
        print(json.dumps(rep, indent=2))
        Path("results").mkdir(exist_ok=True)
        Path("results/judge-calibration.md").write_text(
            _render_calibration_md(rep), encoding="utf-8")
        print("wrote results/judge-calibration.md")
    finally:
        session.close()


def main() -> None:
    ap = argparse.ArgumentParser(prog="triagedesk-evals")
    sub = ap.add_subparsers(required=True)

    p = sub.add_parser("run")
    p.add_argument("--no-judge", action="store_true")
    p.add_argument("--cost-cap", type=float, default=1.00)
    p.add_argument("--ci", action="store_true")
    p.set_defaults(func=cmd_run)

    j = sub.add_parser("judge")
    j.add_argument("--eval-run", required=True)
    j.add_argument("--cost-cap", type=float, default=JUDGE_BACKFILL_COST_CAP)
    j.set_defaults(func=cmd_judge)

    pe = sub.add_parser("label-export")
    pe.add_argument("--out", default="judge_labels.csv")
    pe.set_defaults(func=cmd_label_export)

    pi = sub.add_parser("label-import")
    pi.add_argument("csv")
    pi.set_defaults(func=cmd_label_import)

    pc = sub.add_parser("calibrate")
    pc.set_defaults(func=cmd_calibrate)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
