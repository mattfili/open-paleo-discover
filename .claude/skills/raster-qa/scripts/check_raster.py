#!/usr/bin/env python3
"""Mechanical sanity checks for any raster produced by the midden pipeline.

Usage:
    uv run python .claude/skills/raster-qa/scripts/check_raster.py PATH \
        [--grid detection|model] [--kind KIND]

Every check here catches a failure mode that has already occurred or is named
in CLAUDE.md as silent: wrong CRS, degree-sized pixels, feet-vs-metres DEMs,
undeclared nodata, constant output from a panicked tool, out-of-range
openness. Exit 0 = all checks pass; exit 1 = at least one failure, each
printed as FAIL with the observed value.
"""

import argparse
import math
import sys

import numpy as np
import rasterio

PROJECT_EPSG = 26916
GRID_RES = {"detection": 0.5, "model": 10.0}

# Plausible value ranges by asset kind. Elevation bounds are Middle Tennessee:
# the Cumberland River pool is ~110 m NAVD88 and the Highland Rim tops out
# short of 600 m. A DEM in feet (~360-1900) or degrees fails instantly.
KIND_RANGES = {
    "dem": (50.0, 700.0),
    "openness_pos": (0.0, 180.0),
    "openness_neg": (0.0, 180.0),
    "slope": (0.0, 90.0),
    "aspect": (-1.0, 360.0),  # -1 is the WBT flat-cell convention
    "hand": (0.0, 300.0),
    "twi": (-5.0, 40.0),
    "slrm": (-50.0, 50.0),
    "score": (0.0, 1.0),
}


def check(raster_path: str, grid: str | None, kind: str | None) -> int:
    """Run every applicable check; print PASS/FAIL lines; return failure count."""
    failures = 0

    def result(ok: bool, label: str, detail: str) -> None:
        nonlocal failures
        print(f"{'PASS' if ok else 'FAIL'}  {label}: {detail}")
        failures += 0 if ok else 1

    def warn(ok: bool, label: str, detail: str) -> None:
        """Advisory: printed loudly, never counted — for checks whose failure
        has a legitimate reading the caller must confirm rather than fix."""
        print(f"{'PASS' if ok else 'WARN'}  {label}: {detail}")

    with rasterio.open(raster_path) as src:
        epsg = src.crs.to_epsg() if src.crs else None
        result(
            epsg == PROJECT_EPSG,
            "crs",
            f"EPSG:{epsg} (project CRS is EPSG:{PROJECT_EPSG})",
        )

        px_x, px_y = abs(src.transform.a), abs(src.transform.e)
        result(
            math.isclose(px_x, px_y, rel_tol=0.01),
            "square-pixels",
            f"{px_x:.4g} x {px_y:.4g}",
        )
        result(
            px_x > 0.01,
            "pixel-units",
            f"{px_x:.6g} — a degree-sized pixel means an unwarped fetch",
        )
        if grid:
            expected = GRID_RES[grid]
            result(
                math.isclose(px_x, expected, rel_tol=0.02),
                "grid-resolution",
                f"{px_x:.4g} m (grid '{grid}' expects {expected} m)",
            )

        result(src.nodata is not None, "nodata-declared", f"nodata={src.nodata}")

        band = src.read(1, masked=True)
        n_total = band.size
        n_valid = int(band.count())
        valid_frac = n_valid / n_total if n_total else 0.0
        result(n_valid > 0, "has-data", f"{n_valid}/{n_total} valid cells")
        # Advisory: an output masked to an AOI polygon inside its bounding box
        # is legitimately mostly nodata. Confirm the mask is intended; a low
        # fraction on an UNMASKED product means bad bounds or CRS.
        warn(
            valid_frac > 0.05,
            "mostly-data",
            f"{valid_frac:.1%} valid — fine if masked to an AOI polygon; "
            "on an unmasked product this means bad bounds or CRS",
        )

        if n_valid:
            vmin, vmax = float(band.min()), float(band.max())
            vstd = float(band.std())
            result(
                vstd > 0 or n_valid == 1,
                "not-constant",
                f"std={vstd:.6g} — constant output is the panicked-tool signature",
            )
            # nodata leaking into data: a huge sentinel present as a "valid" value
            for sentinel in (-9999.0, -32768.0, 3.4e38):
                if src.nodata is not None and math.isclose(
                    src.nodata, sentinel, rel_tol=1e-3
                ):
                    continue
                leaked = bool(np.isclose(band.compressed(), sentinel, rtol=1e-3).any())
                result(
                    not leaked,
                    "no-sentinel-leak",
                    f"sentinel {sentinel:g} {'present' if leaked else 'absent'} in valid data",
                )
            if kind and kind in KIND_RANGES:
                lo, hi = KIND_RANGES[kind]
                result(
                    vmin >= lo and vmax <= hi,
                    f"range[{kind}]",
                    f"[{vmin:.4g}, {vmax:.4g}] expected within [{lo:g}, {hi:g}]",
                )

        # WBT-compat: floating-point rasters must not carry a PREDICTOR tag
        # (WhiteboxTools exits 0 while panicking on predictor-compressed input).
        predictor = src.profile.get("predictor") or src.tags(ns="IMAGE_STRUCTURE").get(
            "PREDICTOR"
        )
        is_float = np.issubdtype(band.dtype, np.floating)
        predictor_ok = not (is_float and predictor not in (None, "1", 1))
        # Hard failure only for rasters the hydrology chain reads back in;
        # end products (score, openness, slrm) get an advisory — fine as-is,
        # but they panic WBT at exit 0 if ever fed back.
        wbt_input_kinds = {"dem", "hand", "streams"}
        checker = result if (kind in wbt_input_kinds or kind is None) else warn
        checker(
            predictor_ok,
            "wbt-predictor",
            f"dtype={band.dtype}, predictor={predictor}",
        )

    return failures


def main() -> int:
    """Parse arguments, run the checks, exit nonzero on any failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--grid", choices=list(GRID_RES))
    parser.add_argument("--kind", help=f"one of {sorted(KIND_RANGES)} for range checks")
    args = parser.parse_args()
    failures = check(args.path, args.grid, args.kind)
    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
