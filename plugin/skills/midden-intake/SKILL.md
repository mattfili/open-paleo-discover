---
name: midden-intake
description: >-
  Add a data source to midden or debug one that is failing. Use when writing a new
  sources/*.yml, adding an intake driver, deciding how a fetch should be scoped or cached,
  or working out why an intake run loaded zero rows or the wrong CRS.
---

# Adding and debugging an intake source

## Two YAMLs per source, deliberately

`sources/<name>.yml` is midden's schema — fetch, transform, load.
`semantic/<name>.yml` is boring-semantic-layer's — dimensions, measures, joins.

They are linked by table name and kept apart on purpose: BSL's YAML is its own evolving
contract, and wrapping it in a custom envelope would turn every BSL upgrade into a
migration of that envelope.

## The source file

```yaml
name: nhd_flowline               # must equal the filename stem
description: One sentence on what this is and what it feeds.

fetch:
  driver: pynhd                  # a registered driver name
  params: {layer: flowline, scope: aoi, buffer_m: 2000}
  cache: data/raw/nhd_flowline   # keyed by content hash; a warm cache is a no-op

transform:                       # applied in the order written
  - reproject: {to: EPSG:26916}
  - select: [nhdplusid, gnis_name, streamorde, lengthkm, geometry]
  - rename: {nhdplusid: comid, streamorde: stream_order}
  - filter: "stream_order >= 1"

load:
  target: ref.nhd_flowline
  geometry_column: geom
  mode: replace                  # replace | append | upsert
  upsert_key: [comid]
  index: [gist(geom), btree(stream_order)]
```

**Order in `transform` is load-bearing and it is yours.** `select` names columns as they
arrive from the driver; `filter` usually names them after `rename`. The parser is strict:
an unrecognised key is an error, never a silent drop, because these files are what a human
edits most often.

## Things that fail quietly

**Reproject is not decorative.** NHDPlus HR returns EPSG:4326 regardless of the CRS you
ask it for. Without the reproject step the load fails its CRS assertion — which is the
assertion working. Everything in this project is EPSG:26916, and WhiteboxTools will
happily process degrees as if they were metres.

**Buffer anything hydrological.** HAND is computed from flow accumulated out of the
surrounding catchment, so a network clipped to the AOI is wrong near the edge. The `pynhd`
driver fetches over the AOI's bounding box expanded by `buffer_m`.

**A filter that removes every row raises.** That is deliberate: a source loading zero rows
is invisible downstream and reads as a null result.

**Column names differ between NHD products.** NHDPlus HR keys reaches on `nhdplusid`;
NHDPlus V2 used `comid`. The transform renames HR's back to `comid` so the confluence SQL
and everything downstream keep working.

## Adding a driver

Drivers live in `midden/intake/drivers/` and implement one call:

```python
@register("my_driver")
def fetch(params: dict, aoi: Aoi | None, dest: Path) -> Path:
    """Retrieve the source and write it to dest as a GeoPackage."""
```

Registering a driver should never require touching the runner. Name the module for what it
talks to, not for the library it wraps — and never give it the same name as a package it
imports.

## Debugging a run

`midden_list_sources` shows each source, its target, and its last run and status.
The `derivation` semantic model has the detail: a failed run keeps its row, its parameters,
and its error, so `midden_query(model="derivation", dimensions=["operation","status"])` is
the fastest way to see what broke.

Fetches are cached by content hash of `(driver, params, AOI geometry)`. Changing the AOI
changes the key, so a different AOI always re-fetches. Editing the transform or load does
**not** invalidate the cache, because those are cheap and must be able to take effect
without a re-download. Pass `force=True` to re-fetch.
