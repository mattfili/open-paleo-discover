"""SSURGO soils via USDA Soil Data Access (spec.md §6, the `sda_rest` driver).

SDA takes raw T-SQL over a REST endpoint. Three things about it are not obvious and each
one costs a five-minute timeout to learn:

1. `STIntersects` against the national `mupolygon` table has no usable index path and
   times out. The spatial entry point is the helper function
   `SDA_Get_Mukey_from_intersection_with_WktWgs84`, which is fast.
2. Feeding that helper's result back as a **correlated subquery** also times out. Reading
   the map unit keys first and interpolating them as literals returns in seconds — 2309
   polygons in under four for a Middle Tennessee AOI.
3. A map unit key recurs across its whole soil survey area, so the polygon query returns
   the county rather than the AOI. The result is clipped client-side.

Attributes come from `muaggatt`, the aggregated map-unit table, which already carries the
dominant-condition drainage class and flooding frequency, plus `copmgrp` for the parent
material that `burial_risk` depends on.
"""

from __future__ import annotations

import re
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
from pyproj import Transformer
from shapely.ops import transform as shapely_transform

from midden import PROJECT_CRS
from midden.aoi import Aoi
from midden.intake.drivers import DriverError, register

SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
_TIMEOUT = httpx.Timeout(300.0, connect=30.0)

#: Flooding frequency as an ordinal, for the burial-risk product. SSURGO's dominant
#: condition is a phrase, not a number.
FLOOD_FREQUENCY_SCORE = {
    "none": 0.0, "very rare": 0.2, "rare": 0.4,
    "occasional": 0.7, "frequent": 1.0, "very frequent": 1.0,
}


def _post(sql: str) -> list[list]:
    """Run one T-SQL statement against SDA and return its rows, header included."""
    try:
        response = httpx.post(
            SDA_URL, json={"query": sql, "format": "JSON+COLUMNNAME"}, timeout=_TIMEOUT
        )
    except httpx.HTTPError as exc:
        raise DriverError(f"Soil Data Access request failed: {exc}") from exc

    if "Table" not in response.text:
        match = re.search(r"<ServiceException>(.*?)</ServiceException>", response.text, re.DOTALL)
        detail = (match.group(1).strip() if match else response.text)[:400]
        raise DriverError(
            f"Soil Data Access rejected the query: {detail}. "
            f"Note that a correlated subquery against mupolygon times out; read the "
            f"map unit keys first and interpolate them as literals."
        )
    return response.json()["Table"]


def _envelope_wkt(aoi: Aoi, buffer_m: float) -> str:
    """The AOI's buffered envelope as WGS84 WKT, which is what SDA's helper expects."""
    xmin, ymin, xmax, ymax = aoi.geom.bounds
    from shapely.geometry import box

    envelope = box(xmin - buffer_m, ymin - buffer_m, xmax + buffer_m, ymax + buffer_m)
    to_wgs84 = Transformer.from_crs(PROJECT_CRS, "EPSG:4326", always_xy=True).transform
    return shapely_transform(to_wgs84, envelope).wkt


def _attributes(mukeys: list[str]) -> pd.DataFrame:
    """Drainage class, flooding frequency, and parent material for a set of map units."""
    literals = ",".join(f"'{key}'" for key in mukeys)
    aggregated = _post(f"""
        SELECT ma.mukey, mu.muname, ma.drclassdcd, ma.flodfreqdcd, ma.hydgrpdcd
        FROM muaggatt ma JOIN mapunit mu ON mu.mukey = ma.mukey
        WHERE ma.mukey IN ({literals})
    """)
    parent = _post(f"""
        SELECT c.mukey, pmg.pmgroupname
        FROM component c
        JOIN copmgrp pmg ON pmg.cokey = c.cokey AND pmg.rvindicator = 'Yes'
        WHERE c.majcompflag = 'Yes' AND c.mukey IN ({literals})
    """)

    frame = pd.DataFrame(aggregated[1:], columns=aggregated[0])
    materials = pd.DataFrame(parent[1:], columns=parent[0]).drop_duplicates("mukey")
    return frame.merge(materials, on="mukey", how="left")


def _burial_risk(frame: pd.DataFrame) -> pd.Series:
    """Alluvial parent material times flooding frequency (spec.md §7).

    Not decoration: this is what makes a low suitability score interpretable. A cell can
    score low because the landform is wrong, or because anything there is under metres of
    overbank silt, and those are different findings.
    """
    alluvial = (
        frame["pmgroupname"].fillna("").str.lower().str.contains("alluvi").astype(float)
    )
    flooding = (
        frame["flodfreqdcd"].fillna("").str.strip().str.lower().map(FLOOD_FREQUENCY_SCORE)
    ).fillna(0.0)
    return (alluvial * flooding).astype("float32")


@register("sda_rest")
def fetch(params: dict, aoi: Aoi | None, dest: Path) -> Path:
    """Fetch SSURGO map units covering an AOI, with the attributes the model needs."""
    if aoi is None:
        raise DriverError("sda_rest driver needs an AOI; pass --aoi <slug>.")
    buffer_m = float(params.get("buffer_m", 500.0))

    envelope = _envelope_wkt(aoi, buffer_m)
    keys = _post(
        f"SELECT mukey FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{envelope}')"
    )
    mukeys = [row[0] for row in keys[1:]]
    if not mukeys:
        raise DriverError(f"SSURGO returned no map units over {aoi.slug}.")

    literals = ",".join(f"'{key}'" for key in mukeys)
    # mupolygonkey, not mukey, is the polygon identifier. A map unit key recurs across
    # every polygon of that soil type in the survey area, so keying on it would collapse
    # a whole county's worth of separate polygons into one row.
    polygons = _post(
        f"SELECT mupolygonkey, mukey, mupolygongeo.STAsText() AS wkt FROM mupolygon "
        f"WHERE mukey IN ({literals})"
    )
    frame = gpd.GeoDataFrame(
        {
            "mupolygonkey": [row[0] for row in polygons[1:]],
            "mukey": [row[1] for row in polygons[1:]],
        },
        geometry=gpd.GeoSeries.from_wkt([row[2] for row in polygons[1:]]),
        crs="EPSG:4326",
    ).to_crs(PROJECT_CRS)

    # A mukey recurs across its whole survey area, so this comes back county-wide.
    frame = frame[frame.intersects(aoi.geom.buffer(buffer_m))].copy()
    if frame.empty:
        raise DriverError(
            f"SSURGO map units were found for {aoi.slug} but none intersect it after "
            f"clipping. Check the AOI geometry."
        )

    attributes = _attributes(mukeys)
    frame = frame.merge(attributes, on="mukey", how="left")
    frame["burial_risk"] = _burial_risk(frame)

    dest.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(dest, driver="GPKG", layer="data")
    return dest
