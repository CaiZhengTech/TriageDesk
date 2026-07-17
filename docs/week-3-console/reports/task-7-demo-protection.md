# Task 7: Demo abuse protection (issue #16)

## What was implemented

The last code task before the live deploy — the guards that let strangers try the
demo without burning money. Three independent "before spending" checks gate
`POST /api/demo/run`, plus a post-deploy smoke script.

- **`triagedesk/demo.py` (new):**
  - `list_demo_pool(db)` / `get_demo_ticket(db, ticket_id)` — the pool-only rule:
    only `tickets.source == 'demo'` rows count, whether listing the pool or
    validating a run request. A real (Kaggle) ticket id or an unknown id both fail
    `get_demo_ticket` the same way.
  - `RateLimiter` — in-memory fixed-window (1 hour) limiter keyed by whatever string
    the caller passes (the route passes `request.client.host`). `check(key, now,
    limit)` takes `now` as a parameter — never reads the clock internally — so
    tests drive window resets with a fake `datetime` instead of sleeping. Docstring
    documents the single-instance limitation (a multi-replica deploy would let each
    instance track its own window, effectively multiplying the limit) and the real
    fix (a shared store, same interface). Also carries a `reset()` test-only escape
    hatch (see "route-test isolation" below).
  - `daily_cap_would_be_exceeded(db, now, daily_cap_usd, per_run_cost_cap_usd)` —
    the pre-check daily-spend query. Builds a `[day_start, day_end)` window as
    **naive** datetimes (`_utc_day_window`) because `runs.created_at` is stored
    naive-but-UTC-by-convention (DATA-SCHEMA.md's documented gotcha); normalizing
    `now` to naive UTC first, rather than trying to make the column aware, avoids
    reintroducing the same tz mismatch `console_queries.py` already had to guard
    against for `latency_ms`. Sums `runs.total_cost_usd` for that window and
    compares `spent + per_run_cost_cap_usd > daily_cap_usd`. Wrapped in
    `try/except Exception: return True` — fail closed, matching the project's
    existing cost-cap philosophy (`docs/00-spec` non-negotiable rule: uncomputable
    cost = breach).
- **`triagedesk/config.py`:** `demo_daily_cap_usd: float = 1.00`,
  `demo_rate_limit_per_hour: int = 5`, both documented in `.env.example`.
- **`triagedesk/app.py`:**
  - `GET /api/demo/pool` → `list_demo_pool`, verbatim shape.
  - `POST /api/demo/run` (`DemoRunIn{ticket_id}`) — the four branches, in this
    order: 404 (`get_demo_ticket` returns `None`) → 429 (rate limiter, returned as
    a raw `JSONResponse` — not `HTTPException` — because the required body is
    `{"paused": false, "reason": "rate_limited"}` at the top level, and
    `HTTPException(detail=...)` would nest it under a `"detail"` key instead) → 402
    (`daily_cap_would_be_exceeded`, same `JSONResponse` reasoning, body
    `{"paused": true, "reason": "daily_budget_reached"}`) → else `run_ticket` +
    202 `{"run_id": str(run.id)}`.
  - One module-level `_demo_rate_limiter = RateLimiter()` instance — one per
    process, per the documented single-instance limitation.
- **`scripts/smoke.py` (new):** `python -m scripts.smoke --base-url <url>
  --ticket-id <id>`. POSTs `/api/demo/run`; if it isn't 202, prints the status/body
  to stderr and exits 1. Otherwise polls `GET /api/runs/{run_id}` (default 10
  attempts, 3s apart) until `state` is terminal (`completed`/`escalated`/`failed`).
  Exits 0 iff the final state is `completed` or `escalated` **and**
  `total_cost_usd > 0`; else exits 1 with the specific reason on stderr (wrong
  state, zero/missing cost, or "timed out waiting for terminal state"). Always
  prints `run_id=... state=... cost=...` regardless of outcome. `run_smoke(...)`
  takes an injected `httpx.Client`, so tests use `httpx.MockTransport` — no real
  network, no new dependency (httpx is already in `requirements.txt`).
- **Console (`console/app/demo/page.tsx` + `DemoRunner.tsx`, new; `console/lib/api.ts`
  extended):** a server component fetches the pool and hands it to a client
  component holding the `<select>` + Run button + result messaging — no free-text
  input anywhere, matching the console's existing server/client split
  (`RunRow`/`ReviewItem` pattern). On 402 it renders the banner **verbatim**:
  "Daily demo budget reached — watch the video instead" (with a `{/* link
  placeholder for #17 */}` comment, no link yet). On 429 it shows "Too many demo
  runs from this location in the last hour — try again later." On success it shows
  a link to the run's detail page. `console/app/page.tsx` gained a nav link to
  `/demo` alongside the existing `/review` link.

## The sync-202 decision (binding context from dispatch, noted per instruction)

`run_ticket(ticket_id, session)` (`triagedesk/pipeline/runner.py:23`) creates and
commits its own `Run` row and returns it once finished — it's a synchronous,
~35s-live call. Rather than refactor the pipeline for background dispatch (out of
scope for this task and unrequested), `POST /api/demo/run` calls it synchronously:
the 202 response is only sent after the run has actually finished, carrying its
real `run_id`. This satisfies the plan's contract (`POST /api/demo/run` → 202
`{"run_id": str}`) without inventing an async job model. Consequence for
`scripts/smoke.py`: its poll loop is functionally a formality against this
endpoint today — the first `GET /api/runs/{id}` poll will already see the terminal
state, since the run was fully finished before the 202 was ever returned. The loop
is still written generically (poll-until-terminal-or-timeout) so the script keeps
working unmodified if the endpoint is ever made genuinely async.

