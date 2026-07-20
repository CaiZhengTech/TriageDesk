"use client";

import { useState } from "react";
import Link from "next/link";
import type { RunDetail, RunSummary } from "@/lib/api";
import { getRun } from "@/lib/api";
import AgentText from "../AgentText";
import {
  formatCost,
  formatCreatedAt,
  formatLatency,
  stateBadgeClass,
} from "@/lib/format";

/**
 * One run in the list: a compact one-line header (state stays loud — badge +
 * colored rail, never hidden) that expands in place to the run's trace and
 * replies. Detail is fetched once on first open ($0 read) and cached in
 * state; the full run page stays one click away.
 */
export default function RunCard({ run }: { run: RunSummary }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && detail === null) {
      try {
        setDetail(await getRun(run.id));
      } catch {
        setLoadFailed(true);
      }
    }
  }

  return (
    <div className={`run-card ${run.state} ${open ? "open" : ""}`}>
      <button
        type="button"
        className="run-head"
        onClick={toggle}
        aria-expanded={open}
      >
        <span className={stateBadgeClass(run.state)}>{run.state}</span>
        <span className="run-subject">{run.ticket_subject}</span>
        <span className="run-meta">
          {run.escalation_reason ? `${run.escalation_reason} · ` : ""}
          {formatCost(run.total_cost_usd)} · {formatLatency(run.latency_ms)}
        </span>
        <span className="chevron" aria-hidden="true">
          ▸
        </span>
      </button>
      <div className="card-body">
        <div>
          <div className="card-inner">
            <p className="muted" style={{ margin: "0.75rem 0 0" }}>
              #{run.ticket_id} · {run.model} · created{" "}
              {formatCreatedAt(run.created_at)}
            </p>

            {loadFailed && (
              <p className="error-text">couldn&apos;t load the trace — try the full page below</p>
            )}
            {open && detail === null && !loadFailed && (
              <p className="muted">loading trace…</p>
            )}

            {detail && (
              <>
                <h3 className="eyebrow">Trace</h3>
                <table>
                  <tbody>
                    {detail.spans.map((span, i) => (
                      <tr key={`${span.name}-${i}`}>
                        <td style={{ paddingLeft: 0 }}>{span.name}</td>
                        <td className="dim">{span.status}</td>
                        <td className="num">{formatLatency(span.duration_ms)}</td>
                        <td className="num">{formatCost(span.cost_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <h3 className="eyebrow">Final reply</h3>
                <AgentText text={detail.final_reply} />

                <h3 className="eyebrow">Internal rationale</h3>
                <p className="rationale-caption">
                  agent&apos;s post-hoc rationale — not evidence
                </p>
                <AgentText text={detail.internal_rationale} />
              </>
            )}

            <p style={{ margin: "1.1rem 0 0" }}>
              <Link href={`/runs/${run.id}`}>Open the full trace &rarr;</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
