// Council panel (Phase 3, build step 3) — the full transcript of a Council
// session: every call as a role card with provider, tokens (incl. ADR-022
// cache split), cost and latency; the Arbiter decision card with confidence;
// and a cost panel showing actual spend against the hard caps ($5 session /
// $25 day) plus the cache-hit savings.
//
// The "Load demo session" button replays the committed SYNTHETIC fixture
// ($0, offline) — labeled synthetic everywhere it surfaces. Live sessions
// arrive with build step 4.

import { useCallback, useEffect, useState } from "react";
import {
  CouncilCall,
  CouncilSessionDetail,
  CouncilSessionSummary,
  getCouncilSession,
  getCouncilSessions,
  loadDemoSession,
} from "../api/client";

function usd(n: number): string {
  return `$${n.toFixed(n < 0.01 ? 6 : 4)}`;
}

function CallCard({ call }: { call: CouncilCall }) {
  const cacheNote =
    call.cached_input_tokens > 0 || call.cache_write_input_tokens > 0
      ? ` (cache read ${call.cached_input_tokens}, write ${call.cache_write_input_tokens})`
      : "";
  return (
    <details className="call-card">
      <summary>
        <span className={`badge badge-${call.status === "ok" ? "pass" : "fail"}`}>
          {call.role}
        </span>{" "}
        <span className="call-side">{call.side}</span>{" "}
        <strong>{call.provider}</strong> · {call.model} · in {call.tokens_in}
        {cacheNote} / out {call.tokens_out} tok · {usd(call.cost_usd)} ·{" "}
        {Math.round(call.latency_ms)} ms
        {call.status !== "ok" && (
          <span className="badge badge-fail"> {call.status}</span>
        )}
      </summary>
      {call.error && <p className="call-error">error: {call.error}</p>}
      <h4>Prompt</h4>
      <pre className="payload">{call.prompt}</pre>
      <h4>Response</h4>
      <pre className="payload">{call.response}</pre>
    </details>
  );
}

