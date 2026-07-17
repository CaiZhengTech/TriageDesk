/**
 * Typed fetch helpers for the TriageDesk read-only console API.
 *
 * Shapes match `triagedesk/console_queries.py` verbatim (Task 1, issue #13).
 * No data library (SWR/React Query) per the council's YAGNI cut — plain
 * `fetch` with `cache: "no-store"` so the console always shows current data.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface RunSummary {
  id: string;
  ticket_id: number;
  ticket_subject: string;
  state: string;
  escalation_reason: string | null;
  total_cost_usd: number;
  latency_ms: number | null;
  model: string;
  created_at: string;
}

export interface RunSpan {
  name: string;
  status: string;
  duration_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number;
  attributes: Record<string, unknown>;
}

export interface RunDetail extends RunSummary {
  final_reply: string | null;
  internal_rationale: string | null;
  gate_signals: Record<string, unknown> | null;
  spans: RunSpan[];
}

export interface RunList {
  runs: RunSummary[];
  total: number;
}

export async function listRuns(limit = 50, offset = 0): Promise<RunList> {
  const res = await fetch(
    `${API_BASE_URL}/api/runs?limit=${limit}&offset=${offset}`,
    { cache: "no-store" }
  );
  if (!res.ok) {
    throw new Error(`GET /api/runs failed: ${res.status}`);
  }
  return res.json();
}

export async function getRun(runId: string): Promise<RunDetail | null> {
  const res = await fetch(`${API_BASE_URL}/api/runs/${runId}`, {
    cache: "no-store",
  });
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`GET /api/runs/${runId} failed: ${res.status}`);
  }
  return res.json();
}

export interface ReviewQueueItem extends RunSummary {
  internal_rationale: string | null;
  final_reply: string | null;
}

export interface ReviewQueue {
  items: ReviewQueueItem[];
  total: number;
}

export async function listReviewQueue(): Promise<ReviewQueue> {
  const res = await fetch(`${API_BASE_URL}/api/review-queue`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`GET /api/review-queue failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Result of a review submission, one variant per status this task's UI must
 * distinguish (Task 3's documented contract: 201/401/503/409/404/422). 404
 * and 422 collapse into "error" — they aren't reachable from a queue-derived
 * run id / a UI-constrained decision value, so no dedicated message is
 * required for them.
 */
export type ReviewResult =
  | { status: "ok"; id: number }
  | { status: "invalid_token" }
  | { status: "not_configured" }
  | { status: "already_reviewed" }
  | { status: "error"; httpStatus: number };

export async function postReview(
  runId: string,
  decision: "approve" | "reject",
  note: string,
  token: string
): Promise<ReviewResult> {
  const res = await fetch(`${API_BASE_URL}/api/review/${runId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": token,
    },
    body: JSON.stringify({ decision, note }),
  });

  if (res.status === 201) {
    const body = await res.json();
    return { status: "ok", id: body.id };
  }
  if (res.status === 401) {
    return { status: "invalid_token" };
  }
  if (res.status === 503) {
    return { status: "not_configured" };
  }
  if (res.status === 409) {
    return { status: "already_reviewed" };
  }
  return { status: "error", httpStatus: res.status };
}

/**
 * The demo pool (Task 7, issue #16): seeded `source='demo'` tickets only —
 * no free text anywhere in the demo flow.
 */
export interface DemoPoolTicket {
  id: number;
  subject: string;
}

export interface DemoPool {
  tickets: DemoPoolTicket[];
}

export async function listDemoPool(): Promise<DemoPool> {
  const res = await fetch(`${API_BASE_URL}/api/demo/pool`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`GET /api/demo/pool failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Result of a demo-run submission, one variant per branch the API's "before
 * spending" guards can return (404/429/402/202 — see triagedesk/demo.py).
 */
export type DemoRunResult =
  | { status: "ok"; runId: string }
  | { status: "not_in_pool" }
  | { status: "rate_limited" }
  | { status: "budget_reached" }
  | { status: "error"; httpStatus: number };

export async function runDemo(ticketId: number): Promise<DemoRunResult> {
  const res = await fetch(`${API_BASE_URL}/api/demo/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticket_id: ticketId }),
  });

  if (res.status === 202) {
    const body = await res.json();
    return { status: "ok", runId: body.run_id };
  }
  if (res.status === 404) {
    return { status: "not_in_pool" };
  }
  if (res.status === 429) {
    return { status: "rate_limited" };
  }
  if (res.status === 402) {
    return { status: "budget_reached" };
  }
  return { status: "error", httpStatus: res.status };
}
