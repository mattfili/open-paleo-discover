# Example 1 — Hydrology chain and threshold sweep

The chain that everything else depends on, and the sweep that makes it meaningful.

## Run the sweep, not a single value

```bash
python scripts/hydro_chain.py dem.tif out/ --threshold 1000 2500 5000 10000 20000
```

Conditioning and flow accumulation are cached, so this costs one expensive pass plus
five cheap ones rather than five expensive ones. That caching decision is the difference
between sweeping routinely and never sweeping.

## Read the histogram, not the mode count

`hydro_report.json` reports modes per threshold. The script prints which threshold gave
the most mode structure, but treat that as a hint. Plot the histograms.

What you are looking for:

- **Separated humps** — real terrace surfaces. This is what a correctly-thresholded
  valley looks like.
- **One broad hump** — threshold too high. HAND is being measured to a distant channel,
  smearing the surfaces together.
- **Everything piled near zero** — threshold too low. Every swale became a stream, so
  nothing is far above a stream.
- **No modes at all, in dissected upland** — possibly correct. Not every AOI has terraces.
  If the AOI brief predicted no terraces, this confirms it rather than failing.

## Karst warning

In the Central Basin and Highland Rim, surface drainage is discontinuous — streams sink and
resurface. Flow accumulation over a karst DEM produces confident nonsense in the uplands,
and HAND inherits it.

The chain works well in main-stem river valleys and poorly on dissected karst plateau. If
your AOI is mostly upland karst, treat terrace output as unreliable and lean on the
detection renders instead.

## Why breaching

`hydro_chain.py` uses `breach_depressions_least_cost`, not `fill_depressions`. Filling
raises pits to their spill elevation, which erases small closed depressions.

In this domain those depressions may be the target — ore pits, cellar holes, borrow pits.
In karst they are most of the landscape. Filling first and then hunting for depressions is
self-defeating, and it is an easy mistake because `fill_depressions` is the more commonly
cited tool.

## Chaining onward

The conditioned DEM, not the original, feeds everything downstream. `elevation_above_stream`
takes it, and so should any later terrain derivative that assumes routable flow.

The exception is the detection renders — openness and SLRM should run on the **original**
DEM. Conditioning modifies elevations to make flow route, which is exactly the kind of
surface alteration you do not want under a feature-detection render.
