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
import { CircleAlert, CircleCheck, CircleHelp, CircleX, LocateFixed } from "lucide-react";

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
  elementIds?: string[];
  onSelectElement?: (elementId: string) => void;
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

const STATUS_HEADLINE: Record<GateStatus, string> = {
  pass: "Ready to progress",
  warn: "Review before fabrication",
  fail: "Changes required",
  needs_input: "Project input required",
};

const STATUS_ICON = {
  pass: CircleCheck,
  warn: CircleAlert,
  fail: CircleX,
  needs_input: CircleHelp,
};

function humanize(value: string): string {
  const words = value.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

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
  elementIds = [],
  onSelectElement,
}: ValidationPanelProps) {
  if (!validation) {
    return (
      <div className="panel validation-panel">
        <h2>Checks</h2>
        <p className="hint">Build the design to run fabrication and site checks.</p>
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
  const StatusIcon = STATUS_ICON[headerStatus];
  const issues = gateEntries.flatMap(([gateName, gate]) =>
    gateRows(gate)
      .filter((row) => rowStatus(row) !== "pass")
      .map((row) => {
        const searchable = `${row.check} ${row.message ?? ""} ${JSON.stringify(row.value)}`;
        return {
          gateName,
          row,
          status: rowStatus(row),
          elementId: elementIds.find((id) => searchable.includes(id)) ?? null,
        };
      })
  );

  return (
    <div className="panel validation-panel">
      <div className={`check-summary status-${headerStatus}`}>
        <StatusIcon size={22} aria-hidden="true" />
        <div>
          <strong>{STATUS_HEADLINE[headerStatus]}</strong>
          <p>{STATUS_HINT[headerStatus]}</p>
        </div>
        <span className={`badge badge-${headerStatus}`}>
          {STATUS_LABEL[headerStatus]}
        </span>
      </div>

      {issues.length > 0 && (
        <div className="issue-list">
          <h3>What needs attention</h3>
          {issues.slice(0, 6).map(({ gateName, row, status, elementId }, index) => (
            <div className={`issue-row issue-${status}`} key={`${gateName}:${row.check}:${index}`}>
              <div>
                <strong>{humanize(row.check)}</strong>
                <small>{row.message || `${humanize(gateName)} requires review.`}</small>
              </div>
              {elementId && onSelectElement && (
                <button type="button" onClick={() => onSelectElement(elementId)}>
                  <LocateFixed size={13} /> {elementId}
                </button>
              )}
            </div>
          ))}
          {issues.length > 6 && (
            <p className="hint">{issues.length - 6} more items are listed in all checks.</p>
          )}
        </div>
      )}

      <details className="validation-details" open={headerStatus === "fail"}>
        <summary>All measured checks</summary>
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
                            <td className={numClass(row.value)}>{formatValue(row.value)}</td>
                            <td className={numClass(row.limit)}>{formatValue(row.limit)}</td>
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
              <td className={numClass(row.value)}>{formatValue(row.value)}</td>
              <td className={row.passed ? "pass" : "fail"}>
                {row.passed ? "PASS" : "FAIL"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </details>
    </div>
  );
}

function numClass(value: unknown): string {
  // Composite values (per-element masses, cross-checks) wrap into readable
  // lines; scalar numbers keep the tabular nowrap treatment (2026-08-04).
  return typeof value === "object" && value !== null ? "num num-wrap" : "num";
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }
  if (Array.isArray(value)) {
    return value.map((v) => formatValue(v)).join(", ");
  }
  if (typeof value === "object") {
    // e.g. element_masses_kg — per-key readable pairs, never a JSON blob
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => `${k}: ${formatValue(v)}`)
      .join(" · ");
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
