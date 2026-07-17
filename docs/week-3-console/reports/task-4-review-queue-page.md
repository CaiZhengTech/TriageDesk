# Task 4: Console review queue page (issue #14, UI half)

## What was built

The operator-facing surface for the human-in-the-loop review queue: a page
that renders every escalated run with no decision yet, and lets an operator
approve or reject each one with a required note — the write path Task 3's
API already exposed.

- `console/lib/api.ts` — extended with `ReviewQueueItem` (extends
  `RunSummary` + `internal_rationale` + `final_reply`), `ReviewQueue`
  (`{items, total}`), `listReviewQueue()` (GET, same `cache: "no-store"`
  convention as `listRuns`/`getRun`), and `postReview(runId, decision, note,
  token)`. `postReview` does **not** throw on the status codes the UI must
  distinguish — it returns a discriminated union (`ReviewResult`: `ok` /
  `invalid_token` / `not_configured` / `already_reviewed` / `error`) so the
  caller can switch on outcome without try/catch-per-status. This follows
  the existing `getRun` precedent of handling one expected non-2xx status
  (404 → `null`) instead of throwing, just extended to the four statuses
  Task 3's contract defines.
- `console/app/review/page.tsx` — server component, mirrors `app/page.tsx`'s
  shape: fetches the queue with `listReviewQueue()`, a back-link to `/`, an
  explanatory paragraph (no-auth-system note), then hands the fetched
  `items`/`total` to the client component.
- `console/app/review/ReviewQueueClient.tsx` — client component owning
  state the server component can't: the operator-token field
  (`sessionStorage`-backed, restored on mount via `useEffect`), the live
  item list (items removed client-side on success), and a global banner for
  the 503 case. `refreshQueue()` re-fetches and replaces the list — used by
  the 409 path.
