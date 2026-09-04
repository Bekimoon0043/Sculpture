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
import { Copy, Trash2 } from "lucide-react";
import { swatchFor } from "./appearance";
import type { DesignDoc, ElementDoc, JointDoc } from "./document";
import {
  type PresentedParameter,
  presentParameters,
} from "./parameterPresentation";

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

interface ParameterFieldProps {
  parameter: PresentedParameter;
  element: ElementDoc;
  defaults: AssemblyDefaultsResponse;
  onSetParam: InspectorPanelProps["onSetParam"];
}

function ParameterField({
  parameter: { name, spec, label },
  element,
  defaults,
  onSetParam,
}: ParameterFieldProps) {
  const value = element.parameters[name];
  if (name === "material_id") {
    return (
      <div className="designer-field material-field">
        <div className="field-heading">
          <span>{label}</span>
          <small>{typeof value === "string" ? swatchFor(value).label : "-"}</small>
        </div>
        <div className="swatches">
          {Object.entries(defaults.materials).map(([mid, material]) => {
            const swatch = swatchFor(mid);
            return (
              <button
                key={mid}
                type="button"
                className={`swatch ${value === mid ? "is-active" : ""}`}
                style={{ background: swatch.hex }}
                title={`${material.name} - ${material.density_kg_per_m3} kg/m3 (identification color only)`}
                aria-label={material.name}
                onClick={() => onSetParam(element.element_id, name, mid)}
              />
            );
          })}
        </div>
      </div>
    );
  }

  const commitText = (raw: string) => {
    if (raw !== String(value ?? "")) onSetParam(element.element_id, name, raw);
  };
  const commitNumber = (raw: string) => {
    if (raw === "") {
      if (spec.optional && value !== null) onSetParam(element.element_id, name, null);
      return;
    }
    const number = spec.type === "int" ? Math.trunc(Number(raw)) : Number(raw);
    if (!Number.isNaN(number) && number !== value) {
      onSetParam(element.element_id, name, number);
    }
  };

  return (
    <label className="designer-field">
      <span className="field-heading" title={spec.notes}>
        <span>{label}</span>
        <small>{rangeText(spec)}</small>
      </span>
      <span className="field-control">
        <input
          key={`${element.element_id}:${name}:${String(value)}`}
          type={spec.type === "str" ? "text" : "number"}
          step={spec.type === "int" ? 1 : "any"}
          min={spec.min ?? undefined}
          max={spec.max ?? undefined}
          defaultValue={value === null ? "" : value}
          onBlur={(event) =>
            spec.type === "str"
              ? commitText(event.target.value)
              : commitNumber(event.target.value)
          }
          onKeyDown={(event) => {
            if (event.key === "Enter") event.currentTarget.blur();
          }}
        />
        <span className="field-unit">{spec.unit}</span>
      </span>
    </label>
  );
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
  const presented = presentParameters(params);
  const primaryGroups = ["Form", "Water & services", "Material"] as const;
  const advanced = presented.filter((parameter) => parameter.advanced);

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
          {manifestElement.mass_model &&
          !manifestElement.mass_model.mass_complete ? (
            // FF-A1 (ADR-065): an incomplete mass is never shown as a
            // bare figure — the known-geometry basis and the missing
            // inputs travel with it, and there is no total to show.
            <span
              className="warn-hint"
              title={
                "known-geometry mass only — INCOMPLETE. Missing: " +
                manifestElement.mass_model.missing_mass_inputs.join("; ") +
                ". Total mass: unavailable."
              }
            >
              {fmt(manifestElement.mass_model.known_geometry_mass_kg)} kg
              (incomplete)
            </span>
          ) : (
            <span title="from the built manifest — measured geometry × material density">
              {fmt(manifestElement.mass_kg)} kg
            </span>
          )}
          <span>
            {manifestElement.bbox_mm.map((d) => Math.round(d)).join(" × ")} mm
          </span>
        </div>
      ) : (
        <p className="hint warn-hint">
          Not in the last build — press <strong>Build &amp; validate</strong> to
          see its geometry and its computed mass.
        </p>
      )}

      <div className="inspector-actions">
        <button type="button" onClick={() => onDuplicate(element.element_id)}>
          <Copy size={14} /> Duplicate
        </button>
        <button
          type="button"
          className="danger"
          onClick={() => onRemove(element.element_id)}
        >
          <Trash2 size={14} /> Delete
        </button>
      </div>

      {primaryGroups.map((group) => {
        const groupParameters = presented.filter(
          (parameter) => parameter.group === group && !parameter.advanced
        );
        if (groupParameters.length === 0) return null;
        return (
          <section className="parameter-group" key={group}>
            <h4>{group}</h4>
            {groupParameters.map((parameter) => (
              <ParameterField
                key={parameter.name}
                parameter={parameter}
                element={element}
                defaults={defaults}
                onSetParam={onSetParam}
              />
            ))}
          </section>
        );
      })}

      {advanced.length > 0 && (
        <details className="advanced-params">
          <summary>Advanced construction ({advanced.length})</summary>
          {advanced.map((parameter) => (
            <ParameterField
              key={parameter.name}
              parameter={parameter}
              element={element}
              defaults={defaults}
              onSetParam={onSetParam}
            />
          ))}
        </details>
      )}

      <h4>Placement</h4>
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
              <span className="param-name">{k === "x_offset_mm" ? "Left / right" : "Forward / back"}</span>
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
