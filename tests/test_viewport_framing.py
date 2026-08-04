"""Viewport framing + panel layout structure checks (ADR-020).

2026-08-04 incident: the viewport rendered an empty grid. Root cause:
build123d's export_gltf declares the XDE length unit and OCCT's glTF writer
converts coordinates to METRES (glTF spec) — the 2600 mm cascade arrived
2.6 units wide, sub-pixel at the hardcoded millimetre camera. The fix:
camera distance/near/far/target, grid, and sun are all derived from the
loaded model's bounding box (scale-independent, Phase-6-proof), plus
ResizeObserver-based renderer sizing. These tests lock that in.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"


def test_framing_module_derives_everything_from_bbox():
    framing = (SRC / "viewport" / "framing.ts").read_text(encoding="utf-8")
    assert "setFromObject" in framing, "framing must measure the loaded model"
    assert "getCenter" in framing and "getSize" in framing
    # distance from bounding sphere + fov, aspect-corrected
    assert "camera.fov" in framing and "camera.aspect" in framing
    assert "camera.near" in framing and "camera.far" in framing, (
        "near/far must be derived from the model, not constants"
    )
    assert "updateProjectionMatrix" in framing
    assert "isEmpty" in framing, (
        "a degenerate/empty load must not produce NaN camera planes"
    )


def test_viewport_frames_on_load_and_logs_proof():
    vp = (SRC / "viewport" / "Viewport.tsx").read_text(encoding="utf-8")
    assert "frameCameraToObject" in vp, "load path must frame from the bbox"
    # operator ask #2: scene children + bbox logged after every load
    assert "console.info" in vp and "scene children" in vp
    assert "bbox size" in vp
    # grid + sun follow the model's real bounds (scale-correct ground/light)
    assert "GridHelper(radius * 6" in vp
    assert "box.min.y" in vp, "grid sits just under the model's lowest point"
    assert "sun.target.position.copy(centre)" in vp
    # renderer sizing follows the CONTAINER, not only the window (the
    # 'destination rect smaller than viewport rect' warning)
    assert "ResizeObserver" in vp
    assert "requestAnimationFrame(onResize)" in vp, (
        "one sizing pass after first layout settles"
    )


def test_param_row_middle_column_fits_its_control():
    css = (SRC / "styles.css").read_text(encoding="utf-8")
    row = re.search(r"\.param-row\s*\{([^}]*)\}", css, re.S)
    assert row, "no .param-row rule"
    assert "grid-template-columns: 1fr auto auto" in row.group(1), (
        "a fixed 110px middle track made the 180px material select overflow "
        "onto its unit label (2026-08-04)"
    )


def test_validation_panel_cannot_clip_verdict_column():
    css = (SRC / "styles.css").read_text(encoding="utf-8")
    assert re.search(r"\.validation-panel\s*\{[^}]*overflow-x:\s*auto", css), (
        "panel must scroll horizontally rather than clip the verdict column"
    )
    assert re.search(r"td\.num\s*\{[^}]*white-space:\s*nowrap", css, re.S), (
        "long numbers stay on one line and scroll instead of stretching "
        "the table past the panel"
    )
    assert "scrollbar-gutter: stable" in css, (
        "scrollbar appearance must not shift/clip the panels"
    )


def test_visual_gate_requires_framed_on_load():
    gate = (ROOT / "docs" / "operator" / "gate_phase2_visual.md").read_text(
        encoding="utf-8"
    )
    flat = re.sub(r"\s+", " ", gate)
    assert "framed to fill the view ON ITS OWN" in flat
    assert "you did not zoom, pan, or hunt for it" in flat


def test_int_fields_normalize_leading_zero_drift():
    """Operator cosmetic report (2026-08-04): the tiers field displayed
    "04" after stepping. Mechanism: Number("04") === 4 equals the current
    state, React's same-value bailout skips the re-render, and the DOM
    keeps the stale string. The fix must normalize the DOM string for
    INTEGER fields — and must NOT touch float fields, where rewriting
    "0." to "0" would eat the decimal point mid-typing."""
    panel = (SRC / "panels" / "CascadePanel.tsx").read_text(encoding="utf-8")
    assert "normalizeIntField" in panel
    assert 'spec.type === "int"' in panel, (
        "normalization must be gated to int fields only"
    )
    guard = panel.split("function normalizeIntField", 1)[1].split("}", 1)[0]
    assert "String(n)" in guard and "e.target.value" in guard
    assert "[-+.eE]$" in guard, (
        "typing intermediates (trailing -, +, ., e) must be left alone"
    )
