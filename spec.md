# midden — Archaeological Site-Predictive Modeling Platform

**Status:** proof of concept, local only
**Repo:** `git@github.com:mattfili/open-paleo-discover.git` — public, standalone
**Audience:** Claude Code, implementing from scratch
**Owner:** Fili

---

## 0. Read this first

This spec is written to be executed, not admired. Where it states a design decision,
that decision has a stated reason — if you disagree during implementation, say so in a
comment and continue; do not silently substitute.

**Amended 2026-09-03 — the scope widened from middens to a target-class registry.** The
project models the archaeological and historical landscape record of Middle Tennessee;
middens are one class within it, and the least detectable one. Sections 1, 2, 6, 7, 9, 11, 12
and 13 below carry the amendment inline, each marked **Amended**. `ROADMAP.md` holds the design for the parts not yet built —
the registry itself, per-class detection parameters, historic-map labels, and the validation
programme that replaces the pass/fail control threshold. Where this spec and `ROADMAP.md`
disagree about *state*, the roadmap wins; where they disagree about *intent*, this file does.

Three things in this spec are **verify-before-use** because they change faster than this
document. Do not trust the code shapes below without checking:

1. **boring-semantic-layer YAML schema.** BSL is at ~0.3.16 and moved from a
   `SemanticModel` API to a `to_semantic_table` builder API during 0.3.x. Check the
   installed version's docs at <https://boringdata.github.io/boring-semantic-layer/> and
   the `examples/` directory in the repo before writing any YAML.
2. **Claude Code `plugin.json` manifest schema.** Verify against current Claude Code
   plugin documentation. The *contents* specified in §9 are correct; the *manifest keys*
   may not be.
3. **CDN availability of MapLibre GL JS** for the artifact renderer (§8). If it is not on
   cdnjs, fall back to Leaflet, which is.

Everything else — PDAL pipelines, PostGIS DDL, WhiteboxTools calls, the HyRiver
packages — you can take as written.

---

## 1. What this is

A pipeline that turns public LiDAR and environmental data into a **ranked set of polygons
worth walking** for archaeological survey in Middle Tennessee, plus an AI layer that can
query, configure, and explore the whole thing.

The target is the **archaeological and historical landscape record**, not one feature type.
What is being looked for is declared per target class in `ref.target_class` — precontact
mounds and earthworks, rockshelters, chert quarries, cave entrances, open habitation,
middens, stone-box cemeteries; historic charcoal hearths, iron works, mill seats, homesteads,
family cemeteries, road traces, saltpeter works, field boundaries. Each class declares its
own grid, detectability, label source, burial sensitivity, and detection parameters, because
none of those are shared across classes.

### The domain problem, stated for an engineer

Two problems, one pipeline.

**Precontact.** People camped on flat, well-drained ground close to water but above the flood
line. That preference is stable enough to be modeled, and the observable proxies are all
derivable from a DEM plus soils. This is a *suitability* problem: the model ranks ground, and
for most precontact classes there is no surface signature to detect.

**Historic.** Industry and settlement left built features with geometry — a hearth is a flat
circle ~10 m across, a mill race is a metre-wide linear cut, a homestead is a cellar
depression beside a chimney fall. This is a *detection* problem: the feature is on the ground
surface and the 0.5 m grid can see it directly. It also has something the precontact half
does not — a public, dated label source in historic topographic quads (§6).

The precontact proxies:

| Concept | What it means | How it is computed |
|---|---|---|
| **Terrace (T0/T1/T2)** | Rivers cut downward over geologic time, abandoning old floodplains as flat benches. T0 floods yearly, T1 rarely, T2+ is older and higher. T1 is where sites are. | Low slope + a discrete mode in Height Above Nearest Drainage |
| **Relict channel** | Abandoned river course, still faintly visible as a sinuous shallow depression | Sinuous linear negative relief in a Simple Local Relief Model |
| **Confluence** | Tributary meets main stem. Two water sources, two habitats, travel node. Strong empirical predictor in the eastern US. | Self-intersection of NHD flowlines |
| **Alluvial burial** | Sites under meters of overbank deposit. LiDAR cannot see them. A negative result here means nothing. | SSURGO parent material + flooding frequency |

**Detectability is a property of the class, not of the project.** LiDAR finds mounds,
earthworks, borrow pits, charcoal hearths and mill races well. It finds middens poorly — most
Archaic shell-bearing sites in the Cumberland and Harpeth drainages are buried with no
surface expression. Both statements are true at once, and the design consequence is a
declared field rather than a project-wide caveat:

- **direct** — a LiDAR signature exists and the 0.5 m chain looks for it.
- **proxy** — no surface expression; only a landform-and-soils suitability surface is
  available, and a negative result is not evidence of absence.
- **invisible** — do not run a detection chain and do not report the absence as a finding.

So the system produces both a *suitability surface* and a *feature detector*, and which one
is meaningful is answered per class by `ref.target_class.detectability`. Never present a
proxy result as a detection. The earlier framing — suitability as the primary output, anomaly
detection as a secondary human-in-the-loop mode — was a description of the midden class
generalised to the whole project by mistake.

### Two grids, two jobs

This is the single most important resolution decision. Do not conflate them.

- **Detection grid — 0.5 m.** Positive/negative openness, SLRM, multidirectional hillshade.
  For a human or a model to
  *look at* and spot anomalies. Statistically meaningless; visually essential.
- **Modeling grid — 10 m.** All predictive features resampled here. Fitting a model at
  0.5 m produces noise and a feature matrix nobody can hold in memory. Middle TN at 10 m
  is ~414 M cells; at 0.5 m it would be ~166 B.

Every raster asset carries its grid in metadata. Feature stacks are 10 m only.

---

## 2. Scope

**In scope (POC):** Middle Tennessee — the 41-county Grand Division, Central Basin and
Highland Rim. Practically: all work is AOI-scoped, and the AOI table starts seeded across
**Davidson County plus the six adjacent counties** — Cheatham, Robertson, Sumner, Wilson,
Rutherford, Williamson.

**Dickson** is included as a seventh. It does not touch Davidson, but the Harpeth corridor
runs Cheatham–Dickson–Williamson and Montgomery Bell State Park sits in it, so excluding it
would cut the drainage you most care about in half.

**Not in scope:** deployment, CI/CD, auth, multi-user, cloud. Local Docker + local
filesystem. Deployment is a later problem.

**Deliberately excluded, so you do not build them:** viewshed and cost-distance analysis
(oversold in predictive archaeology, expensive, weak signal at this scale); PostGIS raster
(see §4); any attempt to auto-classify features from LiDAR with a CNN.

### Target classes

**What** is in scope is as AOI-scoped as **where**. `ref.target_class` is the registry and
the single source of truth: `class_id`, `period`, `morphology` (plan form and size range in
metres), `grid`, `detectability`, `burial_sensitivity`, `label_source`, and `params`.

Three rules follow from it, and they are load-bearing:

1. **No unqualified score.** Every scoring, detection, validation and render operation takes
   a `class_id`. The features that predict a Mississippian mound platform are not the
   features that predict a charcoal hearth, so a score surface with no class attached does
   not mean anything.
