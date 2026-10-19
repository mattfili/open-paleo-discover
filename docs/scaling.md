# Scaling midden: statewide, other states, and the single-parcel case

> **Status note, 2026-10-19 (stabilization pass for v0.1.0-research).** The measurements
> below are unchanged; the repo has moved since they were taken (2026-09-03):
>
> - **Ranked polygon output (F1) is built** (2026-09-06): `midden score polygons` writes
>   ranked zones to `derived.candidate_zone`, and `midden score plan` (F2) orders them by
>   survey effort. §"single-parcel is ~90% built" is now closer to 100%; the prototype
>   mentioned there became that command.
> - **The weight set is v4, not the falsified one.** The "do not scale the current weight set"
>   advice cited the set scoring 74.6th / 86.4th percentile at mound-bottom / castalian-springs.
>   `terrace_class` was deleted (C1) and HAND-band plus SSURGO flood frequency entered
>   (v4: 79.3 / 95.5 / 92.9 / 87.9 across four control frames). It is still not validated well
>   enough to scale; the argument stands, the numbers cited do not.
> - **Line counts are stale.** Measured today: ~11,850 lines of Python under `src/`
>   (was 6,420), ~4,770 lines of skill markdown (was 1,698), a 133-line weight set (was 108),
>   `26916` appearing on 51 lines across 25 files (was 26 sites in 13 files), and 4 source YAMLs
>   still national (`nhd_flowline`, `ssurgo`, `sgmc_geology`, `tiger_roads`).
> - The UTM-zone problem (Memphis is zone 15) is unchanged and unaddressed.

Written 2026-09-03. Every number here was measured on this machine against this repo, or
computed from a published dataset; nothing is recalled. Method notes at the bottom.

`spec.md` says what the project should be, `ROADMAP.md` says where it is. This says what
it would take to make it bigger, and which of the three directions is actually hard.

**The one-line answer.** Compute is not the constraint and never was. The constraints are,
in order: (1) the model is currently falsified, so scaling it multiplies a wrong answer;
(2) the project CRS breaks inside Tennessee's own borders; (3) regional archaeological
knowledge does not transfer, and it is 1,698 lines of prose, not code; (4) the detection
half does not scale because the *reviewer* does not scale.

---

## 0. What is regional and what is not

Measured surface area of the problem:

| | Size | Ports as-is? |
|---|---|---|
| Python | 6,420 lines | Yes, except CRS |
| Literal `26916` in code/SQL | 26 sites across 13 files | No — see §1 |
| Seeded AOIs + TN agency service URLs | 13 `SeedSpec`s, 3 URLs | No — replace with PAD-US |
| Intake sources (`sources/*.yml`) | 4, all national datasets | **Yes** |
| Weight set | 108 lines | No — refit and re-falsify per region |
| Regional knowledge in skills | 1,698 lines of markdown | No — this is the real work |

The important finding: **the regional coupling is almost entirely in prose and config, not
in code.** The hydrology, terrace, openness, SLRM, feature-stack, scoring, MCP and render
layers are landscape-agnostic. That was not obviously the design goal, but it is the
outcome, and it is what makes the port tractable.

Every intake source is already a national dataset:

| Source | Coverage | Status |
|---|---|---|
| 3DEP 10 m elevation | CONUS + | `seamless_3dep`, works anywhere |
| 3DEP lidar / EPT | Partial, growing | Coverage index: `WESM.gpkg`, 3.7 GB, updated daily (verified 2026-09-03) |
| NHDPlus HR | National | `hydro.nationalmap.gov`, works anywhere |
| SSURGO | National | Soil Data Access, works anywhere |
| USGS SGMC geology | CONUS | `sources/sgmc_geology.yml` (built 2026-09-08 via the `wfs` driver; this row predates it) |
| Watershed boundaries (WBD) | National, HUC2–HUC16 | Not yet an intake source; needed for tiling (§2) |
| Public land boundaries | National | **PAD-US 4.x** replaces the TDEC + Metro Parks drivers |

---

## 1. The CRS problem, which is worse than it looks

`CLAUDE.md`'s first invariant is "Project CRS is EPSG:26916." Measured:

```
lon  -90.310  UTM zone 15N     <- TN western tip, Mississippi River (Memphis is here)
lon  -86.780  UTM zone 16N     <- Nashville, the current AOIs
lon  -81.646  UTM zone 17N     <- TN eastern tip, Bristol
```

**Tennessee spans three UTM zones.** The invariant does not survive the state it was
written for. Memphis in EPSG:26916 is ~200 km outside the zone's design envelope, where
UTM's scale error grows past what a metre-grid slope calculation should tolerate.

