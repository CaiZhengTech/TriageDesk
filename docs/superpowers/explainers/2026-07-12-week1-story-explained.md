# The Week 1 Story, Explained (issues #1–#7)

*The complete plain-language walkthrough of what got built in Week 1 and why each piece
exists. Every chapter has two halves: **the analogy** (grasp it in 10 seconds) and
**Dana's journey** (watch it actually happen). Dana is our recurring customer: she filed
a ticket saying "My VPN keeps disconnecting — client demo at 3pm. Can you also enable
priority VPN support on my account?" Her plan doesn't include that feature, so the right
answer contains a denial — which triggers this project's most important safety rule.*

*Companion docs: [QA hardening explainer](2026-07-12-week1-qa-explained.md) ·
[PITCH.md](PITCH.md) (interview one-liners, one file).*

*Each chapter has three layers: **the analogy** (10-second grasp), **Dana's journey**
(watch it happen), and **Under the hood** (semi-technical — the actual components and
terms, for when you want one level deeper without reading code).*

---

## What is TriageDesk, in one paragraph?

An AI agent that reads customer support tickets and either resolves them automatically
or hands them to a human — wrapped in the machinery that makes an AI *trustworthy*:
evidence logs for every decision, hard spending limits, safety rules enforced by code
rather than hope, and (in Week 2) measurement against human judgment. The AI is the
easy part. The trust machinery is the project.

---

## Issue #1 — Scaffolding + CI: *building the workshop before the furniture*

**Analogy:** before a carpenter builds anything, they set up the workshop: benches,
power, and — crucially — a smoke detector. This issue built the project's workshop:
the folder structure, the tools configuration, and **CI** (continuous integration) — a
robot that re-runs every test automatically each time code is pushed to GitHub. The
smoke detector that never sleeps.

**Dana's journey:** doesn't exist yet! No database, no AI, nowhere for her ticket to
live. But every future piece of code that will ever touch her ticket now gets
automatically tested before it's allowed in.

**Why it matters / builds on:** it's the foundation everything else stands on. Later in
the week, the smoke detector had a real moment: it turned out CI had been silently
failing for two days (a configuration subtlety) — catching and fixing *that* led to
"branch protection": GitHub now physically refuses to merge code whose tests aren't
green. The workshop enforces its own safety rules.

**Under the hood:** a Python project configured in `pyproject.toml`; **pytest** runs
the test suite and **ruff** enforces code style; a **GitHub Actions** workflow (the CI
robot) runs both on every push; a minimal **FastAPI** web app with a `/health`
endpoint proves the server skeleton works. Branch protection requires the CI check
named `test` to pass before any merge into `main`.

---

## Issue #2 — Database + ticket ingest: *the filing cabinet and 11,922 real letters*

**Analogy:** a support system needs a filing cabinet — organized drawers for tickets,
AI runs, evidence logs, knowledge articles, and review decisions (7 drawers total, each
with a labeled shape for what goes in it). Then we filled the ticket drawer with
**11,922 real customer support tickets** from a public dataset, so the system practices
on messy reality, not tidy invented examples.

**Dana's journey:** her ticket now has a home — a numbered folder in the cabinet with
her subject line, message, and status. Nothing has read it yet, but it exists and can't
get lost.

**Why it matters / builds on:** built inside the workshop from #1, tests and all. Using
real tickets is a deliberate credibility choice: any demo where the AI triages a ticket
is triaging the kind of ticket real support teams actually receive.

**Under the hood:** **PostgreSQL** database hosted on Neon's free tier; tables defined
as **SQLAlchemy 2.0** ORM models (tickets, runs, spans, kb_docs); schema changes are
versioned with **Alembic migrations** — think "git history, but for the database's
shape." The ingest script streams the 20,000-row Kaggle CSV and keeps the 11,922
English-language rows. The `runs` table is append-only with a one-way state machine:
`running → completed | escalated | failed`, one transition ever.

---

## Issue #3 — Tracing layer: *the flight recorder*

**Analogy:** airplanes carry a black box that records every instrument, every second,
so any incident can be reconstructed exactly. This issue built the black box: every
step the AI takes gets a **span** (a timed, structured log entry), every AI call's cost
is computed in dollars, and every run has a hard **$0.10 spending cap** — with a
crucial twist: if the cost *can't be computed*, the system treats that as overspending
and stops. Suspicion of a problem is treated as a problem ("fail closed").

**Dana's journey:** when her ticket eventually gets processed, every stage will leave a
flight-recorder entry: what the AI saw, what it decided, what it cost, how long it
took. When a human later asks "why did the AI escalate this?", the answer is on tape —
not vibes, evidence.

