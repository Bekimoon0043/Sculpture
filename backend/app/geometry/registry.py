"""The fabrication registry — the ONLY geometry vocabulary AI-written code
can reach (Phase 4 ADR-026; restructured in Phase 6 slice A1, ADR-032).

registry.py is now a REGISTRY over the primitive library plus the
assembler, no longer a single primitive's home:

  * PRIMITIVES — id -> primitive module (primitives/, one module each,
    shared protocol in primitives/base.py). The prompt surface and spec
    validation derive from this dict, so vocabulary and code cannot drift
    (ADR-026's anti-drift property carries forward).
  * assemble(elements, seed=0, fabrication=None) — declared joints in, ONE
    watertight fused solid + manifest out. The GEOMETRIST declares; trusted
    code performs every transform and boolean (plan §4, ADR-030: with
    build123d out of the AST whitelist, this module is the CEILING on
    geometric capability — a new shape means a new primitive with its own
    envelopes and tests, a deliberate act with a gate).
  * cascade_fountain(params, seed=0) — the Phase 4 primitive call,
    unchanged: the proven fabrication path keeps working verbatim.

The cascade parameter registry (CASCADE_PARAMETERS, CascadeParams,
validate_params, ConstraintViolation) moved to primitives/cascade.py and
primitives/base.py with the primitive; the names are re-exported here
because this module is their public address — for the backend AND for
generated programs.

SECURITY NOTE for future editors: everything importable from this module
is reachable by AI-written code executing in the sandbox. Keep this
module's public surface benign — no file, network, or process access.
"""

from __future__ import annotations

from typing import Any

from app.geometry.assembly import assemble
from app.geometry.primitives import PRIMITIVES
from app.geometry.primitives.base import ConstraintViolation
from app.geometry.primitives.cascade import (
    CASCADE_PARAMETERS,
    CascadeParams,
    validate_params,
)
from app.geometry.spec_mapper import assembly_plan_from_spec, fabrication_limits_from_spec

__all__ = [
    "PRIMITIVES",
    "assemble",
    "assembly_plan_from_spec",
    "fabrication_limits_from_spec",
    "cascade_fountain",
    "CASCADE_PARAMETERS",
    "CascadeParams",
    "ConstraintViolation",
    "validate_params",
]


def cascade_fountain(params: dict[str, Any], seed: int = 0):
    """THE Phase 4 primitive: dict of cascade parameters -> watertight solid.

    Validates ``params`` against the registry (ranges + hard constraints,
    real numbers in every violation) and builds the fused cascade solid.
    Returns ``(solid, validated_params)`` where ``solid`` is a build123d
    Shape and ``validated_params`` is the validated CascadeParams model —
    the runner persists ``validated_params.canonical_dict()`` for lineage.

    Raises ConstraintViolation listing EVERY violated constraint with the
    real computed numbers.
    """
    from app.geometry.kernel import GeometryBuild  # lazy: registry stays
    # importable without the geometry stack installed

    validated = validate_params(params)
    return GeometryBuild(seed, validated).build(), validated
