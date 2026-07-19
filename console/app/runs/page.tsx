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
              <th className="num">Cost</th>
              <th className="num">Latency</th>
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
