// Designer Workspace — Phase 14. Library | viewport | inspector | history.
//
// The state model in one paragraph: the DOCUMENT (document.ts) is what the
// designer edits, with undo/redo; the VIEWPORT shows the geometry of the
// last BUILD (activeDesignId's scene.glb), never a client-side guess at
// unbuilt edits; DIRTY means the two differ, and "Build & validate" is the
// only bridge. Every build lands in the HISTORY strip as a restorable
// variant. This keeps Rule 5 on screen: the deterministic kernel draws,
// the UI edits the program the kernel will receive.

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ApiError,
  type AssemblyBuildResponse,
  type AssemblyDefaultsResponse,
  type DesignManifestResponse,
  type ExportsResponse,
  type GateStatus,
  type IntakeResponse,
  type LatestValidationResponse,
  type ManifestElement,
  type RenderJob,
  type Validation,
  type ValidationGate,
  designSceneGlbUrl,
  getAssemblyDefaults,
  getAssemblyExports,
  getDesignManifest,
  getDesignValidation,
  getLatestAssemblyValidation,
  getRenderJob,
  listDesigns,
  postAssemblyBuild,
  postAssemblyExports,
  postRenderJob,
  renderViewUrl,
} from "../api/client";
import ErrorBoundary from "../ErrorBoundary";
import ExportPanel from "../panels/ExportPanel";
import ValidationPanel from "../panels/ValidationPanel";
import CompareView from "./CompareView";
import HistoryStrip, { type VariantEntry } from "./HistoryStrip";
import InspectorPanel from "./InspectorPanel";
import PrimitiveLibrary from "./PrimitiveLibrary";
import ScenePanel from "./ScenePanel";
import WorkspaceViewport, {
  type CameraPose,
  type MeasureResult,
  type SectionState,
  type WorkspaceViewportHandle,
  formatMm,
} from "./WorkspaceViewport";
import { tintsFor } from "./appearance";
import {
  type DesignDoc,
  type DocHistory,
  type ElementDoc,
  type JointDoc,
  apply,
  canRedo,
  canUndo,
  historyOf,
  makeElement,
  nextElementId,
  redo,
  starterDoc,
  toBuildElements,
  undo,
} from "./document";

// ---------------------------------------------------------------------------
// localStorage caches — conveniences, never sources of truth
// ---------------------------------------------------------------------------

const THUMBS_KEY = "lf_thumbs_v1";
const VIEWS_KEY = "lf_saved_views_v1";
const THUMBS_CAP = 40;

