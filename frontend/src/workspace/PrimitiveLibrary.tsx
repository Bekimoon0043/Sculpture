// Primitive catalog driven by the live registry. The focused item is rendered
// from a real kernel GLB; only one preview request runs at a time.

import { useEffect, useMemo, useState } from "react";
import { Box, LoaderCircle, Plus } from "lucide-react";
import {
  postAssemblyPreview,
  type AssemblyDefaultsResponse,
} from "../api/client";
import { defaultParams } from "./document";
import WorkspaceViewport from "./WorkspaceViewport";

interface PrimitiveLibraryProps {
  defaults: AssemblyDefaultsResponse;
  onAdd: (primitive: string) => void;
  disabled: boolean;
}

const NO_TINTS: Record<string, string> = {};
const NO_HIDDEN = new Set<string>();

export default function PrimitiveLibrary({
  defaults,
  onAdd,
  disabled,
}: PrimitiveLibraryProps) {
  const ids = Object.keys(defaults.primitives);
  const [focused, setFocused] = useState(ids[0] ?? "");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewMs, setPreviewMs] = useState<number | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const info = defaults.primitives[focused];
    if (!focused || !info) return;
    const abort = new AbortController();
    let nextUrl: string | null = null;
    setLoading(true);
    setPreviewError(null);
    postAssemblyPreview(
      [{
        element_id: "primitive_preview",
        primitive: focused,
        parameters: defaultParams(info.parameters),
      }],
      null,
      0,
      abort.signal
    )
      .then((preview) => {
        nextUrl = preview.objectUrl;
        setPreviewUrl((previous) => {
          if (previous) URL.revokeObjectURL(previous);
          return preview.objectUrl;
        });
        setPreviewMs(preview.buildMs);
        setLoading(false);
      })
      .catch((error: Error) => {
        if (error.name === "AbortError") return;
        setLoading(false);
        setPreviewError(error.message);
      });
    return () => {
      abort.abort();
      const completedUrl = nextUrl;
      if (completedUrl) {
        setPreviewUrl((current) => {
          if (current === completedUrl) {
            URL.revokeObjectURL(completedUrl);
            return null;
          }
          return current;
        });
      }
    };
  }, [defaults, focused]);

  useEffect(() => () => {
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return null;
    });
  }, []);

  const glbUrl = useMemo(
    () => previewUrl ? () => previewUrl : null,
    [previewUrl]
  );
  const focusedInfo = defaults.primitives[focused];

  return (
    <div className="lib-panel">
      <div className="library-heading">
        <div>
          <h3>Add element</h3>
          <p className="hint">Registry defaults / kernel geometry</p>
        </div>
        {previewMs !== null && <span>{Math.round(previewMs)} ms</span>}
      </div>
      <div className="primitive-preview">
        {glbUrl ? (
          <WorkspaceViewport
            reloadToken={ids.indexOf(focused)}
            glbUrl={glbUrl}
            elementIds={["primitive_preview"]}
            selectedId={null}
            onSelect={() => undefined}
            hiddenIds={NO_HIDDEN}
            soloId={null}
            tints={NO_TINTS}
            measureMode={false}
            onMeasure={() => undefined}
            section={null}
            onModelRendered={() => undefined}
            onLoadError={(message) => setPreviewError(message)}
            visualMode="studio"
            compact
          />
        ) : (
          <div className="primitive-preview-state">
            {loading ? <LoaderCircle className="spin" size={20} /> : <Box size={20} />}
            <span>{previewError ? "Preview unavailable" : "Building CAD preview"}</span>
          </div>
        )}
        <div className="primitive-preview-label">
          <strong>{focused.replace(/_/g, " ")}</strong>
          <span>{previewError ?? focusedInfo?.purpose}</span>
        </div>
      </div>
      <div className="primitive-options" role="listbox" aria-label="primitive type">
        {Object.entries(defaults.primitives).map(([id, info]) => (
          <button
            key={id}
            type="button"
            role="option"
            aria-selected={focused === id}
            className={`lib-card ${focused === id ? "is-focused" : ""}`}
            disabled={disabled}
            onMouseEnter={() => setFocused(id)}
            onFocus={() => setFocused(id)}
            onClick={() => onAdd(id)}
            title={`Add ${id.replace(/_/g, " ")}: ${info.purpose}`}
          >
            <span className="lib-card-text">
              <span className="lib-card-name">{id.replace(/_/g, " ")}</span>
              <span className="lib-card-purpose">{info.purpose}</span>
            </span>
            <Plus className="lib-card-add" size={16} aria-hidden="true" />
          </button>
        ))}
      </div>
    </div>
  );
}
