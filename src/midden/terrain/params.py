"""Named parameters for terrain derivations (spec.md §7).

CLAUDE.md: "Judgment calls become parameters, not decisions. If a choice would otherwise
be settled once in prose, make it a named parameter with the value recorded in
derivation.params, and sweep it."

Everything here is pure. `cells_from_metres` is the one conversion that matters most:
several WhiteboxTools arguments and the openness search radius are counts of grid cells,
not distances, so the same numeric value means different things on the 0.5 m detection
grid and the 10 m modelling grid. Parameters are therefore declared in **metres** and
converted against the raster that is actually being processed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DETECTION_RES_M",
    "GRID_BUFFER_M",
    "MODEL_RES_M",
    "PARAMETERS",
    "Grid",
    "Parameter",
    "cells_from_metres",
    "defaults_for",
    "resolve",
]

#: The two grids, two jobs (spec.md §1). Never mixed: a model fitted at 0.5 m is noise
#: and will not fit in memory; feature detection at 10 m is blind.
DETECTION_RES_M = 0.5
MODEL_RES_M = 10.0

Grid = str  # 'detection' | 'model'

#: How far beyond the AOI each grid is computed before being clipped back.
#:
#: The modelling grid carries hydrology, and HAND is elevation above the nearest *downslope*
#: stream — computed from flow accumulated out of the surrounding catchment. Running it on
#: an AOI-shaped DEM truncates the network at the boundary and produces HAND that is wrong
#: everywhere near the edge, which on a small AOI is everywhere. The shakeout AOI is one
#: acre, so without this it would have no streams at all.
#:
#: The detection grid needs only enough margin to cover the openness search radius, so its
#: edge cells see real ground rather than padding.
GRID_BUFFER_M: dict[Grid, float] = {"model": 2000.0, "detection": 50.0}


@dataclass(frozen=True, slots=True)
class Parameter:
    """One swept parameter: what it means, what it defaults to, and why it is contested."""

    derivation: str
    name: str
    default: Any
    unit: str
    why: str
    grid: Grid | None = None


#: spec.md §7's parameter table. `hydro.drawdown.pool_level_m` and `score.overlay.weights`
#: arrive with M5; they are listed so `midden terrain params` shows the whole surface.
PARAMETERS: tuple[Parameter, ...] = (
    Parameter("terrain.streams", "flow_accum_threshold", 5000, "cells",
              "Sets what counts as a stream, which sets HAND, which sets terraces. "
              "The single most consequential knob in the project.", "model"),
    Parameter("terrain.streams", "breach_dist_m", 50.0, "m",
              "Maximum breach length. Breach, never fill: fill_depressions raises pits to "
              "their spill elevation and in karst that is most of the landscape.", "model"),
    Parameter("terrain.slrm", "smoothing_radius_m", 15.0, "m",
              "10 m finds small features and noise; 25 m finds large features and smooths "
              "away small ones.", "detection"),
    Parameter("terrain.openness", "search_radius_m", 10.0, "m",
              "Declared in metres and converted per raster. 10 m is roughly one charcoal "
              "hearth. Tune against the Montgomery Bell hearths.", "detection"),
    Parameter("terrain.openness", "num_directions", 16, "count",
              "Azimuths in the horizon scan. 16 is RVT's default; 8 is visibly faceted.",
              "detection"),
    Parameter("terrain.terrace", "max_slope_deg", 3.0, "degrees",
              "Tighter is cleaner, looser catches gentle fans.", "model"),
    Parameter("terrain.terrace", "hand_mode_tolerance_m", 1.0, "m",
              "How tightly a cell must sit on a HAND mode to be called terrace.", "model"),
)


def defaults_for(derivation: str) -> dict[str, Any]:
    """Return the default parameter values for one derivation. Pure."""
    return {p.name: p.default for p in PARAMETERS if p.derivation == derivation}


def resolve(derivation: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge overrides onto a derivation's defaults, rejecting unknown names. Pure.

    An unknown parameter name is an error rather than an ignored key: a typo in a sweep
    would otherwise run the whole range at the default and look like a null result.
    """
    defaults = defaults_for(derivation)
    if not defaults:
        known = sorted({p.derivation for p in PARAMETERS})
        raise KeyError(f"No parameters for derivation {derivation!r}. Known: {known}")

    overrides = overrides or {}
    unknown = set(overrides) - set(defaults)
    if unknown:
        raise KeyError(
            f"{derivation}: unknown parameter(s) {sorted(unknown)}. "
            f"Known: {sorted(defaults)}"
        )
    return {**defaults, **overrides}


def cells_from_metres(metres: float, resolution_m: float, *, minimum: int = 1) -> int:
    """Convert a distance in metres to a count of grid cells. Pure.

    The conversion that keeps a swept parameter comparable across grids: `search_radius_m`
    of 10 is 20 cells at 0.5 m and 1 cell at 10 m. Hardcoding the cell count instead —
    which is what the WhiteboxTools API invites — silently changes the physical size of
    the thing being measured when the resolution changes.
    """
    if resolution_m <= 0:
        raise ValueError(f"resolution_m must be positive, got {resolution_m}")
    return max(minimum, round(metres / resolution_m))


def grid_resolution(grid: Grid) -> float:
    """Return the resolution in metres for a named grid. Pure."""
    try:
        return {"detection": DETECTION_RES_M, "model": MODEL_RES_M}[grid]
    except KeyError:
        raise ValueError(f"Unknown grid {grid!r}; expected 'detection' or 'model'.") from None


@dataclass(frozen=True, slots=True)
class Resolved:
    """A derivation's resolved parameters plus the grid they will run on."""

    derivation: str
    grid: Grid
    resolution_m: float
    values: dict[str, Any] = field(default_factory=dict)

    def cells(self, name: str) -> int:
        """Convert a metre-valued parameter to cells on this grid."""
        return cells_from_metres(float(self.values[name]), self.resolution_m)
