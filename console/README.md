# TriageDesk Console

Thin, read-only ops console for TriageDesk. Next.js 15 (App Router) + TypeScript,
`create-next-app` defaults — no UI kit, no data-fetching library (plain `fetch`,
`cache: "no-store"`). All data comes from the FastAPI app in `../triagedesk`; the
console never touches the database directly.

## Pages

- `/` — run list: state, ticket subject, model, cost, latency, created time.
  Failed and escalated rows are highlighted but never hidden; clicking a row
  opens its detail page.
- `/runs/[id]` — run detail: summary header, gate signals (if present), a flat
  trace table (one row per span — no waterfall visualization, by design), the
  final reply, and the internal rationale (captioned as post-hoc context, never
  evidence).

## Running locally

1. Start the API (from the repo root):

   ```
   export TRIAGEDESK_ENV_FILE="C:\Users\Wonton Soup\.secrets\credentials.env"
   .venv/Scripts/python -m uvicorn triagedesk.app:app --port 8000
   ```

2. In `console/`, install deps and start the dev server:

   ```
   npm install
   npm run dev
   ```

3. Open http://localhost:3000. The console reads `NEXT_PUBLIC_API_URL` (default
   `http://localhost:8000`) — set it in `.env.local` to point elsewhere:

   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

## Build

```
npm run build
npm run lint
```
