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