function loadThumbs(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(THUMBS_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function saveThumb(designId: string, dataUrl: string, keepOrder: string[]) {
  try {
    const thumbs = loadThumbs();
    thumbs[designId] = dataUrl;
    // Prune to the newest designs we still show — snapshots of designs that
    // fell off the strip are dead weight in a 5-10 MB quota.
    const keep = new Set(keepOrder.slice(0, THUMBS_CAP));
    for (const key of Object.keys(thumbs)) {
      if (!keep.has(key)) delete thumbs[key];
    }
    localStorage.setItem(THUMBS_KEY, JSON.stringify(thumbs));
  } catch {
    /* quota/private mode — thumbnails are a convenience */
  }
}

interface SavedView {
  name: string;
  pose: CameraPose;
}

function loadSavedViews(): SavedView[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(VIEWS_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------

function docFromRequest(
  request: DesignManifestResponse["request"]
): DesignDoc {
  return {
    elements: (request.elements ?? []).map((raw) => {
      const el = raw as Record<string, unknown>;
      return {
        element_id: String(el.element_id),
        primitive: String(el.primitive),
        parameters: { ...(el.parameters as Record<string, number | string | null>) },
        ...(el.joint ? { joint: { ...(el.joint as JointDoc) } } : {}),
      } as ElementDoc;
    }),
    fabrication: { ...(request.fabrication ?? {}) },
    seed: Number(request.seed ?? 0),
    gateProfileId: String(request.gate_profile_id ?? ""),
  };
}

function variantLabel(primitives: string[]): string {
  return primitives.length ? primitives.join(" + ") : "empty assembly";
}

interface DesignerWorkspaceProps {
  intake: IntakeResponse | null;
  onFatal: (message: string) => void;
  /** Pipeline facts the App shell derives the stepper/status bar from. */
  onPipelineChange: (facts: {
    designId: string | null;
    overallStatus: GateStatus | null;
    exports: ExportsResponse | null;
  }) => void;
}

export default function DesignerWorkspace({
  intake,
  onFatal,
  onPipelineChange,
}: DesignerWorkspaceProps) {
  const [defaults, setDefaults] = useState<AssemblyDefaultsResponse | null>(null);
  const [history, setHistory] = useState<DocHistory | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hiddenIds, setHiddenIds] = useState<Set<string>>(new Set());
  const [soloId, setSoloId] = useState<string | null>(null);
  const [measureMode, setMeasureMode] = useState(false);
  const [measure, setMeasure] = useState<MeasureResult | null>(null);
  const [sectionOn, setSectionOn] = useState(false);
  const [section, setSection] = useState<SectionState>({ axis: "y", offset: 1 });
  const [savedViews, setSavedViews] = useState<SavedView[]>(loadSavedViews);
  const [useIntake, setUseIntake] = useState(true);

  // What the viewport shows.
  const [activeDesignId, setActiveDesignId] = useState<string | null>(null);
  const [builtElements, setBuiltElements] = useState<ManifestElement[]>([]);
  const [lastBuiltJson, setLastBuiltJson] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [busy, setBusy] = useState(false);
  const [violations, setViolations] = useState<string[] | null>(null);
  const [buildMs, setBuildMs] = useState<number | null>(null);

  // Validation + exports (shown in the right column, reported to the App).
  const [validation, setValidation] = useState<Validation | null>(null);
  const [gates, setGates] = useState<Record<string, ValidationGate> | null>(null);
  const [gateStatuses, setGateStatuses] =
    useState<Record<string, GateStatus> | null>(null);
  const [overallStatus, setOverallStatus] = useState<GateStatus | null>(null);
  const [exports, setExports] = useState<ExportsResponse | null>(null);
  const [exporting, setExporting] = useState(false);

  // History strip.
  const [variants, setVariants] = useState<VariantEntry[]>([]);
  const [compareIds, setCompareIds] = useState<string[]>([]);

  // Render drawer.
  const [renderOpen, setRenderOpen] = useState(false);
  const [renderJob, setRenderJob] = useState<RenderJob | null>(null);
  const [renderNote, setRenderNote] = useState<string | null>(null);
  const renderAbort = useRef(false);

  const viewportRef = useRef<WorkspaceViewportHandle>(null);
  const pendingThumbFor = useRef<string | null>(null);

  const doc = history?.present ?? null;

  // ------------------------------------------------------------------ boot
  useEffect(() => {
    let cancelled = false;
    (async () => {
      let d: AssemblyDefaultsResponse;
      try {
        d = await getAssemblyDefaults();
      } catch (e: any) {
        onFatal(`Cannot reach the backend (/api/geometry/assembly/defaults): ${e.message}`);
        return;
      }
      if (cancelled) return;
      setDefaults(d);

      // Continuity: reopen on the latest built design when there is one —
      // its stored request IS the document. Otherwise the starter document.
      const list = await listDesigns(50).catch(() => null);
      if (cancelled) return;
      const thumbs = loadThumbs();
      if (list && list.designs.length > 0) {
        setVariants(
          list.designs.map((s) => ({
            design_id: s.design_id,
            created_at: s.created_at,
            label: variantLabel(s.primitives),
            seed: s.seed,
            overall_status: s.overall_status,
            total_mass_kg: s.total_mass_kg,
            thumbnail: thumbs[s.design_id] ?? null,
            element_ids: s.element_ids,
          }))
        );
        const newest = list.designs[0];
        try {
          const m = await getDesignManifest(newest.design_id);
          if (cancelled) return;
          setHistory(historyOf(docFromRequest(m.request)));
          setActiveDesignId(newest.design_id);
          setBuiltElements(m.manifest.elements);
          setLastBuiltJson(JSON.stringify(docFromRequest(m.request)));
          setReloadToken((t) => t + 1);
        } catch {
          setHistory(historyOf(starterDoc(d)));
        }
        const v = await getLatestAssemblyValidation().catch(() => null);
        if (!cancelled && v) applyValidation(v);
        const e = await getAssemblyExports(newest.design_id).catch(() => null);
        if (!cancelled && e) setExports(e);
      } else {
        setHistory(historyOf(starterDoc(d)));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const applyValidation = (v: LatestValidationResponse) => {
    setValidation(v.validation);
    setGates(v.gates ?? null);
    setGateStatuses(v.gate_statuses ?? null);
    setOverallStatus(v.overall_status ?? null);
  };

  // Report pipeline facts upward whenever they change.
  useEffect(() => {
    onPipelineChange({ designId: activeDesignId, overallStatus, exports });
  }, [activeDesignId, overallStatus, exports, onPipelineChange]);

  // ------------------------------------------------------------- edits
  const dispatch = useCallback((action: Parameters<typeof apply>[1]) => {
    setHistory((h) => (h ? apply(h, action) : h));
  }, []);

  const onAdd = useCallback(
    (primitive: string) => {
      if (!doc || !defaults) return;
      const element = makeElement(doc, primitive, defaults);
      dispatch({ kind: "add", element });
      setSelectedId(element.element_id);
    },
    [doc, defaults, dispatch]
  );

  const onDuplicate = useCallback(
    (elementId: string) => {
      if (!doc) return;
      const source = doc.elements.find((e) => e.element_id === elementId);
      if (!source) return;
      const newId = nextElementId(doc, source.primitive);
      dispatch({ kind: "duplicate", elementId, newId });
      // A copy in the exact same place is an undeclared interference the
      // build will refuse. For a stack_on joint we can offset the copy
      // sideways by the source's BUILT width (manifest bbox — a real
      // number). An insert has no offset in the joint model: leave it and
      // let the inspector's hint say why the next build will refuse it.
      if (source.joint?.type === "stack_on") {
        const built = builtElements.find((m) => m.element_id === elementId);
        const width = built ? built.bbox_mm[0] : null;
        const shift =
          (source.joint.x_offset_mm ?? 0) + (width ? width + 100 : 500);
        dispatch({
          kind: "set-joint",
          elementId: newId,
          joint: { ...source.joint, x_offset_mm: shift },
        });
      }
      setSelectedId(newId);
    },
    [doc, builtElements, dispatch]
  );

  const onRemove = useCallback(
    (elementId: string) => {
      dispatch({ kind: "remove", elementId });
      setSelectedId((s) => (s === elementId ? null : s));
    },
    [dispatch]
  );

  // Keyboard: undo/redo/delete — never while typing in a field.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
        e.preventDefault();
        setHistory((h) => (h ? undo(h) : h));
      } else if (
        ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") ||
        ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "z")
      ) {
        e.preventDefault();
        setHistory((h) => (h ? redo(h) : h));
      } else if (e.key === "Delete" && selectedId) {
        e.preventDefault();
        onRemove(selectedId);
      } else if (e.key === "Escape") {
        setMeasureMode(false);
        setSelectedId(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedId, onRemove]);

  // ------------------------------------------------------------- build
  const intakeReady = Boolean(intake && intake.status === "confirmed");
  const dirty = doc ? JSON.stringify(doc) !== lastBuiltJson : false;

  const onBuild = useCallback(() => {
    if (!doc) return;
    setBusy(true);
    setViolations(null);
    postAssemblyBuild(
      toBuildElements(doc),
      doc.fabrication,
      doc.seed,
      doc.gateProfileId || undefined,
      useIntake && intakeReady ? intake!.id : undefined
    )
      .then((resp: AssemblyBuildResponse) => {
        setBusy(false);
        setActiveDesignId(resp.design_id);
        setBuiltElements(
          (resp.manifest.elements as unknown as ManifestElement[]) ?? []
        );
        setLastBuiltJson(JSON.stringify(doc));
        setBuildMs(resp.build_ms);
        setValidation(resp.validation);
        setGates(resp.validation_gates);
        setGateStatuses({
          ...Object.fromEntries(
            Object.entries(resp.validation_gates).map(([k, g]) => [k, g.status])
          ),
          assembly_mesh: resp.validation.passed ? "pass" : "fail",
        });
        setOverallStatus(resp.overall_status ?? null);
        setExports(null);
        getAssemblyExports(resp.design_id).then(setExports).catch(() => undefined);
        setHiddenIds(new Set());
        setSoloId(null);
        pendingThumbFor.current = resp.design_id;
        setReloadToken((t) => t + 1);
        setVariants((prev) => [
          {
            design_id: resp.design_id,
            created_at: new Date().toISOString(),
            label: variantLabel(doc.elements.map((e) => e.primitive)),
            seed: doc.seed,
            overall_status: resp.overall_status ?? null,
            total_mass_kg:
              (resp.manifest as { total_mass_kg?: number }).total_mass_kg ?? null,
            thumbnail: null,
            element_ids: doc.elements.map((e) => e.element_id),
          },
          ...prev,
        ]);
      })
      .catch((e) => {
        setBusy(false);
        if (e instanceof ApiError && e.violations) setViolations(e.violations);
        else onFatal(`Assembly build failed: ${e.message}`);
      });
  }, [doc, useIntake, intakeReady, intake, onFatal]);

  // Thumbnail: captured only when the new geometry is actually on screen.
  const onModelRendered = useCallback(() => {
    const designId = pendingThumbFor.current;
    if (!designId) return;
    pendingThumbFor.current = null;
    const shot = viewportRef.current?.snapshot(320) ?? null;
    if (!shot) return;
    setVariants((prev) => {
      const next = prev.map((v) =>
        v.design_id === designId ? { ...v, thumbnail: shot } : v
      );
      saveThumb(designId, shot, next.map((v) => v.design_id));
      return next;
    });
  }, []);

  // ------------------------------------------------------------- restore
  const onRestore = useCallback(
    (entry: VariantEntry) => {
      getDesignManifest(entry.design_id)
        .then((m) => {
          const restored = docFromRequest(m.request);
          setHistory((h) => (h ? apply(h, { kind: "replace", doc: restored }) : h));
          setActiveDesignId(entry.design_id);
          setBuiltElements(m.manifest.elements);
          setLastBuiltJson(JSON.stringify(restored));
          setSelectedId(null);
          setHiddenIds(new Set());
          setSoloId(null);
          pendingThumbFor.current = entry.thumbnail ? null : entry.design_id;
          setReloadToken((t) => t + 1);
          getDesignValidation(entry.design_id)
            .then((v) => v && applyValidation(v))
            .catch(() => undefined);
          getAssemblyExports(entry.design_id)
            .then(setExports)
            .catch(() => undefined);
        })
        .catch((e) => onFatal(`Could not open variant: ${e.message}`));
    },
    [onFatal]
  );

  // ------------------------------------------------------------- export
  const onExport = useCallback(() => {
    if (!activeDesignId) return;
    setExporting(true);
    postAssemblyExports(activeDesignId)
      .then(() => getAssemblyExports(activeDesignId))
      .then((e) => {
        setExports(e);
        setExporting(false);
      })
      .catch((e) => {
        setExporting(false);
        onFatal(`Export failed: ${e.message}`);
      });
  }, [activeDesignId, onFatal]);

  // ------------------------------------------------------------- render
  const onRender = useCallback(async () => {
    if (!activeDesignId) return;
    setRenderOpen(true);
    setRenderJob(null);
    setRenderNote("Queueing render job…");
    renderAbort.current = false;
    let job: RenderJob;
    try {
      job = await postRenderJob(activeDesignId);
    } catch (e: any) {
      setRenderNote(`Could not queue the render: ${e.message}`);
      return;
    }
    const t0 = Date.now();
    const DEADLINE_MS = 15 * 60 * 1000;
    // The GET blocks server-side up to ~30 s; a "no result within Ns" error
    // means still-rendering OR worker off — keep waiting, say both, and
    // give up only at the deadline. Rendering four Cycles views on this
    // CPU takes minutes; a 30 s "failed" would be a lie.
    for (;;) {
      if (renderAbort.current) return;
      let polled: RenderJob;
      try {
        polled = await getRenderJob(job.id);
      } catch (e: any) {
        setRenderNote(`Render poll failed: ${e.message}`);
        return;
      }
      if (renderAbort.current) return;
      if (polled.status === "done") {
        setRenderJob(polled);
        setRenderNote(null);
        return;
      }
      const stillWaiting =
        polled.error && polled.error.includes("produced no result within");
      if (!stillWaiting) {
        setRenderJob(polled);
        setRenderNote(polled.error ?? "Render failed with no error message.");
        return;
      }
      const elapsed = Math.round((Date.now() - t0) / 1000);
      if (Date.now() - t0 > DEADLINE_MS) {
        setRenderNote(
          `No result after ${elapsed}s. Either the render-worker is not running ` +
            `(start it: docker compose --profile render up -d render-worker) or ` +
            `the render is exceptionally slow. Check: docker compose ps render-worker`
        );
        return;
      }
      setRenderNote(
        `Rendering… ${elapsed}s elapsed (four Cycles CPU views take minutes on ` +
          `this machine). If nothing arrives, check the render-worker container.`
      );
    }
  }, [activeDesignId]);

  // ------------------------------------------------------------- derived
  const selected = doc?.elements.find((e) => e.element_id === selectedId) ?? null;
  const manifestSelected =
    builtElements.find((m) => m.element_id === selectedId) ?? null;
  const builtIds = useMemo(
    () => new Set(builtElements.map((m) => m.element_id)),
    [builtElements]
  );
  const tints = useMemo(
    () => (doc ? tintsFor(doc.elements) : {}),
    [doc]
  );
  const compareEntries = compareIds
    .map((id) => variants.find((v) => v.design_id === id))
    .filter((v): v is VariantEntry => Boolean(v));

  if (!defaults || !history || !doc) {
    return <div className="loading">Loading the designer workspace…</div>;
  }

  const glbUrl = activeDesignId ? designSceneGlbUrl(activeDesignId) : null;

  return (
    <div className="designer">
      {/* ---------------------------------------------------- toolbar --- */}
      <div className="ws-toolbar">
        <div className="ws-group">
          <button
            type="button"
            title="Undo (Ctrl+Z)"
            disabled={!canUndo(history)}
            onClick={() => setHistory((h) => (h ? undo(h) : h))}
          >
            ↶
          </button>
          <button
            type="button"
            title="Redo (Ctrl+Y)"
            disabled={!canRedo(history)}
            onClick={() => setHistory((h) => (h ? redo(h) : h))}
          >
            ↷
          </button>
        </div>
        <div className="ws-group">
          <button
            type="button"
            disabled={!selectedId}
            onClick={() => selectedId && onDuplicate(selectedId)}
          >
            Duplicate
          </button>
          <button
            type="button"
            className="rebuild ws-build"
            disabled={busy}
            onClick={onBuild}
            title="Build the document through the CAD kernel and run every gate"
          >
            {busy ? "Building…" : dirty ? "Build & validate ●" : "Build & validate"}
          </button>
          <button
            type="button"
            disabled={!activeDesignId || dirty}
            title={
              dirty
                ? "The document has unbuilt changes — build first, render what you built"
                : "Four Cycles views via the render worker"
            }
            onClick={onRender}
          >
            Render
          </button>
          <button
            type="button"
            disabled={!activeDesignId || exporting}
            onClick={onExport}
            title="Build the LUXEXCHANGE export package for the active design"
          >
            {exporting ? "Exporting…" : "Export"}
          </button>
        </div>
        <div className="ws-group ws-tools">
          <button
            type="button"
            className={measureMode ? "is-on" : ""}
            onClick={() => setMeasureMode((m) => !m)}
            title="Measure: two clicks on the model, distance in mm (Esc to exit)"
          >
            📐 {measure ? formatMm(measure.distance_mm) : "Measure"}
          </button>
          <button
            type="button"
            className={sectionOn ? "is-on" : ""}
            onClick={() => setSectionOn((s) => !s)}
            title="Section plane"
          >
            ⬓ Section
          </button>
          {sectionOn && (
            <span className="section-controls">
              {(["x", "y", "z"] as const).map((axis) => (
                <button
                  key={axis}
                  type="button"
                  className={section.axis === axis ? "is-on" : ""}
                  onClick={() => setSection((s) => ({ ...s, axis }))}
                >
                  {axis.toUpperCase()}
                </button>
              ))}
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(section.offset * 100)}
                onChange={(e) =>
                  setSection((s) => ({ ...s, offset: Number(e.target.value) / 100 }))
                }
                title="cut position across the model"
              />
            </span>
          )}
          <button
            type="button"
            onClick={() => viewportRef.current?.frameAll()}
            title="Frame the whole model"
          >
            ⛶ Frame
          </button>
          <select
            value=""
            onChange={(e) => {
              const view = savedViews.find((v) => v.name === e.target.value);
              if (view) viewportRef.current?.applyCameraPose(view.pose);
            }}
            title="Saved views (stored in this browser)"
          >
            <option value="" disabled>
              Views…
            </option>
            {savedViews.map((v) => (
              <option key={v.name} value={v.name}>
                {v.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            title="Save the current camera as a named view"
            onClick={() => {
              const pose = viewportRef.current?.getCameraPose();
              if (!pose) return;
              const name = window.prompt("Name this view:", `view ${savedViews.length + 1}`);
              if (!name) return;
              setSavedViews((prev) => {
                const next = [...prev.filter((v) => v.name !== name), { name, pose }];
                try {
                  localStorage.setItem(VIEWS_KEY, JSON.stringify(next));
                } catch {
                  /* convenience only */
                }
                return next;
              });
            }}
          >
            + view
          </button>
        </div>
        <div className="ws-status">
          {buildMs !== null && <span>server build {Math.round(buildMs)} ms</span>}
          {dirty && (
            <span className="badge badge-warn" title="the viewport shows the last build, not these edits">
              UNBUILT CHANGES
            </span>
          )}
        </div>
      </div>

      {/* ------------------------------------------------------ body ---- */}
      <div className="ws-body">
        <aside className="ws-left">
          <ErrorBoundary label="Library">
            <PrimitiveLibrary defaults={defaults} onAdd={onAdd} disabled={busy} />
          </ErrorBoundary>
          <ErrorBoundary label="Scene">
            <ScenePanel
              elements={doc.elements}
              builtIds={builtIds}
              selectedId={selectedId}
              hiddenIds={hiddenIds}
              soloId={soloId}
              onSelect={setSelectedId}
              onToggleHidden={(id) =>
                setHiddenIds((prev) => {
                  const next = new Set(prev);
                  if (next.has(id)) next.delete(id);
                  else next.add(id);
                  return next;
                })
              }
              onToggleSolo={(id) => setSoloId((s) => (s === id ? null : id))}
            />
          </ErrorBoundary>
          <div className="ws-buildopts">
            <label className="param-row">
              <span className="param-name">seed</span>
              <input
                key={`seed:${doc.seed}`}
                type="number"
                step={1}
                defaultValue={doc.seed}
                onBlur={(e) => {
                  const n = Math.trunc(Number(e.target.value));
                  if (!Number.isNaN(n) && n !== doc.seed) {
                    dispatch({ kind: "set-seed", seed: n });
                  }
                }}
              />
              <span className="param-unit">determinism</span>
            </label>
            <label className="param-row">
              <span className="param-name">gate profile</span>
              <select
                value={doc.gateProfileId}
                onChange={(e) =>
                  dispatch({ kind: "set-gate-profile", gateProfileId: e.target.value })
                }
              >
                {Object.entries(defaults.gate_profiles.profiles).map(([id, p]) => (
                  <option key={id} value={id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <span className="param-unit" />
            </label>
            {intake && (
              <label className="param-row intake-toggle">
                <span className="param-name">site context</span>
                <span className="toggle-cell">
                  <input
                    type="checkbox"
                    checked={useIntake && intakeReady}
                    disabled={!intakeReady}
                    onChange={(e) => setUseIntake(e.target.checked)}
                  />
                  {intakeReady
                    ? `use intake ${intake.id.slice(0, 8)}`
                    : "intake not confirmed"}
                </span>
                <span className="param-unit">validation</span>
              </label>
            )}
          </div>
        </aside>

        <div className="ws-center">
          {compareEntries.length === 2 ? (
            <CompareView
              a={compareEntries[0]}
              b={compareEntries[1]}
              onClose={() => setCompareIds([])}
            />
          ) : glbUrl ? (
            <WorkspaceViewport
              ref={viewportRef}
              reloadToken={reloadToken}
              glbUrl={glbUrl}
              elementIds={builtElements.map((m) => m.element_id)}
              selectedId={selectedId}
              onSelect={setSelectedId}
              hiddenIds={hiddenIds}
              soloId={soloId}
              tints={tints}
              measureMode={measureMode}
              onMeasure={setMeasure}
              section={sectionOn ? section : null}
              onModelRendered={onModelRendered}
              onLoadError={(m) =>
                onFatal(`Viewport could not load the scene: ${m}`)
              }
            />
          ) : (
            <div className="ws-empty">
              <p>
                No build yet. The document on the left is ready — press{" "}
                <strong>Build &amp; validate</strong> to see it.
              </p>
            </div>
          )}
          {violations && (
            <div className="violations ws-violations">
              <strong>Constraint violations (real numbers):</strong>
              <ul>
                {violations.map((v, i) => (
                  <li key={i}>{v}</li>
                ))}
              </ul>
              <button type="button" onClick={() => setViolations(null)}>
                Dismiss
              </button>
            </div>
          )}
          {measureMode && (
            <div className="ws-mode-hint">
              Measure: click two points on the model — Esc to exit
            </div>
          )}
        </div>

        <aside className="ws-right">
          <ErrorBoundary label="Inspector">
            <InspectorPanel
              doc={doc}
              element={selected}
              defaults={defaults}
              manifestElement={manifestSelected}
              onSetParam={(id, name, value) =>
                dispatch({ kind: "set-param", elementId: id, name, value })
              }
              onSetJoint={(id, joint) =>
                dispatch({ kind: "set-joint", elementId: id, joint })
              }
              onDuplicate={onDuplicate}
              onRemove={onRemove}
            />
          </ErrorBoundary>
          <ErrorBoundary label="Validation">
            <ValidationPanel
              validation={validation}
              gates={gates}
              overallStatus={overallStatus}
              gateStatuses={gateStatuses}
            />
          </ErrorBoundary>
          <ErrorBoundary label="Export">
            <ExportPanel
              designId={activeDesignId}
              exports={exports}
              exporting={exporting}
              onExport={onExport}
            />
          </ErrorBoundary>
        </aside>
      </div>

      {/* ------------------------------------------------- history ------ */}
      <ErrorBoundary label="History">
        <HistoryStrip
          entries={variants}
          activeDesignId={activeDesignId}
          compareIds={compareIds}
          onRestore={onRestore}
          onToggleCompare={(id) =>
            setCompareIds((prev) =>
              prev.includes(id)
                ? prev.filter((x) => x !== id)
                : prev.length < 2
                  ? [...prev, id]
                  : prev
            )
          }
        />
      </ErrorBoundary>

      {/* ------------------------------------------------- render drawer */}
      {renderOpen && (
        <div className="render-drawer">
          <div className="render-drawer-head">
            <h3>Render — {activeDesignId?.slice(0, 8)}</h3>
            <button
              type="button"
              onClick={() => {
                renderAbort.current = true;
                setRenderOpen(false);
              }}
            >
              Close
            </button>
          </div>
          {renderNote && <p className="hint">{renderNote}</p>}
          {renderJob?.status === "done" && (
            <div className="render-grid">
              {renderJob.views.map((v) => (
                <figure key={v.name}>
                  <a
                    href={renderViewUrl(renderJob.id, v.name)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <img
                      src={renderViewUrl(renderJob.id, v.name)}
                      alt={v.name}
                    />
                  </a>
                  <figcaption>{v.name}</figcaption>
                </figure>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
