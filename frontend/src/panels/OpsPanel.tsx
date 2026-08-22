// Operations — Phase 13 slice A: jobs, spend, and the reconciliation that
// makes the spend trustworthy.
//
// The reconciliation card is the point of this screen: the per-call book
// (ai_calls) and the session ledger are written by different code at
// different moments. When they agree, that is evidence; when they do not,
// this screen says so with the session ids — never smooths it over.

import { useCallback, useEffect, useState } from "react";
import {
  type OpsCosts,
  type OpsJob,
  getOpsCosts,
  getOpsJobs,
} from "../api/client";

const FAILURE_HINTS: Record<string, string> = {
  transient: "retryable — a timeout or dropped connection",
  resource: "free disk or memory, then retry",
  input: "the request itself is invalid — fix it, retrying will not help",
  defect: "our bug — report it, do not retry",
  unclassified: "recorded before failure classes existed",
};

function usd(value: number): string {
  return `$${value.toFixed(value < 0.01 && value > 0 ? 6 : 2)}`;
}

export default function OpsPanel({ onFatal }: { onFatal: (m: string) => void }) {
  const [jobs, setJobs] = useState<OpsJob[]>([]);
  const [costs, setCosts] = useState<OpsCosts | null>(null);

  const reload = useCallback(() => {
    Promise.all([getOpsJobs(), getOpsCosts()])
      .then(([jobsBody, costsBody]) => {
        setJobs(jobsBody.jobs);
        setCosts(costsBody);
      })
      .catch((e) => onFatal(`Could not load operations data: ${e.message}`));
  }, [onFatal]);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <div className="page ops-page">
      <section className="panel">
        <h2>
          Spend{" "}
          {costs && <span className="badge">{usd(costs.total_usd)} total</span>}
          <button className="ghost refresh" onClick={reload}>refresh</button>
        </h2>
        {costs && (
          <>
            <div
              className={`reconcile-card ${costs.reconciliation.clean ? "is-clean" : "is-torn"}`}
            >
              <strong>
                {costs.reconciliation.clean
                  ? "Ledgers reconcile"
                  : `Ledger mismatch — ${costs.reconciliation.mismatches.length} session(s)`}
              </strong>
              <p className="hint">
                Every provider call is logged twice: per call, and as a
                session running total. {costs.reconciliation.checked_sessions}{" "}
                session(s) checked;{" "}
                {costs.reconciliation.clean
                  ? "the two books agree to the cent."
                  : "the books disagree — the sessions below need a look."}
              </p>
              {!costs.reconciliation.clean && (
                <ul>
                  {costs.reconciliation.mismatches.map((m) => (
                    <li key={m.session_id}>
                      <code>{m.session_id}</code>: calls {usd(m.calls_usd)} vs
                      ledger {m.ledger_usd === null ? "—" : usd(m.ledger_usd)} —{" "}
                      {m.finding}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {costs.error_calls.count > 0 && (
              <p className="notice">
                {costs.error_calls.count} failed call(s) still cost{" "}
                {usd(costs.error_calls.cost_usd)} — a flaky connection must
                not read as work done.
              </p>
            )}

            {Object.keys(costs.by_purpose).length > 0 ? (
              <table className="ops-table">
                <thead>
                  <tr><th>purpose</th><th>calls</th><th>errors</th><th>cost</th></tr>
                </thead>
                <tbody>
                  {Object.entries(costs.by_purpose).map(([purpose, row]) => (
                    <tr key={purpose}>
                      <td><code>{purpose}</code></td>
                      <td className="num">{row.calls}</td>
                      <td className="num">{row.errors || "—"}</td>
                      <td className="num">{usd(row.cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="hint">No provider calls logged yet — everything so far ran at $0.</p>
            )}
          </>
        )}
      </section>

      <section className="panel">
        <h2>Jobs</h2>
        {jobs.length === 0 ? (
          <p className="hint">No jobs yet. Export a design to see the first one.</p>
        ) : (
          <table className="ops-table">
            <thead>
              <tr><th>when</th><th>type</th><th>status</th><th>checkpoint</th><th>failure</th></tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} className={job.status === "failed" ? "row-fail" : ""}>
                  <td>{job.ts.slice(0, 19).replace("T", " ")}</td>
                  <td>{job.job_type}</td>
                  <td>
                    <span className={`badge ${job.status === "completed" ? "badge-pass" : job.status === "failed" ? "badge-fail" : "badge-warn"}`}>
                      {job.status}
                    </span>
                  </td>
                  <td><code>{String(job.state?.step ?? "—")}</code></td>
                  <td>
                    {job.failure_class ? (
                      <span title={FAILURE_HINTS[job.failure_class] ?? ""}>
                        <strong>{job.failure_class}</strong>
                        {job.halt_reason && (
                          <span className="hint"> {job.halt_reason.slice(0, 60)}</span>
                        )}
                      </span>
                    ) : ("—")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="panel">
        <h2>Backup</h2>
        <p className="hint">
          Backs up the database (online snapshot, safe while running) and
          every design artifact, then proves the restore by re-verifying the
          newest export package. Run from PowerShell in the repo root:
        </p>
        <pre className="command-block">docker compose exec backend python scripts/backup_restore.py backup --out data/backups/luxuryform-backup.zip</pre>
        <p className="hint">
          Restore into a fresh folder (it refuses to merge over existing data):
        </p>
        <pre className="command-block">docker compose exec backend python scripts/backup_restore.py restore --archive data/backups/luxuryform-backup.zip --into data/restored</pre>
      </section>
    </div>
  );
}
