"""Cohen's kappa -- agreement between two labelers corrected for chance.
Hand-rolled (no scipy/sklearn for one function). kappa = (po - pe) / (1 - pe).

`pe` (chance-expected agreement) is forced to 1.0 only when every category
except one is unused by BOTH raters -- i.e. both labelers put every item in
the same single category. In that degenerate case (po - pe) / (1 - pe) is
0/0: mathematically undefined, not "perfect agreement" and not zero. We
return NaN so callers can detect and report this honestly instead of
crashing (ZeroDivisionError) or silently returning a misleading number.

Hardening Task 2 (issue #45) adds two more hand-rolled stats used by the
calibration report, still no scipy:
- `cohens_kappa_linear_weighted`: the judge/human labels are ORDINAL
  (fail < needs_review < pass), so a fail/pass disagreement is worse than a
  fail/needs_review one. Unweighted kappa treats every disagreement as
  equally bad; linear weighting penalizes by ordinal distance.
- `bootstrap_kappa_ci`: a single kappa point estimate on ~40-50 labeled
  pairs says nothing about how much it would move on a different sample.
  Percentile bootstrap gives an honest 95% interval, deterministic for a
  fixed seed so the calibration report is reproducible."""

import random


def cohens_kappa(labels_a, labels_b, categories=("pass", "fail", "needs_review")) -> float:
    if len(labels_a) != len(labels_b):
        raise ValueError("label lists must be equal length")
    n = len(labels_a)
    if n == 0:
        return float("nan")
    po = sum(a == b for a, b in zip(labels_a, labels_b, strict=True)) / n
    pe = 0.0
    for c in categories:
        pa = sum(a == c for a in labels_a) / n
        pb = sum(b == c for b in labels_b) / n
        pe += pa * pb
    if pe >= 1.0:
        return float("nan")
    return (po - pe) / (1 - pe)


def cohens_kappa_linear_weighted(
    labels_a, labels_b, ordering=("fail", "needs_review", "pass")
) -> float:
    """Linear-weighted Cohen's kappa for ordinal categories: disagreements
    are penalized proportionally to their distance in `ordering`, via
    weight w(i, j) = |i - j| / (k - 1) (0 for exact agreement, 1 for the two
    most-distant categories). Formula: 1 - (observed disagreement) /
    (expected disagreement), where both are weighted sums over the
    confusion matrix -- the direct ordinal generalization of the unweighted
    (po - pe) / (1 - pe) above. Same degenerate contract as cohens_kappa:
    NaN (never a crash or a misleading number) when n == 0 or expected
    disagreement is forced to 0 (both raters used only one category)."""
    if len(labels_a) != len(labels_b):
        raise ValueError("label lists must be equal length")
    n = len(labels_a)
    if n == 0:
        return float("nan")
    k = len(ordering)
    idx = {c: i for i, c in enumerate(ordering)}

    def w(i, j):
        return abs(i - j) / (k - 1)

    counts = [[0] * k for _ in range(k)]
    for a, b in zip(labels_a, labels_b, strict=True):
        counts[idx[a]][idx[b]] += 1

    marg_a = [sum(counts[i][j] for j in range(k)) / n for i in range(k)]
    marg_b = [sum(counts[i][j] for i in range(k)) / n for j in range(k)]

    observed = sum(w(i, j) * counts[i][j] / n for i in range(k) for j in range(k))
    expected = sum(w(i, j) * marg_a[i] * marg_b[j] for i in range(k) for j in range(k))
    if expected == 0:
        return float("nan")
    return 1 - observed / expected


def bootstrap_kappa_ci(labels_a, labels_b, n_boot=2000, seed=0):
    """Percentile bootstrap 95% CI for cohens_kappa (unweighted, default
    categories), deterministic for a fixed seed via `random.Random(seed)` --
    NOT the shared `random` module state, so this never interferes with (or
    is interfered by) other randomness elsewhere in the process. Resamples
    with replacement n times per bootstrap iteration; degenerate resamples
    (cohens_kappa returns NaN) are dropped rather than corrupting the
    percentile calculation. Returns (nan, nan) when there's nothing to
    resample (n == 0) or every resample degenerated."""
    if len(labels_a) != len(labels_b):
        raise ValueError("label lists must be equal length")
    n = len(labels_a)
    if n == 0:
        return (float("nan"), float("nan"))

    rng = random.Random(seed)
    samples = []
    for _ in range(n_boot):
        idxs = [rng.randrange(n) for _ in range(n)]
        a = [labels_a[i] for i in idxs]
        b = [labels_b[i] for i in idxs]
        k = cohens_kappa(a, b)
        if k == k:  # NaN check without importing math
            samples.append(k)

    if not samples:
        return (float("nan"), float("nan"))
    samples.sort()

    def percentile(pct):
        i = min(int(pct * len(samples)), len(samples) - 1)
        return samples[i]

    return (percentile(0.025), percentile(0.975))
