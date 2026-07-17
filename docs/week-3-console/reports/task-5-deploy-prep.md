# Task 5: Deploy-prep code — CORS + JSON logs (issue #15, code half)

## What was implemented

The last piece the console needs before Task 6 (live deploy): today the API has no
CORS middleware, so the console's cross-origin `POST /api/review/{run_id}` (Vercel
domain → Railway domain) is blocked by the browser at the preflight step, review
decisions can't be recorded from the deployed console. Also added the structured
JSON log formatter from the same plan slot (both are cheap, both belong to
"deploy-prep").

- **Config (`triagedesk/config.py`):** two new fields, both safe defaults —
  `cors_origins: str = ""` (comma-separated allowed origins) and
  `log_json: bool = False`. Documented in `.env.example` alongside the existing
  `ADMIN_TOKEN` entry.
- **CORS (`triagedesk/app.py`):** `settings.cors_origins` is parsed into a list
  (strip + drop empties) once at module load. If the list is non-empty, Starlette's
  `CORSMiddleware` (via `fastapi.middleware.cors` — ships with FastAPI, no new
  dependency) is registered with that origin list, `allow_methods=["GET", "POST",
  "OPTIONS"]`, `allow_headers=["X-Admin-Token", "Content-Type"]` — exactly what the
  console's `fetch` calls send. **Fail closed:** if the parsed list is empty, the
  middleware is not added at all (no wildcard, no empty-list CORSMiddleware) — the
  cleanest expression of "empty config = no cross-origin access," and it's what the
  comment in `app.py` documents inline.
