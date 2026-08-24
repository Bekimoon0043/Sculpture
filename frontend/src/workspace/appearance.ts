// Material display colours — UI IDENTIFICATION ONLY, not a render claim.
//
// The backend material model (materials.yaml) is engineering numbers:
// density, wall envelopes, joint floors. It carries NO appearance data —
// no colour, roughness or texture (LIMITATIONS.md, Phase 14). These
// swatches exist so a designer can tell at a glance which element carries
// which material; the honest appearance channel is the Phase 9B render.
//
// Known ids get a recognisable hue; an unknown id (a future materials.yaml
// entry) falls back to a colour DERIVED from its id hash, so two new
// materials never silently share a swatch.

export interface Swatch {
  hex: string;
  label: string;
}

const KNOWN: Record<string, Swatch> = {
  stainless_316l_sheet: { hex: "#9fb2c4", label: "316L stainless" },
  basalt_slab: { hex: "#5b6068", label: "Basalt" },
  cast_concrete_c35_45: { hex: "#a8a29a", label: "Concrete C35/45" },
  bronze_cast: { hex: "#a97c50", label: "Cast bronze" },
};

/** Deterministic fallback hue from the id — stable across sessions. */
function hashHex(id: string): string {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  const hue = h % 360;
  return `hsl(${hue}, 25%, 55%)`;
}

export function swatchFor(materialId: string): Swatch {
  return (
    KNOWN[materialId] ?? { hex: hashHex(materialId), label: materialId }
  );
}

/** Viewport tint map for a document: element id -> colour of its material. */
export function tintsFor(
  elements: Array<{ element_id: string; parameters: Record<string, unknown> }>
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const el of elements) {
    const mid = el.parameters["material_id"];
    if (typeof mid === "string" && mid) out[el.element_id] = swatchFor(mid).hex;
  }
  return out;
}
