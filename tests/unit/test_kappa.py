"""Cohen's kappa unit tests -- pure function, hand-checked values (see report
for the hand-computed confusion-matrix derivation of the 0.583 constant)."""
import math

import pytest

from triagedesk.evals.kappa import bootstrap_kappa_ci, cohens_kappa, cohens_kappa_linear_weighted


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


# ------------------------------------------------------- linear-weighted kappa

def test_linear_weighted_kappa_hand_checked_value():
    """Hand-computed 3-category ("fail","needs_review","pass", indices 0/1/2,
    k=3) example. a = [fail, fail, needs_review, pass],
    b = [fail, needs_review, needs_review, pass], n=4.

    Joint counts (row=a idx, col=b idx): (0,0)=1, (0,1)=1, (1,1)=1, (2,2)=1,
    every other cell 0.
    Marginals: a = [0.5, 0.25, 0.25] (fail, needs_review, pass);
               b = [0.25, 0.5, 0.25].
    Linear disagreement weight w(i,j) = |i-j| / (k-1) = |i-j| / 2.

    observed disagreement = sum_ij w(i,j) * count(i,j) / n
      = w(0,1) * 1/4              (only (0,1) has both count>0 and w>0)
      = 0.5 * 0.25 = 0.125

    expected disagreement = sum_ij w(i,j) * a_i * b_j over all 9 cells:
      (0,1): 0.5 * 0.5  * 0.5  = 0.125
      (0,2): 1.0 * 0.5  * 0.25 = 0.125
      (1,0): 0.5 * 0.25 * 0.25 = 0.03125
      (1,2): 0.5 * 0.25 * 0.25 = 0.03125
      (2,0): 1.0 * 0.25 * 0.25 = 0.0625
      (2,1): 0.5 * 0.25 * 0.5  = 0.0625
      (all i==j cells have w=0)
      sum = 0.4375

    weighted kappa = 1 - 0.125 / 0.4375 = 1 - 0.285714... = 0.714285...
      -> round(3) == 0.714

    Unweighted kappa on the SAME data: po = 3/4 (rows 0,2,3 agree) = 0.75;
    pe = (0.5*0.25)+(0.25*0.5)+(0.25*0.25) = 0.125+0.125+0.0625 = 0.3125;
    kappa = (0.75-0.3125)/(1-0.3125) = 0.4375/0.6875 = 0.636363...
      -> round(3) == 0.636. Different from the weighted value -- proves
    weighting actually changes the result instead of silently degenerating
    to cohens_kappa."""
    a = ["fail", "fail", "needs_review", "pass"]
    b = ["fail", "needs_review", "needs_review", "pass"]
    weighted = cohens_kappa_linear_weighted(a, b, ordering=("fail", "needs_review", "pass"))
    assert round(weighted, 3) == 0.714
    unweighted = cohens_kappa(a, b, categories=("fail", "needs_review", "pass"))
    assert round(unweighted, 3) == 0.636
    assert weighted != unweighted


def test_linear_weighted_kappa_perfect_agreement_is_one():
    a = ["pass", "fail", "needs_review", "pass"]
    assert cohens_kappa_linear_weighted(a, list(a)) == 1.0


def test_linear_weighted_kappa_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        cohens_kappa_linear_weighted(["pass"], ["pass", "fail"])


def test_linear_weighted_kappa_empty_lists_return_nan():
    assert math.isnan(cohens_kappa_linear_weighted([], []))


def test_linear_weighted_kappa_no_variation_is_nan_not_crash():
    """Same degenerate case as the unweighted test: both raters use only one
    category => expected disagreement is forced to 0 (every nonzero-marginal
    cell has w=0), so observed/expected disagreement is 0/0 -- undefined."""
    a = ["pass", "pass", "pass"]
    b = ["pass", "pass", "pass"]
    k = cohens_kappa_linear_weighted(a, b, ordering=("fail", "needs_review", "pass"))
    assert math.isnan(k)


# ---------------------------------------------------------- bootstrap kappa CI

_BOOT_A = ["pass", "pass", "fail", "fail", "needs_review", "pass", "fail", "pass",
          "needs_review", "fail"]
_BOOT_B = ["pass", "fail", "fail", "fail", "needs_review", "pass", "pass", "pass",
          "needs_review", "needs_review"]


def test_bootstrap_kappa_ci_deterministic_for_fixed_seed():
    ci_1 = bootstrap_kappa_ci(_BOOT_A, _BOOT_B, n_boot=200, seed=0)
    ci_2 = bootstrap_kappa_ci(_BOOT_A, _BOOT_B, n_boot=200, seed=0)
    assert ci_1 == ci_2  # same seed -> byte-for-byte identical interval


def test_bootstrap_kappa_ci_contains_point_estimate():
    point = cohens_kappa(_BOOT_A, _BOOT_B)
    lo, hi = bootstrap_kappa_ci(_BOOT_A, _BOOT_B, n_boot=500, seed=0)
    assert lo <= point <= hi


def test_bootstrap_kappa_ci_is_ordered_lo_le_hi():
    lo, hi = bootstrap_kappa_ci(_BOOT_A, _BOOT_B, n_boot=200, seed=0)
    assert lo <= hi


def test_bootstrap_kappa_ci_empty_lists_return_nan_tuple():
    lo, hi = bootstrap_kappa_ci([], [])
    assert math.isnan(lo)
    assert math.isnan(hi)


def test_bootstrap_kappa_ci_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        bootstrap_kappa_ci(["pass"], ["pass", "fail"])
