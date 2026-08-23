# Decision menu — everything on the table, with costs and my recommendation

**Purpose:** one place to decide what ships and what gets cut, rather than tracking
recommendations across a dozen issues and reports. Council-ready.

> **STATUS 2026-08-23 — Tier 1 and Tier 2's first item are DONE.** Shipped: #68
> (null baseline, derived + automated), #76 (landing copy), the CI unit/integration
> split, and the `voyageai` pin. **#61 is now the critical path** — #75, the
> risk-coverage curve, and the re-baseline all queue behind it, and it needs the Neon
> dashboard.

**Constraints as of 2026-08-22:** ~**$8.5 of $20** remaining. Two planned deliverables
never started (#17 demo video, #18 case study). Job-hunt cycle is the deadline.

**State:** live on Northflank, database rebuilt, **2 of 4 demo tickets auto-resolve**,
both escalations are genuine denials. 290 tests green.

---

## The one framing that should drive the decisions

There are two different goals in play, and several items serve only one:

- **Goal A — the system is defensible.** No published claim outruns its evidence.
- **Goal B — the system is more capable.** It resolves more, costs less, does more.

**Goal A is the project's actual thesis** ("the differentiator is NOT the agent — it's
the eval/observability/trust discipline"). Where the two conflict, A wins. Several items
below are pure B and are marked as such — they are the ones to cut first if time runs short.

---

## Tier 1 — Correctness. Things that are currently wrong.

### 1.1 · #61 — eval-gate points at a deleted Neon branch
**Cost:** $0 + Neon dashboard access · **Risk:** none · **Recommend: DO**

The eval gate has been **silently non-functional through every gate change this week**.
It fires on `triagedesk/**`, so #70 and #74 both triggered it; both died at
`alembic upgrade head` before spending anything. The project's regression guard has been
decorative since the Neon expiry.

### 1.2 · #75 — `eval-baseline.json` is stale, and #61 will unmask it
**Cost:** ~$0.90 (one golden suite run) · **Risk:** may reveal a real regression · **Recommend: DO, immediately after 1.1**

Three changes invalidated the recorded floors: #64 (membership), #69 (entitlement
scoping), #74 (margin demoted). The gate is now more willing to auto-resolve, so any
expected-escalate golden case that now completes drops `escalation_recall` below its
1.00 floor and **blocks merges on every eval-path PR**.

⚠️ The failure would be *correct*. Do not fix it by relaxing floors — the question is
*which case moved and is that defensible*.

