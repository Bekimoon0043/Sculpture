// Brief intake — Phase 12 (L1).
//
// The form IS the product here: a client's prose on the left, the typed
// contexts it becomes on the right, and every field wearing its provenance
// (operator / parsed / default / unknown). The operator can always see what
// the parser inferred versus what he typed, with the client's own sentence
// as evidence.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  type IntakeResponse,
  type SourcedField,
  confirmIntake,
  createIntake,
  getLatestIntake,
  parseIntake,
  updateIntake,
} from "../api/client";

interface FieldSpec {
  field: string; // dotted
  label: string;
  unit?: string;
  kind: "text" | "number" | "bool" | "choice";
  choices?: string[];
  help?: string;
}

interface SectionSpec {
  title: string;
  blurb?: string;
  fields: FieldSpec[];
}

const SECTIONS: SectionSpec[] = [
  {
    title: "Project",
    fields: [
      { field: "project.project_type", label: "Project type", kind: "choice",
        choices: ["fountain", "sculpture", "water_wall", "monument"] },
      { field: "project.name", label: "Project name", kind: "text" },
      { field: "project.setting", label: "Setting", kind: "choice",
        choices: ["public", "private"] },
    ],
  },
  {
    title: "Dimensions",
    fields: [
      { field: "dimensions.height_m", label: "Overall height", unit: "m", kind: "number" },
      { field: "dimensions.footprint_m", label: "Footprint", unit: "m", kind: "number" },
    ],
  },
  {
    title: "Site",
    blurb: "Site facts feed the structural gate directly — wind and bearing "
      + "come from the wind map and the geotechnical survey, per project.",
    fields: [
      { field: "site.city", label: "City", kind: "text" },
      { field: "site.country", label: "Country", kind: "text" },
      { field: "site.indoor", label: "Indoor", kind: "bool",
        help: "indoor removes the wind load case" },
      { field: "site.altitude_m", label: "Altitude", unit: "m", kind: "number",
        help: "drives air density for the wind calculation" },
      { field: "site.design_wind_speed_m_s", label: "Design wind (3 s gust)",
        unit: "m/s", kind: "number",
        help: "from the local wind map or the structural engineer" },
      { field: "site.allowable_bearing_kpa", label: "Allowable bearing",
        unit: "kPa", kind: "number", help: "from the geotechnical survey" },
      { field: "site.freeze_risk", label: "Freeze risk", kind: "bool" },
      { field: "site.water_available", label: "Water available on site", kind: "bool" },
    ],
  },
  {
    title: "Water",
    fields: [
      { field: "water.has_water", label: "Water design", kind: "bool" },
      { field: "water.behavior", label: "Behaviour", kind: "choice",
        choices: ["jet", "cascade", "sheet", "still", "mist"] },
      { field: "water.flow_l_per_min", label: "Pump flow", unit: "L/min", kind: "number" },
      { field: "water.operating_depth_mm", label: "Operating depth", unit: "mm", kind: "number" },
      { field: "water.nozzle_bore_mm", label: "Nozzle bore", unit: "mm", kind: "number" },
    ],
  },
  {
    title: "Culture & materials",
    fields: [
      { field: "culture.inspiration", label: "Inspiration", kind: "text" },
      { field: "culture.motifs", label: "Motifs", kind: "text" },
      { field: "culture.forbidden_motifs", label: "Forbidden motifs", kind: "text" },
    ],
  },
  {
    title: "Budget & deadline",
    fields: [
      { field: "budget.currency", label: "Currency", kind: "text" },
      { field: "budget.amount_min", label: "Budget from", kind: "number" },
      { field: "budget.amount_max", label: "Budget to", kind: "number" },
      { field: "budget.contingency_pct", label: "Contingency", unit: "%", kind: "number" },
      { field: "budget.deadline", label: "Deadline", kind: "text" },
    ],
  },
];

function readField(intake: IntakeResponse | null, dotted: string): SourcedField | null {
  if (!intake) return null;
  const [section, name] = dotted.split(".");
  const sec = intake.intake[section];
  if (!sec || typeof sec === "string") return null;
  return sec[name] ?? null;
}

