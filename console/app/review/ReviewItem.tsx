"use client";

import { useState } from "react";
import type { ReviewQueueItem } from "@/lib/api";
import { postReview } from "@/lib/api";
import { formatCost, formatCreatedAt, formatLatency } from "@/lib/format";

/**
 * One queue item: context (subject, escalation reason, draft reply, agent
 * rationale) plus the required-note + approve/reject controls. A client
 * component (needs local note/submitting state and the POST call), same
 * shape as `RunRow`'s split from the server-rendered list page.
 */
export default function ReviewItem({
  item,
  token,
  onResolved,
  onAlreadyReviewed,
  onNotConfigured,
}: {
  item: ReviewQueueItem;
  token: string;
  onResolved: (runId: string) => void;
  onAlreadyReviewed: () => void;
  onNotConfigured: () => void;
}) {
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(decision: "approve" | "reject") {
    if (note.trim() === "") {
      setError("a note is required");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await postReview(item.id, decision, note, token);
      switch (result.status) {
        case "ok":
          onResolved(item.id);
          break;
        case "invalid_token":
          setError("invalid operator token");
          break;
        case "already_reviewed":
          setError("already reviewed");
          onAlreadyReviewed();
          break;
        case "not_configured":
          setError("server has no operator token configured — reviews are disabled");
          onNotConfigured();
          break;
        case "error":
          setError(`review failed: HTTP ${result.httpStatus}`);
          break;
      }
    } catch {
      setError("review failed: could not reach the API");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section
      className="review-card"
      style={{ padding: "1rem 1.25rem", marginBottom: "1rem" }}
    >
      <h3 style={{ marginTop: 0 }}>
        #{item.ticket_id} — {item.ticket_subject}
      </h3>
      <p className="muted">
        escalation reason: {item.escalation_reason ?? "—"} · cost{" "}
        {formatCost(item.total_cost_usd)} · latency{" "}
        {formatLatency(item.latency_ms)} · created{" "}
        {formatCreatedAt(item.created_at)}
      </p>

      <h4 className="eyebrow">Draft reply</h4>
      <p className="prose">{item.final_reply ?? "— none —"}</p>

      <h4 className="eyebrow">Internal rationale</h4>
      <p className="rationale-caption">
        agent&apos;s post-hoc rationale — not evidence
      </p>
      <p className="prose">{item.internal_rationale ?? "— none —"}</p>

      <label htmlFor={`note-${item.id}`}>Note (required)</label>
      <br />
      <textarea
        id={`note-${item.id}`}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        style={{ width: "100%", margin: "0.35rem 0 0.6rem" }}
        disabled={submitting}
      />
      <br />
      <button
        type="button"
        className="btn-approve"
        onClick={() => submit("approve")}
        disabled={submitting}
      >
        Approve
      </button>{" "}
      <button
        type="button"
        className="btn-reject"
        onClick={() => submit("reject")}
        disabled={submitting}
      >
        Reject
      </button>

      {error && <p className="error-text">{error}</p>}
    </section>
  );
}
