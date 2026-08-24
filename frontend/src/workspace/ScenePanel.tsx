// Scene panel — the document's element list under the library.
//
// One row per element: select (click), hide (eye), solo (target). The list
// reflects the DOCUMENT (what the next build will contain), while the eye
// and solo act on the VIEWPORT (what is on screen from the last build) —
// an element added since the last build is listed but marked "unbuilt",
// because there is no geometry of it to show or hide yet.

import { useEffect, useRef, useState } from "react";
import { CircleDot, Eye, EyeOff } from "lucide-react";
import type { ElementDoc } from "./document";

interface ScenePanelProps {
  elements: ElementDoc[];
  /** element ids present in the currently loaded scene GLB. */
  builtIds: Set<string>;
  selectedId: string | null;
  hiddenIds: Set<string>;
  soloId: string | null;
  onSelect: (id: string | null) => void;
  onToggleHidden: (id: string) => void;
  onToggleSolo: (id: string) => void;
  /** Blender-outliner rename: double-click (or F2 on the selection). */
  onRename: (id: string, newId: string) => void;
  /** Set by the F2 shortcut; the panel opens that row's editor. */
  renameRequestId: string | null;
  onRenameRequestHandled: () => void;
}

function jointText(el: ElementDoc): string {
  if (!el.joint) return "free-standing";
  if (el.joint.type === "stack_on") return `on ${el.joint.parent}`;
  if (el.joint.type === "concentric_insert") return `into ${el.joint.parent}`;
  return `${el.joint.type} → ${el.joint.parent}`;
}

export default function ScenePanel({
  elements,
  builtIds,
  selectedId,
  hiddenIds,
  soloId,
  onSelect,
  onToggleHidden,
  onToggleSolo,
  onRename,
  renameRequestId,
  onRenameRequestHandled,
}: ScenePanelProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const editRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (renameRequestId) {
      setEditingId(renameRequestId);
      onRenameRequestHandled();
    }
  }, [renameRequestId, onRenameRequestHandled]);
  useEffect(() => {
    if (editingId) editRef.current?.select();
  }, [editingId]);

  const commitRename = (oldId: string, raw: string) => {
    setEditingId(null);
    const next = raw.trim();
    if (next && next !== oldId) onRename(oldId, next);
  };

  return (
    <div className="scene-panel">
      <h3>Scene</h3>
      {elements.length === 0 && (
        <p className="hint">No elements yet. Use Add in the command bar.</p>
      )}
      <ul className="scene-list">
        {elements.map((el) => {
          const built = builtIds.has(el.element_id);
          const hidden = hiddenIds.has(el.element_id);
          const solo = soloId === el.element_id;
          return (
            <li
              key={el.element_id}
              className={[
                "scene-row",
                selectedId === el.element_id ? "is-selected" : "",
                built ? "" : "is-unbuilt",
              ].join(" ")}
            >
              {editingId === el.element_id ? (
                <input
                  ref={editRef}
                  className="scene-rename"
                  defaultValue={el.element_id}
                  onBlur={(e) => commitRename(el.element_id, e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter")
                      commitRename(el.element_id, e.currentTarget.value);
                    if (e.key === "Escape") setEditingId(null);
                    e.stopPropagation();
                  }}
                />
              ) : (
                <button
                  type="button"
                  className="scene-name"
                  onClick={() => onSelect(el.element_id)}
                  onDoubleClick={() => setEditingId(el.element_id)}
                  title={`${el.primitive} — ${jointText(el)}\ndouble-click (or F2) to rename`}
                >
                  <span>{el.element_id}</span>
                  <small>{built ? jointText(el) : "unbuilt — press Build"}</small>
                </button>
              )}
              <button
                type="button"
                className={`scene-tool ${hidden ? "is-on" : ""}`}
                disabled={!built || soloId !== null}
                onClick={() => onToggleHidden(el.element_id)}
                title={hidden ? "show" : "hide"}
                aria-label={`${hidden ? "show" : "hide"} ${el.element_id}`}
              >
                {hidden ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
              <button
                type="button"
                className={`scene-tool ${solo ? "is-on" : ""}`}
                disabled={!built}
                onClick={() => onToggleSolo(el.element_id)}
                title={solo ? "end solo" : "solo — show only this"}
                aria-label={`solo ${el.element_id}`}
              >
                <CircleDot size={15} />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
