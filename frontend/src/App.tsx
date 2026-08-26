// App shell — the pipeline is the product.
//
// LuxuryForm is one workflow: brief -> build -> validate -> export -> accept.
// The shell makes that visible: a persistent stepper whose states are DERIVED
// from real data (never a stored flag that can drift out of sync), a view per
// stage, and a status bar carrying the numbers that matter continuously.
//
// Phase 14: the Assembly panel grew into the Designer Workspace — library,
// selectable viewport, inspector, history strip. The workspace owns its
// document and build state and reports the pipeline facts (design, verdict,
// exports) up to this shell, which still owns the stepper and status bar.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  BuildResponse,
  DefaultsResponse,
  Validation,
  type ExportsResponse,
  type GateStatus,
  type IntakeResponse,
  type OpsCosts,
  getDefaults,
  getHealth,
  getLatestIntake,
  getLatestValidation,
  getOpsCosts,
  latestGlbUrl,
  listPrecedents,
  postBuild,
} from "./api/client";
import ErrorBoundary from "./ErrorBoundary";
import PipelineStepper, { type PipelineStep, type StepState } from "./PipelineStepper";
import CascadePanel from "./panels/CascadePanel";
import CouncilPanel from "./panels/CouncilPanel";
import IntakePanel from "./panels/IntakePanel";
import LibraryPanel from "./panels/LibraryPanel";
import OpsPanel from "./panels/OpsPanel";
import ValidationPanel from "./panels/ValidationPanel";
import Viewport from "./viewport/Viewport";
import DesignerWorkspace from "./workspace/DesignerWorkspace";

type View =
  | "intake" | "council" | "designer" | "cascade"
  | "library" | "ops";

const VIEWS: Array<{ key: View; label: string; group: "pipeline" | "tools" }> = [
  { key: "intake", label: "Brief", group: "pipeline" },
  { key: "council", label: "AI Council", group: "pipeline" },
  { key: "designer", label: "Designer", group: "pipeline" },
  { key: "library", label: "Library", group: "pipeline" },
  { key: "cascade", label: "Cascade", group: "tools" },
  { key: "ops", label: "Operations", group: "tools" },
];

const STATUS_LABEL: Record<GateStatus, string> = {
  pass: "PASS", warn: "WARN", fail: "FAIL", needs_input: "NEEDS INPUT",
};

interface PipelineFacts {
  designId: string | null;
  overallStatus: GateStatus | null;
  exports: ExportsResponse | null;
}

