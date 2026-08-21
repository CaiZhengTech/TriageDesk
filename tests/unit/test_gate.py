from triagedesk.pipeline.act import ActOutcome
from triagedesk.pipeline.gate import (
    GATED_FEATURES,
    classification_margin,
    decide,
    gated_feature_implicated,
    load_centroids,
    load_global_mean,
)
from triagedesk.schemas import Resolution


def res(rtype):
    return Resolution(resolution_type=rtype, customer_reply="r", internal_rationale="i")


def outcome(rtype="solve", denied=False, checked=True):
    return ActOutcome(resolution=res(rtype), entitlement_denied=denied,
                       entitlement_checked=checked)


CENTROIDS = {"IT Support": [1.0, 0.0], "Billing and Payments": [0.0, 1.0]}


def test_margin_positive_when_near_predicted_centroid():
    m = classification_margin([0.9, 0.1], "IT Support", CENTROIDS)
    assert m > 0.5


def test_margin_negative_when_nearer_another_centroid():
    m = classification_margin([0.1, 0.9], "IT Support", CENTROIDS)
    assert m < 0


def test_confident_solve_auto_resolves():
    d = decide(retrieval_similarity=0.8, margin=0.3, outcome=outcome("solve"),
               entitlement_checked=True, gated_feature=None)
    assert d.auto_resolve is True
    assert d.signals == {
        "retrieval_similarity": 0.8,
        "classification_margin": 0.3,
        "entitlement_checked": True,
        "gated_feature": None,
    }


def test_low_similarity_escalates():
    d = decide(retrieval_similarity=0.2, margin=0.3, outcome=outcome("solve"),
               entitlement_checked=True, gated_feature=None)
    assert d.auto_resolve is False
    assert d.reason == "low_confidence"


def test_margin_sign_no_longer_changes_the_decision():
    """Was `test_low_margin_escalates` / `test_zero_margin_is_the_boundary`.

    Both encoded the pre-#74 rule that a negative margin vetoes auto-resolve.
    The margin is now observability only, so the sign is irrelevant to the
    outcome — asserted here rather than deleted, because "this input stopped
    mattering" is the behaviour change and deserves a test that says so."""
    for m in (-0.9, -0.01, 0.0, 0.9):
        d = decide(retrieval_similarity=0.8, margin=m, outcome=outcome("solve"),
                   entitlement_checked=True, gated_feature=None)
        assert d.auto_resolve is True, f"margin {m} should not block"
        assert d.signals["classification_margin"] == m


def test_deny_always_escalates_even_when_confident():
    d = decide(retrieval_similarity=0.99, margin=0.9, outcome=outcome("deny"),
               entitlement_checked=True, gated_feature=None)
    assert d.auto_resolve is False
    assert d.reason == "adverse_action"


def test_entitlement_denial_always_escalates():
    d = decide(retrieval_similarity=0.99, margin=0.9, outcome=outcome("solve", denied=True),
               entitlement_checked=True, gated_feature=None)
    assert d.auto_resolve is False
    assert d.reason == "adverse_action"


def test_needs_human_escalates():
    d = decide(retrieval_similarity=0.99, margin=0.9, outcome=outcome("needs_human"),
               entitlement_checked=True, gated_feature=None)
    assert d.auto_resolve is False
    assert d.reason == "agent_requested_human"


def test_solve_without_entitlement_evidence_escalates_legacy_shape():
    """Pre-#69 shape, kept: a gated feature IS implicated here."""
    d = decide(retrieval_similarity=0.99, margin=0.9, outcome=outcome("solve", checked=False),
               entitlement_checked=False, gated_feature="dedicated_ip")
    assert d.auto_resolve is False
    assert d.reason == "no_entitlement_evidence"


# --- the entitlement rule is SCOPED to plan-gated features (issue #69) ------
#
# The rule used to demand a `check_entitlement` receipt behind EVERY `solve`.
# That escalated tickets where no entitlement exists to check. Live evidence:
# demo ticket 80011 ("locked out after too many password attempts") retrieved
# its KB article at similarity 0.7175, the model wrote a correct unlock reply,
# and the gate escalated it as `no_entitlement_evidence` because password
# unlock is not a plan feature and so was never checked.
#
# The rule's real target is a soft denial the model never flagged — "sure,
# I've enabled that" for something the plan excludes. That risk only exists
# for features the plan can actually withhold.



