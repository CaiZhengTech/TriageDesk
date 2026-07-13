"""calibration.py unit tests: blind export / idempotent import / kappa report.
No live calls -- pure DB-shaped fakes, same fake-session convention as
test_harness.py / test_judge_backfill.py (DB-level filtering is trusted
SQLAlchemy; fakes return whatever the test pre-selected as already
matching). Verifies (a) the exported CSV never contains judge_verdict --
the blind-labeling requirement -- (b) import is a safe-to-rerun upsert that
rejects labels outside {pass, fail, needs_review}, and (c)
compute_kappa_report handles the degenerate all-one-category case honestly
instead of crashing, and surfaces the disagreement rows."""
import csv
import uuid
from types import SimpleNamespace

import pytest

from triagedesk.evals.calibration import compute_kappa_report, export_labels, import_labels
from triagedesk.models import EvalCase, EvalResult, KbDoc, Run, Span, Ticket


class FakeQuery:
    """Generic fake for session.query(Model).filter(...).order_by(...).all()
    / .filter_by(...).first() -- chaining is a no-op, the fake just returns
    whatever the test pre-loaded (DB-level filtering is trusted SQLAlchemy)."""

    def __init__(self, rows, first_only=False):
        self.rows = rows
        self.first_only = first_only

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, results=None, cases=None, tickets=None, runs=None,
                spans=None, kb_docs=None):
        self.results = results or []
        self.cases = {c.id: c for c in (cases or [])}
        self.tickets = {t.id: t for t in (tickets or [])}
        self.runs = {r.id: r for r in (runs or [])}
        self.spans = spans or []
        self.kb_docs = kb_docs or []
        self.committed = 0

    def query(self, model):
        if model is EvalResult:
            return FakeQuery(self.results)
        if model is Span:
            return FakeQuery(self.spans)
        if model is KbDoc:
            return FakeQuery(self.kb_docs)
        raise AssertionError(f"unexpected query for {model}")

    def get(self, model, id_):
        if model is EvalCase:
            return self.cases.get(id_)
        if model is Ticket:
            return self.tickets.get(id_)
        if model is Run:
            return self.runs.get(id_)
        if model is EvalResult:
            return next((r for r in self.results if r.id == id_), None)
        raise AssertionError(f"unexpected get for {model}")

    def commit(self):
        self.committed += 1


def make_result(id_, case_id=1, run_id=None, judge_verdict="pass", judge_reason="grounded",
                human_label=None):
    return SimpleNamespace(
        id=id_, case_id=case_id, run_id=run_id or uuid.uuid4(),
        judge_verdict=judge_verdict, judge_reason=judge_reason, human_label=human_label,
    )


def make_case(case_id=1, ticket_id=101):
    return SimpleNamespace(id=case_id, ticket_id=ticket_id)


def make_ticket(ticket_id=101, subject="VPN keeps disconnecting", body="Client demo at 3pm."):
    return SimpleNamespace(id=ticket_id, subject=subject, body=body)


def make_run(run_id, final_reply="Please restart your VPN client."):
    return SimpleNamespace(id=run_id, final_reply=final_reply)


def make_span(run_id, slugs):
    return SimpleNamespace(run_id=run_id, name="retrieve",
                           attributes={"retrieval.doc_slugs": slugs})


def make_kb_doc(slug, title="VPN troubleshooting", content="Restart the client. " * 30):
    return SimpleNamespace(slug=slug, title=title, content=content)


# ---------------------------------------------------------------- export_labels

