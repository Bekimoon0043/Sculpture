// Library — DesignDNA precedent memory (Phase 11, L8).
//
// Two jobs: accept the current deliverable into memory (with an author and
// a reason — a precedent that cannot say why it was good is not knowledge),
// and search past precedents with EXPLAINED matches: every hit says which
// fields matched and how, because an operator must be able to see why a
// precedent surfaced.

import { useCallback, useEffect, useState } from "react";
import {
  type ExportsResponse,
  type Precedent,
  acceptDesign,
  archivePrecedent,
  deletePrecedent,
  listPrecedents,
  searchPrecedents,
} from "../api/client";

function PrecedentCard({
  precedent,
  onArchive,
  onDelete,
}: {
  precedent: Precedent;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const tags = precedent.tags;
  if (precedent.status === "deleted") {
    return (
      <article className="precedent-card is-deleted">
        <header>
          <strong>{precedent.id.slice(0, 8)}</strong>
          <span className="badge badge-fail">DELETED</span>
        </header>
        <p className="hint">{precedent.detail}</p>
      </article>
    );
  }
  return (
    <article className={`precedent-card ${precedent.status === "archived" ? "is-archived" : ""}`}>
      <header>
        <strong title={precedent.id}>{precedent.id.slice(0, 8)}</strong>
        <span className={`badge badge-${tags?.overall_status ?? "needs_input"}`}>
          {(tags?.overall_status ?? "?").replace("_", " ").toUpperCase()}
        </span>
        {precedent.status === "archived" && (
          <span className="badge">ARCHIVED</span>
        )}
        <time>{precedent.created_at.slice(0, 10)}</time>
      </header>
      <p className="precedent-note">“{precedent.acceptance_note}”</p>
      <p className="precedent-meta">
        {tags?.materials.join(", ")} · {tags?.primitives.join(" + ")} ·{" "}
        {tags?.height_m} m × {tags?.footprint_m} m ·{" "}
        {tags?.total_mass_kg != null
          ? `${tags.total_mass_kg} kg`
          : "mass incomplete"}{" "}
        ·{" "}
        {tags?.has_water ? "water" : "dry"}
        {tags?.total_cost_usd != null && <> · ${tags.total_cost_usd}</>}
      </p>
      {precedent.match_reasons && precedent.match_reasons.length > 0 && (
        <ul className="match-reasons">
          {precedent.match_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
      <footer className="precedent-actions">
        <span className="digest" title={precedent.content_digest}>
          {precedent.content_digest?.slice(0, 12)}…
        </span>
        <span className="spacer" />
        {precedent.status === "active" && (
          <button className="ghost" onClick={() => onArchive(precedent.id)}>
            archive
          </button>
        )}
        <button
          className="ghost danger"
          onClick={() => {
            if (window.confirm(
              "Delete this precedent? The payload is wiped; only a tombstone "
              + "with the id remains. This cannot be undone."
            )) onDelete(precedent.id);
          }}
        >
          delete
        </button>
      </footer>
    </article>
  );
}

export default function LibraryPanel({
  designId,
  exports,
  onAccepted,
  onFatal,
}: {
  designId: string | null;
  exports: ExportsResponse | null;
  onAccepted: () => void;
  onFatal: (message: string) => void;
}) {
  const [precedents, setPrecedents] = useState<Precedent[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [searching, setSearching] = useState(false);
  const [criteria, setCriteria] = useState<{ material: string; water: string; text: string }>(
    { material: "", water: "", text: "" }
  );
  const [acceptedBy, setAcceptedBy] = useState("operator");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(() => {
    listPrecedents(showArchived)
      .then((body) => setPrecedents(body.precedents))
      .catch((e) => onFatal(`Could not load the library: ${e.message}`));
  }, [showArchived, onFatal]);

  useEffect(() => {
    reload();
  }, [reload]);

  const onSearch = useCallback(() => {
    const query: Record<string, string | boolean> = {};
    if (criteria.material) query.material = criteria.material;
    if (criteria.water) query.has_water = criteria.water === "yes";
    if (criteria.text) query.text = criteria.text;
    if (Object.keys(query).length === 0) {
      setSearching(false);
      reload();
      return;
    }
    setSearching(true);
    searchPrecedents(query)
      .then((body) => setPrecedents(body.precedents))
      .catch((e) => onFatal(`Search failed: ${e.message}`));
  }, [criteria, reload, onFatal]);

  const packageReady = Boolean(exports?.package_built && exports.content_digest);
  const alreadyAccepted = Boolean(
    exports?.content_digest &&
    precedents.some((p) => p.content_digest === exports.content_digest)
  );

  const onAccept = useCallback(() => {
    if (!designId) return;
    setBusy(true);
    acceptDesign({
      design_id: designId,
      accepted_by: acceptedBy,
      acceptance_note: note,
    })
      .then(() => {
        setBusy(false);
        setNote("");
        setNotice("Accepted — this deliverable is now searchable precedent.");
        reload();
        onAccepted();
      })
      .catch((e) => {
        setBusy(false);
        setNotice(e.message);
      });
  }, [designId, acceptedBy, note, reload, onAccepted]);

  const onArchive = useCallback(
    (id: string) => {
      archivePrecedent(id).then(reload).catch((e) => onFatal(e.message));
    },
    [reload, onFatal]
  );
  const onDelete = useCallback(
    (id: string) => {
      deletePrecedent(id).then(reload).catch((e) => onFatal(e.message));
    },
    [reload, onFatal]
  );

  return (
    <div className="page library-page">
      <section className="panel accept-panel">
        <h2>Accept the current design</h2>
        {!designId ? (
          <p className="hint">Build an assembly first — there is nothing to accept yet.</p>
        ) : !packageReady ? (
          <p className="hint">
            A precedent is the accepted <strong>deliverable</strong>, so the
            export package must exist first. Build it in the Assembly view's
            Export panel, then accept here.
          </p>
        ) : alreadyAccepted ? (
          <p className="hint">
            This exact deliverable (digest{" "}
            <code>{exports!.content_digest!.slice(0, 12)}…</code>) is already
            in the library.
          </p>
        ) : (
          <>
            <label className="intake-field">
              <span className="field-label">Accepted by</span>
              <input value={acceptedBy} onChange={(e) => setAcceptedBy(e.target.value)} />
            </label>
            <label className="intake-field">
              <span className="field-label">Why is this design good?</span>
              <input
                value={note}
                placeholder="future Council sessions will read this sentence"
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
            <button
              className="rebuild"
              onClick={onAccept}
              disabled={busy || !note.trim() || !acceptedBy.trim()}
            >
              {busy ? "Accepting…" : "Accept as precedent"}
            </button>
          </>
        )}
        {notice && <p className="notice">{notice}</p>}
      </section>

      <section className="panel">
        <h2>Search the library</h2>
        <div className="search-row">
          <input
            placeholder="material id (e.g. basalt_slab)"
            value={criteria.material}
            onChange={(e) => setCriteria((c) => ({ ...c, material: e.target.value }))}
          />
          <select
            value={criteria.water}
            onChange={(e) => setCriteria((c) => ({ ...c, water: e.target.value }))}
          >
            <option value="">water: any</option>
            <option value="yes">water: yes</option>
            <option value="no">water: no</option>
          </select>
          <input
            placeholder="text in the acceptance note"
            value={criteria.text}
            onChange={(e) => setCriteria((c) => ({ ...c, text: e.target.value }))}
          />
          <button className="rebuild secondary" onClick={onSearch}>
            {searching ? "Search again" : "Search"}
          </button>
          <label className="toggle">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
            />
            show archived
          </label>
        </div>
        {searching && (
          <p className="hint">
            Matches are AND-filtered and every hit lists WHY it matched — no
            unexplainable similarity scores.
          </p>
        )}
        {precedents.length === 0 ? (
          <p className="hint">
            {searching
              ? "No precedent matches every criterion."
              : "The library is empty. Accept a finished design to start the house memory."}
          </p>
        ) : (
          <div className="precedent-grid">
            {precedents.map((p) => (
              <PrecedentCard key={p.id} precedent={p} onArchive={onArchive} onDelete={onDelete} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
