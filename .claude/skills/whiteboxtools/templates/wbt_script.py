#!/usr/bin/env python3
"""
<What this analysis produces, in one line.>

Template for a new WhiteboxTools script. The shape below exists to avoid the
failure modes in SKILL.md: silent failure, extension gating, and cells-vs-metres.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from wbt_helpers import checked, cells_from_metres, describe, make_wbt, require_tools

# CamelCase names from the manual. Checked at startup so a missing paid-extension
# tool fails here rather than forty minutes into a chain.
REQUIRED = [
    # "Slope",
]


def run(wbt, dem: Path, out: Path, radius_m: float) -> None:
    out.mkdir(parents=True, exist_ok=True)

    # Derive cell counts from metres so the parameter keeps its meaning if the
    # DEM resolution changes. Never hardcode a cell count.
    radius_cells = cells_from_metres(dem, radius_m)
    print(f"{radius_m} m -> {radius_cells} cells")

    result = out / "output.tif"

    # Always go through `checked`. wbt methods return 0/1 and never raise; a bad
    # path gives you a 1, no file, and a confusing error somewhere else later.
    # `expect` also catches the case where a tool returns 0 but writes nothing.
    checked(
        wbt, wbt.slope,
        str(dem), str(result),
        units="degrees",
        expect=result,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dem", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--radius", type=float, default=20.0, help="METRES, converted to cells.")
    args = ap.parse_args()

    print(describe(args.dem))          # confirm resolution and CRS before anything runs

    wbt = make_wbt(args.outdir)
    require_tools(wbt, REQUIRED)

    run(wbt, args.dem, args.outdir, args.radius)


if __name__ == "__main__":
    main()
