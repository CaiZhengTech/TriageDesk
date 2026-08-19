import ApiOffline from "../ApiOffline";
import { listRuns } from "@/lib/api";
import RunCard from "./RunCard";

export const metadata = {
  title: "Runs — TriageDesk Console",
};

export default async function RunListPage() {
  let data: Awaited<ReturnType<typeof listRuns>> | null = null;
  try {
    data = await listRuns();
  } catch {
    data = null;
  }

  if (data === null) {
    return (
      <main>
        <h1>Runs</h1>
        <ApiOffline
          what="Run history"
          detail="Every run the agent has executed, with its full trace, lives here."
        />
      </main>
    );
  }

  const { runs, total } = data;

  return (
    <main>
      <h1>Runs</h1>
      <p className="muted">
        Showing {runs.length} of {total} runs, newest first. Failed and
        escalated runs are highlighted below but never hidden — click a run to
        expand its trace in place.
      </p>
      {runs.length === 0 ? (
        <p className="muted">
          No runs recorded yet. Runs appear here as soon as a ticket goes
          through the pipeline — try one on the demo page.
        </p>
      ) : (
        runs.map((run) => <RunCard key={run.id} run={run} />)
      )}
    </main>
  );
}
