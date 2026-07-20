/**
 * Remounts on every route change, giving each page one soft entrance —
 * the cross-section transition. Reduced motion disables it in globals.css.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