function SourceChip({ field }: { field: SourcedField | null }) {
  const source = field?.source ?? "unknown";
  return (
    <span className={`source-chip source-${source}`} title={field?.quote ?? undefined}>
      {source}
    </span>
  );
}

export default function IntakePanel({
  onConfirmed,
  onFatal,
}: {
  onConfirmed: (intake: IntakeResponse) => void;
  onFatal: (message: string) => void;
}) {
  const [intake, setIntake] = useState<IntakeResponse | null>(null);
  const [brief, setBrief] = useState("");
  const [edits, setEdits] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    getLatestIntake()
      .then((latest) => {
        if (latest) {
          setIntake(latest);
          setBrief(latest.brief_text);
        }
      })
      .catch(() => undefined);
  }, []);

  const dirty = Object.keys(edits).length > 0;

  const refresh = useCallback((next: IntakeResponse) => {
    setIntake(next);
    setEdits({});
  }, []);

  const onStart = useCallback(() => {
    setBusy("create");
    createIntake(brief)
      .then((created) => {
        refresh(created);
        setBusy(null);
        setNotice("Intake created. Parse the brief or fill the form by hand.");
      })
      .catch((e) => {
        setBusy(null);
        onFatal(`Could not create the intake: ${e.message}`);
      });
  }, [brief, refresh, onFatal]);

  const onSave = useCallback(() => {
    if (!intake || !dirty) return;
    setBusy("save");
    updateIntake(intake.id, edits)
      .then((next) => {
        refresh(next);
        setBusy(null);
        setNotice("Fields saved — no tokens spent.");
      })
      .catch((e) => {
        setBusy(null);
        onFatal(`Could not save fields: ${e.message}`);
      });
  }, [intake, edits, dirty, refresh, onFatal]);

  const onParse = useCallback(() => {
    if (!intake) return;
    setBusy("parse");
    parseIntake(intake.id)
      .then((next) => {
        refresh(next);
        setBusy(null);
        const p = next.parse;
        setNotice(
          p
            ? `Parsed by ${p.provider}: ${p.applied} fields filled, ` +
              `${p.kept_operator} of yours kept, $${p.cost_usd.toFixed(4)}.`
            : "Parsed."
        );
      })
      .catch((e) => {
        setBusy(null);
        if (e instanceof ApiError) setNotice(e.message);
        else onFatal(`Parse failed: ${e.message}`);
      });
  }, [intake, refresh, onFatal]);

  const onConfirm = useCallback(() => {
    if (!intake) return;
    setBusy("confirm");
    confirmIntake(intake.id)
      .then((next) => {
        refresh(next);
        setBusy(null);
        setNotice("Intake confirmed — the assembly gates and the Council can use it.");
        onConfirmed(next);
      })
      .catch((e) => {
        setBusy(null);
        setNotice(e.message);
      });
  }, [intake, refresh, onConfirmed]);

  const readiness = intake?.readiness;
  const missingTiers = useMemo(
    () => Object.entries(readiness?.missing_by_tier ?? {}).sort(),
    [readiness]
  );

  return (
    <div className="page intake-page">
      <section className="panel">
        <h2>Client brief</h2>
        <p className="hint">
          Paste the client's own words. The parser fills the form from them —
          it never overwrites a field you typed, and it never guesses a value
          the brief does not state.
        </p>
        <textarea
          className="brief-input"
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          placeholder="e.g. A basalt fountain for the hotel forecourt in Addis Ababa, about two and a half metres tall, with a gentle central jet…"
          rows={7}
        />
        <div className="button-row">
          {!intake ? (
            <button className="rebuild" onClick={onStart} disabled={busy !== null}>
              {busy === "create" ? "Creating…" : "Start intake"}
            </button>
          ) : (
            <button
              className="rebuild secondary"
              onClick={onParse}
              disabled={busy !== null || !intake.brief_text.trim()}
              title="One paid provider call, logged and budget-capped"
            >
              {busy === "parse" ? "Parsing…" : "Parse brief ($)"}
            </button>
          )}
        </div>
        {notice && <p className="notice">{notice}</p>}
      </section>

      {intake && (
        <>
          <section className="panel">
            <h2>
              Readiness{" "}
              <span
                className={`badge ${readiness?.ready_for_council ? "badge-pass" : "badge-needs_input"}`}
              >
                {readiness?.ready_for_council ? "READY" : "NOT READY"}
              </span>
              {intake.status === "confirmed" && (
                <span className="badge badge-pass">CONFIRMED</span>
              )}
            </h2>
            {missingTiers.length === 0 ? (
              <p className="hint">Every ranked field is answered.</p>
            ) : (
              <div className="tier-list">
                {missingTiers.map(([tier, rows]) => (
                  <div key={tier} className="tier-row">
                    <span className={`tier-chip tier-${tier}`}>
                      tier {tier} · {readiness?.tier_labels[tier]}
                    </span>
                    <ul>
                      {rows.map((row) => (
                        <li key={row.field}>
                          <code>{row.field}</code> — {row.why}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
            <div className="button-row">
              <button
                className="rebuild"
                onClick={onConfirm}
                disabled={busy !== null || !readiness?.ready_for_council || dirty}
                title={dirty ? "Save your edits first" : undefined}
              >
                {busy === "confirm" ? "Confirming…" : "Confirm intake"}
              </button>
              {dirty && (
                <button className="rebuild secondary" onClick={onSave} disabled={busy !== null}>
                  {busy === "save" ? "Saving…" : `Save ${Object.keys(edits).length} field(s)`}
                </button>
              )}
            </div>
            <p className="hint">
              Tiers 1 and 2 must be answered before paid Council calls. Tiers
              3 and 4 may stay unknown — the affected layer will say so
              honestly instead of inventing a number.
            </p>
          </section>

          <div className="intake-grid">
            {SECTIONS.map((section) => (
              <section className="panel" key={section.title}>
                <h3>{section.title}</h3>
                {section.blurb && <p className="hint">{section.blurb}</p>}
                {section.fields.map((spec) => {
                  const current = readField(intake, spec.field);
                  const pending = edits[spec.field];
                  const shown =
                    pending !== undefined ? pending : current?.value ?? "";
                  return (
                    <label className="intake-field" key={spec.field}>
                      <span className="field-label">
                        {spec.label}
                        {spec.unit && <em> ({spec.unit})</em>}
                      </span>
                      {spec.kind === "bool" ? (
                        <select
                          value={
                            shown === true ? "yes" : shown === false ? "no" : ""
                          }
                          onChange={(e) =>
                            setEdits((prev) => ({
                              ...prev,
                              [spec.field]:
                                e.target.value === ""
                                  ? null
                                  : e.target.value === "yes",
                            }))
                          }
                        >
                          <option value="">unknown</option>
                          <option value="yes">yes</option>
                          <option value="no">no</option>
                        </select>
                      ) : spec.kind === "choice" ? (
                        <select
                          value={typeof shown === "string" ? shown : ""}
                          onChange={(e) =>
                            setEdits((prev) => ({
                              ...prev,
                              [spec.field]: e.target.value || null,
                            }))
                          }
                        >
                          <option value="">unknown</option>
                          {spec.choices!.map((c) => (
                            <option key={c} value={c}>{c}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type={spec.kind === "number" ? "number" : "text"}
                          value={shown === null ? "" : String(shown)}
                          onChange={(e) =>
                            setEdits((prev) => ({
                              ...prev,
                              [spec.field]:
                                e.target.value === ""
                                  ? null
                                  : spec.kind === "number"
                                    ? Number(e.target.value)
                                    : e.target.value,
                            }))
                          }
                        />
                      )}
                      <SourceChip
                        field={
                          pending !== undefined
                            ? { value: pending, source: "operator" }
                            : current
                        }
                      />
                      {current?.quote && pending === undefined && (
                        <span className="field-quote">“{current.quote}”</span>
                      )}
                      {spec.help && <span className="field-help">{spec.help}</span>}
                    </label>
                  );
                })}
              </section>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