export default function CouncilPanel() {
  const [sessions, setSessions] = useState<CouncilSessionSummary[]>([]);
  const [selected, setSelected] = useState<CouncilSessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    getCouncilSessions()
      .then((r) => setSessions(r.sessions))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(refresh, [refresh]);

  const onSelect = useCallback((id: string) => {
    setError(null);
    getCouncilSession(id)
      .then(setSelected)
      .catch((e) => setError(e.message));
  }, []);

  const onDemo = useCallback(() => {
    setBusy(true);
    setError(null);
    loadDemoSession()
      .then((r) => {
        refresh();
        return getCouncilSession(r.session_id);
      })
      .then(setSelected)
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  }, [refresh]);

  const rollup = selected?.cost_rollup ?? null;
  const decision = selected?.arbiter_decision ?? null;
  const capPct =
    rollup && rollup.session_cap_usd > 0
      ? Math.min(100, (rollup.total_cost_usd / rollup.session_cap_usd) * 100)
      : 0;

  return (
    <div className="council">
      <div className="panel">
        <h2>AI Council — sessions</h2>
        <p className="hint">
          Phase 3 of 7, build step 3: transcript viewer. Live sessions arrive
          with step 4; the demo session is the committed synthetic fixture
          ($0, offline).
        </p>
        <button className="rebuild" onClick={onDemo} disabled={busy}>
          {busy ? "Loading…" : "Load demo session (synthetic, $0)"}
        </button>
        {error && <p className="call-error">{error}</p>}
        {sessions.length === 0 ? (
          <p className="hint">No council sessions yet.</p>
        ) : (
          <ul className="session-list">
            {sessions.map((s) => (
              <li key={s.id}>
                <button
                  className="session-item"
                  onClick={() => onSelect(s.id)}
                >
                  <strong>{s.status}</strong> · {usd(s.total_cost_usd)} ·{" "}
                  {new Date(s.created_at).toLocaleString()}
                  {s.synthetic && <span className="badge"> synthetic</span>}
                  {s.degraded === 1 && (
                    <span className="badge badge-fail" title="A provider failure left a role seat empty or reduced"> degraded</span>
                  )}
                  {s.corrected === 1 && (
                    <span className="badge badge-warn" title="A bounded re-ask succeeded — the Council corrected itself"> corrected</span>
                  )}
                  <br />
                  <span className="hint">{s.brief_text}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {selected && (
        <>
          <div className="panel">
            <h2>
              Cost — session {selected.session.id.slice(0, 8)}…
              {selected.session.synthetic && (
                <span className="badge"> synthetic</span>
              )}
            </h2>
            {rollup && (
              <>
                <div className="cost-bar-wrap">
                  <div
                    className="cost-bar"
                    style={{ width: `${capPct}%` }}
                  />
                </div>
                <p>
                  <strong>{usd(rollup.total_cost_usd)}</strong> of{" "}
                  {usd(rollup.session_cap_usd)} session cap (day cap{" "}
                  {usd(rollup.day_cap_usd)}) · {rollup.call_count} calls ·
                  pricing {rollup.pricing_version}
                </p>
                <p className="hint">
                  Cache-hit savings vs all-full-rate billing:{" "}
                  {usd(rollup.cache_savings_usd)} (ADR-022)
                </p>
                <h3>By role</h3>
                <ul className="cost-list">
                  {Object.entries(rollup.by_role).map(([role, cost]) => (
                    <li key={role}>
                      {role}: {usd(cost)}
                    </li>
                  ))}
                </ul>
                <h3>By provider</h3>
                <ul className="cost-list">
                  {Object.entries(rollup.by_provider).map(([prov, cost]) => (
                    <li key={prov}>
                      {prov}: {usd(cost)}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>

          {decision && (
            <div className="panel">
              <h2>Arbiter decision (binding)</h2>
              <p>
                Confidence: <strong>{decision.confidence}</strong>
              </p>
              <p>{decision.rationale}</p>
              <details>
                <summary>Chosen spec ids + disagreement register</summary>
                <pre className="payload">
                  {decision.chosen_spec_ids_json}
                </pre>
                <pre className="payload">
                  {decision.disagreement_register_json}
                </pre>
              </details>
            </div>
          )}

          <div className="panel">
            <h2>Design specs ({selected.specs.length})</h2>
            {selected.specs.map((s) => (
              <details key={s.id} className="call-card">
                <summary>
                  <strong>{s.provider}</strong> alt {s.alternative_no} · seed{" "}
                  {s.seed} ·{" "}
                  <span
                    className={`badge badge-${s.schema_valid ? "pass" : "fail"}`}
                  >
                    {s.schema_valid ? "schema-valid" : "schema-INVALID"}
                  </span>{" "}
                  · hash {s.spec_hash.slice(0, 12)}…
                </summary>
                <pre className="payload">{s.spec_json}</pre>
              </details>
            ))}
          </div>

          {selected.programs && selected.programs.length > 0 && (
            <div className="panel">
              <h2>Fabrication ({selected.programs.length} program attempts)</h2>
              {selected.programs.map((p) => (
                <details key={p.id} className="call-card">
                  <summary>
                    <strong>attempt {p.attempt_no}</strong> · {p.provider} ·{" "}
                    <span
                      className={`badge badge-${p.status === "passed" ? "pass" : "fail"}`}
                    >
                      {p.status}
                    </span>{" "}
                    · spec {p.spec_id.slice(0, 8)}… · hash{" "}
                    {p.program_hash.slice(0, 12)}…
                  </summary>
                  {p.rejection_reason && (
                    <p className="hint">AST rejection: {p.rejection_reason}</p>
                  )}
                  {p.error_digest && (
                    <pre className="payload">{p.error_digest}</pre>
                  )}
                  {p.artifacts_json && (
                    <p className="hint">artifacts: {p.artifacts_json}</p>
                  )}
                  {p.validation_json && (
                    <pre className="payload">{p.validation_json}</pre>
                  )}
                </details>
              ))}
            </div>
          )}

          <div className="panel">
            <h2>Transcript ({selected.calls.length} calls)</h2>
            {selected.calls.map((c) => (
              <CallCard key={c.id} call={c} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
