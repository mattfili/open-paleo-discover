# Stage reference

`pdal --options <stage>` lists every option for a stage in the installed build. That is the
authority; this file covers what is worth knowing and what is easy to get wrong.

## Readers

**`readers.las`** — LAS and LAZ. `filename` accepts a glob for multiple files. Set
`nosrs: true` only if you need to override a wrong embedded CRS, and pass `default_srs`
alongside it.

**`readers.ept`** — Entwine Point Tiles, the format the USGS 3DEP public bucket uses.

```json
{
  "type": "readers.ept",
  "filename": "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/<PROJECT>/ept.json",
  "bounds": "([xmin,xmax],[ymin,ymax])",
  "resolution": 1.0
}
```

- `bounds` is in the **EPT's CRS**, which for that bucket is EPSG:3857. See SKILL.md.
- `resolution` requests a level of detail rather than full density. Setting it to roughly
  your target grid size pulls far less data and is usually what you want — asking for full
  density and then gridding at 0.5 m discards most of what you downloaded.
- Streams from the network. Slow starts are normal; a hung read usually means the bounds
  landed outside the dataset.

**`readers.copc`** — Cloud Optimized Point Cloud. Same spatial-query benefits as EPT in a
single file. Prefer it over EPT for local data.

**Multiple readers** are allowed; PDAL merges them. Useful for stitching adjacent tiles,
but see the tiling discussion in `scale-and-density.md` before doing it at scale.

## Filters

**`filters.range`** — dimension-based selection.

```json
{ "type": "filters.range", "limits": "Classification[2:2]" }
```

Ranges are inclusive, comma-separated for multiple conditions:
`"Classification[2:2],Z[100:400]"`. Negation with `!`.

Newer PDAL has **`filters.expression`**, which takes a readable expression string
(`"Classification == 2"`) and is clearer for anything compound. Both work in current
builds; check `pdal --options filters.expression` to confirm it exists in yours.

**`filters.reprojection`** — `out_srs` required, `in_srs` only if the source lacks a CRS or
has a wrong one. Put it after classification filtering and before the writer.

**`filters.crop`** — clip to a polygon.

```json
{ "type": "filters.crop", "polygon": "POLYGON((...))" }
```

WKT in the current CRS of the pipeline at that point. Order matters: crop after reprojection
if your WKT is in the target CRS. `filters.crop` is the right tool for a real AOI boundary;
`bounds` on a reader is a rectangle and only a prefilter.

**`filters.smrf`** — Simple Morphological Filter, ground classification. Use when the data
is unclassified.

```json
{ "type": "filters.smrf", "scalar": 1.25, "slope": 0.15, "threshold": 0.5, "window": 18 }
```

Those are near the defaults and are a reasonable start for mixed terrain. `slope` is the
expected terrain slope as a ratio; raise it in steep country or SMRF will classify hillside
as non-ground. `window` is the maximum window size in map units and should exceed the
largest non-ground object you want removed.

SMRF outputs classifications; it does not filter. Follow it with `filters.range`.

**`filters.pmf`** — the older progressive morphological filter. SMRF generally performs
better. Present for compatibility.

**`filters.outlier`** — statistical or radius-based noise removal. Run it **before** ground
classification; a single low outlier will drag a whole neighbourhood of SMRF's surface down
with it.

```json
{ "type": "filters.outlier", "method": "statistical", "mean_k": 8, "multiplier": 2.5 }
```

It marks points as class 7 rather than deleting them, so filter afterwards.

**`filters.assign`** — set a dimension conditionally. Common use is resetting classification
before reclassifying: `{"type": "filters.assign", "value": "Classification = 0"}`.

**`filters.sample`** — Poisson-disk thinning to a minimum point spacing. Better than random
decimation for gridding because it preserves even coverage.

**`filters.returns`** — select by return type (`"first"`, `"last"`, `"only"`,
`"intermediate"`). Last returns approximate ground under vegetation, but classification is
better where it exists.

**`filters.hag_nn`** / **`filters.hag_delaunay`** — height above ground per point. Useful
for canopy metrics, and for confirming ground classification is sane before you trust it.

## Writers

**`writers.gdal`** — the raster writer. Options that matter:

| Option | Notes |
|---|---|
| `resolution` | Output CRS units. Reproject first. |
| `output_type` | `idw`, `mean`, `min`, `max`, `count`, `stdev`, or `all`. Use `idw` or `mean` for bare earth. |
| `radius` | Interpolation search radius, output CRS units. ~1.5× resolution to start. |
| `window_size` | Gap-fill expansion. See the warning in SKILL.md. |
| `nodata` | Default -9999. |
| `gdaldriver` | `GTiff` default. |
| `gdalopts` | e.g. `"COMPRESS=DEFLATE,TILED=YES"` — set these or your DEM is uncompressed and untiled. |

`output_type: "count"` is the diagnostic setting. Write a count raster alongside the DEM and
you can see exactly where ground returns are sparse — which tells you whether a hole is
canopy or a real gap, and whether your resolution is supportable.

**`writers.las`** — write points back out. `compression: "laszip"` for LAZ. `a_srs` to set
the output CRS.

**`writers.copc`** — write COPC. Worth doing once for any point cloud you will query
repeatedly.

## Stage ordering

The order that is almost always right:

```
reader
  → filters.crop            (rough spatial cut, cheapest first)
  → filters.outlier         (before classification, not after)
  → filters.smrf            (only if not already classified)
  → filters.range           (Classification[2:2])
  → filters.reprojection    (before the writer, so resolution means metres)
  → writers.gdal
```

Two rules behind it: discard points as early as possible, and reproject as late as possible
before the writer.

## Metadata and provenance

```bash
pdal info --metadata input.laz
pdal pipeline --metadata meta.json pipeline.json
```

The second writes what actually ran, including resolved paths and every stage's options.
Keep it with the output — it is the record of what produced a given DEM, and it costs
nothing.
