# Example 2 — The pipeline ran and produced nothing

PDAL's most common failure is a successful run with an empty result. Exit code 0, a raster
full of NoData, no error message. Four causes, in order of likelihood.

## 1. Bounds in the wrong CRS

`readers.ept` interprets `bounds` in **the EPT's own CRS**. The USGS 3DEP public bucket is
EPSG:3857. Pass UTM or lat/lon and the box lands somewhere with no data — often in the ocean
— and you get zero points, no error.

Diagnose by removing the bounds entirely and reading a tiny `resolution`-limited sample. If
that returns points and your bounded read does not, the bounds are the problem.

Also check the syntax. It is `([xmin,xmax],[ymin,ymax])` — X range first, then Y range. Not
`(xmin,ymin,xmax,ymax)`. Getting the ordering wrong produces a degenerate or transposed box.

## 2. No ground classification

`filters.range` with `Classification[2:2]` selects ground. If the source was never
classified, every point is class 0 or 1, the filter matches nothing, and the pipeline
succeeds while writing an empty raster.

```bash
python scripts/inspect.py input.laz
```

If class 2 is absent, classify it yourself — `templates/reclassify_ground.json`. Note that
SMRF is not streamable, so tile large areas and buffer each tile by at least the `window`
value or you get seams at tile edges.

## 3. Resolution in the wrong units

`resolution` in `writers.gdal` is in **output CRS units**. If the reprojection stage comes
after the writer, or is missing, and your source is geographic, then `"resolution": 1.0`
means one degree. You get a one-pixel raster, or a raster covering a continent.

Correct order: read → filter → reproject → write.

## 4. Crop polygon in the wrong CRS

`filters.crop` takes WKT in the CRS of the pipeline *at that point in the stage list*. Put
the crop before the reprojection with a polygon in the target CRS and it clips everything
away.

Either crop before reprojection with source-CRS WKT, or after with target-CRS WKT. Be
deliberate about which.

## Narrowing it down

Bisect the pipeline. Replace `writers.gdal` with `writers.las` and see whether points come
out at all:

```json
{ "type": "writers.las", "filename": "debug.laz", "compression": "laszip" }
```

Then `pdal info --summary debug.laz`. If the point count is zero, the problem is upstream in
a reader or filter. If it is non-zero, the problem is in the writer — almost always
resolution units or radius.

Strip filters one at a time from the bottom until points appear. The last filter you removed
is the culprit.

## Two other failure shapes

**Hangs instead of failing.** An EPT read with bounds outside the dataset waits rather than
erroring. `run_pipeline.run(..., timeout=...)` turns that into an actionable message.

**Memory climbs until it dies.** A non-streamable stage on too large an input. Check with
`pdal pipeline --stream` — it will say "Pipeline is not streamable" and name the reason.
SMRF, outlier, sample and hag_delaunay all block streaming. Tile.
