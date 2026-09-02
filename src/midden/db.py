"""Postgres access and schema management.

The split here is the one CLAUDE.md asks for: functions that compute a value are separate
from functions that perform I/O. `sql_files()` and `crs_violations()` are pure; everything
that opens a connection is named for the side effect it has.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from midden.config import Settings, settings

__all__ = [
    "OWNED_SCHEMAS",
    "apply_schema",
    "connect",
    "crs_violations",
    "fetch_all",
    "inventory",
    "set_read_only_password",
    "sql_files",
]

#: Geometry columns exempt from the project-CRS rule: they exist to be exported for
#: rendering and are deliberately WGS84.
_WGS84_SUFFIX = "_wgs84"

#: Schemas the project owns. The CRS invariant applies to these and only these.
#:
#: spec.md §3's test queries `geometry_columns` unscoped, which fails on this image for a
#: reason that has nothing to do with our data: the base postgis image installs
#: `postgis_tiger_geocoder`, whose `tiger` schema ships 12 tables in EPSG:4269. They are
#: vendor reference tables we never read and never reproject, so asserting on them would
#: make the most valuable test in the project permanently red.
OWNED_SCHEMAS = ("ref", "derived")


def sql_files(sql_dir: Path) -> list[Path]:
    """Return the numbered DDL files in filename order. Pure."""
    return sorted(sql_dir.glob("[0-9][0-9][0-9]_*.sql"))


@contextmanager
def connect(
    config: Settings | None = None, *, read_only: bool = False
) -> Iterator[psycopg.Connection]:
    """Open a connection, committing on clean exit and rolling back on error.

    `read_only=True` connects as midden_ro, which holds SELECT and nothing else. That is
    the role behind midden_sql (spec.md §9) and behind the mcp-postgis server.
    """
    config = config or settings()
    with psycopg.connect(config.dsn(read_only=read_only), row_factory=dict_row) as conn:
        yield conn


def apply_schema(conn: psycopg.Connection, sql_dir: Path) -> list[str]:
    """Apply every numbered DDL file in order. Returns the names applied.

    The DDL is written to be idempotent, so this is safe to re-run. A file that fails
    aborts the whole call rather than leaving a half-applied schema.
    """
    applied: list[str] = []
    for path in sql_files(sql_dir):
        conn.execute(path.read_text())
        applied.append(path.name)
    if not applied:
        raise FileNotFoundError(f"No numbered .sql files found in {sql_dir}.")
    return applied


def set_read_only_password(conn: psycopg.Connection, config: Settings) -> None:
    """Set the midden_ro password from configuration.

    The DDL creates the role without a password so that no credential is ever written to
    a tracked file. A password cannot be a query parameter, so it is quoted as a literal.
    """
    if not config.midden_ro_password:
        raise ValueError(
            "MIDDEN_RO_PASSWORD is empty. Set it in .env — the read-only role is what "
            "midden_sql and mcp-postgis connect as, and a passwordless login role cannot "
            "be used by either."
        )
    conn.execute(
        sql.SQL("ALTER ROLE {role} PASSWORD {password}").format(
            role=sql.Identifier(config.midden_ro_user),
            password=sql.Literal(config.midden_ro_password),
        )
    )


def fetch_all(conn: psycopg.Connection, query: str, params: Sequence[Any] = ()) -> list[dict]:
    """Run a query and return all rows as dictionaries.

    Empty params are passed as None rather than `()`. psycopg only scans for placeholders
    when parameters are supplied, and a bare `LIKE 'intake.%'` in an otherwise
    parameterless query would otherwise fail with "only '%s', '%b', '%t' are allowed as
    placeholders".
    """
    with conn.cursor() as cur:
        cur.execute(query, params or None)
        return cur.fetchall()


def crs_violations(rows: Sequence[dict]) -> list[dict]:
    """Return the geometry columns that are not in the project CRS. Pure.

    Columns whose name ends in `_wgs84` are exempt: spec.md §3 keeps a WGS84 column only
    on tables that get exported for rendering.
    """
    return [
        row
        for row in rows
        if row["srid"] != 26916 and not row["f_geometry_column"].endswith(_WGS84_SUFFIX)
    ]


def inventory(conn: psycopg.Connection) -> dict[str, list[dict]]:
    """Return a snapshot of extensions, schemas, tables, roles, and geometry columns.

    This is what `midden db check` prints. It is one round trip per category rather than
    one big join because the output is read by a human, not by code.
    """
    return {
        "extensions": fetch_all(
            conn, "SELECT extname, extversion FROM pg_extension ORDER BY extname"
        ),
        "schemas": fetch_all(
            conn,
            "SELECT nspname FROM pg_namespace "
            "WHERE nspname IN ('ref', 'derived') ORDER BY nspname",
        ),
        "tables": fetch_all(
            conn,
            "SELECT schemaname, tablename FROM pg_tables "
            "WHERE schemaname IN ('ref', 'derived') ORDER BY schemaname, tablename",
        ),
        "roles": fetch_all(
            conn,
            "SELECT rolname, rolcanlogin, rolsuper FROM pg_roles "
            "WHERE rolname IN ('midden', 'midden_ro') ORDER BY rolname",
        ),
        "geometry_columns": fetch_all(
            conn,
            "SELECT f_table_schema, f_table_name, f_geometry_column, srid "
            "FROM geometry_columns "
            "WHERE f_table_schema IN ('ref', 'derived') "
            "ORDER BY f_table_schema, f_table_name",
        ),
    }
