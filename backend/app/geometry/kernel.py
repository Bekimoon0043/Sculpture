"""Geometry build context — one deterministic build of one Design Spec's
parameter set (Amendment 1, Rule 5).

GeometryBuild(seed, params) ties together:
  - the run seed (core.seeds.DeterminismContext),
  - the canonical spec_hash: sha256 of canonical JSON (sorted params + seed),
  - the deterministic STEP timestamp: datetime(2026,1,1) + timedelta
    (seconds=seed) — the Amendment-1 lever that makes export_step byte-
    identical for a given (spec, seed) [live-doc confirmed signature,
    ADR-009/ADR-010],
  - the build123d solid itself (via cascade.build_cascade).

Every build is logged with seed + spec_hash (Rule 5: provenance always).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from app.core.seeds import DeterminismContext
from app.geometry.cascade import build_cascade
from app.geometry.registry import CascadeParams

if TYPE_CHECKING:  # avoid importing build123d at module-import time for typing
    from build123d import Solid

log = logging.getLogger("luxuryform.geometry")

#: Fixed epoch for deterministic STEP header timestamps. The timestamp is a
#: function of the seed ONLY — never of the wall clock.
STEP_TIMESTAMP_EPOCH = datetime(2026, 1, 1, 0, 0, 0)


def canonical_spec_json(params: CascadeParams, seed: int) -> str:
    """Canonical JSON of {parameters (sorted), seed} — the reproducible unit."""
    payload = {"parameters": params.canonical_dict(), "seed": seed}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def spec_hash_for(params: CascadeParams, seed: int) -> str:
    """sha256 of the canonical spec JSON."""
    return hashlib.sha256(canonical_spec_json(params, seed).encode("utf-8")).hexdigest()


def step_timestamp_for(seed: int) -> datetime:
    """Deterministic STEP header timestamp derived from the seed alone."""
    return STEP_TIMESTAMP_EPOCH + timedelta(seconds=seed)


class GeometryBuild:
    """One deterministic geometry build: seed + validated params -> solid."""

    def __init__(self, seed: int, params: CascadeParams) -> None:
        self.context = DeterminismContext(seed)  # validates seed is an int
        self.params = params
        self.spec_hash = spec_hash_for(params, seed)
        self.step_timestamp = step_timestamp_for(seed)
        self.solid: Solid | None = None
        self.build_ms: float | None = None

    @property
    def seed(self) -> int:
        return self.context.seed

    def build(self) -> "Solid":
        """Build the cascade solid; measures and records wall-clock build ms.

        The GEOMETRY is fully determined by (params, seed); build_ms is a
        measurement of machine speed, never an input to the geometry.
        """
        t0 = time.perf_counter()
        self.solid = build_cascade(self.params)
        self.build_ms = (time.perf_counter() - t0) * 1000.0
        log.info(
            "geometry build: seed=%d spec_hash=%s tiers=%d build_ms=%.1f",
            self.seed,
            self.spec_hash,
            self.params.tiers,
            self.build_ms,
        )
        return self.solid
