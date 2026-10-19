"""The D8 accumulation guard catches the WBT out_type x10 trap (ROADMAP gotcha)."""

from __future__ import annotations

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from midden.skills import load


def _write(path, values):
    profile = {"driver": "GTiff", "dtype": "float32", "count": 1, "width": 3, "height": 3,
               "crs": "EPSG:26916", "transform": rasterio.transform.from_origin(0, 30, 10, 10),
               "nodata": -32768.0}
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.asarray(values, dtype="float32").reshape(1, 3, 3))


def test_guard_accepts_cell_counts_and_rejects_scaled_counts(tmp_path):
    """Minimum 1 passes (nodata ignored); a x10 raster (minimum 10) raises."""
    chain = load("whiteboxtools", "hydro_chain")
    ok = tmp_path / "ok.tif"
    _write(ok, [1, 2, 3, 4, 5, -32768, 7, 8, 9])
    chain.assert_accum_counts_cells(ok)

    bad = tmp_path / "bad.tif"
    _write(bad, [10, 20, 30, 40, 50, 60, 70, 80, 90])
    with pytest.raises(RuntimeError, match="expected 1 cell"):
        chain.assert_accum_counts_cells(bad)
