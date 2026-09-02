# Example 1 — AOI to bare-earth DEM from 3DEP

The end-to-end path, with the checks that stop you debugging an empty raster.

## 1. Find the project

Browse https://usgs.entwine.io/ for the EPT project covering your area. Names look like
`USGS_LPC_<STATE>_<Region>_<Year>_LAS_<publication year>`.

Confirm the CRS rather than assuming:

```bash
curl -s https://s3-us-west-2.amazonaws.com/usgs-lidar-public/<PROJECT>/ept.json | jq '.srs, .points, .bounds'
```

The USGS public bucket is EPSG:3857. It has been consistent, but check — the cost of being
wrong is an afternoon.

## 2. Pull a small test box first

Before committing to the full AOI, pull one square kilometre. It confirms the project name,
the bounds CRS, and that ground classification exists, in about a minute.

```bash
python scripts/dem_from_ept.py \
    --project USGS_LPC_... \
    --bounds 512000 3995000 513000 3996000 \
    --bounds-crs EPSG:26916 \
    --resolution 1.0 \
    --out test/
```

If it returns no points, it is almost always the bounds CRS. The script converts for you, so
check that `--bounds-crs` actually matches the numbers you passed.

## 3. Read the coverage report

The script writes a `ground_count.tif` alongside the DEM and prints a coverage summary. This
is the check most people skip and it is the one that determines what resolution is honest.

```
Ground-return coverage at this resolution:
  cells with no ground return :  31.2%  (interpolated, not measured)
```

Over a quarter interpolated means you do not have a DEM at that resolution — you have a
coarser one upsampled by gap filling. Every subtle feature in it is at risk of being an
interpolation artifact.

The fix is to coarsen the grid, not to raise `window_size`. Raising the window manufactures
more surface and hides the problem.

Under closed canopy at QL2, 0.5 m is usually optimistic and 1 m is honest. In open ground
0.5 m is fine. Let the count raster decide rather than picking a number you like.

## 4. Run the real AOI

Same command, real bounds. For anything beyond a few tens of square kilometres, tile it —
one `bounds` request per tile, run concurrently. EPT tiling needs no index and the requests
are independent, so a process pool scales cleanly to four to eight before network throughput
flattens the returns.

## 5. Keep the metadata

`pdal_metadata.json` records what actually ran: resolved paths, every stage's options, the
PDAL version. Keep it next to the DEM. It costs nothing and it is the only record of what
produced a given raster.

## What comes next

The DEM feeds the terrain chain. Two things to carry forward:

- Terrain derivatives run on the **original** DEM. Hydrological conditioning modifies
  elevations to make flow route, which is exactly what you do not want under a
  feature-detection render.
- The resolution you settled on here sets the ceiling on what is detectable. If the count
  raster forced you to 1 m, do not later tune detection parameters as though you had 0.5 m.
