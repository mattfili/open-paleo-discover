# midden — roadmap

**This file is the canonical record of what is built, what is not, and what is known to be
broken.** Update it in the same commit as the work it describes. `spec.md` says what the
project *should* be; this file says where it actually is.

Last verified: 2026-09-02, against a live database and a full pipeline run.

---

## Status at a glance

| Milestone | State | What it delivers |
|---|---|---|
| M0 foundation | **done** | Postgres 17 + PostGIS 3.5 + hypopg, schemas, roles, CLI, provenance ledger |
| M1 intake | **done** | Strict source YAML, driver registry, content-hash cache, 13 AOIs seeded |
| M2 terrain | **done** | Both grids: 10 m modelling (3DEP) and 0.5 m detection (PDAL/EPT) |
| M3 semantic layer | **done** | 5 BSL models over `ref.*` / `derived.*` via DuckDB |
| M4 MCP + plugin | **done** | 18 tools, 4 plugin skills, glossary, 10 evals |
| M5 features + overlay | **done, result negative** | 10 m stack, SSURGO soils, weighted overlay — **weight set falsified** |
| M6 render | **done** | QGIS project emitter, self-contained Leaflet artifact |

All seven milestones in `spec.md` §11 are implemented. The pipeline runs end to end. The
**predictive output is not yet trustworthy** — see "Known broken" below.

---

## What exists, concretely

