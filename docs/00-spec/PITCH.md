# TriageDesk — The Pitch File

*One file to read before any interview or recruiter conversation. Updated at every
milestone. Everything here is true and defensible — every claim traces to a commit,
a test, or a logged run.*

**Last updated:** 2026-07-14 (**Week 2 COMPLETE** — CI eval gate green on main, kill criterion met)

---

## The 30-second pitch (lead with this)

> "I built TriageDesk — an AI agent that triages customer support tickets, but the
> point isn't the AI. It's the trust machinery around it: every decision leaves an
> evidence trail with per-run dollar costs, hard spending caps that fail closed, and a
> safety rule — the AI never delivers bad news to a customer on its own — that's
> enforced by code structure, not by hoping the model behaves. I proved that last part
> the hard way: an adversarial review of my own finished work found the rule could be
> bypassed, so I wrote the exploit as a failing test, then closed the hole
> structurally."

## The one-minute version (if they lean in)

> "It's a five-stage pipeline: a safety screen, a classifier, retrieval over a
> knowledge base, a hand-written agent loop with tools — no LangChain, I wanted to own
> every line of the loop — and a confidence gate that decides auto-resolve versus
> human review. The gate only trusts external, measurable signals: retrieval
> similarity and classification margin. Never the model's self-reported confidence —
> models flatter themselves. Week 1 ended with a live end-to-end run: a real ticket
> asking for a feature the customer's plan didn't include went through all five
> stages, and the system correctly refused to auto-deliver the denial and routed it to
> a human, for about four cents, with every step logged. Week 2 is the evaluation
> layer: a golden set with adversarial cases, an LLM judge calibrated against human
> labels with Cohen's kappa, and a CI gate that blocks any change that regresses
> quality."

---

## Per-feature one-liners (drop these when a topic comes up)

**On the safety rule (adverse action):**
> "My safety invariant turned out to depend on model cooperation, so I made it
> structural — the gate now requires tool-call evidence before any auto-resolve, and I
> wrote the exploit as a failing test before writing the fix."

**On the hand-written agent loop (why no LangChain):**
> "I wrote the agent loop by hand on the raw SDK because I wanted to answer for every
> line of it — and it paid off: a live probe showed the model issuing parallel tool
> calls, which my review then caught as an ordering bug in exactly that case. A
> framework would have hidden both the behavior and the bug."

