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

*Next: the console pages themselves (Task 2), then the review queue (Tasks 3–4).*
