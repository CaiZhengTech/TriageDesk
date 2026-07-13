"""Cohen's kappa -- agreement between two labelers corrected for chance.
Hand-rolled (no scipy/sklearn for one function). kappa = (po - pe) / (1 - pe).

`pe` (chance-expected agreement) is forced to 1.0 only when every category
except one is unused by BOTH raters -- i.e. both labelers put every item in
the same single category. In that degenerate case (po - pe) / (1 - pe) is
0/0: mathematically undefined, not "perfect agreement" and not zero. We
return NaN so callers can detect and report this honestly instead of
crashing (ZeroDivisionError) or silently returning a misleading number."""


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
