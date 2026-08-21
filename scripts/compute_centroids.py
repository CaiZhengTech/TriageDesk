"""Per-queue centroid embeddings from labeled Kaggle tickets (up to 100/queue).

The gate's classification margin = sim(ticket, predicted queue centroid) minus
the best sim to any OTHER centroid — an external signal, not LLM self-report.
Output is committed (triagedesk/data/queue_centroids.json) so runs and tests
are deterministic and CI never calls Voyage.

TWO CORRECTIONS FROM ISSUE #67
------------------------------
1. `input_type` now matches the runtime. `triagedesk/pipeline/retrieve.py`
   embeds the ticket with `embed_query(...)` -> input_type="query", and that
   same vector is what the margin is computed against. Building the centroids
   as "document" put the two sides of the comparison in deliberately
   asymmetric regions of the space — correct for the KB retrieval that vector
   also performs, wrong for comparing a ticket to a prototype OF tickets.

2. The global mean is computed and stored alongside the centroids. Support
   tickets are strongly anisotropic: the previous (v1) centroids had mean
   pairwise cosine 0.9782, with Technical Support / IT Support at 0.9963.
   Every centroid sat 0.97-0.997 from their common mean, so raw cosines
   differed only in the third decimal and the margin — a difference of two
   such numbers — was noise. `classification_margin` subtracts this mean from
   both sides before comparing.

OUTPUT FORMAT (v2)
------------------
    {"version": 2, "input_type": "query",
     "centroids": {queue: [...]}, "global_mean": [...]}

v1 was a bare {queue: [...]} mapping; `gate.load_centroids` still reads it and
`load_global_mean` returns None for it, which disables centring — so an old
file degrades to the old behaviour instead of crashing.
"""

import json
import time
from pathlib import Path

from triagedesk.db import SessionLocal
from triagedesk.embeddings import embed_batch
from triagedesk.models import Ticket
from triagedesk.schemas import QUEUES

PER_QUEUE = 100
OUT = Path("triagedesk/data/queue_centroids.json")
# Must match what retrieve.py sends at runtime. Changing one without the other
# reintroduces the #67 mismatch.
INPUT_TYPE = "query"
# Voyage free tier (no payment method on file) caps at 3 RPM / 10K TPM. A
# batch of 100 real ticket texts (~10K tokens) trips the TPM cap on its own,
# so batches are kept well under that, paced to stay under the RPM cap too.
SUB_BATCH = 25
REQUEST_PAUSE_SECONDS = 21


def normalize(v: list[float]) -> list[float]:
    norm = sum(x * x for x in v) ** 0.5
    return [x / norm for x in v]


def _load_progress() -> dict[str, list[float]]:
    """Resume support: free-tier pacing makes a full run ~15 min, so each
    finished queue is written immediately and skipped on re-run. Only a v2 file
    can be resumed — a v1 file was built with the wrong input_type, so mixing
    its centroids with new ones would be worse than starting over."""
    if not OUT.exists():
        return {}
    data = json.loads(OUT.read_text())
    if data.get("version") != 2 or data.get("input_type") != INPUT_TYPE:
        print(f"{OUT} is not a v2/{INPUT_TYPE} file — recomputing all queues")
        return {}
    return data["centroids"]


def _write(centroids: dict[str, list[float]]) -> None:
    payload = {"version": 2, "input_type": INPUT_TYPE, "centroids": centroids}
    if len(centroids) == len(QUEUES):
        dims = len(next(iter(centroids.values())))
        payload["global_mean"] = [
            sum(c[d] for c in centroids.values()) / len(centroids) for d in range(dims)
        ]
    OUT.write_text(json.dumps(payload))


def main() -> None:
    session = SessionLocal()
    centroids = _load_progress()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for queue in QUEUES:
        if queue in centroids:
            print(f"{queue}: already computed, skipping", flush=True)
            continue
        tickets = (
            session.query(Ticket)
            .filter_by(queue=queue, language="en", source="kaggle")
            .limit(PER_QUEUE)
            .all()
        )
        texts = [f"{t.subject}\n{t.body}" for t in tickets]
        vectors = []
        for i in range(0, len(texts), SUB_BATCH):
            vectors += embed_batch(texts[i:i + SUB_BATCH], INPUT_TYPE)
            time.sleep(REQUEST_PAUSE_SECONDS)  # respect free-tier 3 RPM / 10K TPM
        dims = len(vectors[0])
        mean = [sum(v[d] for v in vectors) / len(vectors) for d in range(dims)]
        centroids[queue] = normalize(mean)
        _write(centroids)
        print(f"{queue}: {len(vectors)} tickets", flush=True)
    session.close()
    print(f"Wrote {OUT} ({len(centroids)}/{len(QUEUES)} queues, "
          f"input_type={INPUT_TYPE}, global_mean included)")


if __name__ == "__main__":
    main()
