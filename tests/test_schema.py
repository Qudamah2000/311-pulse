"""Tests for sql/schema.sql.

pglast wraps PostgreSQL's own parser, so these check the schema's syntax and
structure without a running database. Applying it to a real PostgreSQL
server happens in task 4.
"""

from pathlib import Path

import pytest
from pglast import ast, enums, parse_sql

SCHEMA = Path(__file__).parent.parent / "sql" / "schema.sql"


@pytest.fixture(scope="module")
def statements():
    return [raw.stmt for raw in parse_sql(SCHEMA.read_text(encoding="utf-8"))]


def tables(statements) -> dict[str, ast.CreateStmt]:
    return {
        s.relation.relname: s for s in statements if isinstance(s, ast.CreateStmt)
    }


def constraints(table: ast.CreateStmt) -> list[ast.Constraint]:
    """Table-level constraints plus those declared on individual columns."""
    found = []
    for elt in table.tableElts:
        if isinstance(elt, ast.Constraint):
            found.append(elt)
        elif isinstance(elt, ast.ColumnDef):
            found.extend(elt.constraints or [])
    return found


def references(table: ast.CreateStmt) -> list[str]:
    return [
        c.pktable.relname for c in constraints(table)
        if c.contype == enums.ConstrType.CONSTR_FOREIGN
    ]


def test_creates_the_expected_tables(statements):
    assert set(tables(statements)) == {
        "wards", "divisions", "sections", "request_types", "loads", "requests"
    }


def test_runs_inside_one_transaction(statements):
    kinds = enums.TransactionStmtKind
    assert statements[0].kind == kinds.TRANS_STMT_BEGIN
    assert statements[-1].kind == kinds.TRANS_STMT_COMMIT


def test_every_table_is_created_before_tables_that_reference_it(statements):
    created = []
    for name, table in tables(statements).items():
        for target in references(table):
            assert target in created, f"{name} references {target} before it exists"
        created.append(name)


def test_requests_points_at_every_lookup_table(statements):
    assert set(references(tables(statements)["requests"])) == {
        "loads", "wards", "request_types", "divisions", "sections"
    }


def test_section_and_division_are_checked_as_a_pair(statements):
    fks = [
        c for c in constraints(tables(statements)["requests"])
        if c.contype == enums.ConstrType.CONSTR_FOREIGN
        and c.pktable.relname == "sections"
    ]
    assert [a.sval for a in fks[0].fk_attrs] == ["division_id", "section_id"]


def test_reloads_by_year_have_an_index(statements):
    indexes = [s for s in statements if isinstance(s, ast.IndexStmt)]
    assert any(
        s.relation.relname == "requests"
        and [p.name for p in s.indexParams] == ["source_year"]
        for s in indexes
    )
