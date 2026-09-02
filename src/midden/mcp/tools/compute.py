"""Compute MCP tools: create AOIs, run intake, derive terrain, and sweep parameters.

These are the write side. None of them carries `readOnlyHint`, because each one fetches
from a network service, writes rasters to disk, or inserts rows.
"""

from __future__ import annotations

from pathlib import Path
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



def midden_build_feature_stack(
    aoi: Annotated[str, Field(description="AOI slug.")],
    regional: Annotated[
        bool,
        Field(description="Keep the full buffered extent instead of clipping to the AOI. "
                          "Required for a control test: ranking a site against itself is "
                          "not a test."),
    ] = False,
) -> dict[str, Any]:
    """Assemble the 10 m feature stack for an AOI and write it to Parquet.

    Needs the modelling-grid terrain and the SSURGO soils for that AOI to exist already.
    Distances come from the authoritative NHD hydrography rather than from the
    WhiteboxTools stream raster, so they do not move when the stream threshold moves.
    """
    from midden.features.stack import build_feature_stack, register_stack

    with connect() as conn:
        area = get_aoi(conn, aoi)
        result = build_feature_stack(conn, area, clip_to_aoi=not regional)
        if not regional:
            register_stack(conn, area, result)
    return {
        "aoi": result.aoi_slug, "rows": result.rows,
        "path": str(result.path), "columns": result.columns,
        "extent": "buffered" if regional else "clipped to AOI",
    }


def midden_score_overlay(
    aoi: Annotated[str, Field(description="AOI slug.")],
    weights: Annotated[
        str, Field(description="Path to a weight-set YAML.")
    ] = "weights/default.yml",
    regional: Annotated[
        bool, Field(description="Score the buffered extent, for a control test.")
    ] = False,
) -> dict[str, Any]:
    """Apply a weight set to an AOI's feature stack and write a score raster.

    A weighted overlay is a hypothesis, not a measurement. Its only claim to validity is
    whether it ranks published sites highly, so follow this with a control run rather than
    treating the ranking as a finding.

    `burial_risk` is deliberately absent from the sum: a cell scores low either because the
    landform is wrong or because anything there is under metres of overbank silt, and
    those are different findings.
    """
    import pandas as pd

    from midden.features.score import load_weights, score_stack, write_score_raster
    from midden.features.stack import build_feature_stack
    from midden.terrain.cog import list_assets

    weight_set = load_weights(Path(weights))
    with connect() as conn:
        area = get_aoi(conn, aoi)
        stack = build_feature_stack(conn, area, clip_to_aoi=not regional)
        template = next(
            r["path"] for r in list_assets(conn, aoi_id=area.id, kind="hand")
            if r["grid"] == "model"
        )

    result = score_stack(pd.read_parquet(stack.path), weight_set)
    suffix = "_regional" if regional else ""
    destination = settings().aoi_cog_dir(aoi) / f"score{suffix}_10m.tif"
    write_score_raster(result.frame, Path(template), destination)

    scores = result.frame.score
    return {
        "aoi": aoi, "weight_set": result.weight_set, "cells": len(result.frame),
        "score_raster": str(destination),
        "score": {"mean": float(scores.mean()), "min": float(scores.min()),
                  "max": float(scores.max())},
        "weights": result.weights,
        "mean_contribution": result.contributions,
        "companion_bands": sorted(weight_set.companion_bands),
    }


#: Tools that only read. Marked readOnlyHint so a client can reason about which calls are
#: safe to retry or run speculatively.
READ_TOOLS = (midden_list_parameters,)

#: Tools that fetch from a network service, write rasters, or insert rows.
WRITE_TOOLS = (
    midden_run_intake,
    midden_derive_terrain,
    midden_create_aoi,
    midden_sweep,
    midden_build_feature_stack,
    midden_score_overlay,
)


def register(mcp) -> None:
    """Attach this module's tools to a FastMCP server."""
    for tool in READ_TOOLS:
        mcp.tool(tool, annotations=READ_ONLY)
    for tool in WRITE_TOOLS:
        mcp.tool(tool)
