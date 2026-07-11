"""Shared Anthropic client. One place for retries, model pinning, and the
structured-output + single-repair-re-prompt policy.

Sonnet 4.6 notes: effort defaults to "high" (the chosen level) so structured
calls don't pass it; thinking is off when the parameter is omitted (only the
act loop enables it); structured outputs via messages.parse().
The SDK itself retries 408/429/5xx/connection errors with exponential
backoff (max_retries=3); after that, anthropic.APIError propagates and the
runner marks the run `failed`.
"""

from anthropic import Anthropic
from pydantic import BaseModel

from triagedesk.config import settings

PIPELINE_MODEL = "claude-sonnet-4-6"

client = Anthropic(
    api_key=settings.anthropic_api_key or None,
    max_retries=3,
    timeout=60.0,
)


class RepairFailedError(Exception):
    """Structured output failed validation twice (initial + one repair)."""


class LLMRefusalError(Exception):
    """Model returned stop_reason == 'refusal'."""


def structured_call(
    *,
    system: str,
    user: str,
    schema: type[BaseModel],
    max_tokens: int = 1024,
    _client: Anthropic | None = None,
) -> tuple[BaseModel, list]:
    """Call the model expecting `schema`; ONE repair re-prompt on failure.

    Returns (parsed, responses) — responses holds every raw API response so
    the caller can record usage/cost for each (including failed attempts).
    """
    c = _client or client
    responses = []
    messages = [{"role": "user", "content": user}]

    for attempt in range(2):  # initial + exactly one repair
        response = c.messages.parse(
            model=PIPELINE_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            output_format=schema,
        )
        responses.append(response)
        if response.stop_reason == "refusal":
            raise LLMRefusalError("model refused the request")
        if response.parsed_output is not None:
            return response.parsed_output, responses
        if attempt == 0:
            messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "Your previous answer did not validate against the required "
                        f"schema ({schema.__name__}). Answer again, strictly matching "
                        "the schema."
                    ),
                }
            ]
    raise RepairFailedError(f"output failed {schema.__name__} validation after one repair")
