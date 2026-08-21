"""Does the gate's margin actually separate good replies from bad? (Refs #67)

  set TRIAGEDESK_ENV_FILE=...
  python -m scripts.measure_margin_separation            # both label rounds
  python -m scripts.measure_margin_separation --round 2  # one round

THE QUESTION
------------
`docs/week-2-evals/reports/threshold-derivation.md` measured the ORIGINAL gate
signals against 22 held-out human-labelled replies and found they carry no
reply-quality information — worse, they were *directionally inverted*:
human-fail replies scored slightly HIGHER similarity and margin than human-pass
ones. That is why the report concluded "the thresholds cannot carry quality
assurance."

Issue #67 repaired the margin (matched `input_type`, mean-centring) and widened
its usable range ~26x. Widening a signal is not the same as making it
*informative*, so the council protocol says: re-measure on the held-out data,
then decide whether the margin keeps its veto or becomes an observability
signal. This script is that measurement.

WHY THIS IS A FAIR TEST
-----------------------
The labels come from `judge_labels*.csv` — Cai's blind human labels on the
calibration pool, recorded in 2026-07-14 and committed to the repo. They are
HELD OUT from the golden set by construction, and they were written long before
the fix existed, so there is no way to tune toward them. This is the opposite of
authoring a fresh test set for the behaviour you want to demonstrate.

METHOD, AND ITS ONE HONEST WEAKNESS
-----------------------------------
The margin is a property of (ticket, predicted queue) — not of the reply — so it
can be recomputed for a labelled reply without regenerating that reply. Ticket
text and reply text survive in the CSV; the predicted queue does not (it lived
on the classify span, lost with the database), so it is re-derived by running
classify again.

Classify is pinned to temperature=0 with an unchanged prompt version, so the
re-derived queue should match the original — but "should" is not "does", and a
queue that differs from the original run's changes that row's margin. Rows are
reported with their queue so a spot-check is possible.

Old and new margins are computed from the SAME ticket embedding and the SAME
predicted queue, differing only in the centroid file — so the comparison
isolates the fix.

METRIC
------
AUC (equivalently Mann-Whitney U / n_pass·n_fail): the probability that a
randomly chosen human-PASS reply scores higher than a randomly chosen
human-FAIL reply.

    0.50  = no separation, the signal is noise
    >0.50 = higher score means better reply (the useful direction)
    <0.50 = INVERTED — higher score means worse reply

AUC is used rather than a difference of means because it is rank-based: immune
to the scale change the fix introduced, which is exactly the confound a
means comparison would suffer from here.
"""

import argparse
import csv
import json
import subprocess
import time
from pathlib import Path

from sqlalchemy import text

from triagedesk.db import SessionLocal
from triagedesk.embeddings import embed_batch
from triagedesk.llm import structured_call
from triagedesk.pipeline.gate import classification_margin
from triagedesk.prompts import CLASSIFY_SYSTEM
from triagedesk.schemas import ClassifyResult

ROUNDS = {1: Path("judge_labels.csv"), 2: Path("judge_labels_v2.csv")}
NEW_CENTROIDS = Path("triagedesk/data/queue_centroids.json")
# Signals cost ~$0.07 of classify calls to produce and never change unless the
# centroids or the label set do. Cached so re-analysis (different metrics, CIs,
# thresholds) is free — the analysis is the part you iterate on, not the data.
CACHE = Path("results/margin-separation-signals.json")
SUB_BATCH = 25
REQUEST_PAUSE_SECONDS = 21


def load_old_centroids() -> dict[str, list[float]] | None:
    """The pre-#67 centroid file, read straight out of git history so the
    before/after runs against identical inputs."""
    for rev in ("c662659~1", "HEAD~20"):
        try:
            blob = subprocess.check_output(
                ["git", "show", f"{rev}:triagedesk/data/queue_centroids.json"],
                text=True, stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            continue
        data = json.loads(blob)
        if "centroids" not in data:  # v1 was a bare mapping
            return data
    return None


def auc(pos: list[float], neg: list[float]) -> float | None:
    """Probability a random `pos` outranks a random `neg`; ties count a half."""
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def auc_ci(pos, neg, iters=4000, seed=20260821):
    """Bootstrap 95% CI for the AUC.

    With ~11-13 human-FAIL replies, a point estimate alone invites reading
    noise as signal in whichever direction suits the argument. The CI is what
    decides whether a result is reportable: if it straddles 0.50, the honest
    statement is "this sample cannot tell", not "it separates" and not "it is
    inverted"."""
    import random
    rng = random.Random(seed)
    vals = []
    for _ in range(iters):
        a = auc([rng.choice(pos) for _ in pos], [rng.choice(neg) for _ in neg])
        if a is not None:
            vals.append(a)
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))]


def kb_similarity(session, vec: list[float]) -> float:
    row = session.execute(
        text("SELECT 1 - (embedding <=> CAST(:v AS vector)) AS sim "
             "FROM kb_docs ORDER BY embedding <=> CAST(:v AS vector) LIMIT 1"),
        {"v": str(vec)},
    ).first()
    return float(row[0]) if row else 0.0


