"""Terrain orchestration: run a grid end to end and register what it produced.

Two entry points, one per grid, because spec.md §1's two-grids rule is the whole design:

- `run_model_grid`   — 10 m, from 3DEP. Hydrology, HAND, slope. Fast.
- `run_detection_grid` — 0.5 m, from the 3DEP point cloud. Openness, SLRM, hillshade.

Every output becomes a COG in `derived.raster_asset` pointing at a `derived.derivation`
row that records the tool, its version, and the parameters. That is what makes two runs
comparable rather than merely different.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

import psycopg

from midden.aoi import Aoi
from midden.config import Settings, settings
from midden.derivation import open_derivation, param_variant
from midden.registry import get_class, resolve_class_params
from midden.terrain import dem as dem_mod
from midden.terrain import detection, hydro
from midden.terrain import terrace as terrace_mod
from midden.terrain.cog import register_asset, write_cog
from midden.terrain.params import GRID_BUFFER_M, grid_resolution, resolve

__all__ = ["TerrainResult", "run_detection_grid", "run_model_grid"]


class TerrainResult(NamedTuple):
    """What one terrain run produced."""

    aoi_slug: str
    grid: str
    assets: dict[str, int]
    paths: dict[str, Path]
    derivation_id: int
    diagnostics: dict[str, Any]
    variant: str = ""


def _publish(
    conn: psycopg.Connection,
    aoi: Aoi,
    grid: str,
    products: dict[str, Path],
    *,
    derivation_id: int,
    variant: str,
    config: Settings,
) -> tuple[dict[str, int], dict[str, Path]]:
    """Convert each product to a COG under data/cogs/<slug>/ and catalog it."""
    resolution_m = grid_resolution(grid)
    cog_dir = config.aoi_cog_dir(aoi.slug)
    assets, paths = {}, {}
    for kind, source in products.items():
        suffix = f"_{variant}" if variant else ""
        dest = cog_dir / f"{kind}_{resolution_m:g}m{suffix}.tif"
        write_cog(Path(source), dest)
        assets[kind] = register_asset(
            conn,
            aoi_id=aoi.id,
            kind=kind,
            grid=grid,
            path=dest,
            derivation_id=derivation_id,
            variant=variant,
        )
        paths[kind] = dest
    return assets, paths


def _model_derivatives(
    work: Path, outputs: dict[str, Any], terrace_params: dict[str, Any]
) -> tuple[dict[str, Path], dict[str, Any]]:
    """Derive TWI and terrace class from the conditioned hydrology outputs."""
    wbt = hydro.make_wbt(work)
    sca = terrace_mod.specific_contributing_area(
        wbt, Path(outputs["pointer"]), work / "sca.tif"
    )
    twi = terrace_mod.wetness_index(wbt, sca, Path(outputs["slope"]), work / "twi.tif")
    terrace_path, report = terrace_mod.classify(
        Path(outputs["hand"]),
        Path(outputs["slope"]),
        work / "terrace.tif",
        max_slope_deg=terrace_params["max_slope_deg"],
        tolerance_m=terrace_params["hand_mode_tolerance_m"],
    )
    return {"twi": twi, "terrace": terrace_path}, report


def run_model_grid(
    conn: psycopg.Connection,
    aoi: Aoi,
    *,
    overrides: dict[str, Any] | None = None,
    config: Settings | None = None,
    buffer_m: float | None = None,
) -> TerrainResult:
    """Fetch a 10 m DEM, run the hydrology chain, and catalog the outputs."""
    config = config or settings()
    streams = resolve("terrain.streams", overrides)
    buffer_m = GRID_BUFFER_M["model"] if buffer_m is None else buffer_m
    params = {**streams, "buffer_m": buffer_m, "grid": "model"}
    variant = param_variant(params) if overrides else ""

    work = config.scratch_dir / aoi.slug / "model"
    wbt_version = hydro.wbt_version(hydro.make_wbt())

    with open_derivation(
        conn,
        operation="terrain.model",
        tool="WhiteboxTools + seamless-3dep",
        tool_version=wbt_version,
        aoi_id=aoi.id,
        params=params,
        inputs=["3DEP 10m"],
    ) as derivation_id:
        raw_dem = dem_mod.fetch_dem(aoi, work, grid="model", buffer_m=buffer_m)
        outputs, diagnostics = hydro.run_hydro_chain(
            raw_dem,
            work / "hydro",
            breach_dist_m=streams["breach_dist_m"],
            flow_accum_threshold=streams["flow_accum_threshold"],
        )
        derived_paths, terrace_report = _model_derivatives(
            work / "hydro", outputs, resolve("terrain.terrace", None)
        )
        diagnostics = {**diagnostics, "terrace": terrace_report}
        products = {
            "dem": raw_dem,
            "hand": Path(outputs["hand"]),
            "slope": Path(outputs["slope"]),
            "streams": Path(outputs["streams"]),
            "d8_accum": Path(outputs["accum"]),
            **derived_paths,
        }
        assets, paths = _publish(
            conn,
            aoi,
            "model",
            products,
            derivation_id=derivation_id,
            variant=variant,
            config=config,
        )

    return TerrainResult(
        aoi.slug, "model", assets, paths, derivation_id, diagnostics, variant
    )


def run_detection_grid(
    conn: psycopg.Connection,
    aoi: Aoi,
    *,
    ept_project: str,
    class_id: str,
    overrides: dict[str, Any] | None = None,
    config: Settings | None = None,
    buffer_m: float | None = None,
) -> TerrainResult:
    """Build a 0.5 m bare-earth DEM from the point cloud and render the detection set.

    Detection parameters are per class, never global (CLAUDE.md): openness and SLRM
    values come from the class's ref.target_class row, with `overrides` on top for a
    sweep. Every asset carries the class in its variant so two classes' renders of the
    same AOI never clobber each other, and the derivation records which class the run
    (or sweep) was for.
    """
    config = config or settings()
    cls = get_class(conn, class_id)
    if cls.grid not in ("detection", "both"):
        raise ValueError(
            f"Class {class_id!r} is on the {cls.grid!r} grid with detectability "
            f"{cls.detectability!r}; running a detection chain for it would report "
            "absence as evidence. Detection runs are for detection-grid classes."
        )
    openness_params = resolve_class_params(
        cls, "terrain.openness", (overrides or {}).get("openness")
    )
    slrm_params = resolve_class_params(
        cls, "terrain.slrm", (overrides or {}).get("slrm")
    )
    if buffer_m is None:
        # The openness scan mirror-pads beyond the raster edge, so the computed extent
        # must exceed the AOI by at least the search radius or edge cells are fiction.
        buffer_m = max(
            GRID_BUFFER_M["detection"], 2.0 * float(openness_params["search_radius_m"])
        )
    params = {
        **openness_params,
        **slrm_params,
        "class_id": class_id,
        "buffer_m": buffer_m,
        "grid": "detection",
        "ept_project": ept_project,
    }
    variant = f"{class_id}-{param_variant(params)}" if overrides else class_id

    work = config.scratch_dir / aoi.slug / "detection"

    with open_derivation(
        conn,
        operation="terrain.detection",
        tool="PDAL + RVT(vendored) + WhiteboxTools",
        tool_version=f"pdal-cli; rvt-vis vendored; {hydro.wbt_version(hydro.make_wbt())}",
        aoi_id=aoi.id,
        params=params,
        inputs=[f"EPT {ept_project}"],
    ) as derivation_id:
        raw_dem = dem_mod.fetch_dem_ept(
            aoi,
            work,
            project=ept_project,
            resolution_m=grid_resolution("detection"),
            buffer_m=buffer_m,
        )
        renders = detection.detection_renders(
            raw_dem,
            work / "renders",
            search_radius_m=openness_params["search_radius_m"],
            smoothing_radius_m=slrm_params["smoothing_radius_m"],
            num_directions=openness_params["num_directions"],
        )
        products = {
            "dem": raw_dem,
            "ground_count": work / "ground_count.tif",
            **{k: Path(v) for k, v in renders.items()},
        }
        assets, paths = _publish(
            conn,
            aoi,
            "detection",
            products,
            derivation_id=derivation_id,
            variant=variant,
            config=config,
        )

    return TerrainResult(
        aoi.slug, "detection", assets, paths, derivation_id, {}, variant
    )
