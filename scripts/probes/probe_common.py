"""Shared helpers for the PR-2.5 discovery probes (ADR-064).

EXECUTION CONTRACT — read before touching:

  * Every module in scripts/probes/ that CONSTRUCTS geometry
    (probe_freeform_*.py, gen_import_fixture.py) is AI-authored
    geometry-generating code and runs ONLY inside the geo-worker sandbox
    (network none, user 1000:1000, read-only fs except /scratch, cpus 1.0,
    mem 2 GB, host-enforced hard timeout). The host orchestrator
    scripts/run_pr25_discovery.py copies these files into the scratch
    mount and launches them with `docker compose run --rm --no-deps
    geo-worker`. They are NEVER imported by tests or gates.
  * validate_freeform.py and annotate_views.py are ANALYSIS-ONLY: they
    open artifacts the sandbox produced; they never construct design
    geometry. ADR-064 permits them in the backend container.
  * This module is imported by both sides, so it must contain NO geometry
    construction — only hashing, canonical serialization and result I/O.

DETERMINISM: no wall-clock values, no RNG, no set/dict-order dependence
ever reaches an artifact byte. Timing may appear in results JSON (which is
never byte-compared); artifact bytes (STEP, canonical OBJ) are the
determinism contract and are hashed and compared across two separate
sandbox processes.

Units: millimetres everywhere. A bare number is a bug (CLAUDE.md rule 6).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

#: One seed for the whole discovery run (date-derived, fixed forever).
DISCOVERY_SEED = 20260902

#: Owner ruling (2026-09-02): primary references are validated at
#: monumental scale. Tag: owner-ruling. NOT measured from any image.
TARGET_HEIGHT_MIN_MM = 3500.0
TARGET_HEIGHT_MAX_MM = 5000.0


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_canonical_obj(path: str | Path, vertices, faces, name: str) -> str:
    """Write a byte-canonical OBJ: fixed header, %.6f vertices in the given
    order, 1-based triangle faces in the given order, LF line endings.

    The caller supplies vertices/faces in a deterministic order; this
    writer adds nothing time- or environment-dependent. Returns sha256.
    """
    lines = ["# luxuryform pr2.5 canonical obj v1", "o %s" % name]
    for v in vertices:
        lines.append("v %.6f %.6f %.6f" % (float(v[0]), float(v[1]), float(v[2])))
    for f in faces:
        lines.append("f %d %d %d" % (int(f[0]) + 1, int(f[1]) + 1, int(f[2]) + 1))
    data = ("\n".join(lines) + "\n").encode("ascii")
    path = Path(path)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def result_entry(fixture: str, approach: str, *, status: str, detail: str,
                 artifacts: dict | None = None, measures: dict | None = None,
                 expected_invalid: bool = False) -> dict:
    """One capability-matrix row. status: 'constructed' | 'failed'.

    'failed' is EVIDENCE, not an error (owner clarification 4): the row
    records the real exception text and the run continues.
    """
    if status not in ("constructed", "failed"):
        raise ValueError("status must be constructed|failed, got %r" % status)
    return {
        "fixture": fixture,
        "approach": approach,
        "status": status,
        "detail": detail,
        "expected_invalid": bool(expected_invalid),
        "artifacts": artifacts or {},
        "measures": measures or {},
    }


def write_results(out_dir: str | Path, probe_name: str, entries: list[dict],
                  notes: list[str]) -> Path:
    """Atomic, key-sorted results JSON for one probe run."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "probe": probe_name,
        "seed": DISCOVERY_SEED,
        "entries": entries,
        "notes": notes,
    }
    path = out_dir / ("%s.results.json" % probe_name)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True),
                   encoding="utf-8")
    os.replace(tmp, path)
    return path
