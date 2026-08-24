// Read-only A/B judgement: synchronized CAD views plus the stored request
// differences that explain why the silhouettes changed.

import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { X } from "lucide-react";
import {
  designSceneGlbUrl,
  getDesignManifest,
  type DesignManifestResponse,
  type GateStatus,
} from "../api/client";
import type { VariantEntry } from "./HistoryStrip";
import WorkspaceViewport, {
  type CameraPose,
  type ViewportVisualMode,
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

interface DiffRow {
  label: string;
  a: string;
  b: string;
}

function display(value: unknown): string {
  if (value === undefined) return "Not set";
  if (value === null) return "Derived";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  return String(value);
}

function human(name: string): string {
  return name.replace(/_mm$/, "").replace(/_/g, " ");
}

function valuesOf(manifest: DesignManifestResponse): Map<string, { label: string; value: unknown }> {
  const values = new Map<string, { label: string; value: unknown }>();
  values.set("seed", { label: "Build seed", value: manifest.request.seed });
  for (const [name, value] of Object.entries(manifest.request.fabrication ?? {})) {
    values.set(`fabrication.${name}`, {
      label: `Fabrication / ${human(name)}`,
      value,
    });
  }
  (manifest.request.elements ?? []).forEach((raw, index) => {
    const element = raw as Record<string, unknown>;
    const id = String(element.element_id ?? `Element ${index + 1}`);
    values.set(`element.${index}.primitive`, {
      label: `${index + 1}. Element type`,
      value: element.primitive,
    });
    const params = (element.parameters ?? {}) as Record<string, unknown>;
    for (const [name, value] of Object.entries(params)) {
      values.set(`element.${index}.parameter.${name}`, {
        label: `${id} / ${human(name)}`,
        value,
      });
    }
    const joint = (element.joint ?? {}) as Record<string, unknown>;
    for (const [name, value] of Object.entries(joint)) {
      values.set(`element.${index}.joint.${name}`, {
        label: `${id} / joint ${human(name)}`,
        value,
      });
    }
  });
  return values;
}

function differences(a: DesignManifestResponse, b: DesignManifestResponse): DiffRow[] {
  const av = valuesOf(a);
  const bv = valuesOf(b);
  const keys = [...new Set([...av.keys(), ...bv.keys()])];
  return keys.flatMap((key) => {
    const left = av.get(key);
    const right = bv.get(key);
    if (JSON.stringify(left?.value) === JSON.stringify(right?.value)) return [];
    return [{
      label: left?.label ?? right?.label ?? key,
      a: display(left?.value),
      b: display(right?.value),
    }];
  });
}

function ComparePane({
  entry,
  viewportRef,
  visualMode,
  onCameraChange,
}: {
  entry: VariantEntry;
  viewportRef: RefObject<WorkspaceViewportHandle | null>;
  visualMode: ViewportVisualMode;
  onCameraChange: (pose: CameraPose) => void;
}) {
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
        {entry.total_mass_kg !== null && <span>{Math.round(entry.total_mass_kg)} kg</span>}
      </div>
      <div className="compare-canvas">
        <WorkspaceViewport
          ref={viewportRef}
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
          visualMode={visualMode}
          onCameraChange={onCameraChange}
        />
      </div>
    </div>
  );
}

export default function CompareView({
  a,
  b,
  visualMode,
  onClose,
}: {
  a: VariantEntry;
  b: VariantEntry;
  visualMode: ViewportVisualMode;
  onClose: () => void;
}) {
  const left = useRef<WorkspaceViewportHandle>(null);
  const right = useRef<WorkspaceViewportHandle>(null);
  const syncing = useRef(false);
  const [rows, setRows] = useState<DiffRow[] | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setDiffError(null);
    Promise.all([getDesignManifest(a.design_id), getDesignManifest(b.design_id)])
      .then(([am, bm]) => {
        if (!cancelled) setRows(differences(am, bm));
      })
      .catch((error: Error) => {
        if (!cancelled) setDiffError(error.message);
      });
    return () => { cancelled = true; };
  }, [a.design_id, b.design_id]);

  const mirror = (target: RefObject<WorkspaceViewportHandle | null>) => (pose: CameraPose) => {
    if (syncing.current) return;
    syncing.current = true;
    target.current?.applyCameraPose(pose);
    requestAnimationFrame(() => { syncing.current = false; });
  };

  return (
    <div className="compare-view">
      <div className="compare-bar">
        <span>A/B inspection / synchronized cameras / stored build values</span>
        <button
          type="button"
          onClick={onClose}
          title="Close comparison"
          aria-label="Close comparison"
        >
          <X size={15} />
        </button>
      </div>
      <div className="compare-panes">
        <ComparePane
          entry={a}
          viewportRef={left}
          visualMode={visualMode}
          onCameraChange={mirror(right)}
        />
        <ComparePane
          entry={b}
          viewportRef={right}
          visualMode={visualMode}
          onCameraChange={mirror(left)}
        />
      </div>
      <div className="compare-differences">
        <div className="compare-diff-head">
          <strong>Changed build values</strong>
          <span>{rows ? `${rows.length} differences` : "Loading values"}</span>
        </div>
        {diffError ? (
          <p className="error">Could not load build values: {diffError}</p>
        ) : rows && rows.length === 0 ? (
          <p className="hint">The stored requests have no parameter differences.</p>
        ) : (
          <div className="compare-table" role="table" aria-label="changed build values">
            {rows?.map((row) => (
              <div className="compare-row" role="row" key={row.label}>
                <span role="cell">{row.label}</span>
                <strong role="cell">{row.a}</strong>
                <strong role="cell">{row.b}</strong>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