def test_gated_features_are_derived_not_hardcoded():
    # Whatever Basic includes can never be denied, so it can never be the
    # subject of the soft denial this rule guards against.
    from triagedesk.tools import PLAN_ENTITLEMENTS
    assert GATED_FEATURES == (
        set().union(*PLAN_ENTITLEMENTS.values()) - PLAN_ENTITLEMENTS["basic"]
    )
    assert "standard_support" not in GATED_FEATURES
    assert "dedicated_ip" in GATED_FEATURES


def test_informational_ticket_implicates_no_gated_feature():
    assert gated_feature_implicated(
        "Locked out after too many password attempts",
        "I mistyped my password a few times and now the portal says my account is locked.",
        "Here's how to unlock it: use the self-service unlock link.",
    ) is None


def test_feature_request_is_detected_from_the_ticket():
    assert gated_feature_implicated(
        "Please assign us a dedicated IP address",
        "Our security team wants a single fixed IP so they can allowlist it.",
        "",
    ) == "dedicated_ip"


def test_feature_grant_is_detected_from_THE_REPLY_even_if_ticket_is_vague():
    # The dangerous case: the customer asks vaguely, the model promises a
    # gated feature in the reply. Scanning only the ticket would miss it.
    assert gated_feature_implicated(
        "Need help with my account",
        "Something isn't working right.",
        "No problem — I've turned on API access for you.",
    ) == "api_access"


def test_solve_without_entitlement_evidence_escalates_when_a_gated_feature_is_implicated():
    d = decide(retrieval_similarity=0.99, margin=0.9,
               outcome=outcome("solve", checked=False),
               entitlement_checked=False, gated_feature="dedicated_ip")
    assert d.auto_resolve is False
    assert d.reason == "no_entitlement_evidence"


def test_informational_solve_auto_resolves_without_an_entitlement_check():
    # The 80011 case. Nothing is being granted, so there is no receipt to
    # demand, and a KB-grounded answer should be allowed through.
    d = decide(retrieval_similarity=0.72, margin=0.3,
               outcome=outcome("solve", checked=False),
               entitlement_checked=False, gated_feature=None)
    assert d.auto_resolve is True
    assert d.reason is None


def test_gated_feature_is_recorded_in_the_signals_for_the_trace():
    d = decide(retrieval_similarity=0.72, margin=0.3, outcome=outcome("solve"),
               entitlement_checked=True, gated_feature="api_access")
    assert d.signals["gated_feature"] == "api_access"


def test_adverse_action_still_outranks_the_scoped_rule():
    # Scoping the entitlement rule must not weaken the unconditional one.
    d = decide(retrieval_similarity=0.99, margin=0.9,
               outcome=outcome("solve", denied=True, checked=True),
               entitlement_checked=True, gated_feature=None)
    assert d.auto_resolve is False
    assert d.reason == "adverse_action"


# --- mean-centring the margin (issue #67) ----------------------------------
#
# Support-ticket embeddings are strongly anisotropic. Measured on the committed
# centroids: mean pairwise cosine 0.9782, closest pair 0.9963. Raw cosines
# therefore differ only in the third decimal and their DIFFERENCE is noise.
# Centring removes the shared "this is a support ticket" direction.


# Two nearly-identical centroids sharing a large common component — the toy
# version of what the real 1024-dim centroids look like.
ANISOTROPIC = {
    "IT Support":           [10.0, 1.0, 0.0],
    "Billing and Payments": [10.0, 0.0, 1.0],
}
COMMON = [10.0, 0.5, 0.5]  # their global mean


def test_centring_widens_a_margin_that_is_nearly_zero_raw():
    """The core claim: same vectors, same ordering, bigger separation."""
    query = [10.0, 1.0, 0.0]  # unambiguously IT Support once the bulk is gone
    raw = classification_margin(query, "IT Support", ANISOTROPIC)
    centred = classification_margin(query, "IT Support", ANISOTROPIC, COMMON)
    assert 0 < raw < 0.01, f"raw margin should be swamped by the common component, got {raw}"
    assert centred > raw * 10


def test_centring_does_not_flip_the_sign_when_the_prediction_is_wrong():
    """Widening the range must not turn a disagreement into an agreement —
    centring changes the SCALE of the evidence, never its direction."""
    query = [10.0, 0.0, 1.0]  # actually Billing
    assert classification_margin(query, "IT Support", ANISOTROPIC) < 0
    assert classification_margin(query, "IT Support", ANISOTROPIC, COMMON) < 0