Three options, in preference order:

1. **Statewide TN: `EPSG:32136`** (NAD83 / Tennessee State Plane, metres). One conformal
   metre CRS covering the whole state. Smallest possible change: swap `PROJECT_CRS`,
   migrate the 26 literals, re-type the PostGIS geometry columns, re-run intake.
2. **Multi-state modelling grid: `EPSG:5070`** (NAD83 CONUS Albers, metres). Equal-area,
   national, what NLCD and most CONUS-wide raster products use. Measured scale distortion
   across Tennessee: **−0.85% at 35.0°N, −0.94% at 36.6°N.** A 3.00° slope reads 2.97°; a
   150 m distance-to-stream optimum is off by 1.4 m. Both are far inside the noise of a
   10 m DEM, so Albers is acceptable for the *modelling* grid. It is not acceptable for the
   0.5 m detection grid, where you want a local conformal CRS.
3. **Per-region CRS registry.** `PROJECT_CRS` becomes a property of the region, not the
   project. This is where a multi-state build ends up regardless.

Work involved: the constant is already threaded correctly through most call sites. The
awkward ones are `sql/001_init.sql` and `002_feature_stack.sql`, which type geometry
columns as `geometry(Point, 26916)` — a schema-level constraint, so multi-region means
either a database per region or a `region` column plus generic-SRID storage; `db.py:122`,
which is the CRS uniformity *test* and must become region-aware rather than be deleted; and
`render/qgis.py`, which carries a hardcoded QGIS internal SRSID (`3083`) that does not
generalise. Estimate: 2–3 days including re-derivation, most of it re-running intake.

---

## 2. Statewide Tennessee: compute is a laptop job

Benchmarked on the Cowork Linux VM (4 cores, 3 GB RAM) on this Mac, running the real
WhiteboxTools 2.4.0 chain — breach → pointer → accumulation → slope → streams → HAND — on
tiles of the actual Narrows DEM, so the terrain statistics are realistic:

| Raster | Cells | Wall time | Throughput |
|---|---|---|---|
| 528 × 561 | 0.30 M | 1.0 s | 287 Kcell/s |
| 1056 × 1122 | 1.18 M | 2.3 s | 521 Kcell/s |
| 2112 × 2244 | 4.74 M | 5.9 s | 802 Kcell/s |
| 4224 × 4488 | 18.96 M | 16.5 s | **1,151 Kcell/s** |

Throughput rises with size because per-tool process startup amortises. Peak RSS at 19 Mcells
was **380 MB** (breaching) and **320 MB** (accumulation), i.e. roughly 20 bytes/cell.

Tennessee is 109,247 km² = **1.09 × 10⁹ cells** at 10 m. At the measured 1.15 Mcell/s that
is **~16 minutes of single-box CPU** for the entire state's hydrology chain.

**But hydrology does not tile arbitrarily.** Flow accumulation needs the whole upstream
catchment, so a naive grid tiling truncates the network at every tile edge and produces HAND
that is wrong near the boundary — the same failure the existing 2 km AOI buffer exists to
prevent, at a larger scale. Tile by watershed instead. Verified against the national WBD
service: **60 HUC8 subbasins touch Tennessee**, median 2,748 km², max 7,621 km².

| HUC8 | Area | Cells at 10 m | Est. time | Est. peak RAM |
|---|---|---|---|---|
| Median | 2,748 km² | 27.5 M | ~24 s | ~550 MB |
| Largest | 7,621 km² | 76.2 M | ~66 s | ~1.5 GB |
| All 60 | 109,247 km² | 1.09 G | ~16 min | fits on a laptop |

So: add WBD as an intake source, make the AOI concept accept a HUC, buffer each HUC by
2 km, process, and mosaic. That is the whole statewide story for the modelling grid.

**Storage is where Postgres stops being right.** 4.4 GB per float32 band statewide; the
feature stack at 1.09 × 10⁹ rows × ~12 columns is 50–90 GB as Parquet. `derived.feature_stack`
as PostGIS rows is the wrong home at that size. M3 already reads Parquet through DuckDB, so
the move is to a partitioned Parquet lake keyed on HUC, with Postgres keeping only the
catalog, the derivations and the vector `ref.*` tables. That is a real but bounded change.

---

## 3. The detection grid does not scale, and not for the reason you would guess

Measured, on the real 0.5 m Narrows DEM, the vendored RVT horizon scan at
`search_radius_m=10, num_directions=16`, computing both positive and negative openness:

