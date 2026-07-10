# TriageDesk — Project CLAUDE.md

AI support-ticket triage agent with a "glass-box" ops console. Portfolio project targeting
Northeast US (NYC/Boston) new-grad SWE roles, fall 2026 cycle. The differentiator is NOT the
agent — it's the eval/observability/trust discipline around it (market research: eval design
is the #1 hiring signal; plain RAG demos are a yellow flag).

## Current phase
Design complete and spec written: `docs/superpowers/specs/2026-07-10-triagedesk-design.md`
(3 design sections, each llm-council-reviewed; research saved to vault as
`raw/2026-07-10-agentic-portfolio-market-research.md`, awaiting SCREEN → INGEST).
Process: issue-driven — full project decomposed into GitHub issues up front (tracking
layer); superpowers:writing-plans produces one detailed plan per week/phase just-in-time
(canonical layer); implement issue-by-issue with TDD + PRs.

## Locked stack (do not relitigate)
- Python / FastAPI / SQLAlchemy 2.0 / Alembic
- Postgres on Neon free tier, pgvector extension (NO separate vector DB)
- Hand-written agent loop on the Anthropic SDK — deliberately NO LangChain (interview story)
- Thin Next.js console on Vercel; API deployed on Railway via Nixpacks (NO Docker anywhere —
  Windows/WSL2 friction; integration tests hit a Neon test branch, locally and in CI)
- GitHub Actions CI; Kaggle "Customer IT Support" dataset (Tobias Bueck); ~15 authored KB docs,
  whole-doc embeddings, k=3, no chunking/tuning

## Architecture (summary — spec is the full record)
Pipeline: pre-check → classify → retrieve (pgvector) → act loop (tools:
`lookup_account_status`, `check_entitlement`) → multi-signal confidence gate → auto-resolve /
escalate to human review queue. Run states: completed | escalated | failed (failed runs are
simply visible in the console — no dead-letter workflow). Traces use OTel GenAI semantic
conventions (`gen_ai.*` names) stored in hand-rolled Postgres tables.

## Non-negotiable design rules
- **Adverse-action rule:** the agent never autonomously delivers a customer-facing denial;
  those always route to the review queue. Internal rationale is always logged (trace =
  evidence, LLM rationale = post-hoc context, never ground truth).
- **Fail closed on cost:** if the trace layer can't compute a run's cost, treat it as a
  budget breach → escalate. Per-run cap ~$0.10.
- **Evals-first build order.** Judge: pinned model, temp 0, binary + `needs_review`,
  calibrated vs ~40-50 human labels (Cohen's kappa).
- Retries: 429/5xx, backoff, max 3 / 60s. Pydantic validation + ONE repair re-prompt.
  Tool errors: once, then escalate. Loop exhaustion → escalated, reason `agent_incomplete`.

## 4-week plan (part-time, ~45-50h total — top of budget, respect the ladders)
- **Wk1:** full pipeline skeleton + incremental span writes + error handling built inline
  (one-touch: retries, budget cap, run states) + CLI trace dump + 15 KB docs + send friend
  the labeling request
- **Wk2:** 25-ticket golden set (5 adversarial) + deterministic metrics (routing accuracy,
  escalation P/R, adversarial catch rate, confidence-calibration table, cost/latency) +
  judge calibration + CI eval gate on merge-to-main ($1 cap). **Kill criterion: gate not
  green by end of Wk2 → console cut to one read-only page.**
- **Wk3:** minimal console (run list, run detail flat trace table, review queue
  approve/reject) + deploy (Railway + Neon + Vercel, healthcheck, CORS locked). Demo
  protection: seeded ticket pool + per-IP rate limit + hard daily spend cap that VISIBLY
  pauses the demo (no silent cached fallback).
- **Wk4:** buffer + demo video + written case study (include one "what I'd add in
  production" paragraph covering deliberate cuts: contract tests, nightly evals, real OTel
  export, cached fallback).
- **Wk3 descope ladder (in order):** cut post-deploy smoke test → cut structured JSON logs →
  cut per-IP rate limit (spend cap always stays).

## Testing
Unit (mocked LLM, every push) + integration (FastAPI TestClient vs Neon test branch, every
push) + eval suite (merge-to-main only) + one post-deploy smoke test. NO contract tests,
NO nightly cron (council-reviewed cuts — recorded real responses live on as unit mock data).

## Working conventions (this project)
- Superpowers SDLC: plan before code, TDD, code review. Fire `how-we-got-here` after any
  backend/API/DB/AI-ML/infra work.
- Secrets: `C:\Users\Wonton Soup\.secrets\credentials.env` only; verify .gitignore before
  any commit; `.env.example` documents required vars.
- Durable learnings → vault raw source (`raw/YYYY-MM-DD-<slug>.md`) → SCREEN → INGEST.
- Scope discipline: this design survived three council reviews that specifically hunted
  over-engineering. Before adding anything, check it against the hour budget and ladders.
