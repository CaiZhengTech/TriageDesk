# Week 3 — The Glass Box Gets a Window (the plain-language story)

*Same format as Weeks 1–2: every task gets an analogy, Dana's journey, and an
"under the hood" layer. Written so a non-technical recruiter can follow it.*

Two weeks of flight-recorder data exist — every run, every stage, every cent — but only
a terminal command can see it. Week 3 builds the window: a small web console (run list →
run detail → review queue), then puts the whole system on the public internet behind
sensible abuse protection. The console is deliberately thin: it only *reads through the
API*, and it never hides a failure.

---

## Task 1 — The runs API: *the kitchen pass-through* (✅ merged, PR #50, refs #13)

**Analogy:** a restaurant that wants a window into its kitchen doesn't knock a hole in
the wall wherever a diner is standing — it builds one pass-through counter, and
everything the dining room sees comes across it. This task built that counter: two API
endpoints (`/api/runs` and `/api/runs/{id}`) that are now the ONLY way the console will
ever see data. No page will ever query the database directly — one door, so the rules
that come later (the review queue's operator token, the demo's spend cap) can never be
walked around.

**Dana's journey:** Dana's run is now one HTTP call away: `GET /api/runs` returns her
row — escalated, 3¢, 32 seconds — and `GET /api/runs/{her-run-id}` returns the whole
story: five stages with per-stage duration, tokens, and cost, the gate's signals, the
draft reply, and the agent's rationale (labeled as post-hoc context, never evidence).

**Under the hood:** the queries live in one new module (`console_queries.py`), and the
routes stay four lines each. Two old landmines were defused on the way: the
naive-vs-aware timestamp mismatch that once crashed a live eval run is handled by one
normalizing helper (unit-tested both ways), and failed runs are structurally impossible
to filter out of the list — the "no hidden failures" rule is a design property, not a
promise. Seven TDD tests, $0 spent, review clean on the first pass.

---

## Task 2 — The window itself: run list + run detail (✅ merged, PR #51, closes #13)

**Analogy:** Task 1 built the kitchen's pass-through counter; this task built the dining
room that looks through it. Two pages, deliberately plain: a run list — every pipeline
run as a row with its state, cost, latency, and model — and a run detail page where one
click opens the full flight recording. No charts, no animation, no dashboard theater:
the honesty IS the aesthetic. Escalated and failed runs are tinted so they stand out,
and there is structurally no way to hide them — the page renders whatever the API
returns, and the API has no filter.

**Dana's journey:** her VPN ticket's run is a row: `escalated · 3.2¢ · 32s`. Click it
and you watch the agent think — five stages in a flat table (duration, tokens, cost per
stage), the gate's two signals, the draft reply the agent wrote, and its explanation of
why it asked for a human. That explanation is captioned on the page exactly as the
design rules demand: *"agent's post-hoc rationale — not evidence."* Even the UI keeps
the epistemology straight.

**Under the hood:** Next.js 15, TypeScript, zero libraries beyond the scaffold — the
whole console is two server-rendered pages, one client row component, and ~100 lines of
CSS. The response types in `lib/api.ts` were verified field-for-field against the
Python API source (the reviewer re-checked byte-for-byte). The review's one Important
finding — an unreachable API fell through to the framework's generic crash page — was
fixed with a proper error boundary that says plainly "Can't reach the TriageDesk API"
and offers a retry; a glass-box console shouldn't get vague exactly when things break.
Verified against the real dev database: an escalated run (Dana's), a failed run (the
Week-1 `additionalProperties` incident, still visible, error and all), and a genuine
404. One honest footnote: the dev DB currently contains zero *completed* runs — the
system still escalates everything by design — so that rendering path is code-verified
until a completed run exists to click.

---

## Task 3 — The doctor's inbox exists now (✅ merged, PR #52, refs #14)

**Analogy:** for two weeks the triage nurse (the pipeline) has been stamping charts
"needs a doctor" — the adverse-action rule, the confidence gate, the model's own
caution all end in that stamp. But a stamp is meaningless if there's no doctor's inbox.
This task built the inbox: a `review_decisions` table (the doctor's signature line — one
verdict per case, enforced by the database itself) and two API endpoints — one that
lists every escalated run still awaiting a human, oldest first, and one that records
approve/reject with a note.

**Dana's journey:** her dedicated-IP denial has been sitting in `state='escalated'`
since Week 1. It now appears in `GET /api/review-queue` with the draft reply and the
agent's reasoning attached — and when a human posts their verdict, the queue drops it
and the decision is permanent (a second verdict on the same run gets a polite 409
"already reviewed", backed by a database uniqueness constraint, not an if-statement).

**Under the hood (the lock on the door):** the write endpoint requires an operator
token — and it **fails closed**: if the server has no token configured, the endpoint
returns "service unavailable" rather than treating empty-as-open. That ordering (503
before the token is even compared) is the same fail-closed philosophy as the cost caps,
applied to auth. TDD throughout (five red→green steps), the migration round-trip proven
against the real test database, review clean on the first pass.

---

*Next: Task 4 — the queue page itself, so the inbox has a screen. Then (next session):
deploy + demo protection.*
