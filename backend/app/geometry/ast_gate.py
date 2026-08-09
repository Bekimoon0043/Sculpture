"""AST gate — the static check every AI-written program passes BEFORE the
sandbox ever sees it (Phase 4, operator-approved plan: "the AST gate before
the sandbox is the right belt-and-braces").

The sandbox (ADR-005: separate container, non-root, no network, read-only
filesystem except one scratch mount, CPU/memory limits, hard timeout) is the
real security boundary. This gate is the belt in front of it: it rejects
programs that should never consume a sandbox run at all, and — per the
operator's 2026-08-09 order — every rejection reason is PERSISTED, building
the catalogue of what the model tried that it was not allowed to do. That
catalogue informs the Phase 6 vocabulary widening.

Contract a generated program must satisfy:
  * parse as Python 3.11;
  * define a top-level ``def build(spec):`` function — the runner passes the
    Design Spec dict and expects ``(solid, params_dict, seed)`` back;
  * import only from the whitelist roots below;
  * never call the banned names below;
  * never touch a dunder/private attribute (``__builtins__``,
    ``__subclasses__`` and friends are the classic sandbox escapes).

The gate returns a HUMAN-READABLE reason string on rejection (persisted in
generated_programs.rejection_reason and fed back to the GEOMETRIST as the
repair digest), ``None`` on pass.
"""

from __future__ import annotations

import ast

#: Import roots a generated program may use. ``registry`` is the fabrication
#: API alias the runner injects (app.geometry.registry) — the ONLY way to
#: reach geometry primitives. build123d for assembly work; math for
#: arithmetic. Nothing else. Phase 6 widens this list deliberately.
ALLOWED_IMPORT_ROOTS = frozenset({"registry", "build123d", "math"})

#: Names a generated program may never call. File/network/process access,
#: dynamic evaluation, and introspection that leads to sandbox escapes.
BANNED_CALLS = frozenset({
    "open", "eval", "exec", "compile", "__import__", "input",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "breakpoint", "exit", "quit", "help",
    # the runner owns export; a program that writes files breaks lineage
    "export_step", "export_gltf", "export_glb", "export_stl", "save",
    "write_text", "write_bytes",
})

#: Attribute names that are never legitimate in generated geometry code.
_BANNED_ATTR_PREFIX = "_"


def _reason(lineno: int, message: str) -> str:
    return f"line {lineno}: {message}"


def check_program(source: str) -> str | None:
    """Return None if the program may run, else the rejection reason."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return _reason(exc.lineno or 0, f"syntax error: {exc.msg}")

    has_build = any(
        isinstance(node, ast.FunctionDef) and node.name == "build"
        for node in tree.body
    )
    if not has_build:
        return (
            "no top-level `def build(spec):` function found — the runner "
            "calls build(spec) and expects (solid, params_dict, seed) back"
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in ALLOWED_IMPORT_ROOTS:
                    return _reason(
                        node.lineno,
                        f"import of {alias.name!r} is not allowed — only "
                        f"{sorted(ALLOWED_IMPORT_ROOTS)} may be imported",
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                return _reason(node.lineno, "relative imports are not allowed")
            root = (node.module or "").split(".", 1)[0]
            if root not in ALLOWED_IMPORT_ROOTS:
                return _reason(
                    node.lineno,
                    f"import from {node.module!r} is not allowed — only "
                    f"{sorted(ALLOWED_IMPORT_ROOTS)} may be imported",
                )
            for alias in node.names:
                if alias.name.startswith(_BANNED_ATTR_PREFIX):
                    return _reason(
                        node.lineno,
                        f"importing private name {alias.name!r} is not allowed",
                    )
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_CALLS:
                return _reason(
                    node.lineno,
                    f"call to {func.id}() is not allowed in generated code",
                )
            if (
                isinstance(func, ast.Attribute)
                and func.attr.startswith(_BANNED_ATTR_PREFIX)
            ):
                return _reason(
                    node.lineno,
                    f"call to private attribute {func.attr!r} is not allowed",
                )
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith(_BANNED_ATTR_PREFIX):
                return _reason(
                    node.lineno,
                    f"access to private attribute {node.attr!r} is not "
                    "allowed (dunder access is the classic sandbox escape)",
                )
    return None
