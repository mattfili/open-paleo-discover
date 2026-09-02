"""Hydrological conditioning, streams, and HAND — on the modelling grid only.

This is a thin orchestration layer over `.claude/skills/whiteboxtools/scripts/
hydro_chain.py`, which CLAUDE.md says to invoke rather than paraphrase. That script is
also the one that obeys its own skill's rules: every WhiteboxTools call goes through
`checked()`, breach distance is supplied in metres and converted per raster, and the
conditioned outputs are cached so a threshold sweep does not re-run the expensive part.

Grid discipline (spec.md §1): hydrology runs on the 10 m modelling grid. The
`whiteboxtools` skill's performance notes are explicit — "Do not run the hydrology chain
at 0.5 m." Flow routing does not tile cleanly and the intermediate rasters are enormous.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from midden.skills import load
from midden.terrain.params import MODEL_RES_M

__all__ = ["REQUIRED_TOOLS", "HydroOutputs", "make_wbt", "run_hydro_chain"]

#: The open-core WhiteboxTools this chain needs. Checked before any of them runs, so a
#: build missing one fails at the start with a name rather than midway with an empty file.
REQUIRED_TOOLS = [
    "BreachDepressionsLeastCost",
    "D8Pointer",
    "D8FlowAccumulation",
    "ExtractStreams",
    "ElevationAboveStream",
    "Slope",
]


class HydroOutputs(dict):
    """Paths produced by the chain: breached, pointer, accum, slope, streams, hand."""

    @property
    def hand(self) -> Path:
        """Height Above Nearest Drainage — the terrace signal."""
        return self["hand"]

    @property
    def slope(self) -> Path:
        """Slope in degrees."""
        return self["slope"]


def make_wbt(work_dir: Path | None = None):
    """Build a configured WhiteboxTools handle and verify the required tools exist."""
    helpers = load("whiteboxtools", "wbt_helpers")
    wbt = helpers.make_wbt(work_dir)
    helpers.require_tools(wbt, REQUIRED_TOOLS)
    return wbt


def wbt_version(wbt) -> str:
    """Return the build version string, recorded on every derivation row.

    WhiteboxTools argument names drift between releases, so an output is only reproducible
    alongside the version that produced it.
    """
    return (wbt.version() or "unknown").splitlines()[0].strip()


def run_hydro_chain(
    dem: Path,
    out_dir: Path,
    *,
    breach_dist_m: float,
    flow_accum_threshold: int,
    resolution_m: float = MODEL_RES_M,
) -> tuple[HydroOutputs, dict[str, Any]]:
    """Condition the DEM, extract streams, and compute HAND.

    Returns the output paths and the HAND diagnostics. The diagnostics matter as much as
    the raster: `n_modes` is how many terrace surfaces the histogram found, and fewer than
    two means the stream threshold is wrong for this landscape rather than that the
    landscape has no terraces.
    """
    if resolution_m < 1.0:
        raise ValueError(
            f"Hydrology must run on the modelling grid, got {resolution_m} m. "
            f"Flow routing at sub-metre resolution does not tile and produces noise "
            f"(spec.md §1, whiteboxtools/references/performance.md)."
        )

    chain = load("whiteboxtools", "hydro_chain")
    out_dir.mkdir(parents=True, exist_ok=True)
    wbt = make_wbt(out_dir)

    conditioned = chain.condition(wbt, dem.resolve(), out_dir.resolve(), breach_dist_m)
    streams = chain.streams_and_hand(
        wbt, conditioned, out_dir.resolve(), flow_accum_threshold
    )
    diagnostics = chain.hand_diagnostics(streams["hand"])

    return HydroOutputs({**conditioned, **streams}), diagnostics
