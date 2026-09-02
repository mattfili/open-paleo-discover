#!/usr/bin/env python3
"""
Inspect a point cloud before committing to a pipeline.

Answers the three questions that determine whether your pipeline will work:
  1. Is it ground-classified? (if not, filters.range on Classification[2:2] matches
     nothing and you get an empty raster with no error)
  2. What CRS is it in?
  3. What point density do you actually have, and what resolution does that support?

Usage:
    python inspect.py input.laz
"""

from __future__ import annotations

import sys
from pathlib import Path

from run_pipeline import PdalError, info

# ASPRS standard classes worth naming.
CLASSES = {
    0: "created, never classified",
    1: "unassigned",
    2: "ground",
    3: "low vegetation",
    4: "medium vegetation",
    5: "high vegetation",
    6: "building",
    7: "low noise",
    9: "water",
    18: "high noise",
}


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)

    path = Path(sys.argv[1])

    try:
        summary = info(path)
        stats = info(path, stats=True, dimensions="Classification,Z")
    except PdalError as exc:
        raise SystemExit(str(exc))

    s = summary.get("summary", {})
    count = s.get("num_points", 0)
    bounds = s.get("bounds", {})
    srs = s.get("srs", {})

    print(f"File      : {path.name}")
    print(f"Points    : {count:,}")

    wkt = srs.get("wkt", "")
    horiz = srs.get("horizontal", "") or wkt[:80]
    print(f"CRS       : {horiz if horiz else 'NONE -- you must set in_srs explicitly'}")

    if bounds:
        dx = bounds.get("maxx", 0) - bounds.get("minx", 0)
        dy = bounds.get("maxy", 0) - bounds.get("miny", 0)
        area = dx * dy
        print(f"Extent    : {dx:,.0f} x {dy:,.0f} CRS units")
        if area > 0:
            density = count / area
            print(f"Density   : {density:.2f} points per sq unit (ALL classes)")

    # Classification breakdown
    print("\nClassification:")
    found_ground = False
    for st in stats.get("stats", {}).get("statistic", []):
        if st.get("name") != "Classification":
            continue
        lo, hi = int(st.get("minimum", 0)), int(st.get("maximum", 0))
        print(f"  range {lo}-{hi}")
        if lo <= 2 <= hi:
            found_ground = True
        for code in range(lo, min(hi, 20) + 1):
            if code in CLASSES:
                print(f"    {code:>2}  {CLASSES[code]}")

    if not found_ground:
        print(
            "\n  WARNING: class 2 (ground) is outside the observed range.\n"
            "  filters.range with Classification[2:2] will match NOTHING and the\n"
            "  pipeline will succeed while writing an empty raster.\n"
            "  Classify ground yourself first -- see templates/reclassify_ground.json"
        )
    else:
        print("\n  Ground class present. filters.range Classification[2:2] will work.")
        print(
            "  Note this does not tell you ground DENSITY. Write a count raster at your\n"
            "  target resolution to see where ground returns actually are:\n"
            '    {"type":"writers.gdal","output_type":"count","resolution":0.5,...}'
        )


if __name__ == "__main__":
    main()
