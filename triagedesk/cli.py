"""Glass box before any web UI exists.

  python -m triagedesk.cli run <ticket_id>
  python -m triagedesk.cli trace <run_id>
"""

import argparse
import uuid

from triagedesk.db import SessionLocal
from triagedesk.models import Run, Span


def cmd_run(args) -> None:
    from triagedesk.pipeline.runner import run_ticket

    session = SessionLocal()
    run = run_ticket(args.ticket_id, session)
    print(f"run {run.id}  state={run.state}  reason={run.escalation_reason or '-'}  "
          f"cost=${run.total_cost_usd:.4f}")
    _print_trace(session, run)
    session.close()


def cmd_trace(args) -> None:
    session = SessionLocal()
    run = session.get(Run, uuid.UUID(args.run_id))
    if run is None:
        raise SystemExit(f"no run {args.run_id}")
    print(f"run {run.id}  ticket={run.ticket_id}  state={run.state}  "
          f"reason={run.escalation_reason or '-'}\n"
          f"model={run.model}  prompt={run.prompt_version}  "
          f"cost=${run.total_cost_usd:.4f}  gate={run.gate_signals}")
    _print_trace(session, run)
    if run.final_reply:
        print(f"\n--- final reply ---\n{run.final_reply}")
    if run.internal_rationale:
        print(f"\n--- internal rationale (post-hoc context, not ground truth) ---\n"
              f"{run.internal_rationale}")
    session.close()


def _print_trace(session, run: Run) -> None:
    spans = session.query(Span).filter_by(run_id=run.id).order_by(Span.id).all()
    print(f"\n{'stage':<10} {'status':<8} {'ms':>7} {'in_tok':>7} {'out_tok':>8} {'cost':>9}")
    for s in spans:
        ms = ((s.ended_at - s.started_at).total_seconds() * 1000
              if s.ended_at and s.started_at else 0)
        attrs = s.attributes or {}
        print(f"{s.name:<10} {s.status:<8} {ms:>7.0f} "
              f"{attrs.get('gen_ai.usage.input_tokens', '-'):>7} "
              f"{attrs.get('gen_ai.usage.output_tokens', '-'):>8} "
              f"${s.cost_usd:>8.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="triagedesk")
    sub = parser.add_subparsers(required=True)
    p_run = sub.add_parser("run", help="run the pipeline on a ticket")
    p_run.add_argument("ticket_id", type=int)
    p_run.set_defaults(func=cmd_run)
    p_trace = sub.add_parser("trace", help="dump the full trace for a run")
    p_trace.add_argument("run_id")
    p_trace.set_defaults(func=cmd_trace)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