2. **Detection parameters live in `params`, never in global config.** A hearth is ~10 m, a
   mound platform 30–100 m, a mill race a metre wide. One openness search radius serves none
   of them. §7's parameter table is amended accordingly.
3. **Burial sensitivity is a registry field.** Overbank burial removes a midden and does
   nothing to a rockshelter. Burial risk remains a companion band and is still never summed
   into the score; what changed is that *which classes it applies to* is declared rather than
   assumed.

The initial registry and the reasoning behind each class are in `ROADMAP.md`. It is not yet
populated — nothing in the CLI takes `--class` today, and that is the first thing to build.

### Seeded AOIs

**Do not hardcode bounding boxes.** Seed `derived.aoi` by querying the authoritative
boundary services and matching on name, so unit boundaries and spellings come from the
agency that owns them rather than from this document:

- State parks and natural areas → TNMap / TDEC state park boundary layer (`arcgis_rest`)
- Metro parks → data.nashville.gov ArcGIS Hub parks layer (`arcgis_rest`)
- Drawdown zones → derived, not fetched (see below)

Seed list. `role` is a column on `derived.aoi` (see §4) and it determines how the output is
read, not how it is computed:

| Slug | Name | County | Role | Notes |
|---|---|---|---|---|
| `radnor-lake` | Radnor Lake State Natural Area | Davidson | prospect | Mature forest, minimal disturbance. Good bare-earth test case. |
| `harpeth-hidden-lake` | Harpeth River SP — Hidden Lake | Davidson / Cheatham | prospect | Former quarry and resort. Expect heavy 20th-c. earthmoving alongside genuine terrace. |
| `harpeth-highway-100` | Harpeth River SP — Highway 100 | Davidson | shakeout | River access unit. Small — use it for fast iteration. |
| `harpeth-newsoms-mill` | Harpeth River SP — Newsom's Mill | Davidson | prospect | Historic mill. Mills mean fords, and fords are long-duration crossings. |
| `beaman-park` | Beaman Park | Davidson | prospect | Metro Parks. See note below on the address. |
| `long-hunter` | Long Hunter State Park | Wilson / Davidson / Rutherford | prospect | Percy Priest shoreline. |
| `priest-drawdown` | Percy Priest drawdown zone | Davidson / Wilson / Rutherford | prospect | Derived, not fetched. See §7. |
| `harpeth-narrows` | Harpeth River SP — Narrows of the Harpeth | Cheatham | control_detection | Montgomery Bell Tunnel, c. 1819. A large cut earthwork that *must* appear in openness. |
| `mound-bottom` | Mound Bottom | Cheatham | control_positive | Mississippian mound complex. |
| `castalian-springs` | Castalian Springs Mound Site | Sumner | control_positive | Mississippian mound complex. |
| `bledsoe-creek` | Bledsoe Creek State Park | Sumner | prospect | Old Hickory shoreline; pairs with Castalian Springs. |
| `cedars-of-lebanon` | Cedars of Lebanon State Park | Wilson | prospect | Cedar glade / karst. Different landform regime — useful contrast. |
| `montgomery-bell` | Montgomery Bell State Park | Dickson | control_detection | 19th-c. iron district. Charcoal hearths and ore pits are the canonical LiDAR-detectable feature class. See below. |

### Controls

There is no ground-truth site dataset in this project. That is not the same as having no way
to check whether the pipeline works. Published sites are the check — and, since the scope
widening, published *maps* are a second and much larger one.

**`control_positive` — tests the predictive model.** Mound Bottom and Castalian Springs are
major Mississippian centers on public land whose locations have been published for over a
century. If your terrace / HAND / confluence stack does not rank their landform in the top
few percent, something in the chain is broken. Under the registry these are labels for
`mound_earthwork` specifically, which is what they are.

**Two controls is not a sample.** Every validation statistic worth computing is inert at
n = 2, and that — not the weight set — is the binding constraint on the project. The fix is
§6's historic topographic quads: a single 15-minute quad marks dozens of mills, fords,
furnaces, cemeteries and homesteads by symbol, all public domain and all dated. Digitized
into `ref.control_sites` with a `class_id` and a positional error, three quads take n from 2
into the dozens. `ROADMAP.md` A1 has the procedure.

**The vanished-feature test is the strongest check available and it is free.** An 1895 quad
shows a mill; the modern quad does not. Run the 0.5 m chain there and ask whether a headrace
cut, a dam abutment or a leveled mill seat is present. The ground truth is public, dated, and
independent of the model; it produces genuine misses as well as hits, which is what makes
recall estimable; and it needs no permission and no fieldwork.

**`control_detection` — tests the visualization chain.** Two of these, at different scales:

- The **Montgomery Bell Tunnel** at the Narrows is a large, unambiguous, precisely-dated cut
  through a ridge. Coarse check: if openness does not show it, something is badly wrong.
- **Montgomery Bell State Park** is the fine check. It sits in a 19th-century iron district,
  and iron production leaves relict **charcoal hearths** — flat circular platforms roughly
  10 m across — along with shallow ore pits. Hearths are the canonical success story of
  LiDAR archaeology; they show beautifully in SLRM and local relief renders in the iron
  districts of Pennsylvania and New Jersey. They are also right at the scale of the features
  you actually care about. If your 0.5 m detection grid resolves hearths at Montgomery Bell,
  it will resolve a low mound. If it does not, no amount of tuning elsewhere will help.

Montgomery Bell is no longer "the fine detection control" in the abstract. It is the first
worked target class — `charcoal_hearth` — with its own morphology, its own label source, and
its own detection parameters. Tune `smoothing_radius_m` and the openness search radius
against the hearths and record the result **against that class**, not as a project default. A
radius swept without a class recorded cannot be reused, because nothing downstream can tell
what it was swept for.

These controls answer different questions and all of them are free. Run them every time you
change a parameter.

Every control here is a published, mapped, historically-marked site, and every historic-map
label is public-domain cartography. Nothing in this project uses non-public site locations,
and §13 covers what would change if that ever stopped being true.

Labels from different sources are never pooled without recording it. NRHP skews monumental,
historic quads skew historic-period and near-settlement, and model-derived weak labels skew
toward whatever the model already believes — so every row in `ref.control_sites` carries
`source`, `source_id` or `source_sheet`, and `class_id`.

Practical note on Mound Bottom: it is a protected site with managed access, generally
guided-tour only. You can model it freely; you cannot casually walk it.

### Two notes on the list

**Beaman Park's mailing address says Ashland City; the park is in Davidson County.** The
nature center carries a 37015 ZIP because it sits in northwest Davidson near the Cheatham
line, and Ashland City is the nearest post office. This matters for exactly one thing: the
boundary comes from **Metro Nashville Parks**, not TDEC and not Cheatham County. Since §2
requires fetching boundaries from the authoritative service rather than hardcoding them,
the fetch settles it — but do not let the ZIP send you to the wrong layer.

