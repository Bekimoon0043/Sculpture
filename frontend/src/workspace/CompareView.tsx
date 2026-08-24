// Side-by-side variant comparison — two independent viewports, one variant
// each. Read-only on purpose: comparison is for JUDGING, and the active
// document belongs to exactly one viewport (the main one). Each pane loads
// its design's per-element scene and states its verdict and mass, so the
// judgement is made against the real gate outcome, not just the silhouette.

import { useRef } from "react";
import type { GateStatus } from "../api/client";
import { designSceneGlbUrl } from "../api/client";
import type { VariantEntry } from "./HistoryStrip";
import WorkspaceViewport, {
  type WorkspaceViewportHandle,
} from "./WorkspaceViewport";

const STATUS_LABEL: Record<GateStatus, string> = {
  pass: "PASS",
  warn: "WARN",
  fail: "FAIL",
  needs_input: "NEEDS INPUT",
};

const NO_TINTS: Record<string, string> = {};
const NO_HIDDEN = new Set<string>();

function ComparePane({ entry }: { entry: VariantEntry }) {
  const handle = useRef<WorkspaceViewportHandle>(null);
  return (
    <div className="compare-pane">
      <div className="compare-caption">
        <strong>{entry.label}</strong>
        <span>seed {entry.seed}</span>
        {entry.overall_status && (
          <span className={`badge badge-${entry.overall_status}`}>
            {STATUS_LABEL[entry.overall_status]}
          </span>
        )}
        {entry.total_mass_kg !== null && (
          <span>{Math.round(entry.total_mass_kg)} kg</span>
        )}
      </div>
      <div className="compare-canvas">
        <WorkspaceViewport
          ref={handle}
          reloadToken={1}
          glbUrl={designSceneGlbUrl(entry.design_id)}
          elementIds={entry.element_ids}
          selectedId={null}
          onSelect={() => undefined}
          hiddenIds={NO_HIDDEN}
          soloId={null}
          tints={NO_TINTS}
          measureMode={false}
          onMeasure={() => undefined}
          section={null}
          onModelRendered={() => undefined}
          onLoadError={() => undefined}
        />
      </div>
    </div>
  );
}

export default function CompareView({
  a,
  b,
  onClose,
}: {
  a: VariantEntry;
  b: VariantEntry;
  onClose: () => void;
}) {
  return (
    <div className="compare-view">
      <div className="compare-bar">
        <span>Comparing two variants — geometry as built, orbit each freely.</span>
        <button type="button" onClick={onClose}>
          Close compare
        </button>
      </div>
      <div className="compare-panes">
        <ComparePane entry={a} />
        <ComparePane entry={b} />
      </div>
    </div>
  );
}
