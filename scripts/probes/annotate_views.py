"""PR-2.5 render annotation (ANALYSIS-ONLY, backend container).

Owner clarification 4 requires every discovery render to carry a visible
identifier and approach name. render_scene.py deliberately renders
neutral clay with no text, so this post-pass stamps a caption strip UNDER
each PNG (the render pixels themselves are untouched) and writes
<view>.annotated.png next to the original. Pillow's built-in bitmap font
is used -- no fontconfig, no font files, ASCII only.

Input: a JSON spec (written by the host orchestrator) listing
{"job_dir": <basename under /render_scratch>, "label": <ascii label>}.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

STRIP_H = 34
VIEWS = ("ortho_front", "ortho_side", "perspective_3q")


def annotate(png_path: Path, label: str) -> Path:
    from PIL import Image, ImageDraw
    img = Image.open(png_path).convert("RGB")
    out = Image.new("RGB", (img.width, img.height + STRIP_H), (18, 18, 18))
    out.paste(img, (0, 0))
    draw = ImageDraw.Draw(out)
    draw.text((8, img.height + 10), label.encode("ascii", "replace")
              .decode("ascii"), fill=(235, 235, 235))
    dst = png_path.with_suffix(".annotated.png")
    out.save(dst, format="PNG")
    return dst


def main(argv) -> int:
    if len(argv) != 3:
        print("usage: annotate_views.py <render_scratch_root> <spec_json>")
        return 2
    root = Path(argv[1])
    spec = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    done = 0
    missing = []
    for job in spec["jobs"]:
        job_dir = root / job["job_dir"]
        for view in VIEWS:
            png = job_dir / ("%s.png" % view)
            if not png.exists():
                missing.append(str(png))
                continue
            annotate(png, "%s | %s" % (job["label"], view))
            done += 1
    print("annotated %d views; %d missing" % (done, len(missing)))
    for m in missing:
        print("  missing: %s" % m)
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
