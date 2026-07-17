import { listRuns } from "@/lib/api";
import RunRow from "./RunRow";

export const metadata = {
  title: "Runs — TriageDesk Console",
};

export default async function RunListPage() {
  const { runs, total } = await listRuns();

  return (
    <main style={{ padding: "2rem", maxWidth: 1100, margin: "0 auto" }}>
      <h1>Runs</h1>
      <p style={{ color: "var(--muted)" }}>
        Showing {runs.length} of {total} runs, newest first. Failed and
        escalated runs are highlighted below but never hidden.
      </p>
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
    </main>
  );
}
