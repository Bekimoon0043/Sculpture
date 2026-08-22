// App shell — the pipeline is the product.
//
// LuxuryForm is one workflow: brief -> build -> validate -> export -> accept.
// The shell makes that visible: a persistent stepper whose states are DERIVED
// from real data (never a stored flag that can drift out of sync), a view per
// stage, and a status bar carrying the numbers that matter continuously.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  AssemblyBuildResponse,
  BuildResponse,
  DefaultsResponse,
  Validation,
  ValidationGate,
  type ExportsResponse,
  type GateStatus,
  type IntakeResponse,
  type OpsCosts,
  getDefaults,
  getAssemblyExports,
  getHealth,
  getLatestAssemblyValidation,
  getLatestIntake,
  getOpsCosts,
  latestAssemblyGlbUrl,
  latestGlbUrl,
  getLatestValidation,
  listPrecedents,
  postAssemblyExports,
  postBuild,
} from "./api/client";
import ErrorBoundary from "./ErrorBoundary";
import PipelineStepper, { type PipelineStep, type StepState } from "./PipelineStepper";
import AssemblyPanel from "./panels/AssemblyPanel";
import ExportPanel from "./panels/ExportPanel";
import CascadePanel from "./panels/CascadePanel";
import CouncilPanel from "./panels/CouncilPanel";
import IntakePanel from "./panels/IntakePanel";
import LibraryPanel from "./panels/LibraryPanel";
import OpsPanel from "./panels/OpsPanel";
import ValidationPanel from "./panels/ValidationPanel";
import Viewport from "./viewport/Viewport";

type View =
  | "intake" | "council" | "assembly" | "cascade"
  | "library" | "ops";

const VIEWS: Array<{ key: View; label: string; group: "pipeline" | "tools" }> = [
  { key: "intake", label: "Brief", group: "pipeline" },
  { key: "council", label: "AI Council", group: "pipeline" },
  { key: "assembly", label: "Assembly", group: "pipeline" },
  { key: "library", label: "Library", group: "pipeline" },
  { key: "cascade", label: "Cascade", group: "tools" },
  { key: "ops", label: "Operations", group: "tools" },
];

const STATUS_LABEL: Record<GateStatus, string> = {
  pass: "PASS", warn: "WARN", fail: "FAIL", needs_input: "NEEDS INPUT",
};

