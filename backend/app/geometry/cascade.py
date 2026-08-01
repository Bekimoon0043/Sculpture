"""The tiered-cascade primitive — one watertight solid, by construction.

Classic LuxuryCon cascade: round base basin, central column (with plumbing
bore), N stacked dishes of decreasing diameter.

Construction (Rule 6 — watertight BY CONSTRUCTION, never by repair):
  * every element is a solid of revolution: a closed BuildSketch profile in
    the XZ plane revolved 360° about the Z axis;
  * the basin is a tub (outer wall + floor in one profile);
  * each dish is a shallow bowl profile whose lip fillet is drawn INTO the
    profile as a true circular arc (RadiusArc) — the revolved lip is then an
    exact toroidal surface. No fragile post-hoc 3D filleting, so the validated
    parameter ranges never hit a fillet failure (ADR-010);
  * column + dishes + basin are FUSED into one solid;
  * the plumbing bore is cut through the whole stack (a through-hole never
    splits the solid: the column keeps a full wall, enforced by hard
    constraint 4 in registry.py).

Coordinate system: Z up, origin at the centre of the basin's bottom face.
Dish i (0 = top/smallest) has diameter tier_top + i*step and its bottom at
basin_height + (tiers-1-i)*tier_spacing; the widest dish hangs over the basin
interior (hard constraint 1 guarantees the fit).

build123d 0.11.1 API, verified against the installed package (ADR-009).
"""

from __future__ import annotations

from build123d import (
    Axis,
    BuildLine,
    BuildSketch,
    Cylinder,
    Plane,
    Polyline,
    Pos,
    RadiusArc,
    Solid,
    make_face,
    revolve,
)

from app.geometry.registry import CascadeParams


def _revolve_profile(z0: float, draw) -> Solid:
    """Draw a closed XZ-plane profile (local z offset by z0) and revolve it."""
    with BuildSketch(Plane.XZ) as sketch:
        with BuildLine():
            draw(z0)
        make_face()
    return revolve(sketch.sketch, Axis.Z)


def _basin(p: CascadeParams) -> Solid:
    """Tub: outer cylinder wall + floor, one closed profile."""
    R = p.basin_diameter_mm / 2
    H = p.basin_height_mm
    t = p.basin_wall_mm

    def draw(z0: float) -> None:
        Polyline(
            (0, z0),
            (R, z0),
            (R, z0 + H),
            (R - t, z0 + H),
            (R - t, z0 + t),
            (0, z0 + t),
            close=True,
        )

    return _revolve_profile(0.0, draw)


def _dish(p: CascadeParams, index: int) -> Solid:
    """Bowl i: shallow dish with the weir-lip fillet drawn into the profile."""
    diameter = p.tier_top_diameter_mm + index * p.tier_diameter_step_mm
    r = diameter / 2
    D = p.dish_depth_mm
    t = p.basin_wall_mm
    f = p.lip_fillet_mm
    # top dish (index 0) is highest; bottom of dish i:
    z0 = p.basin_height_mm + (p.tiers - 1 - index) * p.tier_spacing_mm

    def draw(base: float) -> None:
        Polyline(
            (0, base),
            (r, base),
            (r, base + D - f),          # outer wall up to the fillet tangent
        )
        # Lip fillet: true circular arc, tangent to outer wall and rim ledge.
        RadiusArc((r, base + D - f), (r - f, base + D), f)
        Polyline(
            (r - f, base + D),
            (r - t, base + D),          # rim ledge (f < t, constraint 5)
            (r - t, base + t),          # inner wall down
            (0, base + t),              # bowl floor
            (0, base),                  # close the profile at the axis
        )

    return _revolve_profile(z0, draw)


def _column(p: CascadeParams) -> Solid:
    """Central column, fused into the basin floor and the top dish."""
    z_top = (
        p.basin_height_mm
        + (p.tiers - 1) * p.tier_spacing_mm
        + p.basin_wall_mm               # flush with the top dish's inner floor
    )
    return Pos(0, 0, z_top / 2) * Cylinder(p.column_diameter_mm / 2, z_top)


def _bore(p: CascadeParams) -> Solid:
    """Plumbing service void through the entire stack (overshot both ends)."""
    z_top = (
        p.basin_height_mm
        + (p.tiers - 1) * p.tier_spacing_mm
        + p.dish_depth_mm
    )
    height = z_top + 2.0                # 1 mm overshot top and bottom
    return Pos(0, 0, z_top / 2) * Cylinder(p.bore_diameter_mm / 2, height)


def build_cascade(params: CascadeParams) -> Solid:
    """Build the full cascade as ONE watertight solid.

    Raises RuntimeError if the fused result is not exactly one solid — a
    construction defect must never ship silently (Rule 6).
    """
    result: Solid = _basin(params)
    result += _column(params)
    for i in range(params.tiers):
        result += _dish(params, i)
    result -= _bore(params)

    solids = result.solids()
    if len(solids) != 1:
        raise RuntimeError(
            f"cascade construction produced {len(solids)} solids, expected 1 — "
            "parameters validated but geometry is not one fused body"
        )
    return solids[0]
