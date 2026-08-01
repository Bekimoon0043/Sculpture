// Validation panel — every trimesh check with its REAL measured number and
// a PASS/FAIL badge (build order §7: never a bare boolean).

import type { CheckRow, Validation } from "../api/client";

interface ValidationPanelProps {
  validation: Validation | null;
}

function rowsFrom(validation: Validation): CheckRow[] {
  if (validation.rows) return validation.rows;
  // Fallback for the /latest/validation payload (no prebuilt rows).
  return [
    { check: "watertight", value: validation.watertight, passed: validation.watertight },
    {
      check: "winding_consistent",
      value: validation.winding_consistent,
      passed: validation.winding_consistent,
    },
    { check: "volume_mm3", value: validation.volume_mm3, passed: validation.volume_mm3 > 0 },
    {
      check: "surface_area_mm2",
      value: validation.surface_area_mm2,
      passed: validation.surface_area_mm2 > 0,
    },
    { check: "euler_number", value: validation.euler_number, passed: true },
    { check: "bounds_mm", value: validation.bounds_mm, passed: true },
    {
      check: "degenerate_face_count",
      value: validation.degenerate_face_count,
      passed: validation.degenerate_face_count === 0,
    },
    { check: "mass_kg", value: validation.mass_kg, passed: validation.mass_kg > 0 },
  ];
}

export default function ValidationPanel({ validation }: ValidationPanelProps) {
  if (!validation) {
    return (
      <div className="panel validation-panel">
        <h2>Validation</h2>
        <p>No build yet — press Rebuild.</p>
      </div>
    );
  }
  return (
    <div className="panel validation-panel">
      <h2>
        Validation{" "}
        <span className={validation.passed ? "badge pass" : "badge fail"}>
          {validation.passed ? "PASS" : "FAIL"}
        </span>
      </h2>
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
              <td className="num">
                {typeof row.value === "number"
                  ? row.value.toLocaleString(undefined, {
                      maximumFractionDigits: 3,
                    })
                  : String(row.value)}
              </td>
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
