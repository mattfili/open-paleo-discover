"""DEM acquisition for both grids (spec.md §7, M2).

Two paths, and which one you need is decided by the grid, not by taste:

- **Modelling grid, 10 m** — `seamless-3dep`. Fast enough to shake the whole WhiteboxTools
  chain out in minutes. `get_dem` offers only res 10, 30 or 60, so 10 m is the finest this
  path reaches, which happens to be exactly the modelling grid.
- **Detection grid, 0.5 m** — the 3DEP point cloud through PDAL. There is no shortcut:
  the fast path cannot produce a detection grid, so hearths and the tunnel cut can only be
  resolved on this side.

Two CRS traps, both silent:

1. `get_dem` returns **EPSG:4269** with a pixel of 9.26e-05 *degrees*. Handing that to
   WhiteboxTools produces a slope raster that looks plausible and is nonsense, because WBT
   does not reproject and treats degrees as metres. Everything is warped to EPSG:26916 on
   arrival.
2. The 3DEP EPT bucket expects bounds in **EPSG:3857**, not the project CRS. Passing UTM
   returns zero points with no error. `dem_from_ept.py` handles that; this module passes
   AOI bounds in the project CRS and lets it convert.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
import seamless_3dep
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

from midden import PROJECT_CRS
from midden.aoi import Aoi
from midden.skills import load
from midden.terrain.params import GRID_BUFFER_M, grid_resolution

__all__ = ["buffered_bounds", "fetch_dem", "fetch_dem_3dep", "fetch_dem_ept"]

_EPSG = int(PROJECT_CRS.split(":")[1])


def buffered_bounds(aoi: Aoi, buffer_m: float) -> tuple[float, float, float, float]:
    """AOI bounds expanded by `buffer_m`, in the project CRS. Pure."""
    xmin, ymin, xmax, ymax = aoi.geom.bounds
    return (xmin - buffer_m, ymin - buffer_m, xmax + buffer_m, ymax + buffer_m)


def _to_wgs84(bounds: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Convert project-CRS bounds to the decimal degrees seamless-3dep expects. Pure-ish."""
    transformer = Transformer.from_crs(PROJECT_CRS, "EPSG:4326", always_xy=True)
    west, south = transformer.transform(bounds[0], bounds[1])
    east, north = transformer.transform(bounds[2], bounds[3])
    return (west, south, east, north)


