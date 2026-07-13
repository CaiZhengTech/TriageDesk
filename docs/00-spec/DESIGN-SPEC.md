# TriageDesk — Design Spec

**Date:** 2026-07-10
**Status:** Council-reviewed (3 rounds), pending final user greenlight
**Author:** Cai + Claude (superpowers:brainstorming flow)

---

## 1. What this is and why

TriageDesk is an AI support-ticket triage agent with a "glass-box" ops console: every
run is traced, evaluated, cost-tracked, and — where the stakes require it — routed to a
human review queue. It is a portfolio project targeting Northeast US (NYC/Boston)
new-grad SWE roles for the fall 2026 cycle.

**The differentiator is not the agent. It is the engineering discipline around it.**
Market research (Exa + Firecrawl, 2026-07) found:

- Eval design is the #1 hiring signal for agentic roles; candidates who can say "here
  is my golden set, here is my judge calibration, here is my regression gate" stand out.
- Basic RAG/chatbot demos are table stakes and read as a yellow flag.
- The industry trust gap is real (~29% of developers trust AI output), so demonstrating
  *verification* machinery is the story employers respond to.
- NYC new-grad postings (Secureframe, Giga AI, EliseAI, Cadence) literally list: RAG
  pipelines, multi-step agents, agent observability, agent memory.
- Anthropic's "Building Effective Agents" positions routing workflows as the canonical
  support-ticket pattern and recommends workflow-style control for high-stakes domains —
  TriageDesk deliberately follows this (structured pipeline, not autonomous agent).

**Success criteria:** a deployed demo + public repo + written case study that together
prove: (1) I can build a multi-step LLM pipeline by hand, (2) I can measure it honestly,
(3) I know where autonomy must stop.

## 2. Scope and non-goals

**In scope:** one FastAPI service, one Postgres database, a 5-stage pipeline, a
25-ticket golden set with deterministic metrics + calibrated LLM judge, a minimal
3-page Next.js console, deployment, demo video, case study.

**Explicit non-goals (council-reviewed cuts — do not add back without a reason):**
- LangChain/LlamaIndex or any agent framework (hand-written loop is the interview story)
- Separate vector DB (pgvector suffices), chunking/retrieval tuning
- Contract tests, nightly eval crons, cached-fallback demo mode, dead-letter workflow
- Docker anywhere (Windows friction; Neon test branch + Railway Nixpacks instead)
- Waterfall trace visuals, trends charts, inline editing in the console
- Real OTel export/collector (we borrow the `gen_ai.*` vocabulary, store in Postgres)
- Multi-tenancy, auth beyond a single shared admin token for the review queue

Cut items get one "what I'd add in production" paragraph in the case study.

## 3. Stack (locked)

| Layer | Choice | Why |
|---|---|---|
| API | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic | Dominant agentic-backend stack in postings |
| DB | Postgres on Neon (free tier) + pgvector | One database for rows, vectors, and traces |
| LLM | Anthropic SDK, hand-written loop | No-framework story; pinned model, temp 0 for judge |
| Console | Next.js (App Router) on Vercel, minimal | Thin read layer; the API is the product |
| CI | GitHub Actions | ruff + pytest every push; eval gate on merge-to-main |
| Data | Kaggle "Customer IT Support" (Tobias Bueck) | Real tickets with category/queue labels |
| KB | ~15 short authored help-center docs | Whole-doc embeddings, k=3, no chunking |

## 4. Pipeline architecture

```
ticket → [1 pre-check] → [2 classify] → [3 retrieve] → [4 act loop] → [5 confidence gate]
              ↓ fail            ↓ low margin                ↓ exhausted        ↓ low
           escalate           escalate                  agent_incomplete    review queue
```

1. **Pre-check** — screens prompt injection, PII leakage requests, off-topic input.
   Failures escalate with reason. Eval metric: adversarial catch rate.
2. **Classify** — category + queue via structured output (Pydantic schema; one repair
   re-prompt on validation failure, then escalate).
3. **Retrieve** — pgvector cosine similarity over the ~15 KB docs, k=3, whole-doc.
4. **Act loop** — hand-written tool loop, max 5 iterations. Tools:
   `lookup_account_status`, `check_entitlement` (simulated against seeded data).
   Loop exhaustion → run `escalated` with reason `agent_incomplete` → review queue.
