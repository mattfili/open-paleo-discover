"""ArcGIS REST driver: any FeatureServer or MapServer layer.

Covers TNMap, data.nashville.gov, and hydro.nationalmap.gov (spec.md §5's driver table).
The AOI is used as a spatial filter when `scope: aoi`.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from midden import PROJECT_CRS
from midden.aoi import Aoi
from midden.arcgis import ArcGisError, query_layer
from midden.intake.drivers import DriverError, register


@register("arcgis_rest")
def fetch(params: dict, aoi: Aoi | None, dest: Path) -> Path:
    """Query an ArcGIS layer and write the result to a GeoPackage."""
    url = params.get("url")
    if not url:
        raise DriverError("arcgis_rest driver needs a 'url' param naming the layer endpoint.")

    where = params.get("where", "1=1")
    scoped = params.get("scope", "aoi") == "aoi"
    if scoped and aoi is None:
        raise DriverError("arcgis_rest with scope 'aoi' needs an AOI; pass --aoi <slug>.")

    try:
        rows = query_layer(url, where, out_crs=PROJECT_CRS)
    except ArcGisError as exc:
        raise DriverError(str(exc)) from exc

    if not rows:
        raise DriverError(f"{url} returned no features for where={where!r}.")

    frame = gpd.GeoDataFrame(
        [attrs for attrs, _ in rows],
        geometry=[geom for _, geom in rows],
        crs=PROJECT_CRS,
    )
    if scoped and aoi is not None:
        # Clipped client-side: layers used this way are reference layers of modest size,
        # and an envelope filter server-side would still need this to trim to the polygon.
        frame = frame[frame.intersects(aoi.geom)]
        if frame.empty:
            raise DriverError(f"{url}: nothing intersects AOI {aoi.slug}.")

    dest.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(dest, driver="GPKG", layer="data")
    return dest
