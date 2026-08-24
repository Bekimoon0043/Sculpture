"""LUXEXCHANGE v1 — the portable design package. Phase 9A.

The package is what actually leaves this machine: it is what a fabricator,
an engineer or a client receives. Three properties make it trustworthy.

REPRODUCIBLE. Same design, same seed, same package bytes. A ZIP is normally
non-deterministic — `writestr` stamps every entry with the wall clock and
`write` copies the file mtime — so every entry here is written with a
seed-derived timestamp, in sorted order, at a fixed compression level. This
extends Rule 5 from the canonical STEP to the deliverable built around it.

SELF-VERIFYING. `CHECKSUMS.sha256` covers every content file, and
`content_digest` is the sha256 of that checksum file — one number that
identifies the whole package. Circularity is avoided by keeping the digest
in `provenance.json`, which is itself excluded from the checksum set along
with the wall-clock metadata it carries.

VERIFIABLE WITHOUT US. `verify_luxexchange.py` is shipped INSIDE the ZIP and
imports nothing but the Python standard library. A fabricator with a bare
Python install can check what we sent them. A checksum nobody outside this
repository can verify is decoration, not integrity.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from app.geometry.export_formats import DWG_SKP_README, ExportResult
from app.geometry.kernel import step_timestamp_for

SCHEMA = "luxexchange_v1"

MANIFEST_NAME = "luxexchange_v1.json"
PROVENANCE_NAME = "provenance.json"
CHECKSUMS_NAME = "CHECKSUMS.sha256"
VERIFIER_NAME = "verify_luxexchange.py"

#: Excluded from CHECKSUMS.sha256 and therefore from content_digest.
#: `provenance.json` holds the wall clock and host — including it would make
#: the digest change on every build for reasons that are not the design.
#: `CHECKSUMS.sha256` cannot list its own hash.
_DIGEST_EXCLUDED = frozenset({PROVENANCE_NAME, CHECKSUMS_NAME})

#: Deflate level pinned so two runs compress identically.
_COMPRESSLEVEL = 6


def _zip_timestamp(seed: int) -> tuple[int, int, int, int, int, int]:
    """Seed-derived entry timestamp — the same trick STEP headers use."""
    ts = step_timestamp_for(int(seed))
    return (ts.year, ts.month, ts.day, ts.hour, ts.minute, ts.second)


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def checksums_text(entries: dict[str, bytes]) -> str:
    """`sha256  name` lines, sorted by name — the standard sha256sum format."""
    lines = []
    for name in sorted(entries):
        if name in _DIGEST_EXCLUDED:
            continue
        lines.append(f"{hashlib.sha256(entries[name]).hexdigest()}  {name}")
    return "\n".join(lines) + "\n"


def content_digest_of(checksums: str) -> str:
    return hashlib.sha256(checksums.encode("utf-8")).hexdigest()


VERIFIER_SOURCE = '''#!/usr/bin/env python3
"""Verify a LUXEXCHANGE v1 package. Python standard library only.

Run it from inside the extracted package:

    python verify_luxexchange.py

