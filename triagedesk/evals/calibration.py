"""Blind judge-calibration flow: export a CSV with no judge_verdict column ->
Cai labels human_label blind -> import writes eval_results.human_label ->
compute_kappa_report compares human_label vs judge_verdict via Cohen's kappa,
including the full confusion matrix and every disagreement row (a
deliverable in its own right -- see results/judge-calibration.md)."""

import csv

from triagedesk.evals.kappa import cohens_kappa
from triagedesk.models import EvalCase, EvalResult, KbDoc, Run, Span, Ticket

LABELS = ("pass", "fail", "needs_review")
_KB_EXCERPT_CHARS = 300

CSV_FIELDS = [
    "result_id", "ticket_subject", "ticket_body", "kb_slugs", "kb_excerpts",
    "customer_reply", "human_label",
]


def _kb_excerpt(doc) -> str:
    text = doc.content.strip().replace("\n", " ")
    if len(text) > _KB_EXCERPT_CHARS:
        text = text[:_KB_EXCERPT_CHARS].rstrip() + "..."
    return f"[{doc.slug}] {doc.title}: {text}"


def export_labels(session, out_csv: str) -> int:
    """Blind CSV for human labeling -- deliberately omits judge_verdict,
    judge_reason, and judge_rule_triggered so Cai cannot see the judge's
    call before labeling. Covers eval_results rows that HAVE a
    judge_verdict (those are the pairs kappa needs). Includes ticket text,
    the retrieved KB slugs + a trimmed excerpt of each, and the agent's
    drafted reply -- enough context for a fair blind grade."""
    rows = (session.query(EvalResult)
            .filter(EvalResult.judge_verdict.isnot(None))
            .order_by(EvalResult.id).all())
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(CSV_FIELDS)
        for r in rows:
            case = session.get(EvalCase, r.case_id)
            ticket = session.get(Ticket, case.ticket_id)
            run = session.get(Run, r.run_id)
            span = session.query(Span).filter_by(run_id=r.run_id, name="retrieve").first()
            slugs = (span.attributes or {}).get("retrieval.doc_slugs", []) if span else []
            kb_docs = session.query(KbDoc).filter(KbDoc.slug.in_(slugs)).all() if slugs else []
            kb_docs_by_slug = {d.slug: d for d in kb_docs}
            excerpts = " | ".join(
                _kb_excerpt(kb_docs_by_slug[s]) for s in slugs if s in kb_docs_by_slug
            )
            w.writerow([
                r.id, ticket.subject, ticket.body, ";".join(slugs), excerpts,
                (run.final_reply if run else "") or "", "",  # human_label blank; judge withheld
            ])
    return len(rows)


def import_labels(session, in_csv: str) -> int:
    """Safe to re-run: upserts human_label onto the matching eval_results
    row by result_id. Blank (or whitespace-only) human_label means "not
    labeled yet" and is silently skipped (Cai may label only some rows in a
    pass). The label is stripped and lowercased before validating -- Cai
    hand-edits this CSV in Excel, which autocapitalizes ("Pass") and can
    leave stray padding (" pass ") on a cell; normalizing first means one
    Excel quirk can't abort the import of an entire 40+ row hand-labeled
    batch. Still rejects any non-blank label outside {pass, fail,
    needs_review} -- fail loud on a genuine typo rather than silently
    corrupt the calibration set."""
    n = 0
    with open(in_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            label = (row.get("human_label") or "").strip().lower()
            if not label:
                continue
            if label not in LABELS:
                raise ValueError(
                    f"row result_id={row.get('result_id')!r}: invalid human_label "
                    f"{label!r} (must be one of {LABELS} or blank)"
                )
            result = session.get(EvalResult, int(row["result_id"]))
            if result is None:
                raise ValueError(
                    f"row result_id={row.get('result_id')!r}: no such eval_results row"
                )
            result.human_label = label
            n += 1
    session.commit()
    return n


def _confusion_matrix(human, judge):
    """{human_label: {judge_verdict: count}} -- rows=human, cols=judge,
    every category present (even at 0) for a complete matrix."""
    matrix = {h: dict.fromkeys(LABELS, 0) for h in LABELS}
    for h, j in zip(human, judge, strict=True):
        matrix[h][j] += 1
    return matrix


def compute_kappa_report(session) -> dict:
    """{n, kappa, kappa_undefined_reason, raw_agreement, confusion,
    disagreements}. Degenerate/small samples are handled honestly: if
    cohens_kappa returns NaN (no labeled pairs yet, or both raters used
    only one category so chance agreement is 100%), kappa is reported as
    None with kappa_undefined_reason explaining why, instead of crashing
    or silently reporting a misleading number. `disagreements` lists every
    row where human_label != judge_verdict -- "where the LLM judge
    diverged from human judgment" is a deliverable in its own right."""
    rows = (session.query(EvalResult)
            .filter(EvalResult.human_label.isnot(None),
                    EvalResult.judge_verdict.isnot(None))
            .order_by(EvalResult.id).all())
    n = len(rows)
    human = [r.human_label for r in rows]
    judge = [r.judge_verdict for r in rows]

    raw_agreement = (
        sum(h == j for h, j in zip(human, judge, strict=True)) / n if n else None
    )

    kappa_value = cohens_kappa(human, judge, categories=LABELS) if n else float("nan")
    if kappa_value != kappa_value:  # NaN check (math.isnan without importing math)
        kappa_out = None
        kappa_undefined_reason = (
            "no labeled pairs yet" if n == 0 else
            "no variation: human and judge both used only a single label category "
            "across all n rows, so chance agreement is 100% and kappa "
            "(po - pe) / (1 - pe) is 0/0 -- mathematically undefined"
        )
    else:
        kappa_out = kappa_value
        kappa_undefined_reason = None

    disagreements = [
        {"result_id": r.id, "human_label": r.human_label, "judge_verdict": r.judge_verdict,
         "judge_reason": r.judge_reason}
        for r in rows if r.human_label != r.judge_verdict
    ]

    return {
        "n": n,
        "kappa": kappa_out,
        "kappa_undefined_reason": kappa_undefined_reason,
        "raw_agreement": raw_agreement,
        "confusion": _confusion_matrix(human, judge),
        "disagreements": disagreements,
    }
