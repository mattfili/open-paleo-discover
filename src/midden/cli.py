"""midden command-line interface.

Sub-apps are registered as their milestones land, so every command listed in `--help`
actually runs. See spec.md §11.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Annotated

import typer

from midden import PROJECT_CRS
from midden.aoi import get_aoi, list_aois, seed_aois
from midden.commands.terrain import terrain_app
from midden.config import settings
from midden.db import (
    apply_schema,
    connect,
    crs_violations,
    fetch_all,
    inventory,
    set_read_only_password,
)
from midden.intake.drivers import registered_drivers
from midden.intake.runner import run_source
from midden.intake.schema import load_all_sources

app = typer.Typer(
    help="Archaeological site-predictive modelling for Middle Tennessee.",
    no_args_is_help=True,
    add_completion=False,
)

db_app = typer.Typer(help="Schema management and database inspection.", no_args_is_help=True)
app.add_typer(db_app, name="db")

aoi_app = typer.Typer(help="Areas of interest: seed and inspect.", no_args_is_help=True)
app.add_typer(aoi_app, name="aoi")

intake_app = typer.Typer(help="Fetch, transform, and load sources.", no_args_is_help=True)
app.add_typer(intake_app, name="intake")

app.add_typer(terrain_app, name="terrain")

#: WhiteboxTools tools the pipeline depends on and that this build must provide.
REQUIRED_WBT_TOOLS = [
    "BreachDepressionsLeastCost",
    "D8Pointer",
    "D8FlowAccumulation",
    "ExtractStreams",
    "ElevationAboveStream",
    "Slope",
    "Aspect",
    "MultidirectionalHillshade",
    "HorizonAngle",
]

#: Tools spec.md assumed were open core but are not, checked so the absence is stated
#: rather than discovered halfway through M2.
#:
#: `Openness` is the one that matters. It is absent from WhiteboxTools v2.4.0 open core —
#: the binary answers `Unrecognized tool name Openness` — yet the Python wrapper still
#: exposes an `openness()` method, because the wrapper is generated from the full manual
#: including paid Whitebox Toolset Extension tools. A bare call would return a non-zero
#: code and write nothing, which is exactly the silent failure the whiteboxtools skill
#: warns about. midden computes openness itself; see terrain/detection.py.
ABSENT_WBT_TOOLS = ["Openness", "SkyViewFactor"]


@db_app.command("init")
def db_init() -> None:
    """Apply the numbered DDL files and set the read-only role's password."""
    config = settings()
    with connect(config) as conn:
        applied = apply_schema(conn, config.sql_dir)
        set_read_only_password(conn, config)
    for name in applied:
        typer.echo(f"applied {name}")
    typer.echo(f"read-only role {config.midden_ro_user} password set from .env")


@db_app.command("check")
def db_check() -> None:
    """Report extensions, schemas, tables, roles, and verify the project CRS."""
    with connect() as conn:
        snapshot = inventory(conn)

    for key in ("extensions", "schemas", "tables", "roles"):
        typer.echo(f"\n[{key}]")
        for row in snapshot[key]:
            typer.echo("  " + "  ".join(str(v) for v in row.values()))

    geometry = snapshot["geometry_columns"]
    violations = crs_violations(geometry)
    typer.echo(f"\n[geometry_columns] {len(geometry)} column(s)")
    for row in geometry:
        typer.echo(
            f"  {row['f_table_schema']}.{row['f_table_name']}."
            f"{row['f_geometry_column']} srid={row['srid']}"
        )
    if violations:
        typer.secho(
            f"\nFAIL: {len(violations)} geometry column(s) are not {PROJECT_CRS} "
            f"and are not named *_wgs84.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    typer.secho(f"\nOK: every geometry column is {PROJECT_CRS} or an explicit *_wgs84 export.",
                fg=typer.colors.GREEN)


@aoi_app.command("seed")
def aoi_seed() -> None:
    """Seed derived.aoi from the authoritative boundary services.

    Idempotent, and re-running deliberately refreshes geometry from the agency that owns
    the boundary rather than from anything stored here.
    """
    with connect() as conn:
        results = seed_aois(conn)
    for slug, action, repaired in results:
        note = "  (geometry repaired: source polygon was invalid)" if repaired else ""
        typer.echo(f"{action:>8}  {slug}{note}")
    typer.secho(f"\n{len(results)} AOI(s) seeded.", fg=typer.colors.GREEN)


@aoi_app.command("list")
def aoi_list(
    role: Annotated[str | None, typer.Option(help="Filter by role.")] = None,
) -> None:
    """List AOIs with area and role."""
    with connect() as conn:
        aois = list_aois(conn, role=role)
    if not aois:
        typer.secho("No AOIs. Run: midden aoi seed", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)
    typer.echo(f"{'slug':<24}{'role':<20}{'km2':>9}  name")
    typer.echo("-" * 88)
    for a in aois:
        typer.echo(f"{a.slug:<24}{a.role:<20}{a.area_km2:>9.3f}  {a.name}")


@aoi_app.command("show")
def aoi_show(slug: str) -> None:
    """Show one AOI's extent and geometry summary."""
    with connect() as conn:
        a = get_aoi(conn, slug)
    xmin, ymin, xmax, ymax = a.bounds
    typer.echo(f"slug       {a.slug}\nname       {a.name}\nkind/role  {a.kind} / {a.role}")
    typer.echo(f"area       {a.area_km2:.4f} km2")
    typer.echo(f"extent     {xmin:.0f} {ymin:.0f} {xmax:.0f} {ymax:.0f}  ({PROJECT_CRS})")
    typer.echo(f"span       {xmax - xmin:.0f} x {ymax - ymin:.0f} m")
    typer.echo(f"source     {a.source}")


