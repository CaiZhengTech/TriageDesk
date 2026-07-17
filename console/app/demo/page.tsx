import Link from "next/link";
import { listDemoPool } from "@/lib/api";
import DemoRunner from "./DemoRunner";

export const metadata = {
  title: "Demo — TriageDesk Console",
};

export default async function DemoPage() {
  const { tickets } = await listDemoPool();

  return (
    <main style={{ padding: "2rem", maxWidth: 700, margin: "0 auto" }}>
      <p>
        <Link href="/">&larr; back to runs</Link>
      </p>
      <h1>Try the demo</h1>
      <p style={{ color: "var(--muted)" }}>
        Pick a seeded ticket below and run it through the live agent. There is
        no free-text ticket entry here — the pool keeps the demo bounded and
        repeatable, and every run is subject to a per-visitor rate limit and a
        shared daily spend cap.
      </p>
      <DemoRunner tickets={tickets} />
    </main>
  );
}
