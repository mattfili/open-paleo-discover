"""The 10 m feature stack (spec.md §7).

One row per modelling-grid cell, written to Parquet and read by DuckDB. Postgres holds
only the catalog row: a few counties at 10 m is tens of millions of rows by roughly twenty
columns, which Postgres will do slowly and DuckDB will do in a second on a laptop.

Distances come from the **authoritative NHD hydrography**, not from the WhiteboxTools
stream raster. The two are different things: the WBT streams raster is whatever the
`flow_accum_threshold` parameter says is a stream, so distance measured against it would
move every time that knob moved. Rasterising `ref.nhd_flowline` onto the modelling grid
and running a Euclidean distance transform keeps the feature anchored to published
hydrography and is grid-native, so it costs one pass rather than one query per cell.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import geopandas as gpd
import numpy as np
import pandas as pd
import psycopg
import rasterio
import rasterio.features
from scipy.ndimage import distance_transform_edt
from shapely.geometry import box

from midden import PROJECT_CRS
from midden.aoi import Aoi
from midden.config import Settings, settings
from midden.db import fetch_all
from midden.terrain.cog import list_assets

__all__ = ["FEATURE_KINDS", "StackResult", "build_feature_stack", "register_stack"]

#: Raster kinds pulled into the stack, mapped to their column name. Every one is on the
#: modelling grid; detection-grid surfaces are resampled in separately (spec.md §7).
FEATURE_KINDS: dict[str, str] = {
    "hand": "hand_m",
    "slope": "slope_deg",
    "twi": "twi",
    "terrace": "terrace_class",
}

#: Minimum Strahler order for a confluence to count as a habitat node. A junction between
#: two reaches of the same stream is a reach break, not a tributary confluence.
MIN_CONFLUENCE_ORDER = 2


class StackResult(NamedTuple):
    """What one feature-stack build produced."""

    aoi_slug: str
    path: Path
    rows: int
    columns: list[str]


def _load_rasters(
    conn: psycopg.Connection, aoi: Aoi
) -> tuple[dict[str, np.ndarray], dict]:
    """Read every modelling-grid feature raster for an AOI onto one common grid."""
    arrays: dict[str, np.ndarray] = {}
    profile: dict | None = None
    for kind, column in FEATURE_KINDS.items():
        rows = [
            r
            for r in list_assets(conn, aoi_id=aoi.id, kind=kind)
            if r["grid"] == "model"
        ]
        if not rows:
            raise ValueError(
                f"{aoi.slug}: no modelling-grid {kind!r} raster. "
                f"Run `midden terrain run --aoi {aoi.slug} --grid model` first."
            )
        with rasterio.open(rows[0]["path"]) as src:
            band = src.read(1, masked=True)
            if profile is None:
                profile = src.profile.copy()
            elif (src.width, src.height) != (profile["width"], profile["height"]):
                raise ValueError(
                    f"{aoi.slug}: {kind} is {src.width}x{src.height} but the stack grid is "
                    f"{profile['width']}x{profile['height']}. All modelling-grid rasters "
                    f"must share one grid; re-derive the AOI so they come from one DEM."
                )
        arrays[column] = band.filled(np.nan).astype("float32")
    return arrays, profile


def _rasterize(
    frame: gpd.GeoDataFrame, profile: dict, value_column: str | None
) -> np.ndarray:
    """Burn vector features onto the stack grid, as a value or a presence mask."""
    if frame.empty:
        return np.zeros((profile["height"], profile["width"]), dtype="float32")
    shapes = (
        zip(frame.geometry, frame[value_column], strict=True)
        if value_column
        else ((geom, 1) for geom in frame.geometry)
    )
    return rasterio.features.rasterize(
        shapes,
        out_shape=(profile["height"], profile["width"]),
        transform=profile["transform"],
        fill=0,
        all_touched=True,
        dtype="float32",
    )


def _distance_and_nearest(
    presence: np.ndarray, values: np.ndarray | None, resolution_m: float
) -> tuple[np.ndarray, np.ndarray | None]:
    """Euclidean distance to the nearest burnt cell, and optionally that cell's value."""
    empty = presence <= 0
    if empty.all():
        shape = presence.shape
        return np.full(shape, np.nan, "float32"), (
            np.full(shape, np.nan, "float32") if values is not None else None
        )
    if values is None:
        return (
            distance_transform_edt(empty, sampling=resolution_m).astype("float32"),
            None,
        )

    distance, indices = distance_transform_edt(
        empty, sampling=resolution_m, return_indices=True
    )
    nearest = values[tuple(indices)].astype("float32")
    return distance.astype("float32"), nearest


