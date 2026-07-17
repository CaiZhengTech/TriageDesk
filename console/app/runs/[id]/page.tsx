import { notFound } from "next/navigation";
import Link from "next/link";
import { getRun } from "@/lib/api";
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
    <main style={{ padding: "2rem", maxWidth: 1100, margin: "0 auto" }}>
      <p>
        <Link href="/">&larr; back to runs</Link>
      </p>
      <h1>Run {run.id}</h1>

      <section style={{ marginBottom: "1.5rem" }}>
        <h2>Summary</h2>
        <table>
          <tbody>
            <tr>
              <th>State</th>
              <td>
                <span className={stateBadgeClass(run.state)}>
                  {run.state}
                </span>
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
        <section style={{ marginBottom: "1.5rem" }}>
          <h2>Gate signals</h2>
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

      <section style={{ marginBottom: "1.5rem" }}>
        <h2>Trace</h2>
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

      <section style={{ marginBottom: "1.5rem" }}>
        <h2>Final reply</h2>
        <p>{run.final_reply ?? "— none —"}</p>
      </section>

      <section style={{ marginBottom: "1.5rem" }}>
        <h2>Internal rationale</h2>
        <p className="rationale-caption">
          agent&apos;s post-hoc rationale — not evidence
        </p>
        <p>{run.internal_rationale ?? "— none —"}</p>
      </section>
    </main>
  );
}
