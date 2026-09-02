---
name: whiteboxtools
description: Use WhiteboxTools (the `whitebox` Python package) correctly for terrain and hydrological analysis. Covers the file-based execution model, silent-failure checking, unit conventions (cells vs metres), the breach-versus-fill decision, D8 pointer chains, and open-core versus paid-extension tool gating. Use whenever calling wbt.* methods, building a hydrology chain, debugging a WhiteboxTools call that produced nothing or produced garbage, or deciding whether a tool is actually available in the installed build. Do NOT use for general raster I/O with rasterio or GDAL, or for point-cloud work — WhiteboxTools has LiDAR tools but PDAL is the better choice for that.
---

# WhiteboxTools

465 open-core tools with consistent internals and inconsistent surface conventions. Most
time lost to WBT is lost to five things, all listed below.

## The execution model — everything follows from this

**WhiteboxTools is a command-line binary. The Python package is a subprocess wrapper.**

Every call serializes your arguments into CLI flags, launches the binary, which reads a
raster from disk, computes, and writes a raster to disk. There is no in-memory array
interface. `wbt.slope(...)` does not return an array; it returns an integer status code
and leaves a file behind.

Consequences you cannot design around:

- **Chaining N tools means N full read/write cycles.** A ten-step hydrology chain on a
  large DEM is ten complete passes over the data. This dominates runtime far more than any
  algorithmic concern.
- **Intermediates are real files.** Plan where they go and clean them up.
- **Failures are exit codes, not exceptions.** See below — this is the one that bites.

If you need array-level interaction, `whitebox-workflows` (WbW) is a separate native
Python extension from the same author with the same core algorithms and a real in-memory
data model. Its free tier matches open core; WbW-Pro matches the paid extension. Different
package, different import, not a drop-in replacement.

## The five things that go wrong

### 1. Silent failure

`wbt.some_tool(...)` returns `0` on success and `1` on failure. **It does not raise.** A
typo'd path, a missing input, or an unavailable tool gives you a `1`, no output file, and
execution continues happily into the next step where the real error surfaces somewhere
unrelated.

Never call a wbt method bare. Wrap it — see `scripts/wbt_helpers.py`.

### 2. Units: cells versus metres

Many spatial parameters are in **grid cells**, not map units. `dist`, `radius`,
`filter_size`, and `search_dist` are the usual offenders, and the convention is not
uniform across tools.

At 0.5 m resolution, `dist=20` is a 10 m search radius. At 1 m it is 20 m. Change your DEM
resolution and every cell-denominated parameter silently changes meaning.

**Always resolve this per tool with `wbt.tool_help("ToolName")` before trusting a number.**
Compute cell-denominated parameters from a metres value and the raster resolution rather
than hardcoding, so the intent survives a resolution change.

### 3. Breach versus fill

Both remove depressions so flow routing terminates. They are not interchangeable.

- `fill_depressions` raises pits to their spill elevation. Fast, and it **destroys small
  closed depressions** — which in this domain are the features you may be hunting, and in
  karst terrain are most of the landscape.
- `breach_depressions_least_cost` carves a drainage channel out of the pit instead.
  Preserves the surrounding surface. Slower. `dist` is the maximum breach length **in
  cells**.

Default to breaching. Fill only when you specifically want a hydrologically simplified
surface and have no interest in closed depressions.

### 4. Pointer rasters

`d8_flow_accumulation` accepts *either* a DEM or a D8 pointer raster, and it cannot tell
which you gave it. The `pntr` flag is how you say.

```python
wbt.d8_pointer(dem_filled, ptr)
wbt.d8_flow_accumulation(ptr, accum, pntr=True)   # pntr=True is not optional here
```

Omit `pntr=True` and the tool interprets your pointer raster as elevations. It runs
successfully and returns 0. The output is nonsense that looks plausible at a glance.

Conditioning must come first. A pointer built from an unconditioned DEM routes flow into
pits and terminates.

### 5. Extension gating

The manual documents both the open core and the paid Whitebox Toolset Extension. A tool
being in the docs does not mean it is in your build. `SkyViewFactor` is a common surprise —
it is in the paid extension.

Check at setup rather than discovering it mid-chain:

```python
available = set(wbt.list_tools().keys())
```

`scripts/wbt_helpers.py` has a `require_tools()` that fails loudly at startup with the
names that are missing.

## Naming

The manual uses CamelCase (`BreachDepressionsLeastCost`). The Python API uses snake_case
(`breach_depressions_least_cost`). Same tool.

To find something:

```python
wbt.list_tools("openness")        # keyword search
wbt.tool_help("Openness")         # full signature and parameter docs
```

`tool_help` is the authority on argument names and units. This skill is not — versions
shift.

## Routing

| Task | File |
|---|---|
| Setup, error checking, tool availability | `scripts/wbt_helpers.py` |
| The hydrology chain, conditioning through HAND | `scripts/hydro_chain.py` |
| Argument conventions, units, gotchas per tool family | `references/tool-conventions.md` |
| Performance, memory, intermediates, parallelism | `references/performance.md` |
| Worked chains | `examples/` |
| A new analysis script | `templates/wbt_script.py` |

## Configuration worth setting every time

```python
wbt = whitebox.WhiteboxTools()
wbt.verbose = False            # default True floods stdout with progress percentages
wbt.compress_rasters = True    # deflate on output; large savings, negligible cost
wbt.max_procs = -1             # -1 uses all cores; some tools ignore it
```

Use **absolute paths for everything**. `set_working_dir()` plus relative filenames works
until one call gets an absolute path and another gets a relative one, and then you are
hunting for output files in two directories. Absolute paths throughout is one fewer thing
to reason about.
