import Link from "next/link";
import { listRuns } from "@/lib/api";
import { formatCost } from "@/lib/format";
import Pipeline from "./Pipeline";
import TypedHeadline from "./TypedHeadline";

export const metadata = {
  title: "TriageDesk — glass-box ticket triage",
};

const stateGlyph: Record<string, string> = {
  escalated: "⚠",
  failed: "✕",
  completed: "✓",
};

export default async function LandingPage() {
  const { runs, total } = await listRuns(50, 0);
  const recent = runs.slice(0, 5);
  const counts = {
    escalated: runs.filter((r) => r.state === "escalated").length,
    failed: runs.filter((r) => r.state === "failed").length,
    completed: runs.filter((r) => r.state === "completed").length,
  };
  const sample = runs.length;

  return (
    <main>
      <section className="hero">
        <p className="eyebrow boot boot-1">
          Glass-box ticket triage — every decision leaves evidence
        </p>
        <h1 className="boot boot-2">
          <TypedHeadline />
        </h1>
        <p className="hero-sub boot boot-3">
          An agent that triages support tickets — wrapped in evidence, cost
          caps, and human review. Every run below is real and traced end to
          end.
        </p>
        <div className="stats">
          <div className="stat stat-amber boot boot-4">
            <div className="stat-value">5/5</div>
            <div className="stat-label">Adversarial catch</div>
          </div>
          <div className="stat stat-green boot boot-5">
            <div className="stat-value">1.00</div>
            <div className="stat-label">Escalation recall</div>
          </div>
          <div className="stat boot boot-6">
            <div className="stat-value">2.9¢</div>
            <div className="stat-label">Avg cost / run</div>
          </div>
          <div className="stat boot boot-7">
            <div className="stat-value">0</div>
            <div className="stat-label">Unsafe auto-sends</div>
          </div>
        </div>
        <div className="ctas boot boot-8">
          <Link className="btn btn-primary" href="/demo">
            ▶ Run a live ticket
          </Link>
          <Link className="btn" href="/runs">
            Open the recorder
          </Link>
          <a
            className="btn"
            href="https://github.com/CaiZhengTech/TriageDesk"
            target="_blank"
            rel="noopener noreferrer"
          >
            Read the code ↗
          </a>
        </div>
      </section>

      <section className="panel lifecycle boot boot-9">
        <h2 className="eyebrow">Lifecycle — five stages, two exits</h2>
        <div className="panel-pad">
          <Pipeline mode="ambient" />
          <p className="muted lifecycle-caption">
            Dana&apos;s VPN ticket rides these five stages on every run — a
            deny-shaped reply can only exit through human review.
          </p>
        </div>
      </section>

      <div className="dash">
        <section className="panel boot boot-10">
          <h2 className="eyebrow">State — last {sample} runs</h2>
          <div className="panel-pad">
            <div
              className="dist-bar"
              role="img"
              aria-label={`Of the last ${sample} runs: ${counts.escalated} escalated, ${counts.failed} failed, ${counts.completed} completed.`}
            >
              {counts.escalated > 0 && (
                <span
                  className="dist-seg escalated"
                  style={{ width: `${(counts.escalated / sample) * 100}%` }}
                />
              )}
              {counts.failed > 0 && (
                <span
                  className="dist-seg failed"
                  style={{ width: `${(counts.failed / sample) * 100}%` }}
                />
              )}
              {counts.completed > 0 && (
                <span
                  className="dist-seg completed"
                  style={{ width: `${(counts.completed / sample) * 100}%` }}
                />
              )}
            </div>
            <ul className="dist-legend">
              <li>
                <span className="escalated">⚠ escalated</span>
                <span>{counts.escalated}</span>
              </li>
              <li>
                <span className="failed">✕ failed</span>
                <span>{counts.failed}</span>
              </li>
              <li>
                <span className="completed">✓ completed</span>
                <span>{counts.completed}</span>
              </li>
            </ul>
            {counts.completed === 0 && (
              <p className="muted dist-note">
                0 completed isn&apos;t a bug — nothing auto-resolves below the
                calibrated thresholds. The gate is doing its job.
              </p>
            )}
          </div>
        </section>

        <section className="ticker panel boot boot-11">
          <h2 className="eyebrow">Latest — {total} runs on record</h2>
          <div className="panel-pad" style={{ paddingTop: 0 }}>
            {recent.map((run) => (
              <Link
                key={run.id}
                href={`/runs/${run.id}`}
                className={`ticker-row ${run.state}`}
              >
                <span>{run.ticket_subject}</span>
                <span className={`ticker-state ${run.state}`}>
                  {stateGlyph[run.state] ?? "·"} {run.state}
                  {run.escalation_reason ? ` · ${run.escalation_reason}` : ""}{" "}
                  · {formatCost(run.total_cost_usd)}
                </span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
