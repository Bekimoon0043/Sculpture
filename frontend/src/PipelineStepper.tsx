// The pipeline stepper — the product's spine, always visible.
//
// LuxuryForm is a pipeline: brief -> build -> validate -> export -> accept.
// Professional tools show the user where they ARE in the workflow, not just
// a pile of tabs. Each step's state is derived from real data (never a
// stored flag that can drift), and clicking a step navigates to the view
// that owns it.

export type StepState = "done" | "attention" | "active" | "pending";

export interface PipelineStep {
  key: string;
  label: string;
  state: StepState;
  /** One line shown under the label — the honest status, e.g. "needs input". */
  detail?: string;
  view: string;
  /** Build/Validate/Export share the Designer view; the tab says which
   *  right-rail surface the step actually means (2026-08-26: clicking
   *  Validate/Export visibly did nothing without it). */
  tab?: string;
}

const STATE_GLYPH: Record<StepState, string> = {
  done: "✓",
  attention: "!",
  active: "●",
  pending: "○",
};

export default function PipelineStepper({
  steps,
  activeView,
  onNavigate,
}: {
  steps: PipelineStep[];
  activeView: string;
  onNavigate: (view: string, tab?: string) => void;
}) {
  return (
    <ol className="pipeline" aria-label="design pipeline">
      {steps.map((step, i) => (
        <li key={step.key} className="pipeline-item">
          {i > 0 && <span className="pipeline-link" aria-hidden="true" />}
          <button
            type="button"
            className={[
              "pipeline-step",
              `is-${step.state}`,
              activeView === step.view ? "is-here" : "",
            ].join(" ")}
            onClick={() => onNavigate(step.view, step.tab)}
            title={step.detail ?? step.label}
          >
            <span className="pipeline-glyph" aria-hidden="true">
              {STATE_GLYPH[step.state]}
            </span>
            <span className="pipeline-text">
              <span className="pipeline-label">{step.label}</span>
              {step.detail && (
                <span className="pipeline-detail">{step.detail}</span>
              )}
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}
