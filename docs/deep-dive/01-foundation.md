# Chunk 1 — The Foundation

`config.py` · `db.py` · `models.py` · `alembic/`

Build order: these are Week-1 Tasks 1–2. Nothing else in the project can be written
until these exist, because every other file either reads configuration, opens a
database session, or refers to a table.

---

## The one-sentence version of each

| File | What it does | Why it's separate |
|---|---|---|
| `config.py` | Turns environment variables into one typed, validated Python object | So no other file ever calls `os.environ` — there is exactly one place that knows what configuration exists |
| `db.py` | Builds the database engine and hands out sessions | So no other file knows the connection URL, the driver, or the pooling policy |
| `models.py` | Declares the 7 tables as Python classes | So the schema is defined once, in code, and both the app and the migrations read the same definition |
| `alembic/` | Version-controls changes to the schema over time | Because `models.py` describes what the schema *should* be; migrations are how a database that already has data *gets* there |

---

## `config.py` — one door for all configuration

25 lines. Pydantic-settings reads environment variables, coerces them to the declared
types, and exposes them as `settings.database_url`, `settings.cost_cap_usd`, etc.

**Three decisions worth being able to defend:**

1. **`TRIAGEDESK_ENV_FILE` indirection.** `config.py` does not know where the secrets
   file lives. The machine says, via an env var. Local dev points it at
   `~/.secrets/credentials.env`; CI and the deploy set real env vars and leave it unset
   (a missing `env_file` is silently ignored). One file that works in three environments
   with no branching.

2. **`extra="ignore"`.** The shared credentials file also holds keys for unrelated
   projects. Pydantic's default is to *raise* on unknown keys. Without this line the app
   would refuse to start because an unrelated API key was in the file.

3. **Every field has a default.** `database_url: str = ""` means importing the module
   never fails, even with nothing configured. That is what lets unit tests and `alembic`
   import the package on a machine with no secrets. The tradeoff is honest: missing
   config fails *later*, at the point of use, instead of loudly at startup.

**`settings = Settings()` is instantiated at import time** — a module-level singleton.
Consequence: changing an env var after import has no effect, so tests patch the
`settings` object rather than the environment.

**Without this file:** every module reaches into `os.environ` with its own spelling and
its own default. `COST_CAP_USD` becomes a string in one file and a float in another, and
the fail-closed cost cap silently compares a string to a number.

---

## `db.py` — engine, session, and two serverless-Postgres details

**The mental model.** The *engine* is the pool of open connections to Postgres —
expensive to create, so you make one and keep it. A *session* is a unit of work: a
shopping cart. You add things to the cart (`session.add`), and nothing reaches the
database until you check out (`session.commit`). If checkout fails partway, you cancel
the whole thing (`session.rollback`) so you never end up with half an order.

**`_driver_url()` — the four lines that would have cost an hour.** Neon hands out URLs
beginning `postgresql://`. SQLAlchemy maps that prefix to **psycopg2**, which this
project does not install — it uses **psycopg 3**. So the URL is rewritten to
`postgresql+psycopg://` before the engine is built. Skip this and you get
`ModuleNotFoundError: No module named 'psycopg2'` — an error that names a library you
never chose and never wanted.

**`pool_pre_ping=True` — a decision that only makes sense on serverless Postgres.**
Neon suspends idle compute. A connection sitting in the pool can therefore be dead
through no fault of the application. Pre-ping sends a cheap `SELECT 1` before handing a
pooled connection to the caller and quietly replaces it if it's dead. On an always-on
Postgres you would likely skip this; on Neon it is the difference between a working app
and random `OperationalError`s after every quiet period.

**`engine = make_engine(...) if settings.database_url else None`.** Importing
`triagedesk.db` must never require a database. That is what allows the unit tests to
import the package with no `DATABASE_URL` set.

**`get_db()`** is a generator dependency: FastAPI calls it per request, yields the
session to the handler, and the `finally` closes it whether the handler succeeded or
raised. `SessionLocal` is exported separately because background work needs its own
session — the request-scoped one dies with the response (see `app.py:_execute_demo_run`).

---

## `models.py` — the 7 tables, and the decisions inside them

`tickets` · `runs` · `spans` · `kb_docs` · `eval_cases` · `eval_results` ·
`review_decisions`

An **ORM** maps a Python class to a table and an instance to a row, so you write
`run.state = "escalated"` instead of assembling UPDATE strings. The cost is a layer of
indirection that can hide expensive queries; the benefit is that the schema is declared
once, in typed Python, and the migration tool reads the same declaration.

### Decisions to be able to defend