export default function App() {
  const [defaults, setDefaults] = useState<DefaultsResponse | null>(null);
  const [values, setValues] = useState<Record<string, number | string>>({});
  const [seed, setSeed] = useState(0);
  const [busy, setBusy] = useState(false);
  const [violations, setViolations] = useState<string[] | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);
  // Cascade-tool mesh validation (the workspace has its own layered view).
  const [validation, setValidation] = useState<Validation | null>(null);
  // Pipeline facts, reported by the Designer Workspace (Phase 14).
  const [facts, setFacts] = useState<PipelineFacts>({
    designId: null,
    overallStatus: null,
    exports: null,
  });
  const [intake, setIntake] = useState<IntakeResponse | null>(null);
  const [precedentCount, setPrecedentCount] = useState(0);
  const [costs, setCosts] = useState<OpsCosts | null>(null);
  const [online, setOnline] = useState(true);
  const [reloadToken, setReloadToken] = useState(0);
  const [view, setView] = useState<View>("designer");
  //: A stepper click's requested Designer right-rail tab. The counter makes
  //: repeated clicks on the same step re-apply (state equality would not).
  const [designerTabRequest, setDesignerTabRequest] = useState<{
    tab: string;
    n: number;
  } | null>(null);
  const [serverBuildMs, setServerBuildMs] = useState<number | null>(null);
  const [lastRebuildMs, setLastRebuildMs] = useState<number | null>(null);
  const rebuildStartRef = useRef<number | null>(null);

  // --- cross-view state, loaded once and refreshed on the events that
  // --- change it. The stepper needs all of it to be honest.
  const refreshPipeline = useCallback(() => {
    getLatestIntake().then((i) => i && setIntake(i)).catch(() => undefined);
    listPrecedents().then((b) => setPrecedentCount(b.count)).catch(() => undefined);
    getOpsCosts().then(setCosts).catch(() => undefined);
  }, []);

  useEffect(() => {
    getDefaults()
      .then((d) => {
        setDefaults(d);
        const initial: Record<string, number | string> = {};
        for (const [name, spec] of Object.entries(d.parameters)) {
          initial[name] = spec.default;
        }
        setValues(initial);
      })
      .catch((e) =>
        setFatalError(
          `Cannot reach the backend (/api/geometry/cascade/defaults): ${e.message}`
        )
      );
    getLatestValidation().then((v) => v && setValidation(v.validation)).catch(() => undefined);
    refreshPipeline();
  }, [refreshPipeline]);

  // A quiet heartbeat: the status bar must tell the truth about the backend
  // even when the operator is not clicking anything.
  useEffect(() => {
    let cancelled = false;
    const tick = () => getHealth().then((ok) => !cancelled && setOnline(ok));
    tick();
    const timer = window.setInterval(tick, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const onPipelineChange = useCallback((next: PipelineFacts) => {
    setFacts(next);
  }, []);

  const onRebuild = useCallback(() => {
    setBusy(true);
    setViolations(null);
    rebuildStartRef.current = performance.now();
    postBuild(values, seed)
      .then((resp: BuildResponse) => {
        setValidation(resp.validation);
        setServerBuildMs(resp.build_ms);
        setReloadToken((t) => t + 1);
        setBusy(false);
      })
      .catch((e) => {
        rebuildStartRef.current = null;
        setBusy(false);
        if (e instanceof ApiError && e.violations) setViolations(e.violations);
        else setFatalError(`Rebuild failed: ${e.message}`);
      });
  }, [values, seed]);

  const onModelRendered = useCallback(() => {
    if (rebuildStartRef.current !== null) {
      setLastRebuildMs(performance.now() - rebuildStartRef.current);
      rebuildStartRef.current = null;
    }
  }, []);

  const onLoadError = useCallback(
    (message: string) => {
      if (reloadToken === 0) return;
      setFatalError(`Viewport could not load the model: ${message}`);
    },
    [reloadToken]
  );

  // --- the stepper: every state DERIVED, never stored ---------------------
  const steps: PipelineStep[] = useMemo(() => {
    const { designId, overallStatus, exports } = facts;
    const intakeState: StepState = !intake
      ? "pending"
      : intake.status === "confirmed"
        ? "done"
        : intake.readiness.ready_for_council
          ? "active"
          : "attention";
    const intakeDetail = !intake
      ? "not started"
      : intake.status === "confirmed"
        ? "confirmed"
        : intake.readiness.ready_for_council
          ? "ready — confirm it"
          : "missing required fields";

    const councilState: StepState = intake?.council_session_id ? "done" : "pending";

    const buildState: StepState = designId ? "done" : "pending";

    const validationState: StepState = !overallStatus
      ? "pending"
      : overallStatus === "pass"
        ? "done"
        : overallStatus === "fail"
          ? "attention"
          : "active";

    const exportState: StepState = exports?.package_built ? "done" : designId ? "active" : "pending";

    const acceptedThis = Boolean(
      exports?.content_digest && precedentCount > 0
    );
    const libraryState: StepState = precedentCount > 0
      ? "done"
      : exports?.package_built ? "active" : "pending";

    return [
      { key: "brief", label: "Brief", state: intakeState, detail: intakeDetail, view: "intake" },
      { key: "council", label: "Council", state: councilState,
        detail: intake?.council_session_id ? "session run" : "not run", view: "council" },
      { key: "build", label: "Build", state: buildState,
        detail: designId ? `design ${designId.slice(0, 8)}` : "no design",
        view: "designer", tab: "design" },
      { key: "validate", label: "Validate", state: validationState,
        detail: overallStatus ? STATUS_LABEL[overallStatus] : "not validated",
        view: "designer", tab: "checks" },
      { key: "export", label: "Export", state: exportState,
        detail: exports?.package_built ? "package sealed" : "no package",
        view: "designer", tab: "output" },
      { key: "accept", label: "Library", state: libraryState,
        detail: precedentCount > 0
          ? `${precedentCount} precedent${precedentCount === 1 ? "" : "s"}`
          : acceptedThis ? "accepted" : "nothing accepted",
        view: "library" },
    ];
  }, [intake, facts, precedentCount]);

  if (fatalError) {
    return (
      <div className="fatal">
        <h1>LuxuryForm Studio</h1>
        <p>{fatalError}</p>
        <p>
          Is the backend running? Start it with <code>docker compose up -d</code>{" "}
          (see docs/operator/02_phase2_viewport.md).
        </p>
        <button className="rebuild" onClick={() => setFatalError(null)}>Dismiss</button>
      </div>
    );
  }
  if (!defaults) {
    return <div className="loading">Loading parameter registry…</div>;
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">LF</span>
          <span className="brand-name">LuxuryForm Studio</span>
        </div>
        <PipelineStepper
          steps={steps}
          activeView={view}
          onNavigate={(v, tab) => {
            setView(v as View);
            // Build/Validate/Export share the Designer view; the tab is what
            // makes clicking them DO something (open the matching right-rail
            // surface), including when the view is already the Designer.
            if (tab) {
              setDesignerTabRequest((prev) => ({ tab, n: (prev?.n ?? 0) + 1 }));
            }
          }}
        />
        <nav className="view-tabs">
          {VIEWS.filter((v) => v.group === "tools").map((v) => (
            <button
              key={v.key}
              className={view === v.key ? "active" : ""}
              onClick={() => setView(v.key)}
            >
              {v.label}
            </button>
          ))}
        </nav>
      </header>

      <main
        className={
          view === "cascade"
            ? "workspace"
            : view === "designer"
              ? "designer-main"
              : "single"
        }
      >
        {view === "intake" && (
          <ErrorBoundary label="Brief intake">
            <IntakePanel
              onConfirmed={(next) => {
                setIntake(next);
                setView("designer");
              }}
              onFatal={setFatalError}
            />
          </ErrorBoundary>
        )}

        {view === "council" && (
          <ErrorBoundary label="AI Council">
            <CouncilPanel />
          </ErrorBoundary>
        )}

        {view === "library" && (
          <ErrorBoundary label="Library">
            <LibraryPanel
              designId={facts.designId}
              exports={facts.exports}
              onAccepted={refreshPipeline}
              onFatal={setFatalError}
            />
          </ErrorBoundary>
        )}

        {view === "ops" && (
          <ErrorBoundary label="Operations">
            <OpsPanel onFatal={setFatalError} />
          </ErrorBoundary>
        )}

        {/* The Designer Workspace stays MOUNTED across view switches — its
            document, undo history and viewport state must survive a detour
            to the Brief or Council views. Hidden with CSS, not unmounted. */}
        <div
          className="designer-host"
          style={{ display: view === "designer" ? "contents" : "none" }}
        >
          <ErrorBoundary label="Designer workspace">
            <DesignerWorkspace
              intake={intake}
              active={view === "designer"}
              tabRequest={designerTabRequest}
              onFatal={setFatalError}
              onPipelineChange={onPipelineChange}
            />
          </ErrorBoundary>
        </div>

        {view === "cascade" && (
          <>
            <div className="viewport-wrap">
              <Viewport
                reloadToken={reloadToken}
                glbUrl={latestGlbUrl}
                onModelRendered={onModelRendered}
                onLoadError={onLoadError}
              />
              <div className="rebuild-timer">
                {lastRebuildMs !== null
                  ? `Last build: ${Math.round(lastRebuildMs)} ms (server ${Math.round(serverBuildMs ?? 0)} ms)`
                  : "Last rebuild: — (press Rebuild)"}
              </div>
            </div>
            <div className="side">
              <CascadePanel
                defaults={defaults}
                values={values}
                seed={seed}
                busy={busy}
                violations={violations}
                onChange={(name, v) => setValues((prev) => ({ ...prev, [name]: v }))}
                onSeedChange={setSeed}
                onRebuild={onRebuild}
              />
              <ErrorBoundary label="Validation">
                <ValidationPanel
                  validation={validation}
                  gates={null}
                  overallStatus={null}
                  gateStatuses={null}
                />
              </ErrorBoundary>
            </div>
          </>
        )}
      </main>

      <footer className="statusbar">
        <span className={`dot ${online ? "is-online" : "is-offline"}`} />
        <span>{online ? "backend connected" : "backend unreachable"}</span>
        <span className="sep" />
        {facts.designId && <span>design <code>{facts.designId.slice(0, 8)}</code></span>}
        {facts.overallStatus && (
          <>
            <span className="sep" />
            <span className={`badge badge-${facts.overallStatus}`}>
              {STATUS_LABEL[facts.overallStatus]}
            </span>
          </>
        )}
        <span className="spacer" />
        {costs && (
          <>
            <span title="total logged provider spend">
              spend ${costs.total_usd.toFixed(2)}
            </span>
            {!costs.reconciliation.clean && (
              <span className="badge badge-warn" title="the two cost ledgers disagree">
                LEDGER MISMATCH
              </span>
            )}
            <span className="sep" />
          </>
        )}
        <span>{precedentCount} precedent{precedentCount === 1 ? "" : "s"}</span>
      </footer>
    </div>
  );
}