Beaman Park is also the most physiographically distinct AOI in the set: dissected Highland
Rim, steep hollows, mature forest, headwater streams rather than a main-stem floodplain.
Every other AOI is Central Basin river valley. Including it is what keeps the model from
learning "Middle Tennessee means big river terrace."

**McCabe Park is dropped.** It is a golf course; every anomaly would be greens construction
and drainage. `harpeth-highway-100` takes over as the small, fast shakeout AOI.

### Size budget — why everything is AOI-scoped

QL2 LiDAR is 2 pts/m². One square mile ≈ 5.2 M points ≈ ~31 MB as LAZ. Middle TN is
~16,000 mi², so a full point-cloud pull is **~500 GB**. Never bulk-download. The AOI table
drives every fetch, and every fetch is cached and idempotent.

---

## 3. Stack

| Layer | Choice | Note |
|---|---|---|
| Language | Python 3.12 | |
| Package manager | `uv` | `uv sync`, `uv run`. No pip, no conda. |
| System of record | Postgres 17 + PostGIS 3.5 | Docker, `compose.yaml` |
| Analytical engine | DuckDB + `spatial` extension | over Parquet, for the wide feature matrix |
| Semantic layer | boring-semantic-layer (Ibis) | federates Postgres + DuckDB |
| Point cloud | PDAL | `brew install pdal` |
| Raster I/O | GDAL, rasterio, rioxarray | |
| Terrain analysis | WhiteboxTools (`whitebox`) + scipy | no rvt-py — see §7 |
| Vector | geopandas, shapely, pyproj | |
| CLI | Typer | |
| Desktop GIS | QGIS | the interactive surface; see §8 |
| MCP | FastMCP | stdio transport |
| Scoring | numpy / rasterio | weighted overlay only; no ML in the POC — see §13 |

### Why both Postgres and DuckDB

Postgres/PostGIS is the system of record: AOIs, vector features, the raster catalog, and the
derivation ledger. It is where correctness and constraints live.

DuckDB over Parquet is the query engine for the feature matrix. A 10 m grid over a few
counties is tens of millions of rows by ~20 columns. Postgres will do it slowly; DuckDB
will do it in a second on your laptop, with zero server tuning.

BSL sits over both via Ibis, so this split is invisible to the semantic layer and to the
MCP tools. That is the whole reason to use BSL rather than hand-rolled SQL.

### Project CRS

**EPSG:26916** (NAD83 / UTM zone 16N, meters). Middle Tennessee is entirely within zone
16. Everything is reprojected to this on intake. Store a WGS84 (EPSG:4326) geometry column
*only* on tables that get exported for rendering.

Write one assertion test for this and never think about it again:

```python
# tests/test_crs.py — the cheapest bug prevention in the project
def test_all_geometry_columns_are_26916(db):
    rows = db.execute("""
        SELECT f_table_schema, f_table_name, f_geometry_column, srid
        FROM geometry_columns
        WHERE f_geometry_column NOT LIKE '%_wgs84'
    """).fetchall()
    assert all(r.srid == 26916 for r in rows), [r for r in rows if r.srid != 26916]
```

You said no CI/CD, and that is fine. Keep exactly three tests: this one, a units check on
DEM output, and a round-trip on the intake YAML loader. CRS and unit bugs are silent and
poison everything downstream; the rest you will catch by looking at maps.

---

## 4. Storage design

### Rasters live on disk as COGs, not in PostGIS

PostGIS raster is slow for this workload, awkward to update, and adds an extension
dependency you will fight during upgrades. Instead:

- Rasters are **Cloud-Optimized GeoTIFFs** in `data/cogs/<aoi_slug>/<kind>_<res>m.tif`
- A `raster_asset` table in Postgres holds the catalog: footprint geometry, path, kind,
  resolution, CRS, and a provenance FK
- "Which rasters cover this AOI" is a PostGIS query; reading pixels is rasterio

This gives you spatial indexing on raster metadata without putting pixels in the database.

### Schemas

Two, created at init:

- **`ref`** — reference data. Boundaries, hydrology, soils, land cover, streets.
- **`derived`** — AOIs, raster catalog, feature stacks, model runs, scores, derivation
  ledger.

That is all this POC needs. Everything it touches is public data, so there is no access
control to build. §13 covers what changes if that assumption ever breaks.

### The repo is public — keep data out of git

Not a confidentiality matter, a hygiene one. Feature stacks are multi-million-row coordinate
tables, COGs are hundreds of megabytes, and QGIS project files embed local absolute paths.
None of it belongs in version control.

```gitignore
data/            # raw fetches, COGs, parquet feature stacks
*.qgs            # project files embed AOI extents and local paths
*.qgz
exports/         # rendered artifact HTML
.env
```

Build the habit now. It is annoying to retrofit after the first 400 MB commit.

### Core DDL

```sql
CREATE SCHEMA ref;
CREATE SCHEMA derived;
CREATE EXTENSION IF NOT EXISTS postgis;

-- Areas of interest. Drives every fetch, derivation, and model run.
CREATE TABLE derived.aoi (
    id           serial PRIMARY KEY,
    slug         text UNIQUE NOT NULL,
    name         text NOT NULL,
    kind         text NOT NULL,          -- state_park | metro_park | county | watershed | custom
    role         text NOT NULL DEFAULT 'prospect',
                 -- prospect         : a real candidate area
                 -- control_positive : known published site; validates the predictive model
                 -- control_detection: known surface feature; validates the render chain
                 -- shakeout         : small AOI used for fast iteration; ignore its scores
    geom         geometry(MultiPolygon, 26916) NOT NULL,
    geom_wgs84   geometry(MultiPolygon, 4326) GENERATED ALWAYS AS
                     (ST_Transform(geom, 4326)) STORED,
    area_km2     double precision GENERATED ALWAYS AS
                     (ST_Area(geom) / 1e6) STORED,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON derived.aoi USING gist (geom);

-- The provenance ledger. Every derived artifact points at one of these rows.
-- Makes any result reproducible and attributable to the inputs and parameters behind it.
CREATE TABLE derived.derivation (
    id           serial PRIMARY KEY,
    aoi_id       int REFERENCES derived.aoi(id),
    operation    text NOT NULL,          -- e.g. 'terrain.openness'
    tool         text NOT NULL,          -- e.g. 'whitebox'
    tool_version text NOT NULL,
    params       jsonb NOT NULL,
    inputs       jsonb NOT NULL,         -- list of input asset ids or source names
    git_sha      text,
    started_at   timestamptz NOT NULL,
    finished_at  timestamptz,
    status       text NOT NULL           -- running | ok | failed
);

CREATE TABLE derived.raster_asset (
    id            serial PRIMARY KEY,
    aoi_id        int NOT NULL REFERENCES derived.aoi(id),
    kind          text NOT NULL,         -- dem | hillshade | slrm | openness_pos | openness_neg
                                         -- | hand | slope | aspect | twi
    grid          text NOT NULL,         -- 'detection' (0.5m) | 'model' (10m)
    resolution_m  double precision NOT NULL,
    path          text NOT NULL,
    footprint     geometry(Polygon, 26916) NOT NULL,
    derivation_id int REFERENCES derived.derivation(id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (aoi_id, kind, resolution_m)
);
CREATE INDEX ON derived.raster_asset USING gist (footprint);

```

