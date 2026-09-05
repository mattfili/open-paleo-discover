"""`midden histmap` — historic quad sheets: search, fetch, tile, and load labels."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from midden.aoi import get_aoi
from midden.config import settings
from midden.db import connect, fetch_all
from midden.histmap import (
    fetch_sheet,
    get_sheet,
    load_sites,
    search_sheets,
    tile_sheet,
)

histmap_app = typer.Typer(
    help="Historic USGS topo quads: the label source for ref.control_sites (ROADMAP A1).",
    no_args_is_help=True,
)


@histmap_app.command("search")
def histmap_search(
    aoi: Annotated[
        str, typer.Option("--aoi", help="AOI slug the sheet must intersect.")
    ],
) -> None:
    """List HTMC sheets covering an AOI, oldest edition first.

    Only sheets with a GeoTIFF download appear; GeoPDF-only editions are skipped.
    """
    with connect() as conn:
        area = get_aoi(conn, aoi)
    sheets = search_sheets(area)
    if not sheets:
        typer.secho(f"No HTMC GeoTIFF sheets intersect {aoi}.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)
    typer.echo(f"{'sheet_id':<38}{'cell':<20}{'year':<6}scale")
    typer.echo("-" * 76)
    for s in sheets:
        typer.echo(f"{s.sheet_id:<38}{s.cell_name:<20}{s.map_year:<6}1:{s.scale}")


@histmap_app.command("fetch")
def histmap_fetch(
    sheet_id: Annotated[
        str, typer.Argument(help="sheet_id from `midden histmap search`.")
    ],
    aoi: Annotated[
        str,
        typer.Option(
            "--aoi",
            help="AOI used to re-run the search that "
            "locates this sheet's download URL.",
        ),
    ],
) -> None:
    """Download one sheet, warp it to EPSG:26916, COG it, and catalogue it."""
    with connect() as conn:
        area = get_aoi(conn, aoi)
        matches = [s for s in search_sheets(area) if s.sheet_id == sheet_id]
        if not matches:
            typer.secho(
                f"Sheet {sheet_id!r} not found over {aoi}; run `midden histmap search "
                f"--aoi {aoi}` and copy a sheet_id from it.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        path = fetch_sheet(conn, matches[0], config=settings())
        row = get_sheet(conn, sheet_id)
    typer.secho(f"catalogued {sheet_id}", fg=typer.colors.GREEN)
    typer.echo(f"  {row['cell_name']} {row['map_year']} 1:{row['scale']}")
    typer.echo(
        f"  positional confidence {row['positional_confidence_m']} m "
        f"(NMAS for the scale + georeferencing margin)"
    )
    typer.echo(f"  -> {path}")


@histmap_app.command("list")
def histmap_list() -> None:
    """List catalogued sheets and how many control points each has produced."""
    with connect() as conn:
        rows = fetch_all(
            conn,
            """
            SELECT s.sheet_id, s.cell_name, s.map_year, s.scale,
                   s.positional_confidence_m,
                   count(c.site_id) AS points
            FROM ref.histmap_sheet s
            LEFT JOIN ref.control_sites c ON c.source_sheet = s.sheet_id
            GROUP BY s.sheet_id ORDER BY s.map_year, s.sheet_id
            """,
        )
    if not rows:
        typer.secho(
            "No sheets catalogued. Run: midden histmap fetch", fg=typer.colors.YELLOW
        )
        raise typer.Exit(code=1)
    typer.echo(
        f"{'sheet_id':<38}{'cell':<20}{'year':<6}{'scale':<9}{'conf_m':<8}points"
    )
    typer.echo("-" * 92)
    for r in rows:
        typer.echo(
            f"{r['sheet_id']:<38}{r['cell_name']:<20}{r['map_year']:<6}"
            f"1:{r['scale']:<7}{r['positional_confidence_m']:<8}{r['points']}"
        )


@histmap_app.command("tiles")
def histmap_tiles(
    sheet_id: Annotated[str, typer.Argument(help="Catalogued sheet_id.")],
    out: Annotated[Path | None, typer.Option("--out", help="Tile directory.")] = None,
) -> None:
    """Cut a sheet into PNG tiles (plus index.json) for visual digitization."""
    with connect() as conn:
        row = get_sheet(conn, sheet_id)
    destination = out or settings().data_dir / "histmap_tiles" / sheet_id
    tile_sheet(Path(row["path"]), destination)
    n = len(list(destination.glob("*.png")))
    typer.secho(f"wrote {n} tile(s) -> {destination}", fg=typer.colors.GREEN)
    typer.echo("  index.json maps each tile to its affine transform (EPSG:26916)")


@histmap_app.command("load-sites")
def histmap_load_sites(
    sheet_id: Annotated[
        str, typer.Argument(help="Catalogued sheet_id the points came from.")
    ],
    geojson: Annotated[
        Path,
        typer.Argument(
            help="GeoJSON of Point features in EPSG:26916 "
            "with properties class_id and name."
        ),
    ],
    method: Annotated[
        str,
        typer.Option(
            "--method",
            help="How the points were digitized; recorded in "
            "provenance (e.g. claude-vision, by-hand).",
        ),
    ] = "claude-vision",
) -> None:
    """Load digitized symbols into ref.control_sites, provenance attached.

    Points land as review_status='unreviewed'; re-loading a sheet replaces its
    unreviewed points and leaves confirmed/rejected rows alone.
    """
    with connect() as conn:
        count = load_sites(conn, sheet_id, geojson, method=method)
    typer.secho(
        f"loaded {count} point(s) from {geojson} for {sheet_id}", fg=typer.colors.GREEN
    )
    typer.echo(
        "  review_status=unreviewed; positional confidence inherited from the sheet"
    )