def _warp_to_project_crs(src_path: Path, dest: Path, resolution_m: float) -> Path:
    """Warp a raster to EPSG:26916 on an exact `resolution_m` grid.

    Bilinear, because this is a continuous elevation surface; nearest would introduce
    stair-stepping that the slope and openness derivatives would then amplify.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, PROJECT_CRS, src.width, src.height, *src.bounds, resolution=resolution_m
        )
        # Built from scratch rather than inherited: the 3DEP source is striped, and
        # carrying its block size into a tiled output fails GDAL's multiple-of-16 rule.
        profile = {
            "driver": "GTiff", "crs": PROJECT_CRS, "transform": transform,
            "width": width, "height": height, "count": 1, "dtype": "float32",
            "nodata": np.nan, "compress": "DEFLATE",
            "tiled": True, "blockxsize": 256, "blockysize": 256,
            # No PREDICTOR. WhiteboxTools' GeoTIFF reader rejects floating-point
            # predictors ("does not currently support floating-point predictors") and
            # does so by panicking *after* returning exit code 0, so the failure surfaces
            # as a missing output file rather than an error. COGs written for QGIS and
            # rasterio may use one; anything WBT reads may not.
        }
        with rasterio.open(dest, "w", **profile) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform, src_crs=src.crs,
                dst_transform=transform, dst_crs=PROJECT_CRS,
                resampling=Resampling.bilinear,
                src_nodata=src.nodata, dst_nodata=np.nan,
            )
    return dest


def fetch_dem_3dep(aoi: Aoi, work_dir: Path, *, resolution_m: float, buffer_m: float) -> Path:
    """Fetch a 3DEP DEM over the buffered AOI and warp it to the project CRS."""
    if resolution_m not in (10.0, 30.0, 60.0):
        raise ValueError(
            f"seamless-3dep get_dem offers res 10, 30 or 60 m only, got {resolution_m}. "
            f"The 0.5 m detection grid needs the point-cloud path (fetch_dem_ept)."
        )
    raw_dir = work_dir / "3dep_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    bbox = _to_wgs84(buffered_bounds(aoi, buffer_m))
    tiles = seamless_3dep.get_dem(bbox, raw_dir, res=int(resolution_m))
    if not tiles:
        raise RuntimeError(f"3DEP returned no tiles for {aoi.slug} over bbox {bbox}.")

    source = tiles[0] if len(tiles) == 1 else Path(
        seamless_3dep.build_vrt(raw_dir / "dem.vrt", tiles)
    )
    return _warp_to_project_crs(source, work_dir / "dem.tif", resolution_m)


def _ept_pipeline(aoi, work_dir, project, resolution_m, buffer_m, dem, count, ept) -> dict:
    """Build the PDAL pipeline for an EPT extract and save it beside its outputs.

    The USGS public bucket is EPSG:3857. Passing UTM bounds returns zero points with no
    error at all, so this conversion is the difference between a DEM and an empty file.
    """
    xmin, ymin, xmax, ymax = buffered_bounds(aoi, buffer_m)
    bounds = ept.ept_bounds(xmin, ymin, xmax, ymax, src_crs=PROJECT_CRS, ept_crs="EPSG:3857")
    pipeline = ept.build_pipeline(
        project, bounds, PROJECT_CRS, resolution_m, dem, count, resolution_m
    )
    (work_dir / "pipeline.json").write_text(json.dumps(pipeline, indent=2))
    return pipeline


def fetch_dem_ept(
    aoi: Aoi,
    work_dir: Path,
    *,
    project: str,
    resolution_m: float,
    buffer_m: float,
    timeout_s: int = 3600,
) -> Path:
    """Build a bare-earth DEM from the 3DEP point cloud, via the pdal-pipelines skill.

    The skill's `dem_from_ept` and `run_pipeline` are imported through `midden.skills`
    rather than shelled out to. Running `python dem_from_ept.py` puts its own directory at
    the front of `sys.path`, and that directory contains an `inspect.py` which shadows the
    standard library's — Python's own error suggests renaming it. The loader appends
    instead of prepending, so the standard library keeps priority.

    Two outputs, and the second is not optional: alongside `dem.tif` the pipeline writes
    `ground_count.tif`, the number of ground returns per cell. That is the honesty check on
    the chosen resolution — under canopy at QL2, 0.5 m is often optimistic and 1 m honest,
    and the count raster is what says which.
    """
    ept = load("pdal-pipelines", "dem_from_ept")
    runner = load("pdal-pipelines", "run_pipeline")

    work_dir.mkdir(parents=True, exist_ok=True)
    dem = work_dir / "dem.tif"
    count = work_dir / "ground_count.tif"
    pipeline = _ept_pipeline(aoi, work_dir, project, resolution_m, buffer_m, dem, count, ept)

    try:
        runner.run(pipeline, metadata_out=work_dir / "pdal_metadata.json", timeout=timeout_s)
    except runner.PdalError as exc:
        raise RuntimeError(
            f"{aoi.slug}: PDAL failed for EPT project {project!r}.\n{exc}\n"
            f"If it produced no points, check the bounds CRS (the USGS public bucket is "
            f"EPSG:3857) and that the project exists at https://usgs.entwine.io/"
        ) from exc

    if not dem.exists():
        raise RuntimeError(
            f"{aoi.slug}: PDAL reported success but wrote no DEM at {dem}. "
            f"A Classification[2:2] filter on unclassified data matches nothing and the "
            f"pipeline still succeeds — check {count} and pdal_metadata.json."
        )
    ept.report_coverage(count)
    return dem


def fetch_dem(
    aoi: Aoi,
    work_dir: Path,
    *,
    grid: str,
    ept_project: str | None = None,
    buffer_m: float | None = None,
) -> Path:
    """Fetch the DEM appropriate to a grid, buffered and in the project CRS."""
    resolution_m = grid_resolution(grid)
    buffer_m = GRID_BUFFER_M[grid] if buffer_m is None else buffer_m

    if grid == "model":
        return fetch_dem_3dep(aoi, work_dir, resolution_m=resolution_m, buffer_m=buffer_m)
    if ept_project is None:
        raise ValueError(
            "The detection grid needs an EPT project name (--ept-project). Find the "
            "Middle TN project at https://usgs.entwine.io/ ; bounds for that bucket are "
            "EPSG:3857 and dem_from_ept converts them."
        )
    return fetch_dem_ept(
        aoi, work_dir, project=ept_project, resolution_m=resolution_m, buffer_m=buffer_m
    )
