import ApiOffline from "../ApiOffline";
import { listDemoPool } from "@/lib/api";
import DemoRunner from "./DemoRunner";

export const metadata = {
  title: "Demo — TriageDesk Console",
};

export default async function DemoPage() {
  let data: Awaited<ReturnType<typeof listDemoPool>> | null = null;
  try {
    data = await listDemoPool();
  } catch {
    data = null;
  }

  if (data === null) {
    return (
      <main>
        <h1>Try the demo</h1>
        <ApiOffline
          what="Live demo"
          detail="Running a ticket needs the agent itself, not just its records."
        />
      </main>
    );
  }

  const { tickets } = data;

  return (
    <main>
      <h1>Try the demo</h1>
      <p className="muted" style={{ maxWidth: 640 }}>
        Pick a seeded ticket below and run it through the live agent. There is
        no free-text ticket entry here — the pool keeps the demo bounded and
        repeatable, and every run is subject to a per-visitor rate limit and a
        shared daily spend cap.
      </p>
      {tickets.length === 0 ? (
        <p className="muted">
          The demo pool is empty — no seeded tickets are available to run.
        </p>
      ) : (
        <DemoRunner tickets={tickets} />
      )}
    </main>
  );
}
