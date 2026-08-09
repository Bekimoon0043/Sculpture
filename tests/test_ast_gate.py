"""AST gate tests (Phase 4) — the static check in front of the sandbox.

Every rejection reason is human-readable and persisted (the operator's
rejection catalogue), so tests assert on reason CONTENT, not just pass/fail.
"""

from __future__ import annotations

from app.geometry.ast_gate import ALLOWED_IMPORT_ROOTS, check_program

GOOD = '''\
"""A passing fabrication program."""
import math
import registry
from build123d import Pos, Rot


def build(spec):
    seed = spec["meta"]["seed"]
    params = {
        "tiers": 3,
        "tier_top_diameter_mm": 600.0,
        "basin_diameter_mm": 2600.0,
        "material_id": "basalt_slab",
    }
    solid, validated = registry.cascade_fountain(params, seed=seed)
    solid = Pos(0, 0, 0) * solid
    _ = math.pi
    return solid, validated.canonical_dict(), seed
'''


def test_good_program_passes():
    assert check_program(GOOD) is None


def test_whitelist_roots_documented():
    assert ALLOWED_IMPORT_ROOTS == {"registry", "build123d", "math"}


def test_import_os_rejected_with_reason():
    src = "import os\n\ndef build(spec):\n    return None, {}, 0\n"
    reason = check_program(src)
    assert reason is not None
    assert "not allowed" in reason and "os" in reason and "line 1" in reason


def test_from_subprocess_import_rejected():
    src = "from subprocess import run\n\ndef build(spec):\n    return None, {}, 0\n"
    reason = check_program(src)
    assert reason is not None and "subprocess" in reason


def test_open_call_rejected():
    src = GOOD.replace('solid = Pos(0, 0, 0) * solid',
                       'open("/etc/passwd")\n    solid = Pos(0, 0, 0) * solid')
    reason = check_program(src)
    assert reason is not None and "open()" in reason


def test_dunder_attribute_access_rejected():
    src = GOOD.replace("return solid",
                       "x = solid.__class__.__subclasses__\n    return solid")
    reason = check_program(src)
    assert reason is not None and "private attribute" in reason


def test_getattr_rejected():
    src = GOOD.replace("return solid",
                       "x = getattr(solid, 'volume')\n    return solid")
    reason = check_program(src)
    assert reason is not None and "getattr()" in reason


def test_export_banned_runner_owns_export():
    src = GOOD.replace("return solid",
                       "export_step(solid, '/tmp/x.step')\n    return solid")
    reason = check_program(src)
    assert reason is not None and "export_step" in reason


def test_missing_build_function_rejected():
    reason = check_program("import registry\n\nx = 1\n")
    assert reason is not None and "def build(spec)" in reason


def test_syntax_error_rejected():
    reason = check_program("def build(spec)\n    return None\n")
    assert reason is not None and "syntax error" in reason


def test_relative_import_rejected():
    src = "from . import sibling\n\ndef build(spec):\n    return None, {}, 0\n"
    reason = check_program(src)
    assert reason is not None and "relative" in reason


def test_private_import_from_allowed_module_rejected():
    src = "from registry import _materials\n\ndef build(spec):\n    return None, {}, 0\n"
    reason = check_program(src)
    assert reason is not None and "private name" in reason
