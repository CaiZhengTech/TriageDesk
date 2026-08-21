# Does the repaired margin separate good replies from bad? (Refs #67)

**Short answer: no — and this sample cannot prove it either way.**

Reproduce with `python -m scripts.measure_margin_separation` (free, from cache;
`--refresh` recomputes for ~$0.07).

---

## Why this measurement exists

Issue #67 repaired the gate's `classification_margin`: matched the Voyage
`input_type` to the runtime, and mean-centred to remove the shared component.
The usable range widened ~26×, and ticket 80010 auto-resolved for the first
time in the project's history.

**Widening a signal is not the same as making it informative.** The council
protocol therefore required re-measuring on held-out human labels *before*
deciding whether the margin keeps its power to veto auto-resolve. This is that
measurement.

## Why it's a fair test

The labels are Cai's blind human labels on the calibration pool, recorded
2026-07-14 and committed as `judge_labels.csv` / `judge_labels_v2.csv`. They are
held out from the golden set by construction, and were written **weeks before
the fix existed** — there is no path by which the fix could have been tuned
toward them. This is the opposite of the trap the council's peer reviewers
flagged (authoring a fresh test set for the behaviour you want to demonstrate).

## Method

The margin is a property of `(ticket, predicted queue)`, **not of the reply**,
so it can be recomputed for an already-labelled reply without regenerating that
reply. Ticket and reply text survive in the CSVs; the predicted queue does not
(it lived on the classify span, lost with the database), so it was re-derived by
re-running classify at `temperature=0` with the unchanged prompt version.

Old and new margins come from the **same ticket embedding and the same predicted
queue**, differing only in the centroid file — so the comparison isolates the fix.

**Metric: AUC** — the probability a randomly chosen human-PASS reply scores
higher than a randomly chosen human-FAIL reply. Chosen over a difference of
means because it is rank-based and therefore immune to the scale change the fix
introduced — exactly the confound a means comparison would suffer here. 95% CIs
by bootstrap (4000 resamples).

---

## Results

### Round 1 — n_pass 26, n_fail 13

| signal | AUC | 95% CI | verdict |
|---|---|---|---|
| margin (pre-#67) | 0.334 | [0.17, 0.52] | cannot tell |
| margin (post-#67) | 0.337 | [0.17, 0.52] | cannot tell |
| retrieval_similarity | 0.559 | [0.38, 0.74] | cannot tell |

### Round 2 — n_pass 28, n_fail 11

| signal | AUC | 95% CI | verdict |
|---|---|---|---|
| margin (pre-#67) | 0.442 | [0.26, 0.63] | cannot tell |
| margin (post-#67) | 0.442 | [0.26, 0.63] | cannot tell |
| retrieval_similarity | 0.643 | [0.46, 0.81] | cannot tell |

**Every interval spans 0.50.** At ~39 usable labels with only 11–13 failures,
this dataset cannot establish separation for any signal in any direction.

---

## Finding 1 — the repair did not make the margin informative

This is the one robust result, because it is **paired on identical data**: same
tickets, same labels, same predicted queues, only the centroid file differs.

| | pre-#67 | post-#67 | Δ |
|---|---|---|---|
| Round 1 | 0.334 | 0.337 | **+0.003** |
| Round 2 | 0.442 | 0.442 | **0.000** |

The fix changed the margin's ability to rank good replies above bad ones by
essentially **zero**.

So #67 made the margin **decisive** (26× range; it did unblock ticket 80010) but
not **informative**. Those are different properties, and the distinction matters:
the auto-resolve that resulted is real, but it is not evidence that the gate is
now making *better* decisions — only that it is making *more decisive* ones.

The likely reason is structural rather than statistical. The margin asks *"did
the router agree with itself about which queue this belongs in?"* The gate's
actual decision is *"may this reply be sent unseen?"* Repairing an instrument
does not change what it measures.

## Finding 2 — the project's "directionally inverted" claim is overstated

`docs/week-2-evals/reports/threshold-derivation.md` reports the signals as
"directionally inverted", citing human-fail replies scoring *higher* mean
similarity and margin than human-pass ones (n=22).

That was a **difference of means without an uncertainty estimate**. Re-measured
with a rank-based metric and bootstrap CIs on a larger slice of the same labels,
the correct statement is **"cannot tell at this sample size"** — not "inverted".
The direction of the point estimate is unstable across label rounds (0.334 vs
0.442 for the identical signal), which is what noise looks like.

This does not rescue the margin — "cannot be shown to help" is not "helps" — but
the existing doc claims more than the data supports and should be corrected.

## Finding 3 — the rounds disagree with each other

Round 1 and Round 2 score the **identical signal** at 0.334 and 0.442. The only
thing that changed is which day the same person labelled the same 41 replies.

This is the project's measured self-agreement problem (Cohen's kappa 0.212)
surfacing from a new angle, and it independently confirms the standing
conclusion: **single-rater ground truth is the binding constraint**, not the
model and not the gate.

## Finding 4 — retrieval_similarity is the only signal leaning the right way

0.559 and 0.643 — above 0.50 in both rounds, unlike the margin. Still not
significant, and not actionable on its own. Worth noting because it is also the
signal that asks a question closer to the actual decision: *does a document that
answers this ticket exist?* rather than *which folder does this belong in?*

---

## The decision this feeds, and the honest case on both sides

**Keep the margin's veto:** `threshold-derivation.md` never claimed it predicted
reply quality — its stated job was narrower, "refuse to auto-resolve when the
classification/retrieval evidence is weak, as a defence-in-depth backstop." This
measurement tests reply-quality prediction, so it does not refute that narrower
claim.

**Demote it to observability:** if it cannot be shown to carry reply-quality
information, then blocking on it rejects good and bad replies at the same rate —
pure throughput loss with no demonstrated safety gain. The three layers that do
the real work (`adverse_action`, `agent_requested_human`, `no_entitlement_evidence`)
are unaffected either way, and were verified live to still escalate correctly.

**A caveat that binds both:** demoting would mean acting on a **null result**.
Absence of evidence at n=39 is not evidence of absence. Whichever way this goes,
the reasoning belongs in the case study alongside the number — the defensible
position is not "the margin is useless" but "we could not demonstrate it helps,
and the burden of proof sits with a layer that blocks work."

## What would actually settle it

More labels — specifically **more failures**, since 11–13 is what pins the CIs
open. A second rater (issue #19's original intent) fixes both this and the
kappa-0.212 problem in one pass.

The measurement infrastructure now exists and is **free to re-run**: signals are
cached in `results/margin-separation-signals.json`, so adding labels and
re-measuring costs nothing. **The blocker is labels, not code.**
