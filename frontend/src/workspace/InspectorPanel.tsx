// Inspector — the contextual right panel: everything about ONE element.
//
// Parameters come from the live registry (unit, range, type), so the form
// is generated, never hardcoded per primitive. Values commit on blur/Enter
// — one undo step per committed edit, not per keystroke. Out-of-range
// values are NOT clamped client-side: the range is shown as a hint, and
// the backend's constraint engine reports breaches with real numbers
// (Rule 11) — silently "fixing" the designer's input would hide the rule.
//
// material_id renders as swatches (appearance.ts): identification colours,
// not rendered materials — the honest appearance channel is a render.

import type {
  AssemblyDefaultsResponse,
  ManifestElement,
  ParameterSpec,
} from "../api/client";
import { swatchFor } from "./appearance";
import type { DesignDoc, ElementDoc, JointDoc } from "./document";

interface InspectorPanelProps {
  doc: DesignDoc;
  element: ElementDoc | null;
  defaults: AssemblyDefaultsResponse;
  /** Built facts for this element from the last manifest, if any. */
  manifestElement: ManifestElement | null;
  onSetParam: (id: string, name: string, value: number | string | null) => void;
  onSetJoint: (id: string, joint: JointDoc | undefined) => void;
  onDuplicate: (id: string) => void;
  onRemove: (id: string) => void;
}

function fmt(n: number | null | undefined, digits = 1): string {
  return n === null || n === undefined ? "—" : n.toFixed(digits);
}

function rangeText(spec: ParameterSpec): string {
  if (spec.min !== null && spec.max !== null) return `${spec.min}–${spec.max}`;
  if (spec.min !== null) return `≥ ${spec.min}`;
  if (spec.max !== null) return `≤ ${spec.max}`;
  return "";
}