**Data loaded.** 13 AOIs (seeded from TDEC Public Access Lands, Nashville Metro Parks, and
TNMap's National Register layer — never hardcoded extents), 500 NHDPlus HR flowline
reaches, 646 confluences, 309 SSURGO map-unit polygons, 44 catalogued raster assets, 5
feature stacks.

**Interfaces.** 9 CLI sub-apps (`db aoi intake terrain semantic features score render`,
plus `doctor`). 18 MCP tools, 10 read-only and 8 write. A Claude Code plugin at `plugin/`
with four skills and a glossary.

**Tests.** Three, as `spec.md` §3 requires: CRS uniformity, DEM units, intake YAML
round-trip. 11 test functions, all passing.

---

## Known broken, in priority order

### 1. The weight set is falsified — `terrace_class` is the cause

```
mound-bottom       74.6th percentile, needs 95.0   FAIL
castalian-springs  86.4th percentile, needs 95.0   FAIL
```

Diagnosis, from comparing normalised feature means inside the control footprint against the
surrounding buffered extent:

| feature | site | regional | weight | reading |
|---|---|---|---|---|
| `terrace_class` | 0.088 | 0.058 | **3.0** | top weight, no discrimination |
| `slope_deg` | 0.680 | 0.429 | 2.5 | carrying the signal |
| `dist_to_confluence_m` | 0.607 | 0.443 | 2.0 | carrying the signal |
| `dist_to_stream_m` | 0.964 | 0.904 | 2.0 | mild |
| `drainage_class` | 0.941 | 0.913 | 1.5 | no signal — soils uniformly well drained here |
| `twi` | 0.443 | 0.560 | 0.5 | site is *worse* than background |

**Root cause.** `terrace_class` labels HAND modes by ordinal position. "Class 2" means
second-lowest mode, and the weight set assumes that is the archaeological T1. It is not:
at `mound-bottom` the site sits nearest the **third** mode (~11.7 m HAND against modes at
0.38 / 3.38 / 10.62 m), and at `castalian-springs` there are only two modes at all.

**Proposed fix, not yet built.** Anchor terrace labelling to soils rather than to mode
counting. SSURGO flooding frequency is already loaded in `ref.ssurgo_mapunit.flood_freq`:
T0 is definitionally the surface that floods, so the lowest HAND mode whose soils are
*not* frequently flooded is T1. This is better than reweighting because it fixes the
feature rather than compensating for it.

**Do not tune the controls to fit.** One principled parameter change was already tried and
recorded: `hand_mode_tolerance_m` 1.0 → 2.0, on the grounds that a terrace tread has
metre-scale microtopography. It moved both controls the wrong way (75.5→74.6, 88.5→86.4).

### 2. The hearths control has never been run

`montgomery-bell` is the **fine** detection control — a 19th-century iron district whose
relict charcoal hearths (flat circular platforms ~10 m across) are what should set
`terrain.openness.search_radius_m`. It has **zero detection-grid rasters**. Only
`harpeth-narrows` has been through the 0.5 m chain, and everything visible there (relict
channels, roadbeds) is an order of magnitude larger than a hearth.

So the central claim of the detection half — *does this resolve features at the scale we
care about* — is unverified. The park is 10.9 km² (~44 M cells at 0.5 m), so cut a small
AOI around the known iron-district features rather than grinding the whole park.

### 3. Seven of thirteen AOIs have no terrain at all

Missing: `beaman-park`, `bledsoe-creek`, `castalian-springs-nr`, `cedars-of-lebanon`,
`harpeth-hidden-lake`, `harpeth-newsoms-mill`, `harpeth-highway-70`, `long-hunter`.

`beaman-park` matters most. Every AOI currently carrying terrain is Central Basin river
valley; Beaman is dissected Highland Rim with steep hollows and headwater streams.
`spec.md` §2 says including it is "what keeps the model from learning 'Middle Tennessee
means big river terrace'" — which is currently exactly what it could be learning.

### 4. The control test and the enrichment statistic measure different things

`control_check.py` tests the **mean** percentile over a control footprint. Those footprints
are whole management units including river channel and bluffs, so even a good model cannot
average above the 95th percentile there. Measured separately:

| control | footprint cells in regional top 5% | vs chance |
|---|---|---|
| `mound-bottom` | 20.1% | **4.0×** |
| `castalian-springs` | 14.0% | **2.8×** |

Both numbers are real; they answer different questions. Changing the test is a deliberate
decision, not a convenience — it is the falsifier, and loosening it to get a pass is
exactly the failure mode the discipline exists to prevent.

---

## Not built

| Item | Where specified | Note |
|---|---|---|
| `priest-drawdown` AOI | §7, the worked example | Derived, not fetched: NHD waterbody minus a pool-elevation contour. **Carries the NAVD88/NGVD29 datum trap** — an unconfirmed datum makes the figure unusable. |
| Historical topo quads | §6 | `http_file` driver target. Changes the interpretation of every drawdown AOI: shows pre-impoundment floodplain, fords, mills, vanished roads. |
| 1930s–50s aerial photography, GLO plats | §6 | Availability varies by county. |
| NLCD canopy (`canopy_pct`) | §7 | Companion band: a predictor of data quality, not of settlement. Distinguishes a weak result in forest from a weak result in an open field. |
| `midden_render_chart` | §9 | Needs a chart backend dependency (Altair or similar). |
| Evals actually executed | §9 | `plugin/mcp/evals.xml` is written with hand-checked answers but has never been run against the server. |
| Ranked polygon output | §11 M5 | Scoring produces a raster; polygonising the top percentile is not implemented. |

---

## Deferred by design

Recorded so the reasoning is not relitigated. See `spec.md` §13.

- **Statistical site-prediction** (MaxEnt, gradient boosting). Needs known site locations,
  which brings two hard problems: survey bias (a naive model learns "sites are near
  highways") and output sensitivity (a probability surface fitted on real sites is
  functionally a treasure map). Would require a `restricted` schema and an export check.
- **Fieldwork loop.** Trivial to add, pointless until someone walks something.
- **Browser explorer.** QGIS plus the artifact export covers it.
- **Anything cloud.**

---

## Environment gotchas that cost time

Each of these was learned the expensive way. They are in the code as comments too.

- **`Openness` is not in WhiteboxTools open core.** The binary answers `Unrecognized tool
  name Openness` while the Python wrapper still exposes an `openness()` method, because the
  wrapper is generated from the full manual including paid Toolset Extension tools. midden
  vendors RVT's horizon scan instead (`src/midden/terrain/_rvt_vis.py`, Apache-2.0).
- **WhiteboxTools returns exit code 0 while panicking.** It rejects floating-point
  compression predictors. Anything WBT reads must be written without `PREDICTOR`. The
  skill's `checked()` wrapper is the only reason this surfaces at all.
- **`pdal-pipelines/scripts/inspect.py` shadows the stdlib `inspect` module.** Running it as
  a subprocess breaks Python itself. `midden.skills.load()` appends to `sys.path` rather
  than prepending, which is what makes the import path safe — **but the skill's own
  documented CLI usage (`python inspect.py input.laz`) is still broken.**
- **3DEP returns EPSG:4269 with a degree-sized pixel.** WhiteboxTools does not reproject and
  will treat degrees as metres. The warp is not optional.
- **USGS EPT bounds are EPSG:3857.** UTM bounds return zero points with no error.
- **USGS WaterData (`api.water.usgs.gov`) is unreachable** — 60 s timeouts. `spec.md` §5's
  `nhdflowline_network` layer lives there. `hydro.nationalmap.gov` (§6) answers in under
  half a second and is what the driver uses.
- **TNMap's `ENVIRONMENTAL/PUBLIC_LANDS` MapServer answers "Service not started."** TDEC's
  ArcGIS Online Public Access Lands layer is the live equivalent.
- **Soil Data Access:** `STIntersects` against the national `mupolygon` table times out, and
  so does feeding `SDA_Get_Mukey_from_intersection_with_WktWgs84` back as a correlated
  subquery. Read the keys first, interpolate as literals. `mukey` is **not** unique per
  polygon — `mupolygonkey` is.
- **Ibis has no cross-backend joins.** DuckDB is the single connection; `ref.*` and
  `derived.*` are attached with `read_postgres`.

---

## Resuming

```bash
docker compose up -d && uv sync
uv run midden doctor          # postgres, PDAL, WhiteboxTools tool set
uv run midden db check        # inventory + the project-CRS assertion
uv run midden aoi list
uv run midden terrain list
uv run pytest tests/ -q
```

Suggested next action: **#2 above** — cut a hearth-scale AOI at Montgomery Bell and put it
through the detection grid. It is bounded, it is compute rather than design, and it either
validates or falsifies the detection chain in one run.
