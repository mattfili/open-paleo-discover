#!/usr/bin/env python3
"""
Extract terrace surfaces from a bare-earth DEM.

A terrace is low slope plus a discrete mode in the Height Above Nearest Drainage
histogram. This script computes HAND, finds the modes, and labels terraces T0/T1/T2...
by ascending HAND.

The stream extraction threshold governs everything downstream. If the HAND histogram
comes back unimodal in an area that visibly has terraces, the threshold is wrong --
sweep it before trusting any output. See references/landform-model.md.

Usage:
    python terrace_extract.py DEM.tif OUTDIR --threshold 5000 --max-slope 3.0

Verify before relying on this:
    - WhiteboxTools argument names. They shift between versions; run
      `wbt.tool_help("ElevationAboveStream")` if a call fails.
    - That Openness and the hydrology tools are open core, not the paid extension.
      wbt.list_tools() exposes what is available in your install.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy.signal import find_peaks


def condition_and_hand(dem_path: Path, outdir: Path, threshold: int) -> dict[str, Path]:
    """Hydrologically condition the DEM and derive HAND, slope, and streams.

    Breaching rather than filling: depression filling raises pits to their spill
    elevation, which destroys small closed depressions and distorts HAND near them.
    """
    import whitebox

    wbt = whitebox.WhiteboxTools()
    wbt.verbose = False
    wbt.set_working_dir(str(outdir.resolve()))

    paths = {
        "filled": outdir / "dem_breached.tif",
        "pointer": outdir / "d8_pointer.tif",
        "accum": outdir / "d8_accum.tif",
        "streams": outdir / "streams.tif",
        "hand": outdir / "hand.tif",
        "slope": outdir / "slope.tif",
    }

    wbt.breach_depressions_least_cost(str(dem_path), str(paths["filled"]), dist=100)
    wbt.d8_pointer(str(paths["filled"]), str(paths["pointer"]))
    wbt.d8_flow_accumulation(str(paths["pointer"]), str(paths["accum"]), pntr=True)
    wbt.extract_streams(str(paths["accum"]), str(paths["streams"]), threshold=threshold)
    wbt.elevation_above_stream(
        str(paths["filled"]), str(paths["streams"]), str(paths["hand"])
    )
    wbt.slope(str(paths["filled"]), str(paths["slope"]), units="degrees")

    return paths


def hand_modes(
    hand: np.ndarray,
    bin_width_m: float = 0.25,
    max_hand_m: float = 40.0,
    prominence_frac: float = 0.02,
) -> tuple[list[float], np.ndarray, np.ndarray]:
    """Find terrace surfaces as modes in the HAND histogram.

    Returns (mode elevations, histogram counts, bin centres).

    prominence_frac is expressed as a fraction of the tallest peak, so the threshold
    scales with AOI size instead of needing a per-AOI absolute count.
    """
    valid = hand[np.isfinite(hand) & (hand >= 0) & (hand <= max_hand_m)]
    if valid.size == 0:
        raise ValueError("No valid HAND values. Check that streams were extracted at all.")

    bins = np.arange(0, max_hand_m + bin_width_m, bin_width_m)
    counts, edges = np.histogram(valid, bins=bins)
    centres = (edges[:-1] + edges[1:]) / 2

    # Light smoothing so single-bin noise does not register as a terrace.
    kernel = np.ones(3) / 3
    smoothed = np.convolve(counts.astype(float), kernel, mode="same")

    peaks, _ = find_peaks(smoothed, prominence=prominence_frac * smoothed.max())
    return [float(centres[p]) for p in peaks], counts, centres


def classify_terraces(
    hand: np.ndarray,
    slope: np.ndarray,
    modes: list[float],
    tolerance_m: float,
    max_slope_deg: float,
) -> np.ndarray:
    """Label each cell with a terrace index, or 0 for none.

    T0 is the lowest mode (active floodplain), T1 the next, and so on. T1 is the
    interesting one -- flat, drained, close to water, rarely flooded.
    """
    out = np.zeros(hand.shape, dtype=np.uint8)
    flat = np.isfinite(slope) & (slope <= max_slope_deg)

    for i, mode in enumerate(sorted(modes)):
        band = np.isfinite(hand) & (np.abs(hand - mode) <= tolerance_m)
        # Later (higher) terraces do not overwrite earlier assignments.
        out[band & flat & (out == 0)] = i + 1

    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dem", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument(
        "--threshold",
        type=int,
        default=5000,
        help="Flow-accumulation threshold for stream extraction, in cells. "
        "The most consequential parameter here -- sweep it.",
    )
    ap.add_argument("--max-slope", type=float, default=3.0, help="Degrees.")
    ap.add_argument(
        "--tolerance",
        type=float,
        default=1.0,
        help="Metres either side of a HAND mode that still counts as that terrace.",
    )
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    paths = condition_and_hand(args.dem, args.outdir, args.threshold)

    with rasterio.open(paths["hand"]) as src:
        hand = src.read(1, masked=True).filled(np.nan)
        profile = src.profile
    with rasterio.open(paths["slope"]) as src:
        slope = src.read(1, masked=True).filled(np.nan)

    modes, counts, centres = hand_modes(hand)

    if len(modes) < 2:
        print(
            f"WARNING: found {len(modes)} HAND mode(s). A terraced valley should show "
            f"several. The stream threshold ({args.threshold}) is probably wrong -- too "
            "high smears terraces together, too low compresses HAND toward zero. "
            "Sweep it before using this output."
        )

    terraces = classify_terraces(hand, slope, modes, args.tolerance, args.max_slope)

    profile.update(dtype=rasterio.uint8, count=1, nodata=0, compress="deflate")
    terrace_path = args.outdir / "terraces.tif"
    with rasterio.open(terrace_path, "w", **profile) as dst:
        dst.write(terraces, 1)

    report = {
        "stream_threshold": args.threshold,
        "max_slope_deg": args.max_slope,
        "tolerance_m": args.tolerance,
        "hand_modes_m": modes,
        "terrace_cell_counts": {
            f"T{i}": int((terraces == i + 1).sum()) for i in range(len(modes))
        },
        "histogram": {
            "bin_centres_m": centres.tolist(),
            "counts": counts.tolist(),
        },
    }
    (args.outdir / "terrace_report.json").write_text(json.dumps(report, indent=2))

    print(f"HAND modes (m): {[round(m, 2) for m in modes]}")
    print(f"Wrote {terrace_path}")
    print(f"Wrote {args.outdir / 'terrace_report.json'}")
    print("\nPlot the histogram in the report before trusting the labels. Real terraces "
          "show as separated humps; a single broad hump means the threshold needs work.")


if __name__ == "__main__":
    main()