def test_global_mean_none_reproduces_the_uncentred_margin():
    """A v1 centroid file has no global mean; it must degrade to the old
    behaviour rather than crash."""
    query = [10.0, 1.0, 0.0]
    assert (classification_margin(query, "IT Support", ANISOTROPIC, None)
            == classification_margin(query, "IT Support", ANISOTROPIC))


def test_committed_centroid_file_is_loadable_and_consistent():
    centroids = load_centroids()
    mean = load_global_mean()
    assert len(centroids) == 10
    if mean is not None:  # v2
        dims = {len(v) for v in centroids.values()} | {len(mean)}
        assert len(dims) == 1, "global mean must match centroid dimensionality"


def test_committed_centroids_are_anisotropic_enough_to_need_centring():
    """Documents the measurement that justifies the change. If a future
    embedding model produces well-separated centroids, this fails and the
    centring should be revisited rather than cargo-culted."""
    from itertools import combinations

    from triagedesk.pipeline.gate import _cosine
    sims = [_cosine(a, b) for a, b in combinations(load_centroids().values(), 2)]
    assert sum(sims) / len(sims) > 0.8, (
        "centroids are no longer near-collinear; re-derive whether centring helps"
    )


# --- the margin is observability, not a veto (issue #74) -------------------
#
# Measured on held-out human labels (docs/week-4-launch/reports/
# margin-separation-measurement.md): the margin's ability to rank human-PASS
# replies above human-FAIL ones is AUC 0.337 / 0.442 across the two label
# rounds, with both 95% CIs spanning 0.50 — and the #67 repair moved that by
# +0.003 / 0.000. It cannot be shown to carry reply-quality information.
#
# A layer that BLOCKS work bears the burden of proof. The margin is still
# computed and still recorded in the trace, because it is genuinely interesting
# evidence about routing confidence — it just no longer vetoes a reply that
# passed every layer that can be justified.


def test_negative_margin_alone_no_longer_blocks_auto_resolve():
    """The 80011 case: a KB-answerable lockout ticket with strong retrieval
    (0.7175) and a strongly negative margin (-0.1409). Under the old gate the
    margin vetoed it; it now auto-resolves on the strength of the evidence that
    can actually be defended."""
    d = decide(retrieval_similarity=0.7175, margin=-0.1409, outcome=outcome("solve"),
               entitlement_checked=True, gated_feature=None)
    assert d.auto_resolve is True
    assert d.reason is None


def test_low_similarity_still_blocks():
    """retrieval_similarity keeps its veto. It is the only signal above 0.50 in
    both label rounds (0.559 / 0.643), and its 0.45 threshold was derived from
    the held-out pool — unchanged here, because re-tuning a threshold while
    changing what it gates is how you launder a tuning decision."""
    d = decide(retrieval_similarity=0.2, margin=0.9, outcome=outcome("solve"),
               entitlement_checked=True, gated_feature=None)
    assert d.auto_resolve is False
    assert d.reason == "low_confidence"


def test_margin_is_still_recorded_for_the_trace():
    """Demoted, not deleted. The glass box still shows it."""
    d = decide(retrieval_similarity=0.8, margin=-0.5, outcome=outcome("solve"),
               entitlement_checked=True, gated_feature=None)
    assert d.signals["classification_margin"] == -0.5
    assert d.auto_resolve is True


def test_safety_layers_still_outrank_everything():
    """Regression guard on the whole point of the project: demoting a
    statistical layer must not weaken any of the three rules that do the real
    work. Each must still fire on perfect signals."""
    perfect = dict(retrieval_similarity=0.99, margin=0.9, gated_feature=None)
    assert decide(**perfect, outcome=outcome("deny"),
                  entitlement_checked=True).reason == "adverse_action"
    assert decide(**perfect, outcome=outcome("solve", denied=True),
                  entitlement_checked=True).reason == "adverse_action"
    assert decide(**perfect, outcome=outcome("needs_human"),
                  entitlement_checked=True).reason == "agent_requested_human"
    assert decide(retrieval_similarity=0.99, margin=0.9,
                  outcome=outcome("solve", checked=False),
                  entitlement_checked=False,
                  gated_feature="api_access").reason == "no_entitlement_evidence"
