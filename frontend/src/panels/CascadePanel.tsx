// Cascade parameter panel — every registry parameter as a labelled numeric
// input with unit + range, straight from GET /api/geometry/cascade/defaults.

import { useState } from "react";
import type { DefaultsResponse } from "../api/client";

// Leading-zero drift (operator cosmetic report, 2026-08-04): an int field
// displays "04" after stepping. Mechanism — typing/stepping "04" fires
// onChange with Number("04") === 4, which EQUALS the current state, so
// React's same-value bailout skips the re-render and the DOM keeps the
// stale "04". Fix: for INTEGER fields only, force the DOM string to the
// normalized number when they disagree. NEVER do this for float fields:
// rewriting "0." to "0" would eat the decimal point mid-typing.
function normalizeIntField(
  e: React.ChangeEvent<HTMLInputElement>,
  n: number
) {
  const raw = e.target.value;
  if (raw !== String(n) && !/[-+.eE]$/.test(raw) && !Number.isNaN(n)) {
    e.target.value = String(n);
  }
}

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
      <p className="hint">
        Legacy single-primitive tool (Phases 2–4) with its own separate
        artifact — what you see here is the last cascade built, not your
        assembly. Assembly designs live under <strong>Build</strong>.
      </p>
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
              onChange={(e) => {
                const n = Number(e.target.value);
                onChange(name, n);
                if (spec.type === "int") normalizeIntField(e, n);
              }}
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
          onChange={(e) => {
            const n = Math.trunc(Number(e.target.value));
            onSeedChange(n);
            normalizeIntField(e, n);
          }}
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
