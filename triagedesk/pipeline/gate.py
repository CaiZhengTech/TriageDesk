"""Multi-signal confidence gate. Signals are EXTERNAL gauges only:
retrieval similarity + embedding-centroid classification margin. The LLM's
self-reported confidence is never consulted (spec rule). Adverse actions
(deny / entitlement denial) escalate unconditionally."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from triagedesk.pipeline.act import ActOutcome

SIM_THRESHOLD = 0.45     # Week-1 placeholders — Week 2's calibration table
MARGIN_THRESHOLD = 0.02  # decides whether these survive.

_CENTROIDS_PATH = Path(__file__).parent.parent / "data" / "queue_centroids.json"


@lru_cache(maxsize=1)
def load_centroids() -> dict[str, list[float]]:
    return json.loads(_CENTROIDS_PATH.read_text())


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb)


def classification_margin(query_embedding, predicted_queue, centroids) -> float:
    sims = {q: _cosine(query_embedding, c) for q, c in centroids.items()}
    own = sims.pop(predicted_queue)
    return own - max(sims.values())


@dataclass
class GateDecision:
    auto_resolve: bool
    reason: str | None
    signals: dict


def decide(*, retrieval_similarity: float, margin: float, outcome: ActOutcome) -> GateDecision:
    signals = {"retrieval_similarity": retrieval_similarity, "classification_margin": margin}

    # Adverse-action rule first: never auto-deliver a denial, however confident.
    if outcome.resolution.resolution_type == "deny" or outcome.entitlement_denied:
        return GateDecision(False, "adverse_action", signals)
    if outcome.resolution.resolution_type == "needs_human":
        return GateDecision(False, "agent_requested_human", signals)
    if retrieval_similarity < SIM_THRESHOLD or margin < MARGIN_THRESHOLD:
        return GateDecision(False, "low_confidence", signals)
    return GateDecision(True, None, signals)
