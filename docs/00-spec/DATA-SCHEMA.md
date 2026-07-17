# TriageDesk — Data Schema Reference

**The single source of truth for table and column names.** Read this before writing any
query. Generated from `triagedesk/models.py` (the real source of truth — if the two ever
disagree, the code wins and this file is stale; fix it).

> **Why this file exists:** twice in one session, queries were written against *guessed*
> column names (`eval_results.eval_case_id` — it's actually `case_id`; `eval_cases.category`
> — it's actually `adversarial_kind`) and blew up. Guessing schema is the database version of
> the SDK-reality rule. Look it up here.

**Database:** Postgres (Neon) + `pgvector`. Migrations via Alembic (`alembic/versions/`).
Schema changes go through a migration — never hand-edit tables.

---

## The tables at a glance

| Table | Rows (dev) | What it is |
|---|---|---|
| `tickets` | 12,030 | Support tickets: 11,922 real (Kaggle) + 5 adversarial + demo/pool rows |
| `runs` | 74 | One pipeline execution over one ticket. **Append-only, one-way state machine.** |
| `spans` | 318 | One row per pipeline stage per run — the evidence trail (OTel-convention) |
| `kb_docs` | 15 | Authored knowledge-base articles + their embeddings |
| `eval_cases` | 50 | The evaluation sets: 20 representative + 5 adversarial (the **golden set**) + 25 calibration-pool |
| `eval_results` | 50 | One row per case per eval-suite execution — the graded outcome + judge/human labels |
| `review_decisions` | 0 | Human approve/reject decision on an escalated run (the review queue's write side) |

---

## `tickets`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | **Load-bearing:** `id % 12` picks the simulated customer account (`triagedesk/tools.py::customer_ref_for`). Adversarial tickets use **pinned ids in the 90000-range** so their account (and its plan entitlements) is deterministic. |
| `subject`, `body` | text | The ticket content |
| `queue` | str(64) | Ground-truth queue label from the dataset (one of the 10 below) |
| `ticket_type`, `priority` | str, nullable | Dataset metadata |
| `language` | str(8) | Only `en` rows were ingested |
| `source` | str(16) | `kaggle` \| `demo` |
| `created_at` | timestamp | Server default |

**The 10 queues:** `Technical Support`, `Product Support`, `Customer Service`, `IT Support`,
`Billing and Payments`, `Returns and Exchanges`, `Service Outages and Maintenance`,
`Sales and Pre-Sales`, `Human Resources`, `General Inquiry`.
*(These overlap heavily in embedding space — that's the documented reason routing accuracy
scores ~29% against them.)*

## `runs` — one pipeline execution

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `ticket_id` | FK → tickets | |
| `state` | str(16) | `running` → `completed` \| `escalated` \| `failed`. **One transition, ever.** |
| `escalation_reason` | str(64), nullable | See the reason vocabulary below |
| `prompt_version` | str(32) | Which prompt version produced this run |
| `model` | str(64) | `claude-sonnet-4-6` |
| `total_cost_usd` | float | Accumulated; hard cap $0.10/run, **fail-closed** (uncomputable cost = breach) |
| `gate_signals` | JSONB, nullable | `{retrieval_similarity, classification_margin, entitlement_checked}` |
| `final_reply` | text, nullable | The customer-facing reply the agent drafted (**what the judge grades**) |
| `internal_rationale` | text, nullable | Post-hoc LLM explanation — **never ground truth** |
| `created_at` | timestamp | ⚠️ **Server default → timezone-NAIVE** |
| `finished_at` | timestamp, nullable | ⚠️ Set in Python → timezone-**AWARE**. Normalize before subtracting (this crashed the first live eval run). |

**`escalation_reason` vocabulary (observed live):** `agent_requested_human` (the model asks
for a human — the most common by far), `adverse_action` (a denial: never auto-delivered),
`no_entitlement_evidence` (the "show your receipt" rule — no `check_entitlement` call before a
`solve`), `precheck_off_topic` / `precheck_pii` / `precheck_injection` (caught by the safety
screen), `low_confidence` (gate thresholds), `budget_breach`, `validation_failed`,
`llm_refusal`, `tool_error`, `agent_incomplete` (loop exhaustion), `api_error:<Type>`,
`unexpected:<Type>` (the catch-all — no run can be stranded).

## `spans` — the evidence trail (one per stage, per run)

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `run_id` | FK → runs | |
| `name` | str(32) | `precheck` \| `classify` \| `retrieve` \| `act` \| `gate` |
| `status` | str(16) | `started` \| `ok` \| `error` |
| `started_at` / `ended_at` | timestamp | |
| `attributes` | JSONB | OTel GenAI-convention keys — see below |
| `cost_usd` | float | Per-stage cost |

**Attribute keys actually written** (query with `attributes->>'key'`):
- Every LLM stage: `gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.response.model`,
  `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`
- `precheck`: `triage.precheck.safe`, `triage.precheck.category`, `triage.precheck.reason`
- `classify`: **`triage.classify.queue`** (the predicted queue — this is where routing accuracy
  is read from; it is NOT stored on `runs`), `triage.classify.category`
- `retrieve`: **`retrieval.doc_slugs`** (list — the judge uses this to reconstruct exactly what
  the agent saw), `retrieval.k`, `retrieval.similarities`
- `act`: `triage.act.entitlement_denied`, `triage.act.entitlement_checked`
- `gate`: `triage.gate.auto_resolve`, `triage.gate.reason`, plus the gate signals

## `kb_docs`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `slug` | str(64), unique | Referenced by `spans.attributes->'retrieval.doc_slugs'` |
| `title`, `content` | text | |
| `embedding` | `Vector(1024)` | Voyage `voyage-3.5-lite`. Whole-doc embeddings, no chunking. Retrieval = cosine, **k=3**. |

## `eval_cases` — the evaluation sets

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | ⚠️ `eval_results.case_id` points here (**not** `eval_case_id`) |
| `ticket_id` | FK → tickets | |
| `kind` | str(16) | **`representative` (20) + `adversarial` (5) = the GOLDEN SET.** `calibration` (25) = the held-out judge-calibration pool. |
| `expected_outcome` | str(16) | `route` \| `escalate` (+ `unlabeled` for calibration rows). **Encodes IDEAL behavior, not what today's config does.** |
| `expected_queue` | str(64), nullable | NULL for 4 adversarial cases — routing is *not graded* for them |
| `adversarial_kind` | str(24), nullable | ⚠️ *not* `category`. Values: `injection`, `pii`, `off_topic`, `ambiguous`, `entitlement_denial` |
| `expected_escalation_reason` | str(64), nullable | |
| `notes` | text | Why this case exists / why its expected outcome is what it is |

> 🔒 **Hold-out rule:** the golden set (`kind IN ('representative','adversarial')`) **measures**;
> it must never **train**. Thresholds are never tuned on it. The `calibration` pool is
> deliberately different tickets — and **every golden metric query must exclude
> `kind = 'calibration'`** (the harness does this in `run_suite`).

## `eval_results` — one row per case per suite execution

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `eval_run_id` | UUID | Groups one suite execution (not an FK) |
| `case_id` | FK → eval_cases | ⚠️ **`case_id`**, not `eval_case_id` |
| `run_id` | FK → runs, nullable | The pipeline run that produced this result |
| `predicted_queue` | str(64), nullable | |
| `predicted_outcome` | str(16) | `route` \| `escalate` \| `failed` |
| `escalation_reason` | str(64), nullable | **The diagnostic gold** — why the gate escalated this case |
| `cost_usd`, `latency_ms` | float | |
| `retrieval_similarity`, `classification_margin` | float, nullable | The gate's signals, flattened for the calibration table |
| `routing_correct` | bool, nullable | NULL when routing isn't graded |
| `outcome_correct` | bool | ⚠️ Defaults to `False` — calibration-pool rows are *not graded*, so a query that doesn't filter on `kind` would misread them as "graded and wrong" |
| `judge_verdict` | str(16), nullable | `pass` \| `fail` \| `needs_review` |
| `judge_reason` | text, nullable | Debugging aid — **never ground truth** |
| `judge_rule_triggered` | str(32), nullable | `grounding` \| `helpfulness` \| `tone` |
| `human_label` | str(16), nullable | Cai's blind label — the other half of Cohen's kappa |

## `review_decisions` — the human decision on an escalated run

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `run_id` | UUID FK → runs, **unique** | One decision per run, ever — the queue query excludes any run with a row here |
| `decision` | str(8) | `approve` \| `reject` |
| `note` | text | The reviewer's note — required on every decision |
| `created_at` | timestamp | Server default |

Added by Week 3 Task 3 (issue #14, Alembic revision `c6811ea1a93e`). The queue endpoint
(`GET /api/review-queue`) reads `runs` where `state = 'escalated'` and no matching
`review_decisions.run_id` exists, oldest first — **no filter on `escalation_reason`**, so
adverse-action escalations (`adverse_action`, `no_entitlement_evidence`) show up like any
other escalation. Writes go through `POST /api/review/{run_id}` (`X-Admin-Token` header,
fail-closed: 503 if `settings.admin_token` is unset, 401 if the header is missing or wrong,
404 unknown run, 409 if the run already has a decision).

## `eval_results_golden` — the ONLY sanctioned read path for golden metrics

A Postgres **view** (Alembic revision `b2a3edf4a55a`, Hardening Task 2, issue #45) —
`eval_results` JOIN `eval_cases` filtered to `kind <> 'calibration'`, so it exposes only the
golden set (representative + adversarial). Columns: every `eval_results` column above, plus
`eval_cases.kind`, `eval_cases.expected_outcome`, `eval_cases.adversarial_kind`.

Built for **Week 3's console** (and any other non-Python consumer) to read golden-set metrics
without re-deriving the `kind <> 'calibration'` filter itself — every golden metric query
elsewhere in this codebase (`run_suite`, `compute_kappa_report` via its `eval_run_id` scoping,
the useful-queries block below) already applies that filter by hand; this view is the one
place a raw SQL client can get it for free. **Do not query `eval_results`/`eval_cases`
directly from a new non-Python consumer** — use this view so the calibration-pool exclusion
can never be forgotten. Read-only: nothing writes through it.

---

## Gotchas that have actually bitten (read before querying)

1. **`case_id`, not `eval_case_id`.** And **`adversarial_kind`, not `category`.**
2. **The predicted queue lives on the classify SPAN**, not on `runs`:
   `spans.attributes->>'triage.classify.queue'` where `name = 'classify'`.
3. **`created_at` is naive, `finished_at` is aware.** Normalize before subtracting.
4. **Always filter `eval_cases.kind`** when computing golden metrics — calibration rows would
   silently corrupt them.
5. **`tickets.id` is semantic** (`id % 12` → customer account). Never renumber tickets; never
   let adversarial tickets take auto-assigned ids.
6. **History tables are append-only.** `eval_results` and `runs`/`spans` are paid-for evidence.
   Destructive reseeds are gated behind `--reset-history` (a previous reseed destroyed a $0.73
   eval run before that guard existed).

## Useful queries

```sql
-- Why did each case escalate? (the entitlement-veto / threshold diagnostic)
SELECT er.escalation_reason, count(*)
FROM eval_results er JOIN eval_cases ec ON ec.id = er.case_id
WHERE ec.kind <> 'calibration'
GROUP BY 1 ORDER BY 2 DESC;

-- Judge vs human, for kappa
SELECT judge_verdict, human_label, count(*)
FROM eval_results
WHERE judge_verdict IS NOT NULL AND human_label IS NOT NULL
GROUP BY 1, 2;

-- One run's full evidence trail
SELECT name, status, cost_usd, attributes
FROM spans WHERE run_id = '<uuid>' ORDER BY started_at;
```
