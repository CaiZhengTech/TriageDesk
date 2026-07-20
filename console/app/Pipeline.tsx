/**
 * The lifecycle pipeline, shared by the landing (ambient mode: stages pulse
 * in a decorative loop) and the demo page (live mode: stages light from real
 * span data while a run executes). One component so the two can never drift.
 */

export const PIPELINE_STAGES = [
  { id: "precheck", label: "PRECHECK", sub: "injection · PII screen" },
  { id: "classify", label: "CLASSIFY", sub: "queue + margin" },
  { id: "retrieve", label: "RETRIEVE", sub: "KB evidence, k=3" },
  { id: "act", label: "ACT", sub: "account · entitlement tools" },
  { id: "gate", label: "GATE", sub: "multi-signal confidence" },
] as const;

export type StageState = "idle" | "active" | "done";

export default function Pipeline({
  mode,
  stageStates,
  outcome,
}: {
  mode: "ambient" | "live";
  /** live mode: state per stage id; omitted stages render idle */
  stageStates?: Partial<Record<string, StageState>>;
  /** live mode: which exit is lit once the run reaches a terminal state */
  outcome?: "auto_resolve" | "human_review" | null;
}) {
  const ambient = mode === "ambient";

  return (
    <div
      className={`pipeline ${mode === "live" ? "pipeline-live" : ""}`}
      role="img"
      aria-label="Pipeline: precheck, classify, retrieve, act, then a confidence gate. Runs exit either to auto-resolve (only above calibrated thresholds) or to human review (every denial exits here)."
    >
      {PIPELINE_STAGES.map((stage, i) => (
        <span key={stage.id} style={{ display: "contents" }}>
          {i > 0 && (
            <span className="flow" aria-hidden="true">
              ▸
            </span>
          )}
          <div
            className={`stage ${ambient ? `pl-${i + 1}` : ""}`}
            data-state={ambient ? undefined : (stageStates?.[stage.id] ?? "idle")}
          >
            <b>{stage.label}</b>
            <span>{stage.sub}</span>
          </div>
        </span>
      ))}
      <span className="flow" aria-hidden="true">
        ▸
      </span>
      <div className="outcomes">
        <div
          className={`outcome outcome-green ${ambient ? "pl-6" : ""}`}
          data-lit={!ambient && outcome === "auto_resolve" ? "true" : undefined}
        >
          <b>AUTO-RESOLVE</b>
          <span>only above calibrated thresholds</span>
        </div>
        <div
          className={`outcome ${ambient ? "pl-7" : ""}`}
          data-lit={!ambient && outcome === "human_review" ? "true" : undefined}
        >
          <b>HUMAN REVIEW</b>
          <span>every denial exits here</span>
        </div>
      </div>
    </div>
  );
}
