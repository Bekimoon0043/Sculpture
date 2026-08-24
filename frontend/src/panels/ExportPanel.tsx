// Export panel — Phase 9A.
//
// The old version put seventeen undifferentiated rows in a narrow side
// panel: STEP sat at the same visual weight as SKP "not possible", the
// error cell was appended as a fourth <td> on some rows only (so the
// columns did not line up), and nothing could be downloaded except the
// whole zip.
//
// Three things drive this layout:
//
// 1. ONE obvious primary action. Build the package, then download it.
// 2. Files grouped by what they are FOR. A fabricator machines from the CAD
//    tier and must never machine from the mesh tier, so the two are
//    visually separated and labelled with the consequence, not the format.
// 3. What is missing stays visible but quiet. Absent formats collapse into
//    a summary that always states the count — a fabricator must never
//    wonder whether something was silently dropped (Rule 2).

import { useCallback, useState } from "react";
import type { ExportEntry, ExportsResponse } from "../api/client";
import { Copy, Download, PackageCheck } from "lucide-react";

interface ExportPanelProps {
  designId: string | null;
  exports: ExportsResponse | null;
  exporting: boolean;
  onExport: () => void;
}

const TIERS: Array<{
  tier: string;
  title: string;
  blurb: string;
}> = [
  {
    tier: "cad",
    title: "CAD — exact geometry",
    blurb: "Cut, machine and measure from these. Curved surfaces are exact.",
  },
  {
    tier: "mesh",
    title: "Mesh — triangulated",
    blurb: "For viewing and reference only. Never machine from a mesh.",
  },
];

const STATUS_COPY: Record<string, { label: string; hint: string }> = {
  failed: {
    label: "failed",
    hint: "This one threw an error. The message below is the real error — report it.",
  },
  unavailable: {
    label: "unavailable",
    hint: "Needs something that is not installed. The reason says what.",
  },
  impossible: {
    label: "not possible",
    hint: "No open writer exists anywhere. The package explains the workaround.",
  },
};

function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} kB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function FileRow({ row }: { row: ExportEntry }) {
  return (
    <li className="file-row">
      <a className="file-link" href={row.download_url ?? undefined}>
        <span className="file-name">{row.format}</span>
        <span className="file-size">{formatBytes(row.bytes)}</span>
        <Download className="file-icon" size={14} aria-hidden="true" />
        {row.purpose && <span className="file-desc">{row.purpose}</span>}
      </a>
    </li>
  );
}

function MissingRow({ row }: { row: ExportEntry }) {
  const copy = STATUS_COPY[row.status ?? ""] ?? {
    label: row.status ?? "unknown",
  };
  return (
    <li className={`file-row missing row-${row.status ?? "unknown"}`}>
      {/* Deliberately NOT a link. A row that cannot be fetched must not look
          clickable — a dead link is worse than an honest dead end. */}
      <div className="file-link static">
        <span className="file-name">{row.format}</span>
        <span className="file-size file-status">{copy.label}</span>
        {(row.error || row.purpose) && (
          <span className="file-desc">{row.error || row.purpose}</span>
        )}
      </div>
    </li>
  );
}

