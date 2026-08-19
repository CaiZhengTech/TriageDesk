import ApiOffline from "../ApiOffline";
import { listReviewQueue } from "@/lib/api";
import ReviewQueueClient from "./ReviewQueueClient";

export const metadata = {
  title: "Review queue — TriageDesk Console",
};

export default async function ReviewQueuePage() {
  let data: Awaited<ReturnType<typeof listReviewQueue>> | null = null;
  try {
    data = await listReviewQueue();
  } catch {
    data = null;
  }

  if (data === null) {
    return (
      <main>
        <h1>Review queue</h1>
        <ApiOffline
          what="Review queue"
          detail="Escalated runs waiting on a human decision are listed here."
        />
      </main>
    );
  }

  const { items, total } = data;

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
