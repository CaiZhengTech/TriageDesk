"""Extract the human labels into a committable, ticket-text-free record (#18).

WHY THIS EXISTS
---------------
The 41 hand-applied judge-calibration labels are the most expensive artifact in
this project and the only one that cannot be regenerated: they cost human hours
and encode a judgment no script reproduces. They were also, until now, the least
protected thing in it -- `.gitignore` excluded `judge_labels*.csv` wholesale
("contains ticket text, never commit"), so the only copies lived on one laptop
and in a Neon branch that expired.

The exclusion was right about the ticket text and wrong about the labels. This
script splits them: the labels (result_id + verdict, a few hundred bytes) go
into version control, the ticket bodies and KB excerpts stay out. Both halves of
the original rule are satisfied.

WHAT IT PROVES, AND WHAT IT CANNOT
----------------------------------
Round 1 reproduces exactly: the marginals recomputed here (26 pass / 13 fail /
2 needs_review) match the published v1 confusion matrix. Round 2 does not --
see results/judge-calibration.md's provenance note. The surviving v2 file is a
mid-labeling snapshot (mtime 2026-07-16 21:43, a day before the round closed);
the completed set was imported to `eval_results.human_label` and died with the
database. This script records the discrepancy rather than hiding it.
"""

import csv
import json
import sys

SOURCES = [("round_1", "judge_labels.csv"), ("round_2_partial", "judge_labels_v2.csv")]
OUT_CSV = "results/human-labels.csv"
OUT_JSON = "results/human-labels-provenance.json"


def read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    cols, marginals = {}, {}
    ids = None
    for name, path in SOURCES:
        rows = read(path)
        cols[name] = [r["human_label"] for r in rows]
        marginals[name] = {c: cols[name].count(c) for c in ("pass", "fail", "needs_review")}
        # result_id differs per round (labels were re-exported against a new eval
        # run), so rows are keyed by position -- verified aligned by ticket body.
        if ids is None:
            ids = [r["result_id"] for r in rows]
            bodies = [r["ticket_body"][:80] for r in rows]
        elif [r["ticket_body"][:80] for r in rows] != bodies:
            raise SystemExit("row alignment broken: the two exports are not the same cases")
        cols[f"{name}_result_id"] = [r["result_id"] for r in rows]

    n = len(ids)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["case_index", "round_1_result_id", "round_1_label",
                    "round_2_result_id", "round_2_partial_label"])
        for i in range(n):
            w.writerow([i, cols["round_1_result_id"][i], cols["round_1"][i],
                        cols["round_2_partial_result_id"][i], cols["round_2_partial"][i]])

    flips = sum(a != b for a, b in zip(cols["round_1"], cols["round_2_partial"], strict=True))
    from triagedesk.evals.kappa import cohens_kappa
    provenance = {
        "_note": "Ticket text deliberately excluded; only labels are committed. "
                 "See results/judge-calibration.md for what each round supports.",
        "n_cases": n,
        "round_1": {
            "status": "COMPLETE — reproduces the published v1 confusion matrix exactly",
            "source": "judge_labels.csv (local, git-ignored: contains ticket text)",
            "marginals": marginals["round_1"],
            "published_marginals": {"pass": 26, "fail": 13, "needs_review": 2},
        },
        "round_2_partial": {
            "status": "INCOMPLETE — a mid-labeling snapshot, NOT the set the published "
                      "v2 kappa was computed from",
            "source": "judge_labels_v2.csv (local, git-ignored)",
            "marginals": marginals["round_2_partial"],
            "published_marginals": {"pass": 34, "fail": 5, "needs_review": 2},
            "why_lost": "The completed round-2 labels were imported to "
                        "eval_results.human_label and were destroyed when the Neon "
                        "branch expired (#64). eval_results is now empty.",
        },
        "self_agreement_from_surviving_files": {
            "cohens_kappa": round(cohens_kappa(cols["round_1"], cols["round_2_partial"]), 4),
            "flips": flips,
            "published_kappa": 0.212,
            "published_flips": 14,
            "interpretation": "Close to but not equal to the published 0.212, consistent "
                              "with a snapshot taken partway through round 2. Quote the "
                              "published figure as archived, not as reproducible.",
        },
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(provenance, fh, indent=2)
        fh.write("\n")

    print(f"wrote {OUT_CSV} ({n} cases) and {OUT_JSON}")
    print(f"  round 1 marginals      {marginals['round_1']}")
    print(f"  round 2 (partial)      {marginals['round_2_partial']}")
    self_agree = provenance["self_agreement_from_surviving_files"]["cohens_kappa"]
    print(f"  self-agreement kappa   {self_agree}  ({flips} flips)")
    if marginals["round_1"] != provenance["round_1"]["published_marginals"]:
        sys.exit("round 1 no longer matches its published matrix — investigate before publishing")


if __name__ == "__main__":
    main()
