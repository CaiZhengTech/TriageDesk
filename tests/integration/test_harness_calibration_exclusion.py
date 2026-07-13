"""Proves at the real DB-filtering level (not a fake) that run_suite's
EvalCase query excludes kind='calibration' rows -- the calibration pool
(issue #11) shares the eval_cases/eval_results tables with the golden set,
so this is the one guarantee that keeps the golden set's metrics completely
unaffected by the pool's existence. No live Anthropic calls: run_ticket is
monkeypatched to return pre-built Run rows."""
from tests.conftest import integration
from triagedesk.evals.harness import run_suite
from triagedesk.models import EvalCase, Run, Ticket


@integration
def test_run_suite_excludes_calibration_kind_cases(test_db, monkeypatch):
    t_rep = Ticket(subject="VPN issue", body="VPN drops.", queue="Technical Support",
                    language="en", source="kaggle")
    t_pool = Ticket(subject="Billing question", body="Charged twice.",
                     queue="Billing and Payments", language="en", source="kaggle")
    test_db.add_all([t_rep, t_pool])
    test_db.flush()

    case_rep = EvalCase(ticket_id=t_rep.id, kind="representative",
                         expected_outcome="route", expected_queue="Technical Support")
    case_pool = EvalCase(ticket_id=t_pool.id, kind="calibration",
                          expected_outcome="unlabeled")
    test_db.add_all([case_rep, case_pool])
    test_db.flush()

    run_rep = Run(ticket_id=t_rep.id, state="completed", prompt_version="1.0",
                  model="claude-sonnet-4-6", total_cost_usd=0.01,
                  final_reply="Please restart your VPN client.")
    run_pool = Run(ticket_id=t_pool.id, state="completed", prompt_version="1.0",
                   model="claude-sonnet-4-6", total_cost_usd=0.01,
                   final_reply="You were charged twice; here is a refund timeline.")
    test_db.add_all([run_rep, run_pool])
    test_db.commit()

    calls = []

    def fake_run_ticket(ticket_id, session):
        calls.append(ticket_id)
        return run_rep if ticket_id == t_rep.id else run_pool

    monkeypatch.setattr("triagedesk.evals.harness.run_ticket", fake_run_ticket)

    eval_run_id, summary = run_suite(test_db, with_judge=False)

    # Only the representative case reached the pipeline -- the calibration
    # case was excluded by the query, never even run.
    assert calls == [t_rep.id]
    assert summary["n_cases"] == 1
