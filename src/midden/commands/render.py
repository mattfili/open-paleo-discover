"""`midden render` — QGIS projects and self-contained artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from midden.aoi import get_aoi
from midden.config import settings
from midden.db import connect
from midden.render.artifact import render_artifact
from midden.render.core import DEFAULT_RASTERS, build_scene
from midden.render.qgis import render_qgis_project

render_app = typer.Typer(
    help="Render an AOI to a QGIS project or a self-contained HTML artifact.",
    no_args_is_help=True,
)


def _scene(aoi: str, kinds: str | None, visible: str | None, class_id: str | None):
    """Build a scene for an AOI, optionally restricting the layers."""
    selected = (
        tuple(k.strip() for k in kinds.split(",") if k.strip())
        if kinds
        else DEFAULT_RASTERS
    )
    with connect() as conn:
        return build_scene(
            conn, get_aoi(conn, aoi), kinds=selected, visible=visible, class_id=class_id
        )


@render_app.command("qgis")
def render_qgis(
    aoi: Annotated[str, typer.Option("--aoi", help="AOI slug.")],
    class_id: Annotated[
        str | None,
        typer.Option(
            "--class",
            help="Target class whose surfaces to show. Without it, "
            "class-qualified layers (score, detection renders) "
            "stay out of the scene.",
        ),
    ] = None,
    out: Annotated[
        Path | None, typer.Option("--out", help="Destination .qgs path.")
    ] = None,
    kinds: Annotated[
        str | None, typer.Option("--kinds", help="Comma-separated raster kinds.")
    ] = None,
) -> None:
    """Emit a QGIS project with the AOI's layers pre-loaded and styled.

    QGIS is the interactive surface for this project (spec.md §8). The project file embeds
    absolute paths, which is why *.qgs is gitignored.
    """
    scene = _scene(aoi, kinds, None, class_id)
    destination = out or settings().repo_root / "exports" / "qgis" / f"{aoi}.qgs"
    render_qgis_project(scene, destination)
    typer.secho(f"wrote {destination}", fg=typer.colors.GREEN)
    typer.echo(f"  {len(scene.rasters)} raster + {len(scene.vectors)} vector layer(s)")
    typer.echo("  open it with: open -a QGIS " + str(destination))


@render_app.command("map")
def render_map(
    aoi: Annotated[str, typer.Option("--aoi", help="AOI slug.")],
    class_id: Annotated[
        str | None,
        typer.Option(
            "--class",
            help="Target class whose surfaces to show. Without it, "
            "class-qualified layers stay out of the scene.",
        ),
    ] = None,
    out: Annotated[
        Path | None, typer.Option("--out", help="Destination .html path.")
    ] = None,
    kinds: Annotated[
        str | None, typer.Option("--kinds", help="Comma-separated raster kinds.")
    ] = None,
    visible: Annotated[
        str | None, typer.Option("--visible", help="Layer shown on open.")
    ] = None,
    max_px: Annotated[
        int, typer.Option("--max-px", help="Cap on each raster's long edge.")
    ] = 1500,
) -> None:
    """Export a single self-contained HTML file: no server, no tiles, no external CSS."""
    scene = _scene(aoi, kinds, visible, class_id)
    destination = out or settings().repo_root / "exports" / f"{aoi}.html"
    render_artifact(scene, destination, max_px=max_px)
    size = destination.stat().st_size
    typer.secho(f"wrote {destination}  ({size / 1e6:.2f} MB)", fg=typer.colors.GREEN)
    typer.echo(f"  {len(scene.rasters)} raster + {len(scene.vectors)} vector layer(s)")