---

## 5. Intake module

### Design: two YAMLs per source, not one

You asked for one YAML per dataset carrying semantic definition + transformation + join.
I am splitting it in two, deliberately:

- `sources/<name>.yml` — **our** schema. Fetch, transform, load.
- `semantic/<name>.yml` — **BSL's** schema. Dimensions, measures, joins.

They are linked by table name. The reason: BSL's YAML is its own evolving contract. If you
wrap it inside a custom envelope, every BSL upgrade becomes a migration of your envelope,
and you lose the ability to paste examples straight from their docs. Keep the seam clean.

### `sources/<name>.yml`

```yaml
name: nhd_flowline
description: NHDPlus HR flowlines, Middle TN. Basis for HAND and confluence features.

fetch:
  driver: pynhd                     # see driver registry below
  params:
    layer: nhdflowline_network
    scope: aoi                      # aoi | statewide
  cache: data/raw/nhd_flowline      # idempotent; skipped if fresh

transform:
  - reproject: {to: EPSG:26916}
  - select: [comid, gnis_name, streamorde, lengthkm, geometry]
  - rename: {streamorde: stream_order}
  - filter: "stream_order >= 1"

load:
  target: ref.nhd_flowline
  geometry_column: geom
  mode: replace                     # replace | append | upsert
  upsert_key: [comid]
  index: [gist(geom), btree(stream_order)]

joins:                              # declared here, consumed by the BSL generator
  - to: ref.nhd_waterbody
    type: spatial
    predicate: ST_DWithin
    args: {distance_m: 500}
```

### Driver registry

Drivers are registered by name in `midden/intake/drivers/`. Each implements one method:
`fetch(params, aoi) -> Path`. Adding a source should never require touching the runner.

| Driver | Wraps | Used for |
|---|---|---|
| `arcgis_rest` | `pygeoogc` or requests | TNMap, data.nashville.gov, hydro.nationalmap.gov |
| `pynhd` | HyRiver `pynhd` | NHD / NHDPlus HR flowlines, waterbodies, catchments |
| `seamless_3dep` | HyRiver `seamless-3dep` | 3DEP DEM by geometry (fast path, no point cloud) |
| `s3_ept` | PDAL `readers.ept` | 3DEP point cloud from the public AWS bucket |
| `sda_rest` | requests | SSURGO via Soil Data Access (accepts raw T-SQL) |
| `http_file` | requests | zip/shp/gpkg/gdb/laz downloads |
| `overpass` | requests | OSM streets outside Davidson County |
| `topoview` | requests | USGS historical topographic quads (see §6) |

Note on HyRiver: `py3dep` is now in maintenance mode; the maintainers point to
**`seamless-3dep`** as the successor. Use `seamless-3dep` for raster DEM pulls and
`pynhd` for hydrography.

### The runner

```
uv run midden intake run <source> --aoi <slug>
uv run midden intake run --all --aoi radnor-lake
uv run midden intake status
```

Every run writes a `derivation` row. Fetches are cached by content hash of
`(driver, params, aoi geometry)`; a re-run with unchanged inputs is a no-op that logs and
exits. This matters more than it sounds — you will re-run intake dozens of times while
tuning downstream steps.

---

## 6. Data sources — Middle Tennessee

### Core

| Source | Endpoint | Driver | Notes |
|---|---|---|---|
| LiDAR point cloud | `usgs.entwine.io` → public AWS EPT bucket | `s3_ept` | Find the Middle TN project name at usgs.entwine.io. Bounds are **EPSG:3857**. |
| LiDAR / DEM (fast path) | TNMap, lidar.tn.gov | `http_file` | State portal, tile index available |
| 3DEP DEM (fastest path) | National Map 3DEP service | `seamless_3dep` | Use for AOI reconnaissance before committing to a point-cloud pull |
| NHD / NHDPlus HR | hydro.nationalmap.gov | `pynhd` | Flowlines, waterbodies, catchments |
| SSURGO soils | Soil Data Access | `sda_rest` | Columns that matter: `drainagecl`, `flodfreqdcd`, parent material, depth to bedrock |
| NLCD land cover | MRLC | `arcgis_rest` | Canopy cover — tells you where bare-earth returns are sparse |
| County boundaries | TIGER | `http_file` | |
| State parks / natural areas | TNMap / TDEC | `arcgis_rest` | Seeds the AOI table |
| Streets (Davidson) | data.nashville.gov ArcGIS Hub | `arcgis_rest` | Authoritative centerlines |
| Streets (rest of Middle TN) | Overpass | `overpass` | |

### Historical layers — add these, they are the highest-value thing not yet discussed

Three impoundments — Percy Priest, Old Hickory, Cheatham — flooded large stretches of the
Cumberland floodplain in the mid-20th century. Modern topography does not show what was
there. Historical sources do:

1. **USGS historical topographic quads** (topoView, `ngmdb.usgs.gov`). Free, georeferenced
   GeoTIFF, multiple editions per quad back to the late 1800s. Shows pre-impoundment
   floodplain, fords, ferries, mills, and vanished roads. Mills and fords are river
   crossings, and river crossings are where people concentrated for ten thousand years.

   **Amended: these are the label source, not only an interpretation aid.** Every quad marks
   mills, fords, churches, schools, cemeteries, furnaces, mines and individual homesteads by
   symbol. Digitized into `ref.control_sites` they retire the n = 2 problem in §2, and the
   symbols that have *vanished* from the modern quad are the ground truth for the strongest
   available test of the detection chain. Two consequences for the schema:

   - `ref.histmap_sheet` records year, scale, `source_url`, and a georeferencing transform.
   - Historic quads are not survey-grade, so `positional_confidence_m` travels with every
     point derived from one and is what sets the tolerance radius in validation. A detection
     "hit" inside a tolerance that was never recorded is not a hit. A feature present on an
     1895 sheet and absent in 1935 is dated to that window — record the window.

   Start manual. Three quads digitized by hand is a bounded weekend; CV symbol extraction is
   a later optimisation and is explicitly not a prerequisite.
2. **1930s–50s USDA aerial photography.** Pre-suburban, pre-reservoir, and low enough
   contrast-managed that plowed-out mounds sometimes still show as soil marks. Availability
   varies by county; check USGS EarthExplorer and the UT Libraries collection.
3. **GLO survey plats and field notes** (`glorecords.blm.gov`). Early surveyors recorded
   mounds, "Indian fields," and trails as landmarks.

Ingest at minimum the topo quads — they are a clean `http_file` driver target, they change
the interpretation of every drawdown-zone AOI, and they are now the highest-priority
unbuilt item in the project for the labelling reason above.

---

## 7. Terrain derivation and scoring

### The background frame (B5, added 2026-09-05)

Every enrichment, percentile, or null-distribution number is relative to a **background
frame**, and a number without its frame is not a result. The frame is defined once,
here: **an AOI's regional buffered extent** — the model-grid stack computed with
`clip_to_aoi=false`, i.e. the AOI bounding box plus the model-grid buffer (2,000 m),
minus nodata. "Regional" in any diagnosis means exactly this. Every validation run
records the frame (`frame`, `frame_cells`) in its `derivation.params`, and B1's null
footprints are drawn from it and nowhere else. Cross-AOI comparisons of enrichment
numbers are comparisons of different frames and must say so.

