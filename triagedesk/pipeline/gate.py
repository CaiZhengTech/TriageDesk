"""Multi-signal confidence gate. Signals are EXTERNAL gauges only:
retrieval similarity + embedding-centroid classification margin. The LLM's
self-reported confidence is never consulted (spec rule). Adverse actions
(deny / entitlement denial) escalate unconditionally."""

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
MARGIN_THRESHOLD = 0.0   # embedding evidence must AGREE with the LLM's queue choice

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

    The threshold does not move: 0.0 is a semantic boundary (agree / disagree),
    not a tuned value, and it means the same thing before and after.
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
    if retrieval_similarity < SIM_THRESHOLD or margin < MARGIN_THRESHOLD:
        return GateDecision(False, "low_confidence", signals)
    return GateDecision(True, None, signals)