def compute_signals(use_cache: bool = True) -> dict[str, dict]:
    """Signals for each labelled ticket, keyed by result_id.

    Computed ONCE and reused across both label rounds: the two rounds relabel
    the same 41 replies three days apart, so the signals are identical by
    construction and only the labels differ. Classifying twice would both waste
    money and let classify non-determinism leak in as a spurious difference
    between rounds.
    """
    if use_cache and CACHE.exists():
        signals = json.loads(CACHE.read_text())
        print(f"loaded {len(signals)} cached signals from {CACHE} "
              f"(--refresh to recompute, ~$0.07)")
        return signals

    rows = {}
    for path in ROUNDS.values():
        for r in csv.DictReader(path.open(encoding="utf-8")):
            if r["human_label"]:
                rows.setdefault(r["result_id"], r)
    rows = list(rows.values())
    print(f"{len(rows)} distinct labelled tickets across both rounds")

    new = json.loads(NEW_CENTROIDS.read_text())
    new_centroids, global_mean = new["centroids"], new["global_mean"]
    old_centroids = load_old_centroids()
    if old_centroids is None:
        print("  (could not recover pre-#67 centroids from git; reporting new only)")

    texts = [f"{r['ticket_subject']}\n{r['ticket_body']}"[:4000] for r in rows]
    vecs: list[list[float]] = []
    for i in range(0, len(texts), SUB_BATCH):
        vecs += embed_batch(texts[i:i + SUB_BATCH], "query")  # matches retrieve.py
        time.sleep(REQUEST_PAUSE_SECONDS)  # Voyage free tier: 3 RPM / 10K TPM
    print(f"  embedded {len(vecs)} tickets (query input_type)")

    session = SessionLocal()
    signals = {}
    try:
        for r, txt, vec in zip(rows, texts, vecs, strict=True):
            result, _ = structured_call(
                system=CLASSIFY_SYSTEM, user=f"<ticket>\n{txt}\n</ticket>",
                schema=ClassifyResult, max_tokens=256, temperature=0,
            )
            queue = result.queue
            rec = {
                "queue": queue,
                "sim": kb_similarity(session, vec),
                "new_margin": classification_margin(vec, queue, new_centroids, global_mean),
            }
            if old_centroids and queue in old_centroids:
                rec["old_margin"] = classification_margin(vec, queue, old_centroids)
            signals[r["result_id"]] = rec
            print(f"    {queue:30s} new={rec['new_margin']:+.4f} sim={rec['sim']:.3f}",
                  flush=True)
    finally:
        session.close()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(signals, indent=2))
    print(f"  cached {len(signals)} signals -> {CACHE}")
    return signals


def report(round_no: int, signals: dict[str, dict]) -> None:
    path = ROUNDS[round_no]
    labelled = [r for r in csv.DictReader(path.open(encoding="utf-8")) if r["human_label"]]
    print(f"\n{'=' * 74}")
    print(f"ROUND {round_no}  ({path}) — {len(labelled)} human-labelled replies")
    print("=" * 74)

    recs = [dict(signals[r["result_id"]], label=r["human_label"])
            for r in labelled if r["result_id"] in signals]
    p = [x for x in recs if x["label"] == "pass"]
    f = [x for x in recs if x["label"] == "fail"]
    print(f"  n_pass={len(p)}  n_fail={len(f)}  "
          f"n_needs_review={sum(1 for x in recs if x['label'] == 'needs_review')}")
    print(f"\n  {'signal':<26} {'AUC':>8}   verdict")
    print(f"  {'-' * 26} {'-' * 8}   {'-' * 42}")
    for key, name in (("old_margin", "margin (pre-#67)"),
                      ("new_margin", "margin (post-#67)"),
                      ("sim", "retrieval_similarity")):
        if not recs or key not in recs[0]:
            continue
        pv, nv = [x[key] for x in p], [x[key] for x in f]
        a = auc(pv, nv)
        if a is None:
            continue
        lo, hi = auc_ci(pv, nv)
        verdict = ("CANNOT TELL at this n (CI spans 0.50)" if lo <= 0.5 <= hi else
                   "INVERTED - higher = worse reply" if hi < 0.5 else
                   "separates: higher = better reply")
        print(f"  {name:<26} {a:>7.3f}  [{lo:.2f}, {hi:.2f}]   {verdict}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="measure_margin_separation")
    ap.add_argument("--round", type=int, choices=[1, 2], default=None,
                    help="label round (default: both)")
    ap.add_argument("--refresh", action="store_true",
                    help="recompute signals instead of using the cache (~$0.07)")
    args = ap.parse_args()
    signals = compute_signals(use_cache=not args.refresh)
    for n in ([args.round] if args.round else [1, 2]):
        report(n, signals)
    print("\n  AUC 0.50 = noise. Below ~0.45 the signal is actively misleading.")
    print("  A signal that does not separate cannot justify a veto over auto-resolve.")


if __name__ == "__main__":
    main()