### Derivation chain

```
EPT / LAZ
  → PDAL: ground-class filter, reproject, grid  →  DEM 0.5 m
  → WhiteboxTools: breach depressions → D8 pointer → flow accumulation
                   → extract streams → elevation_above_stream (HAND)
  → WhiteboxTools: slope, aspect, TWI
  → WhiteboxTools: positive + negative openness, multidirectional hillshade
  → scipy: SLRM
  → resample all → 10 m modeling grid
```

Reference PDAL pipeline — the ground-class filter and the metric CRS are the two things
people get wrong:

```python
import pdal, json

p = {"pipeline": [
    {"type": "readers.ept",
     "filename": "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/<PROJECT>/ept.json",
     "bounds": "([xmin,xmax],[ymin,ymax])"},          # EPSG:3857 for this bucket
    {"type": "filters.range", "limits": "Classification[2:2]"},   # ground returns only
    {"type": "filters.reprojection", "out_srs": "EPSG:26916"},
    {"type": "writers.gdal", "resolution": 0.5, "output_type": "idw",
     "filename": "dem_50cm.tif"},
]}
pdal.Pipeline(json.dumps(p)).execute()
```

Terrace extraction, which is the heart of the whole thing:

```python
# Terraces are: low slope + a discrete mode in Height Above Nearest Drainage.
import whitebox
wbt = whitebox.WhiteboxTools()
wbt.breach_depressions_least_cost("dem.tif", "dem_filled.tif", dist=100)
wbt.d8_pointer("dem_filled.tif", "ptr.tif")
wbt.d8_flow_accumulation("ptr.tif", "fac.tif", pntr=True)
wbt.extract_streams("fac.tif", "streams.tif", threshold=5000)
wbt.elevation_above_stream("dem_filled.tif", "streams.tif", "hand.tif")
wbt.slope("dem_filled.tif", "slope.tif")
# Then: histogram hand.tif within the AOI. Modes are terrace surfaces.
# Mask to slope < 3 degrees, polygonize, label T0/T1/T2 by ascending HAND mode.
```

### Detection-grid visualization: openness, not sky-view factor

Do not use single-azimuth hillshade for the detection grid — it hides features whose
orientation is unlucky.

**There is no `rvt-py` in this project.** It caps at Python <3.12 and cannot share an
environment with the rest of the stack. That turns out not to matter, because openness is
the better tool anyway and it is free in WhiteboxTools open core.

That is not a consolation prize. Doneus (2013, *Remote Sensing* 5(12): 6427) proposed
openness specifically as a better technique than SVF for interpretive mapping of
archaeological DTMs: it carries no directional bias, produces no horizontal displacement of
features, and — the part that matters here — **SVF delineates mainly concave features,
while openness delineates both concave and convex.** Mounds, platforms, and charcoal
hearths are convex. Later comparative work (Remote Sensing 10(10): 1598) found essentially
no gap in automatic-extraction success rates between the two.

So compute both signs and know what each is for:

```python
import whitebox
wbt = whitebox.WhiteboxTools()
wbt.openness("dem.tif", "openness_pos.tif", "openness_neg.tif", dist=20)  # dist in cells
wbt.multidirectional_hillshade("dem.tif", "hillshade_multi.tif")
```

- **Positive openness** is high on **convex** features. This is your mound-and-hearth layer
  and the primary render for `montgomery-bell` and `mound-bottom`.
- **Negative openness** is high on **concave** features — ditches, borrow pits, relict
  channels, the tunnel cut at the Narrows.
- On a flat plane both equal 90°, regardless of slope. That is the property that makes
  openness illumination-independent.
- Negative openness is *not* the inverse of positive. Doneus is explicit about this. Render
  both — a mound with a surrounding borrow ditch shows the mound top in positive openness
  and the ditch ring in negative.

Getting this convention backwards inverts every downstream interpretation and fails
silently. `.claude/skills/landform-archaeology/references/visualization-guide.md` opens with
the same table for the same reason.

`dist` is in cells, not metres. At 0.5 m that means `dist=20` is a 10 m search radius —
roughly one charcoal hearth. Make it a swept parameter (§7).

**Verify the licensing yourself before building on it.** WhiteboxTools open core is ~465
tools; the paid Whitebox Toolset Extension is ~63–78 plugins and `SkyViewFactor` is in it.
`Openness` should be open core, but confirm rather than trust either of us — the tool
listing exposes an `is_extension` flag, so check it programmatically at setup and fail loudly
if it is wrong.

**SLRM** is DEM minus a Gaussian-smoothed DEM, three lines of scipy:

```python
from scipy.ndimage import gaussian_filter
slrm = dem - gaussian_filter(dem, sigma=radius_m / res_m)
```

One gotcha: NaN propagates through a Gaussian kernel and will eat your edges and any NoData
hole. Fill or mask NoData before smoothing, then reapply the mask — do not skip this and
then wonder why the AOI has a soft white halo.

**If true SVF ever becomes necessary**, do not pin the project to Python 3.11 for it, and do
not implement it from scratch either.

RVT splits into three modules, and the split matters: `rvt.vis` is pure numpy, array in and
array out (`sky_view_factor_compute`, `horizon_shift_vector`, `slrm`, `multi_hillshade`).
The GDAL binding lives in `rvt.default`, which handles file I/O. The Python version cap
almost certainly comes from that I/O layer, not from the math. Since this project already
reads rasters with rasterio and passes arrays around, you would only ever want `rvt.vis`.

So the escape hatch is cheaper than a second interpreter: feed your own arrays to
`rvt.vis`, or vendor the single function. **Check RVT's license before vendorings** —
attribution is required either way, and the header on the source file is the authority, not
this document.

Two things in `rvt.vis` are worth reading regardless of whether you use the package:
`fill_where_nan` and `roll_fill_nans` solve exactly the NoData-through-a-kernel problem
flagged above, and they have had more real-world DTMs thrown at them than anything you will
write this week.

### The feature stack

10 m grid, one row per cell, written to Parquet and registered in DuckDB.

| Feature | Source |
|---|---|
| `hand_m` | WhiteboxTools |
| `slope_deg`, `aspect_deg`, `twi` | WhiteboxTools |
| `dist_to_stream_m`, `dist_to_confluence_m` | PostGIS, from NHD |
| `stream_order_nearest` | PostGIS |
| `terrace_class` | derived, above |
| `drainage_class`, `flood_freq`, `parent_material` | SSURGO |
| `burial_risk` | derived: alluvial parent material × flood frequency |
| `slrm`, `openness_pos` | scipy / WhiteboxTools, resampled from detection grid |
| `canopy_pct` | NLCD |

