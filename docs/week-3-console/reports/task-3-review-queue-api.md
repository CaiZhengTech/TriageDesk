# Task 3: `review_decisions` + review-queue API + admin token (issue #14, API half)

## What was implemented

The human-in-the-loop surface the adverse-action rule requires: the write side that
turns "escalate to human review" from a promise into an inbox a person can act on.

- **Model + migration:** `ReviewDecision` (`triagedesk/models.py`) — `id` int PK,
  `run_id` UUID FK → `runs` (**unique** — a run gets exactly one decision, ever),
  `decision` str(8) (`approve`|`reject`), `note` text, `created_at` server-default
  timestamp. Alembic revision `c6811ea1a93e_review_decisions.py`, chained off the
  current head `b2a3edf4a55a` (the `eval_results_golden` view). `upgrade()` creates
  the table (FK + unique constraint on `run_id`), `downgrade()` drops it.
- **Config:** `Settings.admin_token: str = ""` (`triagedesk/config.py`) — empty by
  default, matching the fail-closed contract (unset ⇒ 503, never "open").
- **Queue query:** `list_review_queue(db)` in `console_queries.py` — runs where
  `state='escalated'` and no `ReviewDecision.run_id` matches, ordered by
  `Run.created_at.asc()` (oldest first — the inbox drains front-to-back). Reuses
  `_run_summary()` from Task 1 and adds `internal_rationale` + `final_reply`.
  **No filter on `escalation_reason`** — adverse-action escalations
  (`adverse_action`, `no_entitlement_evidence`) appear like any other escalation,
  per the binding constraint.
- **Routes** (`triagedesk/app.py`):
  - `GET /api/review-queue` → `{"items": [...], "total": int}`.
  - `POST /api/review/{run_id}` — body `ReviewDecisionIn` (Pydantic model,
    `decision: Literal["approve", "reject"]`, `note: str`) + `X-Admin-Token` header
    (via FastAPI's `Header(default=None)`, which maps `x_admin_token` →
    `X-Admin-Token` automatically). Checks in order: **503** if
    `settings.admin_token` is falsy (checked *before* looking at the caller's
    header — fail closed regardless of what the client sends); **401** if the
    header is missing or doesn't match; **404** if the run doesn't exist; **409**
    if a `ReviewDecision` already exists for that run; else insert + commit +
    return `{"id": decision.id}` with **201**. A malformed `decision` value never
    reaches the function — FastAPI/Pydantic reject it with **422** before the
    body is available.
- **Docs:** `docs/00-spec/DATA-SCHEMA.md` gained a `review_decisions` subsection
  (columns + the queue/write contract) and its table-at-a-glance row was updated
  from "not built yet" to the real row count. `.env.example` documents
  `ADMIN_TOKEN` with the fail-closed note inline.

## Test results

Full suite: **202 passed** (182 unit + a live integration run), 1 pre-existing
`httpx`/starlette deprecation warning (unrelated). Ruff: **all checks passed**.

`tests/unit/test_console_api.py` gained: a `review_decisions` SQLite table in the
`db_session` fixture, a `_make_review_decision` helper, and 7 new tests (1 queue +
6 POST-route tests covering persist/409/404/422/401/503).

## TDD evidence

**(a) queue lists escalated-undecided only, oldest first**

RED — route doesn't exist yet:
```
$ .venv/Scripts/python -m pytest tests/unit/test_console_api.py::test_review_queue_lists_escalated_undecided_oldest_first -q
...
assert 404 == 200
1 failed, 1 warning in 0.69s
```
GREEN — after adding `list_review_queue()` + `GET /api/review-queue`:
```
$ .venv/Scripts/python -m pytest tests/unit/test_console_api.py::test_review_queue_lists_escalated_undecided_oldest_first -q
.                                                                        [100%]
1 passed, 1 warning in 0.48s
```
Test asserts: two escalated-undecided runs returned oldest-first (a third
escalated run with a `ReviewDecision` row is excluded; a fourth `completed` run
is excluded); one of the two carries `escalation_reason="adverse_action"` and is
present anyway — covers the "adverse-action escalations appear like any other"
acceptance criterion directly.

**(b)/(c)/(d) POST route — persist/409, 401, 503, plus 404/422**

RED — route doesn't exist (all four behavior tests fail with 404 from FastAPI's
own routing, except the 404-on-unknown-run test, which spuriously passed for the
wrong reason — "route not found" and "run not found" both 404 until the real
route exists):
```
$ .venv/Scripts/python -m pytest tests/unit/test_console_api.py -k "post_review" -q
FAILED test_post_review_persists_then_409_on_second_decision - assert 404 == 201
FAILED test_post_review_422_on_bad_decision_value - assert 404 == 422
FAILED test_post_review_401_when_token_missing_or_wrong - assert 404 == 401
FAILED test_post_review_503_when_admin_token_unset - assert 404 == 503
4 failed, 1 passed, 8 deselected, 1 warning in 0.84s
```
GREEN — after adding `POST /api/review/{run_id}` with the full order-of-checks
(503 → 401 → 404 → 409 → insert):
```
$ .venv/Scripts/python -m pytest tests/unit/test_console_api.py -k "post_review" -q
.....                                                                    [100%]
5 passed, 8 deselected, 1 warning in 0.64s
```
Mapped to the brief's steps:
- **(b)** `test_post_review_persists_then_409_on_second_decision` — first POST
  201 + `id` present; identical second POST on the same `run_id` → 409.
