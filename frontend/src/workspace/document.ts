// The design document — the editable model behind the Designer Workspace.
//
// The workspace edits THIS structure; the backend build turns it into
// geometry. The document is deliberately the exact shape the assembly build
// endpoint accepts (elements + fabrication + seed + gate profile), so
// "what you edit" and "what gets built" can never drift apart. UI-only
// state (hidden/solo flags, selection) lives OUTSIDE the document, because
// it must not participate in undo/redo or affect the build payload.
//
// Undo/redo is a plain past/present/future stack over immutable snapshots.
// Every committed mutation goes through `apply`, which returns a new
// history — there is no mutable store to get out of sync.

import type { AssemblyDefaultsResponse, ParameterSpec } from "../api/client";

export interface JointDoc {
  type: string;
  parent: string;
  /** stack_on only — the assembler ignores offsets on other joint types. */
  x_offset_mm?: number;
  y_offset_mm?: number;
  overlap_mm?: number;
}

export interface ElementDoc {
  element_id: string;
  primitive: string;
  parameters: Record<string, number | string | null>;
  joint?: JointDoc;
}

export interface DesignDoc {
  elements: ElementDoc[];
  fabrication: Record<string, number | string>;
  seed: number;
  gateProfileId: string;
}

// ---------------------------------------------------------------------------
// Element construction
// ---------------------------------------------------------------------------

export function defaultParams(
  parameters: Record<string, ParameterSpec>
): Record<string, number | string | null> {
  const out: Record<string, number | string | null> = {};
  for (const [name, spec] of Object.entries(parameters)) {
    out[name] = spec.default;
  }
  return out;
}

/** plinth_01, plinth_02, ... — first id not already taken in the doc. */
export function nextElementId(doc: DesignDoc, primitive: string): string {
  const taken = new Set(doc.elements.map((e) => e.element_id));
  for (let n = 1; n < 100; n++) {
    const id = `${primitive}_${String(n).padStart(2, "0")}`;
    if (!taken.has(id)) return id;
  }
  // 99 of one primitive is beyond any real fountain; make the collision loud.
  throw new Error(`no free element id for primitive ${primitive}`);
}

/**
 * Where a new element attaches by default: stacked on the LAST element that
 * can parent a stack, because "add a basin, it lands on the plinth" is what
 * a designer expects. No candidate parent -> free-standing (no joint).
 */
export function defaultJoint(
  doc: DesignDoc,
  defaults: AssemblyDefaultsResponse
): JointDoc | undefined {
  for (let i = doc.elements.length - 1; i >= 0; i--) {
    const el = doc.elements[i];
    const info = defaults.primitives[el.primitive];
    if (info?.can_parent_stack) {
      return { type: "stack_on", parent: el.element_id };
    }
  }
  return undefined;
}

export function makeElement(
  doc: DesignDoc,
  primitive: string,
  defaults: AssemblyDefaultsResponse
): ElementDoc {
  const info = defaults.primitives[primitive];
  if (!info) throw new Error(`unknown primitive: ${primitive}`);
  return {
    element_id: nextElementId(doc, primitive),
    primitive,
    parameters: defaultParams(info.parameters),
    joint: defaultJoint(doc, defaults),
  };
}

// ---------------------------------------------------------------------------
// Document mutations — every edit the workspace can make
// ---------------------------------------------------------------------------

export type DocAction =
  | { kind: "add"; element: ElementDoc }
  | { kind: "remove"; elementId: string }
  | { kind: "duplicate"; elementId: string; newId: string }
  | {
      kind: "set-param";
      elementId: string;
      name: string;
      value: number | string | null;
    }
  | { kind: "set-joint"; elementId: string; joint: JointDoc | undefined }
  | { kind: "set-seed"; seed: number }
  | { kind: "set-gate-profile"; gateProfileId: string }
  | { kind: "set-fabrication"; name: string; value: number }
  | { kind: "replace"; doc: DesignDoc };