**`Run.id` is a UUID; `Ticket.id` is an int.** Run ids appear in URLs (`/runs/{id}`) and
are handed to the public console. Sequential integers would leak volume — "this is run
#7" tells a visitor exactly how much traffic the demo has seen — and would let anyone
enumerate every run by counting. Ticket ids are internal, so a cheap auto-increment is
fine. Second benefit: `default=uuid.uuid4` generates the id in Python, so the id is known
*before* the INSERT.

**`gate_signals` and `Span.attributes` are `JSONB`, not columns.** The gate's signals
changed during the project — thresholds were re-derived in Week 2.5. Every change would
have meant a migration if these were real columns. JSONB buys schema flexibility for data
that is *evidence to read back*, not data to filter on. The tradeoff is real: querying
inside JSONB is clumsier and unindexed by default.

**`Span.attributes` uses `gen_ai.*` keys** — OpenTelemetry's GenAI semantic conventions,
stored in a hand-rolled Postgres table instead of exported to a real tracing backend.
Deliberate scope cut: the *naming convention* is the portable part, so the data could be
shipped to a real OTel collector later without renaming anything.

**`ReviewDecision.run_id` is `unique=True`.** "One human verdict per run" is enforced by
a **database constraint**, not by an `if` in the API handler. Application checks can be
raced by two concurrent requests; a unique index cannot. The handler's 409 is the
friendly message, not the actual guarantee.

**`RUN_STATES` is a plain tuple, not a database enum or CHECK constraint.** The valid
states are documented in Python and enforced by convention only. This is a genuine weak
spot, not hidden cleverness — an interviewer who asks "what stops a typo writing
`state='escalted'`?" has found a real answer: nothing does.

**The timestamp gotcha.** `created_at` uses `server_default=func.now()`, so Postgres
writes it into a `timestamp without time zone` — **naive**. `finished_at` is set from
Python with timezone-**aware** datetimes. Comparing the two raises `TypeError`, which is
why `demo.py` normalizes `now` to naive UTC before comparing against `created_at`, and
why `console_queries.py` has a guard in its latency calculation. Documented in
`docs/00-spec/DATA-SCHEMA.md`.

**`eval_results` is the widest table in the schema — 18 columns.** Every eval run records
the prediction, the gate signals, the deterministic verdict, the judge's verdict, *and*
the human label, side by side on one row. That shape is what makes the kappa analysis
possible at all: agreement between judge and human is a query, not a data-collection
project. The widest table in the schema being the eval table is the project's thesis
expressed as a data model.

---

## `alembic/` — version control for the schema

Four migrations, in order: `initial_schema` → `eval_tables` → `review_decisions` →
`eval_results_golden_view`. You can read the project's history in those names.

**Why not just `Base.metadata.create_all()`?** Because `create_all` only creates tables
that don't exist. It will never add a column to a table that already has rows. The moment
there is data you care about, "make the database match the models" becomes a sequence of
*ordered, reversible steps*, and that sequence has to live in version control next to the
code that expects it.

**Three customizations in `env.py`:**

- `url = os.environ.get("DATABASE_URL") or settings.database_url` — the env var wins, so
  CI can run `alembic upgrade head` against the test branch without touching config.
- `_driver_url(url)` is imported from `triagedesk.db` rather than reimplemented — the
  psycopg3 rewrite rule exists in exactly one place.
- `target_metadata = Base.metadata` — this is what lets `alembic revision --autogenerate`
  diff the models against the live database and draft the migration.

---

## Interview lines from this chunk

- *"Why an ORM?"* — The schema is declared once in typed Python; the app, the migrations,
  and the tests all read the same declaration. The cost is that expensive queries can hide
  behind attribute access, which is why the console's queries are hand-written in
  `console_queries.py` rather than lazy-loaded through relationships.
- *"What's a session?"* — A unit of work. A shopping cart: add, then commit as one
  transaction, or roll the whole thing back.
- *"Why UUIDs for runs?"* — They're in public URLs. Sequential ids leak volume and are
  enumerable.
- *"Tell me about a bug that came from a design choice."* — Naive vs. aware timestamps.
  `created_at` is written by Postgres and is naive; `finished_at` is written by Python and
  is aware. Comparing them raises. It bit the latency calculation and again in the demo
  daily-cap window, and it's documented in the schema doc so the next person hits it once,
  not twice.
- *"How do you enforce one review per run?"* — A unique index on
  `review_decisions.run_id`. The 409 response is the polite version; the constraint is the
  guarantee.
- *"What would you do differently?"* — Put the run states in a database CHECK constraint
  or enum. Right now they're a Python tuple and a comment.
