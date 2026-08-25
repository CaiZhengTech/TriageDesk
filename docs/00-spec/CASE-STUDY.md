# TriageDesk — building an AI support agent you can actually audit

**What it is:** an AI agent that reads a support ticket, looks up the customer's
account, searches a knowledge base, drafts a reply, and then decides — from external
evidence, never from its own confidence — whether to send that reply or hand it to a
human.

**What it's really about:** the machinery that makes that decision defensible. Any
capable model can draft a plausible support reply. The hard part is knowing when not to
send it, and being able to prove which parts of your evaluation mean anything.

**Live:** [console](https://triage-desk-xi.vercel.app) ·
[API](https://site--triagedesk-api--26d8jdlxzvsv.code.run) ·
[source](https://github.com/CaiZhengTech/TriageDesk)

**Constraints:** ~4 weeks part-time · **$20 total API budget, no top-ups** · one person.
Every number below traces to a committed artifact, named inline.

---

## The results, with the trivial baseline beside them

The golden set is 25 cases, 22 of which should escalate. On that distribution, several
natural-looking metrics are reproduced exactly by a one-line stub:

```python
def triage(ticket):
    return "escalate"
```

So every metric is published next to what that stub scores. The comparison is derived
programmatically (`results/null-baseline.json`), asserted by a test, and **printed on
every suite run** — it cannot quietly stop being true.

| Metric | System | Null stub | |
|---|---|---|---|
| **Adversarial catch rate (design-intent)** | **1.00** | **0.00** | ✅ real |
| **Adversarial catch rate (strict)** | **0.60** | **0.00** | ✅ real |
| Routing accuracy vs dataset labels | 0.286 | 0.00 | ✅ real |
| Escalation precision | 0.917 | **0.880** | ✅ real, barely — was an artifact until this month |
| Escalation recall | 1.00 | **1.00** | ⚠️ **not distinguishing** |
| Adversarial escalate rate | 1.00 | **1.00** | ⚠️ **not distinguishing** |

*Source: `results/eval-baseline.json` `_source_run`, eval_run `a56f283a`, 2026-08-25.
$0.71 pipeline + $0.16 judge, 25 cases, p50 26.2s.*

**"Escalation recall 1.0" was the number I most wanted to lead with, and it is worth
nothing on its own.** A system that escalates everything scores it perfectly. Publishing
that fact was the single highest-value change I made.

**The catch rate survives the same test**, and not by accident. A case only counts as
caught if the observed `escalation_reason` matches the layer that was *supposed* to catch
it. A stub has no reason to report, so it scores zero. That metric exists because an
earlier adversarial review of my own evals found the outcome-only version was flattering
me — the fix predates the null baseline by a month.

---

## How the decision is made

Five stages. The gate is the point of the project.

```
ticket → pre-check → classify → retrieve → act loop → GATE → auto-send │ human review
         injection/  1 of 10    pgvector   tools +          ▲
         PII screen  queues     k=3, 15 KB  submit          │
                                                    four layers, first match wins
```

| Layer | Blocks when | Why it exists |
|---|---|---|
| 1 · `adverse_action` | the reply denies something, or an entitlement check returned false | **Non-negotiable.** The agent never autonomously tells a customer "no". |
| 2 · `agent_requested_human` | the model itself submitted `needs_human` | The model's own abstention is respected. |
| 3 · `no_entitlement_evidence` | a `solve` grants a plan-gated feature with no `check_entitlement` receipt | An unverified "yes" is a denial the model never flagged. |
| 4 · `low_confidence` | retrieval similarity < 0.45 | The only statistical layer left standing — see below. |

**The gate never reads the model's self-reported confidence.** External evidence only:
what was retrieved, what the tools returned, what the reply actually says.

### Watch two tickets

Same complaint. Same agent. Different plan.

| | Morgan (Pro) | Dana (Basic) |
|---|---|---|
| Ticket | "VPN drops every few minutes" | "My VPN keeps disconnecting — client demo at 3pm" |
| `check_entitlement("priority_vpn_support")` | **covered** | **not covered** |
| Gate | all four layers pass | **layer 1 fires** |
| Outcome | **auto-resolved**, $0.037 | escalated `adverse_action`, $0.041 |

Dana still gets a complete, KB-sourced reply with real troubleshooting steps — it just
reaches a human first, because it carries an implicit "no" about the urgency she asked
for. That is the entire thesis in two tickets.

---

## Five things I got wrong, and how I found out

This is the actual content of the project. Each was found by measurement, and each is
reproducible from the repo.

### 1 · My headline metrics were reproducible by a stub

Recall 1.00 and precision 0.88 are what `return "escalate"` scores on a 22/25 corpus.
I published the baseline beside them and rewrote the résumé bullet that led with them.

**Correction found while implementing:** I initially believed the *catch rate* collapsed
too. It doesn't — it's reason-aware, so a reasonless stub scores 0.00. The honest story
is narrower and better: I'd caught this exact tautology once before, fixed it for one
metric, and never extended the reasoning to the others.
→ `results/null-baseline.json`, `triagedesk/evals/null_baseline.py`

### 2 · The confidence signal was noise, and repairing it didn't help

The gate's `classification_margin` compares a ticket to its predicted queue's centroid.
Two defects, both measured:

- **Wrong embedding space.** Tickets were embedded as `input_type="query"`, centroids as
  `"document"` — Voyage trains those asymmetrically *on purpose*. Right for the KB search
  the same vector performs, wrong for comparing a ticket to a prototype of tickets.
- **Anisotropy.** The ten queue centroids had **mean pairwise cosine 0.9782**; Technical
  Support vs IT Support was **0.9963**. Those aren't ten categories. The margin — a
  *difference* of two such numbers — varied only in the third decimal.

Fixing both widened its usable range ~26×, and a ticket auto-resolved for the first time.
Then I measured whether it had become *informative*, against 41 held-out human labels:

| | pre-fix | post-fix | Δ |
|---|---|---|---|
| Round 1 AUC | 0.334 | 0.337 | **+0.003** |
| Round 2 AUC | 0.442 | 0.442 | **0.000** |

**The repair made the signal decisive without making it informative.** It answers *"did
the router agree with itself about the queue?"* while the gate decides *"may this reply
be sent unseen?"* Repairing an instrument doesn't change what it measures. I demoted it
to observability — still computed, still in every trace, no longer able to veto.
→ `docs/week-4-launch/reports/margin-separation-measurement.md`

⚠️ Stated in the code, not just here: **this acts on a null result.** Every 95% CI spans
0.50. At 39 labels with 11–13 failures, the sample can't establish separation in either
direction. "Cannot be shown to help" isn't "proven useless" — but a layer that *blocks
work* bears the burden of proof.

### 3 · A safety rule was demanding receipts for purchases nobody made

`no_entitlement_evidence` required a `check_entitlement` call behind **every** `solve`.
A password-lockout ticket retrieved its KB article at 0.7175, got a correct unlock reply,
and escalated — because password unlock isn't a plan feature and so was never checked.

The rule guards a real risk: the model saying "sure, I've enabled that" for something the
plan excludes. But that risk only exists for features a plan can **withhold**. Now scoped
to gated features, derived from `PLAN_ENTITLEMENTS` so it can't drift from the tool the
agent calls.

### 4 · An unpinned dependency took production down

`requirements.txt` said `anthropic>=0.116`. A redeploy installed **1.0.0**, which removed
`temperature` from `Messages.create()`. Every run died at pre-check.

**266 mocked tests passed while production couldn't complete a single run.** My own notes
already recorded this failure class from week one — the rule existed, nothing enforced it.
Now `tests/unit/test_sdk_compat.py` introspects the *installed* SDK and names the call
site in its failure message.

### 5 · The regression guard was silently switched off

The eval gate fires on backend changes. It fired on three of them. All three died at
`alembic upgrade head` — the eval database pointed at a deleted branch — **before
spending anything**, so they failed fast and looked like ordinary CI noise.

Three behavioural changes merged with nothing checking them. When I finally repaired it,
**every floor held and precision improved 0.88 → 0.917** — but I didn't know that for a
week, and *believing* is not *having checked*.

---

## The economics, which invert the standard advice

The routing literature's flagship optimization is **model cascading** — run a cheap model
first, escalate on failure. FrugalGPT reports up to 98% cost reduction; RouteLLM ~85%.

I measured my own cost distribution before implementing it:

| stage | cost | latency |
|---|---|---|
| **act loop** | **91.4%** | **86.7%** |
| pre-check + classify | 8.6% | 12.1% |

Cascading the cheap stages targets **8.6%** of API spend. Then I measured what the system
actually costs to operate, over 13 runs of real history:

```
API spend            $0.44
human review labour  $30.00     (10 escalations × 6 min @ $30/h)
TOTAL                $30.44
cost per accepted task  $15.22
break-even deflection    1.12%
```

**Labour is 98.6% of the bill.** So the optimization everyone recommends first would
have addressed roughly **0.1%** of what this system costs to run.

The lever that matters is the **escalation rate** — which is gate design, not model
selection. Break-even at 1.12% means the pipeline pays for itself deflecting 1 ticket in
89; at 15.4% it's ~14× past that.

⚠️ `review_minutes` and `reviewer_hourly_usd` are **assumptions, not measurements** — no
ticket here was reviewed under a stopwatch. They're carried in the output and exposed as
CLI flags so disagreeing is cheap. And the whole result assumes reviewing a draft isn't
*slower* than answering from scratch. That's unmeasured, and it's the assumption that
would invalidate it.
→ `triagedesk/evals/unit_economics.py`

---

## The number I can't fix, and won't hide

Routing accuracy against the dataset's own labels is **0.286**. Two independent methods
agree it's a ceiling, not a defect:

| method | accuracy |
|---|---|
| LLM classifier | 0.286 |
| nearest-centroid on embeddings | 0.28 |
| random (10 classes) | 0.10 |

Two unrelated approaches landing within a point of each other means the constraint is the
**label set**. The geometry says why — Technical Support and IT Support are 0.9963 cosine
apart.

The controlled comparison sits inside the project: the KB docs I **authored** separate at
**0.747** mean pairwise cosine; the queue taxonomy I **inherited** sits at **0.941**. Same
embedding model, same pipeline. The thing I designed is separable; the thing I was handed
isn't.

And a related ceiling on the evaluation itself: my own label self-agreement, relabelling
the same 41 replies three days apart, is **Cohen's κ = 0.212** — *lower* than the judge's
agreement with either round. **Single-rater ground truth is the binding constraint**, not
the model. The fix is a second rater, not more tuning.

---

## What I deliberately did not build

Each of these was a decision, and most were decisions *against measured evidence*:

| Cut | Why |
|---|---|
| **Model cascading** | Measured: targets 8.6% of API spend, which is 1.4% of total cost. |
| No orchestration framework | The agent loop is ~120 lines. LangChain would hide exactly what's worth understanding: what enters the context window each lap, and who decides when to stop. |
| No chunking | Measured: KB docs separate at 0.747, uniform 1.6–2.5KB. Nothing is being blurred. |
| Multi-agent | Adds coordination failure modes to a system whose value is auditability. |
| Reflection loops | Multiplies the stage already at 91% of cost, to improve a reply quality I can't yet measure (κ 0.212). |
| Semantic caching | Needs query repetition. A demo pool has none. |
| Real OTel export | Spans use `gen_ai.*` conventions in Postgres — the naming is the portable part. |

**What I'd add first in production:** a **ticket intake path**. Today nothing "arrives" —
a human clicks Run. The pre-check stage exists precisely for untrusted input and has
never seen any. That's the honest line between a demo and a system.

**Second: a second rater.** Every confidence interval in this project is pinned open by
having 39 labels from one person. It's the cheapest change with the largest effect, and
it needs a human, not money.

---

## What this cost

| | |
|---|---|
| API spend | **~$12.4 of $20**, no top-ups |
| Tests | **307**, gating every merge |
| Per-run cost | $0.028 avg, hard-capped at $0.10, fail-closed |
| Latency | p50 26.2s |

Every figure above is reproducible: `results/` holds the artifacts, `docs/week-4-launch/reports/`
holds the measurements, and the scripts that generate them are committed.

---

## The one-sentence version

*I built an AI support agent, then spent most of the time proving which parts of its
evaluation actually meant anything — and published the parts that didn't.*