```
0.49 Mcells in  2.3 s -> 211 Kcell/s
1.96 Mcells in  8.5 s -> 231 Kcell/s
```

That is **~18 seconds of CPU per km²** — embarrassingly cheap, and embarrassingly parallel.
Statewide that is ~546 core-hours, i.e. one day on 24 cores. CPU is not the problem.

Two things are:

**Data volume.** Measured from the Narrows `ground_count` raster: **15.9 ground returns per
m²** (this is dense data, well above the QL2 minimum), 9.6% of cells with zero ground
returns. That is ~16 M ground points per km², so ~1.7 × 10¹² ground returns for Tennessee,
and considerably more counting all classes — tens of terabytes of point cloud to read, even
via windowed EPT/COPC access rather than download. The derived rasters are the same story
from the other end: this repo currently holds **195 MB of COGs for one 2.33 km² buffered
AOI = 84 MB/km²**, which extrapolates to **~9.2 TB** of detection COGs statewide. An
independent route — 4.37 × 10¹¹ cells × 4 bytes × ~5 bands — gives ~8.7 TB. The two agree,
which is the point of computing it twice.

The fork worth naming: for statewide coverage you can skip the point cloud and use USGS's
**derived 1 m DEM rasters**, roughly 1/30th the volume. You lose the `ground_count` band —
the only thing that tells you whether a feature is real ground or interpolation — and you
lose the sub-metre detail. For a first pass over a state, that trade is probably right; for
anything you would act on, it is not.

**The reviewer does not scale.** This is the harder limit. `midden-interpretation` says
"one anomaly is not a finding" and requires each candidate to be run individually against
the false-positive list — tree throw, sinkhole, log landing, conservation terrace,
foundation, flight-line seam, spoil heap. That is a human judgement per candidate. At
statewide scale the top 0.1% of a 437-billion-cell surface is hundreds of millions of cells
and millions of candidate objects. No human reviews that.

Triage requires a classifier; a classifier requires labels; labels require known site
locations; and fitting on known site locations is exactly what `spec.md` §13 defers, for two
stated reasons that both still hold (survey bias, and output sensitivity). **So the honest
statement is that statewide detection is blocked on a deliberate design decision, not on
engineering.** Detection stays AOI-scoped and human-driven. That is a feature.

---

## 4. Other states: the code ports, the knowledge does not

Mechanically, a new state is: pick a CRS (§1), swap the AOI seeding to PAD-US, re-run
intake against the same four national sources. Days, not weeks.

What does not port is the 1,698 lines of regional knowledge, and the failure mode is silent
— the pipeline will happily produce a confident, well-rendered, wrong surface.

The core landform premise — *flat, well-drained, near water, above the flood* — is close to
universal for eastern woodland riverine settlement, and would likely transfer with only a
refit to Kentucky, Alabama, Georgia, the Carolinas, the Ohio valley. It degrades or inverts
elsewhere:

| Region | What breaks |
|---|---|
| Arid Southwest | Water is the dominant and often the *only* constraint; sites cluster on springs, seeps and defensible mesa tops, not terraces. `dist_to_stream`'s "closer than optimal is floodplain" logic is wrong. |
| Great Plains | Little relief for HAND to work with; the diagnostic sites are arroyo-edge kill sites, a landform the stack has no feature for. |
| Northwest Coast | Shoreline and estuary adaptation; the whole terrace-sequence argument is beside the point. |
| Glaciated New England | No incised terrace sequence; kettles and eskers instead. And the false-positive catalogue is dominated by stone walls and cellar holes, which are everywhere and rectilinear. |

A state port therefore needs four things that are not code: at least two published
`control_positive` sites, a weight set refitted and then honestly falsified against them, a
`deep-time-context` equivalent for that region's culture history, and a false-positive
catalogue for that landscape's specific noise. The first and last are the ones that need a
regional archaeologist, and that is a collaboration cost, not an engineering cost.

**Do not scale the current weight set.** It is falsified (74.6th and 86.4th percentile
against a 95th bar) with `terrace_class` diagnosed as the cause. Applying it to 1.09 billion
cells produces 1.09 billion falsified cells rendered beautifully.

---

## 5. "Here is a parcel, find me the top 10 spots"

Mechanically the **easiest** of the three, and mostly built. A parcel is a small AOI:

```
midden_create_aoi(slug, wkt)            # already accepts WKT in the project CRS
midden_run_intake(nhd_flowline | ssurgo)
midden_derive_terrain(grid="model")     # ~14 km2 buffered = 1.4 Mcells = ~2 s of WBT
midden_build_feature_stack
midden_score_overlay
```

