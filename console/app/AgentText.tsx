/**
 * Renders an agent-written block (draft reply, internal rationale) the way it
 * was written: paragraph and bullet breaks survive via `white-space: pre-wrap`
 * in `.prose`, and `**bold**` spans — which the model emits reliably — render
 * as bold instead of showing raw asterisks.
 *
 * Deliberately NOT a markdown parser: no dependency, and bold is the only
 * markup that actually appears in these replies. Unbalanced markers fall back
 * to the literal text rather than bolding the tail of the message.
 */
export default function AgentText({ text }: { text: string | null }) {
  if (text === null || text.trim() === "") {
    return <p className="prose muted">— none —</p>;
  }

  const parts = text.split("**");
  const balanced = parts.length % 2 === 1;

  return (
    <p className="prose">
      {balanced
        ? parts.map((part, i) =>
            i % 2 === 1 ? <strong key={i}>{part}</strong> : part
          )
        : text}
    </p>
  );
}