- **(c)** `test_post_review_401_when_token_missing_or_wrong` — both the missing
  header and the wrong-value header cases assert 401.
- **(d)** `test_post_review_503_when_admin_token_unset` — `settings.admin_token`
  monkeypatched to `""`; any header value still gets 503, never 401 or success.
- Also added (contract-complete, not brief-mandated as separate TDD letters):
  `test_post_review_404_on_unknown_run`, `test_post_review_422_on_bad_decision_value`.

**(e) migration round-trip — integration-marked**

Ran live against the reachable Neon test branch (`TRIAGEDESK_ENV_FILE` set,
`TEST_DATABASE_URL` present):
```
$ .venv/Scripts/python -m pytest tests/integration/test_review_decisions_migration.py -q
.                                                                        [100%]
1 passed in 3.54s
```
`command.upgrade(cfg, "head")` → table exists; `command.downgrade(cfg,
"b2a3edf4a55a")` → table gone; `command.upgrade(cfg, "head")` again → table
restored (leaves the shared branch at head for other integration tests, same
convention as `test_eval_results_golden_view.py`).

Also confirmed offline that the new revision is the sole head:
```
$ .venv/Scripts/python -m alembic history
b2a3edf4a55a -> c6811ea1a93e (head), review_decisions table
868d4d9166da -> b2a3edf4a55a, eval_results_golden view
...
```

## Files changed

- `triagedesk/models.py` — `ReviewDecision` model (10 lines)
- `triagedesk/config.py` — `admin_token: str = ""`
- `triagedesk/console_queries.py` — `list_review_queue()`
- `triagedesk/app.py` — `ReviewDecisionIn`, `GET /api/review-queue`,
  `POST /api/review/{run_id}`
- `alembic/versions/c6811ea1a93e_review_decisions.py` (new)
- `tests/unit/test_console_api.py` — extended fixture + 7 new tests
- `tests/integration/test_review_decisions_migration.py` (new)
- `.env.example` — `ADMIN_TOKEN`
- `docs/00-spec/DATA-SCHEMA.md` — `review_decisions` subsection + table row

## Self-review

- **Completeness vs. brief:** both endpoint contracts match verbatim (fields,
  status codes, ordering); all three binding acceptance criteria hold (queue
  excludes decided runs; adverse-action escalations appear unfiltered; the three
  auth behaviors are each a test — 401 missing, 401 wrong, 503 unset); TDD steps
  a–e all have a corresponding RED→GREEN pair above.
- **Fail-closed auth, verified in the right order:** the 503 check runs before
  the 401 check in the route body, so an unset token can never be masked by
  "well the header also happened to be missing → 401 instead" — confirmed by
  `test_post_review_503_when_admin_token_unset` sending a *non-empty* header
  (`"anything"`) and still getting 503, not 401.
- **YAGNI:** no additional query params, no soft-delete/undo path, no pagination
  on the queue (not in the brief — the queue is expected to be small; if that
  changes it's a follow-up, not speculative now). Didn't touch the console UI
  (Task 4, separate) or unrelated routes/models.
- **Style match:** `list_review_queue` follows the existing
  `console_queries.py` pattern exactly (module-level function taking `Session`,
  reuses `_run_summary`); the route mirrors the existing `api_get_run` shape
  (`Depends(get_db)`, `HTTPException` for error paths); the migration file
  mirrors `868d4d9166da_eval_tables.py`'s auto-generated style (explicit
  `sa.Column`/`ForeignKeyConstraint`/`PrimaryKeyConstraint` calls) rather than
  the raw-SQL style of the view migration, since this is a real table.
- **Testing:** added two tests beyond the letter-mapped TDD list (404 unknown
  run, 422 bad decision value) because they're explicit, cheap-to-verify parts
  of the endpoint's contract in the brief; kept every other test to one behavior
  per function, matching Task 1's file. Full suite + ruff both clean, output
  pristine (only the pre-existing httpx/starlette deprecation warning).

## Concerns

- **None blocking.** One thing worth flagging for whoever builds Task 4 (the
  queue UI): the queue has no pagination (`GET /api/review-queue` returns every
  escalated-undecided run in one response). Given the current run volume (order
  dozens) this is fine; if the queue grows large enough for pagination to
  matter, that's a small follow-up on top of `list_review_queue`, not a
  redesign.
- The 404-unknown-run test spuriously passed during the RED phase (FastAPI's
  own "no matching route" 404 is indistinguishable from the intended "run not
  found" 404 until the route exists) — noted in the TDD evidence above so it's
  not mistaken for a false-green; the test still exercises the intended code
  path (a real 404 raised by `db.get(Run, run_id)` returning `None`) once the
  route was implemented.
- Live-reachable Neon test branch: the integration test ran for real (not
  skipped), so the migration is verified against actual Postgres DDL, not just
  SQLite's approximation — no live Anthropic/Voyage calls were made ($0 cost).
