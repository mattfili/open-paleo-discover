#!/usr/bin/env python3
"""
Produce the standard detection-grid render set from a 0.5 m bare-earth DEM.

Four outputs:
    openness_pos.tif   convex features -- mounds, hearth platforms, ridges
    openness_neg.tif   concave features -- pits, ditches, relict channels
    slrm.tif           local relief, scale-tunable; best single layer for scanning
    hillshade_multi.tif  context only, not for detection

SIGN CONVENTION -- getting this backwards silently inverts every interpretation:
    positive openness HIGH (>90 deg) = CONVEX
    negative openness HIGH (>90 deg) = CONCAVE
    flat plane = 90 deg for both, regardless of slope

Usage:
    python detection_renders.py DEM.tif OUTDIR
    python detection_renders.py DEM.tif OUTDIR --slrm-radius 10 15 25 --openness-cells 20 40

Sweeping: pass several values to --slrm-radius or --openness-cells and each is written
with the value in the filename. Tune against a control with a known feature, never
against a prospect. See references/visualization-guide.md.

Verify before relying on this:
    - WhiteboxTools openness argument names and whether the tool writes one output or
      two. Run wbt.tool_help("Openness"). Adjust _openness() accordingly.
"""

import argparse
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt, gaussian_filter


def fill_nodata_nearest(arr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Fill NoData with the nearest valid value.

    This exists because NaN propagates through a Gaussian kernel. Smooth an array with
    holes in it and the holes grow by the kernel radius, and the AOI edge develops a
    soft halo that reads as a broad real anomaly. It has been mistaken for archaeology.

    Nearest-neighbour fill is crude but adequate: we reapply the mask afterwards, so the
    filled values only ever serve to keep the kernel well-behaved near edges.
    """
    if not mask.any():
        return arr
    idx = distance_transform_edt(mask, return_distances=False, return_indices=True)
    return arr[tuple(idx)]


def slrm(dem: np.ndarray, mask: np.ndarray, radius_m: float, res_m: float) -> np.ndarray:
    """Simple Local Relief Model: DEM minus a low-pass-filtered DEM.

    Positive = locally high, negative = locally low. The smoothing radius sets which
    feature sizes survive: ~10 m for small features and noise, ~15 m for hearth and
    small-mound scale, ~25 m for larger features.
    """
    filled = fill_nodata_nearest(dem, mask)
    trend = gaussian_filter(filled, sigma=radius_m / res_m)
    out = filled - trend
    out[mask] = np.nan  # reapply the mask -- filled values were scaffolding only
    return out


def _openness(wbt, dem_path: Path, pos_path: Path, neg_path: Path, dist_cells: int) -> None:
    """Call WhiteboxTools openness.

    Isolated in its own function because the signature is the most likely thing to
    break across WBT versions. If this raises, run wbt.tool_help("Openness") and fix
    it here rather than scattering version checks through the module.
    """
    wbt.openness(str(dem_path), str(pos_path), str(neg_path), dist=dist_cells)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dem", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument(
        "--slrm-radius",
        type=float,
        nargs="+",
        default=[15.0],
        help="Metres. Several values produce a sweep.",
    )
    ap.add_argument(
        "--openness-cells",
        type=int,
        nargs="+",
        default=[20],
        help="Search radius in CELLS, not metres. At 0.5 m, 20 cells = 10 m ~ one "
        "charcoal hearth. Several values produce a sweep.",
    )
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    import whitebox

    wbt = whitebox.WhiteboxTools()
    wbt.verbose = False
    wbt.set_working_dir(str(args.outdir.resolve()))

    with rasterio.open(args.dem) as src:
        band = src.read(1, masked=True)
        dem = band.filled(np.nan).astype("float64")
        mask = np.ma.getmaskarray(band) | ~np.isfinite(dem)
        profile = src.profile
        res_m = abs(src.transform.a)

    if abs(res_m - 0.5) > 0.01:
        print(
            f"NOTE: resolution is {res_m} m, not 0.5 m. Openness radii are in cells, so "
            "the metric search distance differs from the defaults documented here."
        )

    profile.update(dtype=rasterio.float32, count=1, nodata=np.nan, compress="deflate")

    for radius in args.slrm_radius:
        out = slrm(dem, mask, radius, res_m)
        name = "slrm.tif" if len(args.slrm_radius) == 1 else f"slrm_r{radius:g}m.tif"
        with rasterio.open(args.outdir / name, "w", **profile) as dst:
            dst.write(out.astype("float32"), 1)
        print(f"Wrote {name}")

    for cells in args.openness_cells:
        suffix = "" if len(args.openness_cells) == 1 else f"_d{cells}"
        pos = args.outdir / f"openness_pos{suffix}.tif"
        neg = args.outdir / f"openness_neg{suffix}.tif"
        _openness(wbt, args.dem, pos, neg, cells)
        print(f"Wrote {pos.name} (CONVEX bright) and {neg.name} (CONCAVE bright)")

    hs = args.outdir / "hillshade_multi.tif"
    wbt.multidirectional_hillshade(str(args.dem), str(hs))
    print(f"Wrote {hs.name} (context only -- do not detect from this)")

    print(
        "\nScan SLRM first, then confirm anything interesting in both openness bands. "
        "A real feature is usually visible in at least two of the three.\n"
        "Stretch: percentile clip 2-98, held constant across a sweep, or you are "
        "comparing stretches rather than parameters."
    )


if __name__ == "__main__":
    main()
