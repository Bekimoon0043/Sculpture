// Cascade parameter panel — every registry parameter as a labelled numeric
// input with unit + range, straight from GET /api/geometry/cascade/defaults.

import { useState } from "react";
import type { DefaultsResponse } from "../api/client";

interface CascadePanelProps {
  defaults: DefaultsResponse;
  values: Record<string, number | string>;
  seed: number;
  busy: boolean;
  violations: string[] | null;
  onChange: (name: string, value: number | string) => void;
  onSeedChange: (seed: number) => void;
  onRebuild: () => void;
}

export default function CascadePanel({
  defaults,
  values,
  seed,
  busy,
  violations,
  onChange,
  onSeedChange,
  onRebuild,
}: CascadePanelProps) {
  const [materialOpen, setMaterialOpen] = useState(false);

  return (
    <div className="panel cascade-panel">
      <h2>Cascade parameters</h2>
      {Object.entries(defaults.parameters).map(([name, spec]) => {
        if (spec.type === "str") {
          // material_id: a select over materials.yaml entries
          return (
            <label key={name} className="param-row">
              <span className="param-name">{name}</span>
              <select
                value={String(values[name] ?? spec.default)}
                onChange={(e) => {
                  onChange(name, e.target.value);
                  setMaterialOpen(true);
                }}
              >
                {Object.entries(defaults.materials).map(([id, m]) => (
                  <option key={id} value={id}>
                    {id} (min wall {m.min_wall_mm} mm)
                  </option>
                ))}
              </select>
              <span className="param-unit">{spec.unit}</span>
            </label>
          );
        }
        return (
          <label key={name} className="param-row" title={spec.notes ?? ""}>
            <span className="param-name">{name}</span>
            <input
              type="number"
              value={Number(values[name] ?? spec.default)}
              min={spec.min ?? undefined}
              max={spec.max ?? undefined}
              step={spec.type === "int" ? 1 : "any"}
              onChange={(e) => onChange(name, Number(e.target.value))}
            />
            <span className="param-unit">
              {spec.unit}
              {spec.min !== null && spec.max !== null
                ? ` [${spec.min}–${spec.max}]`
                : ""}
            </span>
          </label>
        );
      })}
      {materialOpen && (
        <p className="hint">
          Wall minimum follows the selected material (materials.yaml).
        </p>
      )}
      <label className="param-row">
        <span className="param-name">seed</span>
        <input
          type="number"
          value={seed}
          step={1}
          onChange={(e) => onSeedChange(Math.trunc(Number(e.target.value)))}
        />
        <span className="param-unit">determinism</span>
      </label>
      <button className="rebuild" onClick={onRebuild} disabled={busy}>
        {busy ? "Rebuilding…" : "Rebuild"}
      </button>
      {violations && (
        <div className="violations">
          <strong>Constraint violations (real numbers):</strong>
          <ul>
            {violations.map((v, i) => (
              <li key={i}>{v}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
