"""CI guard: a migration that breaks the previously deployed code must say so."""

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND / "scripts"))

from migration_safety import (  # noqa: E402
    FIRST_CHECKED_REVISION,
    contract_reasons,
    has_marker,
)

VERSIONS = BACKEND / "alembic" / "versions"


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "0099_x.py"
    path.write_text(f"from alembic import op\nimport sqlalchemy as sa\n\n{body}")
    return path


def test_expand_only_migration_is_clean(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "def upgrade():\n"
        "    op.add_column('t', sa.Column('a', sa.String(), nullable=True))\n"
        "    op.add_column('t', sa.Column('b', sa.Integer(), nullable=False, server_default='0'))\n"
        "    op.create_table('u', sa.Column('id', sa.Integer(), nullable=False))\n"
        "\n\ndef downgrade():\n    op.drop_table('u')\n",
    )
    assert contract_reasons(path) == []


@pytest.mark.parametrize(
    "stmt",
    [
        "op.drop_column('t', 'a')",
        "op.drop_table('t')",
        "op.drop_constraint('c', 't')",
        "op.drop_index('i')",
        "op.rename_table('t', 'u')",
        "op.alter_column('t', 'a', nullable=False)",
        "op.add_column('t', sa.Column('a', sa.String(), nullable=False))",
        "op.execute('ALTER TABLE t DROP COLUMN a')",
    ],
)
def test_destructive_statement_is_flagged(tmp_path: Path, stmt: str) -> None:
    path = _write(tmp_path, f"def upgrade():\n    {stmt}\n")
    assert contract_reasons(path)


def test_downgrade_is_ignored(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "def upgrade():\n    pass\n\ndef downgrade():\n    op.drop_column('t', 'a')\n",
    )
    assert contract_reasons(path) == []


def test_new_destructive_migrations_carry_a_contract_marker() -> None:
    unmarked = [
        f"{p.name}: {', '.join(reasons)}"
        for p in sorted(VERSIONS.glob("[0-9]*.py"))
        if p.name[:4] >= FIRST_CHECKED_REVISION
        and (reasons := contract_reasons(p))
        and not has_marker(p)
    ]
    assert not unmarked, (
        "These migrations are not expand-only. If that is intended, add a "
        "'# contract: <why>' comment; the release then needs a manual recovery "
        "plan instead of an automatic redeploy of the previous tag:\n"
        + "\n".join(unmarked)
    )


def test_has_marker_ignores_docstrings_and_strings(tmp_path):
    f = tmp_path / "m.py"
    f.write_text('"""Mentions # contract: here."""\nX = "# contract: no"\n')
    assert not has_marker(f)
    f.write_text("def upgrade():\n    pass  # contract: drops old column\n")
    assert has_marker(f)