export default function InspectorPanel({
  doc,
  element,
  defaults,
  manifestElement,
  onSetParam,
  onSetJoint,
  onDuplicate,
  onRemove,
}: InspectorPanelProps) {
  if (!element) {
    return (
      <div className="panel inspector">
        <h2>Inspector</h2>
        <p className="hint">
          Click an element in the viewport or the scene list to edit it.
        </p>
      </div>
    );
  }

  const info = defaults.primitives[element.primitive];
  const params = info?.parameters ?? {};

  // Valid parents per joint type: registry capability minus self minus the
  // element's own descendants (an obvious cycle the backend would reject —
  // better to not offer it than to offer it and fail).
  const descendants = new Set<string>();
  let frontier = [element.element_id];
  while (frontier.length) {
    const next: string[] = [];
    for (const el of doc.elements) {
      if (el.joint && frontier.includes(el.joint.parent) && !descendants.has(el.element_id)) {
        descendants.add(el.element_id);
        next.push(el.element_id);
      }
    }
    frontier = next;
  }
  const parentsFor = (type: string) =>
    doc.elements.filter((el) => {
      if (el.element_id === element.element_id) return false;
      if (descendants.has(el.element_id)) return false;
      const p = defaults.primitives[el.primitive];
      if (!p) return false;
      return type === "stack_on" ? p.can_parent_stack : p.can_parent_insert;
    });

  const joint = element.joint;
  const otherRootExists = doc.elements.some(
    (el) => el.element_id !== element.element_id && !el.joint
  );

  return (
    <div className="panel inspector">
      <h2>
        {element.element_id}
        <span className="inspector-primitive">{element.primitive}</span>
      </h2>
      {info && <p className="hint">{info.purpose}</p>}

      {manifestElement ? (
        <div className="built-facts">
          <span title="from the built manifest — real numbers, not estimates">
            {fmt(manifestElement.mass_kg)} kg
          </span>
          <span>
            {manifestElement.bbox_mm.map((d) => Math.round(d)).join(" × ")} mm
          </span>
        </div>
      ) : (
        <p className="hint warn-hint">
          Not in the last build — press <strong>Build &amp; validate</strong> to
          see its geometry and real mass.
        </p>
      )}

      <div className="inspector-actions">
        <button type="button" onClick={() => onDuplicate(element.element_id)}>
          Duplicate
        </button>
        <button
          type="button"
          className="danger"
          onClick={() => onRemove(element.element_id)}
        >
          Delete
        </button>
      </div>

      <h4>Parameters</h4>
      {Object.entries(params).map(([name, spec]) => {
        const value = element.parameters[name];
        if (name === "material_id") {
          return (
            <div className="param-row swatch-row" key={name}>
              <span className="param-name">material</span>
              <span className="swatches">
                {Object.entries(defaults.materials).map(([mid, m]) => {
                  const sw = swatchFor(mid);
                  return (
                    <button
                      key={mid}
                      type="button"
                      className={`swatch ${value === mid ? "is-active" : ""}`}
                      style={{ background: sw.hex }}
                      title={`${m.name} — ${m.density_kg_per_m3} kg/m³ (colour is identification only)`}
                      onClick={() =>
                        onSetParam(element.element_id, name, mid)
                      }
                    />
                  );
                })}
              </span>
              <span className="param-unit">
                {typeof value === "string" ? swatchFor(value).label : "—"}
              </span>
            </div>
          );
        }
        if (spec.type === "str") {
          return (
            <label className="param-row" key={name}>
              <span className="param-name" title={spec.notes}>
                {name.replace(/_/g, " ")}
              </span>
              <input
                // Remount on external change (undo/redo) so the field shows
                // the document's value without being controlled per keystroke.
                key={`${element.element_id}:${name}:${String(value)}`}
                type="text"
                defaultValue={value === null ? "" : String(value)}
                onBlur={(e) => {
                  if (e.target.value !== String(value ?? "")) {
                    onSetParam(element.element_id, name, e.target.value);
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                }}
              />
              <span className="param-unit">{spec.unit}</span>
            </label>
          );
        }
        return (
          <label className="param-row" key={name}>
            <span className="param-name" title={spec.notes}>
              {name.replace(/_/g, " ")}
              {rangeText(spec) && (
                <small className="param-range">{rangeText(spec)}</small>
              )}
            </span>
            <input
              key={`${element.element_id}:${name}:${String(value)}`}
              type="number"
              step={spec.type === "int" ? 1 : "any"}
              defaultValue={value === null ? "" : Number(value)}
              onBlur={(e) => {
                const raw = e.target.value;
                if (raw === "") return;
                const n =
                  spec.type === "int" ? Math.trunc(Number(raw)) : Number(raw);
                if (!Number.isNaN(n) && n !== value) {
                  onSetParam(element.element_id, name, n);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              }}
            />
            <span className="param-unit">{spec.unit}</span>
          </label>
        );
      })}

      <h4>Joint</h4>
      <label className="param-row">
        <span className="param-name">attachment</span>
        <select
          value={joint?.type ?? "none"}
          onChange={(e) => {
            const type = e.target.value;
            if (type === "none") {
              onSetJoint(element.element_id, undefined);
              return;
            }
            const candidates = parentsFor(type);
            const keep =
              joint && candidates.some((c) => c.element_id === joint.parent)
                ? joint.parent
                : candidates[0]?.element_id;
            if (keep) onSetJoint(element.element_id, { type, parent: keep });
          }}
        >
          <option value="none">free-standing (root)</option>
          {defaults.joint_types.map((t) => (
            <option key={t} value={t} disabled={parentsFor(t).length === 0}>
              {t === "stack_on"
                ? "stacked on"
                : t === "concentric_insert"
                  ? "inserted into"
                  : t}
            </option>
          ))}
        </select>
        <span className="param-unit" />
      </label>
      {!joint && otherRootExists && (
        <p className="hint warn-hint">
          Another element is already free-standing — an assembly has exactly
          one root, so the build will refuse two.
        </p>
      )}
      {joint && (
        <label className="param-row">
          <span className="param-name">parent</span>
          <select
            value={joint.parent}
            onChange={(e) =>
              onSetJoint(element.element_id, { ...joint, parent: e.target.value })
            }
          >
            {parentsFor(joint.type).map((el) => (
              <option key={el.element_id} value={el.element_id}>
                {el.element_id}
              </option>
            ))}
          </select>
          <span className="param-unit" />
        </label>
      )}
      {joint?.type === "stack_on" && (
        <>
          {(["x_offset_mm", "y_offset_mm"] as const).map((k) => (
            <label className="param-row" key={k}>
              <span className="param-name">{k.replace(/_/g, " ")}</span>
              <input
                key={`${element.element_id}:${k}:${String(joint[k] ?? 0)}`}
                type="number"
                step="any"
                defaultValue={joint[k] ?? 0}
                onBlur={(e) => {
                  const n = Number(e.target.value);
                  if (!Number.isNaN(n) && n !== (joint[k] ?? 0)) {
                    onSetJoint(element.element_id, { ...joint, [k]: n });
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                }}
              />
              <span className="param-unit">mm</span>
            </label>
          ))}
        </>
      )}
    </div>
  );
}
