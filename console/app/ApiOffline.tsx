import Link from "next/link";

/**
 * Shared offline state for the pages that genuinely need live data.
 *
 * The landing page can fall back to its static half (issue #60), but /runs,
 * /review and /demo are *about* the API — there is nothing honest to render
 * without it. What they must not do is throw, because Next redacts the real
 * message in a production build and the visitor gets the bare "An error
 * occurred in the Server Components render" digest page, which reads as a
 * broken site rather than a sleeping backend.
 *
 * So: say what is unavailable, say what still works, and offer somewhere to go.
 */
export default function ApiOffline({
  what,
  detail,
}: {
  what: string;
  detail: string;
}) {
  return (
    <section className="panel" style={{ marginTop: "1.5rem" }}>
      <h2 className="eyebrow">{what} — temporarily unavailable</h2>
      <div className="panel-pad">
        <p className="muted">{detail}</p>
        <p className="muted">
          This page reads from the TriageDesk API, which isn&apos;t responding
          right now. The recorded results and the full write-ups don&apos;t
          depend on it.
        </p>
        <div className="ctas" style={{ marginTop: "1rem" }}>
          <Link className="btn btn-primary" href="/">
            Back to the overview
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
      </div>
    </section>
  );
}
