"""The intake runner: fetch, transform, load, and record (spec.md §5).

Pure/effectful split: `apply_transforms` and `index_statements` compute; `run_source`
performs the I/O and writes the ledger row.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

import geopandas as gpd
import psycopg
from sqlalchemy import create_engine

from midden import PROJECT_CRS
from midden.aoi import Aoi, get_aoi
from midden.config import Settings, settings
from midden.derivation import cache_key, open_derivation
from midden.intake.drivers import get_driver
from midden.intake.schema import LoadMode, LoadSpec, Source, TransformStep

__all__ = ["IntakeResult", "apply_transforms", "index_statements", "run_source"]


class IntakeResult(NamedTuple):
    """What one intake run did."""

    source: str
    aoi_slug: str | None
    rows: int
    target: str
    cached: bool
    cache_path: Path
    derivation_id: int | None


def apply_transforms(frame: gpd.GeoDataFrame, steps: list[TransformStep]) -> gpd.GeoDataFrame:
    """Apply transform steps in declared order. Pure.

    Order is load-bearing and is the author's, not ours: `select` names pre-`rename`
    columns, and `filter` usually names post-`rename` ones.
    """
    for step in steps:
        frame = _apply_one(frame, step)
    return frame


def _apply_one(frame: gpd.GeoDataFrame, step: TransformStep) -> gpd.GeoDataFrame:
    """Apply a single transform step."""
    if step.op == "reproject":
        return frame.to_crs(step.value["to"])

    if step.op == "select":
        missing = [c for c in step.value if c not in frame.columns]
        if missing:
            raise KeyError(
                f"transform select names columns not present: {missing}. "
                f"Available: {sorted(frame.columns)}"
            )
        return frame[list(step.value)]

    if step.op == "rename":
        missing = [c for c in step.value if c not in frame.columns]
        if missing:
            raise KeyError(
                f"transform rename names columns not present: {missing}. "
                f"Available: {sorted(frame.columns)}"
            )
        return frame.rename(columns=step.value)

    if step.op == "filter":
        before = len(frame)
        out = frame.query(step.value)
        if out.empty and before:
            # Dropping every row is legal but is almost always a mistake in a predicate.
            raise ValueError(
                f"transform filter {step.value!r} removed all {before} rows. "
                f"A source that loads zero rows fails silently downstream."
            )
        return out

    raise ValueError(f"Unknown transform op {step.op!r}.")


def index_statements(load: LoadSpec) -> list[str]:
    """Return CREATE INDEX statements for a load spec. Pure."""
    return [
        f"CREATE INDEX IF NOT EXISTS "
        f"{load.table_name}_{spec.column}_{spec.method}_idx "
        f"ON {load.target} USING {spec.method} ({spec.column})"
        for spec in load.index
    ]


def _prepare_for_load(frame: gpd.GeoDataFrame, load: LoadSpec) -> gpd.GeoDataFrame:
    """Name the geometry column as the load spec requires and assert the CRS."""
    frame = frame.copy()
    if frame.geometry.name != load.geometry_column:
        frame = frame.rename_geometry(load.geometry_column)
    if frame.crs is None:
        raise ValueError(f"{load.target}: transformed frame has no CRS.")
    if frame.crs.to_epsg() != int(PROJECT_CRS.split(":")[1]):
        raise ValueError(
            f"{load.target}: frame is {frame.crs.to_string()}, expected {PROJECT_CRS}. "
            f"Add a reproject step to the source's transform list."
        )
    return frame


def _write_postgis(frame: gpd.GeoDataFrame, load: LoadSpec, config: Settings) -> int:
    """Write the frame to its target table and build the declared indexes."""
    engine = create_engine(config.sqlalchemy_url())
    if_exists = {
        LoadMode.REPLACE: "replace",
        LoadMode.APPEND: "append",
        LoadMode.UPSERT: "append",
    }[load.mode]
    try:
        frame.to_postgis(
            load.table_name, engine, schema=load.schema_name, if_exists=if_exists, index=False
        )
        with engine.begin() as connection:
            for statement in index_statements(load):
                connection.exec_driver_sql(statement)
    finally:
        engine.dispose()
    return len(frame)


def _ledger_params(source: Source, aoi: Aoi | None, key: str) -> dict[str, Any]:
    """Parameters recorded on the derivation row. Pure.

    The underscore-prefixed keys are midden's, not the driver's: they record what the
    fetch was scoped to so two runs are comparable rather than merely different.
    """
    return {
        **source.fetch.params,
        "_cache_key": key,
        "_aoi": aoi.slug if aoi else None,
        "_target": source.load.target,
    }


def _cache_path(source: Source, aoi: Aoi | None, key: str, config: Settings) -> Path:
    """Where a fetch for this (source, AOI, params) combination is cached. Pure."""
    directory = (
        config.repo_root / source.fetch.cache
        if source.fetch.cache
        else config.raw_dir / source.name
    )
    return directory / f"{key[:16]}.gpkg"


def _fetch_transform_load(
    source: Source, aoi: Aoi | None, cache_path: Path, config: Settings, *, cached: bool
) -> int:
    """Do the work: fetch if needed, transform in order, load. Returns rows loaded."""
    if not cached:
        get_driver(source.fetch.driver)(source.fetch.params, aoi, cache_path)
    frame = gpd.read_file(cache_path, layer="data")
    frame = apply_transforms(frame, source.transform)
    frame = _prepare_for_load(frame, source.load)
    return _write_postgis(frame, source.load, config)


def run_source(
    conn: psycopg.Connection,
    source: Source,
    aoi_slug: str | None = None,
    *,
    config: Settings | None = None,
    force: bool = False,
) -> IntakeResult:
    """Run one source end to end and record a derivation row.

    The fetch is cached by content hash of (driver, params, AOI geometry); `force=True`
    re-fetches. The transform and load always re-run, because they are cheap and because a
    changed YAML must be able to take effect without clearing the cache.
    """
    config = config or settings()
    aoi: Aoi | None = get_aoi(conn, aoi_slug) if aoi_slug else None

    key = cache_key(
        source.fetch.driver, source.fetch.params, aoi.geom.wkb if aoi is not None else None
    )
    cache_path = _cache_path(source, aoi, key, config)
    cached = cache_path.exists() and not force

    with open_derivation(
        conn,
        operation=f"intake.{source.name}",
        tool=source.fetch.driver,
        tool_version=_driver_version(source.fetch.driver),
        aoi_id=aoi.id if aoi else None,
        params=_ledger_params(source, aoi, key),
        inputs=[source.fetch.driver],
        key=key,
    ) as derivation_id:
        rows = _fetch_transform_load(source, aoi, cache_path, config, cached=cached)

    return IntakeResult(
        source=source.name,
        aoi_slug=aoi.slug if aoi else None,
        rows=rows,
        target=source.load.target,
        cached=cached,
        cache_path=cache_path,
        derivation_id=derivation_id,
    )


def _driver_version(driver: str) -> str:
    """Best-effort version string for the library behind a driver."""
    import importlib.metadata as meta

    package = {"pynhd": "pynhd", "arcgis_rest": "httpx"}.get(driver)
    if package is None:
        return "unknown"
    try:
        return f"{package} {meta.version(package)}"
    except meta.PackageNotFoundError:
        return "unknown"
