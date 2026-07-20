"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { RunDetail } from "@/lib/api";
import { getRun } from "@/lib/api";
import Pipeline, { PIPELINE_STAGES, type StageState } from "../Pipeline";

const POLL_MS = 3000;
const MAX_POLLS = 60; // ~3 minutes, then stop honestly

/**
 * Watches one run execute: polls the read-only run endpoint ($0) and lights
 * the shared pipeline from real span data. Spans are committed BEFORE their
 * stage runs (tracing.py), so the newest span is the stage in flight.
 */
export default function LiveProgress({ runId }: { runId: string }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const polls = useRef(0);

  const state = run?.state;
  const terminal =
    state === "completed" || state === "escalated" || state === "failed";

  useEffect(() => {
    if (terminal) return;
    let cancelled = false;

    const tick = async () => {
      polls.current += 1;
      if (polls.current > MAX_POLLS) {
        setTimedOut(true);
        return;
      }
      try {
        const latest = await getRun(runId);
        if (!cancelled && latest) setRun(latest);
      } catch {
        // transient poll failure: keep the last known state, try again
      }
    };

    tick();
    const interval = setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [runId, terminal]);

  const spanNames = new Set((run?.spans ?? []).map((s) => s.name));
  const newest = run?.spans[run.spans.length - 1]?.name;

  const stageStates: Partial<Record<string, StageState>> = {};
  for (const stage of PIPELINE_STAGES) {
    if (!spanNames.has(stage.id)) continue;
    stageStates[stage.id] =
      !terminal && stage.id === newest ? "active" : "done";
  }

  const outcome =
    state === "completed"
      ? "auto_resolve"
      : state === "escalated"
        ? "human_review"
        : null;

  return (
    <section className="panel live-panel" aria-live="polite">
      <h3 className="eyebrow">
        {terminal
          ? `Run ${state}`
          : timedOut
            ? "Still running"
            : "Run in flight — watching the recorder"}
      </h3>
      <div className="panel-pad">
        <Pipeline mode="live" stageStates={stageStates} outcome={outcome} />

        {state === "escalated" && (
          <p className="live-verdict">
            <span className="badge badge-escalated">escalated</span>{" "}
            {run?.escalation_reason ? (
              <span className="muted">{run.escalation_reason} · </span>
            ) : null}
            handed to a human — the gate declined to auto-send.
          </p>
        )}
        {state === "completed" && (
          <p className="live-verdict">
            <span className="badge badge-completed">completed</span>{" "}
            auto-resolved above calibrated thresholds.
          </p>
        )}
        {state === "failed" && (
          <p className="live-verdict error-text">
            <span className="badge badge-failed">failed</span> the run failed —
            the error is preserved verbatim on the run page. Nothing is hidden.
          </p>
        )}
        {timedOut && !terminal && (
          <p className="live-verdict muted">
            Taking longer than expected — the run page has the live record.
          </p>
        )}

        <p className="muted live-footer">
          {terminal || timedOut ? (
            <Link href={`/runs/${runId}`}>Open the full trace &rarr;</Link>
          ) : (
            <>Real spans, polled from the API every 3 seconds — nothing staged.</>
          )}
        </p>
      </div>
    </section>
  );
}