### 1.3 · #76 — landing page says "nothing auto-resolves"
**Cost:** $0 · ✅ **DONE** (PR #78)

Latent, not active: renders only when the last 50 runs contain zero completions — i.e.
after a fresh bootstrap, exactly when a visitor most needs an accurate explanation.

### 1.4 · Pin `voyageai>=0.3`
**Cost:** $0 · ✅ **DONE** (PR #78)

Same unpinned-major-version class as #71, which took production down for an afternoon.
Lower blast radius (build-time scripts, not the request path) but identical latent failure.

### 1.5 · Split CI into unit and integration jobs
**Cost:** $0, ~1h · ✅ **DONE** (PR #78) — 266 of 290 tests (92%) now run with no external service

CI runs `alembic upgrade head` before `pytest`, so **~250 database-free unit tests cannot
run when an external free-tier service is down**. During the Neon outage a doc typo was
unmergeable. Would have helped twice this week.

---

## Tier 2 — Evidence. Making claims match reality.

### 2.1 · #68 — publish the null baseline
**Cost:** $0 · ✅ **DONE** (PR #77)

On a 22-escalate/3-route golden set, `return "escalate"` scores escalation recall 1.00
and precision 0.88 — **identical to what the README published**. Both are now marked
as base-rate artifacts rather than evidence about the pipeline.

**Correction found while implementing:** the design-intent adversarial catch rate does
**not** collapse — it is reason-aware, so a stub with no `escalation_reason` scores
0.00. Three metrics collapse (recall, precision, `adversarial_escalate_rate`); three
carry real signal. `PITCH.md:128` shows the insight was already had in Week 2.5 and
applied to one metric; this extended it to the rest.

An interviewer finds this in thirty seconds. *"My headline metrics were reproducible by a
one-line stub, so I retracted them and published the baseline"* is a self-falsification
almost no new grad can demonstrate — a stronger signal than the original numbers.

### 2.2 · Risk–coverage curve
**Cost:** $0 (after 1.2's suite run) · **Risk:** may be a flat line · **Recommend: DO**

Sweep the gate's layers off in post-processing over stored spans; plot coverage against
error-rate-among-answered. This is the standard evaluation for selective prediction, and
it reframes 2.1 precisely: **"escalation recall 1.0" is the trivial point on that curve at
coverage ≈ 0** — which is why a stub reproduces it. A curve cannot be faked by a stub.

⚠️ Compatible with a negative result. If the curve is flat, that is publishable and honest.
⚠️ Computed against kappa-0.212 labels, so it carries that error bar and must say so.

### 2.3 · Cost per accepted task
**Cost:** $0 · **Risk:** none · **Recommend: DO**

The literature's own metric: per-token cost is misleading when a cheaper model sends more
work to humans. This project has a real review queue and `review_decisions` — so it can
actually compute it, which most can't. Converts auto-resolve rate from a vanity number
into an economic one, and makes the safety layers legible as a cost decision.

---

## Tier 3 — Capability. Genuinely new work.

### 3.1 · Deterministic grounding check (replace the demoted margin)
**Cost:** $0/run, ~3h · **Risk:** may not separate — but that is measurable first · **Recommend: DO if time allows**

Production systems gate on **groundedness** (is each claim entailed by retrieved
context?), not confidence scores — exactly the council's structural criticism. Layer 4 is
currently retrieval similarity alone, so there is a real gap.

`judge.py` is already a groundedness checker but **cannot be moved into the gate**: it
would reverse the "judge never vetoes" ruling, it is calibrated at kappa 0.133, and it is
documented tool-blind (flagged 7/7 true tool-derived facts as hallucinations).

The deterministic version — verify the reply's concrete claims appear in the retrieved KB
text, same spirit as `gated_feature_implicated()` — dodges all three. **And it is testable
for free before it gates anything**, using the existing held-out labels and
`scripts/measure_margin_separation.py`.

### 3.2 · Intake path — `POST /api/tickets`
**Cost:** ~$0, 3–4h · **Risk:** scope creep · **Recommend: DECIDE DELIBERATELY**

**No ticket ever "arrives."** There is no intake endpoint, no queue, no worker — the only
trigger is a human clicking Run. That is the honest line between *a demo* and *a system*,
and the biggest remaining differentiator.

Minimal version: admin-token-guarded endpoint → `source='inbound'` → existing
`execute_run` via `BackgroundTasks`. **The pre-check stage exists precisely for untrusted
input and has never seen any.**

⚠️ Counter-argument with real weight: this project's discipline has been ruthless
scope-cutting, and every cut has a "what I'd add in production" paragraph. A half-built
queue is worse than a documented cut. **This is the item most worth councilling.**

### 3.3 · Parallelise precheck + classify
**Cost:** $0, ~1h · **Risk:** low · **Recommend: OPTIONAL** (pure Goal B)

Independent of each other, ~9.5s combined, both blocking. ~12% latency win. Real but modest.

---

## Tier 4 — Deliverables. What actually gets you hired.

### 4.1 · #17 demo video · **Recommend: DO**
Now has something to show: a ticket auto-resolving, and a denial being refused.
Suggested opening, from the council's Outsider: *"The system refused to answer a customer
because it couldn't decide whether their ticket belonged in the 'Technical Support' folder
or the 'IT Support' folder — and those two folders are 99.6% identical."* Then the fix.

### 4.2 · #18 case study · **Recommend: DO — this is the deadline**
The spine is unusually strong now: five defects found by measurement, one fix proven not
to work the way it was claimed, and a gate that resolves routine tickets while never
auto-sending a denial. Every declined item below is a "what I'd add in production" paragraph.

---

## Declined, with reasons (each is a case-study paragraph)

| Item | Why declined |
|---|---|
| **Model cascading** (FrugalGPT / RouteLLM) | **Measured:** act loop is 91.4% of cost, 86.7% of latency; precheck+classify are 8.6%. A perfect 5× saving on the cheap stages nets ~7% of total (~$0.0025/run) for a real architectural change plus a second calibration surface. Cascading the act loop pays twice on the stage that needs capability. |
| Multi-agent orchestration | The single hand-written loop is a deliberate interview story. Adds coordination failure modes; contradicts scope discipline. |
| Semantic caching | Needs query repetition. A 4-ticket demo pool has none. |
| Reflection / self-critique loops | Multiplies the stage already at 91% of cost, to improve a reply quality that cannot currently be measured (kappa 0.212). |
| KB chunking | **Measured:** docs separate at 0.747 mean pairwise cosine, uniform 1612–2490 chars. Nothing is being blurred. |
| Re-tuning thresholds for throughput | Forbidden by the hold-out rule, and the exact failure the council exists to prevent. |
| Second rater for the labels | Not declined — *blocked*. Needs a human, not money. It is the real ceiling: every CI in the margin measurement spans 0.50 because 11–13 failures pin them open. |

---

## My recommended sequence

| | Items | Cost | Rationale |
|---|---|---|---|
| **1** | 2.1 (#68) | $0 | Protects every other number on the page. Do before anything. |
| **2** | 1.3, 1.4, 1.5 | $0 | Cheap correctness. Mobile-friendly. |
| **3** | 1.1 → 1.2 | ~$0.90 | In this order. Unmasks the eval gate, then re-derives the floor. |
| **4** | 2.2, 2.3 | $0 | Free once step 3 has data. Turns results into a curve and an economic number. |
| **5** | 4.1, 4.2 | ~$0.50 | The deliverables. **This is the deadline.** |
| **6** | 3.1, 3.2, 3.3 | varies | Only if steps 1–5 are done. |

Leaves ~$7 of headroom against ~$8.5.

**The honest risk:** Tier 3 is the most *interesting* work and the most likely to eat the
time that #17 and #18 need. A finished case study describing a system with a documented
gap beats an unfinished one describing a better system.

---

## Questions worth councilling

1. **3.2 (intake path)** — genuine differentiator, or scope creep dressed as one? The
   strongest case against is that this project's identity *is* its cut list.
2. **3.1 (grounding check)** — is a deterministic keyword check honest enough to gate on,
   or does a weak-but-cheap signal repeat the margin's mistake in a new costume?
3. **Sequencing** — should 4.2 (case study) start *now*, in parallel, rather than last?
   It is the actual deliverable, and every item above changes what it says.
4. **2.2** — if the risk–coverage curve comes out flat, is that a publishable finding or
   a reason not to publish the curve at all?
