"""Detection-grid renders: openness, SLRM, and multidirectional hillshade (spec.md §7).

These are the surfaces a human or a model *looks at* to spot anomalies. Statistically
meaningless, visually essential.

Openness, not sky-view factor. Doneus (2013) proposed openness as the better technique for
interpretive mapping of archaeological DTMs: no directional bias, no horizontal
displacement of features, and — the part that decides it here — SVF delineates mainly
*concave* features while openness delineates both concave and convex. Mounds, platforms
and charcoal hearths are convex.

Sign convention, and getting it backwards silently inverts every interpretation
downstream:

    positive openness HIGH (>90 deg) = CONVEX   mounds, hearths, ridges
    negative openness HIGH (>90 deg) = CONCAVE  pits, ditches, the tunnel cut
    flat plane = 90 deg for both, regardless of slope

Negative openness is not the inverse of positive. Render both: a mound with a surrounding
borrow ditch shows its top in positive openness and the ditch ring in negative.

`Openness` is absent from WhiteboxTools v2.4.0 open core — the binary answers
"Unrecognized tool name Openness" while the Python wrapper still exposes the method — so
the horizon scan is RVT's, vendored in `_rvt_vis.py` (Apache-2.0, see NOTICE).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from midden.skills import load
from midden.terrain._rvt_vis import sky_view_factor_compute
from midden.terrain.params import cells_from_metres

__all__ = [
    "OPENNESS_FLAT_DEG",
    "detection_renders",
    "multidirectional_hillshade",
    "openness",
    "read_dem",
    "slrm",
    "write_like",
]

#: A flat plane reads exactly this in both signs, whatever its slope. The property that
#: makes openness illumination-independent, and the first thing to check on a new render.
OPENNESS_FLAT_DEG = 90.0


def read_dem(path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any], float]:
    """Read a DEM as (values, nodata_mask, profile, resolution_m).

    Values come back with NaN in the nodata cells, which is the form RVT's horizon scan
    expects — it treats NaN as fully open sky rather than as an elevation.
    """
    with rasterio.open(path) as src:
        band = src.read(1, masked=True)
        profile = src.profile.copy()
        resolution_m = abs(src.transform.a)
    mask = np.ma.getmaskarray(band)
    values = band.filled(np.nan).astype(np.float32)
    return values, mask, profile, resolution_m


def write_like(dest: Path, data: np.ndarray, profile: dict[str, Any]) -> Path:
    """Write a float32 raster matching a source profile, NaN as nodata."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = profile | {
        "driver": "GTiff", "dtype": "float32", "count": 1, "nodata": np.nan,
        "compress": "DEFLATE", "tiled": True, "blockxsize": 256, "blockysize": 256,
    }
    # No PREDICTOR: WhiteboxTools cannot read floating-point predictors and fails by
    # panicking after returning exit code 0.
    out.pop("predictor", None)
    with rasterio.open(dest, "w", **out) as dst:
        dst.write(data.astype(np.float32), 1)
    return dest


def openness(
    dem: np.ndarray,
    *,
    resolution_m: float,
    search_radius_m: float,
    num_directions: int = 16,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (positive, negative) openness in degrees.

    The search radius is given in **metres** and converted to cells against this raster's
    own resolution. RVT's `radius_max` is a cell count, so passing a fixed number would
    silently measure a 10 m neighbourhood on the detection grid and a 200 m one on the
    modelling grid.

    Negative openness is the same horizon scan run on a negated DEM, which is how RVT
    itself computes it — not an inversion of the positive result.
    """
    radius_cells = cells_from_metres(search_radius_m, resolution_m, minimum=2)

    def scan(surface: np.ndarray) -> np.ndarray:
        return sky_view_factor_compute(
            surface,
            radius_max=radius_cells,
            radius_min=1,
            num_directions=num_directions,
            compute_svf=False,
            compute_opns=True,
        )["opns"]

    return scan(dem), scan(-dem)


def slrm(dem: np.ndarray, mask: np.ndarray, *, radius_m: float, resolution_m: float) -> np.ndarray:
    """Simple Local Relief Model: DEM minus a Gaussian-smoothed DEM.

    Delegates to `detection_renders.slrm` in the landform-archaeology skill, which already
    handles the trap: NaN propagates through a Gaussian kernel and will eat the edges and
    every nodata hole, so the surface is filled before smoothing and re-masked after.
    """
    renders = load("landform-archaeology", "detection_renders")
    return renders.slrm(dem, mask, radius_m, resolution_m)


def multidirectional_hillshade(dem_path: Path, dest: Path) -> Path:
    """Multi-azimuth hillshade, for context only — never detect from it.

    Single-azimuth hillshade hides features whose orientation is unlucky, which is why the
    detection set is openness and SLRM. This is here because a shaded relief underneath
    them is how a reader orients themselves.
    """
    helpers = load("whiteboxtools", "wbt_helpers")
    wbt = helpers.make_wbt(dest.parent)
    helpers.require_tools(wbt, ["MultidirectionalHillshade"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    helpers.checked(
        wbt, wbt.multidirectional_hillshade,
        str(dem_path.resolve()), str(dest.resolve()), full_mode=True,
        expect=dest,
    )
    # WhiteboxTools writes -9999 for nodata but does not tag it, so every downstream
    # reader treats it as a real value and any percentile stretch collapses.
    with rasterio.open(dest, "r+") as handle:
        handle.nodata = -9999
    return dest


def detection_renders(
    dem_path: Path,
    out_dir: Path,
    *,
    search_radius_m: float,
    smoothing_radius_m: float,
    num_directions: int = 16,
) -> dict[str, Path]:
    """Produce the standard detection set from a bare-earth DEM.

    Returns paths keyed `openness_pos`, `openness_neg`, `slrm`, `hillshade_multi`.
    """
    dem, mask, profile, resolution_m = read_dem(dem_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    positive, negative = openness(
        dem,
        resolution_m=resolution_m,
        search_radius_m=search_radius_m,
        num_directions=num_directions,
    )
    relief = slrm(dem, mask, radius_m=smoothing_radius_m, resolution_m=resolution_m)

    for surface in (positive, negative, relief):
        surface[mask] = np.nan

    outputs = {
        "openness_pos": write_like(out_dir / "openness_pos.tif", positive, profile),
        "openness_neg": write_like(out_dir / "openness_neg.tif", negative, profile),
        "slrm": write_like(out_dir / "slrm.tif", relief, profile),
    }
    outputs["hillshade_multi"] = multidirectional_hillshade(
        dem_path, out_dir / "hillshade_multi.tif"
    )
    return outputs
