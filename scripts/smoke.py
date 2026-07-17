"""Post-deploy smoke check (Task 6, issue #15/#16): drives one real demo run
through a deployed API and confirms it actually cost money and reached a
terminal state — the cheapest possible proof the deployed pipeline works.

  python -m scripts.smoke --base-url https://triagedesk.up.railway.app --ticket-id 90001

POSTs /api/demo/run, polls GET /api/runs/{id} until a terminal state, and
exits 0 iff state in {completed, escalated} AND total_cost_usd > 0 (state
"failed" or a zero/missing cost is a failure), else 1 with the reason on
stderr. Always prints run id + state + cost. Uses httpx (already a project
dependency) — nothing new added.

Under the Task-7 sync-202 decision, run_ticket executes synchronously inside
the POST, so the first poll already sees a terminal state in practice; the
poll loop still exists so this script keeps working if the endpoint is ever
made async.
"""

import argparse
import sys
import time

import httpx

TERMINAL_STATES = {"completed", "escalated", "failed"}
SUCCESS_STATES = {"completed", "escalated"}
DEFAULT_MAX_POLLS = 10
DEFAULT_POLL_INTERVAL_S = 3.0


def run_smoke(
    base_url: str,
    ticket_id: int,
    client: httpx.Client,
    max_polls: int = DEFAULT_MAX_POLLS,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
) -> int:
    resp = client.post(f"{base_url}/api/demo/run", json={"ticket_id": ticket_id})
    if resp.status_code != 202:
        print(
            f"POST /api/demo/run returned {resp.status_code}: {resp.text}",
            file=sys.stderr,
        )
        return 1
    run_id = resp.json()["run_id"]

    state = None
    cost = None
    for i in range(max_polls):
        poll = client.get(f"{base_url}/api/runs/{run_id}")
        poll.raise_for_status()
        body = poll.json()
        state = body.get("state")
        cost = body.get("total_cost_usd")
        if state in TERMINAL_STATES:
            break
        if i < max_polls - 1:
            time.sleep(poll_interval_s)

    print(f"run_id={run_id} state={state} cost={cost}")

    if state not in TERMINAL_STATES:
        print(
            f"smoke check failed: timed out waiting for terminal state "
            f"(last state={state})",
            file=sys.stderr,
        )
        return 1
    if state not in SUCCESS_STATES:
        print(f"smoke check failed: run ended in state={state}", file=sys.stderr)
        return 1
    if not cost or cost <= 0:
        print(f"smoke check failed: total_cost_usd={cost} is not > 0", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="deployed API base URL")
    parser.add_argument("--ticket-id", required=True, type=int, help="a seeded demo-pool ticket id")
    args = parser.parse_args()

    with httpx.Client(timeout=60.0) as client:
        sys.exit(run_smoke(args.base_url, args.ticket_id, client))


if __name__ == "__main__":
    main()