@intake_app.command("run")
def intake_run(
    source: Annotated[str | None, typer.Argument(help="Source name, or omit with --all.")] = None,
    aoi: Annotated[str | None, typer.Option("--aoi", help="AOI slug to scope the fetch.")] = None,
    all_sources: Annotated[bool, typer.Option("--all", help="Run every source.")] = False,
    force: Annotated[bool, typer.Option("--force", help="Re-fetch even if cached.")] = False,
) -> None:
    """Run a source's intake for an AOI."""
    config = settings()
    available = load_all_sources(config.sources_dir)
    if all_sources:
        chosen = list(available.values())
    elif source:
        if source not in available:
            typer.secho(
                f"No source {source!r}. Available: {', '.join(available) or '(none)'}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        chosen = [available[source]]
    else:
        typer.secho("Name a source or pass --all.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    with connect(config) as conn:
        for spec in chosen:
            result = run_source(conn, spec, aoi, config=config, force=force)
            state = "cached fetch" if result.cached else "fetched"
            typer.secho(
                f"{result.source}: {state}, loaded {result.rows} row(s) into "
                f"{result.target} (derivation {result.derivation_id})",
                fg=typer.colors.GREEN,
            )


@intake_app.command("status")
def intake_status() -> None:
    """Show each defined source, its target, and its most recent run."""
    config = settings()
    sources = load_all_sources(config.sources_dir)
    if not sources:
        typer.secho(f"No source YAML in {config.sources_dir}", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    with connect(config) as conn:
        recent = {
            r["operation"]: r
            for r in fetch_all(
                conn,
                """
                SELECT DISTINCT ON (operation) operation, status, started_at, aoi_id
                FROM derived.derivation
                WHERE operation LIKE 'intake.%'
                ORDER BY operation, started_at DESC
                """,
            )
        }

    typer.echo(f"{'source':<20}{'driver':<14}{'target':<24}{'last run':<22}status")
    typer.echo("-" * 92)
    for name, spec in sources.items():
        last = recent.get(f"intake.{name}")
        when = last["started_at"].strftime("%Y-%m-%d %H:%M:%S") if last else "-"
        status = last["status"] if last else "never run"
        typer.echo(f"{name:<20}{spec.fetch.driver:<14}{spec.load.target:<24}{when:<22}{status}")
    typer.echo(f"\nregistered drivers: {', '.join(registered_drivers())}")


@app.command()
def doctor(
    check_whitebox: Annotated[
        bool,
        typer.Option(
            "--whitebox/--no-whitebox",
            help="Import whitebox and verify the required tools. Downloads ~100 MB on "
            "first run.",
        ),
    ] = True,
) -> None:
    """Verify the environment: database, PDAL CLI, and the WhiteboxTools tool set."""
    failures: list[str] = []

    config = settings()
    try:
        with connect(config) as conn:
            version = conn.execute("SELECT postgis_version()").fetchone()
        typer.secho(f"OK   postgres reachable, postgis {version['postgis_version']}",
                    fg=typer.colors.GREEN)
    except Exception as exc:  # noqa: BLE001 - reported, not raised, so doctor lists everything
        failures.append(f"postgres: {exc}")
        typer.secho(f"FAIL postgres: {exc}", fg=typer.colors.RED)

    # PDAL is called as a subprocess, never through the Python bindings (CLAUDE.md).
    pdal = shutil.which("pdal")
    if pdal:
        out = subprocess.run([pdal, "--version"], capture_output=True, text=True, check=False)
        typer.secho(f"OK   pdal CLI: {out.stdout.strip() or out.stderr.strip()}",
                    fg=typer.colors.GREEN)
    else:
        failures.append("pdal not on PATH (brew install pdal)")
        typer.secho("FAIL pdal not on PATH — brew install pdal", fg=typer.colors.RED)

    if check_whitebox:
        failures.extend(_check_whitebox())

    if failures:
        typer.secho(f"\n{len(failures)} check(s) failed.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho("\nAll checks passed.", fg=typer.colors.GREEN)


def _check_whitebox() -> list[str]:
    """Verify the WhiteboxTools build exposes every tool the pipeline needs.

    Returns a list of failure messages, empty when the build is complete. Openness must be
    open core; if this build lacks it, the detection chain cannot be built on it and the
    fallback is a horizon scan, not SkyViewFactor.
    """
    from midden.skills import load

    helpers = load("whiteboxtools", "wbt_helpers")
    try:
        wbt = helpers.make_wbt()
        helpers.require_tools(wbt, REQUIRED_WBT_TOOLS)
    except Exception as exc:  # noqa: BLE001 - surfaced as a doctor failure line
        typer.secho(f"FAIL whitebox: {exc}", fg=typer.colors.RED)
        return [f"whitebox: {exc}"]

    typer.secho(
        f"OK   whitebox {wbt.version().splitlines()[0].strip()} — "
        f"all {len(REQUIRED_WBT_TOOLS)} required tools present",
        fg=typer.colors.GREEN,
    )

    available = {k.lower().replace("_", "") for k in wbt.list_tools()}
    for tool in ABSENT_WBT_TOOLS:
        present = tool.lower().replace("_", "") in available
        typer.secho(
            f"{'NOTE' if present else 'INFO'} {tool} "
            + (
                "is present in this build after all — revisit terrain/detection.py."
                if present
                else "absent from open core, as expected; midden computes it directly."
            ),
            fg=typer.colors.YELLOW if present else typer.colors.BLUE,
        )
    return []


if __name__ == "__main__":
    app()
