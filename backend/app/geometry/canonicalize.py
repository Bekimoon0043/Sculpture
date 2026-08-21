"""Byte-canonicalization of exported artifacts — Phase 9A.

Rule 5 says identical spec + seed + pinned image must give byte-identical
output. Two exporters in this image break that on their own, for reasons
that have nothing to do with geometry. Both are fixed here, and both fixes
touch METADATA ONLY — never a coordinate, never a topology reference.

STEP — OCCT's process-global occurrence counter
-----------------------------------------------
Found 2026-08-21 while proving package reproducibility. Exporting the SAME
solid twice inside one Python process gives:

    -#224 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('1','=>[0:1:1:2]','',#5,#27,$);
    +#224 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('2','=>[0:1:1:2]','',#5,#27,$);

OCCT numbers occurrences from a counter that lives for the life of the
PROCESS, not the file. A fresh process always starts at 1, which is why
every gate that ran one build per process saw byte-identical STEP and this
went unnoticed. In the long-running backend it means two builds of the same
Design Spec produce two different `geometry_hash` values — a visible breach
of the determinism guarantee.

The fix renumbers the occurrence ids sequentially from 1 in order of
appearance. Within one file the ids stay unique, which is all they are for.
A file exported first in a fresh process is unchanged, so the canonical
Phase 2 STEP hash (proven cross-machine 2026-08-04) still reproduces
byte-for-byte.

DXF — random GUIDs and a wall-clock stamp
-----------------------------------------
ezdxf writes `$FINGERPRINTGUID` and `$VERSIONGUID` as fresh random GUIDs on
every save, plus a `<version> @ <ISO timestamp>` marker. None of it is
drawing content. Each is replaced with a value derived from the seed, so the
same design always yields the same drawing bytes.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

#: `NEXT_ASSEMBLY_USAGE_OCCURRENCE('<id>', ...` — only the quoted id is touched.
_STEP_OCCURRENCE = re.compile(r"(NEXT_ASSEMBLY_USAGE_OCCURRENCE\(')([^']*)(')")

#: A DXF header variable followed by its group-2 string value.
_DXF_GUID_VAR = re.compile(
    r"(\$(?:FINGERPRINTGUID|VERSIONGUID)\r?\n\s*2\r?\n)\{[0-9A-Fa-f-]{36}\}"
)

#: ezdxf's "1.4.4 @ 2026-08-21T11:31:34.281743+00:00" provenance marker.
_DXF_TOOL_STAMP = re.compile(
    r"(\d+\.\d+\.\d+ @ )\d{4}-\d{2}-\d{2}T[0-9:.]+(?:\+\d{2}:\d{2}|Z)?"
)

#: Wall-clock header variables carried as group-40 Julian dates/durations.
#: Two exports one second apart differ here by ~1e-5 of a day.
_DXF_TIME_VAR = re.compile(
    r"(\$(?:TDCREATE|TDUCREATE|TDUPDATE|TDUUPDATE|TDINDWG|TDUSRTIMER)"
    r"\r?\n\s*40\r?\n)[-+0-9.eE]+"
)


def _julian_date(moment: datetime) -> float:
    """Julian date for a naive UTC datetime, the way DXF stores $TDCREATE."""
    day = moment.toordinal() + 1721424.5
    seconds = (
        moment.hour * 3600 + moment.minute * 60 + moment.second
        + moment.microsecond / 1_000_000.0
    )
    return day + seconds / 86400.0


def canonicalize_step_text(text: str) -> str:
    """Renumber assembly-occurrence ids sequentially from 1.

    Geometry, topology and the header timestamp are untouched.
    """
    counter = {"n": 0}

    def _renumber(match: re.Match[str]) -> str:
        counter["n"] += 1
        return f"{match.group(1)}{counter['n']}{match.group(3)}"

    return _STEP_OCCURRENCE.sub(_renumber, text)


def canonicalize_step_file(path: Path) -> bool:
    """Rewrite a STEP file in place if canonicalization changed it."""
    path = Path(path)
    original = path.read_text(encoding="utf-8", errors="surrogateescape")
    canonical = canonicalize_step_text(original)
    if canonical == original:
        return False
    path.write_text(canonical, encoding="utf-8", errors="surrogateescape", newline="")
    return True


def _seed_guid(seed: int, salt: str) -> str:
    """A stable GUID-shaped string derived from the seed. Not a real UUID v4."""
    digest = hashlib.sha256(f"luxuryform:{salt}:{int(seed)}".encode("utf-8")).hexdigest()
    return (
        f"{{{digest[0:8].upper()}-{digest[8:12].upper()}-{digest[12:16].upper()}"
        f"-{digest[16:20].upper()}-{digest[20:32].upper()}}}"
    )


def canonicalize_dxf_text(text: str, seed: int, timestamp: datetime) -> str:
    """Replace ezdxf's random GUIDs and wall-clock stamp with seed-derived values."""
    counter = {"n": 0}

    def _guid(match: re.Match[str]) -> str:
        counter["n"] += 1
        salt = "dxf%d" % counter["n"]
        return match.group(1) + _seed_guid(seed, salt)

    text = _DXF_GUID_VAR.sub(_guid, text)

    naive = timestamp.replace(tzinfo=None)
    julian = f"{_julian_date(naive):.9f}"
    text = _DXF_TIME_VAR.sub(lambda m: f"{m.group(1)}{julian}", text)

    stamp = naive.isoformat()
    return _DXF_TOOL_STAMP.sub(lambda m: f"{m.group(1)}{stamp}", text)


def canonicalize_dxf_file(path: Path, seed: int, timestamp: datetime) -> bool:
    path = Path(path)
    original = path.read_text(encoding="utf-8", errors="surrogateescape")
    canonical = canonicalize_dxf_text(original, seed, timestamp)
    if canonical == original:
        return False
    path.write_text(canonical, encoding="utf-8", errors="surrogateescape", newline="")
    return True
