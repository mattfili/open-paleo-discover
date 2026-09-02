# Tool conventions by family

`wbt.tool_help("ToolName")` is always the authority on a specific signature. This file
covers the patterns and the traps that recur across families.

## Universal

**Output paths are arguments, not return values.** Every tool takes its output file as a
positional or keyword argument. The return value is an exit code.

**Booleans are Python bools.** `pntr=True`, not `pntr="true"`.

**NoData propagates.** Most tools carry NoData through. A few — notably some filters —
shrink the valid area by the kernel radius. Check output extents when chaining.

**Format.** GeoTIFF in and out works throughout. WBT also has its own `.dep`/`.tas` format;
no reason to use it here. Set `compress_rasters = True` or outputs are uncompressed and
large.

**CRS.** WBT is largely CRS-agnostic — it operates on the grid and copies the projection
through. It does **not** reproject, and it will happily process a raster whose units are
degrees while you assume metres. Reproject before, not during.

## Hydrology

The canonical chain, in order. Skipping or reordering breaks the ones after it.

```
DEM
  → breach_depressions_least_cost      conditioning
  → d8_pointer                          flow direction
  → d8_flow_accumulation(pntr=True)     contributing area
  → extract_streams(threshold=N)        stream network
  → elevation_above_stream              HAND
```

**`breach_depressions_least_cost(dem, output, dist=...)`**
`dist` is maximum breach length **in cells**. Too small and deep pits stay unbreached; too
large and it carves through legitimate ridges. Start around 100 cells and check that the
output has no remaining large pits.

**`d8_pointer(dem, output)`**
Input must be conditioned. Output is a direction-coded raster, not elevations.

**`d8_flow_accumulation(input, output, pntr=False, out_type=...)`**
`pntr=True` when the input is a pointer raster. `out_type` chooses cells, specific
catchment area, or catchment area — the default is cells, which is what `extract_streams`
expects. Change one without the other and your threshold means something different.

**`extract_streams(flow_accum, output, threshold=N)`**
`threshold` is in whatever units `d8_flow_accumulation` produced. With the default it is a
count of upstream cells.

**This is the most consequential parameter in any terrain chain.** It defines what counts
as a stream, which defines HAND, which defines terraces and every distance-to-water metric.
Sweep it; do not accept a default.

**`elevation_above_stream(dem, streams, output)`**
HAND. Wants the *conditioned* DEM, not the original.

There is also `elevation_above_stream_euclidean`, which measures to the nearest stream in
straight-line distance rather than along the flow path. Different quantity, cheaper, worse.
Use the flow-path version unless you have a reason.

## Terrain attributes

**`slope(dem, output, zfactor=None, units="degrees")`**
Default units vary by version — pass `units` explicitly. `zfactor` corrects for vertical
and horizontal units differing; leave it alone for a projected metric CRS, set it if your
DEM is in degrees (but reproject instead).

**`aspect`, `plan_curvature`, `profile_curvature`, `total_curvature`** — same shape.
Curvature outputs are small numbers with long tails; stretch hard to see anything.

**`openness(dem, pos_output, neg_output, dist=...)`**
`dist` in **cells**. Writes two rasters. Positive openness is high on convex features,
negative openness is high on concave; on a flat plane both are 90° regardless of slope.

Verify the exact signature — whether it takes two output paths or one, and the parameter
name for the radius — with `tool_help` before building on it. This is the call most likely
to differ from what is written here.

**`multidirectional_hillshade(dem, output)`** — blended across azimuths, no directional
bias. Good for legibility, weaker than openness for subtle features.

**`hillshade(dem, output, azimuth=315, altitude=30)`** — single sun position. Do not use it
for feature detection; the directional bias hides features whose orientation is unlucky.

**`wetness_index(sca, slope, output)`** — TWI. Note it takes **specific catchment area and
slope**, not a DEM. Produce SCA with `d8_flow_accumulation(out_type="specific contributing
area")` and slope separately. Passing a DEM here is a common error that runs and returns
garbage.

## Filters

Kernel sizes are in **cells**, and are usually required to be **odd**. `filter_size=11` at
0.5 m is a 5.5 m kernel.

`gaussian_filter`, `mean_filter`, `median_filter`, `high_pass_filter` all follow this. For
SLRM specifically, `scipy.ndimage.gaussian_filter` is easier to control and lets you handle
the NoData problem yourself — WBT's filters will erode your valid extent by the kernel
radius without saying so.

## LiDAR tools

WBT has a substantial LiDAR toolset — `lidar_tin_gridding`, `lidar_ground_point_filter`,
`normalize_lidar`, `lidar_idw_interpolation`.

For this project, use PDAL instead. PDAL's pipeline model is better suited to filtering and
gridding chains, it handles EPT and COPC natively, and it is the standard for point-cloud
work. Use WBT for what comes after the DEM exists.

## Vector tools

WBT reads and writes shapefiles. It does not read GeoPackage or GeoJSON in most tools. If
you are working in PostGIS and GeoPandas, do the vector work there and only hand WBT
rasters — round-tripping through shapefiles will silently truncate your field names to ten
characters and mangle your attribute types.

## Tools whose names mislead

- `fill_depressions` — see the breach-versus-fill discussion in SKILL.md. It is not the
  safe default.
- `flow_accumulation_full_workflow` — convenience wrapper that does conditioning, pointer,
  and accumulation in one call. Handy, but it hides the conditioning choice, which is
  exactly the choice you want to be making deliberately.
- `feature_preserving_smoothing` — a normal-vector-based DEM smoother. Genuinely good for
  reducing noise before curvature analysis without rounding off breaks of slope. Nothing to
  do with archaeological features despite the name.
- `remove_off_terrain_objects` — a bare-earth filter for DSMs. If you already have
  ground-classified LiDAR you do not need it.