def _hydrography(conn: psycopg.Connection, profile: dict) -> gpd.GeoDataFrame:
    """Read NHD flowlines intersecting the stack footprint."""
    bounds = rasterio.transform.array_bounds(
        profile["height"], profile["width"], profile["transform"]
    )
    rows = fetch_all(
        conn,
        """
        SELECT comid, stream_order, ST_AsText(geom) AS wkt
        FROM ref.nhd_flowline
        WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 26916)
        """,
        bounds,
    )
    return gpd.GeoDataFrame(
        {
            "comid": [r["comid"] for r in rows],
            "stream_order": [r["stream_order"] for r in rows],
        },
        geometry=gpd.GeoSeries.from_wkt([r["wkt"] for r in rows]),
        crs=PROJECT_CRS,
    )


def _confluences(conn: psycopg.Connection, profile: dict) -> gpd.GeoDataFrame:
    """Read confluences that are genuine tributary junctions, not reach breaks."""
    bounds = rasterio.transform.array_bounds(
        profile["height"], profile["width"], profile["transform"]
    )
    rows = fetch_all(
        conn,
        """
        SELECT ST_AsText(geom) AS wkt
        FROM ref.confluence
        WHERE order_minor >= %s
          AND order_minor < order_major
          AND geom && ST_MakeEnvelope(%s, %s, %s, %s, 26916)
        """,
        (MIN_CONFLUENCE_ORDER, *bounds),
    )
    return gpd.GeoDataFrame(
        geometry=gpd.GeoSeries.from_wkt([r["wkt"] for r in rows]), crs=PROJECT_CRS
    )


