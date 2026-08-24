"""Extract the Blender tarball during the image build.

WHY NOT `tar -xJf`
------------------
python:3.11-slim-trixie ships GNU tar but NOT the `xz` binary, and tar shells
out to xz for .tar.xz. The obvious fix -- add xz-utils -- would mean either
apt (which this image deliberately does not use; see debs.txt) or an
eighteenth pinned deb carried solely to unpack one file at build time.

Python's stdlib already has lzma, and tarfile reads "r:xz" through it. So the
tool is already in the image and the deb list stays at exactly the set the
RENDERER needs at runtime.

Symlinks matter here: Blender ships its bundled libraries (libtbb, libOpenEXR,
libopenvdb, MaterialX ...) as versioned files with symlinked sonames, and the
binary finds them through its RUNPATH. tarfile recreates symlinks and file
modes on extraction, so the executable bit and those links survive -- which is
what a host-side extraction on Windows does NOT manage, and the reason this
runs in the container instead.
"""

from __future__ import annotations

import sys
import tarfile
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit("usage: extract_blender.py <tarball> <dest_dir>")
    tarball, dest = Path(argv[1]), Path(argv[2])
    dest.mkdir(parents=True, exist_ok=True)

    count = 0
    with tarfile.open(tarball, "r:xz") as tar:
        members = []
        for member in tar.getmembers():
            # Equivalent of --strip-components=1: the archive has a single
            # blender-<version>-linux-x64/ top directory we do not want.
            parts = member.name.split("/", 1)
            if len(parts) != 2 or not parts[1]:
                continue
            stripped = parts[1]
            # Refuse anything that would escape dest. A pinned, sha256-checked
            # tarball from blender.org will never contain one, but an
            # extraction routine that cannot say that for certain is a bug
            # waiting for the day the pin changes.
            if stripped.startswith("/") or ".." in Path(stripped).parts:
                raise SystemExit("refusing unsafe path in archive: %s" % member.name)
            member.name = stripped
            members.append(member)
            count += 1
        tar.extractall(path=dest, members=members)

    blender = dest / "blender"
    if not blender.exists():
        raise SystemExit("extraction produced no %s" % blender)
    print("extracted %d entries to %s" % (count, dest), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
