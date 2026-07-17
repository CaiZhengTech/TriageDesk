/** Small display-formatting helpers shared by the run list and detail pages. */

/** USD amount -> "¢" below a dollar, "$" at or above, always 2+ decimals. */
export function formatCost(usd: number | null | undefined): string {
  if (usd === null || usd === undefined) {
    return "—";
  }
  if (Math.abs(usd) < 1) {
    return `${(usd * 100).toFixed(2)}¢`;
  }
  return `$${usd.toFixed(2)}`;
}

/** Milliseconds -> seconds string; null while a run hasn't finished. */
export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) {
    return "—";
  }
  return `${(ms / 1000).toFixed(2)}s`;
}

/** ISO timestamp -> locale-formatted date/time for display. */
export function formatCreatedAt(iso: string): string {
  return new Date(iso).toLocaleString();
}

/** CSS row/badge class for run state — failed/escalated stay visible, just styled. */
export function stateRowClass(state: string): string {
  if (state === "escalated") return "row-escalated";
  if (state === "failed") return "row-failed";
  return "";
}

export function stateBadgeClass(state: string): string {
  if (state === "escalated") return "badge badge-escalated";
  if (state === "failed") return "badge badge-failed";
  return "badge";
}
