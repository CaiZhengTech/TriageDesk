import Link from "next/link";

/** Shared recorder chrome: brand + the only nav on the site. */
export default function SiteHeader() {
  return (
    <header className="site-header">
      <Link href="/" className="brand">
        TRIAGEDESK{" "}
        <span className="rec-dot" aria-hidden="true">
          ●
        </span>{" "}
        REC
      </Link>
      <nav>
        <Link href="/">Home</Link>
        <Link href="/runs">Runs</Link>
        <Link href="/review">Review</Link>
        <Link href="/demo">Demo</Link>
        <a
          className="repo-link"
          href="https://github.com/CaiZhengTech/TriageDesk"
          target="_blank"
          rel="noopener noreferrer"
        >
          Source ↗
        </a>
      </nav>
    </header>
  );
}
