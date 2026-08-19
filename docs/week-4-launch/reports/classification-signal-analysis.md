# Can the classification signal be optimised?

**Question asked:** can the classification algorithm be improved so the gate's margin
actually does something?

**Short answer:** the *accuracy* cannot be meaningfully improved — ~30% is a ceiling
imposed by the label set, and two independent methods now agree on that number. The
*margin signal* can be improved a great deal, and two of its problems are outright
defects rather than tuning opportunities.

**Cost of this investigation:** $0 against the Anthropic budget. The centroid geometry is
pure offline arithmetic on a committed file; the ticket experiment used 50 Voyage
embeddings on the free tier.

---

## Method

Two experiments, both reproducible.

1. **Centroid geometry, offline.** Pairwise cosine between the 10 committed queue
   centroids (`triagedesk/data/queue_centroids.json`), before and after subtracting their
   global mean. No API calls at all.
2. **Real tickets.** 50 tickets, 5 per queue, sampled deterministically
   (`random.Random(20260819)`) from the source corpus. Embedded both ways — `input_type`
   `"query"` (what production does) and `"document"` (what the centroids were built with)
   — then scored by nearest centroid, raw and mean-centred.

---

## Finding 1 — the queue taxonomy does not separate in embedding space

Pairwise cosine between the 10 queue centroids:

| | value |
|---|---|
| mean | **0.9782** |
| max | **0.9963** — Technical Support ↔ IT Support |
| min | 0.9422 |
| every centroid's cosine to the global mean | 0.9708 – 0.9974 |

Ten "different" categories whose prototypes are 0.978 cosine apart are not ten
categories. **Technical Support and IT Support at 0.9963 are one category with two
names.** Product Support ↔ Returns and Exchanges (0.9952) and Sales ↔ General Inquiry
(0.9951) are barely better.

This is the first *quantitative* evidence for the project's long-standing "29% routing
accuracy is a dataset-noise finding, not a defect" claim. Until now that claim rested on
inspection. It can now be stated as a measurement.

## Finding 2 — ~30% is a ceiling, not a starting point

| Method | Top-1 accuracy vs dataset label |
|---|---|
| LLM classifier (recorded, full golden runs) | **29%** |
| Nearest-centroid on embeddings (this experiment, n=50) | **28%** |
| Random baseline, 10 classes | 10% |

An LLM reading the ticket and a cosine comparison against centroids — two methods with
nothing in common — land **within one point of each other**, and both at roughly 3×
random. When two unrelated approaches converge like that, the constraint is the labels,
not the classifier.

**Consequence: there is no tuning that gets this materially higher, and chasing it would
be overfitting to noisy labels.** That is the honest answer to "can we optimise the
classification algorithm."

## Finding 3 — the *margin signal* has two real defects

The gate's margin is
`cos(ticket, centroid[predicted]) − max cos(ticket, centroid[other])`.

### Defect A — `input_type` mismatch

`triagedesk/pipeline/retrieve.py:20` embeds the ticket with `embed_query(...)` →
`input_type="query"`. `scripts/compute_centroids.py` built the centroids with
`embed_documents(...)` → `input_type="document"`.

Voyage trains those two input types **asymmetrically on purpose** — a query and its
matching document are meant to land near each other despite being phrased differently.
That asymmetry is exactly right for the KB search this same vector performs, and exactly
wrong for the margin, which compares a ticket to a *prototype of tickets*. Both sides of
a classification comparison should be the same input type.

### Defect B — anisotropy swamps the signal

Because every centroid is ~0.98 cosine to every other, `cos(ticket, centroid_i)` varies
only in the third decimal across queues. The margin — a *difference* of two such numbers
— is therefore a tiny quantity dominated by the shared "this is a support ticket"
direction. The recorded margin range on held-out data (−0.0267 to +0.0290) is exactly
what this predicts.

Subtracting the global mean before comparing removes the shared component and leaves what
actually distinguishes the queues. Centred, the same 10 centroids span −0.71 to +0.75
instead of 0.94 to 0.996.

---

## Measured effect of fixing both

n = 50 tickets, nearest-centroid, dataset labels as truth:

