# RESUME HERE — Week 4 state + how to continue

**Any new session starts with this file.** Last updated: 2026-07-21 — **#56
and #58 both CLOSED, merged to `main`, deployed and verified live.**
Console: https://triage-desk-xi.vercel.app · API:
https://agenticproject-production.up.railway.app.

> The **operating manual** (environment facts, per-task choreography, budget
> rules, binding decisions) lives in
> [`../week-2-evals/HANDOFF.md`](../week-2-evals/HANDOFF.md) — still applies
> verbatim. Week 3 deploy facts: [`../week-3-console/HANDOFF.md`](../week-3-console/HANDOFF.md).
> This file holds only Week 4 state.

---

## 🚨 CURRENT STATE (2026-08-19): the database was lost and rebuilt-able, the API is down

Three linked failures, in the order they must be fixed.

### 1. Neon free-tier branches EXPIRED — the database is gone (issue #64)

Neon expires idle branches on the free tier. Both `prod` and `test` were
garbage-collected. The replacements are **new endpoints and were completely
empty** — no tables, no `pgvector`. Lost: schema, 11,922 tickets, KB
embeddings, all eval cases, all run history.

This is the real root cause of the `password authentication failed` errors
that looked like a rotated password: the stored connection strings pointed at
endpoints that no longer existed.

**Done:** `TEST_DATABASE_URL` refreshed + migrated + secret updated, CI green
again. `scripts/bootstrap.py` now rebuilds an empty database in one command.

**Still to do:** run `python -m scripts.bootstrap` against the new prod branch.

**Survived:** the 41 human labels (both rounds) in `judge_labels.csv` /
`judge_labels_v2.csv`, `results/`, the centroids, and every report. The
headline numbers are still evidenced by committed artifacts — only the
console's ability to *display* traces was lost.

### 2. Railway paused the service — the API 404s (issue #60)

Railway's permanent free tier ended in 2023; the Week-3 deploy used the 30-day
trial, which expired. Migration target chosen: **Northflank** free tier
(always-on, buildpacks, no Docker). Full runbook is in the #60 comments.
`Procfile` + `.python-version` are now committed (#63) so the start command
lives in the repo instead of a dashboard field.

The console no longer 500s while the API is down — the landing page degrades
to its static half (#63).

### 3. `EVAL_DATABASE_URL` still points at a dead endpoint (issue #61)

The old finding — that the eval-gate wrote 25 golden-set runs into the
production database — is now moot in practice, because that database no longer
exists. The **fix is still required**: point the secret at a dedicated eval
branch before the next eval-path merge, or the same contamination recurs on the
rebuilt prod.

### The lesson that keeps repeating

Railway's start command, the demo pool, and two golden cases were all lost the
same way: **they lived outside version control.** #63 and #64 move all three
into the repo. Before adding any new deploy or seed step, ask where it lives if
the machine holding it disappears tonight.

## Week 4 progress

| Item | Issue | State |
|---|---|---|
| Console redesign — flight-recorder identity, dark-only, cockpit-stack landing | #56 | ✅ merged `b66aa78` (PR #57, squash) — **CLOSED**, `console/**`-only, $0 gate |
| Live run progress — demo watches the pipeline execute; backend moved to `BackgroundTasks` | #58 | ✅ merged `cb69291` (PR #59, squash) — **CLOSED**, touches `triagedesk/**` ⇒ eval-gate fired, **PASSED**, $0.879 |
| Post-merge polish (not separately issued, same PR #59 branch before merge) | — | ✅ typed-headline rotation bugfix + dynamic height, one-stage-at-a-time lifecycle pulse (was trailing), expandable run/review cards, page transitions, Home nav, GitHub repo links, readable agent-reply prose (`white-space: pre-wrap` + bold) |
| Demo video | #17 | not started |
| Case study + `results/` + final README | #18 | not started |

**Deferred, tracked verbally (not yet an issue):** seed one demo-pool ticket
that's genuinely auto-resolvable (KB-answerable, no denial), to prove the
gate *can* auto-resolve rather than always escalating — every current
demo-pool ticket is deliberately adverse-action-shaped by design, so 100%
escalation there is correct behavior, not a defect. Open as an issue before
acting on it (council/golden-set discipline applies — no hand-tuning the
gate).

## 🌐 Live deployment facts (re-verified 2026-07-21, after PR #59 merge)

| Thing | Value |
|---|---|
| Console | https://triage-desk-xi.vercel.app — confirmed serving the new build (`/runs`, `/demo` 200; landing markup includes the new "Lifecycle" panel + GitHub source link) |
| API | https://agenticproject-production.up.railway.app — `GET /api/runs` and `GET /api/demo/pool` both 200 |
| CI on `main` | `ci` ✅ success · `eval-gate` ✅ success (PASSED, $0.879) — both on merge commit `cb69291` |
| DB | Neon `prod` branch — **also currently receiving eval-gate golden-set runs, see finding above** |

## Budget

Week-3 close was **≈$9.6 of $20**. Since then:
- PR #57 (#56): $0 (console/docs-only, no gate).
- PR #59 (#58) eval-gate: **$0.879** (`$0.719022` eval + `$0.160035` judge),
  confirmed from the CI log, gate **PASSED**.
- Demo-pool verification runs this session (mislabeled "dev branch" in the
  task report — see correction): **8 runs, $0.3007 exact** (queried from
  prod `/api/runs`, 2026-07-19T08:29 through 2026-07-20T19:59, the 25
  golden-set runs excluded by timestamp window).
- **Running total: $9.6 + $0.879 + $0.3007 ≈ $10.78 of $20.** The 25
  golden-set eval runs' $0.879 is already counted via the eval-gate line —
  don't double-count it if re-deriving from prod's raw run list.

## ✅ Verify at session start (30 seconds)

- `curl https://agenticproject-production.up.railway.app/api/runs?limit=1` →
  200 with a run. If down, check Railway deployments (failed pre-deploy
  migration is the usual cause after a schema change — none happened this
  week, so unlikely).
- `gh run list --branch main --limit 2` → both `ci` and `eval-gate` (if
  triggered) should read `success`.
- Read the eval-gate finding above before running any eval-path merge again.
