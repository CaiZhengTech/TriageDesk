"""Voyage AI embeddings. One embedding per ticket, reused by retrieve + gate."""

import voyageai

from triagedesk.config import settings
from triagedesk.models import EMBED_DIMS

EMBED_MODEL = "voyage-3.5-lite"

_client: voyageai.Client | None = None


def _vo() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client(api_key=settings.voyage_api_key or None)
    return _client


def embed_batch(texts: list[str], input_type: str) -> list[list[float]]:
    """Voyage places `query` and `document` embeddings in deliberately
    asymmetric regions — right for retrieval (a question near its answer),
    wrong for comparing a ticket to a prototype OF tickets. Callers that
    classify must therefore embed both sides with the SAME input_type; see
    issue #67 for the mismatch this parameter exists to prevent recurring."""
    return _vo().embed(
        texts, model=EMBED_MODEL, input_type=input_type, output_dimension=EMBED_DIMS
    ).embeddings


def embed_documents(texts: list[str]) -> list[list[float]]:
    return embed_batch(texts, "document")


def embed_query(text: str) -> list[float]:
    return _vo().embed(
        [text], model=EMBED_MODEL, input_type="query", output_dimension=EMBED_DIMS
    ).embeddings[0]
