"""Embedding calls must retry rate limits like the Anthropic path does (#81).

FOUND IN PRODUCTION, BY REAL TRAFFIC.
The first batch of tickets to arrive through the intake endpoint produced 4
failed runs out of 12. All four died at `retrieve` with Voyage's free-tier
message: "reduced rate limits of 3 RPM and 10K TPM."

The project's stated policy is "retries: 429/5xx, backoff, max 3" and it WAS
implemented -- for Anthropic only, via `Anthropic(max_retries=3)` in llm.py.
The Voyage client was constructed bare, so the embedding call had no retry at
all. One provider hardened, one forgotten, and nothing caught it because a
click-to-run demo never produces two concurrent runs.

Two defects, both tested here:
  1. no retry on a retryable error
  2. the resulting failure was labelled `unexpected:RateLimitError` -- but a
     provider rate limit is the most expected failure mode there is, and
     calling it "unexpected" sends whoever reads the trace looking for a bug
     that isn't there.
"""

import pytest
import voyageai.error as voyage_error

import triagedesk.embeddings as emb


class _FlakyClient:
    """Raises RateLimitError for the first `fail_times` calls, then succeeds."""

    def __init__(self, fail_times):
        self.fail_times = fail_times
        self.calls = 0

    def embed(self, texts, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise voyage_error.RateLimitError("3 RPM")
        return type("R", (), {"embeddings": [[0.1] * 4 for _ in texts]})()


@pytest.fixture()
def no_sleep(monkeypatch):
    """Backoff is real in production and pointless in tests."""
    slept = []
    monkeypatch.setattr(emb.time, "sleep", lambda s: slept.append(s))
    return slept


def test_retries_a_rate_limit_and_succeeds(monkeypatch, no_sleep):
    flaky = _FlakyClient(fail_times=2)
    monkeypatch.setattr(emb, "_vo", lambda: flaky)

    result = emb.embed_query("my vpn keeps dropping")

    assert len(result) == 4
    assert flaky.calls == 3, "should have retried twice before succeeding"


def test_backoff_grows_between_attempts(monkeypatch, no_sleep):
    """Voyage's free tier is 3 requests/minute, so a flat 1s retry would just
    burn all attempts inside the same window. Delays must increase."""
    flaky = _FlakyClient(fail_times=2)   # one instance: the lambda must not
    monkeypatch.setattr(emb, "_vo", lambda: flaky)  # rebuild it per call
    emb.embed_query("x")
    assert no_sleep == sorted(no_sleep) and len(set(no_sleep)) > 1, no_sleep


def test_gives_up_after_max_retries_and_reraises(monkeypatch, no_sleep):
    """Bounded, matching Anthropic's max_retries=3. A run that cannot embed
    must fail visibly rather than retry forever inside a request."""
    flaky = _FlakyClient(fail_times=99)
    monkeypatch.setattr(emb, "_vo", lambda: flaky)

    with pytest.raises(voyage_error.RateLimitError):
        emb.embed_query("x")

    assert flaky.calls == emb.MAX_EMBED_RETRIES + 1


def test_non_retryable_errors_are_not_retried(monkeypatch, no_sleep):
    """An auth failure will fail identically every time; retrying it wastes a
    minute of backoff to reach the same answer."""
    class _Broken:
        def __init__(self):
            self.calls = 0

        def embed(self, texts, **kwargs):
            self.calls += 1
            raise voyage_error.AuthenticationError("bad key")

    broken = _Broken()
    monkeypatch.setattr(emb, "_vo", lambda: broken)

    with pytest.raises(voyage_error.AuthenticationError):
        emb.embed_query("x")
    assert broken.calls == 1
    assert no_sleep == []


def test_embed_documents_is_protected_too(monkeypatch, no_sleep):
    """Same guard on the batch path -- compute_centroids and embed_kb run
    hundreds of these against the same 3 RPM ceiling."""
    flaky = _FlakyClient(fail_times=1)
    monkeypatch.setattr(emb, "_vo", lambda: flaky)

    out = emb.embed_documents(["a", "b"])

    assert len(out) == 2
    assert flaky.calls == 2