## TDD sequence (RED → GREEN per criterion)

RED — `triagedesk.demo` doesn't exist yet:
```
$ .venv/Scripts/python -m pytest tests/unit/test_demo_guards.py -q
ModuleNotFoundError: No module named 'triagedesk.demo'
```
GREEN — after adding `triagedesk/demo.py`, `config.py` fields, and the two new
routes in `app.py`:
```
$ .venv/Scripts/python -m pytest tests/unit/test_demo_guards.py -q
............                                                             [100%]
12 passed, 1 warning in 2.18s
```
Covers, in order: `RateLimiter` allows-then-blocks at the limit; resets exactly at
the 1-hour boundary via a fake clock (not at 59:59, allowed again at exactly
+1:00:00); tracks independent keys separately; `daily_cap_would_be_exceeded` sums
only today's UTC runs and flags a breach, stays green under budget, treats "no
runs today" as not-a-breach, and fails closed when the query raises; then the four
route branches — pool filtering, 404 (both an existing-but-wrong-source ticket and
an unknown id), 429 (with the exact response body), 402 (with the exact response
body, seeded via a same-day run whose cost plus the per-run cap crosses the
configured 1.00 cap), and 202 (asserts `run_ticket` was called with the right
ticket id and the response echoes its `run.id`). Every guard-branch test
monkeypatches `app_module.run_ticket` and asserts the call count stays 0 —
"before spending" is verified, not assumed.

