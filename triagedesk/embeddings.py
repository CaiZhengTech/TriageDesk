"""Voyage AI embeddings. One embedding per ticket, reused by retrieve + gate.

RETRY POLICY (#81) — added after real traffic broke it
------------------------------------------------------
The project's stated policy is "retries: 429/5xx, backoff, max 3". That was
implemented for Anthropic (`Anthropic(max_retries=3)` in llm.py) and NOT for
Voyage, whose client was constructed bare. The asymmetry survived because a
click-to-run demo never issues two concurrent requests.

The first batch of tickets to arrive through the intake endpoint issued 12,
and 4 of them died at `retrieve` with Voyage's free-tier ceiling: 3 requests
per minute. Those runs were lost after already paying for pre-check and
classify — the two stages that run before retrieval.

So the retry lives here rather than in the caller: every embedding path
(`retrieve`, `embed_kb`, `compute_centroids`, the measurement scripts) needs
the same protection, and only one of them is on the request path.

Backoff is deliberately slow. At 3 RPM a flat 1-second retry would burn every
attempt inside the same rate-limit window and fail anyway; the delays below
carry the last attempt past a minute.
"""

import time

import voyageai
import voyageai.error as voyage_error

from triagedesk.config import settings
from triagedesk.models import EMBED_DIMS

EMBED_MODEL = "voyage-3.5-lite"

# Matches Anthropic's max_retries=3 in llm.py — one policy, both providers.
MAX_EMBED_RETRIES = 3
# Seconds before attempts 2, 3 and 4. Tuned against the free tier's 3 RPM: the
# cumulative wait crosses 60s so a retry lands in a fresh window rather than
# re-hitting the exhausted one.
_BACKOFF_SECONDS = (5.0, 20.0, 45.0)

# Errors worth retrying: transient, and likely to succeed unchanged on a later
# attempt. An auth or invalid-request failure will fail identically every time,
# so retrying it only spends a minute of backoff to reach the same answer.
_RETRYABLE = (
    voyage_error.RateLimitError,
    voyage_error.ServiceUnavailableError,
    voyage_error.Timeout,
    voyage_error.APIConnectionError,
)

_client: voyageai.Client | None = None


def _vo() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client(api_key=settings.voyage_api_key or None)
    return _client


def _embed_with_retry(texts: list[str], input_type: str) -> list[list[float]]:
    last: Exception | None = None
    for attempt in range(MAX_EMBED_RETRIES + 1):
        try:
            return _vo().embed(
                texts, model=EMBED_MODEL, input_type=input_type,
                output_dimension=EMBED_DIMS,
            ).embeddings
        except _RETRYABLE as exc:
            last = exc
            if attempt == MAX_EMBED_RETRIES:
                break
            time.sleep(_BACKOFF_SECONDS[attempt])
    raise last  # exhausted: let the runner record a failed run, visibly


def embed_batch(texts: list[str], input_type: str) -> list[list[float]]:
    """Voyage places `query` and `document` embeddings in deliberately
    asymmetric regions — right for retrieval (a question near its answer),
    wrong for comparing a ticket to a prototype OF tickets. Callers that
    classify must therefore embed both sides with the SAME input_type; see
    issue #67 for the mismatch this parameter exists to prevent recurring."""
    return _embed_with_retry(texts, input_type)


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _embed_with_retry(texts, "document")


def embed_query(text: str) -> list[float]:
    return _embed_with_retry([text], "query")[0]
