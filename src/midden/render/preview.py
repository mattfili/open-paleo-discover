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


#: Viridis, sampled at 16 stops. Embedded rather than pulled from matplotlib, which is not
#: a dependency: this project needs one colour ramp, not a plotting library.
_VIRIDIS = [
    (68, 1, 84), (72, 26, 108), (71, 47, 125), (65, 68, 135), (57, 86, 140),
    (49, 104, 142), (42, 120, 142), (35, 136, 142), (31, 152, 139), (34, 168, 132),
    (53, 183, 121), (84, 197, 104), (122, 209, 81), (165, 219, 54), (210, 226, 27),
    (253, 231, 37),
]

#: Terrace classes are nominal, not continuous, so they get distinct hues rather than a
#: ramp: 0 none, 1 T0 (floods yearly), 2 T1 (the target), 3 T2, 4 T3.
_TERRACE = {
    0: (40, 40, 46), 1: (70, 100, 130), 2: (250, 200, 60),
    3: (150, 180, 110), 4: (110, 130, 120),
}


def _apply_palette(scaled: np.ndarray, palette: str) -> np.ndarray:
    """Map a 0-1 array to RGB using a named palette."""
    if palette == "viridis":
        index = np.clip((scaled * (len(_VIRIDIS) - 1)), 0, len(_VIRIDIS) - 1)
        low = np.floor(index).astype(int)
        high = np.minimum(low + 1, len(_VIRIDIS) - 1)
        weight = (index - low)[..., None]
        table = np.array(_VIRIDIS, dtype="float32")
        return (table[low] * (1 - weight) + table[high] * weight).astype("uint8")

    if palette == "terrace":
        out = np.zeros((*scaled.shape, 3), dtype="uint8")
        classes = np.rint(scaled * 4).astype(int)
        for value, colour in _TERRACE.items():
            out[classes == value] = colour
        return out

    grey = (scaled * 255).astype("uint8")
    return np.dstack([grey, grey, grey])


def to_web_png(
    src_path: Path,
    dest: Path,
    *,
    stretch: Stretch | None = None,
    palette: str = "grey",
    max_px: int = 1500,
) -> tuple[Path, tuple[float, float, float, float]]:
    """Warp a raster to Web Mercator, render it, and return the PNG and its WGS84 bounds.

    Leaflet places an image overlay by its lat/lng corners but draws it in the map's own
    projection, which is Web Mercator. Handing it a UTM raster's corners would stretch the
    image; warping first is what makes the overlay land where the ground is.
    """
    from rasterio.warp import calculate_default_transform, reproject, transform_bounds

    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, "EPSG:3857", src.width, src.height, *src.bounds
        )
        scale = min(1.0, max_px / max(width, height))
        width, height = max(1, int(width * scale)), max(1, int(height * scale))
        transform, _, _ = calculate_default_transform(
            src.crs, "EPSG:3857", src.width, src.height, *src.bounds,
            dst_width=width, dst_height=height,
        )
        warped = np.full((height, width), np.nan, dtype="float32")
        reproject(
            source=rasterio.band(src, 1), destination=warped,
            src_transform=src.transform, src_crs=src.crs,
            dst_transform=transform, dst_crs="EPSG:3857",
            src_nodata=src.nodata, dst_nodata=np.nan,
        )
        west, south, east, north = transform_bounds("EPSG:3857", "EPSG:4326",
                                                    *rasterio.transform.array_bounds(
                                                        height, width, transform))
        if stretch is None:
            stretch = percentile_stretch(src_path)

    valid = np.isfinite(warped)
    scaled = np.clip((warped - stretch.low) / (stretch.high - stretch.low), 0.0, 1.0)
    rgb = _apply_palette(np.nan_to_num(scaled), palette)
    alpha = np.where(valid, 255, 0).astype("uint8")

    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.dstack([rgb, alpha]), mode="RGBA").save(
        dest, format="PNG", optimize=True
    )
    return dest, (west, south, east, north)
