"""Spatial MCP tools: AOIs, sources, the raster catalog, and reading pixel values."""

from __future__ import annotations

from typing import Annotated, Any

import numpy as np
import rasterio
import rasterio.mask
from pydantic import Field

from midden.aoi import get_aoi, list_aois
from midden.config import settings
from midden.db import connect, fetch_all
from midden.intake.schema import load_all_sources
from midden.terrain.cog import list_assets

READ_ONLY = {"readOnlyHint": True}


def _resolve_raster(conn, aoi_slug: str, kind: str, variant: str | None) -> dict[str, Any]:
    """Find one catalogued raster, or raise naming what is available for that AOI."""
    area = get_aoi(conn, aoi_slug)
    rows = list_assets(conn, aoi_id=area.id, kind=kind)
    if variant is not None:
        rows = [r for r in rows if (r["variant"] or "") == variant]
    if not rows:
        available = sorted({r["kind"] for r in list_assets(conn, aoi_id=area.id)})
        raise ValueError(
            f"No {kind!r} raster for AOI {aoi_slug!r}"
            + (f" with variant {variant!r}" if variant else "")
            + f". Available kinds: {available or '(none)'}. "
            f"Run midden_derive_terrain for this AOI first."
        )
    return rows[0]


def midden_list_aois(
    role: Annotated[
        str | None,
        Field(description="Filter by role: prospect, control_positive, "
                          "control_detection, or shakeout."),
    ] = None,
) -> dict[str, Any]:
    """List areas of interest with their area, role, and boundary source.

    Role decides how an output is read, not how it is computed. control_positive AOIs
    falsify a weight set; control_detection AOIs validate the render chain; a
    shakeout AOI exists for fast iteration and its scores should be ignored.
    """
    with connect() as conn:
        areas = list_aois(conn, role=role)
    return {
        "count": len(areas),
        "aois": [
            {
                "slug": a.slug, "name": a.name, "county_kind": a.kind, "role": a.role,
                "area_km2": round(a.area_km2, 4), "source": a.source,
                "bounds_utm16n": [round(v) for v in a.bounds],
            }
            for a in areas
        ],
    }


def midden_list_sources() -> dict[str, Any]:
    """List the defined intake sources and when each last ran."""
    config = settings()
    sources = load_all_sources(config.sources_dir)
    with connect(config) as conn:
        recent = {
            r["operation"]: r
            for r in fetch_all(
                conn,
                """
                SELECT DISTINCT ON (operation) operation, status, started_at
                FROM derived.derivation WHERE operation LIKE 'intake.%'
                ORDER BY operation, started_at DESC
                """,
            )
        }
    return {
        "sources": [
            {
                "name": name,
                "driver": spec.fetch.driver,
                "target": spec.load.target,
                "last_run": (
                    recent[f"intake.{name}"]["started_at"].isoformat()
                    if f"intake.{name}" in recent else None
                ),
                "last_status": recent.get(f"intake.{name}", {}).get("status", "never run"),
            }
            for name, spec in sources.items()
        ]
    }


def midden_list_rasters(
    aoi: Annotated[str | None, Field(description="Filter by AOI slug.")] = None,
    kind: Annotated[str | None, Field(description="Filter by kind, e.g. openness_pos.")] = None,
) -> dict[str, Any]:
    """List catalogued raster assets, optionally filtered by AOI and kind."""
    with connect() as conn:
        aoi_id = get_aoi(conn, aoi).id if aoi else None
        rows = list_assets(conn, aoi_id=aoi_id, kind=kind)
    return {
        "count": len(rows),
        "rasters": [
            {
                "aoi": r["aoi"], "kind": r["kind"], "grid": r["grid"],
                "resolution_m": r["resolution_m"], "variant": r["variant"] or None,
                "path": r["path"], "derivation_id": r["derivation_id"],
            }
            for r in rows
        ],
    }


def midden_sample_raster(
    aoi: Annotated[str, Field(description="AOI slug.")],
    kind: Annotated[str, Field(description="Raster kind, e.g. hand or openness_pos.")],
    points: Annotated[
        list[list[float]],
        Field(description="Points as [[easting, northing], ...] in EPSG:26916 metres."),
    ],
    variant: Annotated[str | None, Field(description="Sweep variant digest.")] = None,
) -> dict[str, Any]:
    """Read raster values at supplied points.

    Coordinates are EPSG:26916 (NAD83 / UTM 16N) in metres, which is the project CRS
    for everything. Longitude/latitude will silently sample nothing useful.
    """
    with connect() as conn:
        row = _resolve_raster(conn, aoi, kind, variant)
    with rasterio.open(row["path"]) as src:
        sampled = [
            None if v is None or np.isnan(v) else float(v)
            for v in (s[0] for s in src.sample([(p[0], p[1]) for p in points]))
        ]
    return {
        "aoi": aoi, "kind": kind, "crs": "EPSG:26916",
        "samples": [
            {"easting": p[0], "northing": p[1], "value": v}
            for p, v in zip(points, sampled, strict=True)
        ],
    }


def midden_raster_stats(
    aoi: Annotated[str, Field(description="AOI slug.")],
    kind: Annotated[str, Field(description="Raster kind.")],
    clip_to_aoi: Annotated[
        bool,
        Field(description="Clip to the AOI polygon. False uses the whole buffered raster."),
    ] = True,
    variant: Annotated[str | None, Field(description="Sweep variant digest.")] = None,
) -> dict[str, Any]:
    """Zonal statistics for one raster over an AOI.

    Rasters are computed on a buffered extent, because HAND needs upslope context.
    `clip_to_aoi=True` reports the AOI itself; False reports the whole computed area.
    """
    with connect() as conn:
        area = get_aoi(conn, aoi)
        row = _resolve_raster(conn, aoi, kind, variant)

    with rasterio.open(row["path"]) as src:
        if clip_to_aoi:
            band, _ = rasterio.mask.mask(src, [area.geom.__geo_interface__],
                                        crop=True, filled=False)
            band = band[0]
        else:
            band = src.read(1, masked=True)

    values = band.compressed()
    if values.size == 0:
        raise ValueError(
            f"{aoi}/{kind}: no valid cells"
            + (" inside the AOI polygon" if clip_to_aoi else "")
            + ". The raster may be entirely nodata."
        )
    percentiles = np.percentile(values, [2, 25, 50, 75, 98])
    return {
        "aoi": aoi, "kind": kind, "clipped_to_aoi": clip_to_aoi,
        "resolution_m": row["resolution_m"], "grid": row["grid"],
        "valid_cells": int(values.size),
        "nodata_fraction": round(float(band.mask.mean()), 6),
        "min": float(values.min()), "max": float(values.max()),
        "mean": float(values.mean()), "std": float(values.std()),
        "p2": float(percentiles[0]), "p25": float(percentiles[1]),
        "median": float(percentiles[2]), "p75": float(percentiles[3]),
        "p98": float(percentiles[4]),
    }


#: Tools that only read. Marked readOnlyHint so a client can reason about
#: which calls are safe to retry or run speculatively.
READ_TOOLS = (midden_list_aois, midden_list_sources, midden_list_rasters, midden_sample_raster, midden_raster_stats)

#: Tools that fetch from a network service, write rasters, or insert rows.
WRITE_TOOLS = ()


def register(mcp) -> None:
    """Attach this module's tools to a FastMCP server."""
    for tool in READ_TOOLS:
        mcp.tool(tool, annotations=READ_ONLY)
    for tool in WRITE_TOOLS:
        mcp.tool(tool)
