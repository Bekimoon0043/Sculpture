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
    basin_round,
    cascade,
    plinth,
    sculptural_column,
)

PRIMITIVES: dict[str, ModuleType] = {
    module.PRIMITIVE_ID: module
    for module in (cascade, basin_round, plinth, sculptural_column)
}

__all__ = ["PRIMITIVES", "basin_round", "cascade", "plinth", "sculptural_column"]