def _soils(
    conn: psycopg.Connection, profile: dict
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Rasterise SSURGO drainage class and burial risk onto the stack grid.

    Drainage class is a phrase, so it is burnt as an integer code and mapped back to its
    label afterwards; the weight set matches on the label, not the code, so a code shift
    between AOIs cannot silently re-score anything.
    """
    bounds = rasterio.transform.array_bounds(
        profile["height"], profile["width"], profile["transform"]
    )
    rows = fetch_all(
        conn,
        """
        SELECT drainage_class, flood_freq, burial_risk, ST_AsText(geom) AS wkt
        FROM ref.ssurgo_mapunit
        WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 26916)
        """,
        bounds,
    )
    shape = (profile["height"], profile["width"])
    if not rows:
        return (
            np.full(shape, 0, "float32"),
            np.full(shape, 0, "float32"),
            np.full(shape, np.nan, "float32"),
            [],
            [],
        )

    frame = gpd.GeoDataFrame(
        {
            "drainage_class": [r["drainage_class"] for r in rows],
            "flood_freq": [r["flood_freq"] for r in rows],
            "burial_risk": [float(r["burial_risk"] or 0.0) for r in rows],
        },
        geometry=gpd.GeoSeries.from_wkt([r["wkt"] for r in rows]),
        crs=PROJECT_CRS,
    )
    labels = sorted({c for c in frame.drainage_class if c})
    codes = {label: index + 1 for index, label in enumerate(labels)}
    frame["drainage_code"] = frame.drainage_class.map(codes).fillna(0).astype("float32")
    # Same label-coding trick for SSURGO flooding frequency (C1 follow-on): T0 is
    # definitionally the surface that floods, so flood_freq is the soils-anchored
    # signal terrace_class tried and failed to encode ordinally.
    flood_labels = sorted({c for c in frame.flood_freq if c})
    flood_codes = {label: index + 1 for index, label in enumerate(flood_labels)}
    frame["flood_code"] = frame.flood_freq.map(flood_codes).fillna(0).astype("float32")

    return (
        _rasterize(frame, profile, "drainage_code"),
        _rasterize(frame, profile, "flood_code"),
        _rasterize(frame, profile, "burial_risk"),
        labels,
        flood_labels,
    )


def _assemble(
    arrays: dict[str, np.ndarray], profile: dict, aoi: Aoi, clip_to_aoi: bool
) -> pd.DataFrame:
    """Flatten the raster stack into one row per valid cell, with cell centres."""
    height, width = profile["height"], profile["width"]
    rows, cols = np.mgrid[0:height, 0:width]
    xs, ys = rasterio.transform.xy(profile["transform"], rows.ravel(), cols.ravel())

    frame = pd.DataFrame(
        {"easting": np.asarray(xs, "float64"), "northing": np.asarray(ys, "float64")}
    )
    for column, values in arrays.items():
        frame[column] = values.ravel()

    # A cell with no elevation-derived value is outside the computed surface entirely.
    valid = frame[["hand_m", "slope_deg"]].notna().all(axis=1)
    if clip_to_aoi:
        points = gpd.GeoSeries(
            gpd.points_from_xy(frame.easting, frame.northing), crs=PROJECT_CRS
        )
        valid &= points.within(aoi.geom).to_numpy()
    return frame.loc[valid].reset_index(drop=True)


def build_feature_stack(
    conn: psycopg.Connection,
    aoi: Aoi,
    *,
    config: Settings | None = None,
    clip_to_aoi: bool = True,
) -> StackResult:
    """Assemble the 10 m feature stack for one AOI and write it to Parquet.

    Rasters are derived on a buffered extent because HAND needs upslope context, so the
    stack is clipped back to the AOI by default: the buffer exists to make the hydrology
    correct, not to be scored.
    """
    config = config or settings()
    arrays, profile = _load_rasters(conn, aoi)
    resolution_m = abs(profile["transform"].a)

    flowlines = _hydrography(conn, profile)
    order_raster = _rasterize(flowlines, profile, "stream_order")
    dist_stream, nearest_order = _distance_and_nearest(
        order_raster, order_raster, resolution_m
    )
    arrays["dist_to_stream_m"] = dist_stream
    arrays["stream_order_nearest"] = nearest_order

    junctions = _confluences(conn, profile)
    confluence_raster = _rasterize(junctions, profile, None)
    dist_confluence, _ = _distance_and_nearest(confluence_raster, None, resolution_m)
    arrays["dist_to_confluence_m"] = dist_confluence

    drainage_codes, flood_codes, burial, labels, flood_labels = _soils(conn, profile)
    arrays["drainage_code"] = drainage_codes
    arrays["flood_code"] = flood_codes
    arrays["burial_risk"] = burial

    frame = _assemble(arrays, profile, aoi, clip_to_aoi)
    # Codes back to labels: the weight set matches phrases, not integers.
    code_to_label = {float(i + 1): label for i, label in enumerate(labels)}
    frame["drainage_class"] = frame.drainage_code.map(code_to_label)
    flood_to_label = {float(i + 1): label for i, label in enumerate(flood_labels)}
    frame["flood_freq"] = frame.flood_code.map(flood_to_label)
    frame = frame.drop(columns=["drainage_code", "flood_code"])
    if frame.empty:
        raise ValueError(
            f"{aoi.slug}: the feature stack has no valid cells. Either the rasters are "
            f"entirely nodata or the AOI does not intersect them."
        )

    destination = config.parquet_dir / f"{aoi.slug}_{resolution_m:g}m.parquet"
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(destination, index=False, compression="zstd")

    return StackResult(aoi.slug, destination, len(frame), list(frame.columns))


def register_stack(
    conn: psycopg.Connection,
    aoi: Aoi,
    result: StackResult,
    *,
    resolution_m: float = 10.0,
    derivation_id: int | None = None,
) -> int:
    """Catalog a feature stack in derived.feature_stack, returning its id."""
    import json

    frame = pd.read_parquet(result.path, columns=["easting", "northing"])
    footprint = box(
        float(frame.easting.min()) - resolution_m / 2,
        float(frame.northing.min()) - resolution_m / 2,
        float(frame.easting.max()) + resolution_m / 2,
        float(frame.northing.max()) + resolution_m / 2,
    ).wkt
    row = fetch_all(
        conn,
        """
        INSERT INTO derived.feature_stack
            (aoi_id, resolution_m, path, row_count, columns, footprint, derivation_id)
        VALUES (%s, %s, %s, %s, %s::jsonb, ST_GeomFromText(%s, 26916), %s)
        ON CONFLICT (aoi_id, resolution_m) DO UPDATE SET
            path = EXCLUDED.path, row_count = EXCLUDED.row_count,
            columns = EXCLUDED.columns, footprint = EXCLUDED.footprint,
            derivation_id = EXCLUDED.derivation_id, created_at = now()
        RETURNING id
        """,
        (
            aoi.id,
            resolution_m,
            str(result.path.resolve()),
            result.rows,
            json.dumps(result.columns),
            footprint,
            derivation_id,
        ),
    )
    return row[0]["id"]
