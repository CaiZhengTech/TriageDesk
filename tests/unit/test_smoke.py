"""Unit tests for scripts/smoke.py (the Task-6 post-deploy smoke check),
using httpx.MockTransport as the monkeypatched HTTP layer — no real network,
no live pipeline calls.
"""

import httpx

from scripts.smoke import run_smoke


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0)


def test_smoke_exits_0_when_run_completes_with_positive_cost(capsys):
    run_id = "11111111-1111-1111-1111-111111111111"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/demo/run":
            return httpx.Response(202, json={"run_id": run_id})
        if request.method == "GET" and request.url.path == f"/api/runs/{run_id}":
            return httpx.Response(
                200, json={"state": "completed", "total_cost_usd": 0.031}
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    code = run_smoke("http://example.test", 42, client=_client(handler))

    assert code == 0
    out = capsys.readouterr().out
    assert run_id in out
    assert "completed" in out


def test_smoke_exits_0_for_escalated_terminal_state_with_cost():
    run_id = "22222222-2222-2222-2222-222222222222"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"run_id": run_id})
        return httpx.Response(200, json={"state": "escalated", "total_cost_usd": 0.02})

    assert run_smoke("http://example.test", 42, client=_client(handler)) == 0


def test_smoke_exits_1_when_cost_is_zero(capsys):
    run_id = "33333333-3333-3333-3333-333333333333"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"run_id": run_id})
        return httpx.Response(200, json={"state": "completed", "total_cost_usd": 0.0})

    code = run_smoke("http://example.test", 42, client=_client(handler))

    assert code == 1
    err = capsys.readouterr().err
    assert "cost" in err.lower()


def test_smoke_exits_1_when_run_failed(capsys):
    run_id = "44444444-4444-4444-4444-444444444444"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"run_id": run_id})
        return httpx.Response(200, json={"state": "failed", "total_cost_usd": 0.01})

    code = run_smoke("http://example.test", 42, client=_client(handler))

    assert code == 1
    assert "failed" in capsys.readouterr().err.lower()


def test_smoke_exits_1_when_post_is_not_202(capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"paused": True, "reason": "daily_budget_reached"})

    code = run_smoke("http://example.test", 42, client=_client(handler))

    assert code == 1
    assert "402" in capsys.readouterr().err


def test_smoke_exits_1_when_run_stays_running(capsys):
    run_id = "55555555-5555-5555-5555-555555555555"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"run_id": run_id})
        return httpx.Response(200, json={"state": "running", "total_cost_usd": 0.0})

    code = run_smoke(
        "http://example.test", 42, client=_client(handler),
        max_polls=2, poll_interval_s=0,
    )

    assert code == 1
    assert "timed out" in capsys.readouterr().err.lower()
