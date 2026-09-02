# Density, memory, and tiling

## Point density determines achievable resolution

USGS quality levels, aggregate nominal pulse density:

| QL | pulses/m² | Nominal point spacing |
|---|---|---|
| QL0 | 8.0 | 0.35 m |
| QL1 | 8.0 | 0.35 m |
| QL2 | 2.0 | 0.71 m |

QL2 is baseline 3DEP coverage and is what most of the country has.

**Those are pulse densities, not ground-return densities.** Under closed canopy, ground
returns can be a small fraction of pulses — often well under 1 per m². The practical
question is not "what is the QL" but "how many ground points per cell do I actually have."

Answer it directly:

```bash
pdal info --stats input.laz    # total points, extent -> overall density
```

and then write a count raster at your target resolution:

```json
{ "type": "writers.gdal", "filename": "count.tif", "resolution": 0.5, "output_type": "count" }
```

Open it. Cells with zero ground returns are cells where your DEM is interpolated rather than
measured. If most cells are 0 or 1 at 0.5 m, you do not have a 0.5 m DEM — you have a
coarser DEM that has been upsampled by the gap-filling, and every subtle feature you think
you see in it is at risk of being an interpolation artifact.

**Rule of thumb:** you want at least a few ground returns per cell. At QL2 with 2 pulses/m²
and heavy canopy, 0.5 m is optimistic and 1 m is honest. In open ground 0.5 m is fine.

This is worth resolving before tuning any detection parameters, because it sets the floor on
what is detectable at all.

## Memory

PDAL loads points into memory unless the pipeline can stream. A LAZ file expands roughly
5–10× on read.

| Extent at QL2 | Points | Approx. RAM |
|---|---|---|
| 1 km² | ~2 M | ~100 MB |
| 40 km² | ~80 M | ~4 GB |
| 500 km² | ~1 B | ~50 GB |

A 40 km² park is manageable. A county is not, in one pass.

## Streaming

`pdal pipeline --stream` processes in chunks and keeps memory flat. It only works if every
stage in the pipeline is streamable.

Streamable: `readers.las`, `filters.range`, `filters.expression`, `filters.reprojection`,
`filters.assign`, `writers.las`, `writers.gdal`.

Not streamable: `filters.smrf`, `filters.outlier`, `filters.hag_delaunay`, `filters.sample`
— anything needing a global view of the points.

So the common bare-earth pipeline over already-classified data streams; the reclassification
pipeline does not. If you need SMRF on a large area, tile it.

PDAL will tell you rather than silently using more memory:

```bash
pdal pipeline --stream pipeline.json
# "Pipeline is not streamable" if a stage blocks it
```

## Tiling

For anything beyond a few tens of km², tile.

```bash
pdal tindex create index.gpkg "tiles/*.laz"          # spatial index of a tile set
pdal tindex merge index.gpkg out.laz --bounds "(...)"
```

**Buffer your tiles.** Neighbourhood operations — SMRF, outlier removal, IDW gridding — need
context beyond the tile edge, and without a buffer you get visible seams in the output DEM.
A buffer of 20–50 m is usually enough for gridding; SMRF wants at least its `window` value.

Process buffered, then clip each output back to the unbuffered tile before mosaicking.

For EPT sources, tiling is simpler: issue one `bounds` request per tile. No index needed, and
each request is independent so they parallelize cleanly.

## Reading from EPT efficiently

Two levers, and using them well is the difference between a two-minute pull and a
forty-minute one.

**`resolution`.** Requests a level of detail rather than full density. Set it near your
target grid size. Asking for full density and then gridding at 1 m downloads several times
more data than the output can express.

**`bounds`.** Always set it. In the EPT's CRS — EPSG:3857 for the USGS public bucket. An
unbounded read of a state-scale EPT is not something you want to start by accident.

Rough figure for planning: QL2 is around 30 MB per square mile as LAZ. A 40 km² AOI is
roughly 15 km² × ... — work it in your own units, but the point is that a county is tens of
gigabytes and Middle Tennessee entire is several hundred. AOI-scoped reads are not an
optimization, they are the only workable approach.

## Parallelism

PDAL is largely single-threaded per pipeline. Parallelism comes from running independent
pipelines concurrently — one per tile or per AOI.

A process pool over tiles scales close to linearly until you saturate disk or, for EPT,
network. Four to eight concurrent EPT reads is usually where the returns flatten.

## Diagnosing a slow or hung pipeline

**Hung on an EPT read** — bounds are probably outside the dataset, or in the wrong CRS. The
reader waits rather than failing. Verify with a tiny bounds box first.

**Slow gridding** — `radius` or `window_size` too large. Both scale badly.

**Memory climbing until it dies** — a non-streamable stage on too large an input. Check with
`--stream`, then tile.

**Fast but empty output** — not a performance problem. The classification filter matched
nothing. See SKILL.md.