- **JSON logs (`triagedesk/logging_setup.py`, new):** a stdlib `logging.Formatter`
  subclass (`JsonFormatter`) that emits one-line `{"ts", "level", "logger", "msg"}`
  JSON objects (`ts` = the record's timestamp as UTC ISO-8601, no new deps). A
  `configure_json_logging()` helper repoints the root logger at a single
  `StreamHandler` using that formatter. `app.py` calls it at module load when
  `settings.log_json` is true.

## The settings-override / middleware-registration problem, and how it was solved

The rest of `app.py`'s settings-driven behavior (e.g. `admin_token`) is checked
*inside* a route function body, so tests can `monkeypatch.setattr(settings,
"admin_token", ...)` before a request and it just works — the check runs fresh on
every call. CORS doesn't have that luxury: `CORSMiddleware` is a structural piece
of the ASGI stack, registered once via `app.add_middleware(...)` at import time, not
re-evaluated per request. And `app` is a module-level singleton imported once at
test collection (`from triagedesk.app import app` at the top of
`test_console_api.py`), so by the time any test runs, the middleware stack (or lack
of it) is already baked in from whatever `settings.cors_origins` happened to be at
first import.

Two options considered:
1. **App factory** (`create_app()` returning a fresh `FastAPI` per call) — rejected
   because the brief and the plan are explicit that `app.py` stays a plain module
   with `app` at module scope (the deploy command is literally
   `uvicorn triagedesk.app:app`); introducing a factory here is a structural change
   the task didn't ask for.
2. **Monkeypatch + `importlib.reload`** — the approach taken. The two new CORS
   tests in `tests/unit/test_console_api.py` do:
   ```python
   monkeypatch.setattr(settings, "cors_origins", "https://console.example.com")
   importlib.reload(app_module)
   cors_client = TestClient(app_module.app)
   ```
   `importlib.reload(app_module)` re-executes `app.py`'s top-level code, which
   creates a **new** `FastAPI()` instance and re-registers `CORSMiddleware` against
   the just-patched `settings.cors_origins` value. Critically, this only rebinds
   `app_module.app` (a new module-level test import, `import triagedesk.app as
   app_module`, added for exactly this) — the `app` name imported at the top of the
   file (`from triagedesk.app import app`), which every other test's `client`
   fixture uses, still points at the original object created at test-collection
   time. So the reload can't leak into any of the other 202 pre-existing tests; it
   only affects the two CORS tests, which build their own `TestClient` from the
   freshly reloaded module. No app-factory refactor, no change to the production
   entrypoint, no cross-test state.

## TDD sequence (RED → GREEN per criterion)

**JSON log formatter**

RED — module doesn't exist:
```
$ .venv/Scripts/python -m pytest -q tests/unit/test_logging_setup.py
ModuleNotFoundError: No module named 'triagedesk.logging_setup'
1 error in 0.43s
```
GREEN — after adding `triagedesk/logging_setup.py`:
```
$ .venv/Scripts/python -m pytest -q tests/unit/test_logging_setup.py
..                                                                       [100%]
2 passed in 0.03s
```
Two tests: a record with `%s`-style args formats to valid JSON with `ts`/`level`/
`logger`/`msg` present and `msg` interpolated; a second record confirms `level`
tracks the record's actual level (`ERROR`, not hardcoded).

**CORS**

RED — no middleware registered yet, so a preflight `OPTIONS` doesn't get CORS
handling at all (Starlette's router returns 405, not a CORS response):
```
$ .venv/Scripts/python -m pytest -q tests/unit/test_console_api.py -k cors
F.
AssertionError: assert None == 'https://console.example.com'
 ...Response [405 Method Not Allowed]...
1 failed, 1 passed, 13 deselected, 1 warning in 0.56s
```
(The fail-closed test passed trivially at this point too — no middleware existed
yet — but it exercises the real code path once the middleware is added, since
`cors_origins=""` still yields "no middleware registered" after the change, not
"by accident.")

GREEN — after adding the `CORSMiddleware` registration block in `app.py`:
```
$ .venv/Scripts/python -m pytest -q tests/unit/test_console_api.py -k cors
..                                                                       [100%]
2 passed, 13 deselected, 1 warning in 0.38s
```
- `test_cors_allows_configured_origin_and_omits_header_for_others`: preflight with
  `Origin: https://console.example.com` gets that origin echoed back in
  `access-control-allow-origin`; the same preflight with `Origin:
  https://evil.example.com` gets no such header at all.
- `test_cors_empty_origins_registers_no_middleware_fail_closed`: `cors_origins=""`
  → preflight from any origin gets no `access-control-allow-origin` header
  (confirms the "don't add the middleware at all" path, not just "add it with an
  empty list").

## Test + ruff output summary

Full suite, from repo root with `TRIAGEDESK_ENV_FILE` set:
```
$ .venv/Scripts/python -m pytest -q
206 passed, 1 warning in 28.76s
```
(202 baseline + 2 logging + 2 CORS = 206; the one warning is the pre-existing
`httpx`/starlette deprecation notice, unrelated to this change.)
```
$ .venv/Scripts/python -m ruff check .
All checks passed!
```

## Decisions

- **`allow_credentials` left at Starlette's default (`False`).** The console
  authenticates with a custom `X-Admin-Token` header, not cookies, so credentialed
  CORS was never needed — adding it would be unrequested scope.
- **`OPTIONS` included in `allow_methods`** per the brief, even though browsers
  send the *target* method (e.g. `POST`) in `Access-Control-Request-Method` during
  preflight, not literally `"OPTIONS"` — harmless and matches the brief's explicit
  list verbatim.
- **JSON log timestamp format:** `datetime.fromtimestamp(record.created,
  tz=UTC).isoformat()` rather than the record's default `asctime` — ISO-8601 UTC is
  what downstream log aggregators (Railway's log viewer, if piped anywhere later)
  expect, and it's a one-line stdlib call, not a new dependency.
- **`configure_json_logging()` called at `app.py` module load**, not inside a
  FastAPI `@app.on_event("startup")` hook. Since `app.py` *is* the process
  entrypoint (`uvicorn triagedesk.app:app` imports it once at boot), module-load
  time already **is** startup time here — a startup-event hook would be an
  unrequested extra layer for the same effect.

## Files changed

- `triagedesk/config.py` — `cors_origins: str = ""`, `log_json: bool = False`
- `triagedesk/app.py` — CORS middleware registration block, JSON logging
  bootstrap call
- `triagedesk/logging_setup.py` (new) — `JsonFormatter`, `configure_json_logging()`
- `.env.example` — `CORS_ORIGINS`, `LOG_JSON` documented
- `tests/unit/test_console_api.py` — 2 new CORS tests + `importlib`/`app_module`
  imports
- `tests/unit/test_logging_setup.py` (new) — 2 tests for `JsonFormatter`

## Known gaps / not done here

- No live deploy, no Railway/Vercel config touched (Task 6, needs Cai's accounts).
- No post-deploy smoke script (`scripts/smoke.py`) — that's also Task 6/descope-
  ladder territory per the plan's ordering, not this task's file list.
- `CORS_ORIGINS` and `LOG_JSON` are not yet set in any real environment (Railway env
  vars); that's a Task 6 action, not code.

## Fix: CORS preflight coverage

**Finding (code review):** The two existing CORS tests in `tests/unit/test_console_api.py`
only cover preflight for `GET /api/runs`. The browser-real POST request this task
unblocks — the console review-queue page's cross-origin `POST /api/review/{run_id}`
carrying `Content-Type: application/json` + `X-Admin-Token` — had no test pinning it,
so a future narrowing of `allow_methods` or `allow_headers` would pass the suite while
breaking production.

**Fix:** Added one new CORS test, `test_cors_preflight_review_endpoint_post_with_admin_token_header`,
which:
- Sends a preflight `OPTIONS` request against `/api/review/<uuid>`
- Includes headers: `Origin: https://console.example.com`, 
  `Access-Control-Request-Method: POST`, 
  `Access-Control-Request-Headers: X-Admin-Token, Content-Type`
- Asserts: status 200, origin echo, `POST` in allowed methods, and `X-Admin-Token`
  in allowed headers (case-insensitive comparison)
- Follows the existing test pattern (monkeypatch + `importlib.reload`)

**Test run and output:**
```
$ .venv/Scripts/python -m pytest tests/unit/test_console_api.py -q
................                                                         [100%]
16 passed, 1 warning in 0.53s

$ .venv/Scripts/python -m ruff check tests/unit/test_console_api.py
All checks passed!
```

All 16 tests pass (14 pre-existing + 2 CORS baseline + 1 new review-endpoint test),
linter clean.