A 100-acre parcel with the mandatory 2 km hydrological buffer is ~14 km² of processing —
seconds of CPU, minutes end to end including the 3DEP fetch. Detection at 0.5 m over the
parcel itself is under a minute of openness, *if* lidar exists there; `WESM.gpkg` is the
precheck that answers that, and it should become a `midden doctor`-style command.

**The one missing piece is already named in `ROADMAP.md`:** "Ranked polygon output — scoring
produces a raster; polygonising the top percentile is not implemented." That is literally
the ask. It was prototyped by hand in this session for Hidden Lake — connected components on
the top decile, area-weighted centroid, rank by mean score × √area — in about 60 lines; see
`exports/hidden-lake/`. Productionising it is a `midden features rank` command plus a
`midden_rank_polygons` MCP tool, and it should emit, per polygon: rank, area, mean and max
score, the per-feature contributions that produced the score, the companion `burial_risk`
band, the `canopy_pct` data-quality band, and a centroid in both UTM and lat/lon. A week,
including tests.

### The part that is not an engineering question

On **private** land in Tennessee the legal picture is the inverse of what most people
assume. The Tennessee Antiquities Act's permit requirement governs state land; artifacts on
private land belong to the landowner, and the Division of Archaeology
"cannot force a private landowner" to do anything. Excavating for artifacts on your own
land is lawful.

**Burials are the exception, and they are not a footnote.** Desecration of a place of burial
is a Class A misdemeanor (T.C.A. 39-17-311); disinterring a corpse without legal authority
is a **Class E felony** (T.C.A. 39-17-312). These apply everywhere, private land included.
Relocating graves requires a Chancery Court petition under T.C.A. 46-4-101 et seq. On
discovery, work stops and the medical examiner and law enforcement are notified
(T.C.A. 11-6-107(d)).

Now put that next to what the model actually ranks. In Middle Tennessee the highest-scoring
landform is a flat, well-drained terrace edge above a river — and per
`midden-interpretation`'s own reference, terrace edges and bluff shoulders overlooking the
towns are exactly where Mississippian **stone-box cemeteries** cluster. So a "top 10 spots
on my land" list is positively correlated with grave locations. That is not a hypothetical
risk; it is the central tendency of the output.

Two consequences for the product, both of which are design decisions rather than opinions:

1. **Never fit the model on the state site file.** `spec.md` §13 already says a
   site-fitted probability surface is functionally a treasure map, and TN site-file
   locations are protected from public disclosure. A landform-and-soils model derived only
   from public terrain and soils is what keeps this publishable. A parcel product raises the
   stakes on that decision; it does not change it.
2. **Ship the frame with the ranking.** Ranked polygons should arrive with the burial-risk
   band beside them (never summed in), the canopy/data-quality band, an explicit
   "walk, photograph, record coordinates — do not dig" instruction, the felony statute in
   plain words, and the Division of Archaeology contact. Not as a disclaimer nobody reads:
   as the reason the output is shaped the way it is.

And a product observation worth more than the top-10 list: for most landowners the real
question is not "where do I dig" but "is there anything here I should know about before I
build / clear / sell, and who do I call." A parcel report that answers *that* — what
landforms are present, what periods they could plausibly hold, what the burial and burial-risk
picture looks like, what a Phase I would cost, who to contact — is a better product, is
legal everywhere, and is built from exactly the same pipeline.

---

## Method

- CRS zone spans, Albers distortion: `pyproj`, TN bounding box −90.310/−81.646 lon.
- WBT timings: synthetic tilings (×1, ×2, ×4, ×8) of `data/cogs/harpeth-narrows/dem_10m.tif`,
  full six-tool chain, wall clock, `/usr/bin/time -f %M` for RSS. 4-core Cowork Linux VM on
  the Mac; a native macOS run should be at least as fast.
- Openness timings: `midden.terrain.detection.openness` on windows of the real 0.5 m
  Narrows DEM, both surfaces, radius 10 m, 16 directions.
- Point density and COG volume: `ground_count_0.5m.tif` and `du -sh` on
  `data/cogs/harpeth-narrows`.
- HUC8 counts and areas: live query against `hydro.nationalmap.gov/arcgis/rest/services/wbd`
  layer 4, `states LIKE '%TN%'`.
- WESM and PAD-US availability: HTTP HEAD/GET, 2026-09-03.
- Tennessee law: TDEC Division of Archaeology, "Human Remains and Burials"; T.C.A. 11-6-107,
  39-17-311, 39-17-312, 46-4-101 et seq. Not legal advice.
