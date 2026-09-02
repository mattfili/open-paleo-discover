"""Compute MCP tools: create AOIs, run intake, derive terrain, and sweep parameters.

These are the write side. None of them carries `readOnlyHint`, because each one fetches
from a network service, writes rasters to disk, or inserts rows.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from midden.aoi import get_aoi
from midden.config import settings
from midden.db import connect
from midden.derivation import param_variant
from midden.intake.runner import run_source
from midden.intake.schema import load_all_sources
from midden.terrain.params import PARAMETERS, defaults_for, resolve
from midden.terrain.run import run_detection_grid, run_model_grid

READ_ONLY = {"readOnlyHint": True}

#: Detection-grid work scales with area at four million cells per square kilometre, so a
#: large AOI is refused with a suggestion rather than left to hang (spec.md §9).
MAX_DETECTION_KM2 = 25.0

#: The EPT project covering all four Middle Tennessee control AOIs.
DEFAULT_EPT_PROJECT = "USGS_LPC_TN_Middle_B1_2018_LAS_2019"


def midden_list_parameters(
    derivation: Annotated[
        str | None,
        Field(description="Filter to one derivation, e.g. terrain.openness."),
    ] = None,
) -> dict[str, Any]:
    """List the named parameters for terrain derivations, with defaults and rationale.

    Every judgment call in this project is a parameter rather than a decision, so that
    two runs are comparable and the choice is recorded in derivation.params. Distances
    are declared in metres and converted to grid cells against whichever raster is
    being processed.
    """
    selected = [p for p in PARAMETERS if derivation is None or p.derivation == derivation]
    if derivation and not selected:
        raise ValueError(
            f"No parameters for {derivation!r}. Known derivations: "
            f"{sorted({p.derivation for p in PARAMETERS})}"
        )
    return {
        "parameters": [
            {
                "derivation": p.derivation, "name": p.name, "default": p.default,
                "unit": p.unit, "grid": p.grid, "why_contested": p.why,
            }
            for p in selected
        ]
    }


def midden_run_intake(
    source: Annotated[str, Field(description="Source name from midden_list_sources.")],
    aoi: Annotated[str, Field(description="AOI slug to scope the fetch.")],
    force: Annotated[bool, Field(description="Re-fetch even if the cache is warm.")] = False,
) -> dict[str, Any]:
    """Fetch, transform, and load one source for an AOI.

    Fetches are cached by content hash of (driver, params, AOI geometry), so a re-run
    with unchanged inputs reuses the cached file and only re-runs transform and load.
    """
    config = settings()
    sources = load_all_sources(config.sources_dir)
    if source not in sources:
        raise ValueError(
            f"No source {source!r}. Available: {sorted(sources)}. "
            f"Sources are YAML files in {config.sources_dir}."
        )
    with connect(config) as conn:
        result = run_source(conn, sources[source], aoi, config=config, force=force)
    return {
        "source": result.source, "aoi": result.aoi_slug, "rows_loaded": result.rows,
        "target": result.target, "used_cached_fetch": result.cached,
        "derivation_id": result.derivation_id,
    }


def midden_derive_terrain(
    aoi: Annotated[str, Field(description="AOI slug.")],
    grid: Annotated[
        str, Field(description="'model' (10 m, hydrology and HAND) or "
                               "'detection' (0.5 m, openness and SLRM).")
    ] = "model",
    ept_project: Annotated[
        str | None,
        Field(description="EPT project for the detection grid. Defaults to the one "
                          "covering all four Middle TN control AOIs."),
    ] = None,
    max_area_km2: Annotated[
        float, Field(description="Refuse a detection run larger than this.", gt=0)
    ] = MAX_DETECTION_KM2,
) -> dict[str, Any]:
    """Derive terrain for an AOI on one grid and catalog the outputs as COGs.

    Synchronous, and minutes-long on a detection grid. The modelling grid gives
    hydrology, HAND, slope and streams; the detection grid gives the renders you look
    at. They are separate because a model fitted at 0.5 m is noise and feature
    detection at 10 m is blind.
    """
    config = settings()
    with connect(config) as conn:
        area = get_aoi(conn, aoi)
        if grid == "model":
            result = run_model_grid(conn, area, config=config)
        elif grid == "detection":
            if area.area_km2 > max_area_km2:
                raise ValueError(
                    f"AOI {aoi} is {area.area_km2:.1f} km2, over the "
                    f"{max_area_km2:g} km2 detection limit "
                    f"(~{area.area_km2 * 4:.0f}M cells at 0.5 m). Raise max_area_km2 "
                    f"if you mean it, or split the AOI."
                )
            result = run_detection_grid(
                conn, area, ept_project=ept_project or DEFAULT_EPT_PROJECT, config=config
            )
        else:
            raise ValueError(f"Unknown grid {grid!r}; expected 'model' or 'detection'.")

    return {
        "aoi": result.aoi_slug, "grid": result.grid,
        "assets": {k: str(v) for k, v in result.paths.items()},
        "derivation_id": result.derivation_id,
        "hand_diagnostics": result.diagnostics or None,
    }


def midden_create_aoi(
    slug: Annotated[str, Field(description="Stable identifier, kebab-case.")],
    name: Annotated[str, Field(description="Human-readable name.")],
    wkt: Annotated[
        str,
        Field(description="Polygon or MultiPolygon as WKT in EPSG:26916 metres."),
    ],
    role: Annotated[
        str, Field(description="prospect | control_positive | control_detection | shakeout")
    ] = "prospect",
    kind: Annotated[
        str, Field(description="state_park | metro_park | county | watershed | custom")
    ] = "custom",
) -> dict[str, Any]:
    """Create an AOI from WKT geometry in the project CRS.

    Prefer seeding from an authoritative boundary service where one exists — spec.md
    §2 is explicit that unit boundaries and spellings should come from the agency that
    owns them, not from a hand-entered extent. Use this for a derived or ad-hoc area
    that no service publishes, such as a reservoir drawdown zone.

    Geometry is EPSG:26916 (NAD83 / UTM 16N) in metres, and is repaired if the polygon
    is invalid — PostGIS does not raise on an invalid polygon, it silently returns
    wrong areas and wrong intersections.
    """
    import shapely

    from midden.aoi import SeedSpec, to_multipolygon, upsert_aoi

    geometry = shapely.from_wkt(wkt)
    multipolygon, repaired = to_multipolygon(geometry, slug=slug)
    spec = SeedSpec(
        slug=slug, name=name, county="", kind=kind, role=role,
        layer="midden_create_aoi (supplied WKT)", where="",
    )
    with connect() as conn:
        action = upsert_aoi(conn, spec, multipolygon)
        area = get_aoi(conn, slug)
    return {
        "slug": area.slug, "action": action, "role": area.role,
        "area_km2": round(area.area_km2, 4),
        "geometry_repaired": repaired,
        "bounds_utm16n": [round(v) for v in area.bounds],
    }


def _check_sweepable(derivation: str, parameter: str) -> None:
    """Reject a sweep that cannot run, naming what would work instead."""
    if derivation not in {"terrain.openness", "terrain.slrm"}:
        raise ValueError(
            f"Sweeping {derivation!r} is not supported yet; the detection derivations "
            f"terrain.openness and terrain.slrm are."
        )
    known = defaults_for(derivation)
    if parameter not in known:
        raise ValueError(f"{derivation} has no parameter {parameter!r}. Known: {sorted(known)}.")


def midden_sweep(  # cq-allow: 53 lines, of which 30 are logic; the remainder is the
    # Annotated signature and docstring. The docstring carries the tuning discipline
    # (sweep a control, never a prospect), which is the point of the tool.
    aoi: Annotated[str, Field(description="AOI slug. Use a control, not a prospect.")],
    values: Annotated[
        list[float], Field(description="Values to sweep, e.g. [5, 10, 20].", min_length=1)
    ],
    derivation: Annotated[
        str, Field(description="terrain.openness or terrain.slrm.")
    ] = "terrain.openness",
    parameter: Annotated[
        str, Field(description="Parameter name, e.g. search_radius_m.")
    ] = "search_radius_m",
    ept_project: Annotated[str | None, Field(description="EPT project override.")] = None,
) -> dict[str, Any]:
    """Run a detection derivation across a parameter range, one asset per value.

    Each value gets its own derivation row and its own raster_asset, tagged with a
    variant digest, so the outputs are addressable by the parameters that produced
    them rather than merely different. Follow with midden_preview_raster on each
    variant and compare.

    Sweep against a control AOI. Tuning against a prospect, where there is no ground
    truth, is how a parameter gets fitted to noise.
    """
    if derivation not in {"terrain.openness", "terrain.slrm"}:
        raise ValueError(
            f"Sweeping {derivation!r} is not supported yet; the detection derivations "
            f"terrain.openness and terrain.slrm are."
        )
    known = defaults_for(derivation)
    if parameter not in known:
        raise ValueError(
            f"{derivation} has no parameter {parameter!r}. Known: {sorted(known)}."
        )

    group = "openness" if derivation == "terrain.openness" else "slrm"
    config = settings()
    results = []
    with connect(config) as conn:
        area = get_aoi(conn, aoi)
        for value in values:
            overrides = {group: {parameter: value}}
            result = run_detection_grid(
                conn, area, ept_project=ept_project or DEFAULT_EPT_PROJECT,
                overrides=overrides, config=config,
            )
            merged = resolve(derivation, {parameter: value})
            results.append({
                "value": value,
                "variant": param_variant({**merged, "grid": "detection"}),
                "derivation_id": result.derivation_id,
                "assets": {k: str(v) for k, v in result.paths.items()},
            })
    return {"aoi": aoi, "derivation": derivation, "parameter": parameter, "runs": results}


#: Tools that only read. Marked readOnlyHint so a client can reason about
#: which calls are safe to retry or run speculatively.
READ_TOOLS = (midden_list_parameters,)

#: Tools that fetch from a network service, write rasters, or insert rows.
WRITE_TOOLS = (midden_run_intake, midden_derive_terrain, midden_create_aoi, midden_sweep)


def register(mcp) -> None:
    """Attach this module's tools to a FastMCP server."""
    for tool in READ_TOOLS:
        mcp.tool(tool, annotations=READ_ONLY)
    for tool in WRITE_TOOLS:
        mcp.tool(tool)
