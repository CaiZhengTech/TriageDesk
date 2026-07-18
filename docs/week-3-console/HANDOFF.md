# RESUME HERE — Week 3 state + how to continue

**Any new session starts with this file.** Last updated: 2026-07-18 — **WEEK 3 IS
COMPLETE. The system is LIVE:** console https://triage-desk-xi.vercel.app · API
https://agenticproject-production.up.railway.app (deploy record:
`reports/task-6-deploy.md`). **#13/#14/#15/#16 all CLOSED.** Next: Week 4 (#17 demo
video → #18 case study; #56 console polish as stretch).

> The **operating manual** (environment facts, per-task choreography, budget rules,
> binding decisions, the three standing deliverables) lives in
> [`../week-2-evals/HANDOFF.md`](../week-2-evals/HANDOFF.md) — it all still applies
> verbatim. This file holds only Week 3 state. One fact, one home.

---

## ▶️ NEXT ACTION: Week 4 — #17 (demo video) then #18 (case study + results/ + README)

Per the standing plan (operating manual, bottom section): the **adversarial catch rate
is the standalone headline number**; every deliberate cut gets a "what I'd add in
production" paragraph; the fail-closed/all-escalate finding is the approved opening
narrative. Stretch (fit before #17 if schedule allows, else skip): **#56 console UI
polish** — `console/**`-only ⇒ $0 gate. When #17's video URL exists, wire it into the
demo page's pause-banner placeholder (one-line console change, $0).

## 🌐 Live deployment facts (Task 6, 2026-07-18)

| Thing | Value |
|---|---|
| Console | https://triage-desk-xi.vercel.app (Vercel, root `console/`) |
| API | https://agenticproject-production.up.railway.app (Railway, Railpack builder — NOT Nixpacks, deprecated; still no-Docker) |
| DB | Neon **`prod` branch** (branched off dev — carried all data incl. demo pool 12023/12027/12039) |
| Start cmd | `uvicorn triagedesk.app:app --host 0.0.0.0 --port $PORT --proxy-headers` + pre-deploy `alembic upgrade head` + healthcheck `/health` |
| CORS | exactly `https://triage-desk-xi.vercel.app` — **NO trailing slash** (exact-string match; the slash cost us a debug loop) |
| Admin token | in Cai's `credentials.env` (`ADMIN_TOKEN`) — used in the review page's operator field |
| Smoke run | `41a3486e` escalated, $0.0355, exit 0 (Dana's 12027) — full record: `reports/task-6-deploy.md` |
| Demo guards | live: $1/day cap (fail-closed pre-check), 5/hr/IP, pool-only |

## ✅ Verify at session start (30 seconds)

- `curl https://agenticproject-production.up.railway.app/health` → `{"status":"ok"}` and
  the console loads with the run list. If the API is down, check Railway deployments
  first (a failed pre-deploy migration is the likely culprit after any schema change).
- No pending gate runs; last billed: 29621157110 GREEN $0.911 (ledger).

## Week 3 state

| Task (plan) | Issue | State |
|---|---|---|
| 1 Runs read API (list + detail) | #13 | ✅ merged `360b1d0` (PR #50), review clean |
| 2 Console scaffold + run list/detail | #13 | ✅ merged `9f41aaa` (PR #51), review clean (1 Important fixed: error boundary) — **#13 CLOSED** |
| 3 review_decisions + queue API + admin token | #14 | ✅ merged `f760367` (PR #52), review clean |
| 4 Console review-queue page | #14 | ✅ merged `4f51143` (PR #53), review APPROVE-WITH-MINORS (1 dead-CSS Minor fixed in-PR) — **#14 CLOSED** |
| 5 Deploy-prep: CORS + JSON logs | #15 | ✅ merged `d1275f7` (PR #54), review APPROVE (1 Important — real-preflight test gap — fixed in-PR, re-review APPROVE); its gate run cancelled as superseded (~$0) |
| 6 Live deploy Railway+Neon+Vercel + smoke — **controller + Cai** | #15 | ✅ **LIVE 2026-07-18** — smoke exit 0 ($0.0355); nothing descoped; 2 incidents (Railpack start cmd, CORS trailing slash) in `reports/task-6-deploy.md` — **#15 CLOSED, WEEK 3 COMPLETE** |
| 7 Demo protection (pool, rate limit, visible spend-cap pause) + smoke script | #16 | ✅ merged `f37ceec` (PR #55), review APPROVE (2 Importants — cap TOCTOU + limiter race — fixed in-PR with a serialized-dispatch lock, race independently reproduced both ways by the reviewer) — **#16 CLOSED** |

**Plan:** `docs/week-3-console/PLAN.md` (canonical; global constraints at top are binding
— note especially the **gate-cost rule**: `triagedesk/**`/`alembic/**`/`requirements.txt`/
`kb/**`/baseline merges each trigger a ~$0.90 eval-gate run; batch API merges back-to-back
and cancel superseded queued runs, keep only the last; `console/**` and docs are free).
**Descope ladder if the week overruns (cut in order):** smoke test → JSON logs → per-IP
rate limit. The daily spend cap is NEVER cut.

## Budget

≈ **$9.6 of $20** at Week-3 close (wave gate run $0.911 + smoke run $0.0355; Task 5's
own gate run cancelled ~$0). Week 4 is docs/video — near-$0 API spend expected, EXCEPT:
each public demo run costs ~3.5¢ against the demo's own $1/day cap (that's the demo
budget working, not a leak), and any eval-path merge still bills the ~$0.90 gate.

## Standing items to fold in when convenient

- Dedicated Neon eval branch (`EVAL_DATABASE_URL` still points at dev).
- Second rater for judge calibration (chore #19) — the kappa bottleneck is single-rater
  label noise, NOT judge quality (see `results/judge-calibration.md`).
- Seed at least one `completed` run before the demo (dev DB currently has zero — the
  console's completed-row styling is code-verified only).
