"""Cloud-Optimized GeoTIFF output and the raster catalog (spec.md §4).

Rasters live on disk as COGs; only their metadata lives in Postgres. That gives spatial
indexing on "which rasters cover this AOI" without putting pixels in the database, and it
lets QGIS read them windowed with overviews and no tile server (spec.md §8).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import psycopg
import rasterio
import rasterio.shutil
from shapely.geometry import box

from midden import PROJECT_CRS
from midden.db import fetch_all

__all__ = ["RasterInfo", "describe", "register_asset", "write_cog"]

_EPSG = int(PROJECT_CRS.split(":")[1])


class RasterInfo:
    """Summary of a raster on disk, read once."""

    __slots__ = (
        "bounds",
        "crs_epsg",
        "height",
        "nodata",
        "path",
        "resolution_m",
        "width",
    )

    def __init__(self, path: Path) -> None:
        with rasterio.open(path) as src:
            self.path = Path(path)
            self.crs_epsg = src.crs.to_epsg() if src.crs else None
            self.resolution_m = abs(src.transform.a)
            self.bounds = tuple(src.bounds)
            self.width, self.height = src.width, src.height
            self.nodata = src.nodata

    def __repr__(self) -> str:
        return (
            f"RasterInfo({self.path.name}, EPSG:{self.crs_epsg}, "
            f"{self.resolution_m:g} m, {self.width}x{self.height})"
        )


def describe(path: Path) -> RasterInfo:
    """Read a raster's grid metadata."""
    return RasterInfo(path)


def write_cog(src: Path, dest: Path, *, overwrite: bool = True) -> Path:
    """Rewrite a GeoTIFF as a Cloud-Optimized GeoTIFF with overviews.

    GDAL's COG driver builds the overviews and the internal tiling itself, so this is a
    single copy rather than a build-overviews-then-copy dance.

    Integer rasters get a predictor; floating-point ones do not. WhiteboxTools panics on
    float predictors after exiting 0, and while today's chains feed WBT only from
    scratch intermediates, a catalogued COG must stay safe to hand to any consumer.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        return dest
    with rasterio.open(src) as probe:
        is_float = np.issubdtype(np.dtype(probe.dtypes[0]), np.floating)
    rasterio.shutil.copy(
        str(src),
        str(dest),
        driver="COG",
        compress="DEFLATE",
        predictor="NO" if is_float else "YES",
        overview_resampling="average",
        blocksize=512,
    )
    return dest


def register_asset(
    conn: psycopg.Connection,
    *,
    aoi_id: int,
    kind: str,
    grid: str,
    path: Path,
    derivation_id: int | None = None,
    variant: str = "",
) -> int:
    """Insert or refresh a raster_asset row, returning its id.

    Resolution and footprint are read from the file rather than passed in, so the catalog
    cannot drift from what is actually on disk — which is what `test_dem_units.py` asserts.
    """
    info = describe(path)
    if info.crs_epsg != _EPSG:
        raise ValueError(
            f"{path}: CRS is EPSG:{info.crs_epsg}, expected {PROJECT_CRS}. "
            f"Register only reprojected rasters; WhiteboxTools will not reproject and "
            f"will treat degrees as metres."
        )

    footprint = box(*info.bounds).wkt
    row = fetch_all(
        conn,
        """
        INSERT INTO derived.raster_asset
            (aoi_id, kind, grid, resolution_m, variant, path, footprint, derivation_id)
        VALUES (%s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 26916), %s)
        ON CONFLICT (aoi_id, kind, resolution_m, variant) DO UPDATE SET
            grid = EXCLUDED.grid,
            path = EXCLUDED.path,
            footprint = EXCLUDED.footprint,
            derivation_id = EXCLUDED.derivation_id,
            created_at = now()
        RETURNING id
        """,
        (
            aoi_id,
            kind,
            grid,
            info.resolution_m,
            variant,
            str(path.resolve()),
            footprint,
            derivation_id,
        ),
    )
    return row[0]["id"]


def list_assets(
    conn: psycopg.Connection, aoi_id: int | None = None, kind: str | None = None
) -> list[dict[str, Any]]:
    """Return catalog rows, optionally filtered by AOI and kind."""
    clauses, params = [], []
    if aoi_id is not None:
        clauses.append("a.aoi_id = %s")
        params.append(aoi_id)
    if kind is not None:
        clauses.append("a.kind = %s")
        params.append(kind)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return fetch_all(
        conn,
        f"""
        SELECT a.id, o.slug AS aoi, a.kind, a.grid, a.resolution_m, a.variant,
               a.path, a.derivation_id, a.created_at
        FROM derived.raster_asset a
        JOIN derived.aoi o ON o.id = a.aoi_id
        {where}
        ORDER BY o.slug, a.kind, a.resolution_m, a.variant
        """,
        params,
    )
