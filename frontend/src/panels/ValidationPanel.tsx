// Validation panel — every check with its REAL measured number and a
// four-state badge (build order §7: never a bare boolean).
//
// Phase 8 honesty rule: a warning is NOT a pass, and `needs_input` is not a
// warning. The header shows the WORST status across every gate, so a design
// warned on three layers can never display a green PASS.

import type {
  CheckRow,
  GateStatus,
  Validation,
  ValidationGate,
} from "../api/client";

interface ValidationPanelProps {
  validation: Validation | null;
  gates?: Record<string, ValidationGate> | null;
  overallStatus?: GateStatus | null;
  /**
   * The AUTHORITATIVE per-gate status, from the persisted status column.
   *
   * Not every gate blob carries a status of its own: the mesh report is a
   * ValidationReport, not a LayeredGateReport, so it has no `status` key.
   * Falling back to needs_input for it made a PASSING watertight check
   * render as NEEDS INPUT — the card contradicted the server.
   */
  gateStatuses?: Record<string, GateStatus> | null;
}

const STATUS_RANK: Record<GateStatus, number> = {
  fail: 3,
  needs_input: 2,
  warn: 1,
  pass: 0,
};

const STATUS_LABEL: Record<GateStatus, string> = {
  pass: "PASS",
  warn: "WARN",
  fail: "FAIL",
  needs_input: "NEEDS INPUT",
};

const STATUS_HINT: Record<GateStatus, string> = {
  pass: "Every check ran and every measured value is inside its limit.",
  warn: "Checks ran. At least one value is marginal, or breached a threshold "
    + "whose gate profile has not been signed off yet.",
  fail: "At least one measured value is outside a limit. This blocks acceptance.",
  needs_input: "At least one check could NOT be evaluated — a required input "
    + "is missing. This is not a pass. See the rows below for what to supply.",
};

function worstStatus(statuses: GateStatus[]): GateStatus {
  return statuses.reduce<GateStatus>(
    (worst, s) => (STATUS_RANK[s] > STATUS_RANK[worst] ? s : worst),
    "pass"
  );
}

function rowStatus(row: CheckRow): GateStatus {
  if (row.status) return row.status;
  return row.passed ? "pass" : "fail";
}

/**
 * Rows for one gate card, defensively.
 *
 * `gates` comes straight from persisted reports, and not every report is a
 * layered gate: the mesh report has neither `rows` nor `checks`. Reading
 * `(gate.rows ?? gate.checks).map(...)` threw on it and took the whole app
 * down — a blank page, which on this theme reads as a black screen.
 *
 * A panel whose job is to report failures must never be the thing that
 * fails. Anything without check rows renders as a badge with a note.
 */
function gateRows(gate: ValidationGate): CheckRow[] {
  const rows = gate.rows ?? gate.checks;
  return Array.isArray(rows) ? rows : [];
}

function gateStatus(
  name: string,
  gate: ValidationGate,
  authoritative?: Record<string, GateStatus> | null
): GateStatus {
  const fromServer = authoritative?.[name];
  if (fromServer && fromServer in STATUS_RANK) return fromServer;
  if (gate.status && gate.status in STATUS_RANK) return gate.status;
  return "needs_input";
}

function rowsFrom(validation: Validation): CheckRow[] {
  if (Array.isArray(validation.rows)) return validation.rows;
  const preferred = [
    "watertight",
    "winding_consistent",
    "body_count",
    "element_count",
    "joint_count",
    "volume_mm3",
    "surface_area_mm2",
    "degenerate_face_count",
    "face_count",
    "element_masses_kg",
    "total_mass_kg",
    "volume_crosscheck",
    "euler_number",
    "bounds_mm",
    "mass_kg",
  ];
  const rows = preferred
    .filter((key) => validation[key] !== undefined)
    .map((key) => ({
      check: key,
      value: validation[key],
      passed: valuePasses(key, validation[key]),
    }));
  if (rows.length > 0) return rows;
  return [{ check: "passed", value: validation.passed, passed: validation.passed }];
}

export default function ValidationPanel({
  validation,
  gates,
  overallStatus,
  gateStatuses,
}: ValidationPanelProps) {
  if (!validation) {
    return (
      <div className="panel validation-panel">
        <h2>Validation</h2>
        <p>No build yet — press Rebuild.</p>
      </div>
    );
  }

  const gateEntries = gates ? Object.entries(gates) : [];
  const headerStatus: GateStatus =
    overallStatus ??
    worstStatus([
      validation.passed ? "pass" : "fail",
      ...gateEntries.map(([name, gate]) => gateStatus(name, gate, gateStatuses)),
    ]);

  return (
    <div className="panel validation-panel">
      <h2>
        Validation{" "}
        <span className={`badge badge-${headerStatus}`}>
          {STATUS_LABEL[headerStatus]}
        </span>
      </h2>
      <p className="hint">{STATUS_HINT[headerStatus]}</p>

      {gateEntries.length > 0 && (
        <div className="gate-list">
          {gateEntries.map(([name, gate]) => {
            const status = gateStatus(name, gate, gateStatuses);
            const rows = gateRows(gate);
            return (
              <details className="gate-card" key={name} open={status === "fail"}>
                <summary>
                  <strong>{name}</strong>{" "}
                  <span className={`badge badge-${status}`}>
                    {STATUS_LABEL[status]}
                  </span>
                  {gate.profile_signed_off === false && (
                    <em className="profile-note">
                      {" "}
                      profile “{gate.gate_profile_id}” not signed off
                    </em>
                  )}
                </summary>
                {rows.length === 0 ? (
                  <p className="hint">
                    This report has no per-check rows of its own — its
                    measurements are in the table below. (The mesh report is
                    a whole-body watertight check, not a list of thresholds.)
                  </p>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th>check</th>
                        <th>value</th>
                        <th>limit</th>
                        <th>verdict</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => {
                        const rstatus = rowStatus(row);
                        return (
                          <tr key={row.check} className={`row-${rstatus}`}>
                            <td>
                              {row.check}
                              {row.units ? (
                                <span className="unit"> ({row.units})</span>
                              ) : null}
                              {row.message && (
                                <div className="check-message">{row.message}</div>
                              )}
                              {row.basis && (
                                <div className="check-basis">basis: {row.basis}</div>
                              )}
                            </td>
                            <td className="num">{formatValue(row.value)}</td>
                            <td className="num">{formatValue(row.limit)}</td>
                            <td className={`verdict ${rstatus}`}>
                              {STATUS_LABEL[rstatus]}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </details>
            );
          })}
        </div>
      )}

      <table>
        <thead>
          <tr>
            <th>check</th>
            <th>value</th>
            <th>verdict</th>
          </tr>
        </thead>
        <tbody>
          {rowsFrom(validation).map((row) => (
            <tr key={row.check}>
              <td>{row.check}</td>
              <td className="num">{formatValue(row.value)}</td>
              <td className={row.passed ? "pass" : "fail"}>
                {row.passed ? "PASS" : "FAIL"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }
  if (Array.isArray(value) || typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function valuePasses(key: string, value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (key === "body_count") return value === 1;
  if (key === "degenerate_face_count") return value === 0;
  if (key === "volume_crosscheck" && value && typeof value === "object") {
    return (value as { within_tolerance?: unknown }).within_tolerance === true;
  }
  if (typeof value === "number") return value > 0;
  return value !== undefined && value !== null;
}
