---
name: pdal-pipelines
description: Build and debug PDAL pipelines for LiDAR point-cloud processing — reading LAS/LAZ/EPT/COPC, filtering by classification, reprojecting, and gridding to a bare-earth DEM. Covers the EPT bounds-CRS trap, ground-classification checks, writers.gdal gap filling, stage ordering, and when to reclassify ground yourself with SMRF. Use whenever writing a pipeline JSON, extracting points for an area of interest, producing a DEM from LiDAR, or debugging a pipeline that returned no points or a DEM full of holes. Do NOT use for raster analysis after the DEM exists — that is WhiteboxTools or rasterio.
---

# PDAL pipelines

## Call the CLI, not the Python bindings

The PDAL Python bindings compile against libpdal and the versions must match. On macOS this
breaks regularly and the failure is a build error deep in a wheel.

Use the CLI as a subprocess:

```python
subprocess.run(["pdal", "pipeline", str(pipeline_path)], check=True)
```

You lose nothing. The pipeline is JSON either way, so you write the same dict and dump it
to a temp file instead of passing it to `pdal.Pipeline`. `scripts/run_pipeline.py` wraps
this with error handling.

Install with `brew install pdal`. Confirm with `pdal --version`.

## The pipeline model

A pipeline is a JSON array of **stages**, executed in order:

```json
{
  "pipeline": [
    { "type": "readers.ept",         "filename": "..." },
    { "type": "filters.range",       "limits": "Classification[2:2]" },
    { "type": "filters.reprojection","out_srs": "EPSG:26916" },
    { "type": "writers.gdal",        "filename": "dem.tif", "resolution": 0.5 }
  ]
}
```

Readers first, writers last, filters between. A bare string in the array is shorthand for a
reader or writer inferred from the file extension.

## The four traps

### 1. EPT bounds are in the EPT's own CRS

This is the one that wastes an afternoon.

`readers.ept` takes a `bounds` parameter to subset spatially. Those bounds are interpreted
in **the CRS of the EPT dataset**, not in your project CRS and not in whatever you last
thought about.

**The USGS 3DEP public EPT bucket is EPSG:3857** (Web Mercator). Pass UTM coordinates and
you will get zero points back, or points from somewhere in the Atlantic, with no error.

Convert explicitly:

```python
from pyproj import Transformer
t = Transformer.from_crs("EPSG:26916", "EPSG:3857", always_xy=True)
xmin, ymin = t.transform(utm_xmin, utm_ymin)
xmax, ymax = t.transform(utm_xmax, utm_ymax)
bounds = f"([{xmin},{xmax}],[{ymin},{ymax}])"
```

Note the syntax: `([xmin,xmax],[ymin,ymax])`. X range first, then Y range — **not**
`(xmin,ymin,xmax,ymax)`. Optionally a third bracket pair for Z. It is a PDAL-specific
string, not GeoJSON and not a WKT envelope.

Verify the EPT's CRS rather than trusting this file:

```bash
curl -s https://s3-us-west-2.amazonaws.com/usgs-lidar-public/<PROJECT>/ept.json | jq .srs
```

### 2. Ground classification may not exist

`filters.range` with `Classification[2:2]` selects ground returns. If the data was never
classified, every point is class 1 (unassigned) or 0, the filter matches nothing, and you
get an empty output — **with no error**. The pipeline succeeds and writes an empty or
all-NoData raster.

Always check before filtering:

```bash
pdal info --stats --dimensions Classification input.laz
```

If ground is absent, classify it yourself with `filters.smrf` (see
`templates/reclassify_ground.json`). SMRF is the Simple Morphological Filter and is the
usual default; `filters.pmf` is the older progressive morphological filter.

Relevant ASPRS classes: 1 unassigned, 2 ground, 3–5 low/medium/high vegetation, 6 building,
7 low noise, 9 water, 18 high noise.

### 3. writers.gdal leaves holes without `window_size`

Gridding ground points to a raster produces NoData wherever no ground point fell in a cell.
Under dense canopy at QL2 density that is a lot of cells, and the resulting DEM is
speckled — which then propagates into every derivative and eats your edges when you smooth.

```json
{
  "type": "writers.gdal",
  "filename": "dem.tif",
  "resolution": 0.5,
  "output_type": "idw",
  "radius": 0.75,
  "window_size": 3
}
```

- `output_type` — `idw` or `mean` for a bare-earth DEM. `min` is for something else and
  will give you a pitted surface. `count` is useful diagnostically.
- `radius` — search radius for the interpolation, in output CRS units. Roughly 1.5×
  resolution is a reasonable start.
- `window_size` — fills remaining gaps by expanding the search. Start at 3; raise it if the
  DEM is still speckled, but understand you are inventing elevation in those cells.

Bigger `window_size` is not free. It smooths real relief and manufactures surface where
there were no returns. If you need a large window to get a continuous DEM, the honest
conclusion is that the point density will not support your target resolution — coarsen the
grid instead.

### 4. Stage order determines what units mean

`resolution` in `writers.gdal` is in **output CRS units**. Reproject *before* writing, or
`"resolution": 0.5` means half a degree.

Correct order: read → filter classification → reproject → write. Reprojecting after the
writer is not possible; reprojecting before the range filter just wastes work on points you
are about to discard.

## Routing

| Task | File |
|---|---|
| Running a pipeline with error handling | `scripts/run_pipeline.py` |
| AOI → bare-earth DEM from 3DEP EPT | `scripts/dem_from_ept.py` |
| Checking a file before committing to it | `scripts/inspect.py` |
| Bare-earth DEM from classified LAZ | `templates/dem_bare_earth.json` |
| EPT subset by AOI | `templates/ept_aoi_extract.json` |
| Classifying ground when it is missing | `templates/reclassify_ground.json` |
| Noise removal | `templates/denoise.json` |
| Stage reference and less-obvious filters | `references/stage-reference.md` |
| Density, memory, tiling, streaming | `references/scale-and-density.md` |
| Worked runs | `examples/` |

## Before any real work

```bash
pdal info --summary input.laz          # extents, point count, CRS, dimensions
pdal info --stats --dimensions Classification input.laz
```

Three questions answered in two commands: is it classified, what CRS is it in, and how many
points are there. Skipping this is how you end up debugging an empty DEM.
