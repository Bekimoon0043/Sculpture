// Recent builds — persisted design snapshots a designer can reopen or compare.
//
// Entries come from two honest sources, merged: builds made THIS session
// (which carry a real viewport snapshot taken when their geometry was on
// screen) and the persisted design list from the backend (which survives
// reloads; their thumbnails come from the localStorage snapshot cache, or
// a schematic placeholder when the snapshot never existed on this
// machine). A thumbnail is never synthesised from anything but a real
// rendered frame.
//
// Click a card -> restore that design (viewport + document). Check two
// cards -> side-by-side compare.

import type { GateStatus } from "../api/client";
import { ChevronDown, ChevronUp, Images } from "lucide-react";

export interface VariantEntry {
  design_id: string;
  created_at: string;
  /** e.g. "plinth + basin_round + sculptural_column" */
  label: string;
  seed: number;
  overall_status: GateStatus | null;
  total_mass_kg: number | null;
  thumbnail: string | null;
  element_ids: string[];
}

const STATUS_SHORT: Record<GateStatus, string> = {
  pass: "PASS",
  warn: "WARN",
  fail: "FAIL",
  needs_input: "NEEDS INPUT",
};

interface HistoryStripProps {
  entries: VariantEntry[];
  activeDesignId: string | null;
  compareIds: string[];
  onRestore: (entry: VariantEntry) => void;
  onToggleCompare: (designId: string) => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

export default function HistoryStrip({
  entries,
  activeDesignId,
  compareIds,
  onRestore,
  onToggleCompare,
  collapsed,
  onToggleCollapsed,
}: HistoryStripProps) {
  return (
    <section className={`history-strip ${collapsed ? "is-collapsed" : ""}`}>
      <button
        type="button"
        className="history-toggle"
        onClick={onToggleCollapsed}
        title={collapsed ? "Open recent builds" : "Collapse recent builds"}
        aria-expanded={!collapsed}
      >
        <Images size={15} aria-hidden="true" />
        <span>Recent builds</span>
        <span className="history-count">{entries.length}</span>
        {collapsed ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
      </button>
      {!collapsed && entries.length === 0 && (
        <div className="history-empty">
          <span className="hint">Saved builds appear here after the first build.</span>
        </div>
      )}
      {!collapsed && (
        <div className="history-items" role="list" aria-label="recent design builds">
          {entries.map((v) => {
        const active = v.design_id === activeDesignId;
        const comparing = compareIds.includes(v.design_id);
        return (
          <div
            key={v.design_id}
            role="listitem"
            className={[
              "variant-card",
              active ? "is-active" : "",
              comparing ? "is-comparing" : "",
            ].join(" ")}
          >
            <button
              type="button"
              className="variant-thumb"
              onClick={() => onRestore(v)}
              title={`${v.label}\nseed ${v.seed} — click to open`}
            >
              {v.thumbnail ? (
                <img src={v.thumbnail} alt={v.label} />
              ) : (
                <span className="variant-thumb-placeholder" aria-hidden="true">
                  <Images size={22} />
                </span>
              )}
            </button>
            <div className="variant-meta">
              <span className="variant-time">
                {new Date(v.created_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
              {v.overall_status && (
                <span className={`badge badge-${v.overall_status}`}>
                  {STATUS_SHORT[v.overall_status]}
                </span>
              )}
              {v.total_mass_kg !== null && (
                <span className="variant-mass">
                  {Math.round(v.total_mass_kg)} kg
                </span>
              )}
              <label
                className="variant-compare"
                title="select two variants to compare side by side"
              >
                <input
                  type="checkbox"
                  checked={comparing}
                  disabled={!comparing && compareIds.length >= 2}
                  onChange={() => onToggleCompare(v.design_id)}
                />
                <span>A/B</span>
              </label>
            </div>
          </div>
        );
          })}
        </div>
      )}
    </section>
  );
}
