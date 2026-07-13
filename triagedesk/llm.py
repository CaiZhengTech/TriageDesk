"""Shared Anthropic client. One place for retries, model pinning, and the
structured-output + single-repair-re-prompt policy.

Sonnet 4.6 notes: effort defaults to "high" (the chosen level) so structured
calls don't pass it; thinking is off when the parameter is omitted (only the
act loop enables it); structured outputs via messages.create() with
output_config.format (constrained decoding) and our own Pydantic validation
of the returned text — not messages.parse(), which validates eagerly inside
the SDK call and would make our repair path unreachable.
The SDK itself retries 408/429/5xx/connection errors with exponential
backoff (max_retries=3); after that, anthropic.APIError propagates and the
runner marks the run `failed`.
"""

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

from triagedesk.config import settings

PIPELINE_MODEL = "claude-sonnet-4-6"

client = Anthropic(
    api_key=settings.anthropic_api_key or None,
    max_retries=3,
    timeout=60.0,
)


def _strict_schema(node):
    """The API requires every 'object' in an output_config schema to set
    additionalProperties: false explicitly; Pydantic's model_json_schema()
    omits it (found live in the Week-1 E2E checkpoint)."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            node.setdefault("additionalProperties", False)
        for value in node.values():
            _strict_schema(value)
    elif isinstance(node, list):
        for item in node:
            _strict_schema(item)
    return node


class StructuredCallError(Exception):
    """Base for structured_call failures. Carries every raw API response so
    the caller can still record usage/cost for failed attempts."""

    def __init__(self, message: str, responses: list | None = None):
        super().__init__(message)
        self.responses = responses or []


class RepairFailedError(StructuredCallError):
    """Structured output failed validation twice (initial + one repair)."""


class LLMRefusalError(StructuredCallError):
    """Model returned stop_reason == 'refusal'."""


def structured_call(
    *,
    system: str,
    user: str,
    schema: type[BaseModel],
    max_tokens: int = 1024,
    temperature: float | None = None,
    _client: Anthropic | None = None,
) -> tuple[BaseModel, list]:
    """Call the model expecting `schema`; ONE repair re-prompt on failure.

    Uses output_config.format (constrained decoding) and validates the text
    ourselves with Pydantic, so validation failures are OUR control flow,
    not an exception inside the SDK. Returns (parsed, responses) — responses
    holds every raw API response so the caller can record usage/cost for
    each attempt, including failed ones. `temperature` is passed through to
    the API only when explicitly set (omitted => API default) so pipeline
    call sites that never set it stay byte-for-byte unchanged; the judge
    (Task 5) is the first caller to pin temperature=0.
    """
    c = _client or client
    responses: list = []
    messages: list = [{"role": "user", "content": user}]
    extra = {} if temperature is None else {"temperature": temperature}

    for attempt in range(2):  # initial + exactly one repair
        response = c.messages.create(
            model=PIPELINE_MODEL,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system,
                     "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": _strict_schema(schema.model_json_schema()),
                }
            },
            **extra,
        )
        responses.append(response)
        if response.stop_reason == "refusal":
            raise LLMRefusalError("model refused the request", responses)
        text = "".join(b.text for b in response.content if b.type == "text")
        try:
            return schema.model_validate_json(text), responses
        except ValidationError as exc:
            if attempt == 0:
                messages = messages + [
                    {"role": "assistant", "content": response.content},
                    {
                        "role": "user",
                        "content": (
                            f"Your previous answer did not validate against the required "
                            f"schema ({schema.__name__}). Validation errors:\n{exc}\n"
                            "Answer again, strictly matching the schema."
                        ),
                    },
                ]

    raise RepairFailedError(
        f"structured output failed validation twice for {schema.__name__}", responses
    )
