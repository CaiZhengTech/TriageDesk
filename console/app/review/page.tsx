import Link from "next/link";
import { listReviewQueue } from "@/lib/api";
import ReviewQueueClient from "./ReviewQueueClient";

export const metadata = {
  title: "Review queue — TriageDesk Console",
};

export default async function ReviewQueuePage() {
  const { items, total } = await listReviewQueue();

  return (
    <main style={{ padding: "2rem", maxWidth: 1100, margin: "0 auto" }}>
      <p>
        <Link href="/">&larr; back to runs</Link>
      </p>
      <h1>Review queue</h1>
      <p style={{ color: "var(--muted)" }}>
        Escalated runs with no decision yet. Approving or rejecting requires
        the operator token configured on the server (there is deliberately no
        login system — this is a shared token for a single operator).
      </p>
      <ReviewQueueClient initialItems={items} initialTotal={total} />
    </main>
  );
}
