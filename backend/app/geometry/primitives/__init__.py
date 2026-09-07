"""The primitive library (Phase 6, ADR-032).

One module per primitive, each exposing the protocol documented in
primitives/base.py. PRIMITIVES is the single id -> module registry the
platform reads: registry.assemble, the prompt surface (A2) and the
spec validator all derive from it — nothing lists primitives twice.

Slice A1 ships the assembly core + three revolved masses beside the
existing cascade; slices B-D widen this dict deliberately, one gated
slice at a time (PHASE_6_PLAN.md §2).
"""

from __future__ import annotations

from types import ModuleType

from app.geometry.primitives import (
    basin_rect,
    basin_round,
    blade_fin_array,
    cascade,
    freeform_loop,
    lotus_petal_array,
    plinth,
    sculptural_column,
    stepped_monolith,
    torus_ring,
    water_wall,
)

PRIMITIVES: dict[str, ModuleType] = {
    module.PRIMITIVE_ID: module
    for module in (
        cascade, basin_round, plinth, sculptural_column,          # A1
        basin_rect, stepped_monolith, water_wall, torus_ring,     # C1
        blade_fin_array, lotus_petal_array,                       # C1 arrays
        freeform_loop,                                            # FF-A2
    )
}

__all__ = [
    "PRIMITIVES", "basin_rect", "basin_round", "blade_fin_array", "cascade",
    "freeform_loop", "lotus_petal_array", "plinth", "sculptural_column",
    "stepped_monolith", "torus_ring", "water_wall",
]