5. **Confidence gate** — multi-signal: retrieval similarity + classification margin
   (NOT the LLM's self-reported confidence, which is unvalidated). Start with these two
   signals; add more only if the Wk2 calibration table shows they help.

**Run states:** `completed | escalated | failed`. Failed runs are visible in the
console with their error reason — no separate triage workflow.

### Non-negotiable design rules
- **Adverse-action rule:** the agent never autonomously delivers a customer-facing
  denial (of access, entitlement, or claim). Adverse outcomes always route to the human
  review queue. Internal rationale is always logged: the trace is evidence, the LLM's
  stated rationale is post-hoc context — useful for review, never ground truth.
- **Fail closed on cost:** per-run cap ~$0.10, computed in the trace layer from token
  counts. If cost cannot be computed, treat as a breach → escalate.

## 5. Data model (7 tables)

| Table | Purpose |
|---|---|
| `tickets` | Ingested Kaggle tickets + demo-pool tickets |
| `runs` | One pipeline execution; state machine; append-only; records prompt version |
| `spans` | Incremental writes per stage; OTel GenAI attribute names (`gen_ai.*`) |
| `kb_docs` | Authored help-center docs + pgvector embeddings |
| `eval_cases` | The 25-ticket golden set (5 adversarial) with expected outcomes |
| `eval_results` | Per-case metric outcomes per eval run (CI history) |
| `review_decisions` | Human approve/reject on the review queue, with reviewer note |

Human calibration labels for the judge live in `eval_cases` (expected outcome +
human-labeled verdicts) rather than an eighth table.

## 6. Evals (the heart of the project — built Week 2, designed first)

- **Golden set:** 25 tickets — 20 representative (stratified across dataset queues) +
  5 adversarial (injection, PII bait, off-topic, ambiguous, entitlement-denial trap).
- **Deterministic metrics (primary):** routing accuracy, escalation precision/recall,
  adversarial catch rate, cost per run, p50/p95 latency, confidence-calibration table
  (gate signal vs. actual correctness by bucket).
- **LLM-as-judge (secondary):** pinned model, temperature 0, binary pass/fail plus
  `needs_review` third label; structured verdict `{verdict, reason, rule_triggered}`.
  Calibrated against ~40–50 solo human labels; report Cohen's kappa. Judge explanations
  are debugging aids, not ground truth.
- **CI gate:** eval suite runs on merge to main, ~$1 cap per run, tolerance band on
  judge-based metrics (deterministic metrics are exact).
- **Kill criterion:** if the eval gate is not green by end of Week 2, the console is
  cut to a single read-only page and the remaining time goes to the pipeline + evals.

## 7. Error handling (built inline during Weeks 1–2, one-touch)

- API errors 429/5xx: exponential backoff, max 3 retries / 60s total, then run → `failed`.
- Structured-output validation: Pydantic + exactly one repair re-prompt, then escalate.
- Tool errors: retry once, then escalate.
- Budget: per-run cost cap ~$0.10, fail-closed (see design rules).
- Spans written incrementally (a crash mid-run still leaves a partial trace).
- `runs` append-only; every run records the prompt version that produced it.

## 8. Testing strategy

| Layer | Runs | Details |
|---|---|---|
| Unit | every push | Mocked LLM (recorded real responses as mock data); pipeline logic, gate math, cost calc |
| Integration | every push | FastAPI TestClient against a **Neon test branch** (no Docker, locally or in CI) |
| Eval suite | merge to main | Golden set, $1 cap, tolerance band |
| Smoke | post-deploy | One scripted run against prod healthcheck + a seeded ticket |
| Static | every push | ruff + type checking in Actions |

Deliberately absent: contract tests, nightly evals (council cuts — 4-week shelf life,
pinned model, merge-gate coverage is sufficient).

## 9. Deployment

- API on Railway (Nixpacks build straight from the repo — no Dockerfile), DB on Neon,
  console on Vercel. Alembic migrations run on deploy. `/health` endpoint. CORS locked
  to the Vercel origin. Structured JSON logs.
- Secrets: env vars only; local dev reads `C:\Users\Wonton Soup\.secrets\credentials.env`;
  repo carries `.env.example`; .gitignore verified before first commit.
- **Demo abuse protection:** visitors run tickets from a seeded pool only (no free-text
  to the LLM), per-IP rate limit, hard daily spend cap that **visibly pauses the demo**
  ("Daily demo budget reached — watch the video instead"). No silent cached fallback.

## 10. Console (Week 3, minimal by design)

Three pages: run list → run detail (flat trace table: stage, duration, tokens, cost,
status) → review queue (approve/reject with note; adverse-action items land here).
Failed runs appear in the run list with error reason.

## 11. Build plan (4 weeks, part-time, ~45–50h — top of budget)

- **Wk1 — pipeline skeleton:** all 5 stages wired end-to-end (crude prompts fine),
  incremental span writes, run state machine, error handling built inline (retries,
  cost cap, repair re-prompt), CLI trace dump, ~15 KB docs authored + embedded, dataset
  ingested, friend asked for labeling favor (off critical path).
- **Wk2 — evals:** golden set, deterministic metrics + calibration table, judge +
  calibration (~40–50 solo labels, Cohen's kappa), CI eval gate. **Kill criterion
  checked at end of week.**
- **Wk3 — console + deploy:** 3 console pages, Railway + Neon + Vercel, smoke test,
  demo protection. **Descope ladder if overrunning:** cut smoke test → cut JSON logs →
  cut per-IP rate limit (spend cap always stays).
- **Wk4 — buffer + story:** demo video, written case study (metrics, failure analysis,
  "what I'd add in production" paragraph covering the deliberate cuts).

## 12. Development process (issue-driven)

- This spec → superpowers:writing-plans, **one plan per week/phase** (right-sized for
  review), written just before that phase begins.
- The full project is decomposed into **GitHub issues up front** (one issue per
  right-sized task: goal, acceptance criteria, files touched, dependencies, week label).
  Issues are the tracking layer; plan docs remain canonical for implementation detail.
- Implementation goes issue-by-issue: branch → TDD → PR referencing the issue → human
  review → merge closes the issue. Commit history narrates the build.
- superpowers discipline throughout: TDD, code review, verification before completion;
  `how-we-got-here` fires after backend/AI-ML/infra work.

## 13. Council review history

- **Round 1 (scope/architecture):** caught "five projects stapled together" risk →
  evals-first ordering, golden set 75→25, kill criterion in writing, console cuts.
- **Round 2 (pipeline):** caught nonexistent-KB assumption (→ author ~15 docs), tool/
  domain mismatch (→ `lookup_account_status`/`check_entitlement`), unvalidated
  confidence signal (→ multi-signal gate + calibration table), undefined loop
  exhaustion (→ `agent_incomplete`), missing pre-check metric (→ adversarial catch
  rate), external dependency on kill-criterion week (→ friend favor off critical path).
- **Round 3 (error handling/testing/deploy):** cut contract tests, nightly evals,
  cached fallback, Docker; adopted one-touch sequencing (error handling built inside
  Wk1–2); added fail-closed cost rule and the Wk3 descope ladder.
