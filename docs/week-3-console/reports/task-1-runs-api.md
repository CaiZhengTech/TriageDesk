# Task 1: Runs read API — list + detail (issue #13, API half)

## What was implemented

Two new read-only endpoints on the existing FastAPI app, backed by a new
`triagedesk/console_queries.py` module (no ORM queries inline in routes, per the
binding constraint):

- `GET /api/runs?limit=50&offset=0` — newest-first run list. Each row: `id`,
  `ticket_id`, `ticket_subject`, `state`, `escalation_reason`, `total_cost_usd`,
  `latency_ms`, `model`, `created_at`. `total` is a separate `COUNT(*)` over the
  whole table, independent of `limit`/`offset`. No filtering by state — failed
  runs appear with their `escalation_reason` visible (non-negotiable design rule).
- `GET /api/runs/{run_id}` — the same fields plus `final_reply`,
  `internal_rationale`, `gate_signals`, and `spans` (ordered by `started_at`,
  each with `name`, `status`, `duration_ms`, `input_tokens`, `output_tokens`,
  `cost_usd`, `attributes`). 404 on an unknown UUID (query returns `None`, route
  raises `HTTPException(404)`); 422 on a malformed UUID — FastAPI's
  `run_id: uuid.UUID` path-param typing gives this for free.

`console_queries.py` exports:
- `_to_naive_utc(dt)` / `_duration_ms(start, end)` — the tz-normalization helper
  the brief calls out (`runs.created_at` is naive, `runs.finished_at` is aware;
  subtracting them directly raises `TypeError`). Applied symmetrically to both
  operands, so it's correct regardless of which side ends up aware at runtime —
  it doesn't hardcode "created_at is naive, finished_at is aware," it just
  normalizes whichever side has tzinfo. Reused for span `duration_ms` too, since
  `started_at`/`ended_at` come from the same code path. Returns `None` if either
  input is `None` (covers `state='running'` and any run without a `finished_at`).
- `list_runs(db, limit, offset)` and `get_run_detail(db, run_id)` — the two
  public query functions the routes call.

`triagedesk/app.py` gained `import uuid`, the `console_queries` import, and the
two route functions (16 lines added, nothing else touched).

## Test results

Full suite: **195 passed**, 1 pre-existing deprecation warning
(`httpx`/starlette, unrelated). Ruff: **all checks passed**.

New file: `tests/unit/test_console_api.py` — 7 tests, all using an in-memory
SQLite session (`sqlite://` + `StaticPool` + `check_same_thread=False`, needed
because FastAPI's `TestClient` can dispatch the request on a different thread
than the one that opened the in-memory DB — first run failed with
`SQLite objects created in a thread can only be used in that same thread`
until that was added). Tables are created with hand-written DDL (`JSON` instead
of `JSONB`) because the real `Run`/`Span` models use Postgres `JSONB` columns,
which have no SQLite DDL compiler (`Compiler ... can't render element of type
JSONB` — confirmed empirically before writing the fixture). The real
`triagedesk.models` ORM classes are used unmodified for all inserts/queries —
only the table DDL is swapped, not the model code, so `console_queries.py` runs
the same ORM code path it would against Postgres.

## TDD evidence

**RED** — before `console_queries.py` existed:

```
$ .venv/Scripts/python -m pytest tests/unit/test_console_api.py -q
...
ModuleNotFoundError: No module named 'triagedesk.console_queries'
1 warning, 1 error in 0.80s
```

Then, after adding `console_queries.py` but before `check_same_thread`/`StaticPool`
in the test fixture, list/detail tests failed with
`sqlite3.OperationalError: no such table: runs` (each request got a fresh
in-memory DB because SQLite's default pooling opens a new connection per
checkout for `sqlite:///:memory:`) — fixed by switching to `sqlite://` +
`StaticPool` + `check_same_thread=False` so the whole test shares one
connection/DB.

**GREEN** — after implementing `console_queries.py` + the two routes and fixing
the SQLite pooling:

```
$ .venv/Scripts/python -m pytest tests/unit/test_console_api.py -q
.......                                                                  [100%]
7 passed, 1 warning in 0.46s
```

Per TDD step, mapped to the test functions:

- **(a)** `test_list_runs_newest_first_with_latency_and_failed_run_visible` —
  newest-first order, `latency_ms` computed on the completed run, the failed
  run present with `escalation_reason="budget_breach"` and `latency_ms is None`.
- **(b)** `test_duration_ms_normalizes_naive_and_aware_datetimes` +
  `test_duration_ms_is_none_when_finished_at_missing` — naive `created_at` +
  aware `finished_at` subtract without raising, `3000.0`ms; `None` when
  `finished_at` is `None`.
- **(c)** `test_get_run_detail_404_on_missing_id` +
  `test_get_run_detail_422_on_non_uuid_id`.
- **(d)** `test_get_run_detail_spans_ordered_with_tokens_and_cost` — spans
  inserted out of order, asserted back in `started_at` order; token/cost fields
  extracted from `attributes`, missing keys give `None`.
- **(e)** `test_list_runs_pagination_total_independent_of_limit` — 3 runs,
  `limit=1` returns 1 row but `total=3`.

## Files changed

- `triagedesk/console_queries.py` (new)
- `triagedesk/app.py` (modified — 2 new routes, 2 new imports)
- `tests/unit/test_console_api.py` (new — 7 tests)

## Self-review

- **Completeness:** both endpoints match the brief's shapes verbatim; all 3
  acceptance criteria hold (failed runs unfiltered; all reads through
  `console_queries.py`; tests use an in-memory, non-live DB); TDD steps a–e all
  have a corresponding test.
- **Quality:** names and style match the existing `app.py`/`models.py`
  conventions (module-level functions taking `Session`, `-> dict` return
  annotations, docstrings pointing back to the schema doc for the gotcha).
- **Discipline (YAGNI):** no filtering/sorting params beyond `limit`/`offset`
  from the brief; no new schema, no migration; didn't touch unrelated routes or
  `models.py`.
- **Testing:** all 7 tests assert behavior (ordering, computed fields, 404/422,
  pagination independence), not implementation details; full suite + ruff both
  clean; output is pristine (no unexpected warnings beyond the pre-existing
  httpx deprecation notice).

## Concerns

- None blocking. One judgment call worth flagging: the brief's tz gotcha is
  phrased as "naive `created_at` + aware `finished_at`," but I made
  `_duration_ms` normalize symmetrically (whichever side has `tzinfo`) rather
  than hardcoding which field is naive vs. aware. This is deliberately more
  robust — it's also what let me reuse the same helper for span
  `duration_ms` (`started_at`/`ended_at`, both written via the same
  `datetime.now(UTC)` call in `tracing.py`, so normalization is a no-op there
  today but costs nothing to keep uniform).
- Console pages (the UI half of issue #13) are out of scope for this task —
  API only, per the task brief.
