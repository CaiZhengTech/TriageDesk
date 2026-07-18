# Task 6 — Live deploy: Railway + Neon + Vercel + smoke (issue #15)

**Date:** 2026-07-17/18 (joint session: Cai drove the browser consoles, controller drove
config, verification, and the smoke run). **Result: LIVE and smoke-verified.**

## The URLs

| Thing | URL |
|---|---|
| API (Railway) | https://agenticproject-production.up.railway.app |
| Console (Vercel) | https://triage-desk-xi.vercel.app |
| Health | `GET /health` → `{"status":"ok"}` |

## What was stood up

1. **Neon `prod` branch**, branched off dev (Cai's choice from the two options; copy-on-write).
   This carried ALL data for free: 11,922 tickets, the 15 KB docs with embeddings, the
   demo pool (`source='demo'`: 12023, 12027, 12039), and the real run history — so the
   console had honest data to show from the first page load, and the planned "seed the
   prod demo pool" step disappeared.
2. **Railway service** from the GitHub repo:
   - Builder: **Railpack** (v0.31.1) — *deviation from the plan's "Nixpacks"*: Railway has
     since made Railpack (Nixpacks' successor) the default. Same property the council
     cared about — build-from-source, NO Docker — so we followed the platform default
     rather than pinning a deprecated builder.
   - Start command: `uvicorn triagedesk.app:app --host 0.0.0.0 --port $PORT --proxy-headers`
     (`--proxy-headers` so the demo rate limiter keys real client IPs, not Railway's proxy —
     the Task-7 review's deploy TODO, closed).
   - Pre-deploy: `alembic upgrade head` (no-op on the copied branch — `alembic_version`
     came across at head — but wired for every future deploy).
   - Healthcheck path: `/health` (Railway now gates each deploy on the API actually answering).
   - Env vars: `DATABASE_URL` (Neon prod), `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`,
     `COST_CAP_USD=0.10`, `ADMIN_TOKEN` (fresh random token, stored in Cai's
     credentials.env), `LOG_JSON=1`, `DEMO_DAILY_CAP_USD=1.00`,
     `DEMO_RATE_LIMIT_PER_HOUR=5`, `CORS_ORIGINS=https://triage-desk-xi.vercel.app`.
     (`TEST_DATABASE_URL` was also set — unused at runtime, harmless; can be removed.)
3. **Vercel project**, root directory `console/`, `NEXT_PUBLIC_API_URL=<railway url>`.
4. **CORS backfill** on Railway once the Vercel URL existed (the designed order — the API
   ran fail-closed, zero cross-origin access, until the console's exact origin was known).

## Incidents (both small, both instructive)

- **First build failed: "No start command detected."** Railpack (unlike the old Nixpacks
  FastAPI heuristic) requires the explicit start command; it had also guessed
  `npm run start` from the nested `console/package.json`. Setting the uvicorn start
  command fixed it. Python version pin was NOT needed (Railpack resolved a working
  Python; `NIXPACKS_PYTHON_VERSION` would have been a no-op under Railpack).
- **CORS preflight rejected after deploy: "Disallowed CORS origin."** The configured
  value had a trailing slash (`.../` — what the address bar gives you when copying), and
  origin matching is exact-string. The 400-not-405 signature was itself diagnostic: it
  proved the middleware WAS registered and rejecting, not absent. Removing the slash
  fixed it. This is the CORS twin of the Week-2 tz gotcha — worth remembering.

## Verification evidence (all observed live, in order)

1. `GET /health` → `{"status":"ok"}`.
2. `GET /api/runs?limit=2` → real run history served from the prod branch.
3. `GET /api/demo/pool` → exactly the three `source='demo'` tickets.
4. `POST /api/review/{uuid}` with a wrong token → **401** (the operator lock is live and
   failing closed; a missing-token config would have been 503).
5. Browser-real CORS preflight (`OPTIONS /api/review/{uuid}`, Origin = the Vercel URL,
   method POST, headers `X-Admin-Token, Content-Type`) → **200**, origin echoed,
   methods `GET, POST, OPTIONS`, headers include `X-Admin-Token`, max-age 600.
6. Same preflight from `https://evil.example.com` → **400 "Disallowed CORS origin"**, no
   allow-origin header (fail closed for everyone but the console).
7. All three Vercel pages render 200; the run list shows the real data (202 escalated
   runs, 18 adverse-action at time of check).
8. **Smoke run** (`scripts/smoke.py --base-url <railway> --ticket-id 12027`, Dana's VPN
   ticket): `run_id=41a3486e-f415-46ca-9278-1de40d5410a7 state=escalated cost=0.035529`,
   **exit 0** — full pipeline through the deployed stack, ~3.6¢, every stage traced,
   correctly escalated to the review queue.

## Descope ladder

**Nothing was cut.** Smoke test ran, JSON logs are on, the rate limit is live. The daily
spend cap (never cuttable) is live and was verified fail-closed in Task 7's tests.

## Known footnotes carried forward

- Prod (like dev) has **zero completed runs** — the smoke run escalated, as the
  conservative system is expected to. The console's completed-row styling remains
  code-verified only. This is the honest state of the system, not a deploy gap.
- The demo pool shows two tickets with the same subject (12023/12027 both "My VPN keeps
  disconnecting") — cosmetic; candidates for a nicer pool in the #56 polish pass.
- Console UI polish deliberately deferred → issue #56.
