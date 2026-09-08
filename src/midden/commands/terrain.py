"""`midden terrain` — derive, inspect, and preview terrain rasters."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from midden.aoi import get_aoi
from midden.config import settings
from midden.db import connect
from midden.terrain.cog import list_assets
from midden.terrain.params import PARAMETERS
from midden.terrain.run import run_detection_grid, run_model_grid

terrain_app = typer.Typer(
    help="Terrain derivation on the modelling (10 m) and detection (0.5 m) grids.",
    no_args_is_help=True,
)

#: Guard on synchronous work (spec.md §9). A detection-grid run scales with area at
#: 0.5 m — four million cells per square kilometre — so a large AOI is refused with a
#: suggestion rather than left to hang.
MAX_DETECTION_KM2 = 25.0


def _check_detection_preflight(
    area, ept_project: str | None, max_area_km2: float
) -> None:
    """Refuse a detection run that cannot work, with the next action rather than a hang."""
    # --ept-project is now a PREFERENCE, not a requirement: coverage is resolved from
    # the published boundary index (Middle TN splits across B1/B2 plus county and
    # 2011 collections, and the ept.json cube bounds do not describe footprints).
    # An unresolvable AOI fails later with the candidates it actually tried.
    if area.area_km2 > max_area_km2:
        typer.secho(
            f"AOI {area.slug} is {area.area_km2:.1f} km2, over the {max_area_km2:g} km2 "
            f"detection limit (~{area.area_km2 * 4:.0f}M cells at 0.5 m). "
            f"Raise --max-area if you mean it, or split the AOI.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


@terrain_app.command("run")
def terrain_run(
    aoi: Annotated[str, typer.Option("--aoi", help="AOI slug.")],
    grid: Annotated[
        str, typer.Option("--grid", help="'model' (10 m) or 'detection' (0.5 m).")
    ] = "model",
    class_id: Annotated[
        str | None,
        typer.Option(
            "--class",
            help="Target class whose registry parameters the detection "
            "chain runs with; required for --grid detection. "
            "See `midden classes`.",
        ),
    ] = None,
    ept_project: Annotated[
        str | None,
        typer.Option(
            "--ept-project", help="EPT project name; required for --grid detection."
        ),
    ] = None,
    max_area_km2: Annotated[
        float,
        typer.Option("--max-area", help="Refuse a detection run larger than this."),
    ] = MAX_DETECTION_KM2,
) -> None:
    """Derive terrain for an AOI on one grid and register the outputs as COGs."""
    config = settings()
    with connect(config) as conn:
        area = get_aoi(conn, aoi)

        if grid == "detection":
            if class_id is None:
                typer.secho(
                    "--grid detection needs --class: detection parameters are per class, "
                    "never global. List classes with `midden classes`.",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)
            _check_detection_preflight(area, ept_project, max_area_km2)
            # Seam-aware, same as validate: a project's ept.json bounds are the
            # enclosing cube, not its footprint, so an explicit --ept-project is a
            # PREFERENCE. Candidates come from the published coverage index and are
            # tried in order; without this a covered AOI reports "no points".
            from midden.terrain.coverage import covering_projects
            from midden.terrain.dem import buffered_bounds

            candidates = covering_projects(
                buffered_bounds(area, 50.0), config.raw_dir, prefer=ept_project
            ) or [ept_project]
            if candidates[0] != ept_project:
                typer.secho(
                    f"note: {ept_project} does not cover {area.slug}; "
                    f"trying {candidates}",
                    fg=typer.colors.YELLOW,
                )
            result = None
            failures = []
            for candidate in candidates:
                try:
                    result = run_detection_grid(
                        conn,
                        area,
                        ept_project=candidate,
                        class_id=class_id,
                        config=config,
                    )
                    break
                except RuntimeError as exc:
                    failures.append(f"{candidate}: {str(exc).splitlines()[0]}")
            if result is None:
                typer.secho(
                    "no covering EPT project produced points:\n  "
                    + "\n  ".join(failures),
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)
        elif grid == "model":
            result = run_model_grid(conn, area, config=config)
        else:
            typer.secho(
                f"Unknown grid {grid!r}; expected 'model' or 'detection'.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

    typer.secho(
        f"\n{result.aoi_slug} / {result.grid}: {len(result.assets)} asset(s) "
        f"(derivation {result.derivation_id})",
        fg=typer.colors.GREEN,
    )
    for kind, path in result.paths.items():
        typer.echo(f"  {kind:<16} {path}")
    if result.diagnostics:
        typer.echo("\nHAND diagnostics:")
        for key, value in result.diagnostics.items():
            typer.echo(f"  {key}: {value}")


@terrain_app.command("list")
def terrain_list(
    aoi: Annotated[
        str | None, typer.Option("--aoi", help="Filter by AOI slug.")
    ] = None,
    kind: Annotated[
        str | None, typer.Option("--kind", help="Filter by raster kind.")
    ] = None,
) -> None:
    """List catalogued raster assets."""
    with connect() as conn:
        aoi_id = get_aoi(conn, aoi).id if aoi else None
        rows = list_assets(conn, aoi_id=aoi_id, kind=kind)
    if not rows:
        typer.secho(
            "No raster assets. Run: midden terrain run --aoi <slug>",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)
    typer.echo(f"{'aoi':<22}{'kind':<16}{'grid':<11}{'res':>6}  {'variant':<11}path")
    typer.echo("-" * 110)
    for r in rows:
        typer.echo(
            f"{r['aoi']:<22}{r['kind']:<16}{r['grid']:<11}{r['resolution_m']:>6.2f}  "
            f"{(r['variant'] or '-'):<11}{r['path']}"
        )


@terrain_app.command("preview")
def terrain_preview(
    aoi: Annotated[str, typer.Option("--aoi", help="AOI slug.")],
    kind: Annotated[str, typer.Option("--kind", help="Raster kind.")] = "openness_pos",
    variant: Annotated[
        str | None,
        typer.Option(
            "--variant",
            help="Asset variant (class id, or class-digest for a "
            "sweep). Required when several are catalogued.",
        ),
    ] = None,
    out: Annotated[Path | None, typer.Option("--out", help="PNG path.")] = None,
    max_px: Annotated[
        int, typer.Option("--max-px", help="Cap on the long edge.")
    ] = 1500,
) -> None:
    """Render a catalogued raster to a PNG you can look at."""
    from midden.render.preview import openness_stretch, percentile_stretch, to_png

    with connect() as conn:
        area = get_aoi(conn, aoi)
        rows = list_assets(conn, aoi_id=area.id, kind=kind)
    if not rows:
        typer.secho(f"No {kind!r} raster for {aoi}.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if variant is not None:
        rows = [r for r in rows if (r["variant"] or "") == variant]
    variants = sorted({r["variant"] or "" for r in rows})
    if len(variants) > 1:
        # Rendering an arbitrary variant would show one class's parameters under an
        # unlabelled preview; make the choice explicit instead.
        typer.secho(
            f"{aoi}/{kind} has {len(variants)} variants: "
            f"{[v or '(unqualified)' for v in variants]}. Pass --variant.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    if not rows:
        typer.secho(
            f"No {kind!r} raster with variant {variant!r} for {aoi}.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    chosen = rows[0]["variant"] or ""
    source = Path(rows[0]["path"])
    suffix = f"_{chosen}" if chosen else ""
    dest = out or settings().repo_root / "exports" / f"{aoi}_{kind}{suffix}.png"
    # Openness is meaningful in absolute degrees around 90, so it gets a fixed window
    # rather than a per-image percentile stretch that would make a sweep incomparable.
    stretch = (
        openness_stretch()
        if kind.startswith("openness")
        else percentile_stretch(source)
    )
    to_png(source, dest, stretch=stretch, max_px=max_px)
    typer.secho(
        f"wrote {dest}  (variant {chosen or '(unqualified)'}, "
        f"stretch {stretch.low:.2f}..{stretch.high:.2f})",
        fg=typer.colors.GREEN,
    )


@terrain_app.command("zones")
def terrain_zones(
    aoi: Annotated[str, typer.Option("--aoi", help="AOI slug.")],
    class_id: Annotated[
        str, typer.Option("--class", help="Detection class to promote.")
    ],
) -> None:
    """Promote a class's detection clusters to candidate zones (the cascade stage).

    Applies the SAME firing rule validation uses, across the whole raster instead of
    at labelled points, and writes what qualifies to derived.candidate_zone — which
    is what makes a detection usable as a survey candidate and as an evidence layer
    for classes that cannot be detected directly.
    """
    from midden.detect_zones import detect_zones
    from midden.registry import get_class

    with connect() as conn:
        area = get_aoi(conn, aoi)
        cls = get_class(conn, class_id)
        result = detect_zones(conn, area, cls, config=settings())

    typer.secho(
        f"{result['aoi']} / {result['class_id']}: {result['zones']} zone(s), "
        f"{result['total_area_m2']:,} m2 (derivation {result['derivation_id']})",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"  surface {result['surface']} ({result['tail']} tail)")
    typer.echo(
        "  Threshold is AOI-wide here, not a local annulus as in validation: a zone "
        "clears the percentile for THIS raster, so the number is a statement about "
        "this AOI. Zones are candidates, never findings."
    )


@terrain_app.command("params")
def terrain_params() -> None:
    """Show the named parameters, their defaults, and why each is contested."""
    typer.echo(f"{'derivation':<20}{'parameter':<24}{'default':>10} {'unit':<9}grid")
    typer.echo("-" * 84)
    for p in PARAMETERS:
        typer.echo(
            f"{p.derivation:<20}{p.name:<24}{p.default!s:>10} {p.unit:<9}{p.grid or '-'}"
        )
        typer.echo(f"{'':20}{p.why}")
    typer.echo(
        "\nDetection-grid rows are the parameter schema only: the values a detection run "
        "actually uses come from ref.target_class per class (`midden classes`), never "
        "from these defaults."
    )