Amended. `terrace_class` is **slated for deletion, not repair.** It encodes a human
interpretive category as an ordinal integer carrying a hand-assigned weight, which discards
the continuous information in HAND, inherits mode-counting fragility, and forces a weight
onto a variable whose units are "rank." Feed continuous `hand_m` and `flood_freq` as separate
features and let the response curve be fitted. Keep the terrace concept for the write-up,
where a reader can see the reasoning, and out of the stack, where it is silently
load-bearing. Delete it *after* the ablation in `ROADMAP.md` B2 records the number, so the
removal is evidence rather than argument.

Feature families the widened scope adds, designed in `ROADMAP.md` C2–C6 and not yet built:
karst (`dist_to_sinkhole_m`, `dist_to_spring_m`, `sinkhole_density` — Middle Tennessee is
limestone and the stack does not know it), lithic raw material (`dist_to_chert_outcrop_m`,
a standard strong predictor in eastern woodlands models and absent here), aspect and
insolation, rockshelter potential on the 0.5 m grid, and portage nodes.

Two standing rules for anything added to this table:

- **Before adding a feature, ask what it would take to remove it.** If ablation cannot
  measure its contribution, it is not ready to be scored.
- **A companion band is promoted to a scored feature only by test, never by argument.** The
  bar is two recorded answers: does the feature fire at a control where it should, and do the
  controls move when it is included? `dist_to_road` is permanently unpromotable — it is a
  diagnostic, and §13's sampling-bias problem is why.

Confluences in SQL:

```sql
SELECT ST_Intersection(a.geom, b.geom) AS geom
FROM ref.nhd_flowline a
JOIN ref.nhd_flowline b
  ON ST_Intersects(a.geom, b.geom) AND a.comid < b.comid;
```

`burial_risk` is not decoration. It is what makes a low score interpretable: a cell can
score low because the landform is wrong, or because any site there is under three meters of
overbank silt. Those are different findings and the output must distinguish them.

### Every judgment call is a parameter, not a decision

Any question of the form "should we use X or Y?" that would otherwise be settled once in
this document becomes a **named parameter on a derivation**, with the chosen value recorded
in `derived.derivation.params`. That is what the ledger in §4 is for.

Three consequences, and they are the point:

1. Nothing is settled by argument. You run it both ways and look.
2. Every output is addressable by the parameters that produced it, so two runs are
   comparable rather than merely different.
3. The AI can drive the sweep, because a parameter is a tool argument.

Parameters that matter and their defaults:

| Derivation | Parameter | Default | Why it is contested |
|---|---|---|---|
| `terrain.streams` | `flow_accum_threshold` | 5000 | Sets what counts as a stream, which sets HAND, which sets terraces. The single most consequential knob in the project. |
| `terrain.slrm` | `smoothing_radius_m` | 15 | **Per class.** 10 m finds small features and noise; 25 m finds large features and smooths away small ones. |
| `terrain.openness` | `search_dist_cells` | 20 | **Per class.** 10 m radius at 0.5 m — correct for `charcoal_hearth`, wrong for a 30–100 m mound platform and wrong for a metre-wide mill race. Tune against the Montgomery Bell hearths and record the sweep against `charcoal_hearth`. |
| `terrain.terrace` | `max_slope_deg` | 3.0 | Tighter is cleaner, looser catches gentle fans. |
| `terrain.terrace` | `hand_mode_tolerance_m` | 1.0 | How tightly a cell must sit on a HAND mode to be called terrace. |
| `hydro.drawdown` | `pool_level_m` | winter pool | See below. |
| `score.overlay` | `weights` | `weights/default.yml` | **Per class.** Seeded by guess; tuned against the controls. |

Rows marked **per class** read from `ref.target_class.params`, not from global config. A
sweep that does not record which class it was swept for produces a number nothing downstream
can reuse.

### `hydro.drawdown` — the worked example

The Percy Priest drawdown zone has no boundary layer to fetch. Derive it: take the
reservoir polygon from NHD waterbodies and difference it against a pool-elevation contour
extracted from the DEM. The band between is exposed lakebed — pre-impoundment floodplain,
walkable at low water, described by no modern survey layer. This is where the historical
topo quads (§6) earn their place.

`pool_level_m` is the parameter. Defaults to winter pool, which is defensible because it is
the level the reservoir is actually held at for months every year. A lower contour exposes
more surface but is only walkable in drought years — that is a legitimate thing to model,
not a thing to argue about. Run both; label the outputs by the level that produced them.

**Datum trap, and it will bite you.** Your LiDAR-derived DEM is NAVD88. USACE pool
elevations for Percy Priest may be published in NGVD29 depending on the vintage of the
document. The offset in Middle Tennessee is on the order of tens of centimetres — small
enough to look plausible, large enough to move a shoreline contour tens of metres
horizontally across a flat lakebed. Resolve the datum explicitly in the source YAML, record
it in `params`, and convert rather than assuming. If you cannot confirm the datum of a
published figure, treat that figure as unusable.

### Sweeps

`midden sweep <derivation> --param <name> --values a,b,c --aoi <slug>` runs a derivation
across a parameter range, writes each output as its own `raster_asset` with its own
`derivation` row, and emits a side-by-side comparison. Exposed to the AI as `midden_sweep`
(§9), which means the sweep and the looking can happen in one loop: sweep SLRM radius over
10/15/25 m, call `midden_preview_raster` on each, and let the model say which one resolves
the tunnel at the Narrows most cleanly.

This is the mechanism that turns a control AOI from a one-time check into a tuning signal.

### Scoring: weighted overlay

One mode in the POC. Normalize each feature to 0–1, apply weights from a YAML file in
`weights/`, sum, rank, polygonize the top percentile.

Seed the weights with plausible values and treat the output as a test of the pipeline, not
as a finding. The controls are what tell you whether the weights are defensible: if
`mound-bottom` and `castalian-springs` do not land in the top few percent under a given
weight set, that weight set is wrong. That is a real, self-contained tuning loop and it
needs no external data.

`burial_risk` stays out of the score and rides alongside it as a separate band, because a
cell can rank low for two unrelated reasons — the landform is wrong, or any site there is
under three metres of overbank silt. Collapsing those into one number destroys the only
interesting distinction in the output.

Statistical modelling from known site locations is deliberately out of scope. See §13.

---

## 8. Frontend

### There is no web explorer. QGIS is the driving surface.

An earlier draft of this spec called for a local FastAPI + MapLibre + TiTiler explorer.
It is cut. Reasoning, since the omission is deliberate:

The only thing such an explorer would provide that the semantic layer cannot is **dynamic
raster tiling** — panning and zooming a 0.5 m openness surface over a 40 km² AOI at
full resolution. BSL is a semantic layer over Ibis backends and has no concept of a COG, so
that gap is real. But it is a gap in *browser* clients specifically, and COGs exist
precisely so that a desktop GIS can read them windowed, with overviews, over HTTP or from
disk, with no tile server at all.

QGIS reads COGs natively, connects to PostGIS natively, does dynamic symbology, spatial
selection, and on-the-fly reprojection, and costs zero engineering. For a single-operator
POC it delivers effectively everything the web explorer would.

So there are two rendering targets, and neither is a web app:

