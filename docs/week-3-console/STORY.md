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

## Task 4 — The doctor sits down at the desk (✅ merged, PR #53, closes #14)

**Analogy:** Task 3 built the doctor's inbox — the table where flagged cases land and the
lock on who may sign them off. But an inbox with no screen is just a database. This task
built the desk the doctor actually sits at: a web page that lists every waiting case as a
card — the patient's complaint (ticket subject), why the nurse flagged it (escalation
reason), the reply the AI drafted, and the nurse's chart-note (the agent's reasoning,
captioned so no one mistakes it for evidence). The doctor types a note, clicks approve or
reject, and the card disappears — signed, permanent.

**Dana's journey:** her dedicated-IP denial has waited in the queue since Week 1. Now it's
a card on the review page: subject, "escalated — adverse action", the draft reply, and the
agent's post-hoc rationale under the exact caption the design rules demand. The operator
types "correctly identified plan limitation", clicks **Approve** — the page sends the
verdict with the operator token, the server records it, and the card vanishes from the
queue (the count ticks down by one). Try to approve without a note and the page refuses
before it ever touches the network. Type the wrong token and it says "invalid operator
token" and leaves the queue exactly as it was — nothing lost, nothing guessed.

**Under the hood:** a thin Next.js page — one server component that fetches the queue, one
client component that owns the operator-token field (kept in the browser's `sessionStorage`,
never sent anywhere but the `X-Admin-Token` header), and one row component per case with
its note field and buttons. The careful bit is honest error handling: instead of throwing
on a bad response, the fetch helper returns a *labeled* result — `ok`, `invalid_token`,
`already_reviewed`, `not_configured` — so the page reacts precisely to each of the four
outcomes Task 3's API defines (201 success, 401 wrong token, 409 already-decided → refresh
the list, 503 no-token-configured → say so plainly). Every one of those five paths was
verified through a *real browser*, not a curl script: approve (queue 223→222), reject
(→221), wrong-token (401, queue untouched), unset-token (503), and a 409 triggered by
deciding a row out-of-band and then submitting it (→ automatic refresh). Zero new
dependencies; the page is plain `fetch` and the same CSS variables as the rest of the
console. **One honest, correctly-scoped gap:** because the console and the API are
different origins, the browser sends a CORS "preflight" before the POST — and the real app
doesn't answer it yet, because CORS is Task 5's job. It's flagged in the report and the PR,
not worked around. The review's one Minor finding (a dead CSS class that highlighted
nothing) was fixed in the same PR. **Issue #14 is now complete — the promise the pipeline
has been making since Week 1, that a human reviews every denial, finally has a human-usable
screen.**

---

## Task 5 — Wiring the house for the move (✅ merged, PR #54, refs #15)

**Analogy:** the console and the API are about to move out of the laptop and into two
different buildings on the internet (Vercel and Railway). Two bits of unglamorous wiring
have to exist before the move. First, the **doorbell rules**: browsers won't let a page in
one building talk to an API in another unless the API explicitly names who may call —
that's CORS. The rule here fails closed: if no guest list is configured, *nobody* outside
gets in; there is no "allow everyone" setting anywhere in the code. Second, the **flight
recorder's voice**: in production, logs get read by machines, not scrolled by humans — so
the app can switch to one-line JSON log entries a log service can filter, timestamped in
UTC.

**Dana's journey:** when the review page approves Dana's escalation from the deployed
console, the browser first knocks on the API's door and asks "may a page from this address
POST here, carrying an operator token?" Before this task the API didn't answer that knock
at all — the very gap Task 4 flagged. Now it answers precisely: yes to the configured
console address, with exactly those headers — and silence to everyone else.

**Under the hood:** Starlette's `CORSMiddleware` (ships with FastAPI — zero new
dependencies), registered only when `CORS_ORIGINS` is non-empty, no wildcards, and only
the methods and headers the console actually uses. A stdlib JSON formatter
(`logging_setup.py`) emits `{"ts", "level", "logger", "msg"}` lines when `LOG_JSON` is on.
TDD throughout; the review's one Important finding was a good one: the CORS tests
preflighted a GET endpoint, but the request that matters is the review page's POST with
its operator-token header — so a test now pins that exact browser-real preflight, meaning
no future edit can quietly re-break the review queue in production. 207 tests green. One
process story worth keeping: this PR's CI failed once on a duplicate-key error that had
nothing to do with the change — two copies of the test suite (a local review run and CI)
had raced each other on the shared test database. Diagnosed from the timeline, re-run
green; the lesson (don't run local integration tests while CI is mid-flight) is in the
ledger.

---

## Task 7 — The bouncer at the open bar (✅ merged, PR #55, closes #16)

**Analogy:** a public demo with a paid AI behind it is an open bar with your credit card
behind it. This task hired the bouncer and wrote the house rules. **The fixed menu:**
visitors pick from a small pool of seeded tickets — there is no text box anywhere, so
nobody can order off-menu (which also closes the front-door prompt-injection channel).
**The per-person limit:** one IP gets a handful of runs per hour. **The honest
"kitchen closed" sign:** a hard daily dollar cap, checked *before* any money is spent —
cross it and the demo visibly pauses with "Daily demo budget reached — watch the video
instead." No recording dressed up as a live run; the council killed that idea as
deception in miniature.

**Dana's journey:** a visitor picks Dana's VPN ticket from the dropdown and watches the
real pipeline run it — real model, real trace, ~3¢. A bored visitor hammering the button
hits the hourly limit and gets told so. And when the day's budget is gone, the next
visitor doesn't get a fake — they get the honest pause banner.

**Under the hood:** one new module (`demo.py`) holds the three guards: the pool query
(`source='demo'` only), a fixed-window rate limiter whose clock is injected (so tests
drive window resets deterministically), and the daily-cap query — spent-today (UTC,
tz-explicit on the naive column) plus one per-run cap must stay under the daily cap,
fail closed. All three run BEFORE the pipeline is invoked; unit tests assert the
pipeline function is literally never called on any blocked branch. The review earned its
keep here: it asked what happens when several requests arrive at once — and the honest
answer was that they could all pass the cap check before any of them had spent anything
(the classic time-of-check/time-of-use race, on the money path of a public endpoint).
The fix: demo dispatch is serialized — one demo run at a time on this instance — so the
cap check always sees committed costs and the overspend window closes to zero. The
regression test was proven the right way: the reviewer independently removed the lock
and watched the double-spend appear five times out of five, then restored it and watched
serialization hold five times out of five. Plus `scripts/smoke.py` — the turn-the-key
script Task 6 will run against production: send one seeded ticket through the deployed
API, poll to a terminal state, exit green only if the run finished AND recorded real
cost. 206 unit tests green.

---

*Next: Task 6 — the live deploy (Railway + Neon + Vercel), a joint session with Cai
(needs his accounts). The smoke script and the env-var checklist are ready.*
