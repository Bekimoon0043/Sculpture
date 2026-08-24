"""Compose the four canonical views into one image for the vision critique.

WHY ONE IMAGE AND NOT FOUR
--------------------------
The critique judges proportion, silhouette and composition, and every one of
those judgements is COMPARATIVE: is the bowl too wide *for* the plinth, does
the elevation agree with the plan. A model shown four separate images has to
hold three of them in memory to answer; shown a contact sheet it can look.

There is a second, more practical reason. `AIProvider.vision()` takes exactly
one image, and that path is the one wired through `app.ai.call_log` — the
pre-dispatch budget check, the real-token cost calculation, and the `ai_calls`
audit row that Rule 8 requires of every AI call. Extending the provider layer
to take a list would mean touching per-provider image token accounting on the
way to the same result. Compositing costs one PIL call and leaves the audited
path exactly as it was proven.

It is also cheaper: one image at 2x the linear size costs far fewer tokens
than four images at 1x, because each image carries its own fixed overhead.
"""

from __future__ import annotations

from pathlib import Path

#: Order matters -- it is the order a person reads a drawing sheet, and the
#: labels tell the model which projection it is looking at. Without labels a
#: model will confuse the plan with the elevation and propose a delta on the
#: wrong axis.
SHEET_ORDER = ("front", "side", "top", "three_quarter")

#: Gap between tiles and the band under each one, in pixels at tile scale.
GUTTER = 8
LABEL_H = 26


def build_contact_sheet(views: dict[str, Path], out_path: Path,
                        order: tuple[str, ...] = SHEET_ORDER) -> Path:
    """Compose `views` into a labelled 2x2 sheet at `out_path`.

    `views` maps view name -> PNG path, as returned by RenderResult.views.
    Views not present in `order` are ignored; missing ones leave an empty
    tile rather than shifting the others, so the layout is stable between
    rounds and the model does not see the sheet rearrange itself.
    """
    from PIL import Image, ImageDraw

    present = [name for name in order if name in views]
    if not present:
        raise ValueError("no known views to compose; got %s" % sorted(views))

    with Image.open(views[present[0]]) as first:
        tile_w, tile_h = first.size

    cols, rows = 2, 2
    sheet_w = cols * tile_w + (cols + 1) * GUTTER
    sheet_h = rows * (tile_h + LABEL_H) + (rows + 1) * GUTTER

    sheet = Image.new("RGB", (sheet_w, sheet_h), (24, 24, 26))
    draw = ImageDraw.Draw(sheet)

    for index, name in enumerate(order):
        col, row = index % cols, index // cols
        x = GUTTER + col * (tile_w + GUTTER)
        y = GUTTER + row * (tile_h + LABEL_H + GUTTER)
        if name in views:
            with Image.open(views[name]) as img:
                sheet.paste(img.convert("RGB"), (x, y))
        # The label sits UNDER the tile, never over it: text on top of the
        # render is something the critique would try to interpret as part of
        # the design.
        draw.text((x + 4, y + tile_h + 6), name.replace("_", " ").upper(),
                  fill=(210, 210, 214))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, format="PNG")
    return out_path


__all__ = ["build_contact_sheet", "SHEET_ORDER"]