def test_export_writes_one_row_per_judged_result(tmp_path):
    run_id = uuid.uuid4()
    result = make_result(1, run_id=run_id)
    session = FakeSession(
        results=[result], cases=[make_case()], tickets=[make_ticket()],
        runs=[make_run(run_id)], spans=[make_span(run_id, ["vpn-troubleshooting"])],
        kb_docs=[make_kb_doc("vpn-troubleshooting")],
    )
    out = tmp_path / "labels.csv"

    n = export_labels(session, str(out))

    assert n == 1
    with open(out, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["result_id"] == "1"
    assert rows[0]["ticket_subject"] == "VPN keeps disconnecting"
    assert rows[0]["kb_slugs"] == "vpn-troubleshooting"
    assert rows[0]["customer_reply"] == "Please restart your VPN client."
    assert rows[0]["human_label"] == ""


def test_export_csv_never_reveals_judge_verdict(tmp_path):
    """The blind-labeling requirement: no column can leak the judge's call."""
    run_id = uuid.uuid4()
    result = make_result(1, run_id=run_id, judge_verdict="fail", judge_reason="invented a refund")
    session = FakeSession(
        results=[result], cases=[make_case()], tickets=[make_ticket()],
        runs=[make_run(run_id)], spans=[make_span(run_id, [])], kb_docs=[],
    )
    out = tmp_path / "labels.csv"

    export_labels(session, str(out))

    with open(out, encoding="utf-8") as fh:
        header = next(csv.reader(fh))
        body = fh.read()
    assert "judge_verdict" not in header
    assert "judge_reason" not in header
    assert "judge_rule_triggered" not in header
    assert "fail" not in body  # the judge's actual verdict must not leak into any cell
    assert "invented a refund" not in body  # nor its reason


def test_export_includes_kb_excerpt_for_grading_context(tmp_path):
    run_id = uuid.uuid4()
    result = make_result(1, run_id=run_id)
    session = FakeSession(
        results=[result], cases=[make_case()], tickets=[make_ticket()],
        runs=[make_run(run_id)], spans=[make_span(run_id, ["vpn-troubleshooting"])],
        kb_docs=[make_kb_doc("vpn-troubleshooting", title="VPN Troubleshooting")],
    )
    out = tmp_path / "labels.csv"

    export_labels(session, str(out))

    with open(out, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert "vpn-troubleshooting" in rows[0]["kb_excerpts"]
    assert "VPN Troubleshooting" in rows[0]["kb_excerpts"]


def test_export_handles_no_retrieved_docs(tmp_path):
    run_id = uuid.uuid4()
    result = make_result(1, run_id=run_id)
    session = FakeSession(
        results=[result], cases=[make_case()], tickets=[make_ticket()],
        runs=[make_run(run_id)], spans=[], kb_docs=[],
    )
    out = tmp_path / "labels.csv"

    n = export_labels(session, str(out))

    assert n == 1
    with open(out, encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))
    assert row["kb_slugs"] == ""
    assert row["kb_excerpts"] == ""


def test_export_returns_zero_for_no_judged_rows(tmp_path):
    session = FakeSession(results=[])
    out = tmp_path / "labels.csv"

    n = export_labels(session, str(out))

    assert n == 0
    with open(out, encoding="utf-8") as fh:
        assert list(csv.DictReader(fh)) == []


# ---------------------------------------------------------------- import_labels

def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["result_id", "ticket_subject", "ticket_body", "kb_slugs",
                    "kb_excerpts", "customer_reply", "human_label"])
        for r in rows:
            w.writerow(r)


def test_import_writes_human_label_onto_matching_row(tmp_path):
    result = make_result(1)
    session = FakeSession(results=[result])
    path = tmp_path / "labels.csv"
    _write_csv(path, [[1, "s", "b", "", "", "reply", "pass"]])

    n = import_labels(session, str(path))

    assert n == 1
    assert result.human_label == "pass"
    assert session.committed == 1


def test_import_skips_blank_labels_cai_only_labeled_some_rows(tmp_path):
    r1, r2 = make_result(1), make_result(2)
    session = FakeSession(results=[r1, r2])
    path = tmp_path / "labels.csv"
    _write_csv(path, [
        [1, "s", "b", "", "", "reply", "pass"],
        [2, "s", "b", "", "", "reply", ""],  # not labeled yet -- skip, don't crash
    ])

    n = import_labels(session, str(path))

    assert n == 1
    assert r1.human_label == "pass"
    assert r2.human_label is None


