#!/usr/bin/env python3
"""
AOI -> bare-earth DEM from a 3DEP EPT dataset.

Handles the trap that costs people an afternoon: readers.ept interprets `bounds`
in the EPT's OWN CRS, not yours. The USGS 3DEP public bucket is EPSG:3857. Pass UTM
coordinates and you get zero points back with no error.

This script takes AOI bounds in your project CRS, converts them, and writes both a
DEM and a ground-return count raster. Look at the count raster before trusting the
DEM -- it shows where elevation was measured and where it was interpolated.

Usage:
    python dem_from_ept.py \\
        --project USGS_LPC_TN_..._LAS_2019 \\
        --bounds 512000 3995000 516000 3999000 \\
        --bounds-crs EPSG:26916 \\
        --resolution 1.0 \\
        --out out/

Find project names at https://usgs.entwine.io/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyproj import Transformer
from run_pipeline import PdalError, run

EPT_BASE = "https://s3-us-west-2.amazonaws.com/usgs-lidar-public"


def ept_bounds(
    xmin: float, ymin: float, xmax: float, ymax: float,
    src_crs: str, ept_crs: str = "EPSG:3857",
) -> str:
    """Convert AOI bounds to the EPT's CRS and format them for PDAL.

    PDAL's bounds syntax is ([xmin,xmax],[ymin,ymax]) -- X range first, then Y
    range. NOT (xmin,ymin,xmax,ymax), and not GeoJSON or a WKT envelope.
    """
    if src_crs.upper() == ept_crs.upper():
        bx0, by0, bx1, by1 = xmin, ymin, xmax, ymax
    else:
        t = Transformer.from_crs(src_crs, ept_crs, always_xy=True)
        bx0, by0 = t.transform(xmin, ymin)
        bx1, by1 = t.transform(xmax, ymax)

    return f"([{bx0},{bx1}],[{by0},{by1}])"


def build_pipeline(
    project: str, bounds: str, out_crs: str, resolution: float,
    dem_path: Path, count_path: Path, ept_resolution: float | None,
) -> dict:
    """Stage order matters: filter cheap and early, reproject before the writer.

    Reprojecting last means `resolution` in writers.gdal is in metres. Put the
    writer before the reprojection and 1.0 means one degree.
    """
    reader: dict = {
        "type": "readers.ept",
        "filename": f"{EPT_BASE}/{project}/ept.json",
        "bounds": bounds,
    }
    if ept_resolution is not None:
        # Requests a level of detail rather than full density. Setting it near the
        # target grid size avoids downloading several times more data than the
        # output can express.
        reader["resolution"] = ept_resolution

    gdal_opts = "COMPRESS=DEFLATE,TILED=YES"

    return {
        "pipeline": [
            reader,
            # Ground returns only. If this matches nothing you get an empty raster
            # and no error -- run inspect.py first to confirm class 2 exists.
            {"type": "filters.range", "limits": "Classification[2:2]"},
            {"type": "filters.reprojection", "out_srs": out_crs},
            {
                "type": "writers.gdal",
                "filename": str(dem_path),
                "resolution": resolution,
                "output_type": "idw",
                "radius": resolution * 1.5,
                "window_size": 3,
                "gdaldriver": "GTiff",
                "gdalopts": gdal_opts,
            },
            {
                # The diagnostic. Cells reading 0 are interpolated, not measured.
                "type": "writers.gdal",
                "filename": str(count_path),
                "resolution": resolution,
                "output_type": "count",
                "gdaldriver": "GTiff",
                "gdalopts": gdal_opts,
            },
        ]
    }


def report_coverage(count_path: Path) -> None:
    """Summarize ground-return coverage. This is the honesty check on resolution."""
    try:
        import numpy as np
        import rasterio
    except ImportError:
        return

    with rasterio.open(count_path) as src:
        arr = src.read(1, masked=True).filled(0)

    total = arr.size
    empty = int((arr == 0).sum())
    thin = int(((arr > 0) & (arr < 2)).sum())
    print(
        f"\nGround-return coverage at this resolution:\n"
        f"  cells with no ground return : {empty / total:6.1%}  (interpolated, not measured)\n"
        f"  cells with exactly 1        : {thin / total:6.1%}\n"
        f"  median count where present  : {np.median(arr[arr > 0]):.1f}"
    )
    if empty / total > 0.25:
        print(
            "  -> Over a quarter of the grid is interpolated. You do not have a DEM at "
            "this resolution; you have a coarser one that has been upsampled by gap "
            "filling. Coarsen the grid rather than raising window_size."
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True, help="EPT project name from usgs.entwine.io")
    ap.add_argument(
        "--bounds", nargs=4, type=float, required=True,
        metavar=("XMIN", "YMIN", "XMAX", "YMAX"),
    )
    ap.add_argument("--bounds-crs", default="EPSG:26916", help="CRS of --bounds.")
    ap.add_argument("--ept-crs", default="EPSG:3857", help="CRS of the EPT dataset itself.")
    ap.add_argument("--out-crs", default="EPSG:26916", help="Output DEM CRS. Must be metric.")
    ap.add_argument("--resolution", type=float, default=1.0, help="Output CRS units.")
    ap.add_argument(
        "--ept-resolution", type=float, default=None,
        help="Level-of-detail request. Defaults to the output resolution.",
    )
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    bounds = ept_bounds(*args.bounds, src_crs=args.bounds_crs, ept_crs=args.ept_crs)
    print(f"AOI bounds in {args.bounds_crs}: {args.bounds}")
    print(f"Converted to {args.ept_crs} for readers.ept: {bounds}")

    dem = args.out / "dem.tif"
    count = args.out / "ground_count.tif"

    pipeline = build_pipeline(
        args.project, bounds, args.out_crs, args.resolution,
        dem, count, args.ept_resolution or args.resolution,
    )
    (args.out / "pipeline.json").write_text(json.dumps(pipeline, indent=2))

    try:
        run(pipeline, metadata_out=args.out / "pdal_metadata.json")
    except PdalError as exc:
        raise SystemExit(
            f"{exc}\n\n"
            "If this produced no points: check that the bounds CRS is right (the USGS "
            "public bucket is EPSG:3857) and that the project name exists at "
            "https://usgs.entwine.io/"
        )

    print(f"\nWrote {dem}")
    print(f"Wrote {count}")
    report_coverage(count)


if __name__ == "__main__":
    main()
