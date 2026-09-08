"""OGC WFS driver: vector features from a WFS endpoint, scoped to an AOI bbox.

Added for the USGS State Geologic Map Compilation (C4, lithic raw material), which
publishes polygons over WFS rather than ArcGIS REST. Two things this driver must get
right, both of which bite silently:

- **The bbox is WGS84 lon/lat in WFS 1.0.0**, and the AOI is project-CRS metres, so
  the transform is not optional. WFS 1.1.0 flips axis order to lat/lon depending on
  the CRS declaration, which is exactly the class of silent error this project
  refuses; 1.0.0 is pinned for that reason.
- **The response declares no CRS that GeoPandas will honour** (`crs` reads None on
  this server's GML), so it is set explicitly to EPSG:4326 before the transform
  chain. Loading it as if it were already project CRS would place Tennessee geology
  a few hundred metres off the coast of Africa.
"""

from __future__ import annotations

import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
from pyproj import Transformer

from midden import PROJECT_CRS, __version__
from midden.aoi import Aoi
from midden.intake.drivers import DriverError, register

_TIMEOUT = 600
_TO_WGS84 = Transformer.from_crs(PROJECT_CRS, "EPSG:4326", always_xy=True)


@register("wfs")
def fetch(params: dict, aoi: Aoi | None, dest: Path) -> Path:
    """Fetch one WFS feature type over the AOI's buffered bbox to a GeoPackage."""
    url = params.get("url")
    typename = params.get("typename")
    if not url or not typename:
        raise DriverError("wfs driver needs 'url' and 'typename' params.")
    if aoi is None:
        raise DriverError("wfs driver is AOI-scoped; pass --aoi <slug>.")

    buffer_m = float(params.get("buffer_m", 0.0))
    xmin, ymin, xmax, ymax = aoi.geom.bounds
    west, south = _TO_WGS84.transform(xmin - buffer_m, ymin - buffer_m)
    east, north = _TO_WGS84.transform(xmax + buffer_m, ymax + buffer_m)

    query = urllib.parse.urlencode(
        {
            "service": "WFS",
            "version": params.get("version", "1.0.0"),
            "request": "GetFeature",
            "typeName": typename,
            "bbox": f"{west},{south},{east},{north}",
        }
    )
    raw = dest.with_suffix(".gml")
    raw.parent.mkdir(parents=True, exist_ok=True)
    # An explicit User-Agent is required, not cosmetic: mrdata.usgs.gov answers
    # urllib's default agent with HTTP 403 while serving the identical URL to curl.
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": f"midden/{__version__} (research)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            raw.write_bytes(response.read())
    except OSError as exc:
        raise DriverError(f"{url}: {exc}") from exc

    try:
        frame = gpd.read_file(raw)
    except Exception as exc:  # noqa: BLE001 - surfaced as a driver failure with the path
        raise DriverError(
            f"{url}: response at {raw} is not readable vector data ({exc})"
        )
    finally:
        raw.unlink(missing_ok=True)

    if frame.empty:
        raise DriverError(f"{url}: {typename} returned no features over {aoi.slug}.")

    # The server declares no usable CRS on this GML; WFS 1.0.0 bbox is lon/lat, so
    # the response is EPSG:4326. Asserting it beats inheriting None and loading
    # degrees as metres.
    frame = frame.set_crs("EPSG:4326", allow_override=True).to_crs(PROJECT_CRS)

    keep = params.get("where_in")
    if keep:
        column, values = keep["column"], set(keep["values"])
        frame = frame[frame[column].isin(values)]
        if frame.empty:
            raise DriverError(
                f"{url}: no {typename} feature over {aoi.slug} has "
                f"{column} in {sorted(values)}."
            )

    frame.to_file(dest, driver="GPKG", layer="data")
    return dest