def test_import_rejects_invalid_label(tmp_path):
    result = make_result(1)
    session = FakeSession(results=[result])
    path = tmp_path / "labels.csv"
    _write_csv(path, [[1, "s", "b", "", "", "reply", "maybe"]])

    with pytest.raises(ValueError):
        import_labels(session, str(path))


def test_import_is_idempotent_safe_to_rerun(tmp_path):
    result = make_result(1)
    session = FakeSession(results=[result])
    path = tmp_path / "labels.csv"
    _write_csv(path, [[1, "s", "b", "", "", "reply", "fail"]])

    n1 = import_labels(session, str(path))
    n2 = import_labels(session, str(path))

    assert n1 == n2 == 1
    assert result.human_label == "fail"


# ------------------------------------------------------------ compute_kappa_report

def test_report_basic_shape():
    results = [
        make_result(1, judge_verdict="pass", judge_reason="grounded", human_label="pass"),
        make_result(2, judge_verdict="fail", judge_reason="invented step", human_label="fail"),
        make_result(3, judge_verdict="pass", judge_reason="grounded", human_label="fail"),
    ]
    session = FakeSession(results=results)

    report = compute_kappa_report(session)

    assert report["n"] == 3
    assert report["raw_agreement"] == pytest.approx(2 / 3)
    assert report["kappa"] is not None
    assert report["kappa_undefined_reason"] is None


def test_report_includes_full_confusion_matrix():
    results = [
        make_result(1, judge_verdict="pass", human_label="pass"),
        make_result(2, judge_verdict="fail", human_label="pass"),
        make_result(3, judge_verdict="needs_review", human_label="fail"),
    ]
    session = FakeSession(results=results)

    report = compute_kappa_report(session)

    assert report["confusion"]["pass"]["pass"] == 1
    assert report["confusion"]["pass"]["fail"] == 1
    assert report["confusion"]["fail"]["needs_review"] == 1
    # every category present even at zero, for a complete matrix
    assert report["confusion"]["needs_review"] == {"pass": 0, "fail": 0, "needs_review": 0}


def test_report_lists_disagreements_with_reason():
    results = [
        make_result(1, judge_verdict="pass", judge_reason="grounded", human_label="pass"),
        make_result(2, judge_verdict="pass", judge_reason="looked fine to me",
                    human_label="fail"),
    ]
    session = FakeSession(results=results)

    report = compute_kappa_report(session)

    assert len(report["disagreements"]) == 1
    d = report["disagreements"][0]
    assert d["result_id"] == 2
    assert d["human_label"] == "fail"
    assert d["judge_verdict"] == "pass"
    assert d["judge_reason"] == "looked fine to me"


def test_report_handles_zero_labeled_rows_without_crashing():
    session = FakeSession(results=[])

    report = compute_kappa_report(session)

    assert report["n"] == 0
    assert report["kappa"] is None
    assert report["kappa_undefined_reason"] is not None
    assert report["raw_agreement"] is None
    assert report["disagreements"] == []


def test_report_handles_no_variation_degenerate_sample_without_crashing():
    """Every row human=pass, judge=pass -- pe is forced to 1.0, kappa's
    (po-pe)/(1-pe) is 0/0. Must report a clear reason, not crash or claim
    a misleading kappa=1.0 / kappa=0.0."""
    results = [
        make_result(1, judge_verdict="pass", human_label="pass"),
        make_result(2, judge_verdict="pass", human_label="pass"),
    ]
    session = FakeSession(results=results)

    report = compute_kappa_report(session)

    assert report["n"] == 2
    assert report["kappa"] is None
    assert report["kappa_undefined_reason"] is not None
    assert report["raw_agreement"] == 1.0
    assert report["disagreements"] == []
