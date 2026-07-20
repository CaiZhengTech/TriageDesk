import { notFound } from "next/navigation";
import Link from "next/link";
import { getRun } from "@/lib/api";
import AgentText from "../../AgentText";
import {
  formatCost,
  formatCreatedAt,
  formatLatency,
  stateBadgeClass,
} from "@/lib/format";

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const run = await getRun(id);

  if (run === null) {
    notFound();
  }

  return (
    <main>
      <p>
        <Link href="/runs">&larr; back to runs</Link>
      </p>
      <h1>
        Run <span className="muted">{run.id}</span>
      </h1>

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
              <th className="num">Duration</th>
              <th className="num">Tokens in</th>
              <th className="num">Tokens out</th>
              <th className="num">Cost</th>
            </tr>
          </thead>
          <tbody>
            {run.spans.map((span, i) => (
              <tr key={`${span.name}-${i}`}>
                <td>{span.name}</td>
                <td className="dim">{span.status}</td>
                <td className="num">{formatLatency(span.duration_ms)}</td>
                <td className="num">{span.input_tokens ?? "—"}</td>
                <td className="num">{span.output_tokens ?? "—"}</td>
                <td className="num">{formatCost(span.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2 className="eyebrow">Final reply</h2>
        <div className="panel-pad">
          <AgentText text={run.final_reply} />
        </div>
      </section>

      <section className="panel">
        <h2 className="eyebrow">Internal rationale</h2>
        <div className="panel-pad">
          <p className="rationale-caption">
            agent&apos;s post-hoc rationale — not evidence
          </p>
          <AgentText text={run.internal_rationale} />
        </div>
      </section>
    </main>
  );
}