export default function App() {
  const [defaults, setDefaults] = useState<DefaultsResponse | null>(null);
  const [values, setValues] = useState<Record<string, number | string>>({});
  const [seed, setSeed] = useState(0);
  const [busy, setBusy] = useState(false);
  const [violations, setViolations] = useState<string[] | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [validationGates, setValidationGates] =
    useState<Record<string, ValidationGate> | null>(null);
  const [overallStatus, setOverallStatus] = useState<GateStatus | null>(null);
  // The per-gate statuses the SERVER computed. The gate blobs cannot all
  // supply this themselves (the mesh report has no status key), so the
  // authoritative map travels alongside them.
  const [gateStatuses, setGateStatuses] =
    useState<Record<string, GateStatus> | null>(null);
  const [designId, setDesignId] = useState<string | null>(null);
  const [exports, setExports] = useState<ExportsResponse | null>(null);
  const [exporting, setExporting] = useState(false);
  const [intake, setIntake] = useState<IntakeResponse | null>(null);
  const [precedentCount, setPrecedentCount] = useState(0);
  const [costs, setCosts] = useState<OpsCosts | null>(null);
  const [online, setOnline] = useState(true);
  const [reloadToken, setReloadToken] = useState(0);
  const [view, setView] = useState<View>("assembly");
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

  useEffect(() => {
    if (view !== "assembly") return;
    getAssemblyExports()
      .then((e) => {
        if (!e) return;
        setExports(e);
        setDesignId((current) => current ?? e.design_id);
      })
      .catch(() => undefined);
    getLatestAssemblyValidation()
      .then((v) => {
        if (!v) return;
        setValidation(v.validation);
        setValidationGates(v.gates ?? null);
        setGateStatuses(v.gate_statuses ?? null);
        setOverallStatus(v.overall_status ?? null);
      })
      .catch(() => undefined);
  }, [view]);

  const onRebuild = useCallback(() => {
    setBusy(true);
    setViolations(null);
    rebuildStartRef.current = performance.now();
    postBuild(values, seed)
      .then((resp: BuildResponse) => {
        setValidation(resp.validation);
        setValidationGates(null);
        setGateStatuses(null);
        setOverallStatus(null);
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

  const onAssemblyBuilt = useCallback((resp: AssemblyBuildResponse) => {
    setValidation(resp.validation);
    setValidationGates(resp.validation_gates);
    // The build response reports the layered gates only; the mesh verdict
    // rides in `validation.passed`, so name it here too.
    setGateStatuses({
      ...Object.fromEntries(
        Object.entries(resp.validation_gates).map(([k, g]) => [k, g.status])
      ),
      assembly_mesh: resp.validation.passed ? "pass" : "fail",
    });
    setOverallStatus(resp.overall_status ?? null);
    setServerBuildMs(resp.build_ms);
    setDesignId(resp.design_id);
    setExports(null);
    getAssemblyExports(resp.design_id).then(setExports).catch(() => undefined);
    setReloadToken((t) => t + 1);
  }, []);

  const onExport = useCallback(() => {
    if (!designId) return;
    setExporting(true);
    postAssemblyExports(designId)
      .then(() => getAssemblyExports(designId))
      .then((e) => {
        setExports(e);
        setExporting(false);
      })
      .catch((e) => {
        setExporting(false);
        setFatalError(`Export failed: ${e.message}`);
      });
  }, [designId]);

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
        detail: designId ? `design ${designId.slice(0, 8)}` : "no design", view: "assembly" },
      { key: "validate", label: "Validate", state: validationState,
        detail: overallStatus ? STATUS_LABEL[overallStatus] : "not validated",
        view: "assembly" },
      { key: "export", label: "Export", state: exportState,
        detail: exports?.package_built ? "package sealed" : "no package", view: "assembly" },
      { key: "accept", label: "Library", state: libraryState,
        detail: precedentCount > 0
          ? `${precedentCount} precedent${precedentCount === 1 ? "" : "s"}`
          : acceptedThis ? "accepted" : "nothing accepted",
        view: "library" },
    ];
  }, [intake, designId, overallStatus, exports, precedentCount]);

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

  const workspace = view === "assembly" || view === "cascade";

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">LF</span>
          <span className="brand-name">LuxuryForm Studio</span>
        </div>
        <PipelineStepper steps={steps} activeView={view} onNavigate={(v) => setView(v as View)} />
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

      <main className={workspace ? "workspace" : "single"}>
        {view === "intake" && (
          <ErrorBoundary label="Brief intake">
            <IntakePanel
              onConfirmed={(next) => {
                setIntake(next);
                setView("assembly");
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
              designId={designId}
              exports={exports}
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

        {workspace && (
          <>
            <div className="viewport-wrap">
              <Viewport
                reloadToken={reloadToken}
                glbUrl={view === "assembly" ? latestAssemblyGlbUrl : latestGlbUrl}
                onModelRendered={onModelRendered}
                onLoadError={onLoadError}
              />
              <div className="rebuild-timer">
                {lastRebuildMs !== null
                  ? `Last build: ${Math.round(lastRebuildMs)} ms (server ${Math.round(serverBuildMs ?? 0)} ms)`
                  : view === "assembly"
                    ? "Last build: — (press Build assembly)"
                    : "Last rebuild: — (press Rebuild)"}
              </div>
              <div className="viewport-switch">
                {VIEWS.filter((v) => v.key === "assembly" || v.key === "cascade").map((v) => (
                  <button
                    key={v.key}
                    className={view === v.key ? "active" : ""}
                    onClick={() => setView(v.key)}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="side">
              {view === "assembly" ? (
                <ErrorBoundary label="Assembly">
                  <AssemblyPanel
                    seed={seed}
                    busy={busy}
                    violations={violations}
                    intake={intake}
                    onSeedChange={setSeed}
                    onBusyChange={setBusy}
                    onViolationsChange={setViolations}
                    onBuilt={onAssemblyBuilt}
                    onFatal={setFatalError}
                  />
                </ErrorBoundary>
              ) : (
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
              )}
              <ErrorBoundary label="Validation">
                <ValidationPanel
                  validation={validation}
                  gates={validationGates}
                  overallStatus={overallStatus}
                  gateStatuses={gateStatuses}
                />
              </ErrorBoundary>
              {view === "assembly" && (
                <ErrorBoundary label="Export">
                  <ExportPanel
                    designId={designId}
                    exports={exports}
                    exporting={exporting}
                    onExport={onExport}
                  />
                </ErrorBoundary>
              )}
            </div>
          </>
        )}
      </main>

      <footer className="statusbar">
        <span className={`dot ${online ? "is-online" : "is-offline"}`} />
        <span>{online ? "backend connected" : "backend unreachable"}</span>
        <span className="sep" />
        {designId && <span>design <code>{designId.slice(0, 8)}</code></span>}
        {overallStatus && (
          <>
            <span className="sep" />
            <span className={`badge badge-${overallStatus}`}>
              {STATUS_LABEL[overallStatus]}
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
