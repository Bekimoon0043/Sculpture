"""Generate the deterministic gate test image (Amendment 5).

A 256x256 PNG with a seeded geometric pattern, built with Pillow. Same code,
same seed -> same pixels, every run, on every machine. The Phase 1 gate sends
this image to each provider's vision endpoint.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw

SEED = 20260701
SIZE_PX = 256

# Fixed palette — deep blue field, gold ring, white square (dominant: blue).
_BACKGROUND_RGB = (24, 60, 140)
_RING_RGB = (212, 175, 55)
_SQUARE_RGB = (245, 245, 245)


def generate(path: Path) -> Path:
    """Draw the seeded pattern and write the PNG. Returns the path."""
    rng = random.Random(SEED)
    img = Image.new("RGB", (SIZE_PX, SIZE_PX), _BACKGROUND_RGB)
    draw = ImageDraw.Draw(img)

    # Deterministic faint grid (seeded jitter, same every run).
    for i in range(8):
        offset = rng.randint(0, 12)
        xy = 16 + i * 28 + offset
        draw.line([(xy, 0), (xy, SIZE_PX)], fill=(30, 70, 155), width=1)
        draw.line([(0, xy), (SIZE_PX, xy)], fill=(30, 70, 155), width=1)

    # Gold ring centered, white square inside.
    draw.ellipse([48, 48, 208, 208], outline=_RING_RGB, width=10)
    draw.rectangle([96, 96, 160, 160], fill=_SQUARE_RGB)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "assets" / "gate_test_image.png",
        help="output PNG path (default: scripts/assets/gate_test_image.png)",
    )
    args = parser.parse_args()
    out = generate(args.out)
    print(f"wrote {out} ({out.stat().st_size} bytes, {SIZE_PX}x{SIZE_PX}, seed {SEED})")


if __name__ == "__main__":
    main()
