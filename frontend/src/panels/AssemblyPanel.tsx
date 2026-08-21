import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  AssemblyDefaultsResponse,
  type AssemblyBuildResponse,
  getAssemblyDefaults,
  postAssemblyBuild,
} from "../api/client";

interface AssemblyPanelProps {
  seed: number;
  busy: boolean;
  violations: string[] | null;
  onSeedChange: (seed: number) => void;
  onBusyChange: (busy: boolean) => void;
  onViolationsChange: (violations: string[] | null) => void;
  onBuilt: (response: AssemblyBuildResponse) => void;
  onFatal: (message: string) => void;
}

/** Joints read as English, not as the JSON we happen to send the backend. */
function describeJoint(joint: unknown): string | null {
  if (!joint || typeof joint !== "object") return null;
  const { type, parent } = joint as { type?: string; parent?: string };
  if (!parent) return null;
  if (type === "stack_on") return `stacked on ${parent}`;
  if (type === "concentric_insert") return `inserted into ${parent}`;
  return `${type ?? "joined"} → ${parent}`;
}

function normalizeIntField(
  e: React.ChangeEvent<HTMLInputElement>,
  n: number
) {
  const raw = e.target.value;
  if (raw !== String(n) && !/[-+.eE]$/.test(raw) && !Number.isNaN(n)) {
    e.target.value = String(n);
  }
}

export default function AssemblyPanel({
  seed,
  busy,
  violations,
  onSeedChange,
  onBusyChange,
  onViolationsChange,
  onBuilt,
  onFatal,
}: AssemblyPanelProps) {
  const [defaults, setDefaults] = useState<AssemblyDefaultsResponse | null>(null);
  const [profileId, setProfileId] = useState<string>("");

  useEffect(() => {
    getAssemblyDefaults()
      .then((d) => {
        setDefaults(d);
        setProfileId(d.gate_profiles.default);
      })
      .catch((e) =>
        onFatal(
          `Cannot reach the backend (/api/geometry/assembly/defaults): ${e.message}`
        )
      );
  }, [onFatal]);

  const elements = useMemo(() => {
    if (!defaults) return [];
    const p = defaults.primitives;
    return [
      {
        element_id: "plinth_01",
        primitive: "plinth",
        parameters: {
          ...defaultParams(p.plinth.parameters),
          top_diameter_mm: 2200,
          height_mm: 300,
          wall_mm: 120,
        },
      },
      {
        element_id: "basin_01",
        primitive: "basin_round",
        parameters: {
          ...defaultParams(p.basin_round.parameters),
          diameter_mm: 2000,
          height_mm: 450,
          wall_mm: 40,
          floor_mm: 160,
          min_clearance_mm: 220,
        },
        joint: { type: "stack_on", parent: "plinth_01" },
      },
      {
        element_id: "column_01",
        primitive: "sculptural_column",
        parameters: {
          ...defaultParams(p.sculptural_column.parameters),
          diameter_mm: 360,
          height_mm: 900,
          bore_mm: 80,
        },
        joint: { type: "concentric_insert", parent: "basin_01" },
      },
    ];
  }, [defaults]);

  const onBuild = () => {
    onBusyChange(true);
    onViolationsChange(null);
    postAssemblyBuild(
      elements,
      { max_lift_kg: 3000, max_module_m: 4.0 },
      seed,
      profileId || undefined
    )
      .then((resp) => {
        onBuilt(resp);
        onBusyChange(false);
      })
      .catch((e) => {
        onBusyChange(false);
        if (e instanceof ApiError && e.violations) {
          onViolationsChange(e.violations);
        } else {
          onFatal(`Assembly build failed: ${e.message}`);
        }
      });
  };

  if (!defaults) {
    return <div className="panel">Loading assembly registry...</div>;
  }

  const profile = defaults.gate_profiles.profiles[profileId];

  return (
    <div className="panel cascade-panel">
      <h2>Assembly manifest</h2>
      <p className="hint">
        Live primitives: {Object.keys(defaults.primitives).join(", ")}
      </p>
      {elements.map((el) => (
        <div className="assembly-element" key={String(el.element_id)}>
          <strong>{String(el.element_id)}</strong>
          <span>{String(el.primitive)}</span>
          {"joint" in el && <small>{describeJoint(el.joint)}</small>}
        </div>
      ))}

      <label className="param-row">
        <span className="param-name">gate profile</span>
        <select value={profileId} onChange={(e) => setProfileId(e.target.value)}>
          {Object.entries(defaults.gate_profiles.profiles).map(([id, p]) => (
            <option key={id} value={id}>
              {p.name}
            </option>
          ))}
        </select>
        <span className="param-unit">validation</span>
      </label>
      {profile && !profile.signed_off && (
        <p className="hint warn-hint">
          This profile is <strong>not signed off</strong>: threshold breaches
          report as warnings, not failures.
          {profile.unset_thresholds.length > 0 && (
            <>
              {" "}
              Unset ({profile.unset_thresholds.length}):{" "}
              <code>{profile.unset_thresholds.join(", ")}</code> — checks that
              need these report <strong>NEEDS INPUT</strong>. Fill them in{" "}
              <code>config/gate_profiles.yaml</code>.
            </>
          )}
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

      <button className="rebuild" onClick={onBuild} disabled={busy}>
        {busy ? "Building..." : "Build assembly"}
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

function defaultParams(parameters: AssemblyDefaultsResponse["primitives"][string]["parameters"]) {
  const out: Record<string, number | string | null> = {};
  for (const [name, spec] of Object.entries(parameters)) {
    out[name] = spec.default;
  }
  return out;
}
