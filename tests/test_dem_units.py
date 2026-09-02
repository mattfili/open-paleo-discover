"""Units check on DEM output (spec.md §3).

A DEM in feet, or on a degree grid, produces a slope raster that looks entirely plausible
and is wrong. Nothing downstream will complain. This becomes live as soon as M2 registers
its first DEM; until then it skips rather than pretending to pass.
"""

from __future__ import annotations

import pytest

rasterio = pytest.importorskip("rasterio")

from midden.db import fetch_all

#: Middle Tennessee ground elevation, NAVD88 metres. The Central Basin floor is near 120 m
#: and the Highland Rim tops out around 360 m; anything far outside this is feet, a
#: different datum, or nodata leaking into the statistics.
MIN_ELEV_M, MAX_ELEV_M = 80.0, 450.0


def _dem_assets(db):
    return fetch_all(
        db,
        "SELECT path, resolution_m, grid FROM derived.raster_asset WHERE kind = 'dem'",
    )


def test_dem_is_metric_and_in_range(db):
    """Every registered DEM is a metre grid carrying plausible Middle TN elevations."""
    assets = _dem_assets(db)
    if not assets:
        pytest.skip("no DEM registered yet (arrives in M2)")

    for asset in assets:
        with rasterio.open(asset["path"]) as src:
            assert src.crs.linear_units.lower() in {"metre", "meter", "m"}, (
                f"{asset['path']}: horizontal units are {src.crs.linear_units!r}"
            )
            assert src.crs.to_epsg() == 26916, f"{asset['path']}: CRS is {src.crs}"

            band = src.read(1, masked=True)
            assert band.count(), f"{asset['path']}: DEM is entirely nodata"
            low, high = float(band.min()), float(band.max())
            assert MIN_ELEV_M <= low and high <= MAX_ELEV_M, (
                f"{asset['path']}: elevations {low:.1f}..{high:.1f} m fall outside the "
                f"plausible Middle TN range {MIN_ELEV_M}..{MAX_ELEV_M} m. "
                f"Feet would read roughly 3.28x high."
            )


def test_declared_resolution_matches_the_file(db):
    """The catalog's resolution_m must match the raster, or AOI-scoped queries lie."""
    assets = _dem_assets(db)
    if not assets:
        pytest.skip("no DEM registered yet (arrives in M2)")
    for asset in assets:
        with rasterio.open(asset["path"]) as src:
            assert abs(abs(src.transform.a) - asset["resolution_m"]) < 1e-6, (
                f"{asset['path']}: catalog says {asset['resolution_m']} m, "
                f"file says {abs(src.transform.a)} m"
            )
