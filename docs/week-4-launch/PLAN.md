# Week 4 PLAN — #56 Console Redesign ("Flight Recorder")

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the four console pages (+ a new landing page) into the
"flight recorder" identity chosen in the #56 brainstorm — dark-only instrument
panel, mono-first type, amber/green/red state lights — without weakening any
honesty rule.

**Architecture:** Pure presentation pass on `console/**`: a token system in
`globals.css`, fonts via `next/font/google` (build-time, zero runtime deps), a
shared recorder header in `layout.tsx`, a new cockpit-stack landing page at `/`
(run list moves to `/runs`), and class-swap restyles of the existing pages. No
API changes, no auth changes, no data library.

**Tech Stack:** Next.js (existing), hand-rolled CSS custom properties,
`next/font/google` (IBM Plex Mono + IBM Plex Sans). **No Tailwind, no new
`package.json` dependencies.**

## Decisions on record (brainstorm 2026-07-18, session `.superpowers/brainstorm/1609-1784348706`)

- **Identity:** B — flight recorder, **dark-only** (the issue's "dark mode
  optional" is resolved as dark-ONLY; `color-scheme: dark`, no light theme).
- **Motion:** micro-interactions (150–250ms, strong ease-out) + ONE
  orchestrated boot-sequence moment on the landing hero. Nothing else animates
  big. `prefers-reduced-motion` respected everywhere.
- **Landing layout:** 1 — cockpit stack (centered thesis → 4 instrument stats
  → two CTAs → live ticker of real runs).
- **CSS approach (the issue's "decide at pickup"):** hand-rolled CSS in
  `globals.css`. Reasoning: keeps the council's zero-dependency cut fully
  intact, the surface is 5 pages / ~1 stylesheet so a utility framework buys
  nothing, and "no framework anywhere" stays a clean interview line.
- **Copy divergence from mockup:** the landing stat is **2.9¢ AVG COST / RUN**
  (the documented headline in CLAUDE.md/PITCH), not the mockup's 3.6¢ (that was
  the single prod smoke run $0.0355). Quote the record, not the sketch.

## Global Constraints

- `console/**` and `docs/**` only ⇒ **$0 eval gate**. Never touch `triagedesk/`,
  `tests/`, `.github/`.
- **No new entries in `console/package.json` `dependencies` or `devDependencies`.**
  `next/font` ships with Next.
- **Honesty rules are design constraints (issue #56 AC):**
  - failed/escalated states stay loud — tint + 3px state rail + colored badge;
    a redesign that makes a failed run harder to spot is wrong, not the rule.
  - the caption string `agent's post-hoc rationale — not evidence` stays
    **byte-for-byte verbatim in markup** (Task-4 reviewer precedent) and gets
    MORE prominent (amber outlined chip), never minimized.
  - the demo pause banner becomes a filled amber block — unmistakable.
- Contrast: smallest muted text uses `--muted: #7d8a96` (≈5.2:1 on `--bg`);
  `--faint: #5d6b78` (≈3.6:1) is allowed ONLY for decorative marks, never for
  text that carries information.
- Motion: only `transform`/`opacity` animate; no animation on keyboard-driven
  actions; hover effects gated behind `@media (hover: hover) and (pointer: fine)`;
  all entrance animation disabled under `prefers-reduced-motion: reduce`.
- Verification per task: `cd console; npm run build` must succeed (this also
  runs lint). No test framework exists in `console/` — the verify loop is
  build + screenshot inspection (agent-browser), matching Week 3 practice.
- Screenshots run the dev server against the LIVE API (read-only GETs = $0):
  PowerShell: `$env:NEXT_PUBLIC_API_URL = "https://agenticproject-production.up.railway.app"; npm run dev`
- Branch: `feat/56-console-redesign` (exists, at main). PR references #56.
- Commits end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## Design tokens (single source — every color/type choice below derives from these)

| Token | Value | Role |
|---|---|---|
| `--bg` | `#0b0e11` | page background |
| `--surface` | `#11151a` | panels/cards |
| `--surface-2` | `#12171d` | rows, inputs, secondary buttons |
| `--border` | `#232b33` | panel borders |
| `--border-subtle` | `#1c232b` | row separators, header rule |
| `--text` | `#e8edf2` | primary text |
| `--text-dim` | `#9daebc` | secondary text |
| `--muted` | `#7d8a96` | smallest readable muted text |
| `--faint` | `#5d6b78` | decorative only |
| `--amber` | `#ffb454` | escalated / warning / primary CTA |
| `--green` | `#7fd962` | completed / ok |
| `--red` | `#f26d78` | failed / errors / REC dot |

Type: **IBM Plex Mono** (all UI chrome, headings, data — the instrument voice),
**IBM Plex Sans** (long prose only: draft replies, rationale bodies — class
`.prose`). Uppercase micro-labels (`.eyebrow`) at 10px / `.1em+` tracking are
the structural device. Signature elements: the `TRIAGEDESK ● REC` header, the
state rails, the landing boot sequence.

---

### Task 0: Baseline ("before") screenshots

**Files:**
- Create: `docs/week-4-launch/reports/assets/before-landing.png` (current run
  list at `/`), `before-run-detail.png`, `before-review.png`, `before-demo.png`

**Interfaces:** Produces the "before" half of the issue's screenshot AC. Must
run BEFORE any code change.

- [ ] **Step 1:** Start the dev server (background):
  PowerShell in `console/`: `$env:NEXT_PUBLIC_API_URL = "https://agenticproject-production.up.railway.app"; npm run dev`
- [ ] **Step 2:** Using the **agent-browser** skill, open and screenshot at
  1440×900: `http://localhost:3000/`, one run-detail page (click the first
  row), `/review`, `/demo`. Save to the asset paths above.
- [ ] **Step 3:** Commit:
  `git add docs/week-4-launch/reports/assets && git commit -m "docs: #56 before screenshots"`

---

### Task 1: Token system, fonts, shared recorder chrome

**Files:**
- Modify: `console/app/globals.css` (full rewrite below)
- Modify: `console/app/layout.tsx` (fonts + header)
- Create: `console/app/SiteHeader.tsx`
- Modify: `console/lib/format.ts:34-38` (`badge-completed`)
- Modify: `console/app/error.tsx` (old token names die here)

**Interfaces:**
- Produces (all later tasks rely on these exact class names): `.eyebrow`,
  `.panel`, `.panel-pad`, `.prose`, `.badge`/`.badge-escalated`/`.badge-failed`/
  `.badge-completed`, `.btn`/`.btn-primary`/`.btn-approve`/`.btn-reject`,
  `.error-text`, `.pause-banner`, `.rationale-caption`, `.review-card`,
  `.row-escalated`/`.row-failed`, `.hero`, `.hero-sub`, `.stats`, `.stat`,
  `.stat-amber`, `.stat-green`, `.stat-value`, `.stat-label`, `.ctas`,
  `.ticker`, `.ticker-row`, `.ticker-state`, `.boot`, `.boot-1`…`.boot-11`.
- Kills: `--background`, `--foreground`, `--escalated-bg/border`,
  `--failed-bg/border` (error.tsx is their only consumer outside globals).

- [ ] **Step 1:** Replace `console/app/globals.css` entirely with:

```css
/* Flight-recorder identity (#56) — dark-only.
   Honesty rules are design constraints: failed/escalated stay loud, the
   rationale caption stays prominent, the pause banner stays unmistakable. */

:root {
  --bg: #0b0e11;
  --surface: #11151a;
  --surface-2: #12171d;
  --border: #232b33;
  --border-subtle: #1c232b;
  --text: #e8edf2;
  --text-dim: #9daebc;
  --muted: #7d8a96;
  --faint: #5d6b78;
  --amber: #ffb454;
  --amber-tint: rgba(255, 180, 84, 0.07);
  --green: #7fd962;
  --green-tint: rgba(127, 217, 98, 0.08);
  --red: #f26d78;
  --red-tint: rgba(242, 109, 120, 0.07);
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
  color-scheme: dark;
}

* {
  box-sizing: border-box;
}

html,
body {
  max-width: 100vw;
  overflow-x: hidden;
}

body {
  margin: 0;
  padding: 0;
  color: var(--text);
  background: var(--bg);
  font-family: var(--font-mono), ui-monospace, "Cascadia Code", Consolas,
    monospace;
  font-size: 14px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

main {
  padding: 2rem 1.5rem 4rem;
  max-width: 1100px;
  margin: 0 auto;
}

h1 {
  font-size: 1.3rem;
  letter-spacing: -0.01em;
  font-weight: 600;
}

h3,
h4 {
  font-weight: 600;
}

a {
  color: inherit;
}

code {
  font-family: inherit;
  color: var(--text-dim);
}

.prose {
  font-family: var(--font-sans), system-ui, sans-serif;
  font-size: 0.95rem;
  line-height: 1.6;
}

.eyebrow {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
}

.muted {
  color: var(--muted);
}

.error-text {
  color: var(--red);
}

/* ---- recorder chrome ---- */

.site-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.7rem 1.5rem;
  border-bottom: 1px solid var(--border-subtle);
  position: sticky;
  top: 0;
  background: rgba(11, 14, 17, 0.92);
  backdrop-filter: blur(6px);
  z-index: 10;
}

.brand {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--text-dim);
  text-decoration: none;
  white-space: nowrap;
}

.rec-dot {
  color: var(--red);
  font-size: 9px;
  animation: rec-pulse 2.4s ease-in-out infinite;
}

@keyframes rec-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

.site-header nav {
  display: flex;
  gap: 1.25rem;
}

.site-header nav a {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  text-decoration: none;
  color: var(--muted);
  transition: color 150ms var(--ease-out);
}

@media (hover: hover) and (pointer: fine) {
  .site-header nav a:hover {
    color: var(--text);
  }
}

/* ---- panels ---- */

.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 1.5rem;
}

.panel-pad {
  padding: 1rem 1.25rem;
}

.panel .eyebrow {
  display: block;
  padding: 0.7rem 1.25rem 0;
}

/* ---- tables ---- */

table {
  border-collapse: collapse;
  width: 100%;
}

th,
td {
  border: 0;
  border-bottom: 1px solid var(--border-subtle);
  padding: 0.6rem 0.85rem;
  text-align: left;
  font-size: 0.85rem;
}

tr:last-child th,
tr:last-child td {
  border-bottom: 0;
}

thead th {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
}

tbody th {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  width: 200px;
  vertical-align: top;
}

tbody tr {
  transition: background 150ms var(--ease-out);
}

/* state rows: tint + 3px rail — loud by design, never hidden */
tr.row-escalated td {
  background: var(--amber-tint);
}

tr.row-escalated td:first-child {
  box-shadow: inset 3px 0 0 var(--amber);
}

tr.row-failed td {
  background: var(--red-tint);
}

tr.row-failed td:first-child {
  box-shadow: inset 3px 0 0 var(--red);
}

@media (hover: hover) and (pointer: fine) {
  tbody tr:hover td {
    background: var(--surface-2);
  }
  tr.row-escalated:hover td {
    background: rgba(255, 180, 84, 0.12);
  }
  tr.row-failed:hover td {
    background: rgba(242, 109, 120, 0.12);
  }
}

/* ---- badges ---- */

.badge {
  display: inline-block;
  padding: 0.1rem 0.55rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border: 1px solid var(--border);
  color: var(--text-dim);
}

.badge-escalated {
  border-color: var(--amber);
  color: var(--amber);
  background: var(--amber-tint);
}

.badge-failed {
  border-color: var(--red);
  color: var(--red);
  background: var(--red-tint);
}

.badge-completed {
  border-color: var(--green);
  color: var(--green);
  background: var(--green-tint);
}

/* ---- controls ---- */

button,
.btn {
  display: inline-block;
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 0.45rem 1rem;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text);
  text-decoration: none;
  cursor: pointer;
  transition: transform 160ms var(--ease-out),
    border-color 150ms var(--ease-out), background 150ms var(--ease-out);
}

button:active,
.btn:active {
  transform: scale(0.97);
}

button:disabled {
  opacity: 0.5;
  cursor: default;
  transform: none;
}

.btn-primary {
  background: var(--amber);
  border-color: var(--amber);
  color: #0b0e11;
}

.btn-approve {
  background: transparent;
  border-color: var(--green);
  color: var(--green);
}

.btn-reject {
  background: transparent;
  border-color: var(--red);
  color: var(--red);
}

@media (hover: hover) and (pointer: fine) {
  button:hover,
  .btn:hover {
    border-color: var(--muted);
  }
  .btn-primary:hover {
    border-color: var(--amber);
    background: #ffc06e;
  }
  .btn-approve:hover {
    background: var(--green-tint);
    border-color: var(--green);
  }
  .btn-reject:hover {
    background: var(--red-tint);
    border-color: var(--red);
  }
}

input,
select,
textarea {
  font-family: inherit;
  font-size: 0.85rem;
  color: var(--text);
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.5rem 0.6rem;
}

input:focus-visible,
select:focus-visible,
textarea:focus-visible,
button:focus-visible,
a:focus-visible {
  outline: 2px solid var(--amber);
  outline-offset: 2px;
}

label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
}

/* ---- honesty fixtures ---- */

/* Styled MORE prominent, never minimized (issue #56 AC). Markup text stays
   byte-for-byte: "agent's post-hoc rationale — not evidence" */
.rationale-caption {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 600;
  font-style: normal;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--amber);
  border: 1px solid var(--amber);
  border-radius: 3px;
  background: var(--amber-tint);
  padding: 0.15rem 0.5rem;
  margin: 0 0 0.6rem 0;
}

.pause-banner {
  background: var(--amber);
  color: #0b0e11;
  font-weight: 700;
  font-size: 0.95rem;
  padding: 1rem 1.25rem;
  border-radius: 6px;
  margin: 1rem 0;
}

.review-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--amber);
  border-radius: 6px;
}

/* ---- landing (cockpit stack) ---- */

.hero {
  text-align: center;
  padding: 4rem 1rem 2.5rem;
}

.hero h1 {
  font-size: clamp(1.6rem, 4vw, 2.4rem);
  margin: 0.8rem 0 0.6rem;
}

.hero-sub {
  color: var(--muted);
  max-width: 580px;
  margin: 0 auto;
  font-size: 0.9rem;
}

.stats {
  display: flex;
  justify-content: center;
  gap: 2.5rem;
  flex-wrap: wrap;
  margin: 2.2rem 0;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 600;
}

.stat-label {
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  margin-top: 0.2rem;
}

.stat-amber .stat-value {
  color: var(--amber);
}

.stat-green .stat-value {
  color: var(--green);
}

.ctas {
  display: flex;
  gap: 0.9rem;
  justify-content: center;
  flex-wrap: wrap;
}

.ticker {
  border-top: 1px solid var(--border-subtle);
  margin-top: 3rem;
  padding-top: 1.2rem;
}

.ticker-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
  padding: 0.55rem 0.75rem;
  margin-top: 0.4rem;
  background: var(--surface-2);
  border-left: 2px solid var(--border);
  border-radius: 0 4px 4px 0;
  text-decoration: none;
  font-size: 0.85rem;
  transition: background 150ms var(--ease-out);
}

.ticker-row.escalated {
  border-left-color: var(--amber);
}

.ticker-row.failed {
  border-left-color: var(--red);
}

.ticker-row.completed {
  border-left-color: var(--green);
}

@media (hover: hover) and (pointer: fine) {
  .ticker-row:hover {
    background: var(--surface);
  }
}

.ticker-state {
  font-size: 0.75rem;
  color: var(--muted);
  white-space: nowrap;
}

.ticker-state.escalated {
  color: var(--amber);
}

.ticker-state.failed {
  color: var(--red);
}

.ticker-state.completed {
  color: var(--green);
}

/* ---- boot sequence (landing only; rare page ⇒ delight is allowed) ---- */

.boot {
  opacity: 0;
  transform: translateY(6px);
  animation: boot-in 480ms var(--ease-out) forwards;
}

@keyframes boot-in {
  to {
    opacity: 1;
    transform: none;
  }
}

.boot-1 { animation-delay: 0ms; }
.boot-2 { animation-delay: 70ms; }
.boot-3 { animation-delay: 140ms; }
.boot-4 { animation-delay: 240ms; }
.boot-5 { animation-delay: 300ms; }
.boot-6 { animation-delay: 360ms; }
.boot-7 { animation-delay: 420ms; }
.boot-8 { animation-delay: 520ms; }
.boot-9 { animation-delay: 640ms; }
.boot-10 { animation-delay: 700ms; }
.boot-11 { animation-delay: 760ms; }

@media (prefers-reduced-motion: reduce) {
  .boot {
    animation: none;
    opacity: 1;
    transform: none;
  }
  .rec-dot {
    animation: none;
  }
  button,
  .btn,
  .ticker-row,
  tbody tr,
  .site-header nav a {
    transition: none;
  }
}
```

- [ ] **Step 2:** Replace `console/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";
import SiteHeader from "./SiteHeader";

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-mono",
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "TriageDesk Console",
  description: "Glass-box ops console for the TriageDesk triage agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${plexMono.variable} ${plexSans.variable}`}>
      <body>
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 3:** Create `console/app/SiteHeader.tsx`:

```tsx
import Link from "next/link";

/** Shared recorder chrome: brand + the only nav on the site. */
export default function SiteHeader() {
  return (
    <header className="site-header">
      <Link href="/" className="brand">
        TRIAGEDESK <span className="rec-dot" aria-hidden="true">●</span> REC
      </Link>
      <nav>
        <Link href="/runs">Runs</Link>
        <Link href="/review">Review</Link>
        <Link href="/demo">Demo</Link>
      </nav>
    </header>
  );
}
```

- [ ] **Step 4:** In `console/lib/format.ts`, replace `stateBadgeClass` with:

```ts
export function stateBadgeClass(state: string): string {
  if (state === "escalated") return "badge badge-escalated";
  if (state === "failed") return "badge badge-failed";
  if (state === "completed") return "badge badge-completed";
  return "badge";
}
```

- [ ] **Step 5:** Replace `console/app/error.tsx` (dead token names → new
  classes) with:

```tsx
"use client";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main>
      <h1>Can&apos;t reach the TriageDesk API</h1>
      <p className="muted">
        The run data couldn&apos;t be loaded — check that the API is up and{" "}
        <code>NEXT_PUBLIC_API_URL</code> is correct.
      </p>
      <div
        className="panel panel-pad error-text"
        style={{ borderColor: "var(--red)", overflowX: "auto" }}
      >
        <code>{error.message}</code>
      </div>
      <button onClick={reset}>Try again</button>
    </main>
  );
}
```

- [ ] **Step 6:** Verify: `cd console; npm run build` — expected: build
  succeeds, no lint errors. Load `http://localhost:3000/` in the dev server:
  dark chrome + header render; the (still-unstyled-content) pages remain
  functional.
- [ ] **Step 7:** Commit:
  `git add console && git commit -m "feat(#56): flight-recorder tokens, fonts, shared chrome"`

---

### Task 2: Landing page (cockpit stack) + run list moves to /runs

**Files:**
- Move: `console/app/page.tsx` → `console/app/runs/page.tsx` (git mv, then
  restyle in place — final content below)
- Move: `console/app/RunRow.tsx` → `console/app/runs/RunRow.tsx`
- Create: `console/app/page.tsx` (the new landing)
- Modify: `console/app/runs/[id]/page.tsx:26` (back link `/` → `/runs`)

**Interfaces:**
- Consumes: `listRuns(limit, offset)` from `@/lib/api` (existing), Task 1's
  landing/ticker/boot classes.
- Produces: route `/` = landing, `/runs` = run list. All later tasks assume
  these routes.

- [ ] **Step 1:** `git mv console/app/page.tsx console/app/runs/page.tsx && git mv console/app/RunRow.tsx console/app/runs/RunRow.tsx`
  (the `./RunRow` relative import survives the move).
- [ ] **Step 2:** Replace `console/app/runs/page.tsx` content with:

```tsx
import { listRuns } from "@/lib/api";
import RunRow from "./RunRow";

export const metadata = {
  title: "Runs — TriageDesk Console",
};

export default async function RunListPage() {
  const { runs, total } = await listRuns();

  return (
    <main>
      <h1>Runs</h1>
      <p className="muted">
        Showing {runs.length} of {total} runs, newest first. Failed and
        escalated runs are highlighted below but never hidden.
      </p>
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>State</th>
              <th>Ticket subject</th>
              <th>Model</th>
              <th>Cost</th>
              <th>Latency</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <RunRow key={run.id} run={run} />
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
```

  (The old inline "Review queue → / Try the demo →" links are dropped — the
  shared header owns navigation now.)
- [ ] **Step 3:** Create the new `console/app/page.tsx` landing:

```tsx
import Link from "next/link";
import { listRuns } from "@/lib/api";
import { formatCost } from "@/lib/format";

export const metadata = {
  title: "TriageDesk — glass-box ticket triage",
};

const stateGlyph: Record<string, string> = {
  escalated: "⚠",
  failed: "✕",
  completed: "✓",
};

export default async function LandingPage() {
  const { runs, total } = await listRuns(3, 0);

  return (
    <main>
      <section className="hero">
        <p className="eyebrow boot boot-1">
          Glass-box ticket triage — every decision leaves evidence
        </p>
        <h1 className="boot boot-2">The AI never sends bad news on its own.</h1>
        <p className="hero-sub boot boot-3">
          An agent that triages support tickets — wrapped in evidence, cost
          caps, and human review. Every run below is real and traced end to
          end.
        </p>
        <div className="stats">
          <div className="stat stat-amber boot boot-4">
            <div className="stat-value">5/5</div>
            <div className="stat-label">Adversarial catch</div>
          </div>
          <div className="stat stat-green boot boot-5">
            <div className="stat-value">1.00</div>
            <div className="stat-label">Escalation recall</div>
          </div>
          <div className="stat boot boot-6">
            <div className="stat-value">2.9¢</div>
            <div className="stat-label">Avg cost / run</div>
          </div>
          <div className="stat boot boot-7">
            <div className="stat-value">0</div>
            <div className="stat-label">Unsafe auto-sends</div>
          </div>
        </div>
        <div className="ctas boot boot-8">
          <Link className="btn btn-primary" href="/demo">
            ▶ Run a live ticket
          </Link>
          <Link className="btn" href="/runs">
            Open the recorder
          </Link>
        </div>
      </section>

      <section className="ticker">
        <p className="eyebrow boot boot-9">
          Latest — {total} runs on record
        </p>
        {runs.map((run, i) => (
          <Link
            key={run.id}
            href={`/runs/${run.id}`}
            className={`ticker-row boot boot-${10 + i > 11 ? 11 : 10 + i} ${run.state}`}
          >
            <span>{run.ticket_subject}</span>
            <span className={`ticker-state ${run.state}`}>
              {stateGlyph[run.state] ?? "·"} {run.state}
              {run.escalation_reason ? ` · ${run.escalation_reason}` : ""} ·{" "}
              {formatCost(run.total_cost_usd)}
            </span>
          </Link>
        ))}
      </section>
    </main>
  );
}
```

- [ ] **Step 4:** In `console/app/runs/[id]/page.tsx`, change the back link:
  `<Link href="/">&larr; back to runs</Link>` → `<Link href="/runs">&larr; back to runs</Link>`.
- [ ] **Step 5:** Verify: `npm run build` passes; dev server: `/` shows the
  cockpit hero with real ticker rows booting in; `/runs` lists runs; clicking
  a ticker row lands on the run detail. Check `prefers-reduced-motion` via
  DevTools emulation: no movement, content visible immediately.
- [ ] **Step 6:** Commit:
  `git add console && git commit -m "feat(#56): cockpit-stack landing; run list moves to /runs"`

---

### Task 3: Run list rows + run detail restyle

**Files:**
- Modify: `console/app/runs/RunRow.tsx` (escalation reason → muted span)
- Modify: `console/app/runs/[id]/page.tsx` (panels, eyebrow headers,
  prominent rationale chip, prose classes)

**Interfaces:** Consumes Task 1 classes only. No API/type changes.

- [ ] **Step 1:** In `RunRow.tsx`, replace the state cell so the reason reads
  as secondary data:

```tsx
      <td>
        <span className={stateBadgeClass(run.state)}>{run.state}</span>
        {run.escalation_reason ? (
          <span className="muted"> {run.escalation_reason}</span>
        ) : null}
      </td>
```

- [ ] **Step 2:** Restyle `console/app/runs/[id]/page.tsx` — final JSX of the
  returned tree (imports/data logic unchanged apart from Task 2's back link):

```tsx
  return (
    <main>
      <p>
        <Link href="/runs">&larr; back to runs</Link>
      </p>
      <h1>Run {run.id}</h1>

      <section className="panel">
        <h2 className="eyebrow">Summary</h2>
        <table>
          <tbody>
            <tr>
              <th>State</th>
              <td>
                <span className={stateBadgeClass(run.state)}>{run.state}</span>
              </td>
            </tr>
            <tr>
              <th>Escalation reason</th>
              <td>{run.escalation_reason ?? "—"}</td>
            </tr>
            <tr>
              <th>Ticket</th>
              <td>
                #{run.ticket_id} — {run.ticket_subject}
              </td>
            </tr>
            <tr>
              <th>Model</th>
              <td>{run.model}</td>
            </tr>
            <tr>
              <th>Cost</th>
              <td>{formatCost(run.total_cost_usd)}</td>
            </tr>
            <tr>
              <th>Latency</th>
              <td>{formatLatency(run.latency_ms)}</td>
            </tr>
            <tr>
              <th>Created</th>
              <td>{formatCreatedAt(run.created_at)}</td>
            </tr>
          </tbody>
        </table>
      </section>

      {run.gate_signals && (
        <section className="panel">
          <h2 className="eyebrow">Gate signals</h2>
          <table>
            <tbody>
              {Object.entries(run.gate_signals).map(([key, value]) => (
                <tr key={key}>
                  <th>{key}</th>
                  <td>{JSON.stringify(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="panel">
        <h2 className="eyebrow">Trace</h2>
        <table>
          <thead>
            <tr>
              <th>Stage</th>
              <th>Status</th>
              <th>Duration</th>
              <th>Tokens in</th>
              <th>Tokens out</th>
              <th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {run.spans.map((span, i) => (
              <tr key={`${span.name}-${i}`}>
                <td>{span.name}</td>
                <td>{span.status}</td>
                <td>{formatLatency(span.duration_ms)}</td>
                <td>{span.input_tokens ?? "—"}</td>
                <td>{span.output_tokens ?? "—"}</td>
                <td>{formatCost(span.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2 className="eyebrow">Final reply</h2>
        <p className="panel-pad prose" style={{ marginTop: 0 }}>
          {run.final_reply ?? "— none —"}
        </p>
      </section>

      <section className="panel">
        <h2 className="eyebrow">Internal rationale</h2>
        <div className="panel-pad">
          <p className="rationale-caption">
            agent&apos;s post-hoc rationale — not evidence
          </p>
          <p className="prose" style={{ margin: 0 }}>
            {run.internal_rationale ?? "— none —"}
          </p>
        </div>
      </section>
    </main>
  );
```

  ⚠ The caption line stays byte-for-byte: `agent&apos;s post-hoc rationale — not evidence`.
- [ ] **Step 3:** Verify: `npm run build`; dev server: run list rows show
  rails/tints/badges (find a failed run — `b133b107`'s ticket subject "My VPN
  keeps disconnecting" exists in the data); detail page shows panels + amber
  rationale chip.
- [ ] **Step 4:** Commit:
  `git add console && git commit -m "feat(#56): run list + run detail in recorder style"`

---

### Task 4: Review queue + demo page restyle

**Files:**
- Modify: `console/app/review/page.tsx`
- Modify: `console/app/review/ReviewQueueClient.tsx`
- Modify: `console/app/review/ReviewItem.tsx`
- Modify: `console/app/demo/page.tsx`
- Modify: `console/app/demo/DemoRunner.tsx`

**Interfaces:** Consumes Task 1 classes. All handler logic, status branches,
and copy stay EXACTLY as-is — class/layout swaps only, except where noted.

- [ ] **Step 1:** `review/page.tsx`: drop the `<p><Link href="/">…` back-link
  paragraph (header owns nav); `<main style={…}>` → `<main>`; the intro `<p style={{color:…}}>`
  → `<p className="muted">`. Copy unchanged.
- [ ] **Step 2:** `ReviewQueueClient.tsx` render section becomes:

```tsx
  return (
    <>
      <div style={{ marginBottom: "1.5rem" }}>
        <label htmlFor="operator-token">Operator token</label>
        <br />
        <input
          id="operator-token"
          type="password"
          value={token}
          onChange={(e) => updateToken(e.target.value)}
          style={{ width: "100%", maxWidth: 400, marginTop: "0.35rem" }}
          placeholder="X-Admin-Token sent with each review"
        />
      </div>

      <p className="muted">
        {items.length} of {total} queued at page load — oldest escalations
        first.
      </p>

      {banner && <p className="error-text">{banner}</p>}

      {items.length === 0 && <p>Nothing waiting for review.</p>}

      {items.map((item) => (
        <ReviewItem
          key={item.id}
          item={item}
          token={token}
          onResolved={handleResolved}
          onAlreadyReviewed={refreshQueue}
          onNotConfigured={() =>
            setBanner(
              "the server has no operator token configured — reviews cannot be submitted"
            )
          }
        />
      ))}
    </>
  );
```

- [ ] **Step 3:** `ReviewItem.tsx` render section becomes (logic above it
  untouched):

```tsx
  return (
    <section
      className="review-card"
      style={{ padding: "1rem 1.25rem", marginBottom: "1rem" }}
    >
      <h3 style={{ marginTop: 0 }}>
        #{item.ticket_id} — {item.ticket_subject}
      </h3>
      <p className="muted">
        escalation reason: {item.escalation_reason ?? "—"} · cost{" "}
        {formatCost(item.total_cost_usd)} · latency{" "}
        {formatLatency(item.latency_ms)} · created{" "}
        {formatCreatedAt(item.created_at)}
      </p>

      <h4 className="eyebrow">Draft reply</h4>
      <p className="prose">{item.final_reply ?? "— none —"}</p>

      <h4 className="eyebrow">Internal rationale</h4>
      <p className="rationale-caption">
        agent&apos;s post-hoc rationale — not evidence
      </p>
      <p className="prose">{item.internal_rationale ?? "— none —"}</p>

      <label htmlFor={`note-${item.id}`}>Note (required)</label>
      <br />
      <textarea
        id={`note-${item.id}`}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        style={{ width: "100%", margin: "0.35rem 0 0.6rem" }}
        disabled={submitting}
      />
      <br />
      <button
        type="button"
        className="btn-approve"
        onClick={() => submit("approve")}
        disabled={submitting}
      >
        Approve
      </button>{" "}
      <button
        type="button"
        className="btn-reject"
        onClick={() => submit("reject")}
        disabled={submitting}
      >
        Reject
      </button>

      {error && <p className="error-text">{error}</p>}
    </section>
  );
```

  Note: the `.eyebrow` h4s keep their heading semantics; the caption chip
  stays byte-for-byte.
- [ ] **Step 4:** `demo/page.tsx`: drop the back-link paragraph; `<main style={…}>`
  → `<main style={{ maxWidth: 700 }}>`; intro `<p>` → `className="muted"`.
  Copy unchanged.
- [ ] **Step 5:** `DemoRunner.tsx` render: `<button …>` gets
  `className="btn-primary"` and label `{submitting ? "Running…" : "▶ Run"}`;
  the budget banner `<p style={…}>` becomes:

```tsx
      {budgetBanner && (
        <p className="pause-banner">
          Daily demo budget reached — watch the video instead
          {/* link placeholder for #17 */}
        </p>
      )}
```

  Select keeps its inline width style; everything else unchanged.
- [ ] **Step 6:** Verify: `npm run build`; dev server: `/review` shows amber-
  railed cards, green/red decision buttons; `/demo` shows the pool select +
  amber primary button. To see the pause banner without spending: temporarily
  set `budgetBanner` initial state to `true` locally, screenshot, revert
  (state the revert in the task report).
- [ ] **Step 7:** Commit:
  `git add console && git commit -m "feat(#56): review queue + demo in recorder style"`

---

### Task 5: Guidelines audit, after-screenshots, task report

**Files:**
- Create: `docs/week-4-launch/reports/task-console-redesign.md`
- Create: `docs/week-4-launch/reports/assets/after-*.png` (5 pages)
- Modify: anything the audit flags (small fixes only)

- [ ] **Step 1:** Run the **web-design-guidelines** skill (fetch its live
  rules) over `console/app/**/*.tsx` + `globals.css`; fix in-scope findings
  (contrast, focus, touch targets, reduced-motion); note out-of-scope ones in
  the report.
- [ ] **Step 2:** Spot-check contrast pairs (WebAIM contrast checker or
  equivalent): `--muted` on `--bg` and on `--surface` ≥ 4.5:1; `--amber`,
  `--green`, `--red` on their tinted row backgrounds ≥ 4.5:1; pause banner
  text `#0b0e11` on `--amber` ≥ 4.5:1. Record the numbers in the report.
- [ ] **Step 3:** After-screenshots (same viewport as Task 0): `/`, `/runs`,
  one run detail, `/review`, `/demo` (+ the forced pause banner shot from
  Task 4 Step 6).
- [ ] **Step 4:** Write `reports/task-console-redesign.md`: before/after
  pairs, the token table, the CSS-over-Tailwind decision, the 2.9¢-not-3.6¢
  copy decision, contrast numbers, and known gaps.
- [ ] **Step 5:** `npm run build` one final time; commit docs; open PR
  referencing #56 (base `main`, head `feat/56-console-redesign`), PR checklist
  self-review per project convention.

---

## Self-review (done at plan time)

- Issue AC coverage: consistent system (Task 1) ✓ · state colors loud +
  contrast (Tasks 1/3/5) ✓ · rationale caption prominent (Tasks 1/3/4) ✓ ·
  pause banner unmistakable (Tasks 1/4) ✓ · no deps/API/auth changes (Global)
  ✓ · before/after screenshots (Tasks 0/5) ✓.
- Landing page is additive scope beyond the issue's four pages — it came out
  of the brainstorm (cockpit stack) and is `console/**`-only; the issue's
  "four pages" all still get the pass.
- Type consistency: class names in Tasks 2–4 all exist in Task 1's stylesheet;
  `stateBadgeClass` signature unchanged; routes `/` and `/runs` consistent
  across Tasks 2–4.