**On the SDK-reality rule (the week's best story):**
> "Three separate times, code that passed green mocked tests was wrong against the
> real API. So I made a standing rule: no code against an API surface I haven't
> observed live — run a real probe first, commit the actual response as a test
> fixture, build mocks only from that. Reality is the spec."

**On cost controls:**
> "Every run has a ten-cent cap that fails closed — if cost can't be computed, that
> IS a breach. And the boundary is pinned by tests, including the exactly-at-cap
> case, so the policy lives in the test suite, not in tribal knowledge."

**On observability (the glass box):**
> "Every stage writes structured spans following OTel GenAI conventions — model,
> tokens, cost, decision reasons. When someone asks 'why did the AI escalate this
> ticket?', I print the trace. The rationale the LLM gives is logged as context, but
> the trace is the evidence — I never treat the model's explanation as ground truth."

**On the gate's design:**
> "The gate never asks the model how confident it is — self-reported confidence is
> miscalibrated flattery. It uses two external signals, retrieval similarity and
> classification margin, and Week 2 calibrates the thresholds against human labels
> instead of me guessing them."

**On judge calibration (the tool-blind judge — the flagship honest-number story):**
> "I calibrated my LLM judge against 41 of my own blind labels and got a kappa of
> 0.28 — a number most people would hide. But the disagreement report explained it:
> the judge was flagging 'you're on the Pro plan' as hallucination, and when I
> replayed those claims against the simulated CRM, seven out of seven were true —
> facts the agent got from its tools, which the judge was never shown. The grader
> wasn't wrong, it was under-informed. That finding changed my CI design: a
> kappa-0.28 judge advises, it doesn't veto."

**On why a low kappa was still safe to ship:**
> "Eighteen of the twenty disagreements were the judge being stricter than me —
> for a triage gate that's the failure direction you want. The two lenient misses
> are the real risk, and they're why deterministic metrics carry my CI gate."

**On process (CI/branch protection):**
> "CI gates every merge: tests, linting, and gitleaks secret-scanning. I learned the
> hard way after CI was silently red for two days — now GitHub physically refuses
> merges without green checks."

**On the CI eval gate (the Week-2 finale):**
> "My golden set re-runs automatically in CI whenever behavior-relevant code changes —
> agent code, knowledge base, schema migrations, dependencies — under a $1 hard cap
> that fails the job if exceeded. Deterministic metrics gate exactly; my LLM judge
> only advises, because I measured its agreement with me first and a kappa-0.28 judge
> hasn't earned a veto. And the trigger is path-filtered, because at a dollar per run,
> an every-merge trigger would have eaten my entire remaining budget."

**On honest limitations (say this proactively — it builds trust):**
> "Right now nothing auto-resolves — both live runs' classification margins were below
> my placeholder threshold. That's deliberate: the thresholds are placeholders, and
> Week 2's whole job is setting them from a calibration table against human labels
> rather than my intuition."

---

## "What I'd add in production" (deliberately cut — knowing what NOT to build)

Scope discipline was a design goal: a 4-week part-time budget and a hard $20 API
budget. Each cut is a talking point, not a gap:

- **Contract tests & nightly eval runs** — CI evals run on merge; nightly cadence
  matters at team scale, not solo scale.
- **Docker** — Windows/WSL2 friction wasn't worth it for one developer; Railway's
  Nixpacks builds from source. In production: containerize for parity.
- **Real OTel export** (Jaeger/Honeycomb) — spans already follow OTel conventions in
  Postgres; production would export to a real collector. The conventions make that a
  config change, not a rewrite.
- **CodeQL / Dependabot / pip-audit** — enterprise supply-chain scanning is
  maintenance noise on a solo portfolio repo; gitleaks covers the realistic risk
  (leaked secrets).
- **Dead-letter queue for failed runs** — failed runs are visible in the console;
  at production volume they'd need retry workflows.

---

## The numbers (live, as of Week 2)

| Metric | Value |
|---|---|
| **Adversarial catch rate** | **5 / 5 = 100%** — every trap caught by its intended defense layer |
| **Escalation recall** | **1.0** — nothing needing a human slipped through (precision 0.88) |
| Real tickets in the database | 11,922 (public Kaggle dataset, English) |
| Golden evaluation set | 25 cases (20 stratified real + 5 authored adversarial) |
| Judge calibration | 41 blind human labels · raw agreement 0.512 · **Cohen's kappa 0.279** (judge stricter than human in 18/20 disagreements — fails in the safe direction) |
| Judge "hallucination" flags replayed against the CRM | 7/7 were TRUE tool-derived facts — the judge is tool-blind (see disagreement report) |
| Knowledge-base articles authored + embedded | 15 |
| Pipeline stages, all live-verified end-to-end | 5 |
| Cost per full pipeline run | **~2.9¢** with prompt caching (hard-capped at 10¢) |
| Latency | p50 31s · p95 41s |
| CI eval gate | **GREEN on main, first live run** — 25 golden cases re-run on behavior-relevant pushes, $1 cap, $0.72 actual |
| Test suite | 145+ tests + lint + secret-scan, gating every merge |
| **Total API spend, entire project to date** | **~$3.77** against a hard $20 budget |

*(Week 2 complete — every planned eval-layer artifact landed. Next: the Week-3 console.)*

---

## Deep-dive companions (for interview prep, not for recruiters)

- [The Week 1 story, issue by issue](STORY.md) — analogies
  + Dana's journey through every stage
- [The QA hardening explainer](QA-HARDENING.md) — the
  "show your receipt" fix in full
- Design record: `docs/00-spec/DESIGN-SPEC.md`
