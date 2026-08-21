"""Guard against SDK drift breaking the pipeline (issue #71).

Every other test in this suite mocks the Anthropic client, so none of them can
see a change in the real SDK's signature. That gap has now cost this project
twice: once when a planned `structured_call` didn't exist on the real SDK
despite green mocked tests, and again when `anthropic` 1.0.0 removed
`temperature` from `Messages.create()` and a fresh deploy install crashed every
run with `TypeError: got an unexpected keyword argument 'temperature'` —
inside `precheck`, before anything could be traced.

These tests introspect the INSTALLED SDK rather than a mock. They make no
network calls and cost nothing, but they fail loudly at CI time if a dependency
bump removes a parameter the pipeline actually passes.
"""

import inspect

import anthropic
import pytest


def _create_params() -> set[str]:
    sig = inspect.signature(anthropic.resources.messages.Messages.create)
    return set(sig.parameters)


# Every kwarg triagedesk actually passes to Messages.create, and where from.
REQUIRED_PARAMS = {
    "model": "every call",
    "max_tokens": "every call",
    "messages": "every call",
    "system": "llm.py (with cache_control for prompt caching)",
    "temperature": "precheck.py, classify.py, judge.py — pinned to 0 for determinism",
    "tools": "act.py",
    "thinking": "act.py (adaptive)",
    "output_config": "act.py (effort)",
}


@pytest.mark.parametrize("param", sorted(REQUIRED_PARAMS))
def test_installed_sdk_accepts_every_parameter_the_pipeline_passes(param):
    params = _create_params()
    if "kwargs" in params:
        pytest.skip("SDK signature is **kwargs-based; introspection can't verify")
    assert param in params, (
        f"the installed anthropic SDK ({anthropic.__version__}) no longer accepts "
        f"{param!r} on Messages.create(), which triagedesk passes from "
        f"{REQUIRED_PARAMS[param]}. Pin the SDK or migrate the call sites — do not "
        f"discover this on a production deploy."
    )


def test_sdk_major_version_is_pinned_below_the_breaking_release():
    """requirements.txt pins <1.0. anthropic 1.0.0 removed `temperature` from
    Messages.create() — an unpinned install on a fresh deploy picks it up and
    every pipeline run fails at precheck."""
    major = int(anthropic.__version__.split(".")[0])
    assert major == 0, (
        f"anthropic {anthropic.__version__} is installed but requirements.txt pins "
        "<1.0. Either the pin was widened without migrating the temperature call "
        "sites, or this environment is stale."
    )