| Configuration | Accuracy | margin > 0 | **margin spread** |
|---|---|---|---|
| **Production today** (query vs doc-centroids, raw) | 28.0% | 14/50 | **0.203** |
| Matched `input_type` only | 30.0% | 15/50 | 0.151 |
| Mean-centring only | 30.0% | 15/50 | 1.318 |
| **Both fixes** | **34.0%** | 17/50 | **1.771** |

### Reading this honestly

**The accuracy column is not a result.** At n = 50, six percentage points is three
tickets. It is nowhere near significant, and it should not be quoted as "I improved
classification accuracy from 28% to 34%." Finding 2 is the real story about accuracy, and
it says the ceiling is elsewhere.

**The spread column is a result.** It is not a statistical estimate — it is a
deterministic geometric property of the vectors. The usable range of the margin widens
**~8.7×**. That is the difference between a statistic whose variation is noise in the
third decimal and one that can carry a decision.

### Why this makes `low_confidence` a live gate layer

`docs/week-2-evals/reports/threshold-derivation.md` already found the margin near-useless:
only 4 of 22 held-out rows cleared `margin ≥ 0`, and the old `0.02` threshold was
"structurally near-unreachable" at 1 of 22. That was diagnosed as a *threshold* problem
and fixed by lowering the threshold to the semantic zero.

The geometry says it was never a threshold problem. **The signal itself was flat.** The
threshold was lowered to compensate for a signal that could not discriminate — and the
same report honestly recorded that the signals "carry no reply-quality information",
with human-fail replies scoring *higher* similarity and margin than human-pass ones.

Note what this does **not** require: `MARGIN_THRESHOLD = 0.0` stays correct. Zero is a
*semantic* boundary — "the embedding evidence agrees with the LLM's queue choice" — not a
tuned value, and it keeps that meaning under both fixes. The threshold does not move; the
signal underneath it gets a real dynamic range.

---

## Proposed change, and the protocol it must follow

This touches a gate signal, so the council's hold-out rule applies in full. The sequence
is not negotiable:

1. **Recompute centroids with `input_type="query"`**, matching the runtime. One-off,
   offline, Voyage only (~15 min at free-tier pacing). Requires the database populated.
2. **Mean-centre in `classification_margin()`.** Store the global mean next to the
   centroids so it is committed, deterministic, and CI never calls Voyage — the property
   `compute_centroids.py` already protects.
3. **Re-derive thresholds from the held-out calibration pool**, never the golden set, and
   never by choosing a value that makes the golden numbers look better.
4. **Re-baseline** `results/eval-baseline.json` (already required anyway — the golden set
   changed membership in #64).
5. **Report the before/after honestly**, including that the accuracy ceiling did not move.

### What must NOT happen

- No threshold nudging to produce more auto-resolves. If the fixed signal escalates more,
  that is the answer.
- No claim that classification accuracy improved. It did not, measurably.
- No touching the adverse-action rule, the entitlement-receipt rule, or the prompts. The
  binding safety layers are unaffected by any of this, and they remain the reason the
  system fails closed.

---

## The interview version

> "My routing accuracy was 29%, which looks terrible. I wanted to know whether that was my
> classifier or my data, so I measured the geometry: the ten queue centroids have a mean
> pairwise cosine of 0.978, and Technical Support versus IT Support is 0.996. They aren't
> ten separable categories. Then I checked a completely different method — nearest
> centroid on embeddings instead of an LLM — and it scored 28%. Two unrelated approaches
> within a point of each other means the ceiling is the label set.
>
> What I *did* find was a real bug. The gate's confidence margin compared a ticket
> embedded as a query against centroids built as documents — Voyage makes those
> deliberately asymmetric — and on top of that the raw cosines were dominated by a common
> component, so the margin only varied in the third decimal. Mean-centring and matching
> the input type widen its usable range about ninefold. It doesn't make the routing more
> accurate — nothing would — but it turns the confidence signal from noise into something
> that can actually gate a decision."

That is a better answer than a fixed number, because it demonstrates telling the
difference between a model problem and a data problem — and being willing to say which
one you have.
