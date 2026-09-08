"""Which EPT project actually covers a given extent (ROADMAP ticket, 2026-09-07).

The USGS public EPT bucket is a patchwork of collection blocks, and a project's
`ept.json` bounds are the CUBE that encloses its data, not its footprint: the cube
for `USGS_LPC_TN_Middle_B1_2018` contains Montgomery Bell, while the flight coverage
does not — PDAL then reports "Unable to write GDAL data with no points" and a cluster
becomes a false coverage gap.

The authoritative footprints are the polygons in hobu/usgs-lidar's
`boundaries/resources.geojson`, which this module fetches once and caches. Callers
resolve candidates per extent and fall back across them, so a seam cluster tries the
neighbouring block instead of being reported as missing data.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import shapely
import shapely.geometry
from pyproj import Transformer

from midden import PROJECT_CRS

__all__ = ["BOUNDARIES_URL", "covering_projects", "load_boundaries"]

BOUNDARIES_URL = (
    "https://raw.githubusercontent.com/hobu/usgs-lidar/master/boundaries/"
    "resources.geojson"
)

_TO_WGS84 = Transformer.from_crs(PROJECT_CRS, "EPSG:4326", always_xy=True)


def load_boundaries(cache_dir: Path) -> dict:
    """Return the coverage index, fetching and caching it on first use.

    Cached by content: the index changes only when USGS publishes new collections,
    so a stale-but-present cache is preferable to a network dependency mid-run.
    """
    cache = cache_dir / "usgs_ept_boundaries.geojson"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(BOUNDARIES_URL, timeout=120) as response:
            cache.write_bytes(response.read())
    return json.loads(cache.read_text())


def covering_projects(
    bounds: tuple[float, float, float, float],
    cache_dir: Path,
    *,
    prefer: str | None = None,
) -> list[str]:
    """EPT project names whose published footprint intersects `bounds`. Pure-ish.

    `bounds` is in the project CRS (metres); the index is WGS84. `prefer` is moved
    to the front when it covers, so an explicit --ept-project stays authoritative
    where it is valid and is merely bypassed where it is not. Ordering after that
    prefers the most recent collection (names carry their year), which is generally
    the denser one.
    """
    xmin, ymin, xmax, ymax = bounds
    west, south = _TO_WGS84.transform(xmin, ymin)
    east, north = _TO_WGS84.transform(xmax, ymax)
    extent = shapely.geometry.box(west, south, east, north)

    index = load_boundaries(cache_dir)
    names = []
    for feature in index.get("features", []):
        geometry = feature.get("geometry")
        name = (feature.get("properties") or {}).get("name")
        if not geometry or not name:
            continue
        if shapely.geometry.shape(geometry).intersects(extent):
            names.append(name)

    names.sort(key=lambda n: (n != prefer, _year(n) * -1, n))
    return names


def _year(name: str) -> int:
    """Best-effort collection year from a project name; 0 when absent. Pure."""
    return max(
        (
            int(part)
            for part in name.replace("-", "_").split("_")
            if part.isdigit() and len(part) == 4 and 1990 < int(part) < 2100
        ),
        default=0,
    )
