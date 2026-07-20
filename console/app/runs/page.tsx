import { listRuns } from "@/lib/api";
import RunCard from "./RunCard";

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
        escalated runs are highlighted below but never hidden — click a run to
        expand its trace in place.
      </p>
      {runs.map((run) => (
        <RunCard key={run.id} run={run} />
      ))}
    </main>
  );
}
