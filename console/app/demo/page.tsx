import { listDemoPool } from "@/lib/api";
import DemoRunner from "./DemoRunner";

export const metadata = {
  title: "Demo — TriageDesk Console",
};

export default async function DemoPage() {
  const { tickets } = await listDemoPool();

  return (
    <main>
      <h1>Try the demo</h1>
      <p className="muted" style={{ maxWidth: 640 }}>
        Pick a seeded ticket below and run it through the live agent. There is
        no free-text ticket entry here — the pool keeps the demo bounded and
        repeatable, and every run is subject to a per-visitor rate limit and a
        shared daily spend cap.
      </p>
      <DemoRunner tickets={tickets} />
    </main>
  );
}
