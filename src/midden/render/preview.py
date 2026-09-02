"""Raster to PNG, for looking at.

This is what makes the AI layer useful rather than decorative (spec.md §9): FastMCP can
return image content blocks, so a model can *look at* a positive-openness render and say
there is a rectilinear anomaly at the northeast edge that does not match the surrounding
drainage. It is also how a human checks a sweep.

The stretch is the important part. A percentile stretch computed per-image makes every
render in a sweep look equally contrasty and therefore incomparable, so the limits can be
supplied and held constant across a sweep — which is exactly what
`visualization-guide.md` requires ("2-98 percentile stretch held constant across sweeps").
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import numpy as np
import rasterio
from PIL import Image

__all__ = ["Stretch", "percentile_stretch", "to_png"]

#: Openness is meaningful in absolute degrees around 90, so a symmetric window around 90
#: reads more honestly than a percentile stretch: two renders of different ground stay
#: comparable, and flat is always mid-grey.
OPENNESS_WINDOW_DEG = 6.0


class Stretch(NamedTuple):
    """A (low, high) display range in the raster's own units."""

    low: float
    high: float

    @classmethod
    def of(cls, low: float, high: float) -> Stretch:
        """Build a stretch, rejecting an inverted or empty range."""
        if not high > low:
            raise ValueError(f"stretch high must exceed low, got ({low}, {high})")
        return cls(low, high)


def percentile_stretch(path: Path, low_pct: float = 2.0, high_pct: float = 98.0) -> Stretch:
    """Compute a percentile stretch from one raster.

    Compute it once on a reference raster and pass the same Stretch to every render in a
    sweep; recomputing per image is what makes a sweep impossible to compare.
    """
    with rasterio.open(path) as src:
        band = src.read(1, masked=True)
    values = band.compressed()
    if values.size == 0:
        raise ValueError(f"{path}: raster is entirely nodata.")
    low, high = np.percentile(values, [low_pct, high_pct])
    if high <= low:
        high = low + 1e-6
    return Stretch.of(float(low), float(high))


def openness_stretch(window_deg: float = OPENNESS_WINDOW_DEG) -> Stretch:
    """A fixed display window centred on 90 degrees, for openness rasters."""
    return Stretch.of(90.0 - window_deg, 90.0 + window_deg)


def to_png(
    src_path: Path,
    dest: Path,
    *,
    stretch: Stretch | None = None,
    max_px: int = 1500,
    invert: bool = False,
) -> Path:
    """Render a single-band raster to a greyscale PNG.

    `max_px` caps the long edge. spec.md §8 requires that for the artifact export, and it
    keeps an MCP image block small enough to be worth returning.
    """
    with rasterio.open(src_path) as src:
        band = src.read(1, masked=True)

    stretch = stretch or percentile_stretch(src_path)
    # Cast before filling: WhiteboxTools writes hillshade as int16 with -9999 nodata, and
    # a masked int array cannot take NaN as a fill value.
    values = band.astype("float32").filled(np.nan)
    scaled = (values - stretch.low) / (stretch.high - stretch.low)
    scaled = np.clip(scaled, 0.0, 1.0)
    if invert:
        scaled = 1.0 - scaled

    grey = np.where(np.isnan(scaled), 0, (scaled * 255)).astype(np.uint8)
    alpha = np.where(np.ma.getmaskarray(band), 0, 255).astype(np.uint8)

    image = Image.fromarray(np.dstack([grey, grey, grey, alpha]), mode="RGBA")
    if max(image.size) > max_px:
        scale = max_px / max(image.size)
        image = image.resize(
            (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="PNG", optimize=True)
    return dest
