"""Multi-signal confidence gate. Signals are EXTERNAL gauges only — the LLM's
self-reported confidence is never consulted (spec rule). Adverse actions
(deny / entitlement denial) escalate unconditionally.

WHAT ACTUALLY BLOCKS AUTO-RESOLVE, IN ORDER
-------------------------------------------
1. `adverse_action`          — a denial, or an entitlement check that came back
                               false. Unconditional; outranks everything.
2. `agent_requested_human`   — the model submitted `needs_human`.
3. `no_entitlement_evidence` — a `solve` granting a PLAN-GATED feature with no
                               `check_entitlement` receipt behind it (#69).
4. `low_confidence`          — retrieval similarity below SIM_THRESHOLD.

WHY THE CLASSIFICATION MARGIN IS NO LONGER IN THAT LIST (#74)
-------------------------------------------------------------
It used to be half of layer 4. It was measured against held-out human labels
and could not be shown to carry reply-quality information:

    ability to rank human-PASS replies above human-FAIL ones (AUC)
      round 1:  0.334   95% CI [0.17, 0.52]
      round 2:  0.442   95% CI [0.26, 0.63]

Both intervals span 0.50, and the #67 repair — which widened the signal's
usable range ~26x — moved those numbers by +0.003 and 0.000. Repairing the
instrument made it decisive without making it informative, because it answers
the wrong question: the margin asks "did the router agree with itself about
which queue this belongs in?", while this gate decides "may this reply be sent
unseen?" Those are different quantities.

A layer that BLOCKS work bears the burden of proof, and this one could not meet
it — so it rejects good and bad replies at the same rate, which is throughput
loss with no demonstrated safety gain.

Stated honestly: this acts on a NULL RESULT. At ~39 labels with 11-13 failures
the sample cannot establish separation in either direction, so "cannot be shown
to help" is not the same as "proven useless". The margin is therefore demoted,
not deleted — still computed, still recorded in `gate_signals`, still visible in
every trace. Full measurement and both sides of the argument:
docs/week-4-launch/reports/margin-separation-measurement.md

SIM_THRESHOLD is deliberately UNCHANGED at its derived value. Re-tuning a
threshold in the same change that alters what it gates is how a tuning decision
gets laundered into a principled one."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from triagedesk.pipeline.act import ActOutcome
from triagedesk.tools import PLAN_ENTITLEMENTS

# Features Basic does NOT include — the only ones a plan can actually withhold,
# and therefore the only ones a "sure, I've enabled that" reply could be a soft
# denial about. Derived from PLAN_ENTITLEMENTS so it cannot drift out of sync
# with the tool the agent actually calls.
GATED_FEATURES = (
    set().union(*PLAN_ENTITLEMENTS.values()) - PLAN_ENTITLEMENTS["basic"]
)

# How a human writes about each gated feature. The feature name itself (with
# underscores as spaces) is always matched too, so this only carries the
# phrasings that differ. Deliberately conservative: a missed phrasing costs an
# escalation that could have auto-resolved, which is the safe direction.
_FEATURE_PHRASES: dict[str, tuple[str, ...]] = {
    "priority_vpn_support": ("priority vpn", "priority support", "same-day triage",
                             "same day triage", "expedite", "escalate my vpn"),
    "api_access": ("api access", "api key", "api keys", "developer key",
                   "developer api"),
    "data_export": ("data export", "export my data", "export our data",
                    "export their data", "self-service export", "account backup"),
    "dedicated_ip": ("dedicated ip", "static ip", "fixed ip", "reserved ip",
                     "allowlist our ip", "allowlist it"),
    "custom_integrations": ("custom integration", "custom integrations",
                            "third-party integration", "integrate northbeam"),
}


def gated_feature_implicated(*texts: str) -> str | None:
    """Name the plan-gated feature this ticket/reply is about, or None.

    Scans the REPLY as well as the ticket on purpose: the risk this guards is
    the model promising a gated feature the plan excludes, and a vaguely-worded
    ticket with a generous reply is exactly the shape that would slip past a
    ticket-only scan.

    Deterministic string matching, not an LLM judgement — the gate never
    consults the model about its own trustworthiness (spec rule).
    """
    blob = " ".join(t for t in texts if t).lower()
    for feature in sorted(GATED_FEATURES):
        if feature.replace("_", " ") in blob:
            return feature
        if any(phrase in blob for phrase in _FEATURE_PHRASES.get(feature, ())):
            return feature
    return None

# Derived from the held-out calibration pool, never the golden set —
# see docs/week-2-evals/reports/threshold-derivation.md (Refs #45).
SIM_THRESHOLD = 0.45     # ~36th percentile of held-out retrieval similarity

_CENTROIDS_PATH = Path(__file__).parent.parent / "data" / "queue_centroids.json"


@lru_cache(maxsize=1)
def _load_centroid_file() -> dict:
    return json.loads(_CENTROIDS_PATH.read_text())


def load_centroids() -> dict[str, list[float]]:
    data = _load_centroid_file()
    # v2 wraps the centroids alongside the global mean; v1 was a bare mapping.
    return data["centroids"] if "centroids" in data else data


def load_global_mean() -> list[float] | None:
    """The shared direction every centroid points in. None for v1 files, which
    disables centring and reproduces the original (measured-as-noise) margin."""
    return _load_centroid_file().get("global_mean")


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb)


def _centre(v: list[float], mean: list[float]) -> list[float]:
    return [x - m for x, m in zip(v, mean, strict=True)]


def classification_margin(query_embedding, predicted_queue, centroids,
                          global_mean: list[float] | None = None) -> float:
    """How much more this ticket looks like its predicted queue than the next
    best queue. Positive = the embedding evidence AGREES with the LLM's choice.

    Mean-centring (issue #67). Support-ticket embeddings are strongly
    anisotropic: measured over the ten committed centroids, mean pairwise
    cosine is 0.9782 and the closest pair (Technical Support / IT Support) is
    0.9963. Every centroid sits 0.97-0.997 from their common mean. Raw cosines
    therefore differ only in the third decimal, and a DIFFERENCE of two such
    numbers is noise — which is exactly what the held-out calibration found
    when it reported the signal "directionally inverted" (human-fail replies
    scoring higher than human-pass).

    Subtracting the shared component removes "this is a support ticket" and
    leaves what actually distinguishes the queues. Measured effect on 50
    tickets: the margin's usable range widens ~8.7x. It does NOT make routing
    more accurate (28% -> 34%, n=50, not significant) — the ceiling there is
    the label set, not the classifier. It makes the signal capable of carrying
    a decision at all.

    NOTE (#74): this value no longer gates anything. Measured against held-out
    human labels it could not be shown to separate good replies from bad, so it
    was demoted to observability — still computed, still recorded in the trace,
    but no longer able to veto a reply. See the module docstring.
    """
    if global_mean is not None:
        query_embedding = _centre(query_embedding, global_mean)
        centroids = {q: _centre(c, global_mean) for q, c in centroids.items()}
    sims = {q: _cosine(query_embedding, c) for q, c in centroids.items()}
    own = sims.pop(predicted_queue)
    return own - max(sims.values())


@dataclass
class GateDecision:
    auto_resolve: bool
    reason: str | None
    signals: dict


def decide(*, retrieval_similarity: float, margin: float, outcome: ActOutcome,
           entitlement_checked: bool, gated_feature: str | None) -> GateDecision:
    signals = {
        "retrieval_similarity": retrieval_similarity,
        "classification_margin": margin,
        "entitlement_checked": entitlement_checked,
        "gated_feature": gated_feature,
    }

    # Adverse-action rule first: never auto-deliver a denial, however confident.
    if outcome.resolution.resolution_type == "deny" or outcome.entitlement_denied:
        return GateDecision(False, "adverse_action", signals)
    if outcome.resolution.resolution_type == "needs_human":
        return GateDecision(False, "agent_requested_human", signals)
    # A solve that grants a PLAN-GATED feature without positive entitlement
    # evidence is a soft denial the model never flagged — escalate rather than
    # trust it. Scoped to gated features (issue #69): the rule used to demand a
    # receipt behind every solve, which escalated tickets where no entitlement
    # existed to check. Live evidence — demo ticket 80011 ("locked out after too
    # many password attempts") retrieved its KB article at 0.7175, got a correct
    # unlock reply, and was escalated for failing to check an entitlement that
    # does not exist for password unlock. Basic-inclusive features are excluded
    # by construction: a plan cannot withhold what it already includes.
    if (outcome.resolution.resolution_type == "solve"
            and gated_feature is not None
            and not entitlement_checked):
        return GateDecision(False, "no_entitlement_evidence", signals)
    # Similarity only. The margin was demoted to observability in #74 — see the
    # module docstring. It is still computed and still in `signals` above, so
    # the trace shows it; it just no longer vetoes a reply that cleared every
    # layer that can be justified.
    if retrieval_similarity < SIM_THRESHOLD:
        return GateDecision(False, "low_confidence", signals)
    return GateDecision(True, None, signals)