function mutate(doc: DesignDoc, action: DocAction): DesignDoc {
  switch (action.kind) {
    case "add":
      return { ...doc, elements: [...doc.elements, action.element] };
    case "remove": {
      // Children jointed to the removed element would orphan; re-parent them
      // to the removed element's own parent (or free-stand). Silently
      // dropping a joint would change the build in a way the designer never
      // asked for, so keep the structure as close as possible.
      const removed = doc.elements.find((e) => e.element_id === action.elementId);
      return {
        ...doc,
        elements: doc.elements
          .filter((e) => e.element_id !== action.elementId)
          .map((e) =>
            e.joint?.parent === action.elementId
              ? { ...e, joint: removed?.joint }
              : e
          ),
      };
    }
    case "duplicate": {
      const source = doc.elements.find((e) => e.element_id === action.elementId);
      if (!source) return doc;
      const copy: ElementDoc = {
        ...source,
        element_id: action.newId,
        parameters: { ...source.parameters },
        joint: source.joint ? { ...source.joint } : undefined,
      };
      const at = doc.elements.findIndex((e) => e.element_id === action.elementId);
      const elements = [...doc.elements];
      elements.splice(at + 1, 0, copy);
      return { ...doc, elements };
    }
    case "set-param":
      return {
        ...doc,
        elements: doc.elements.map((e) =>
          e.element_id === action.elementId
            ? { ...e, parameters: { ...e.parameters, [action.name]: action.value } }
            : e
        ),
      };
    case "set-joint":
      return {
        ...doc,
        elements: doc.elements.map((e) =>
          e.element_id === action.elementId ? { ...e, joint: action.joint } : e
        ),
      };
    case "set-seed":
      return { ...doc, seed: action.seed };
    case "set-gate-profile":
      return { ...doc, gateProfileId: action.gateProfileId };
    case "set-fabrication":
      return {
        ...doc,
        fabrication: { ...doc.fabrication, [action.name]: action.value },
      };
    case "replace":
      return action.doc;
  }
}

// ---------------------------------------------------------------------------
// History — undo/redo over document snapshots
// ---------------------------------------------------------------------------

export interface DocHistory {
  past: DesignDoc[];
  present: DesignDoc;
  future: DesignDoc[];
}

/** Beyond this the oldest snapshots fall off; 100 edits of a <100-element
 *  document is kilobytes, so the cap is about bounded behaviour, not RAM. */
const HISTORY_CAP = 100;

export function historyOf(doc: DesignDoc): DocHistory {
  return { past: [], present: doc, future: [] };
}

export function apply(h: DocHistory, action: DocAction): DocHistory {
  const next = mutate(h.present, action);
  if (next === h.present) return h;
  return {
    past: [...h.past.slice(-HISTORY_CAP + 1), h.present],
    present: next,
    future: [], // a new edit invalidates the redo branch, as everywhere
  };
}

/**
 * Replace the present WITHOUT a history entry — for continuous gestures
 * (dragging a slider) where each intermediate value must not become an undo
 * step. The gesture's start commits once via `apply`.
 */
export function amend(h: DocHistory, action: DocAction): DocHistory {
  return { ...h, present: mutate(h.present, action) };
}

export function undo(h: DocHistory): DocHistory {
  if (h.past.length === 0) return h;
  return {
    past: h.past.slice(0, -1),
    present: h.past[h.past.length - 1],
    future: [h.present, ...h.future],
  };
}

export function redo(h: DocHistory): DocHistory {
  if (h.future.length === 0) return h;
  return {
    past: [...h.past, h.present],
    present: h.future[0],
    future: h.future.slice(1),
  };
}

export const canUndo = (h: DocHistory) => h.past.length > 0;
export const canRedo = (h: DocHistory) => h.future.length > 0;

// ---------------------------------------------------------------------------
// The build payload — the document IS the request body
// ---------------------------------------------------------------------------

export function toBuildElements(
  doc: DesignDoc
): Array<Record<string, unknown>> {
  return doc.elements.map((e) => ({
    element_id: e.element_id,
    primitive: e.primitive,
    parameters: e.parameters,
    ...(e.joint ? { joint: e.joint } : {}),
  }));
}

/** The starter document: the proven three-element fountain the assembly
 *  panel has always built, so the workspace never opens onto nothing. */
export function starterDoc(defaults: AssemblyDefaultsResponse): DesignDoc {
  const p = defaults.primitives;
  const doc: DesignDoc = {
    elements: [],
    fabrication: { max_lift_kg: 3000, max_module_m: 4.0 },
    seed: 0,
    gateProfileId: defaults.gate_profiles.default,
  };
  if (!p.plinth || !p.basin_round || !p.sculptural_column) {
    // Registry changed under us — open empty rather than lie about what
    // exists. The library panel still offers whatever IS registered.
    return doc;
  }
  doc.elements = [
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
  return doc;
}
