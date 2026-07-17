"use client";

import { useEffect, useState } from "react";
import type { ReviewQueueItem } from "@/lib/api";
import { listReviewQueue } from "@/lib/api";
import ReviewItem from "./ReviewItem";

const TOKEN_KEY = "triagedesk_operator_token";

/**
 * Owns the operator-token field (sessionStorage-backed) and the queue's
 * client-side item list. Each row is delegated to `ReviewItem`, which does
 * the actual POST; this component only reacts to the outcome — removing a
 * resolved item, or refetching on a 409 (someone else already decided it).
 */
export default function ReviewQueueClient({
  initialItems,
  initialTotal,
}: {
  initialItems: ReviewQueueItem[];
  initialTotal: number;
}) {
  const [token, setToken] = useState("");
  const [items, setItems] = useState(initialItems);
  const [total, setTotal] = useState(initialTotal);
  const [banner, setBanner] = useState<string | null>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem(TOKEN_KEY);
    if (stored) {
      setToken(stored);
    }
  }, []);

  function updateToken(value: string) {
    setToken(value);
    sessionStorage.setItem(TOKEN_KEY, value);
  }

  function handleResolved(runId: string) {
    setItems((prev) => prev.filter((item) => item.id !== runId));
    setBanner(null);
  }

  async function refreshQueue() {
    const queue = await listReviewQueue();
    setItems(queue.items);
    setTotal(queue.total);
  }

  return (
    <>
      <div style={{ marginBottom: "1.5rem" }}>
        <label htmlFor="operator-token">Operator token</label>
        <br />
        <input
          id="operator-token"
          type="password"
          value={token}
          onChange={(e) => updateToken(e.target.value)}
          style={{ width: "100%", maxWidth: 400 }}
          placeholder="X-Admin-Token sent with each review"
        />
      </div>

      <p style={{ color: "var(--muted)" }}>
        {items.length} of {total} queued at page load — oldest escalations
        first.
      </p>

      {banner && (
        <p style={{ color: "var(--failed-border)" }}>{banner}</p>
      )}

      {items.length === 0 && <p>Nothing waiting for review.</p>}

      {items.map((item) => (
        <ReviewItem
          key={item.id}
          item={item}
          token={token}
          onResolved={handleResolved}
          onAlreadyReviewed={refreshQueue}
          onNotConfigured={() =>
            setBanner(
              "the server has no operator token configured — reviews cannot be submitted"
            )
          }
        />
      ))}
    </>
  );
}
