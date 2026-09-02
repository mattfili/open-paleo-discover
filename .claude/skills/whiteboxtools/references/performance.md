# Performance and operations

## Where the time goes

Runtime is dominated by disk I/O, not computation. Every tool is a full read of the input
and a full write of the output. A ten-step chain on a 4 GB DEM moves something like 80 GB
through the filesystem.

Implications, in order of impact:

**Cut the DEM to the AOI before doing anything else.** Running a chain over a full county
tile to analyse one park is the single most common waste. Clip first.

**Work at the coarsest resolution the task allows.** The detection grid needs 0.5 m; the
modelling grid does not. Do not run the hydrology chain at 0.5 m and then resample to 10 m
— run it at the resolution the answer needs. Terrain derivatives at 0.5 m over a large AOI
will take hours and tell you nothing that 1 or 2 m would not.

**Put intermediates on fast local storage.** Not a network mount, not an external drive.

**`compress_rasters = True`.** Deflate compression costs a little CPU and saves a lot of
write time on the large float rasters these chains produce.

## Parallelism

`wbt.max_procs = -1` uses all cores. Many tools are single-threaded regardless — the
hydrology chain in particular is largely sequential by nature, since flow routing depends
on globally ordered elevations.

Real parallelism here comes from running **separate AOIs concurrently**, not from making
one chain faster. Each WBT invocation is an independent subprocess, so a process pool over
AOIs scales cleanly. Watch memory: each concurrent chain holds its own raster.

## Memory

WBT loads full rasters into memory. A float64 raster is 8 bytes per cell:

| Extent | 0.5 m | 1 m | 10 m |
|---|---|---|---|
| 1 km² | 32 MB | 8 MB | 0.08 MB |
| 40 km² (a large park) | 1.3 GB | 320 MB | 3 MB |
| 500 km² | 16 GB | 4 GB | 40 MB |

Several tools hold more than one raster at once. Assume a 2–3× multiplier over the naive
figure, and note that a 40 km² AOI at 0.5 m is already uncomfortable on a 16 GB machine
once you are three steps into a chain.

If an AOI is too large: tile it, process tiles, mosaic. Hydrology does not tile cleanly —
flow accumulation needs upstream area that may be off-tile — so for the hydrology chain
either process the full hydrological unit or accept edge effects and buffer generously
(a kilometre or more) before clipping back.

## Intermediates

A hydrology chain produces breached DEM, pointer, accumulation, streams, HAND, slope. At
0.5 m over a large AOI that is several gigabytes of files you will never look at again.

Write them to a scratch directory keyed by AOI and parameter set, so a re-run with the same
parameters can skip work and a re-run with different parameters does not collide:

```
scratch/<aoi_slug>/<param_hash>/
```

Keep the pointer and accumulation rasters if you plan to sweep the stream threshold —
`extract_streams` is cheap and re-running it against a cached accumulation raster avoids
redoing the expensive conditioning step every time. That single caching decision makes
threshold sweeps practical rather than tedious.

## Capturing output instead of printing

`verbose = True` prints progress percentages to stdout, which is noise in a script and
worse in a subprocess. Setting `verbose = False` silences it, but then you also lose the
error text on failure.

The callback mechanism gives you both:

```python
lines: list[str] = []
wbt = whitebox.WhiteboxTools()
wbt.verbose = True                 # still needed; callback receives what would print
wbt.set_default_callback(lines.append)
```

Now progress goes into `lines` and you can print it only when the exit code is non-zero.
`scripts/wbt_helpers.py` does this.

## Binary management

The `whitebox` package downloads the WhiteboxTools binary on first use, into the package
directory. Two consequences:

**First run is slow and needs network.** In a container or CI, either pre-warm it or vendor
the binary.

**macOS quarantine.** On Apple Silicon the downloaded binary may be quarantined by
Gatekeeper, producing an opaque failure. Clear it:

```bash
xattr -dr com.apple.quarantine "$(python -c 'import whitebox, os; print(os.path.dirname(whitebox.__file__))')"
```

To pin a specific binary rather than whatever gets downloaded, `wbt.set_whitebox_dir(path)`.

## Version drift

Argument names and defaults change between WBT releases. Two habits that make this
survivable:

**Record the version alongside outputs.** `wbt.version()` returns it. Put it in the
provenance record next to the parameters, so a result can be reproduced against the build
that made it.

**Fail at startup, not mid-chain.** Check tool availability and, where it matters, argument
presence during setup. A chain that dies on step eight after forty minutes of conditioning
is a much worse experience than one that refuses to start.
