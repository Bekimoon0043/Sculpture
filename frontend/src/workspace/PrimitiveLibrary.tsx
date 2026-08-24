// Primitive library — the left rail's catalog, driven by the LIVE registry
// (/api/geometry/assembly/defaults), never a hardcoded list: a primitive
// added to the backend appears here with no frontend change.
//
// Thumbnails are SCHEMATIC line art (drawn SVG, labelled as such in the
// visual gate), not rendered geometry — rendering every primitive at
// startup would cost a full OCCT build per card on a machine where each
// build is seconds (LIMITATIONS.md, Phase 14). Unknown primitives get a
// generic solid glyph, so the card is never blank.

import type { AssemblyDefaultsResponse } from "../api/client";

interface PrimitiveLibraryProps {
  defaults: AssemblyDefaultsResponse;
  onAdd: (primitive: string) => void;
  disabled: boolean;
}

const S = {
  stroke: "var(--text-dim)",
  accent: "var(--accent)",
  fill: "none",
  w: 1.6,
};

function Glyph({ primitive }: { primitive: string }) {
  const common = {
    fill: S.fill,
    stroke: S.stroke,
    strokeWidth: S.w,
    strokeLinejoin: "round" as const,
  };
  switch (primitive) {
    case "plinth":
      return (
        <svg viewBox="0 0 64 64" className="lib-glyph" aria-hidden="true">
          {/* squat truncated cone: wide stable base */}
          <ellipse cx="32" cy="46" rx="24" ry="7" {...common} />
          <ellipse cx="32" cy="30" rx="19" ry="6" {...common} />
          <path d="M8 46 L13 30 M56 46 L51 30" {...common} />
        </svg>
      );
    case "basin_round":
      return (
        <svg viewBox="0 0 64 64" className="lib-glyph" aria-hidden="true">
          {/* open bowl with a water line */}
          <ellipse cx="32" cy="24" rx="24" ry="8" {...common} />
          <path d="M8 24 C10 44, 22 50, 32 50 C42 50, 54 44, 56 24" {...common} />
          <path d="M16 27 C22 31, 42 31, 48 27" stroke={S.accent} strokeWidth={S.w} fill="none" />
        </svg>
      );
    case "sculptural_column":
      return (
        <svg viewBox="0 0 64 64" className="lib-glyph" aria-hidden="true">
          {/* slender column with a bore */}
          <ellipse cx="32" cy="10" rx="9" ry="4" {...common} />
          <path d="M23 10 L23 52 M41 10 L41 52" {...common} />
          <ellipse cx="32" cy="52" rx="9" ry="4" {...common} />
          <path d="M29 10 L29 52 M35 10 L35 52" stroke={S.stroke} strokeWidth={0.9} strokeDasharray="2 2.5" fill="none" />
        </svg>
      );
    case "cascade":
      return (
        <svg viewBox="0 0 64 64" className="lib-glyph" aria-hidden="true">
          {/* stepped tiers */}
          <path d="M10 52 H54 M14 52 V40 H50 V52 M20 40 V28 H44 V40 M26 28 V16 H38 V28" {...common} />
          <path d="M32 16 V10" stroke={S.accent} strokeWidth={S.w} fill="none" />
        </svg>
      );
    default:
      return (
        <svg viewBox="0 0 64 64" className="lib-glyph" aria-hidden="true">
          <path d="M16 22 L32 14 L48 22 L48 44 L32 52 L16 44 Z M16 22 L32 30 L48 22 M32 30 V52" {...common} />
        </svg>
      );
  }
}

export default function PrimitiveLibrary({
  defaults,
  onAdd,
  disabled,
}: PrimitiveLibraryProps) {
  return (
    <div className="lib-panel">
      <h3>Library</h3>
      <p className="hint">Click to add to the assembly.</p>
      {Object.entries(defaults.primitives).map(([id, info]) => (
        <button
          key={id}
          type="button"
          className="lib-card"
          disabled={disabled}
          onClick={() => onAdd(id)}
          title={info.purpose}
        >
          <Glyph primitive={id} />
          <span className="lib-card-text">
            <span className="lib-card-name">{id.replace(/_/g, " ")}</span>
            <span className="lib-card-purpose">{info.purpose}</span>
          </span>
          <span className="lib-card-add" aria-hidden="true">+</span>
        </button>
      ))}
    </div>
  );
}