RED — `scripts.smoke` doesn't exist:
```
$ .venv/Scripts/python -m pytest tests/unit/test_smoke.py -q
ModuleNotFoundError: No module named 'scripts.smoke'
```
GREEN — after adding `scripts/smoke.py`:
```
$ .venv/Scripts/python -m pytest tests/unit/test_smoke.py -q
......                                                                   [100%]
6 passed in 0.04s
```
Covers: exit 0 on `completed` + positive cost; exit 0 on `escalated` + positive
cost; exit 1 when cost is 0; exit 1 when state is `failed`; exit 1 when the POST
itself isn't 202; exit 1 ("timed out") when the run never leaves `running` within
`max_polls` (using `poll_interval_s=0` so the test doesn't actually sleep).

## Route-test isolation problem, and how it was solved

`_demo_rate_limiter` is a module-level singleton in `app.py` (deliberately — it's
meant to persist across requests within one process). But `fastapi.testclient`'s
`TestClient` sends every request from the same fixed host string
(`"testclient"`), so without intervention, rate-limit state from one test would
leak into the next test in the same file. `RateLimiter.reset()` was added as a
test-only escape hatch, called in the `client` fixture's setup and teardown
(`app_module._demo_rate_limiter.reset()`), the same isolation problem
`test_console_api.py`'s CORS tests solve differently (via `importlib.reload`) —
here a plain reset method was simpler since the singleton itself, not the whole
app object, needed resetting between tests.

## Manual verification ($0 — no live pipeline call, per the hard rule)

The dev DB already had 3 `source='demo'` tickets seeded from earlier work
(`12023`/`12027` "My VPN keeps disconnecting", `12039` "Please enable dedicated
IP") — no new seeding was needed; documenting what exists rather than adding
duplicates.

**API guard branches** (local `uvicorn`, various `DEMO_*` env overrides, verified
via `curl`, servers killed immediately after each check):
- `GET /api/demo/pool` → returned exactly the 3 demo tickets, correct shape.
- `POST /api/demo/run {"ticket_id": 1}` (a real Kaggle ticket) → 404. Same for
  `{"ticket_id": 999999}` (nonexistent).
- With `DEMO_RATE_LIMIT_PER_HOUR=0` → first-ever call from that host → 429, body
  `{"paused": false, "reason": "rate_limited"}` exactly.
- With `DEMO_DAILY_CAP_USD=0` → 402, body `{"paused": true, "reason":
  "daily_budget_reached"}` exactly.
- **Never let a request reach a guard-passing configuration** — one setup mistake
  (see "incident" below) was caught and killed *before* any request was sent to
  it, specifically to protect the $0 rule.

**Console UI** (local `npm run dev` at `127.0.0.1:3099` against the local API at
`127.0.0.1:8099`, `CORS_ORIGINS` set to match, driven with `agent-browser`):
- `/demo` renders the pool dropdown (3 tickets, no free-text field anywhere) and a
  Run button.
- With `DEMO_DAILY_CAP_USD=0`: clicking Run rendered the banner verbatim —
  **"Daily demo budget reached — watch the video instead"**.
- With `DEMO_RATE_LIMIT_PER_HOUR=0`: clicking Run rendered "Too many demo runs
  from this location in the last hour — try again later."
- Confirmed via a direct DB query afterward that the most recent `runs` row
  predates this session's testing by hours — no run was created by any of the
  manual checks above.
- `npm run build` in `console/` passes clean, including the new `/demo` route.

**Minor incident during manual testing (caught, not a code issue):** an earlier
`uvicorn` instance wasn't killed between two Bash tool calls (each call is a fresh
shell — background job control (`kill %1`) doesn't carry over), so a later `curl`
round briefly hit the *old* process's settings instead of the new ones, making a
429 check look like a 402. Diagnosed via `netstat`, the stale process was killed
by PID, and — critically — the follow-up attempt with a large daily cap (which
would have let a real request through to `run_ticket`) was killed by PID **before
any request was sent to it**, specifically to protect the $0 rule the moment the
risk was noticed. Re-ran with `DEMO_RATE_LIMIT_PER_HOUR=0` (blocks the very first
request, before the daily-cap check is ever reached) instead — confirms the
route's guard *ordering* (404 → 429 → 402) is real, not just individually testable
in isolation.

## Test + ruff output summary

```
$ .venv/Scripts/python -m pytest -q tests/unit
205 passed, 1 warning in 3.00s
$ .venv/Scripts/python -m ruff check .
All checks passed!
$ cd console && npm run build
✓ Compiled successfully
```
(187 pre-Task-7 unit tests + 12 `test_demo_guards.py` + 6 `test_smoke.py` = 205.)

## Decisions

- **`JSONResponse` instead of `HTTPException` for 429/402.** `HTTPException`
  always wraps its `detail` under a `"detail"` key in the response body
  (`{"detail": {...}}`), which doesn't match the brief's required top-level shape
  (`{"paused": ..., "reason": ...}`). 404 keeps using `HTTPException` since its
  body shape isn't specified and matches the rest of the app's 404 convention.
- **Reused `settings.cost_cap_usd` as the "per-run cap" in the daily-cap formula**,
  rather than hardcoding `0.10` a second time — it's already the project's single
  source of truth for the per-run cost cap (`docs/00-spec` non-negotiable rule),
  and the brief's "$0.10 per-run cap" phrase is literally that setting's default.
- **`get_demo_ticket` folds "doesn't exist" and "exists but wrong source" into the
  same `None` result.** The pool-only rule doesn't distinguish those cases for the
  caller — both are simply "not a valid demo run target" — so the route only needs
  one branch, and a real ticket id can't be used to probe whether it exists.
- **No new console dependency, no data library.** The demo page follows the exact
  server-component-fetches / client-component-mutates split already established by
  `page.tsx`/`RunRow` and `review/page.tsx`/`ReviewQueueClient`/`ReviewItem`.
- **Separate `console/app/demo/page.tsx` rather than extending the run-list page**,
  matching the review queue's own precedent (Task 3/4 got its own route) — keeps
  the guarded, no-free-text demo flow visually and structurally distinct from the
  internal ops views.

## Files changed

- `triagedesk/demo.py` (new) — pool queries, `RateLimiter`, `daily_cap_would_be_exceeded`
- `triagedesk/config.py` — `demo_daily_cap_usd`, `demo_rate_limit_per_hour`
- `triagedesk/app.py` — `GET /api/demo/pool`, `POST /api/demo/run`, `DemoRunIn`,
  `_demo_rate_limiter`, `run_ticket` import
- `.env.example` — `DEMO_DAILY_CAP_USD`, `DEMO_RATE_LIMIT_PER_HOUR` documented
- `scripts/smoke.py` (new) — the post-deploy smoke check
- `tests/unit/test_demo_guards.py` (new) — 12 tests
- `tests/unit/test_smoke.py` (new) — 6 tests
- `console/lib/api.ts` — `listDemoPool`, `runDemo`, `DemoPoolTicket`/`DemoPool`/`DemoRunResult`
- `console/app/demo/page.tsx`, `console/app/demo/DemoRunner.tsx` (new)
- `console/app/page.tsx` — nav link to `/demo`

## Known gaps / not done here

- No production seeding — the brief is explicit that production pool seeding
  happens at Task 6 deploy time, not here.
- The rate limiter's single-instance limitation is documented, not fixed (a
  multi-replica Railway deploy would need a shared store); acceptable for a
  single-replica demo deploy per the plan.
- No reverse-proxy / `X-Forwarded-For` handling — `request.client.host` is used
  directly, which is correct for a direct connection but would see the proxy's IP
  for all callers behind one (not the plan's concern this week; Railway's default
  setup was not verified against this).
- `scripts/smoke.py`'s poll loop is effectively unexercised by the current
  synchronous 202 design (see the sync-202 section) — it will matter if the
  endpoint is ever made async, not before.
