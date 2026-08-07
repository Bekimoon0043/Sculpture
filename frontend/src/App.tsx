// App — wires the parameter panel, viewport and validation panel together,
// including the [ADD-5] rebuild timer: ms from POST start until the new GLB
// is rendered on screen, shown persistently in the viewport corner.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  BuildResponse,
  DefaultsResponse,
  Validation,
  getDefaults,
  getLatestValidation,
  postBuild,
} from "./api/client";
import CascadePanel from "./panels/CascadePanel";
import CouncilPanel from "./panels/CouncilPanel";
import ValidationPanel from "./panels/ValidationPanel";
import Viewport from "./viewport/Viewport";

export default function App() {
  const [defaults, setDefaults] = useState<DefaultsResponse | null>(null);
  const [values, setValues] = useState<Record<string, number | string>>({});
  const [seed, setSeed] = useState(0);
  const [busy, setBusy] = useState(false);
  const [violations, setViolations] = useState<string[] | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [view, setView] = useState<"cascade" | "council">("cascade");
  const [serverBuildMs, setServerBuildMs] = useState<number | null>(null);
  const [lastRebuildMs, setLastRebuildMs] = useState<number | null>(null);
  const rebuildStartRef = useRef<number | null>(null);

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
    getLatestValidation()
      .then((v) => v && setValidation(v.validation))
      .catch(() => undefined);
  }, []);

  const onRebuild = useCallback(() => {
    setBusy(true);
    setViolations(null);
    rebuildStartRef.current = performance.now(); // [ADD-5] timer starts
    postBuild(values, seed)
      .then((resp: BuildResponse) => {
        setValidation(resp.validation);
        setServerBuildMs(resp.build_ms);
        setReloadToken((t) => t + 1); // viewport reloads; timer stops on render
        setBusy(false);
      })
      .catch((e) => {
        rebuildStartRef.current = null;
        setBusy(false);
        if (e instanceof ApiError && e.violations) {
          setViolations(e.violations);
        } else {
          setFatalError(`Rebuild failed: ${e.message}`);
        }
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
      // Before the first build, latest.glb 404s — that is expected, not fatal.
      if (reloadToken === 0) return;
      setFatalError(`Viewport could not load the model: ${message}`);
    },
    [reloadToken]
  );

  if (view === "council") {
    return (
      <div className="council-wrap">
        <nav className="view-nav">
          <button onClick={() => setView("cascade")}>Cascade viewport</button>
          <button className="active" disabled>
            AI Council
          </button>
        </nav>
        <CouncilPanel />
      </div>
    );
  }

  if (fatalError) {
    return (
      <div className="fatal">
        <h1>LuxuryForm Studio — Cascade Viewport</h1>
        <p>{fatalError}</p>
        <p>
          Is the backend running? Start it with <code>docker compose up</code>{" "}
          (see docs/operator/02_phase2_viewport.md).
        </p>
      </div>
    );
  }
  if (!defaults) {
    return <div className="loading">Loading parameter registry…</div>;
  }

  return (
    <div>
      <nav className="view-nav">
        <button className="active" disabled>
          Cascade viewport
        </button>
        <button onClick={() => setView("council")}>AI Council</button>
      </nav>
      <div className="app-grid">
      <div className="viewport-wrap">
        <Viewport
          reloadToken={reloadToken}
          onModelRendered={onModelRendered}
          onLoadError={onLoadError}
        />
        <div className="rebuild-timer">
          {lastRebuildMs !== null
            ? `Last rebuild: ${Math.round(lastRebuildMs)} ms (server build: ${Math.round(
                serverBuildMs ?? 0
              )} ms)`
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
        <ValidationPanel validation={validation} />
      </div>
      </div>
    </div>
  );
}
