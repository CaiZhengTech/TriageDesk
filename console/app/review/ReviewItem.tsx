"use client";

import { useState } from "react";
import type { ReviewQueueItem } from "@/lib/api";
import { postReview } from "@/lib/api";
import AgentText from "../AgentText";
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
  const [open, setOpen] = useState(false);
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
    <section className={`run-card escalated ${open ? "open" : ""}`}>
      <button
        type="button"
        className="run-head"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span className="badge badge-escalated">escalated</span>
        <span className="run-subject">
          #{item.ticket_id} — {item.ticket_subject}
        </span>
        <span className="run-meta">
          {item.escalation_reason ?? "—"} ·{" "}
          {formatCost(item.total_cost_usd)} · {formatLatency(item.latency_ms)}
        </span>
        <span className="chevron" aria-hidden="true">
          ▸
        </span>
      </button>
      <div className="card-body">
        <div>
          <div className="card-inner">
            <p className="muted" style={{ margin: "0.75rem 0 0" }}>
              created {formatCreatedAt(item.created_at)}
            </p>
            <h4 className="eyebrow">Draft reply</h4>
            <AgentText text={item.final_reply} />

            <h4 className="eyebrow">Internal rationale</h4>
            <p className="rationale-caption">
              agent&apos;s post-hoc rationale — not evidence
            </p>
            <AgentText text={item.internal_rationale} />

            <div style={{ marginTop: "1.1rem" }}>
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
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
