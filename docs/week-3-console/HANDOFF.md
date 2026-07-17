# RESUME HERE — Week 3 state + how to continue

**Any new session starts with this file.** Last updated: 2026-07-17 (night — **Wk3 Tasks
5 + 7 done, #16 CLOSED**; all Week-3 CODE is merged. The only remaining Week-3 work is
**Task 6: the live deploy — a JOINT session needing Cai's Railway + Vercel accounts**).

> The **operating manual** (environment facts, per-task choreography, budget rules,
> binding decisions, the three standing deliverables) lives in
> [`../week-2-evals/HANDOFF.md`](../week-2-evals/HANDOFF.md) — it all still applies
> verbatim. This file holds only Week 3 state. One fact, one home.

---

## ▶️ NEXT ACTION: Task 6 — the live deploy (issue #15, closes it) — CONTROLLER + CAI

All code is on `main`. This step is a **joint session** (Cai creates/links the accounts;
the controller drives config and verification). Sequence per PLAN.md Task 6:

1. **Cai: create a Railway project** linked to the GitHub repo. Settings:
   - Build: Nixpacks from repo root (NO Docker).
   - Start command: `uvicorn triagedesk.app:app --host 0.0.0.0 --port $PORT --proxy-headers`
     (**`--proxy-headers` matters** — without it the demo rate limiter keys every visitor
     to Railway's proxy IP instead of real client IPs; ledger minor from Task 7 review).
   - Release phase: `alembic upgrade head`.
   - Env vars (values from `credentials.env` / Neon dashboard / choices made live):
     `DATABASE_URL` (Neon — decide with Cai: dev branch vs a fresh prod branch; a prod
     branch is cleaner and cheap), `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`,
     `COST_CAP_USD=0.10`, `ADMIN_TOKEN=<generate a long random string>`,
     `CORS_ORIGINS=<the exact Vercel URL, once known>`, `LOG_JSON=1`,
     `DEMO_DAILY_CAP_USD=1.00`, `DEMO_RATE_LIMIT_PER_HOUR=5`.
2. **Cai: create a Vercel project** with root directory `console/`; env var
   `NEXT_PUBLIC_API_URL=<the Railway URL>`. (Then backfill `CORS_ORIGINS` on Railway
   with the Vercel URL — chicken-and-egg resolved in that order.)
3. Verify `/health` live on the Railway URL.
4. **Seed the prod demo pool** (tickets with `source='demo'` — the pool endpoint serves
   ONLY those; dev has ids 12023/12027/12039 as the model) + at least one completed run
   if feasible (the console's completed-row styling has never rendered real data).
5. Run the smoke script (ONE live run ≈ 3¢):
   `python scripts/smoke.py --base-url <railway-url> --ticket-id <seeded-demo-id>` —
   exit 0 iff terminal state ∈ {completed, escalated} AND cost > 0.
6. Record everything in `docs/week-3-console/reports/task-6-deploy.md`; close #15;
   STORY chapter; ledger. Descope ladder (if overrunning): smoke → JSON logs → rate
   limit; the daily cap is NEVER cut.

## ✅ Verify at session start (30 seconds)

- Gate run **29621157110 confirmed GREEN** (PR #55's merge — the Task 5+7 wave's ONE
  billed run), cost **$0.911** ($0.750 base + $0.161 judge) — in the ledger. Task 5's
  own gate run (29610154311) was cancelled as superseded (~$0), per the batching rule.
  **Nothing is pending at session start** — go straight to the Task 6 checklist above.

## Week 3 state

| Task (plan) | Issue | State |
|---|---|---|
| 1 Runs read API (list + detail) | #13 | ✅ merged `360b1d0` (PR #50), review clean |
| 2 Console scaffold + run list/detail | #13 | ✅ merged `9f41aaa` (PR #51), review clean (1 Important fixed: error boundary) — **#13 CLOSED** |
| 3 review_decisions + queue API + admin token | #14 | ✅ merged `f760367` (PR #52), review clean |
| 4 Console review-queue page | #14 | ✅ merged `4f51143` (PR #53), review APPROVE-WITH-MINORS (1 dead-CSS Minor fixed in-PR) — **#14 CLOSED** |
| 5 Deploy-prep: CORS + JSON logs | #15 | ✅ merged `d1275f7` (PR #54), review APPROVE (1 Important — real-preflight test gap — fixed in-PR, re-review APPROVE); its gate run cancelled as superseded (~$0) |
| 6 Live deploy Railway+Neon+Vercel + smoke — **controller + Cai** (needs his accounts) | #15 | ▶️ **NEXT — the only remaining Week-3 work** (checklist above) |
| 7 Demo protection (pool, rate limit, visible spend-cap pause) + smoke script | #16 | ✅ merged `f37ceec` (PR #55), review APPROVE (2 Importants — cap TOCTOU + limiter race — fixed in-PR with a serialized-dispatch lock, race independently reproduced both ways by the reviewer) — **#16 CLOSED** |

**Plan:** `docs/week-3-console/PLAN.md` (canonical; global constraints at top are binding
— note especially the **gate-cost rule**: `triagedesk/**`/`alembic/**`/`requirements.txt`/
`kb/**`/baseline merges each trigger a ~$0.90 eval-gate run; batch API merges back-to-back
and cancel superseded queued runs, keep only the last; `console/**` and docs are free).
**Descope ladder if the week overruns (cut in order):** smoke test → JSON logs → per-IP
rate limit. The daily spend cap is NEVER cut.

## Budget

≈ **$9.5 of $20** (run 29621157110 finalized at $0.911 — the Task 5+7 wave's one billed
run; Task 5's own run cancelled ~$0; Task 4's merge and all docs $0). Week 3's only
remaining live spend: Task 6's smoke run (~3¢).

## Standing items to fold in when convenient

- Dedicated Neon eval branch (`EVAL_DATABASE_URL` still points at dev).
- Second rater for judge calibration (chore #19) — the kappa bottleneck is single-rater
  label noise, NOT judge quality (see `results/judge-calibration.md`).
- Seed at least one `completed` run before the demo (dev DB currently has zero — the
  console's completed-row styling is code-verified only).