**QGIS — for you.** `midden qgis-project --aoi <slug>` emits a `.qgs` project file with
the PostGIS layers and the AOI's COGs pre-loaded and styled. Roughly 100 lines of XML
templating, no PyQGIS dependency, and it saves you re-adding and re-styling layers every
session. This is the highest-leverage small feature in the spec.

**Artifact export — for sharing and for the AI.** A single self-contained HTML file.

Revisit a browser explorer only if you need to hand something interactive to someone who
will not install QGIS.

### Why the artifact must be self-contained

Do not build the artifact to fetch from `http://localhost:8000`. Claude artifacts run in a
sandboxed, cross-origin iframe served over HTTPS; a request to a local HTTP origin is
mixed-content and sandbox-restricted, and even where a browser would permit
`http://localhost` as a trustworthy origin, the iframe's CSP will not. There is no local
server in this design anyway — but if you add one later, this constraint still holds.

The artifact export bundles:

- MapLibre GL JS from CDN (verify cdnjs availability; **Leaflet is the fallback and is
  definitely on cdnjs**)
- Vector layers inlined as GeoJSON
- Raster overlays as base64 PNG, **downsampled to ≤1500 px on the long edge**, with a
  hard size assertion in the exporter

Budget check: a 1500×1500 RGBA PNG of a scored surface is roughly 1–3 MB before base64,
which inflates by ~33%. Assert on the final byte count and fail loudly rather than
producing an artifact that will not load.

### Rendering core

One module, `midden/render/`, two adapters over a shared scene spec — layers, styles,
extent, legend. `artifact.py` emits the self-contained HTML; `qgis.py` emits the `.qgs`
project. `midden_render_map` (§9) uses the artifact adapter.

Keep the scene spec the only thing adapters consume. When a third adapter appears — and one
will — it should require no changes outside `render/`.

---

## 9. AI layer

### Plugin structure

```
plugin/
├── plugin.json            # verify schema against current Claude Code plugin docs
├── skills/
│   ├── midden-terrain/    # how to read openness/SLRM; what a terrace looks like
│   ├── midden-semantic/   # how to write/extend BSL YAML in this project
│   ├── midden-intake/     # how to add a new source YAML + driver
│   └── midden-scoring/    # feature normalization, weight sets, reading against controls
├── templates/
│   ├── source.yml.j2
│   ├── semantic_model.yml.j2
│   └── scene.json.j2
├── examples/              # 3–4 worked end-to-end runs on a small AOI
├── scripts/               # thin CLI wrappers the skills can shell out to
├── references/
│   ├── crs.md             # why 26916, what breaks otherwise
│   ├── glossary.md        # HAND, SLRM, openness, terrace, midden, QL2 — one definition each
└── mcp/
    └── server.py          # FastMCP, stdio
```

`references/glossary.md` is not filler. Terrace, midden, HAND, and grid all mean specific
things here and will otherwise drift between skills.

### MCP tool surface

Consistent `midden_` prefix. Atomic tools that compose, plus a small number of workflow
tools where the composition is fiddly. Pydantic input schemas, `readOnlyHint` annotations
on reads, and error messages that state the next action rather than just the failure.

**Read — semantic layer**

| Tool | Purpose |
|---|---|
| `midden_list_semantic_models` | What models exist |
| `midden_get_model_schema` | Dimensions, measures, joins for one model |
| `midden_query` | BSL query: dimensions, measures, filters, order, limit |
| `midden_sql` | Read-only SQL escape hatch against a read-only role |

**Read — spatial**

| Tool | Purpose |
|---|---|
| `midden_list_aois` | AOIs with area and status |
| `midden_list_sources` | Defined sources and their load state |
| `midden_list_rasters` | Raster catalog, filterable by AOI and kind |
| `midden_sample_raster` | Raster values at supplied points |
| `midden_raster_stats` | Zonal statistics over an AOI or geometry |

**Write — configure and compute**

| Tool | Purpose |
|---|---|
| `midden_create_aoi` | From bbox, county name, park name, or WKT |
| `midden_define_semantic_model` | Write a new BSL YAML. This is the "create new definitions" capability. |
| `midden_run_intake` | Run a source's intake for an AOI |
| `midden_derive_terrain` | Run a named derivative for an AOI |
| `midden_build_feature_stack` | Assemble the 10 m matrix |
| `midden_score_overlay` | Weighted overlay with supplied weights |
| `midden_sweep` | Run a derivation across a parameter range; returns one asset per value |
| `midden_list_parameters` | Named parameters for a derivation, with defaults and current values |

**Visual**

| Tool | Purpose |
|---|---|
| `midden_preview_raster` | Returns a PNG as an image content block |
| `midden_render_map` | Returns the self-contained artifact HTML, and writes it to disk |
| `midden_render_chart` | BSL's chart backend (Altair or ECharts) |

`midden_preview_raster` is the one that makes the AI genuinely useful rather than
decorative. FastMCP can return image content blocks, so the model can *look at* a
positive-openness render of a terrace and say "there is a rectilinear anomaly at the
northeast edge that does not match the surrounding drainage pattern." That is a real
contribution, and it is exactly the kind of pattern-spotting that is tedious for a human
across hundreds of tiles.

**Amended — the agent layer is the interpretive surface, and that raises its correctness
bar.** Its purpose is to let someone without geoarchaeology training read what the pipeline
is saying, which is not overhead; judge it on whether it produces correct and *traceable*
interpretations, not on whether it improves model accuracy. A query tool that is occasionally
wrong wastes a minute. An interpretive tool that is occasionally wrong installs a false
belief that then shapes feature design — the openness sign convention is the worst case,
because a confidently inverted explanation flips every downstream reading silently.

Two rules and four tools follow, designed in `ROADMAP.md` G2–G3 and not yet built.

- **Interpretations cite.** A skill explaining a landform association or an
  industrial-archaeology signature carries references, or says the claim is unsourced.
- **Attribution over assertion.** Explaining a high score returns the per-feature
  decomposition — values, normalised percentiles, contribution. The narrative is the user's
  job; the numbers are the tool's.

| Tool | Purpose |
|---|---|
| `midden_explain_cell` | Per-feature values, percentiles, and score contribution at a point |
| `midden_compare_landform` | Contrast two locations' feature vectors and landform context |
| `midden_describe_aoi` | Physiographic context, drainage, soils, terrain coverage state |
| `midden_class_brief` | A class's morphology, size range, parameters, detectability, confusers, sources |

### Long-running operations

`midden_derive_terrain` on a large AOI takes minutes. For a POC, keep it synchronous but
guard it: a `max_area_km2` parameter that errors with an actionable message
("AOI radnor-lake is 4,200 km²; pass --max-area or split it — suggested split: by HUC-12")
rather than hanging the client. Do not build a job queue yet.

### Evals

Ten questions in `plugin/mcp/evals.xml`. Independent, read-only, verifiable, stable —
questions like "how many square kilometres of the Radnor Lake AOI are classified T1 with
slope under 3 degrees?" where the answer is a number you have checked by hand. The
mcp-builder skill's evaluation guide covers the format.

