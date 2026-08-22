# Agentic pipeline: methodology research and what actually applies

Research pass on how production systems make the auto-resolve/escalate decision, and
where TriageDesk's pipeline could be more efficient. Each finding is scored against
*this* project's constraints — the hour budget, the ~$8 remaining, and the standing
scope-discipline rule — not against a greenfield rebuild.

**Headline:** the single most-recommended optimization in the literature (model
cascading) is **not worth doing here**, and the measurement below says why. The
highest-value finding is that the project already built the right gate signal and is
only using it offline.

---

## 1. The frame has a name, a literature, and a metric

What TriageDesk does — answer when confident, abstain to a human otherwise — is
**selective prediction** (also "abstention", "learning to defer"). It is an established
subfield, not an ad-hoc design.

The standard evaluation is the **risk–coverage curve**: sweep the gate from
permissive to strict, and plot

- **coverage** — fraction of tickets answered autonomously
- **risk** — error rate *among the answered ones*

summarized as **AURC** (area under the risk–coverage curve). Lower is better: it means
the errors concentrate in the portion you abstained on.

**Why this matters for the project, concretely:** "escalation recall 1.0" is a single
point on that curve — the trivial one, at coverage ≈ 0 — which is precisely why a
`return "escalate"` stub reproduces it (#68). A curve cannot be faked by a stub, because
a stub has exactly one point on it.

**What it costs to produce:** nothing new needs building. Sweeping the gate's layers
off in post-processing over stored spans yields the curve directly. The blocker is that
run history was lost with the database and there are currently ~10 runs — so the curve
needs a golden-suite run (~$0.90) to have data underneath it, which #75 requires anyway.

> One caveat the literature is explicit about, and which applies here with force: a
> risk–coverage curve computed against **noisy labels** measures the labels as much as
> the system. With single-rater kappa 0.212 (`results/judge-calibration.md`), any curve
> this project plots carries that error bar and must say so.

---

## 2. The right replacement for the demoted margin already exists in this repo

Production systems that gate on "is this answer safe to send" do **not** use a
confidence score. The dominant pattern is **groundedness / entailment verification**:

1. decompose the generated reply into atomic claims,
2. check each claim is *entailed* by the retrieved context (NLI, or an LLM judge),
3. flag or block on any claim that is contradicted or merely unsupported.

This is exactly the structural criticism the council's First Principles advisor made:
the margin asks *"did the router agree with itself about the queue?"* while the decision
needs *"is this reply grounded in a document that actually answers the ticket?"*

**The observation that matters: TriageDesk already built this.** `triagedesk/evals/judge.py`
grades a reply against its retrieved KB context — a groundedness checker by construction.
It is used **only offline, for evaluation**. The literature says that shape of check is
what belongs in the runtime gate.

### Why moving it into the gate is not a simple win

Three project-specific objections, all real:

| Objection | Weight |
|---|---|
| **"Judge advises, never vetoes"** is a standing council decision, and `eval-baseline.json` ships `tolerance: {}` to enforce it. | Binding — this would reverse a deliberate ruling, not fill a gap. |
| **The judge is calibrated at kappa 0.133** (official v2). Gating on a signal that agrees with humans barely above chance repeats the margin's mistake with a more expensive instrument. | Strong. This is the same error one level up. |
| **The judge is tool-blind** — the documented root cause of its low kappa. 7/7 flagged "hallucinations" were true CRM/tool-derived facts. It would block correct replies that cite tool output. | Decisive as things stand. |

**Honest read:** the *architecture* is right and the *instrument* is not calibrated
enough to gate on. The tool-blind fix was deferred to a council checkpoint and never
made. That deferral is now the thing standing between this project and a principled
layer 4.

**Cheapest version that avoids all three objections:** a deterministic, non-LLM
grounding check — verify the reply's concrete claims (steps, settings, feature names)
appear in the retrieved KB text, in the same spirit as `gated_feature_implicated()`.
Weaker than NLI, but it costs $0 per run, adds no latency, needs no calibration, and
does not touch the judge ruling. Whether it separates good replies from bad is then an
empirical question answerable with the *existing* held-out labels and the *existing*
measurement harness (`scripts/measure_margin_separation.py`) — for free.

---

## 3. Cost optimization: measured, and the popular answer is wrong here

Measured on a live run (`/api/runs/{id}`, per-span attribution):

| stage | cost | share | latency | share |
|---|---|---|---|---|
| precheck | $0.0019 | 4.5% | 3.9s | 5.0% |
| classify | $0.0018 | 4.1% | 5.6s | 7.1% |
| retrieve | $0.0000 | 0.0% | 0.6s | 0.8% |
| **act** | **$0.0388** | **91.4%** | **68.0s** | **86.7%** |
| gate | $0.0000 | 0.0% | 0.3s | 0.4% |

**The act loop is 91% of cost and 87% of latency.** Everything else is rounding.

### Why model cascading does not apply

The literature's flagship result is cascading — FrugalGPT (Stanford) reports up to 98%
cost reduction; RouteLLM (Berkeley, ICLR 2025) reports ~85% cost reduction at 95% of
frontier quality by routing only 14% of queries to the strong model. The standard advice
is "run the cheap model first, escalate on a failed check."

Applied here it collapses:

- **Cascading precheck + classify to Haiku** touches 8.6% of spend. Even a perfect 5×
  saving nets **~7% of total cost** — roughly $0.0025/run. Two live runs' worth of
  savings for a real architectural change plus a second calibration surface.
- **Cascading the act loop** is where the 91% lives, but the act loop is exactly the
  part that needs capability: multi-turn tool use, entitlement reasoning, and the
  customer-facing reply. A cheap-model attempt that fails the check means paying twice
  *and* adding its latency — and the literature is emphatic that escalation rate is a
  live cost variable that silently drifts toward 100%.

**Verdict: don't.** This is worth writing down precisely *because* it is the obvious
recommendation — "measured the distribution, the optimization targets 8% of spend, so
declined it" is a stronger case-study line than having implemented it.

### The metric the literature insists on, which this project can actually compute

> *"A model can cost 80% less per call and still lose money if it triples failure-rate
> or sends more work to human reviewers. The full measure includes model spend, tool and
> runtime costs, retries, and human review."* — cost **per accepted task**, not per token.

TriageDesk is unusually well placed to compute this, because it has a real human review
queue and `review_decisions` records the verdicts. An escalation has a labour cost; an
auto-resolve does not. That converts the auto-resolve rate from a vanity number into an
economic one — and makes the safety layers legible as a *cost* decision as well as an
ethical one.

### The real latency lever

Not the model. `triage.act.iterations` was **2** on the auto-resolving run — one lap to
call tools, one to submit. The floor for the current design is roughly two sequential
model calls. Meaningful latency reduction would require parallelising precheck and
classify (independent of each other, ~9.5s combined, both blocking), which is a genuine
but modest ~12% win.

---

## 4. Explicitly not recommended

| Pattern | Why not here |
|---|---|
| Multi-agent orchestration | The single hand-written loop is a deliberate interview story. Adding agents adds coordination failure modes and contradicts the scope discipline. |
| Semantic caching | Real wins need query repetition. A 4-ticket demo pool has none. |
| Reflection / self-critique loops | Multiplies the stage that is already 91% of cost, to improve a reply quality that cannot currently be measured (kappa 0.212). |
| Chunking the KB | Measured: KB docs separate at 0.747 mean pairwise cosine, lengths 1612–2490 chars. Nothing is being blurred. The "no chunking" cut holds. |
| Re-tuning thresholds for throughput | Forbidden by the project's own hold-out rule, and the exact failure the council was convened to prevent. |

---

## 5. Ranked, with cost

| # | Action | Cost | Why |
|---|---|---|---|
| 1 | **Publish the null baseline (#68)** | $0 | Unchanged. A curve or a baseline is the difference between a metric and a claim. |
| 2 | **Plot the risk–coverage curve** from stored spans after the #75 suite run | $0 extra | Turns "auto-resolves 2 of 4" into an operating curve. Compatible with a negative result. |
| 3 | **Deterministic grounding check**, measured with the existing harness before it gates anything | $0 | The principled layer-4 replacement, minus all three judge objections. |
| 4 | **Cost per accepted task** | $0 | The literature's own metric, and this project can actually compute it. |
| 5 | Parallelise precheck + classify | $0 | ~12% latency, no quality risk. Small but real. |
| — | Model cascading | — | **Declined on measurement.** Targets 8.6% of spend. |

Items 2–4 are all **$0 and reuse infrastructure built this week**. That is not a
coincidence: the measurement harness, the cached signals, and the per-span cost
attribution were the expensive part, and they are already paid for.

---

## Sources

- Selective prediction / abstention: *Aligning Language Models with Selective Prediction*
  (arXiv 2607.03528); *Calibrating LLMs for Selective Prediction* (OpenReview);
  *The Art of Abstention* — risk–coverage and AURC as the standard evaluation.
- Groundedness: *Grounded in Context* (Deepchecks, arXiv 2504.15771) — per-claim
  retrieval and verification; FActScore-style atomic decomposition + NLI entailment.
- Cascades: FrugalGPT (arXiv 2305.05176); RouteLLM (arXiv 2406.18665, ICLR 2025);
  TrueFoundry and Splunk practitioner writeups on escalation rate as a monitored SLO and
  on cost-per-accepted-task.
- Agent loops: max-iteration caps and per-iteration latency as the dominant cost —
  consistent with the measured 2-iteration, 68s act span here.