**Why it matters / builds on:** the cabinet (#2) stores *what happened*; the black box
records *why and at what cost*. This is the "glass-box" in the project's pitch — you
can always see inside. It also enforces one more rule: a run's story can only end once
(completed, escalated, or failed — never two endings), so the record can't be quietly
rewritten.

**Under the hood:** hand-rolled tracing (no vendor SDK): each pipeline stage writes a
**span** — a database row with start/end times and a JSON blob of attributes that
follow the **OpenTelemetry GenAI naming conventions** (`gen_ai.request.model`,
`gen_ai.usage.input_tokens`, …), the industry-standard vocabulary for describing AI
calls. Cost = token counts × a per-model price table, accumulated per run; a
`BudgetExceededError` stops the run over the $0.10 cap, and a `CostUnknownError` does
the same when cost *can't* be computed (fail closed). Spans are written incrementally,
so even a crash mid-run leaves a partial evidence trail.

---

## Issue #4 — Safety screening + sorting (precheck & classify): *the mail room*

**Analogy:** big offices route all mail through a mail room that does two things:
X-ray the package (is this dangerous? is someone trying to trick us?) and read the
address (which department handles this?). This issue built both AI stages — plus the
plumbing that forces the AI to answer in strict forms (exact checkboxes, not freeform
essays), with exactly **one** retry if the form comes back malformed, then escalation.

**Dana's journey:** her ticket enters the mail room. X-ray: legitimate customer issue,
no prompt-injection tricks — pass. Sorting: "Technical Support," and the sorter also
reports *how confident* it was between its top two choices (that confidence-gap number
becomes a key safety signal later, at the gate).

**Why it matters / builds on:** first issue where the AI actually reads tickets — and
where reality bit back. The form-checking code, though it passed all simulated tests,
turned out to be built on wrong assumptions about the AI provider's API. That failure
created the project's **SDK-reality rule**: never code against an API surface you
haven't personally observed live; capture the real response and build tests from it.
This rule earned its keep twice more during the week.

**Under the hood:** both stages call `claude-sonnet-4-6` through the official Anthropic
SDK using **structured outputs** — the API is handed a JSON Schema and constrained to
answer in exactly that shape — then the response is validated again locally with
**Pydantic** models (`PrecheckVerdict`, `ClassifyResult`). On validation failure, the
error text is fed back to the model in exactly **one** "repair" re-prompt, then the run
escalates (`validation_failed`). The classifier scores all 10 queue labels; the
**classification margin** — the gap between its top two choices — is the
confidence-gap signal the gate consumes later.

---

## Issue #5 — Knowledge base + retrieval: *the reference library and the librarian*

**Analogy:** a support agent is only as good as the manuals on the shelf. We wrote 15
knowledge-base articles (VPN troubleshooting, billing, entitlements policy…), then
converted each to an **embedding** — think of it as a point on a giant map where
similar meanings sit near each other. When a ticket arrives, the librarian places it on
the same map and pulls the **3 nearest articles**. No keyword matching — proximity of
meaning.

**Dana's journey:** her VPN-disconnection ticket lands on the map near the VPN
troubleshooting guide, the network diagnostics doc, and the support-plan entitlements
article. Those three go into the AI's briefing packet. How *close* the best match was
(the similarity score) is recorded — the second key safety signal for the gate.

**Why it matters / builds on:** the mail room (#4) knows *what kind* of ticket this is;
the library gives the AI *company-approved grounding* to answer from, instead of
improvising from general knowledge. Grounding + a measurable relevance score = both an
input and a safety signal.

**Under the hood:** each of the 15 authored markdown docs is converted to an
**embedding** — a 1,024-number vector from Voyage AI's `voyage-3.5-lite` model — and
stored in Postgres using the **pgvector** extension (no separate vector database:
one less moving part). Retrieval embeds the incoming ticket the same way and takes the
top **k=3** docs by **cosine similarity** (the math for "how close on the meaning
map"). Deliberately simple: whole-document embeddings, no chunking, no reranking —
each cut is a documented trade-off, and the best-match similarity score is persisted
per run as a gate signal.

---

## Issue #6 — Tools + the act loop: *the junior rep with two phone lines and a form*

**Analogy:** now the actual worker. Picture a junior support rep with a strict
protocol: two phone lines — one to look up the customer's account, one to check
whether their plan covers a feature — and one final form (`submit_resolution`) they
must file, exactly once, choosing **solve / deny / needs-human**. Max 5 rounds of
phone calls; failing to file the form in time doesn't error out — it escalates to a
human ("ran out of time" is itself an answer).

**Dana's journey:** the rep reads her ticket + the 3 library articles. Calls line 1:
account active, basic plan. Calls line 2: does basic include priority VPN support? →
**not covered**. The moment that "not covered" comes back, a flag is raised in the
system — *outside* the AI's control. The rep files the form with troubleshooting help
for the disconnections, and the flag follows the ticket to the gate.

**Why it matters / builds on:** this was gated on the SDK-reality rule from #4 — before
writing the loop, we ran a live probe of the AI provider's API and committed the real
responses as test fixtures. The probe caught something the plan hadn't predicted (the
AI sometimes uses both phone lines *simultaneously*), and review then caught an
ordering bug in exactly that scenario — where the denial flag could have been missed if
the rep filed the form in the same breath as a phone call. Fixed so evidence-gathering
always completes before the form is honored.

**Under the hood:** a hand-written **tool-use loop** on the raw Anthropic SDK — no
LangChain or agent framework, every line owned and explainable. The model is offered
three **tools** (functions it can request): `lookup_account_status` and
`check_entitlement` (simulated against a seeded accounts file — Dana is customer-3,
active, basic plan), plus `submit_resolution`, a **strict-schema** tool (the API
guarantees its arguments match the schema exactly). The loop runs at most 5
iterations with **adaptive extended thinking** enabled. The subtle fix: the model can
request several tools *in one turn*, so the loop partitions them — evidence tools
always execute (and can raise the `entitlement_denied` flag) before any
`submit_resolution` in the same turn is honored.

---

## Issue #7 — The confidence gate + the assembly line + the window: *the bouncer*

**Analogy:** the final checkpoint before an answer reaches a customer — a bouncer with
a strict, short rulebook checked in strict order: (1) is this bad news (a denial, or
that "not covered" flag from #6)? → a human delivers it, always, no matter how
confident the AI was. (2) Did the AI itself ask for a human? → done. (3) Are both
independent evidence signals strong — the sorting confidence-gap from #4 AND the
library-match score from #5? Only then does an answer auto-send. Critically, the
bouncer **never asks the AI how confident it feels** — self-ratings from AI models are
notoriously miscalibrated flattery. Only external, measurable signals count.

This issue also built the **runner** (the assembly-line manager that moves each ticket
through all 5 stations under one flight recording, mapping every possible failure to a
clean ending) and the **CLI** (a window: one command prints a run's full evidence
trail — every stage, every cost, the gate's reasoning).

**Dana's journey — the live finale:** her real ticket went through all five stations
with real AI calls. Screened ✅, sorted ✅, briefed ✅, worked ✅ (the "not covered" flag
raised), and at the gate: **escalated to a human, reason: adverse action.** The system
correctly refused to auto-deliver bad news. Total cost: about 3.6 cents, every step on
tape. That was Week 1's pass/fail criterion — met.

**Why it matters / builds on:** every previous issue feeds this moment — #4's
confidence-gap and #5's similarity are the gate's signals, #6's flag is its veto, #3's
black box is its evidence, #2's cabinet holds it all, #1's robot guards the code. One
more honest detail: both live runs' sorting-confidence signals were *below* the
auto-send bar — as configured, nothing auto-resolves yet. That's deliberate: the bars
are placeholder values, and Week 2's entire job is setting them from measured data
instead of guesses.

**Under the hood:** `gate.decide()` is a small **pure function** (same inputs → same
answer, no hidden state — trivially testable) over external signals only: retrieval
similarity ≥ 0.45, classification margin ≥ 0.02, plus the entitlement flags from the
act loop. The **runner** orchestrates all five stages under one trace and maps every
failure type to a terminal state (budget breach, validation failure, model refusal,
tool error, loop exhaustion, API error, and — post-QA — a catch-all so nothing can
strand a run mid-state). The **CLI** (`python -m triagedesk.cli run|trace`) executes a
ticket and prints the full evidence trail. The two live runs cost 3.1¢ and 3.6¢,
every span on record.

---

## Epilogue — the QA hardening (issue #28)

After Week 1 merged, we ran an adversarial review against our own finished work. It
found that the bouncer's #1 rule was *obeyed but not enforced* — the AI could have
slipped bad news past it by mislabeling. We closed that structurally (the "show your
receipt" rule) and hardened a dozen smaller things. Full story:
[2026-07-12-week1-qa-explained.md](2026-07-12-week1-qa-explained.md).

**The meta-lesson of Week 1** (the thread recruiters should hear): three separate
times, something that looked correct under simulated tests was wrong against reality.
Each time, the same response: verify against reality, capture the evidence, encode the
lesson as a permanent rule. That habit is the actual product.
