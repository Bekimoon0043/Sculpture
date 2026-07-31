"""Central seed registry for determinism (Rule 5, Amendment 1).

The platform's determinism guarantee, restated verbatim and binding:

"Identical Design Spec + identical seed + pinned Docker image = byte-identical
canonical geometry (STEP + parameter set). Brief → Spec is non-deterministic
by nature; every Spec is therefore persisted permanently as the reproducible
unit of record."

No gate ever tests brief-level reproducibility.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

# The verbatim restatement — printed by gate_phase1.py section 5 and quoted
# in DECISIONS.md (ADR-004). Keep byte-identical in all three places.
DETERMINISM_STATEMENT = (
    "Identical Design Spec + identical seed + pinned Docker image = "
    "byte-identical canonical geometry (STEP + parameter set). "
    "Brief → Spec is non-deterministic by nature; every Spec is therefore "
    "persisted permanently as the reproducible unit of record."
)


@dataclass(frozen=True)
class DeterminismContext:
    """Carries the run seed; derives reproducible random streams by name.

    One context per Design Spec build. Named streams let different subsystems
    (geometry, critique sampling, ...) draw independent randomness that is
    still fully determined by (seed, stream name).
    """

    seed: int

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an integer, got {self.seed!r}")

    def rng(self, stream: str) -> random.Random:
        """A fresh random.Random fully determined by (seed, stream)."""
        if not stream:
            raise ValueError("stream name must be a non-empty string")
        digest = hashlib.sha256(f"{self.seed}:{stream}".encode("utf-8")).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))
