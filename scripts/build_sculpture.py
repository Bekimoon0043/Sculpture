"""Build a sculpture from a hand-authored assembly request, and report honestly.

This is the operator-facing path for a design that was NOT written by the AI
Council: you write the elements and joints yourself (see
``sculptures/entoto_halo/request.json``) and this script drives the real
platform endpoints — it does not re-implement any geometry.

What it does, in order:

1. POST the request to ``/api/geometry/assembly/build``. The kernel validates,
   fuses, exports and persists. A 422 comes back with every violation carrying
   real numbers; this script prints them verbatim and exits non-zero.
2. Print the measured evidence: element masses and placements, the joints and
   their seats, the segmentation result, and the four layered gate statuses.
3. With ``--exports`` also POST ``/{design_id}/exports`` and download the sealed
   LUXEXCHANGE package; with ``--bom`` fetch the BOM (JSON + text).
4. With ``--twice`` build the SAME request a second time and compare the
   canonical STEP digest. Rule 5: identical request + seed + image must give a
   byte-identical STEP. A mismatch is reported as a FAIL, never smoothed over.
5. With ``--project NAME`` group the build under that project, creating the
   project when it does not exist. Grouping is METADATA — ``project_id`` is
   documented in routes_assembly as "never part of the canonical geometry
   payload/spec hash" — so the run prints the id and the spec_hash, and the
   spec_hash must be the same one the ungrouped build produced. This is the
   only way an operator-authored design gets a human name in the viewport:
   the Designer Workspace labels a design by its project, not by a filename.

It never invents a verdict. ``overall_status`` is printed exactly as the
platform returns it, so a ``needs_input`` design reads as ``needs_input`` here
too — the whole point of the layered gates.

Usage (host, stack up):

    python scripts/build_sculpture.py sculptures/entoto_halo/request.json
    python scripts/build_sculpture.py sculptures/entoto_halo/request.json --twice --exports --bom
    python scripts/build_sculpture.py sculptures/entoto_halo/request.json ^
        --project "Entoto Halo" --project-brief "wet plaza fountain, Entoto"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE = "http://localhost:8000"

_STATUS_MARK = {"pass": "ok  ", "warn": "WARN", "fail": "FAIL", "needs_input": "n/a "}


def _post(url: str, payload: dict[str, Any] | None) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except ValueError:
            return exc.code, body


def _get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=900) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _resolve_project(
    base: str, name: str, brief: str
) -> tuple[str | None, str | None]:
    """The project a build may be grouped under, created when it is absent.

    Returns ``(project_id, error)``. Matching is case-insensitive on the
    trimmed name: re-running the same command must reuse the project rather
    than pile up look-alikes. An archived project is refused instead of
    silently reopened — that is the operator's decision, not this script's.
    """
    status, blob = _get(f"{base}/api/geometry/assembly/projects")
    if status != 200:
        return None, f"could not list projects (HTTP {status})"
    wanted = name.strip().casefold()
    for project in json.loads(blob.decode("utf-8"))["projects"]:
        if project["name"].strip().casefold() == wanted:
            if project["status"] != "open":
                return None, (
                    f"project {project['name']!r} is {project['status']}; "
                    f"reopen it with PATCH /api/geometry/assembly/projects/"
                    f"{project['project_id']} ({{'status': 'open'}}) first"
                )
            return project["project_id"], None
    status, created = _post(
        f"{base}/api/geometry/assembly/projects",
        {"name": name.strip(), "brief_text": brief.strip()},
    )
    if status != 201 or not isinstance(created, dict):
        return None, f"could not create project {name!r} (HTTP {status})"
    return created["project_id"], None


def _print_build(build: dict[str, Any]) -> None:
    manifest = build["manifest"]
    print(f"  design_id    {build['design_id']}")
    print(f"  spec_hash    {build['spec_hash']}")
    print(f"  step_sha256  {build['step_sha256']}")
    print(f"  glb_sha256   {build['glb_sha256']}")
    print(f"  build_ms     {build['build_ms']:.0f}")
    print(f"  fused bodies {manifest['body_count_brep']}   "
          f"total mass {manifest['total_mass_kg']:,.1f} kg   "
          f"bbox {[round(v) for v in manifest['assembly_bbox_max_mm']]} mm")

    print("\n  ELEMENTS (each in its own material; nothing apportioned)")
    for element in sorted(manifest["elements"], key=lambda e: e["element_id"]):
        print(f"    {element['element_id']:3} {element['primitive']:18} "
              f"{element['material_id']:22} {element['mass_kg']:9.1f} kg  "
              f"z {element['placement_mm']['z']:8.1f}  "
              f"bbox {[round(v) for v in element['bbox_mm']]}")

    print("\n  JOINTS (real interference, and a real seat)")
    for joint in manifest.get("joints", []):
        print(f"    {joint['child']} -> {joint['parent']:<3} {joint['type']:18} "
              f"overlap {joint['overlap_mm']:5.1f} mm "
              f"(floor {joint['floor_mm']:.1f})  "
              f"intersection {joint['intersection_volume_mm3']:,.0f} mm3")

    segmentation = manifest.get("segmentation") or {}
    modules = sum((segmentation.get("elements") or {})
                  .get(e["element_id"], {}).get("module_count", 1)
                  for e in manifest["elements"])
    print(f"\n  SEGMENTATION  {modules} module(s) — {segmentation.get('basis')}")

    violations = manifest.get("fabrication_limit_violations") or []
    print(f"  LIMIT VIOLATIONS  {len(violations)}")
    for violation in violations:
        print(f"    ! {violation}")

    mesh = build.get("validation") or {}
    print(f"\n  MESH  watertight={mesh.get('watertight')} "
          f"winding={mesh.get('winding_consistent')} "
          f"bodies={mesh.get('body_count')} "
          f"faces={mesh.get('face_count')} "
          f"degenerate={mesh.get('degenerate_face_count')}")
    crosscheck = mesh.get("volume_crosscheck") or {}
    if crosscheck:
        print(f"        volume cross-check delta {crosscheck.get('delta_pct'):.4f}% "
              f"(tolerance {crosscheck.get('tolerance_pct')}%)")


def _print_gates(build: dict[str, Any]) -> None:
    print(f"\n  GATES — overall_status: {build.get('overall_status')}  "
          f"passed: {build.get('passed')}")
    for name, report in (build.get("validation_gates") or {}).items():
        print(f"\n    [{name}] {report.get('status')}")
        for check in report.get("checks", []):
            mark = _STATUS_MARK.get(check["status"], "??  ")
            print(f"      {mark} {check['check']}: value={check.get('value')} "
                  f"limit={check.get('limit')} {check.get('units') or ''}")
            if check["status"] == "needs_input":
                print(f"           missing — {check.get('message')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("request", type=Path, help="assembly request JSON")
    parser.add_argument("--base", default=DEFAULT_BASE, help="API base URL")
    parser.add_argument("--twice", action="store_true",
                        help="build twice and compare the canonical STEP digest")
    parser.add_argument("--exports", action="store_true",
                        help="run the export job and download the package")
    parser.add_argument("--bom", action="store_true",
                        help="fetch the bill of materials (json + text)")
    parser.add_argument("--project", default=None,
                        help="group the build under this project name, "
                             "creating the project when it does not exist "
                             "(metadata only - the spec_hash must not move)")
    parser.add_argument("--project-brief", default="",
                        help="brief text for a project this run creates")
    parser.add_argument("--out", type=Path, default=None,
                        help="directory for captured evidence "
                             "(default data/sculpture_runs/<design_id>)")
    args = parser.parse_args(argv)

    # A Windows console defaults to a legacy code page (GBK here) and this
    # script prints real Unicode (—, ⌀, ·). Without this, a host run dies with
    # UnicodeEncodeError mid-report — the same class of defect gate_phase14 hit.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    payload = json.loads(args.request.read_text(encoding="utf-8"))
    base = args.base.rstrip("/")
    failures: list[str] = []

    project_id: str | None = None
    if args.project:
        project_id, project_error = _resolve_project(
            base, args.project, args.project_brief)
        if project_id is None:
            print(f"RESULT: build not attempted - {project_error}")
            return 1
        # Metadata, not geometry (routes_assembly: project_id is "never part
        # of the canonical geometry payload/spec hash"). The spec_hash this
        # run reports must therefore equal the ungrouped build's.
        payload = {**payload, "project_id": project_id}

    print("=" * 78)
    print(f"BUILD  {args.request}")
    if project_id:
        print(f"PROJECT  {args.project}  ({project_id})  - grouping, not geometry")
    print("=" * 78)
    status, build = _post(f"{base}/api/geometry/assembly/build", payload)
    if status != 200 or not isinstance(build, dict) or "design_id" not in build:
        print(f"  HTTP {status} — the kernel refused this design:\n")
        detail = build.get("detail") if isinstance(build, dict) else build
        print(json.dumps(detail, indent=2))
        return 1

    _print_build(build)
    _print_gates(build)

    if args.twice:
        print("\n" + "=" * 78)
        print("DETERMINISM — build the identical request again (Rule 5)")
        print("=" * 78)
        status2, second = _post(f"{base}/api/geometry/assembly/build", payload)
        same_step = second.get("step_sha256") == build["step_sha256"]
        same_glb = second.get("glb_sha256") == build["glb_sha256"]
        print(f"  run 1 STEP {build['step_sha256']}")
        print(f"  run 2 STEP {second.get('step_sha256')}")
        print(f"  STEP byte-identical: {'YES' if same_step else 'NO'}")
        print(f"  GLB  byte-identical: {'YES' if same_glb else 'NO'}")
        if not same_step:
            failures.append("non-deterministic STEP digest across two builds")

    design_id = build["design_id"]
    out = args.out or Path("data") / "sculpture_runs" / design_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "build.json").write_text(
        json.dumps(build, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\n  evidence written to {out / 'build.json'}")

    if args.exports:
        print("\n" + "=" * 78)
        print("EXPORTS — every format, then the sealed LUXEXCHANGE package")
        print("=" * 78)
        status, exports = _post(
            f"{base}/api/geometry/assembly/{design_id}/exports", None)
        if status != 200:
            print(f"  HTTP {status}: {json.dumps(exports)[:800]}")
            failures.append(f"export job returned HTTP {status}")
        else:
            print(f"  package_class  {exports['package_class']}")
            for reason in exports.get("warrant_reasons") or []:
                print(f"    not warranted: {reason}")
            print(f"  content_digest {exports['content_digest']}")
            print(f"  package_sha256 {exports['package_sha256']}")
            for entry in exports["exports"]:
                print(f"    {entry['format']:<8} {entry['status']:<12} "
                      f"{str(entry.get('bytes') or ''):>9}  "
                      f"{entry.get('sha256') or ''}")
            (out / "exports.json").write_text(
                json.dumps(exports, indent=2, sort_keys=True), encoding="utf-8")

            package_url = (f"{base}/api/geometry/assembly/"
                           f"{design_id}/luxexchange.zip")
            code, blob = _get(package_url)
            if code == 200:
                target = out / "luxexchange_v1.zip"
                target.write_bytes(blob)
                digest = hashlib.sha256(blob).hexdigest()
                ok = digest == exports["package_sha256"]
                print(f"\n  downloaded {len(blob):,} bytes -> {target}")
                print(f"  served file digest "
                      f"{'MATCHES' if ok else 'DIFFERS FROM'} the seal")
                if not ok:
                    failures.append("served package digest differs from the seal")
            else:
                print(f"  package download HTTP {code}")
                failures.append(f"package download returned HTTP {code}")

    if args.bom:
        print("\n" + "=" * 78)
        print("BILL OF MATERIALS")
        print("=" * 78)
        code, blob = _get(f"{base}/api/costing/bom/{design_id}")
        if code == 200:
            bom = json.loads(blob.decode("utf-8"))
            (out / "bom.json").write_bytes(blob)
            print(f"  complete      {bom.get('complete')}")
            print(f"  totals        {json.dumps(bom.get('totals'))}")
            print(f"  cost drivers  {json.dumps(bom.get('drivers'))[:300]}")
            missing = bom.get("missing_rates") or []
            print(f"  missing rates {len(missing)}")
            for path_ in missing:
                print(f"    - {path_}")
            blocked = bom.get("not_computable") or []
            if blocked:
                print(f"  not computable {blocked}")
        else:
            print(f"  HTTP {code}")
            failures.append(f"BOM returned HTTP {code}")
        code, blob = _get(f"{base}/api/costing/bom/{design_id}.txt")
        if code == 200:
            (out / "bom.txt").write_bytes(blob)
            print(f"  text BOM written to {out / 'bom.txt'}")

    print("\n" + "=" * 78)
    if failures:
        print("RESULT: the build ran, but these checks did NOT hold:")
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print(f"RESULT: built and captured. The gate verdict stands exactly as "
          f"reported above ({build.get('overall_status')}) — this script does "
          f"not upgrade it.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
