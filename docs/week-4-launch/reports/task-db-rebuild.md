# Reproducible database rebuild (issue #64)

**What happened:** Neon's free tier expires idle branches. Both `prod` and `test` were
garbage-collected, taking the whole database with them — schema, 11,922 tickets, the KB
embeddings, every eval case, and all run history. The replacement branches are new
endpoints and were completely empty (no tables, no `pgvector`).

This was the true root cause behind the #60 symptoms. The `password authentication
failed` errors seen from two machines against two branches were not a rotated password;
they were connection strings pointing at endpoints that no longer existed.

**What this task delivers:** not "the data, restored" — the *ability* to restore it. The
branches will expire again.

### Correction, caught by CI

The first version of this work claimed a rebuild "from the repo alone." **That was
wrong**, and CI proved it: `test_every_representative_case_is_rebuildable_from_the_repo`
failed on the runner with `FileNotFoundError` on the ticket CSV.

The corpus is a **separate, gitignored HuggingFace clone** — `Tobi-Bueck/customer-support-tickets`,
pinned at `ddf1c81`, ~19 MB, CC-BY-NC-4.0. Correctly not committed (size and licence
both argue against it), but it means the honest claim is "**this repo plus one pinned
external dataset**."

That distinction has teeth. Ticket ids are the insertion order of the rows surviving the
ingest filter, so **a different dataset revision silently renumbers every ticket** and
invalidates `golden_expectations.json` without any error. `bootstrap.py` now checks the
clone exists before touching the database, and the deep test asserts the row count is
still 11,922 before trusting a single id.

It is also, precisely, a *fifth* instance of the finding below — external state the
rebuild depends on. The difference is that this one is legitimately external; what was
missing was it being *written down*.

---

## The real finding: state that lived outside the repo

Three things could not be rebuilt, and all three failed for the same reason.

| Lost | Why it was unrecoverable |
|---|---|
| Railway's start command | Typed into a dashboard field during the Week-3 deploy, never committed. Died with the paused service. Fixed in #63 (`Procfile`). |
| The demo pool (12023/12027/12039) | Created by hand in a Neon dev branch; reached prod only because prod was cut copy-on-write from dev. `task-6-deploy.md` records the moment the planned "seed the prod demo pool" step was skipped *because branching had already carried the rows*. No script ever existed. |
| Golden cases 12027, 11964 | Hand-inserted above the Kaggle ingest range. `task-9` describes inserting *filler tickets* by hand to steer `id % 12` onto the right account — a manual step that left no trace in code. |

The pattern is one sentence: **configuration and seed data that live outside version
control are not real.** They survive exactly as long as the machine holding them.

---

## What survived, verified rather than assumed

| Asset | Verification |
|---|---|
| Schema | 4 Alembic migrations, incl. `CREATE EXTENSION IF NOT EXISTS vector`. Replayed cleanly onto the empty test branch. |
| 11,922 Kaggle tickets | Replaying `row_to_ticket`'s filter over the source CSV offline yields **exactly 11,922** rows — matching the recorded count. |
| 18 of 20 golden cases | Same offline replay puts **18/20 golden ids on their recorded `expected_queue`, with zero mismatches.** The ingest is genuinely deterministic. |
| 5 adversarial cases | Pinned ids + full text in `triagedesk/evals/adversarial.py`. |
| Queue centroids | `triagedesk/data/queue_centroids.json`, committed. No recompute needed. |
| **41 human labels × 2 rounds** | `judge_labels.csv` / `judge_labels_v2.csv`, **41/41 filled in each**. The only asset that cost human hours was never at risk. |
| All analysis | `results/judge-calibration.md`, `results/eval-baseline.json`, every `reports/` file. |

The headline numbers on the README and PITCH remain evidenced: they are backed by
committed artifacts, not by rows in a database. What was lost is the console's ability to
*display* the traces behind them.

---

## What was built

### `triagedesk/demo_pool.py` — the pool as data in version control

Four authored tickets, pinned ids in the **80000+** band (above the 11,922 ingest range,
clear of adversarial's 90000+). The redesign was forced by the loss, so it also closes
#62 — the pool now demonstrates both gate exits instead of only escalation:

| id | Customer | Plan | Scenario | Intent |
|---|---|---|---|---|
| 80007 | Dana Fuentes | basic | VPN drops, client demo at 3pm | escalate — `priority_vpn_support` not covered |
| 80010 | Morgan Lee | **pro** | Same VPN complaint | **auto-resolve** — same feature, covered |
| 80011 | Taylor Brooks | basic | Locked out after failed logins | **auto-resolve** — `standard_support` is Basic-inclusive |
| 80019 | Dana Fuentes | basic | Requests a dedicated IP | escalate — `dedicated_ip` is Enterprise-only |

**80007 and 80010 are the demo's whole argument in one screen:** the same question, the
same agent, two plans, two different exits. Dana's canon is untouched — she stays basic,
and the auto-resolving counterpart is a colleague, rather than rewriting her account to
make the demo look good.

`expected_gate_outcome` records **design intent, not a promise.** Nothing here tunes the
gate; no threshold, prompt, or rule was touched. If a ticket marked `auto_resolve` still
escalates in a live run, that is a finding to write up, not a knob to turn.

### `scripts/seed_demo_pool.py`

Idempotent delete-then-reinsert at pinned ids, the same precedent as
`seed_adversarial_tickets()`. Fails closed when runs exist for a pooled ticket
(`--reset-history` to override), because those runs are the trace evidence the console
displays.

It also re-checks the id→customer mapping at seed time. `customer_ref_for` is `id % 12`,
so an id silently selects whose **plan** the act loop reads. A drifted id still runs
fine and quietly tests a different scenario — the loudest possible failure is the right
one here.

### `scripts/bootstrap.py`

One command, empty Postgres to fully seeded: migrations → ingest → KB embeddings → demo
pool → golden set → calibration pool. Refuses to run against a database that already has
tickets unless `--force`, and `--dry-run` prints the plan without touching anything.

**It deliberately does not recreate run history.** Traces are records of real executions;
re-running the pipeline costs real money. That stays an explicit, separate decision.

### Golden-set repair

12027 and 11964 were replaced with Kaggle tickets drawn deterministically from the same
queues — `random.Random(20260818).choice(sorted(candidates))`, excluding ids already in
the file. Provenance is recorded in each row's `notes`.

| Out | In | Queue | Outcome |
|---|---|---|---|
| 12027 | **5803** | IT Support | `escalate` — reported unauthorized access to medical data |
| 11964 | **4475** | Human Resources | `escalate` — Enterprise-only integrations, delinquent Pro account |

**Both orphans were already `escalate`, and all three `route` cases (565, 4646, 2342) sit
inside the reproducible range — so the 17/3 balance is preserved exactly.** That matters:
escalation *precision* is only measurable against cases that should route, and a set that
drifts to zero route cases makes "escalation recall 1.0" a tautology again, which is
precisely the Week-2.5 council's complaint.

4475 was kept despite its dataset queue label ("Human Resources") plainly contradicting
its technical content. That mismatch is a concrete, pointable instance of the taxonomy
noise behind the documented 0.29 routing accuracy. Swapping it for a tidier ticket would
have quietly flattered the routing number.

---

## Honest consequence: the baseline is no longer like-for-like

Two of 25 golden cases changed. `results/eval-baseline.json` was derived from the old
membership, so it is **not** a valid regression floor against the new set. It must be
re-derived on the next golden run, and the case study should say so plainly rather than
presenting a continuous history that isn't.

---

## Tests

21 new (249 total, up from 228), all passing, `ruff` clean.

- `tests/unit/test_demo_pool.py` (11) — ids above the ingest range, no collision with the
  adversarial band, **every pinned id resolves to its intended customer**, both gate
  outcomes represented, and each scenario's entitlement evidence agrees with its stated
  intent (an `auto_resolve` ticket's plan must *cover* its feature; an escalate-on-
  entitlement ticket's must not).
- `tests/unit/test_bootstrap.py` (6) — ordering is the claim worth testing: migrations
  first, ingest before anything referencing a ticket id, calibration pinned to
  `--seed-only` so a rebuild never silently triggers ~$0.90 of live spend, and no step
  destructive by default.
- `tests/integration/test_seed_demo_pool.py` (4) — idempotency, visibility to the
  `source='demo'` pool query, the fail-closed guard when runs exist, and `--reset-history`.
- `tests/unit/test_golden_set.py` (+3) — **the regression that prevents a recurrence**,
  deliberately in two layers. The cheap invariant (no golden id above the 11,922 ingest
  range) needs no dataset and therefore runs in CI — it is exactly the check that would
  have caught 12027 and 11964 years earlier. The deep check (every id recreates at the
  same id *and* queue, and the corpus still yields 11,922 rows) skips where the gitignored
  dataset clone is absent. A guard that only runs on one laptop is the same class of
  problem as seed data that only exists on one, so the important half runs everywhere.
  The 17/3 outcome balance is pinned too.

---

## Also found

The Neon **test branch is shared mutable state between CI and local dev.**
`tests/conftest.py:22` runs `TRUNCATE … RESTART IDENTITY CASCADE` after every integration
test. A CI run triggered by merging #63 wiped 11,922 locally-ingested rows mid-verification,
which is how the offline replay method got adopted instead. A per-run schema or a
disposable branch would be the real fix; noted, not fixed here.

Relatedly, CI's `test` job runs `alembic upgrade head` against a live Neon branch *before*
`pytest`, so 223 database-free unit tests cannot run when an external free-tier service is
unreachable. Splitting unit from integration jobs would let CI fail honestly instead of
all-red.
