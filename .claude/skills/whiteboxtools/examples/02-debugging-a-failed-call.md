# Example 2 — Debugging a WhiteboxTools call

WBT failures are usually one of five things. Work them in this order.

## It returned 1

You have an actual error. If you used `checked()`, the captured output is in the
exception. If you called the method bare, you got a `1` and no message — rerun through
`checked()` to see it.

Most common causes: a path that does not exist, a path with a space and no quoting, or an
output directory that does not exist. WBT will not create parent directories.

## It returned 0 but wrote nothing

Usually a wrong argument name. WBT silently ignores unrecognized keyword arguments in some
versions rather than erroring, so `wbt.slope(dem, out, unit="degrees")` — note the missing
`s` — runs, returns 0, and does nothing useful.

```python
wbt.tool_help("Slope")
```

This is the authority. Not the manual, not this skill — the installed build.

## The tool does not exist

```python
"openness" in {k.lower() for k in wbt.list_tools().keys()}
```

If it is missing, it is probably in the paid Whitebox Toolset Extension. `SkyViewFactor` is
the usual surprise. `require_tools()` at startup turns this into an immediate, legible
failure rather than a mid-chain one.

## The output is garbage

Three classics:

**Pointer raster read as elevations.** `d8_flow_accumulation` accepts either a DEM or a
pointer and cannot distinguish them. Missing `pntr=True` produces a result that looks
plausible and is meaningless.

**Wrong input to `wetness_index`.** It takes specific catchment area and slope, not a DEM.
Passing a DEM runs and returns nonsense.

**Degrees processed as metres.** WBT copies the CRS through and never reprojects. Feed it a
geographic raster and every distance-denominated parameter is wrong by a factor of roughly
100,000. `cells_from_metres()` raises on non-metric linear units for this reason.

## The output extent shrank

Filters erode the valid area by the kernel radius without warning. If you chained several
filters, the cumulative loss can be substantial. Check `src.bounds` between steps.

## First run fails opaquely on macOS

The `whitebox` package downloads its binary on first import, and on Apple Silicon Gatekeeper
may quarantine it.

```bash
xattr -dr com.apple.quarantine "$(python -c 'import whitebox, os; print(os.path.dirname(whitebox.__file__))')"
```

## Everything is slow

Almost always the DEM is bigger than the question. Clip to the AOI first, and run terrain
chains at the resolution the answer needs rather than the resolution you have — the
modelling grid does not need 0.5 m. See `references/performance.md`.