**Amended — the evals must actually run.** They are written with hand-checked answers and
have never been executed against the server, which under the interpretive framing above is
the only thing standing between the tool and confidently teaching the wrong sign convention.
One command, in CI if the server starts headless, with the openness sign convention, the
two-grids rule, and per-class detectability as explicit cases. The sign convention is a test
case, not a comment.

---

## 10. Layout

```
midden/
├── compose.yaml
├── pyproject.toml
├── spec.md
├── sources/              # intake YAML, one per dataset
├── semantic/             # BSL YAML, one per model
├── weights/              # expert overlay weight sets
├── data/
│   ├── raw/              # cached fetches, gitignored
│   ├── cogs/             # derived rasters, gitignored
│   └── parquet/          # feature stacks, gitignored
├── midden/
│   ├── cli.py            # Typer
│   ├── config.py         # pydantic-settings
│   ├── db.py
│   ├── intake/
│   │   ├── runner.py
│   │   ├── schema.py     # pydantic model of sources/*.yml
│   │   └── drivers/
│   ├── terrain/
│   ├── features/
│   ├── semantic/
│   └── render/
│       ├── core.py       # scene spec
│       ├── artifact.py
│       └── qgis.py       # emits .qgs project files
├── plugin/
└── tests/                # three tests, per §3
```

---

## 11. Milestones

Vertical slice first. Each milestone ends with something observable.

**M0 — foundation.** `compose.yaml` up, PostGIS extensions, three schemas, two roles,
core DDL, Typer CLI skeleton, `uv sync` clean.

**M1 — one source end to end.** NHD flowlines via `pynhd` into `ref.nhd_flowline`, driven
by `sources/nhd_flowline.yml`. Proves the intake contract. Seed the AOI table with Radnor
Lake and the Harpeth River SP units.

**M2 — terrain.** 3DEP DEM via `seamless-3dep` for one small AOI (start here, not with the
point cloud — it is a hundred times faster for shaking out the chain). HAND, slope, openness,
SLRM. Registered as COGs in `raster_asset`. Then swap in the PDAL/EPT path for the same AOI
and confirm the 0.5 m DEM is materially better before committing to it everywhere.

**M3 — semantic layer.** BSL YAML over `ref.*` and `derived.*`. `midden_query` returning
real numbers.

**M4 — MCP + plugin.** FastMCP server, the tool surface in §9, plugin scaffolding,
`midden_preview_raster` returning an image you can actually see in a Claude conversation.

**M5 — features and overlay.** 10 m feature stack to Parquet in DuckDB. Weighted overlay
with seeded weights. Ranked polygon output.

**M6 — render.** QGIS project emitter, then artifact export with a scored surface, terrace
polygons, hydrology, and a street overlay. Paste the artifact into a Claude conversation
and confirm it loads.

M5 is where the controls start earning: tune weights until Mound Bottom and Castalian
Springs rank where they should, then look at what else ranks with them.

**Amended.** All seven milestones are implemented, and M5's weight set was falsified by its
own controls — the loop working as intended. Two things about that sentence changed with the
scope widening. First, "rank where they should" was a mean-percentile threshold with no error
bar; it is replaced by a permutation test that reports an effect size against a matched null
(`ROADMAP.md` B1). Second, every milestone was built against a single implicit target class,
so M5 and M6 are complete but *unqualified* — they emit a score surface and a render with no
`class_id` attached, which §2 now forbids. `ROADMAP.md` holds the work order.

---

## 12. Decisions made on your behalf

Override any of these; they are judgment calls, not requirements.

1. **Two YAMLs per source instead of one.** §5. Keeps BSL's contract clean.
2. **COGs on disk, not PostGIS raster.** §4.
3. **Postgres and DuckDB together.** §3. Postgres for record, DuckDB for the wide matrix.
4. **10 m modeling grid, 0.5 m detection grid.** §1. Non-negotiable in my view; the
   alternative is either noise or blindness.
5. **No access control, no ML.** §4, §7, §13. Everything here is public data and a weighted
   overlay. Both would need building if that changed; neither is worth building now.
6. **No web explorer; QGIS plus a self-contained artifact export.** §8. Cuts a milestone.
7. **Three tests only.** §3. You said no CI/CD; CRS and unit bugs are the exception because
   they are silent.
8. **Published sites as controls.** §2. The only validation signal available without a site
   dataset, and it is a good one — treat a weight set that misses Mound Bottom as falsified.
   **Amended:** not the only one. Public-domain historic cartography is a second label source,
   and a larger one — see §2 and §6.
9. **A target-class registry, not a single target.** §2. Detectability, scale, labels and
   parameters are per class; a global value for any of them silently serves no class well.

## 13. Deferred

Explicitly out of scope. Recorded here so the reasoning is not lost, not as a roadmap — this
is a proof of concept and may well get thrown away.

**Statistical site-prediction.** Fitting a presence-background model (MaxEnt via `elapid`,
or gradient boosting) requires known site locations. Two things would need solving first,
and both are substantial:

- *Sampling bias.* Recorded site inventories are a biased sample — surveys happen where
  roads get built and where fields get plowed. A model trained naively on them learns "sites
  are near highways." Correcting for it requires knowing where people **looked**, not only
  what they found, which means survey-coverage polygons and not just site points. Without
  those, every number the model produces is suspect.

  **Amended — measure it, do not correct it.** Keeping `dist_to_road` out of the feature
  stack does not remove access bias; it removes the ability to see it, because roads follow
  terrace edges, gentle slope and water access, so the bias re-enters through `slope_deg` and
  `dist_to_stream_m`. Every scoring run should therefore compare the distance-to-road
  distribution of top-5% cells against the AOI background and report the ratio. If the top
  5% sits systematically closer to roads than chance, the stack is laundering accessibility
  and the result carries that caveat. Correction still needs the non-public survey-coverage
  polygons and stays deferred; the distinction between *measured* and *corrected* must stay
  explicit so it does not blur in a later write-up.
- *Output sensitivity.* A high-resolution probability surface fitted on real site locations
  is itself a disclosure of those locations — lossy, but functionally a treasure map. This
  is a live argument in archaeological predictive modelling and it is why site inventories
  are restricted in the first place. If real site data ever enters this project, model
  outputs inherit the sensitivity of their inputs, which means a `restricted` schema, a
  read-only role with no grant on it, a lineage-based sensitivity column on
  `derived.raster_asset`, and an export check in `render/core.py`. Roughly a day of work.
  Not worth building against a requirement that does not exist yet.

None of that touches the controls in §2, which are published, mapped, historically-marked
sites, nor the historic-map labels in §6, which are public-domain cartography. The POC's
validation loop is self-contained and stays that way.

One rule guards the boundary as the label set grows. **Weak labels never become ground
truth.** Where the two grids cascade — 10 m suitability triaging candidates, 0.5 m detection
confirming them — stage-2 detections fed back as stage-1 training labels are flagged in
provenance and excluded from every validation set. A model validated against its own output
is validated against nothing.

**Fieldwork loop.** A `field_visit` table recording walked polygons and outcomes. Trivial to
add; pointless until someone walks something.

**Browser explorer.** §8.

**Anything cloud.** §2.