export default function ExportPanel({
  designId,
  exports,
  exporting,
  onExport,
}: ExportPanelProps) {
  const [copied, setCopied] = useState(false);

  const copyDigest = useCallback(() => {
    const digest = exports?.content_digest;
    if (!digest) return;
    navigator.clipboard
      ?.writeText(digest)
      .then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1600);
      })
      .catch(() => undefined);
  }, [exports]);

  if (!designId) {
    return (
      <div className="panel export-panel">
        <h2>Fabrication package</h2>
        <p className="hint">
          Build an assembly first — there is nothing to export yet.
        </p>
      </div>
    );
  }

  const rows = exports?.exports ?? [];
  const included = rows.filter((r) => r.status === "included");
  const missing = rows.filter(
    (r) => r.status !== "included" && r.format !== "LUXEXCHANGE"
  );
  const failed = missing.filter((r) => r.status === "failed");
  const notPossible = missing.filter((r) => r.status === "impossible");
  const notInstalled = missing.filter((r) => r.status === "unavailable");
  const jobFailed = exports?.last_job?.status === "failed";
  const built = Boolean(exports?.package_built);
  const fileCount = included.filter((r) => r.format !== "LUXEXCHANGE").length;

  return (
    <div className="panel export-panel">
      <h2>
        Fabrication package{" "}
        {built && (
          <span className="badge badge-pass">{fileCount} files</span>
        )}
      </h2>

      {jobFailed && (
        <p className="export-error">
          The last export job failed: {exports?.last_job?.halt_reason}
        </p>
      )}

      {!built ? (
        <>
          <button
            className="rebuild export-primary"
            onClick={onExport}
            disabled={exporting}
          >
            {exporting ? "Building package…" : "Build export package"}
          </button>
          <p className="hint">
            {exporting
              ? "Writing every format and sealing the package. A few seconds."
              : "Writes every format this machine can produce, hashes them, and seals a package you can send to a fabricator."}
          </p>
        </>
      ) : (
        <>
          <a className="package-card" href={exports!.luxexchange_url}>
            <PackageCheck size={20} aria-hidden="true" />
            <span className="package-title">Download LUXEXCHANGE package</span>
            <span className="package-meta">
              .zip · {formatBytes(exports!.package_bytes)} · {fileCount} files ·
              verifier included
            </span>
          </a>

          {exports!.content_digest && (
            <div className="digest-row">
              <span className="digest-label">content digest</span>
              <code title={exports!.content_digest}>
                {exports!.content_digest.slice(0, 16)}…
              </code>
              <button
                type="button"
                className="digest-copy"
                onClick={copyDigest}
                title="Copy the full digest"
              >
                <Copy size={13} /> {copied ? "copied" : "copy"}
              </button>
            </div>
          )}
          <p className="hint">
            The same design always produces the same package. Run{" "}
            <code>python verify_luxexchange.py</code> inside the extracted zip
            to check nothing was altered in transit.
          </p>

          <button
            className="rebuild secondary"
            onClick={onExport}
            disabled={exporting}
          >
            {exporting ? "Rebuilding…" : "Rebuild package"}
          </button>
        </>
      )}

      {built && (
        <details className="individual-files">
          <summary>Individual files ({fileCount})</summary>
          {TIERS.map(({ tier, title, blurb }) => {
          const tierRows = included.filter((r) => r.tier === tier);
          if (tierRows.length === 0) return null;
          return (
            <section className="file-group" key={tier}>
              <h3>
                {title} <span className="group-count">{tierRows.length}</span>
              </h3>
              <p className="group-blurb">{blurb}</p>
              <ul className="file-list">
                {tierRows.map((row) => (
                  <FileRow key={row.format} row={row} />
                ))}
              </ul>
            </section>
          );
          })}
        </details>
      )}

      {failed.length > 0 && (
        <section className="file-group">
          <h3 className="group-fail">
            Failed <span className="group-count">{failed.length}</span>
          </h3>
          <p className="group-blurb">
            These threw an error. That is a bug, not a configuration problem —
            the real message is shown.
          </p>
          <ul className="file-list">
            {failed.map((row) => (
              <MissingRow key={row.format} row={row} />
            ))}
          </ul>
        </section>
      )}

      {notInstalled.length > 0 && (
        <details className="file-group collapsed-group">
          <summary>
            Not included ({notInstalled.length}) — needs something installed
          </summary>
          <ul className="file-list">
            {notInstalled.map((row) => (
              <MissingRow key={row.format} row={row} />
            ))}
          </ul>
        </details>
      )}

      {notPossible.length > 0 && (
        <details className="file-group collapsed-group">
          <summary>
            Not possible ({notPossible.length}) — no open writer exists
          </summary>
          <p className="group-blurb">
            The package ships <code>README_DWG_SKP.txt</code> with the
            workaround, so a fabricator reading the zip offline still knows
            what to do.
          </p>
          <ul className="file-list">
            {notPossible.map((row) => (
              <MissingRow key={row.format} row={row} />
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
