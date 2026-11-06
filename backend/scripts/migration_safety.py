"""Find migrations that the previously deployed code may not survive.

A release that fails after migrating is recovered by redeploying the previous
tag on the new schema, which only works while migrations are expand-only. A
migration that drops, renames or tightens something must say so with a
``# contract:`` comment (explaining why it is safe or what to do); the release
workflow then stops instead of redeploying automatically.
"""

import ast
import tokenize
from pathlib import Path

MARKER = "# contract:"
# Applied migrations are never edited, so the rule starts after the last one
# written before it existed.
FIRST_CHECKED_REVISION = "0019"

DESTRUCTIVE_OPS = {
    "drop_column",
    "drop_table",
    "drop_constraint",
    "drop_index",
    "rename_table",
    "alter_column",
}


def has_marker(path: Path) -> bool:
    """True when a real comment starts with the marker (not a docstring or string)."""
    with path.open("rb") as f:
        return any(
            tok.type == tokenize.COMMENT and tok.string.startswith(MARKER)
            for tok in tokenize.tokenize(f.readline)
        )


def contract_reasons(path: Path) -> list[str]:
    """What in ``upgrade()`` breaks old code; empty for an expand-only migration."""
    tree = ast.parse(path.read_text())
    reasons: list[str] = []
    for fn in tree.body:
        if not (isinstance(fn, ast.FunctionDef) and fn.name == "upgrade"):
            continue
        for node in ast.walk(fn):
            if not (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            ):
                continue
            name = node.func.attr
            if name in DESTRUCTIVE_OPS:
                reasons.append(name)
            elif name == "add_column" and _adds_required_column(node):
                reasons.append("add_column NOT NULL without server_default")
            elif name == "execute" and _executes_drop(node):
                reasons.append("execute DROP")
    return reasons


def _adds_required_column(call: ast.Call) -> bool:
    for arg in call.args:
        if not (
            isinstance(arg, ast.Call) and getattr(arg.func, "attr", "") == "Column"
        ):
            continue
        kwargs = {k.arg: k.value for k in arg.keywords}
        nullable = kwargs.get("nullable")
        if (
            isinstance(nullable, ast.Constant)
            and nullable.value is False
            and "server_default" not in kwargs
        ):
            return True
    return False


def _executes_drop(call: ast.Call) -> bool:
    text = ast.unparse(call).upper()
    return "DROP " in text or "RENAME " in text
