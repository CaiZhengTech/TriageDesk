"""Cohen's kappa unit tests -- pure function, hand-checked values (see report
for the hand-computed confusion-matrix derivation of the 0.583 constant)."""
import math

from triagedesk.evals.kappa import cohens_kappa


def test_perfect_agreement_is_one():
    a = ["pass", "fail", "needs_review", "pass"]
    assert cohens_kappa(a, list(a)) == 1.0


def test_chance_level_is_zero():
    # a always pass; b split 50/50 pass/fail => observed agreement == expected
    a = ["pass", "pass", "pass", "pass"]
    b = ["pass", "pass", "fail", "fail"]
    assert abs(cohens_kappa(a, b, categories=("pass", "fail"))) < 1e-9


def test_known_value():
    # 10 items: 8 agree, 2 disagree; marginals chosen so kappa is a clean number
    a = ["pass"] * 6 + ["fail"] * 4
    b = ["pass"] * 5 + ["fail"] * 1 + ["pass"] * 1 + ["fail"] * 3
    k = cohens_kappa(a, b, categories=("pass", "fail"))
    assert -1.0 <= k <= 1.0 and round(k, 3) == 0.583


def test_mismatched_lengths_raise():
    import pytest

    with pytest.raises(ValueError):
        cohens_kappa(["pass"], ["pass", "fail"])


def test_empty_lists_return_nan():
    assert math.isnan(cohens_kappa([], []))


def test_no_variation_both_raters_single_category_is_nan_not_crash():
    """Degenerate/small-sample case: every category except one is unused by
    BOTH raters => pe (chance agreement) is mathematically forced to 1.0, so
    (po - pe) / (1 - pe) is 0/0 -- undefined, not 1.0 and not a crash."""
    a = ["pass", "pass", "pass"]
    b = ["pass", "pass", "pass"]
    k = cohens_kappa(a, b, categories=("pass", "fail", "needs_review"))
    assert math.isnan(k)
