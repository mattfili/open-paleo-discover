"""The semantic layer: boring-semantic-layer over Ibis (spec.md §3, §11 M3).

**DuckDB is the single Ibis connection.** spec.md §3 says BSL "federates Postgres +
DuckDB" so that the split is invisible, but Ibis has no cross-backend joins — a Postgres
table and a DuckDB table cannot appear in one query. What does work, and is what makes the
spec's intent true in practice, is DuckDB's postgres_scanner: `ref.*` and `derived.*` are
attached into the DuckDB session with `read_postgres`, and the wide feature matrix is read
from Parquet in the same session. One backend, both stores.

The coupling this adds, stated rather than discovered later: the semantic layer now reads
Postgres *through* DuckDB, so Postgres being down takes BSL down with it. Both are local
to this machine, so that is a cheap price for one query engine instead of two.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

import ibis
from boring_semantic_layer import from_yaml

from midden.config import Settings, settings

__all__ = [
    "POSTGRES_TABLES",
    "SemanticLayer",
    "build_layer",
    "connect_duckdb",
    "load_postgres_tables",
]

#: YAML `table:` alias -> (postgres schema, table). The alias is what `semantic/*.yml`
#: names; keeping the two apart means a model can be repointed at a Parquet stack later
#: without editing the YAML.
POSTGRES_TABLES: dict[str, tuple[str, str]] = {
    "aoi_tbl": ("derived", "aoi"),
    "derivation_tbl": ("derived", "derivation"),
    "raster_asset_tbl": ("derived", "raster_asset"),
    "nhd_flowline_tbl": ("ref", "nhd_flowline"),
    "confluence_tbl": ("ref", "confluence"),
}


class SemanticLayer(NamedTuple):
    """A live semantic layer: the models, the connection, and what could not be loaded."""

    models: dict[str, Any]
    connection: Any
    missing_tables: dict[str, str]

    def model(self, name: str):
        """Return one model by name, or raise listing what exists."""
        try:
            return self.models[name]
        except KeyError:
            raise KeyError(
                f"No semantic model {name!r}. Available: {sorted(self.models) or '(none)'}"
            ) from None


def connect_duckdb(extensions: tuple[str, ...] = ("postgres", "spatial")):
    """Open an in-process DuckDB connection with the extensions this project needs.

    `spatial` is loaded now rather than when the feature stack arrives, because a query
    that touches a geometry column fails without it and the error names the extension
    rather than the cause.
    """
    connection = ibis.duckdb.connect()
    for extension in extensions:
        connection.raw_sql(f"INSTALL {extension}; LOAD {extension};")
    return connection


def load_postgres_tables(
    connection, config: Settings, specs: dict[str, tuple[str, str]] | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Attach Postgres tables into the DuckDB session.

    Returns `(tables, missing)`. A table that does not exist yet is reported rather than
    skipped silently — `ref.confluence` only appears once the confluence SQL has run, and
    a semantic model quietly missing its source is the kind of absence that reads as a
    null result.
    """
    specs = specs or POSTGRES_TABLES
    uri = config.dsn()
    tables: dict[str, Any] = {}
    missing: dict[str, str] = {}
    for alias, (schema, table) in specs.items():
        try:
            tables[alias] = connection.read_postgres(uri, table_name=table, database=schema)
        except Exception as exc:  # noqa: BLE001 - reported per table, not fatal
            missing[alias] = f"{schema}.{table}: {type(exc).__name__}: {exc}"
    return tables, missing


def model_files(semantic_dir: Path) -> list[Path]:
    """Return the semantic YAML files in a directory. Pure."""
    return sorted(semantic_dir.glob("*.yml"))


def build_layer(config: Settings | None = None) -> SemanticLayer:
    """Build the semantic layer from `semantic/*.yml` over the attached tables."""
    config = config or settings()
    connection = connect_duckdb()
    tables, missing = load_postgres_tables(connection, config)

    files = model_files(config.semantic_dir)
    if not files:
        raise FileNotFoundError(
            f"No semantic models in {config.semantic_dir}. "
            f"BSL YAML uses unbound `_.field` syntax, one file per subject area."
        )

    models: dict[str, Any] = {}
    for path in files:
        try:
            models.update(from_yaml(str(path), tables=tables))
        except Exception as exc:
            raise ValueError(
                f"{path}: {type(exc).__name__}: {exc}. "
                f"Attached tables: {sorted(tables)}."
            ) from exc

    return SemanticLayer(models=models, connection=connection, missing_tables=missing)
