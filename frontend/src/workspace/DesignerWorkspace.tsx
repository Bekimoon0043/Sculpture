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
  BookmarkPlus,
  Box,
  Copy,
  Focus,
  Hammer,
  KeyRound,
  PanelLeft,
  PanelRight,
  Plus,
  Redo2,
  Ruler,
  ScanLine,
  Undo2,
} from "lucide-react";
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
  postAssemblyPreview,
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
  type StandardView,
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

type RightTab = "design" | "checks" | "output";

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
  /** False while another view is shown — the workspace stays mounted but
   *  its keyboard map must not swallow keys meant for that view. */
  active: boolean;
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
  active,
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
  const [addOpen, setAddOpen] = useState(false);
  const [rightTab, setRightTab] = useState<RightTab>("design");
  const [historyCollapsed, setHistoryCollapsed] = useState(true);

  // What the viewport shows.
  const [activeDesignId, setActiveDesignId] = useState<string | null>(null);
  const [builtElements, setBuiltElements] = useState<ManifestElement[]>([]);
  const [lastBuiltJson, setLastBuiltJson] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [busy, setBusy] = useState(false);
  const [violations, setViolations] = useState<string[] | null>(null);
  const [buildMs, setBuildMs] = useState<number | null>(null);
  const [draftGlbUrl, setDraftGlbUrl] = useState<string | null>(null);
  const [draftForJson, setDraftForJson] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewBuildMs, setPreviewBuildMs] = useState<number | null>(null);
  const draftUrlRef = useRef<string | null>(null);
  const previewSequence = useRef(0);

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

  // Blender-familiar chrome (Phase 14b): collapsible rails (T/N), keymap
  // overlay (?), projection indicator (5), outliner rename (F2).
  const [leftOpen, setLeftOpen] = useState(
    () => localStorage.getItem("lf_rail_left") !== "closed"
  );
  const [rightOpen, setRightOpen] = useState(
    () => localStorage.getItem("lf_rail_right") !== "closed"
  );
  const [keymapOpen, setKeymapOpen] = useState(false);
  const [projection, setProjection] = useState<"persp" | "ortho">("persp");
  const [renameRequestId, setRenameRequestId] = useState<string | null>(null);
  useEffect(() => {
    try {
      localStorage.setItem("lf_rail_left", leftOpen ? "open" : "closed");
      localStorage.setItem("lf_rail_right", rightOpen ? "open" : "closed");
    } catch {
      /* convenience only */
    }
  }, [leftOpen, rightOpen]);

  const viewportRef = useRef<WorkspaceViewportHandle>(null);
  const pendingThumbFor = useRef<string | null>(null);

  const doc = history?.present ?? null;
  const docJson = useMemo(() => (doc ? JSON.stringify(doc) : null), [doc]);
  const dirty = docJson !== null && docJson !== lastBuiltJson;
  const draftCurrent = Boolean(
    dirty && draftGlbUrl && draftForJson === docJson
  );
  const glbUrl = useMemo(() => {
    if (draftCurrent && draftGlbUrl) return () => draftGlbUrl;
    return activeDesignId ? designSceneGlbUrl(activeDesignId) : null;
  }, [activeDesignId, draftCurrent, draftGlbUrl]);

  const replaceDraftUrl = useCallback((next: string | null) => {
    if (draftUrlRef.current && draftUrlRef.current !== next) {
      URL.revokeObjectURL(draftUrlRef.current);
    }
    draftUrlRef.current = next;
    setDraftGlbUrl(next);
  }, []);

  useEffect(() => () => {
    if (draftUrlRef.current) URL.revokeObjectURL(draftUrlRef.current);
  }, []);

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

  const onRename = useCallback(
    (oldId: string, rawNewId: string) => {
      // Mirror the reducer's validity rules BEFORE remapping UI state, so a
      // rejected rename (taken/invalid name) never leaves selection or
      // hide/solo pointing at an id that does not exist.
      const newId = rawNewId.trim();
      if (
        !doc ||
        !newId ||
        newId === oldId ||
        !/^[a-z0-9_]+$/i.test(newId) ||
        doc.elements.some((e) => e.element_id === newId) ||
        !doc.elements.some((e) => e.element_id === oldId)
      ) {
        return;
      }
      dispatch({ kind: "rename", elementId: oldId, newId });
      setSelectedId((s) => (s === oldId ? newId : s));
      setSoloId((s) => (s === oldId ? newId : s));
      setHiddenIds((prev) => {
        if (!prev.has(oldId)) return prev;
        const next = new Set(prev);
        next.delete(oldId);
        next.add(newId);
        return next;
      });
    },
    [doc, dispatch]
  );

  // Keyboard — the Blender-derived map (Phase 14b). Top-row digits, not
  // numpad-only: the operator's laptop has no numpad. Never fires while
  // typing in a field; Ctrl+digit is left to the browser (tab switching).
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      const vp = viewportRef.current;

      // --- history ------------------------------------------------------
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
        e.preventDefault();
        setHistory((h) => (h ? undo(h) : h));
        return;
      }
      if (
        ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") ||
        ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "z")
      ) {
        e.preventDefault();
        setHistory((h) => (h ? redo(h) : h));
        return;
      }
      if (e.ctrlKey || e.metaKey) return; // everything below is unmodified keys

      // --- views (1/3/7 + Shift opposites, 5 ortho, ./Home framing) ------
      const viewByCode: Record<string, [string, string]> = {
        Digit1: ["front", "back"],
        Numpad1: ["front", "back"],
        Digit3: ["right", "left"],
        Numpad3: ["right", "left"],
        Digit7: ["top", "bottom"],
        Numpad7: ["top", "bottom"],
      };
      if (viewByCode[e.code]) {
        e.preventDefault();
        const [plain, shifted] = viewByCode[e.code];
        vp?.applyStandardView((e.shiftKey ? shifted : plain) as StandardView);
        return;
      }
      if (e.code === "Digit5" || e.code === "Numpad5") {
        e.preventDefault();
        const mode = vp?.toggleProjection();
        if (mode) setProjection(mode);
        return;
      }
      if (e.code === "Home") {
        e.preventDefault();
        vp?.frameAll();
        return;
      }
      if (e.code === "Period" || e.code === "NumpadDecimal") {
        e.preventDefault();
        if (selectedId) vp?.frameSelected(selectedId);
        else vp?.frameAll();
        return;
      }

      // --- selection-centric --------------------------------------------
      if (e.shiftKey && e.code === "KeyD" && selectedId) {
        e.preventDefault();
        onDuplicate(selectedId);
        return;
      }
      if (e.code === "KeyH") {
        e.preventDefault();
        if (e.altKey) {
          setHiddenIds(new Set());
          setSoloId(null);
        } else if (selectedId) {
          setHiddenIds((prev) => {
            const next = new Set(prev);
            next.add(selectedId);
            return next;
          });
        }
        return;
      }
      if (e.key === "/" && !e.shiftKey) {
        e.preventDefault();
        if (selectedId) setSoloId((s) => (s === selectedId ? null : selectedId));
        return;
      }
      if (e.key === "?") {
        e.preventDefault();
        setKeymapOpen((k) => !k);
        return;
      }
      if (e.code === "F2" && selectedId) {
        e.preventDefault();
        setRenameRequestId(selectedId);
        return;
      }
      if ((e.key === "Delete" || e.code === "KeyX") && selectedId) {
        e.preventDefault();
        onRemove(selectedId);
        return;
      }

      // --- chrome --------------------------------------------------------
      if (e.code === "KeyT") {
        e.preventDefault();
        setLeftOpen((v) => !v);
        return;
      }
      if (e.code === "KeyN") {
        e.preventDefault();
        setRightOpen((v) => !v);
        return;
      }
      if (e.key === "Escape") {
        setKeymapOpen(false);
        setMeasureMode(false);
        setSelectedId(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, selectedId, onRemove, onDuplicate]);

  // ------------------------------------------------------------- build
  const intakeReady = Boolean(intake && intake.status === "confirmed");

  useEffect(() => {
    if (!doc || !docJson) return;
    const needsPreview = dirty || !activeDesignId;
    if (!needsPreview || busy) {
      setPreviewing(false);
      if (!needsPreview) {
        replaceDraftUrl(null);
        setDraftForJson(null);
        setPreviewError(null);
      }
      return;
    }

    const sequence = ++previewSequence.current;
    const controller = new AbortController();
    setPreviewing(true);
    setPreviewError(null);
    const timer = window.setTimeout(() => {
      postAssemblyPreview(
        toBuildElements(doc),
        doc.fabrication,
        doc.seed,
        controller.signal
      )
        .then((preview) => {
          if (sequence !== previewSequence.current) {
            URL.revokeObjectURL(preview.objectUrl);
            return;
          }
          replaceDraftUrl(preview.objectUrl);
          setDraftForJson(docJson);
          setPreviewBuildMs(preview.buildMs);
          setPreviewing(false);
        })
        .catch((error) => {
          if (controller.signal.aborted || sequence !== previewSequence.current) return;
          const message =
            error instanceof ApiError && error.violations?.length
              ? error.violations[0]
              : error instanceof Error
                ? error.message
                : "Draft preview failed";
          setPreviewError(message);
          setPreviewing(false);
        });
    }, 550);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [activeDesignId, busy, dirty, doc, docJson, replaceDraftUrl]);

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

  return (
    <div className={`designer ${historyCollapsed ? "history-closed" : ""}`}>
      {/* ---------------------------------------------------- toolbar --- */}
      <div className="ws-toolbar">
        <div className="ws-group">
          <button
            type="button"
            className="icon-button"
            title="Undo (Ctrl+Z)"
            aria-label="Undo"
            disabled={!canUndo(history)}
            onClick={() => setHistory((h) => (h ? undo(h) : h))}
          >
            <Undo2 size={16} />
          </button>
          <button
            type="button"
            className="icon-button"
            title="Redo (Ctrl+Y)"
            aria-label="Redo"
            disabled={!canRedo(history)}
            onClick={() => setHistory((h) => (h ? redo(h) : h))}
          >
            <Redo2 size={16} />
          </button>
        </div>
        <div className="ws-group ws-authoring">
          <button
            type="button"
            className={addOpen ? "is-on" : ""}
            onClick={() => setAddOpen((open) => !open)}
            title="Add an element"
          >
            <Plus size={16} />
            <span>Add</span>
          </button>
          <button
            type="button"
            className="icon-button"
            disabled={!selectedId}
            onClick={() => selectedId && onDuplicate(selectedId)}
            title="Duplicate the selected element (Shift+D)"
            aria-label="Duplicate selected element"
          >
            <Copy size={16} />
          </button>
          <button
            type="button"
            className="rebuild ws-build"
            disabled={busy}
            onClick={onBuild}
            title="Build through the CAD kernel and run every validation gate"
          >
            <Hammer size={16} />
            <span>{busy ? "Building…" : "Build"}</span>
            {dirty && <span className="dirty-dot" aria-label="unbuilt changes" />}
          </button>
        </div>
        <div className="ws-group ws-tools">
          <button
            type="button"
            className={`icon-button ${measureMode ? "is-on" : ""}`}
            onClick={() => setMeasureMode((m) => !m)}
            title="Measure: two clicks on the model, distance in mm (Esc to exit)"
            aria-label="Measure"
          >
            <Ruler size={16} />
          </button>
          <button
            type="button"
            className={`icon-button ${sectionOn ? "is-on" : ""}`}
            onClick={() => setSectionOn((s) => !s)}
            title="Section plane"
            aria-label="Section plane"
          >
            <ScanLine size={16} />
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={() => viewportRef.current?.frameAll()}
            title="Frame the whole model (Home) · frame selected (.)"
            aria-label="Frame model"
          >
            <Focus size={16} />
          </button>
          <button
            type="button"
            className={`projection-button ${projection === "ortho" ? "is-on" : ""}`}
            onClick={() => {
              const mode = viewportRef.current?.toggleProjection();
              if (mode) setProjection(mode);
            }}
            title="Orthographic ⇄ perspective (5) — judge proportions in ortho, depth in perspective"
          >
            <Box size={16} />
            <span>{projection === "ortho" ? "Ortho" : "Perspective"}</span>
          </button>
        </div>
        <div className="ws-group ws-views">
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
            className="icon-button"
            title="Save the current camera as a named view"
            aria-label="Save current view"
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
            <BookmarkPlus size={16} />
          </button>
        </div>
        <div className="ws-status">
          {measure && <span>{formatMm(measure.distance_mm)}</span>}
          {buildMs !== null && <span>{Math.round(buildMs)} ms</span>}
          {dirty && (
            <span className="badge badge-warn" title="the viewport shows the last build, not these edits">
              UNBUILT
            </span>
          )}
          <button
            type="button"
            className={`icon-button ${keymapOpen ? "is-on" : ""}`}
            onClick={() => setKeymapOpen((k) => !k)}
            title="Navigation and editing shortcuts (?)"
            aria-label="Keyboard shortcuts"
          >
            <KeyRound size={16} />
          </button>
          <button
            type="button"
            className={`icon-button ${leftOpen ? "is-on" : ""}`}
            onClick={() => setLeftOpen((open) => !open)}
            title="Toggle scene rail (T)"
            aria-label="Toggle scene rail"
          >
            <PanelLeft size={16} />
          </button>
          <button
            type="button"
            className={`icon-button ${rightOpen ? "is-on" : ""}`}
            onClick={() => setRightOpen((open) => !open)}
            title="Toggle properties rail (N)"
            aria-label="Toggle properties rail"
          >
            <PanelRight size={16} />
          </button>
        </div>
      </div>

      {addOpen && (
        <div className="ws-add-popover">
          <PrimitiveLibrary
            defaults={defaults}
            disabled={busy}
            onAdd={(primitive) => {
              onAdd(primitive);
              setAddOpen(false);
            }}
          />
        </div>
      )}

      {/* ------------------------------------------------------ body ---- */}
      <div
        className={[
          "ws-body",
          leftOpen ? "" : "left-closed",
          rightOpen ? "" : "right-closed",
        ].join(" ")}
      >
        {leftOpen && (
        <aside className="ws-left">
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
              onRename={onRename}
              renameRequestId={renameRequestId}
              onRenameRequestHandled={() => setRenameRequestId(null)}
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
        )}

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
              elementIds={
                draftCurrent
                  ? doc.elements.map((element) => element.element_id)
                  : builtElements.map((element) => element.element_id)
              }
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
          {(dirty || !activeDesignId) && (
            <div className={`draft-status ${previewError ? "has-error" : ""}`}>
              {draftCurrent
                ? `DRAFT · CAD preview · unvalidated${previewBuildMs ? ` · ${Math.round(previewBuildMs)} ms` : ""}`
                : previewing
                  ? "Updating CAD preview…"
                  : previewError
                    ? `Draft cannot build: ${previewError}`
                    : "Draft preview waiting"}
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
          {sectionOn && (
            <div className="section-popover">
              <span>Section</span>
              <div className="segmented" aria-label="Section axis">
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
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(section.offset * 100)}
                onChange={(e) =>
                  setSection((s) => ({ ...s, offset: Number(e.target.value) / 100 }))
                }
                title="Section position across the model"
              />
            </div>
          )}
          {compareEntries.length !== 2 && glbUrl && (
            <div className="ws-mouse-hints" aria-hidden="true">
              {measureMode
                ? "LMB pick point · Esc cancel"
                : "LMB select / orbit · MMB orbit · Shift+MMB pan · wheel zoom · 1/3/7 views · 5 ortho · ? keys"}
            </div>
          )}
        </div>

        {rightOpen && (
        <aside className="ws-right">
          <div className="right-tabs" role="tablist" aria-label="Workspace properties">
            {(["design", "checks", "output"] as RightTab[]).map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={rightTab === tab}
                className={rightTab === tab ? "is-active" : ""}
                onClick={() => setRightTab(tab)}
              >
                {tab[0].toUpperCase() + tab.slice(1)}
                {tab === "checks" && overallStatus && (
                  <span className={`tab-dot badge-${overallStatus}`} />
                )}
              </button>
            ))}
          </div>
          <div className="right-tab-content">
            {rightTab === "design" && (
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
            )}
            {rightTab === "checks" && (
              <ErrorBoundary label="Validation">
                <ValidationPanel
                  validation={validation}
                  gates={gates}
                  overallStatus={overallStatus}
                  gateStatuses={gateStatuses}
                  elementIds={doc.elements.map((element) => element.element_id)}
                  onSelectElement={(elementId) => {
                    setSelectedId(elementId);
                    setRightTab("design");
                  }}
                />
              </ErrorBoundary>
            )}
            {rightTab === "output" && (
              <div className="output-tab">
                <button
                  type="button"
                  className="output-render"
                  disabled={!activeDesignId || dirty}
                  title={dirty ? "Build changes before rendering" : "Create four Cycles views"}
                  onClick={onRender}
                >
                  Render presentation views
                </button>
                <ErrorBoundary label="Export">
                  <ExportPanel
                    designId={activeDesignId}
                    exports={exports}
                    exporting={exporting}
                    onExport={onExport}
                  />
                </ErrorBoundary>
              </div>
            )}
          </div>
        </aside>
        )}
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
          collapsed={historyCollapsed}
          onToggleCollapsed={() => setHistoryCollapsed((collapsed) => !collapsed)}
        />
      </ErrorBoundary>

      {/* ------------------------------------------------- keymap ------- */}
      {keymapOpen && (
        <div className="keymap-overlay" onClick={() => setKeymapOpen(false)}>
          <div className="keymap-card" onClick={(e) => e.stopPropagation()}>
            <div className="keymap-head">
                <h3>Workspace shortcuts</h3>
              <button type="button" onClick={() => setKeymapOpen(false)}>
                Close (Esc)
              </button>
            </div>
            <div className="keymap-cols">
              <dl>
                <dt>Views</dt>
                <dd><kbd>1</kbd>/<kbd>3</kbd>/<kbd>7</kbd> front / right / top</dd>
                <dd><kbd>Shift</kbd>+<kbd>1</kbd>/<kbd>3</kbd>/<kbd>7</kbd> back / left / bottom</dd>
                <dd><kbd>5</kbd> orthographic ⇄ perspective</dd>
                <dd><kbd>.</kbd> frame selected · <kbd>Home</kbd> frame all</dd>
                <dd>Axis gizmo (top right): click a dot to snap</dd>
              </dl>
              <dl>
                <dt>Mouse</dt>
                <dd>LMB click select · LMB drag / MMB orbit</dd>
                <dd><kbd>Shift</kbd>+MMB or RMB pan · wheel zoom</dd>
                <dt>Edit</dt>
                <dd><kbd>Shift</kbd>+<kbd>D</kbd> duplicate · <kbd>X</kbd>/<kbd>Del</kbd> delete</dd>
                <dd><kbd>F2</kbd> or double-click rename</dd>
                <dd><kbd>Ctrl</kbd>+<kbd>Z</kbd>/<kbd>Y</kbd> undo / redo</dd>
              </dl>
              <dl>
                <dt>Show</dt>
                <dd><kbd>H</kbd> hide · <kbd>Alt</kbd>+<kbd>H</kbd> unhide all · <kbd>/</kbd> solo</dd>
                <dt>Panels</dt>
                <dd><kbd>T</kbd> library rail · <kbd>N</kbd> inspector rail</dd>
                <dd><kbd>Esc</kbd> deselect / exit mode · <kbd>?</kbd> this card</dd>
              </dl>
            </div>
            <p className="hint">
              No move/rotate keys on purpose: elements are placed by joints
              and parameters, not dragged — the kernel draws, the document
              decides (ADR-044).
            </p>
          </div>
        </div>
      )}

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
