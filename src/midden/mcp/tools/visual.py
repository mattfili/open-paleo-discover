"""Visual MCP tools: return a raster as an image the model can actually look at.

spec.md §9 calls `midden_preview_raster` "the one that makes the AI genuinely useful
rather than decorative", and it is right: FastMCP can return image content blocks, so a
model can look at a positive-openness render of a terrace and say there is a rectilinear
anomaly at the northeast edge that does not match the surrounding drainage.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

from fastmcp.utilities.types import Image
from pydantic import Field

from midden.db import connect
from midden.mcp.tools.spatial import _resolve_raster
from midden.render.preview import openness_stretch, percentile_stretch, to_png

READ_ONLY = {"readOnlyHint": True}

#: How openness renders are read. Repeated here because it is the single most
#: consequential thing to get right when looking at one.
_OPENNESS_LEGEND = (
    "Bright is HIGH. In openness_pos, bright = CONVEX (mounds, charcoal hearths, ridges). "
    "In openness_neg, bright = CONCAVE (pits, ditches, relict channels, cut earthworks). "
    "Mid-grey is 90 degrees, which is flat ground regardless of its slope."
)


def midden_preview_raster(
    aoi: Annotated[str, Field(description="AOI slug.")],
    kind: Annotated[
        str,
        Field(description="Raster kind: openness_pos, openness_neg, slrm, hand, "
                          "slope, dem, hillshade_multi, ground_count."),
    ] = "openness_pos",
    max_px: Annotated[
        int, Field(description="Cap on the long edge in pixels.", ge=64, le=2000)
    ] = 1200,
    variant: Annotated[str | None, Field(description="Sweep variant digest.")] = None,
) -> list:
    """Render a catalogued raster to a PNG and return it as an image to look at.

    Openness rasters use a display window fixed on 90 degrees rather than a
    per-image percentile stretch, so two renders in a sweep stay directly comparable.
    Everything else gets a 2-98 percentile stretch.
    """
    with connect() as conn:
        row = _resolve_raster(conn, aoi, kind, variant)

    source = Path(row["path"])
    stretch = (
        openness_stretch() if kind.startswith("openness") else percentile_stretch(source)
    )
    with tempfile.TemporaryDirectory() as directory:
        destination = Path(directory) / f"{aoi}_{kind}.png"
        to_png(source, destination, stretch=stretch, max_px=max_px)
        image = Image(path=destination)
        block = image.to_image_content()

    legend = _OPENNESS_LEGEND if kind.startswith("openness") else (
        "Bright is high, dark is low, within a 2-98 percentile stretch."
    )
    caption = (
        f"{aoi} / {kind} at {row['resolution_m']:g} m ({row['grid']} grid). "
        f"Display range {stretch.low:.2f} to {stretch.high:.2f}. {legend}"
    )
    return [caption, block]


#: Tools that only read. Marked readOnlyHint so a client can reason about
#: which calls are safe to retry or run speculatively.
READ_TOOLS = (midden_preview_raster,)

#: Tools that fetch from a network service, write rasters, or insert rows.
WRITE_TOOLS = ()


def register(mcp) -> None:
    """Attach this module's tools to a FastMCP server."""
    for tool in READ_TOOLS:
        mcp.tool(tool, annotations=READ_ONLY)
    for tool in WRITE_TOOLS:
        mcp.tool(tool)
