#!/usr/bin/env python3
"""
WhiteboxTools helpers: checked execution, tool availability, unit conversion.

The three things this exists to prevent:

1. Silent failure. wbt methods return 0/1 and never raise. A bad path or an
   unavailable tool gives you a 1, no output file, and a confusing error several
   steps later.
2. Extension surprises. A tool in the manual may be in the paid Whitebox Toolset
   Extension and absent from your build. Find out at startup.
3. Cells-versus-metres. Many spatial parameters are in grid cells. Hardcoding a
   cell count means the parameter silently changes meaning when resolution changes.

Import and use `checked` around every call, or use `WBT` which wraps automatically.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Iterable

import rasterio


class WhiteboxError(RuntimeError):
    """A WhiteboxTools call returned a non-zero exit code."""


def make_wbt(work_dir: Path | None = None, compress: bool = True):
    """Construct a configured WhiteboxTools instance with output capture.

    verbose stays True because the callback receives what would otherwise print --
    setting it False discards the error text too. We buffer the lines and only show
    them when something fails.
    """
    import whitebox

    wbt = whitebox.WhiteboxTools()
    wbt.verbose = True
    wbt.compress_rasters = compress
    wbt.max_procs = -1

    buffer: list[str] = []
    wbt.set_default_callback(buffer.append)
    wbt._output_buffer = buffer  # attached for `checked` to read and clear

    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        wbt.set_working_dir(str(work_dir.resolve()))

    return wbt


def checked(wbt, fn: Callable[..., int], *args: Any, expect: Path | None = None, **kwargs: Any) -> None:
    """Run a WhiteboxTools call and raise if it failed.

    `expect` is the output path. Checking that it exists catches the case where a
    tool returns 0 but wrote nothing, which happens with some argument mistakes.

        checked(wbt, wbt.slope, str(dem), str(out), expect=out, units="degrees")
    """
    buffer: list[str] = getattr(wbt, "_output_buffer", [])
    buffer.clear()

    code = fn(*args, **kwargs)

    if code != 0:
        detail = "\n".join(buffer[-20:]) or "(no output captured)"
        raise WhiteboxError(
            f"{fn.__name__} returned {code}\n"
            f"args={args} kwargs={kwargs}\n"
            f"--- last output ---\n{detail}"
        )

    if expect is not None and not Path(expect).exists():
        detail = "\n".join(buffer[-20:]) or "(no output captured)"
        raise WhiteboxError(
            f"{fn.__name__} returned 0 but did not write {expect}. "
            "Usually an argument name or path problem.\n"
            f"--- last output ---\n{detail}"
        )


def require_tools(wbt, names: Iterable[str]) -> None:
    """Fail at startup if any named tool is missing from this build.

    Tool names are the CamelCase names from the manual. The common surprise is
    SkyViewFactor, which lives in the paid Whitebox Toolset Extension.
    """
    # list_tools() returns snake_case keys ("d8_pointer"); the names callers pass are the
    # manual's CamelCase ("D8Pointer"). Lowercasing alone leaves "d8pointer" vs
    # "d8_pointer" and never matches, so strip underscores from both sides.
    def _norm(name: str) -> str:
        return name.lower().replace("_", "")

    try:
        available = {_norm(k) for k in wbt.list_tools().keys()}
    except Exception as exc:  # noqa: BLE001 -- surface the real problem
        raise WhiteboxError(
            f"Could not list tools: {exc}. If this is a first run, the binary may "
            "still be downloading. On macOS, check Gatekeeper quarantine on the "
            "whitebox package directory."
        ) from exc

    missing = [n for n in names if _norm(n) not in available]
    if missing:
        raise WhiteboxError(
            f"Tools not available in this WhiteboxTools build: {', '.join(missing)}. "
            "These may be in the paid Whitebox Toolset Extension rather than open core. "
            f"Build version: {wbt.version().splitlines()[0] if wbt.version() else 'unknown'}"
        )


def cells_from_metres(raster: Path, metres: float, odd: bool = False) -> int:
    """Convert a distance in metres to a cell count for this raster.

    Many WBT parameters -- dist, radius, filter_size, search_dist -- are in cells.
    Deriving the cell count from an intended metric distance means the parameter
    keeps its meaning when the resolution changes, instead of silently becoming a
    different search radius.

    `odd=True` for kernel-size parameters, which usually require an odd value.
    """
    with rasterio.open(raster) as src:
        res = abs(src.transform.a)
        if res == 0:
            raise ValueError(f"{raster} reports zero pixel size")
        units = src.crs.linear_units if src.crs else "unknown"

    if units.lower() not in {"metre", "meter", "m", "unknown"}:
        raise ValueError(
            f"{raster} has linear units '{units}', not metres. Reproject to a metric "
            "CRS before computing cell counts -- WhiteboxTools will not reproject and "
            "will process degrees as if they were metres."
        )

    n = max(1, int(round(metres / res)))
    if odd and n % 2 == 0:
        n += 1
    return n


def describe(raster: Path) -> str:
    """One-line summary. Useful in logs between chain steps."""
    with rasterio.open(raster) as src:
        res = abs(src.transform.a)
        mb = src.width * src.height * 8 / 1e6
        return (
            f"{raster.name}: {src.width}x{src.height} @ {res:g}m "
            f"{src.crs}  ~{mb:.0f}MB float64"
        )


def memory_estimate_gb(raster: Path, multiplier: float = 2.5) -> float:
    """Rough peak memory for a WBT tool on this raster.

    WhiteboxTools loads full rasters into memory and several tools hold more than
    one at a time. The multiplier is a working assumption, not a guarantee.
    """
    with rasterio.open(raster) as src:
        cells = src.width * src.height
    return cells * 8 * multiplier / 1e9


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage: python wbt_helpers.py DEM.tif   -- prints a raster summary")
        raise SystemExit(0)

    path = Path(sys.argv[1])
    print(describe(path))
    print(f"Estimated peak memory for a WBT tool: {memory_estimate_gb(path):.2f} GB")
    print(f"20 m radius at this resolution = {cells_from_metres(path, 20)} cells")
