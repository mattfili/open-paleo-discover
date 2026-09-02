#!/usr/bin/env python3
"""
Test a suitability surface against known site locations.

This is the falsification test for a weight set. A weighted overlay is a hypothesis, and
its only claim to validity is that it ranks known sites highly. If it does not put a
major published site in the top few percent of its own AOI, the weight set is wrong --
discard it rather than defending it.

Uses PUBLISHED sites only: places with historical markers, literature, and public
coordinates. Never point this at a restricted state site file and never write control
coordinates into a public repository.

Usage:
    python control_check.py score.tif controls.geojson --top-pct 5

controls.geojson: point or polygon features, each with properties:
    name        str
    role        "control_positive" | "control_detection"
    source      str   -- where the location came from, so it can be checked

Exit code is 1 if any control_positive fails, so this can gate a weight-set change.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask


def percentile_rank(score: np.ndarray, values: np.ndarray) -> float:
    """What percentile of the AOI does this set of values sit at?

    Returns the mean percentile across the supplied values, where 100 = highest scoring
    in the AOI. Uses the mean rather than the max because a single lucky cell inside a
    mound footprint proves nothing -- we want the footprint as a whole to score well.
    """
    valid = score[np.isfinite(score)]
    if valid.size == 0 or values.size == 0:
        return float("nan")
    ranks = np.searchsorted(np.sort(valid), values) / valid.size * 100.0
    return float(np.mean(ranks))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("score", type=Path, help="Suitability raster, 10 m modelling grid.")
    ap.add_argument("controls", type=Path, help="GeoJSON of published control sites.")
    ap.add_argument(
        "--top-pct",
        type=float,
        default=5.0,
        help="A control_positive must rank within this top percentage to pass.",
    )
    args = ap.parse_args()

    controls = json.loads(args.controls.read_text())
    failures: list[str] = []
    results: list[tuple[str, str, float, str]] = []

    with rasterio.open(args.score) as src:
        full = src.read(1, masked=True).filled(np.nan)

        for feat in controls["features"]:
            props = feat.get("properties", {})
            name = props.get("name", "<unnamed>")
            role = props.get("role", "control_positive")

            if role != "control_positive":
                # Detection controls are validated by eye against the renders, not
                # against the suitability surface. Nothing to score here.
                results.append((name, role, float("nan"), "visual check only"))
                continue

            try:
                clipped, _ = rio_mask(src, [feat["geometry"]], crop=True, filled=False)
            except ValueError:
                results.append((name, role, float("nan"), "OUTSIDE RASTER"))
                failures.append(f"{name}: geometry does not overlap the score raster")
                continue

            vals = clipped[0].compressed()
            vals = vals[np.isfinite(vals)]
            if vals.size == 0:
                results.append((name, role, float("nan"), "NO DATA"))
                failures.append(f"{name}: no valid score cells at this location")
                continue

            pct = percentile_rank(full, vals)
            threshold = 100.0 - args.top_pct
            verdict = "pass" if pct >= threshold else "FAIL"
            if verdict == "FAIL":
                failures.append(
                    f"{name}: ranks at the {pct:.1f}th percentile, needs {threshold:.1f}"
                )
            results.append((name, role, pct, verdict))

    width = max(len(r[0]) for r in results) if results else 10
    print(f"{'control':<{width}}  {'role':<18}  {'pctile':>7}  verdict")
    print("-" * (width + 40))
    for name, role, pct, verdict in results:
        pct_s = "  --  " if np.isnan(pct) else f"{pct:6.1f}"
        print(f"{name:<{width}}  {role:<18}  {pct_s}  {verdict}")

    if failures:
        print("\nFAILED:")
        for f in failures:
            print(f"  - {f}")
        print(
            "\nThis weight set has been falsified. Do not tune the controls to fit it; "
            "change the weights, or check whether a feature in the stack is broken -- a "
            "unimodal HAND histogram will do this on its own."
        )
        sys.exit(1)

    print("\nAll positive controls pass. That is a floor, not a result: it means the "
          "weight set is not obviously wrong. Now look at what else ranks with them.")


if __name__ == "__main__":
    main()
