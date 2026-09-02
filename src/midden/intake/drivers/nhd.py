"""NHD / NHDPlus High Resolution driver, via HyRiver's `pynhd`.

Endpoint note, because the spec is internally inconsistent and one half of it is down:
spec.md §5's source YAML names the layer `nhdflowline_network`, which is a **WaterData**
layer (NHDPlus V2, medium resolution) served from `api.water.usgs.gov`. That host does not
respond — a GetCapabilities request times out after 60 s. spec.md §6 names
`hydro.nationalmap.gov` instead, which answers in under half a second and serves NHDPlus
**High Resolution**, which is also what the source's own description asks for. So this
driver uses `pynhd.NHDPlusHR`.

The practical consequence for the source YAML: NHDPlus HR keys reaches on `nhdplusid`,
not `comid`. The transform renames it back to `comid` so that
`ref.nhd_flowline` keeps the column name `confluence_extract.sql` and spec.md §7 expect.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from pynhd import NHDPlusHR

from midden import PROJECT_CRS
from midden.aoi import Aoi
from midden.intake.drivers import DriverError, register

#: Hydrology needs context beyond the AOI: HAND is computed from upslope flow, and a
#: confluence just outside the boundary still governs the ground inside it. Fetching only
#: what intersects the AOI would truncate the network at the edge.
DEFAULT_BUFFER_M = 2000.0


@register("pynhd")
def fetch(params: dict, aoi: Aoi | None, dest: Path) -> Path:
    """Fetch one NHDPlus HR layer over the AOI's buffered bounding box."""
    layer = params.get("layer", "flowline")
    scope = params.get("scope", "aoi")
    buffer_m = float(params.get("buffer_m", DEFAULT_BUFFER_M))

    if scope != "aoi":
        raise DriverError(
            f"pynhd driver supports scope 'aoi' only, got {scope!r}. A statewide NHD pull "
            f"is hundreds of megabytes and spec.md §2 scopes every fetch to an AOI."
        )
    if aoi is None:
        raise DriverError("pynhd driver needs an AOI; pass --aoi <slug>.")

    xmin, ymin, xmax, ymax = aoi.geom.bounds
    bbox = (xmin - buffer_m, ymin - buffer_m, xmax + buffer_m, ymax + buffer_m)

    try:
        service = NHDPlusHR(layer, crs=PROJECT_CRS)
        frame = service.bygeom(bbox, geo_crs=PROJECT_CRS)
    except Exception as exc:
        raise DriverError(
            f"NHDPlus HR layer {layer!r} over {aoi.slug}: {exc}. "
            f"Check https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer"
        ) from exc

    if frame.empty:
        raise DriverError(
            f"NHDPlus HR layer {layer!r} returned no features for {aoi.slug} "
            f"(bbox buffered by {buffer_m:g} m). An empty hydrology layer would silently "
            f"produce a DEM with no streams and therefore no HAND."
        )

    _write(frame, dest)
    return dest


def _write(frame: gpd.GeoDataFrame, dest: Path) -> Path:
    """Write a GeoDataFrame to a GeoPackage, creating the parent directory."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(dest, driver="GPKG", layer="data")
    return dest
