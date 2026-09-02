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

from midden.aoi import get_aoi
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



def midden_render_map(
    aoi: Annotated[str, Field(description="AOI slug.")],
    kinds: Annotated[
        list[str] | None,
        Field(description="Raster kinds to include. Defaults to whatever the AOI has."),
    ] = None,
    visible: Annotated[str | None, Field(description="Layer shown when the map opens.")] = None,
    max_px: Annotated[
        int, Field(description="Cap on each raster's long edge.", ge=256, le=2000)
    ] = 1200,
) -> dict:
    """Export the AOI as a single self-contained HTML file and return its path.

    No server, no tile requests, no external stylesheet: the artifact sandbox blocks all
    three. Leaflet's script loads from a CDN, its stylesheet is inlined, vector layers are
    inlined as GeoJSON, and rasters are base64 PNGs warped to Web Mercator so they land
    where the ground is.

    The file is written to disk rather than returned inline because it runs to megabytes.
    """
    from midden.config import settings
    from midden.render.artifact import render_artifact
    from midden.render.core import DEFAULT_RASTERS, build_scene

    selected = tuple(kinds) if kinds else DEFAULT_RASTERS
    with connect() as conn:
        scene = build_scene(conn, get_aoi(conn, aoi), kinds=selected, visible=visible)

    destination = settings().repo_root / "exports" / f"{aoi}.html"
    render_artifact(scene, destination, max_px=max_px)
    return {
        "aoi": aoi,
        "path": str(destination),
        "bytes": destination.stat().st_size,
        "raster_layers": [r.kind for r in scene.rasters],
        "vector_layers": [v.name for v in scene.vectors],
    }


def midden_render_qgis_project(
    aoi: Annotated[str, Field(description="AOI slug.")],
    kinds: Annotated[list[str] | None, Field(description="Raster kinds to include.")] = None,
) -> dict:
    """Emit a QGIS project with the AOI's layers pre-loaded and styled.

    QGIS is the interactive surface for this project: it reads the COGs windowed and with
    overviews straight off disk, with no tile server. This saves re-adding and re-styling
    a dozen layers at the start of every session.
    """
    from midden.config import settings
    from midden.render.core import DEFAULT_RASTERS, build_scene
    from midden.render.qgis import render_qgis_project

    selected = tuple(kinds) if kinds else DEFAULT_RASTERS
    with connect() as conn:
        scene = build_scene(conn, get_aoi(conn, aoi), kinds=selected)

    destination = settings().repo_root / "exports" / "qgis" / f"{aoi}.qgs"
    render_qgis_project(scene, destination)
    return {
        "aoi": aoi, "path": str(destination),
        "raster_layers": [r.kind for r in scene.rasters],
        "vector_layers": [v.name for v in scene.vectors],
    }


#: Tools that only read.
READ_TOOLS = (midden_preview_raster,)

#: Tools that write a file to disk.
WRITE_TOOLS = (midden_render_map, midden_render_qgis_project)


def register(mcp) -> None:
    """Attach this module's tools to a FastMCP server."""
    for tool in READ_TOOLS:
        mcp.tool(tool, annotations=READ_ONLY)
    for tool in WRITE_TOOLS:
        mcp.tool(tool)