- `console/app/review/ReviewItem.tsx` — one queue row (client component, the
  `RunRow` pattern extended: local `note`/`submitting`/`error` state, since
  each row needs its own draft note and independent submit state). Shows
  ticket subject, escalation reason, cost/latency/created (extra context,
  cheap to include since the fields are already on the item), the draft
  `final_reply`, and `internal_rationale` captioned **exactly**
  "agent's post-hoc rationale — not evidence" (byte-for-byte match with
  Task 2's `runs/[id]/page.tsx`) — the non-negotiable rule that the LLM's
  rationale is never presented as evidence. A required note field (client
  validated before any network call — empty note never reaches
  `postReview`) plus Approve/Reject buttons.
- `console/app/page.tsx` — added a `Link` to `/review` near the top (`Review
  queue →`) for discoverability; `/review` already links back to `/`.

Response handling, mapped to `ReviewResult`:
- `ok` → `onResolved(runId)`: parent filters the item out of `items`.
- `invalid_token` → row shows "invalid operator token"; item stays (no
  removal, no refresh).
- `already_reviewed` (409) → row shows "already reviewed" and calls
  `onAlreadyReviewed`, which refetches the whole queue (the decided run is
  gone from the fresh response, so it disappears along with the refresh —
  not a separate client-side filter).
- `not_configured` (503) → row shows a message and the parent sets a
  page-level banner ("the server has no operator token configured —
  reviews cannot be submitted"); item stays.
- `error` (anything else, or a network failure) → generic
  `review failed: HTTP <status>` / `could not reach the API` message.

No new dependencies were added (`package.json` untouched besides being
read); plain `fetch`, inline styles + `globals.css` variables throughout,
matching Task 2's house style.

## API contract consumed (verbatim, per `triagedesk/app.py`)

- `GET /api/review-queue` → `{"items": [...RunSummary + internal_rationale +
  final_reply], "total": int}`.
- `POST /api/review/{run_id}` — body `{"decision": "approve"|"reject",
  "note": str}`, header `X-Admin-Token`. `201 {"id": int}` / `401` /
  `503` / `409` / `404` / `422`, in that check order server-side.

## Files changed

- `console/lib/api.ts` — `ReviewQueueItem`, `ReviewQueue`, `listReviewQueue`,
  `ReviewResult`, `postReview`
- `console/app/review/page.tsx` (new)
- `console/app/review/ReviewQueueClient.tsx` (new)
- `console/app/review/ReviewItem.tsx` (new)
- `console/app/page.tsx` — nav link to `/review`
- `docs/week-3-console/reports/task-4-review-queue-page.md` (this report)

## Build / lint output

```
$ npm run build
   ▲ Next.js 15.5.20 (Turbopack)
 ✓ Compiled successfully in 4.5s
 ✓ Generating static pages (6/6)

Route (app)                         Size  First Load JS
┌ ƒ /                             3.9 kB         119 kB
├ ○ /_not-found                      0 B         115 kB
├ ƒ /review                      5.14 kB         120 kB
└ ƒ /runs/[id]                   3.42 kB         118 kB
```

```
$ npm run lint
> eslint
(no output — clean)
```

## Manual verification (executed for real, against the local API)

Setup: `TRIAGEDESK_ENV_FILE` pointed at the real secrets file,
`uvicorn triagedesk.app:app --port 8000` (dev Neon branch), console on
`npm run dev` with `NEXT_PUBLIC_API_URL=http://localhost:8000`. Driven
through a real Chrome instance via the `agent-browser` skill (snapshot →
click/fill → re-snapshot), not just curl against the HTML.

**Environment finding, worth recording:** the console (`localhost:3000`)
and API (`localhost:8000`) are different origins. `GET` requests work fine
cross-origin (no preflight for a simple GET), which is why the queue
*renders* correctly with no extra setup. But `POST /api/review/{run_id}`
carries a custom `X-Admin-Token` header, which forces a CORS preflight
(`OPTIONS`) — and CORS middleware doesn't exist yet (`CORSMiddleware` is
Task 5, not yet built). The real `triagedesk/app.py`, unmodified, returns
`405` on that `OPTIONS` request, and the browser blocks the POST before it
ever reaches the server. This is expected given the plan's task order, not
a defect in this task's code — but it means the POST paths cannot be
exercised through a real browser against the *unmodified* app on two
different ports today.

To still get a genuine, unfaked end-to-end observation of the POST paths
(rather than settle for curl-only verification), I wrote a **test-only**
script (`cors_test_shim.py`, kept in this session's scratchpad, never
touched the repo) that imports the real `triagedesk.app:app` object
unmodified and wraps it with a permissive `CORSMiddleware` *in that
process only*, then serves it on port 8000 in place of plain `uvicorn
triagedesk.app:app`. Every route, model, and business-logic file is exactly
what's in this branch — only the process wrapper differs, and only for
this verification session. This is called out explicitly rather than
silently worked around, per the instruction not to claim something was
observed that wasn't; the actual repo's Task-5-shaped CORS gap is a known,
already-planned follow-up, not something this task papers over.

1. **Queue renders with real escalated rows.** `GET /review` (port 3000)
   rendered 223 real escalated-undecided runs (dev DB), oldest first. First
   row: `#12027 — My VPN keeps disconnecting` (the project's Dana-VPN
   ticket, adverse-action variant), `escalation reason: adverse_action ·
   cost 3.62¢ · latency 38.15s · created 7/12/2026, 5:09:16 AM`, the full
   draft reply text, an **Internal rationale** section captioned exactly
   "agent's post-hoc rationale — not evidence" above the rationale text, a
   required note field, and Approve/Reject buttons. Confirmed via browser
   snapshot + screenshot, not just curl.
2. **Approve with a note → removed from the queue (201).** Filled the
   operator token + a note on `#12027`'s row, clicked Approve. Network log
   showed `OPTIONS .../review/441299f4-... 200` then `POST
   .../review/441299f4-... 201`; the row disappeared from the rendered
   list immediately; `GET /api/review-queue` afterward confirmed
   `total: 222` (down from 223) and the run id no longer present. The
   write is permanent in the dev DB per the task's instructions.
3. **Reject with a note → removed from the queue.** Also tested the
   **required-note validation** first: clicked Approve on the next row
   (`#12039`) with an empty note — no network request fired, "a note is
   required" appeared under the buttons, item stayed. Filled a note and
   clicked Reject: `POST .../review/745a67c6-... 201`, row disappeared,
   `GET /api/review-queue` confirmed `total: 221`.
4. **Wrong-token path (401) — queue not cleared.** Set the operator-token
   field to `wrong-token-xyz`, clicked Approve on the current top row with
   a note filled: `POST .../review/522dce90-... 401`. UI showed "invalid
   operator token" directly under that row's buttons; the row **stayed** in
   the list (not removed); `GET /api/review-queue` confirmed `total`
   unchanged at 221.
5. **503 path — token unset server-side.** Restarted the API with
   `ADMIN_TOKEN` unset (confirmed via a direct curl: `POST
   /api/review/<id>` → `503 {"detail":"admin token not configured"}`
   before touching the browser). Reloaded `/review` (token still populated
   from `sessionStorage`, confirming that persistence works across a
   navigation in the same tab/origin), filled a note, clicked Approve:
   `POST .../review/53f27bf2-... 503`. UI showed both a **row-level**
   message ("server has no operator token configured — reviews are
   disabled") and a **page-level banner** ("the server has no operator
   token configured — reviews cannot be submitted"); the row was not
   removed. Reset `ADMIN_TOKEN` back before finishing (not needed further
   since verification was complete).

Also incidentally exercised the **409 "already reviewed"** path (not
explicitly in the required 5, but part of the binding acceptance criteria):
decided a currently-displayed run out-of-band via a direct `curl` POST
(simulating a second operator/tab winning a race), then clicked Approve on
that same still-rendered row in the UI with the correct token: `POST
.../review/522dce90-... 409`, followed automatically by `GET
/api/review-queue 200` (the `onAlreadyReviewed` → `refreshQueue()` path).
The row showed "already reviewed" and then the whole list refreshed to the
server's current state, taking that row (and the other out-of-band-decided
run) out of view. Confirmed via the network log and a before/after
`total` count.

All five required observations plus the 409 path were driven through a
real, running browser session (`agent-browser`), not simulated — see the
screenshots taken during the session for the note-required, 401, and 503
states.

## Decisions / tradeoffs

- **`ReviewResult` discriminated union instead of throwing.** The brief
  requires four distinct UI reactions (success / 401 / 409 / 503) plus a
  catch-all; a thrown `Error` per status would push string-matching or a
  custom error class onto the caller. A typed return value keeps
  `ReviewItem`'s `switch` exhaustive and readable, and mirrors the existing
  `getRun` precedent of special-casing one expected status instead of
  throwing.
- **Per-row local state instead of a parent-owned map.** Each row's note
  text, submit-in-flight flag, and error message live in `ReviewItem`
  itself rather than in an array/map in `ReviewQueueClient`. Simpler code,
  no key-management for note drafts, and matches the `RunRow` precedent of
  keeping interaction-only state local to the smallest component that
  needs it.
- **Extra context fields shown per row (cost/latency/created), beyond the
  four the brief names.** These are already present on `ReviewQueueItem`
  (it extends `RunSummary`) — surfacing them costs nothing extra and gives
  an operator more to go on before deciding. Not gold-plating: no new
  fetch, no new endpoint, no layout restructuring.
- **Global banner + per-row message for 503, not one or the other.** The
  503 case is a systemic condition (nothing in the queue is submittable
  until the server is reconfigured), so a page-level banner communicates
  that clearly; the per-row message keeps the failure visible at the point
  of action too. Small duplication, deliberate.

## Known gaps

- **CORS is still Task 5's job.** As documented above, the console and API
  on two different localhost ports cannot complete a real POST today
  without CORS middleware — this is expected (the plan explicitly slates
  CORS for Task 5), not a defect introduced here, but it means "run it
  locally on two ports" won't demo the write path until Task 5 lands. The
  verification above used a test-only, uncommitted process wrapper to
  prove the actual page/route code is correct; nothing in this branch
  works around or depends on that wrapper.
- **No pagination on the queue page**, matching Task 3's already-recorded
  concern that `GET /api/review-queue` returns everything in one response
  (223 rows today) — this task renders all of them in one scroll. Given the
  existing queue size this is usable but a long scroll; if the queue grows
  further, pagination is a small follow-up on both the API and this page,
  not a redesign.
- **The 409 "already reviewed" message is momentary by design** — the
  moment `refreshQueue()` completes, the resolved item's component
  unmounts along with its message, since the list is replaced wholesale
  rather than patched. This matches the acceptance criteria's wording
  ("shows ... and refreshes the list") but means the message is visible
  only briefly, not left standing.
