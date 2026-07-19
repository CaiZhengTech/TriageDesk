"use client";

import { useRouter } from "next/navigation";
import type { RunSummary } from "@/lib/api";
import {
  formatCost,
  formatCreatedAt,
  formatLatency,
  stateBadgeClass,
  stateRowClass,
} from "@/lib/format";

/**
 * One clickable row in the run list. A client component (needs onClick) so
 * the whole row navigates to the detail page, not just a link cell — the
 * subject cell keeps a real `<a>` inside so keyboard/no-JS navigation still
 * works.
 */
export default function RunRow({ run }: { run: RunSummary }) {
  const router = useRouter();

  return (
    <tr
      className={stateRowClass(run.state)}
      onClick={() => router.push(`/runs/${run.id}`)}
      style={{ cursor: "pointer" }}
    >
      <td>
        <span className={stateBadgeClass(run.state)}>{run.state}</span>
        {run.escalation_reason ? (
          <span className="muted"> {run.escalation_reason}</span>
        ) : null}
      </td>
      <td>
        <a href={`/runs/${run.id}`}>{run.ticket_subject}</a>
      </td>
      <td className="dim">{run.model}</td>
      <td className="num">{formatCost(run.total_cost_usd)}</td>
      <td className="num">{formatLatency(run.latency_ms)}</td>
      <td className="dim">{formatCreatedAt(run.created_at)}</td>
    </tr>
  );
}