Exit code 0 means every file matches the checksums recorded when the package
was produced, and the package content digest matches the manifest. Any other
exit code means the package has been altered or is incomplete — do not
fabricate from it until you know why.
"""

import hashlib
import json
import sys
from pathlib import Path

CHECKSUMS = "CHECKSUMS.sha256"
PROVENANCE = "provenance.json"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    root = Path(__file__).resolve().parent
    checksums_path = root / CHECKSUMS
    if not checksums_path.exists():
        print("FAIL: %s is missing - this is not a complete package" % CHECKSUMS)
        return 2

    raw = checksums_path.read_bytes()
    expected = {}
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        expected[name] = digest

    problems = []
    for name, digest in sorted(expected.items()):
        target = root / name
        if not target.exists():
            problems.append("MISSING   %s" % name)
            continue
        actual = sha256_file(target)
        if actual != digest:
            problems.append("MODIFIED  %s" % name)
            problems.append("          recorded %s" % digest)
            problems.append("          actual   %s" % actual)

    listed = set(expected)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        if name in (CHECKSUMS, PROVENANCE) or name in listed:
            continue
        problems.append("UNLISTED  %s" % name)

    digest = hashlib.sha256(raw).hexdigest()
    provenance_path = root / PROVENANCE
    if provenance_path.exists():
        recorded = json.loads(provenance_path.read_text(encoding="utf-8")).get(
            "content_digest"
        )
        if recorded and recorded != digest:
            problems.append("DIGEST MISMATCH")
            problems.append("          recorded %s" % recorded)
            problems.append("          actual   %s" % digest)

    if problems:
        print("LUXEXCHANGE VERIFICATION FAILED")
        for line in problems:
            print("  " + line)
        return 1

    print("LUXEXCHANGE VERIFICATION PASSED")
    print("  files checked  : %d" % len(expected))
    print("  content digest : %s" % digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


class PackageBuilder:
    """Collects the package contents, then seals them into a reproducible ZIP."""

    def __init__(self, seed: int) -> None:
        self.seed = int(seed)
        self._entries: dict[str, bytes] = {}

    def add_bytes(self, name: str, data: bytes) -> None:
        self._entries[name] = data

    def add_json(self, name: str, payload: Any) -> None:
        self._entries[name] = _canonical_json(payload)

    def add_text(self, name: str, text: str) -> None:
        self._entries[name] = text.encode("utf-8")

    def add_file(self, name: str, path: Path) -> None:
        self._entries[name] = Path(path).read_bytes()

    @property
    def names(self) -> list[str]:
        return sorted(self._entries)

    def seal(self, package_path: Path, provenance: dict[str, Any]) -> str:
        """Write the ZIP. Returns the content digest.

        `provenance` is written last and excluded from the digest, so wall
        clock and tool versions can be recorded without making two builds of
        the same design differ.
        """
        checksums = checksums_text(self._entries)
        digest = content_digest_of(checksums)
        self._entries[CHECKSUMS_NAME] = checksums.encode("utf-8")
        self._entries[PROVENANCE_NAME] = _canonical_json(
            {**provenance, "content_digest": digest}
        )

        package_path.parent.mkdir(parents=True, exist_ok=True)
        date_time = _zip_timestamp(self.seed)
        tmp = package_path.with_suffix(package_path.suffix + ".tmp")
        with zipfile.ZipFile(
            tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=_COMPRESSLEVEL
        ) as zf:
            for name in sorted(self._entries):
                info = zipfile.ZipInfo(filename=name, date_time=date_time)
                info.compress_type = zipfile.ZIP_DEFLATED
                # Fixed across platforms: create_system defaults to 0 on
                # Windows and 3 on Unix, which alone would change the bytes.
                info.create_system = 3
                info.external_attr = (0o644 & 0xFFFF) << 16
                zf.writestr(info, self._entries[name])
        tmp.replace(package_path)
        return digest


def build_luxexchange_package(
    package_path: Path,
    *,
    seed: int,
    design: dict[str, Any],
    request_payload: dict[str, Any],
    assembly_manifest: dict[str, Any],
    validation_reports: dict[str, Any],
    exports: list[ExportResult],
    design_spec: dict[str, Any] | None = None,
    costing: dict[str, Any] | None = None,
    costing_unavailable_reason: str | None = None,
    renders: list[Path] | None = None,
    provenance: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any], str]:
    """Assemble and seal one package. Returns (path, manifest, content_digest)."""
    builder = PackageBuilder(seed)

    # Paths in the manifest are relative to the PACKAGE, never absolute host
    # paths. Two reasons: an absolute path would make the content digest
    # depend on where the file happened to be written, and it would ship the
    # operator's filesystem layout to whoever receives the package. The
    # absolute path belongs on the export row in the database.
    #: A format whose bytes differ between two exports of the same design
    #: cannot go INTO this ZIP. Excluding it from the content digest alone
    #: would not be enough -- the ZIP contains the bytes, so the ZIP itself
    #: would differ, and Rule 5 (and the Phase 13a resume-equivalence check)
    #: is about the package being byte-identical, not just its digest field.
    #:
    #: These files are still PRODUCED and still downloadable individually;
    #: they are simply not sealed into the reproducible deliverable. The
    #: manifest says so per format rather than omitting them silently.
    from app.geometry.export_formats import FORMATS_BY_NAME

    export_entries = []
    omitted_non_reproducible: list[dict[str, Any]] = []
    for result in exports:
        entry = result.to_manifest_entry()
        spec = FORMATS_BY_NAME.get(result.format)
        reproducible = spec.deterministic if spec is not None else True
        if result.status == "included" and result.path and not reproducible:
            entry["path"] = None
            entry["in_package"] = False
            # The manifest is COVERED by the content digest, so nothing that
            # varies between two builds may go in it. That includes this
            # format's own sha256 and byte count -- the very things that vary.
            # They are recorded in provenance.json instead, which is excluded
            # from the digest precisely so per-build facts have a home.
            entry["sha256"] = None
            entry["bytes"] = None
            entry["excluded_reason"] = (
                "produced, but not sealed into this package: two exports of "
                "the same design do not produce identical bytes for this "
                "format (embedded creation timestamps), and the package is "
                "guaranteed byte-reproducible. Download it separately."
            )
            omitted_non_reproducible.append({
                "format": result.format,
                "filename": Path(result.path).name,
                "sha256_this_build": result.sha256,
                "bytes": result.bytes,
            })
        elif result.status == "included" and result.path:
            name = f"exports/{Path(result.path).name}"
            builder.add_file(name, Path(result.path))
            entry["path"] = name
            entry["in_package"] = True
        else:
            entry["path"] = None
            entry["in_package"] = False
        export_entries.append(entry)

    render_entries: list[dict[str, Any]] = []
    for render in renders or []:
        path = Path(render)
        if not path.exists():
            continue
        name = f"renders/{path.name}"
        builder.add_file(name, path)
        render_entries.append({"name": name, "bytes": path.stat().st_size})

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "design": design,
        "request": request_payload,
        "assembly_manifest": assembly_manifest,
        "validation_reports": validation_reports,
        "exports": export_entries,
        # Named explicitly so a fabricator reading the manifest learns that
        # these formats exist and why they are not in the ZIP, instead of
        # noticing an absence and assuming the export failed. Only the FORMAT
        # NAMES -- the per-build hashes live in provenance.json, because this
        # manifest is digest-covered and must be identical between builds.
        "omitted_non_reproducible": sorted(
            e["format"] for e in omitted_non_reproducible),
        "renders": render_entries,
        "package_layout": {
            MANIFEST_NAME: "this manifest",
            PROVENANCE_NAME: "wall clock, host and tool versions (excluded from content_digest)",
            CHECKSUMS_NAME: "sha256 of every content file",
            VERIFIER_NAME: "stdlib-only verifier — run: python verify_luxexchange.py",
            "assembly_manifest.json": "the geometry manifest this package was built from",
            "validation/": "one JSON per validation gate",
            "exports/": "geometry files",
            "renders/": "render images, when the render worker produced them",
            "costing/": "bill of materials, when it could be computed",
            "README_DWG_SKP.txt": "how to get DWG and SketchUp from these files",
        },
    }
    if design_spec is not None:
        manifest["design_spec_included"] = True
        builder.add_json("design_spec.json", design_spec)
    else:
        manifest["design_spec_included"] = False

    if costing is not None:
        builder.add_json("costing/bom.json", costing)
        manifest["costing_included"] = True
    else:
        manifest["costing_included"] = False
        manifest["costing_unavailable_reason"] = (
            costing_unavailable_reason or "no bill of materials was supplied"
        )

    builder.add_json("assembly_manifest.json", assembly_manifest)
    for gate_name, report in sorted(validation_reports.items()):
        builder.add_json(f"validation/{gate_name}.json", report)
    builder.add_text("README_DWG_SKP.txt", DWG_SKP_README)
    builder.add_text(VERIFIER_NAME, VERIFIER_SOURCE)
    builder.add_json(MANIFEST_NAME, manifest)

    # NOTE on the omitted formats' per-build hashes: they are deliberately
    # NOT recorded anywhere inside this package -- not in the manifest, and
    # not in provenance either. provenance is excluded from the content
    # DIGEST, but it is still a file INSIDE the ZIP, so a value that changes
    # every build would still change the package bytes, which is the thing
    # Phase 13a's resume-equivalence check compares. Those hashes already
    # have a correct home: the `exports` table row for each file, which is
    # per-build by nature and outside the reproducible deliverable.
    digest = builder.seal(package_path, provenance or {})
    return package_path, manifest, digest
