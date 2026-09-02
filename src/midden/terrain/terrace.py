"""Terrace classification and the topographic wetness index (spec.md §7).

Terraces are the heart of the predictive model: low slope plus a discrete mode in the
Height Above Nearest Drainage histogram. Rivers cut downward over geologic time, leaving
old floodplains as flat benches — T0 floods yearly, T1 rarely, T2+ is older and higher.
**T1 is where sites are.**

The mode-finding and the classification come from the landform-archaeology skill's
`terrace_extract.py`, which CLAUDE.md says to import rather than paraphrase. Only its two
pure functions are used: its own `condition_and_hand()` duplicates `hydro_chain` without
that script's caching or its `checked()` wrapping, so the hydrology comes from
`midden.terrain.hydro` instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from midden.skills import load
from midden.terrain.detection import write_like

__all__ = ["classify", "specific_contributing_area", "wetness_index"]


def specific_contributing_area(wbt, pointer: Path, dest: Path) -> Path:
    """Flow accumulation as specific contributing area, which is what TWI needs.

    `pntr=True` is not optional. Without it the tool reads the pointer's direction codes
    as elevations, returns zero, and writes plausible nonsense.
    """
    helpers = load("whiteboxtools", "wbt_helpers")
    helpers.checked(
        wbt, wbt.d8_flow_accumulation,
        str(pointer.resolve()), str(dest.resolve()),
        out_type="specific contributing area", pntr=True,
        expect=dest,
    )
    return dest


def wetness_index(wbt, sca: Path, slope: Path, dest: Path) -> Path:
    """Topographic wetness index, ln(A / tan(slope)).

    Takes specific contributing area and a slope raster in degrees — not a DEM. Handing it
    a DEM is a silent failure: the tool runs and the numbers mean nothing.
    """
    helpers = load("whiteboxtools", "wbt_helpers")
    helpers.checked(
        wbt, wbt.wetness_index,
        str(sca.resolve()), str(slope.resolve()), str(dest.resolve()),
        expect=dest,
    )
    return dest


def classify(
    hand_path: Path,
    slope_path: Path,
    dest: Path,
    *,
    max_slope_deg: float,
    tolerance_m: float,
) -> tuple[Path, dict[str, Any]]:
    """Label terrace surfaces from the HAND histogram and a slope mask.

    Returns the raster and a report carrying the modes found. A cell is labelled for the
    first ascending mode it sits within `tolerance_m` of, and only if its slope is at or
    below `max_slope_deg`; 0 means no terrace.

    Fewer than two modes usually means the stream threshold is wrong for this landscape
    rather than that the landscape has no terraces — but a dissected upland with only
    headwater streams genuinely has no low terrace, and that is a real result.
    """
    extract = load("landform-archaeology", "terrace_extract")

    with rasterio.open(hand_path) as src:
        hand = src.read(1, masked=True)
        profile = src.profile.copy()
    with rasterio.open(slope_path) as src:
        slope = src.read(1, masked=True)

    hand_values = hand.filled(np.nan)
    modes, _, _ = extract.hand_modes(hand_values)
    labels = extract.classify_terraces(
        hand_values, slope.filled(np.nan), modes, tolerance_m, max_slope_deg
    )

    counts = {
        f"T{i}": int((labels == i + 1).sum()) for i in range(len(modes))
    }
    write_like(dest, labels.astype("float32"), profile)

    return dest, {
        "hand_modes_m": [round(float(m), 2) for m in modes],
        "n_modes": len(modes),
        "max_slope_deg": max_slope_deg,
        "tolerance_m": tolerance_m,
        "terrace_cell_counts": counts,
        "note": (
            "fewer than two modes -- check the stream threshold, or accept that a "
            "dissected upland has no low terrace"
            if len(modes) < 2 else "multiple modes -- plausible terrace structure"
        ),
    }
