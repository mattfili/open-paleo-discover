#!/usr/bin/env python3
"""
The canonical hydrology chain: conditioning through HAND.

    DEM
      -> breach_depressions_least_cost      conditioning (NOT fill -- see SKILL.md)
      -> d8_pointer                          flow direction
      -> d8_flow_accumulation(pntr=True)     contributing area
      -> extract_streams(threshold=N)        stream network
      -> elevation_above_stream              HAND
      -> slope

Conditioning and accumulation are the expensive steps and do not depend on the
stream threshold. They are cached, so sweeping the threshold re-runs only
extract_streams and elevation_above_stream. That is what makes a sweep practical
instead of an afternoon.

Usage:
    python hydro_chain.py DEM.tif OUT/ --threshold 5000
    python hydro_chain.py DEM.tif OUT/ --threshold 1000 2500 5000 10000   # sweep

Sweep first, always. The threshold defines what counts as a stream, which defines
HAND, which defines terraces and every distance-to-water metric. A default is not
an answer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio

from wbt_helpers import checked, cells_from_metres, describe, make_wbt, require_tools

REQUIRED = [
    "BreachDepressionsLeastCost",
    "D8Pointer",
    "D8FlowAccumulation",
    "ExtractStreams",
    "ElevationAboveStream",
    "Slope",
]


def condition(wbt, dem: Path, out: Path, breach_dist_m: float) -> dict[str, Path]:
    """Conditioning, pointer, accumulation, slope. Threshold-independent, so cached."""
    paths = {
        "breached": out / "dem_breached.tif",
        "pointer": out / "d8_pointer.tif",
        "accum": out / "d8_accum.tif",
        "slope": out / "slope.tif",
    }

    if all(p.exists() for p in paths.values()):
        print("Conditioning outputs already present -- reusing.")
        return paths

    dist_cells = cells_from_metres(dem, breach_dist_m)
    print(f"Breaching with dist={dist_cells} cells ({breach_dist_m} m)")

    # Breach, not fill: filling raises pits to their spill elevation, destroying
    # small closed depressions. In karst that is most of the landscape, and in this
    # domain closed depressions may be the target.
    checked(
        wbt, wbt.breach_depressions_least_cost,
        str(dem), str(paths["breached"]), dist=dist_cells,
        expect=paths["breached"],
    )
    checked(
        wbt, wbt.d8_pointer,
        str(paths["breached"]), str(paths["pointer"]),
        expect=paths["pointer"],
    )
    # pntr=True is load-bearing. Without it the pointer raster is read as
    # elevations, the tool returns 0, and the output is plausible-looking nonsense.
    checked(
        wbt, wbt.d8_flow_accumulation,
        str(paths["pointer"]), str(paths["accum"]), pntr=True,
        expect=paths["accum"],
    )
    checked(
        wbt, wbt.slope,
        str(paths["breached"]), str(paths["slope"]), units="degrees",
        expect=paths["slope"],
    )
    return paths


def streams_and_hand(wbt, cond: dict[str, Path], out: Path, threshold: int) -> dict[str, Path]:
    """The cheap, threshold-dependent tail of the chain."""
    streams = out / f"streams_t{threshold}.tif"
    hand = out / f"hand_t{threshold}.tif"

    checked(
        wbt, wbt.extract_streams,
        str(cond["accum"]), str(streams), threshold=threshold,
        expect=streams,
    )
    # HAND wants the conditioned DEM, not the original.
    checked(
        wbt, wbt.elevation_above_stream,
        str(cond["breached"]), str(streams), str(hand),
        expect=hand,
    )
    return {"streams": streams, "hand": hand}


def hand_diagnostics(hand_path: Path, max_hand_m: float = 40.0) -> dict:
    """Summarize the HAND distribution.

    The histogram is the diagnostic for whether the threshold is right. Real
    terraces show as separated modes. A single broad hump means the threshold is
    wrong and nothing downstream is meaningful yet.
    """
    from scipy.signal import find_peaks

    with rasterio.open(hand_path) as src:
        arr = src.read(1, masked=True).filled(np.nan)

    valid = arr[np.isfinite(arr) & (arr >= 0) & (arr <= max_hand_m)]
    if valid.size == 0:
        return {"modes_m": [], "note": "no valid HAND values -- were any streams extracted?"}

    counts, edges = np.histogram(valid, bins=np.arange(0, max_hand_m + 0.25, 0.25))
    centres = (edges[:-1] + edges[1:]) / 2
    smoothed = np.convolve(counts.astype(float), np.ones(3) / 3, mode="same")
    peaks, _ = find_peaks(smoothed, prominence=0.02 * smoothed.max())

    modes = [round(float(centres[p]), 2) for p in peaks]
    return {
        "modes_m": modes,
        "n_modes": len(modes),
        "median_hand_m": round(float(np.median(valid)), 2),
        "p95_hand_m": round(float(np.percentile(valid, 95)), 2),
        "note": (
            "unimodal -- threshold likely wrong: too high smears terraces together, "
            "too low compresses HAND toward zero"
            if len(modes) < 2
            else "multiple modes -- plausible terrace structure"
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dem", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument(
        "--threshold", type=int, nargs="+", default=[5000],
        help="Flow-accumulation threshold in cells. Several values run a sweep.",
    )
    ap.add_argument(
        "--breach-dist", type=float, default=50.0,
        help="Maximum breach length in METRES; converted to cells for WBT.",
    )
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    print(describe(args.dem))

    wbt = make_wbt(args.outdir)
    require_tools(wbt, REQUIRED)

    cond = condition(wbt, args.dem, args.outdir, args.breach_dist)

    report = {"dem": str(args.dem), "breach_dist_m": args.breach_dist, "sweep": {}}

    for t in args.threshold:
        print(f"\n--- threshold {t} ---")
        outs = streams_and_hand(wbt, cond, args.outdir, t)
        diag = hand_diagnostics(outs["hand"])
        report["sweep"][str(t)] = {**diag, "hand": str(outs["hand"])}
        print(f"HAND modes (m): {diag['modes_m']}")
        print(f"  {diag['note']}")

    (args.outdir / "hydro_report.json").write_text(json.dumps(report, indent=2))
    print(f"\nWrote {args.outdir / 'hydro_report.json'}")

    if len(args.threshold) > 1:
        best = max(
            report["sweep"].items(),
            key=lambda kv: kv[1].get("n_modes", 0),
        )
        print(
            f"\nMost mode structure at threshold {best[0]} "
            f"({best[1].get('n_modes', 0)} modes). Look at the histograms before "
            "accepting that -- mode count is a hint, not a verdict."
        )


if __name__ == "__main__":
    main()
