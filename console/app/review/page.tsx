import { listReviewQueue } from "@/lib/api";
import ReviewQueueClient from "./ReviewQueueClient";

export const metadata = {
  title: "Review queue — TriageDesk Console",
};

export default async function ReviewQueuePage() {
  const { items, total } = await listReviewQueue();

  return (
    <main>
      <h1>Review queue</h1>
      <p className="muted">
        Escalated runs with no decision yet. Approving or rejecting requires
        the operator token configured on the server (there is deliberately no
        login system — this is a shared token for a single operator).
      </p>
      <ReviewQueueClient initialItems={items} initialTotal={total} />
    </main>
  );
}
