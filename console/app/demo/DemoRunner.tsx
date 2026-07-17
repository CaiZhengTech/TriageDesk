"use client";

import { useState } from "react";
import Link from "next/link";
import type { DemoPoolTicket } from "@/lib/api";
import { runDemo } from "@/lib/api";

/**
 * The pool dropdown + Run button + guard-branch messaging. A client
 * component (needs local selection/submitting state and the POST call),
 * same split as ReviewItem/ReviewQueueClient. No free-text input anywhere —
 * the only control is a <select> over the seeded pool.
 */
export default function DemoRunner({ tickets }: { tickets: DemoPoolTicket[] }) {
  const [ticketId, setTicketId] = useState<number | null>(tickets[0]?.id ?? null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [budgetBanner, setBudgetBanner] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);

  async function handleRun() {
    if (ticketId === null) return;
    setSubmitting(true);
    setMessage(null);
    setBudgetBanner(false);
    setRunId(null);
    try {
      const result = await runDemo(ticketId);
      switch (result.status) {
        case "ok":
          setRunId(result.runId);
          setMessage("Run started.");
          break;
        case "rate_limited":
          setMessage(
            "Too many demo runs from this location in the last hour — try again later."
          );
          break;
        case "budget_reached":
          setBudgetBanner(true);
          break;
        case "not_in_pool":
          setMessage("That ticket isn't in the demo pool — pick another.");
          break;
        case "error":
          setMessage(`Run failed: HTTP ${result.httpStatus}`);
          break;
      }
    } catch {
      setMessage("Run failed: could not reach the API");
    } finally {
      setSubmitting(false);
    }
  }

  if (tickets.length === 0) {
    return <p>No demo tickets are seeded yet.</p>;
  }

  return (
    <div>
      <label htmlFor="demo-ticket">Ticket</label>
      <br />
      <select
        id="demo-ticket"
        value={ticketId ?? ""}
        onChange={(e) => setTicketId(Number(e.target.value))}
        disabled={submitting}
        style={{ width: "100%", maxWidth: 500, marginBottom: "1rem" }}
      >
        {tickets.map((t) => (
          <option key={t.id} value={t.id}>
            {t.subject}
          </option>
        ))}
      </select>
      <br />
      <button type="button" onClick={handleRun} disabled={submitting}>
        {submitting ? "Running…" : "Run"}
      </button>

      {budgetBanner && (
        <p style={{ color: "var(--failed-border)", fontWeight: 600 }}>
          Daily demo budget reached — watch the video instead
          {/* link placeholder for #17 */}
        </p>
      )}
      {message && <p>{message}</p>}
      {runId && (
        <p>
          <Link href={`/runs/${runId}`}>View run &rarr;</Link>
        </p>
      )}
    </div>
  );
}
