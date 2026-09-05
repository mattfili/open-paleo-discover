# midden — roadmap

**This file is the canonical record of what is built, what is not, and what is known to be
broken.** Update it in the same commit as the work it describes. `spec.md` says what the
project *should* be; this file says where it actually is.

Last verified: 2026-09-02, against a live database and a full pipeline run.
Scope widened 2026-09-03 — see the next section before reading anything below it.

---

## Scope — target classes, not middens

The project was scoped to middens, and `README.md` opens by conceding that LiDAR finds them
poorly. That concession is accurate and it is a limit of the *target*, not of the method.
Middens are one feature class among many in the Middle Tennessee record, and they happen to
be the least detectable one.

The target is now the archaeological and historical landscape record. Middens stay in as a
class — buried, proxy-only, high burial risk. Several other classes are directly
LiDAR-visible, have public label sources, and are what the detection grid was built for.

### Target class registry — built 2026-09-04

`sql/003_target_class.sql` creates and seeds `ref.target_class` (all 15 classes below, with
per-class detection params as JSONB), plus `ref.control_sites` and `ref.histmap_sheet` for
A1. `src/midden/registry.py` is the accessor; `midden classes` lists the registry.
`resolve_class_params` raises rather than falling back to a global default when a class row
is missing a known detection parameter.

**Scope acceptance met, and D with it (2026-09-04):** `midden score run/controls/weights`,
`midden terrain run --grid detection`, and their MCP mirrors (`midden_score_overlay`,
`midden_derive_terrain`, `midden_sweep`) all require a class; `midden render` and
`midden_render_*` drop class-qualified layers (score included) from any scene without one,
so no unqualified score surface is produced or rendered. Detection parameter *values* come
only from the registry (`terrain/params.py` keeps the schema: names, units, why); sweeps
record their class in the derivation and in every asset variant. Score surfaces are
published as `score_10m_<class>.tif` with the class in `raster_asset.variant`, and score
runs finally open a derivation row (they previously passed `derivation_id=None`).
`weights/default.yml` is now `weights/open_habitation.yml` — weight sets are keyed by
class. Known residue: `terrain preview` / `midden_preview_raster` still pick the first
catalogued asset of a kind regardless of variant; ambiguity predates this change (sweeps
created it) and is now more visible.

Every class declares its own detectability and parameters, because they
are not shared: a 10 m charcoal hearth and a 100 m earthwork cannot be found with the same
openness search radius, and a global value silently serves neither.

| column | meaning |
|---|---|
| `class_id` | `charcoal_hearth`, `rockshelter`, `mound_earthwork`, `open_habitation`, … |
| `period` | precontact / historic / either |
| `morphology` | plan form and expected size range in metres |
| `grid` | detection (0.5 m) or model (10 m) |
| `detectability` | direct, proxy, or invisible |
| `burial_sensitivity` | whether overbank burial removes the signature |
| `label_source` | where controls for this class come from |
| `params` | per-class detection parameters (see **D** under Not built) |

Initial registry, with honest detectability.

**Precontact**

| class | grid | detectability | notes |
|---|---|---|---|
| `mound_earthwork` | model + detection | direct | what `mound-bottom` and `castalian-springs` actually are |
| `rockshelter` | detection | direct | negative openness + bluff mask; see **C3** |
| `chert_quarry` | detection | direct | pit clusters on outcrop; pairs with **C4** |
| `cave_entrance` | detection | direct | karst; see **C2** |
| `open_habitation` | model | proxy | the current predictive target |
| `midden` | model | proxy | buried, no surface expression; keep, do not lead with |
| `stone_box_cemetery` | model | proxy | Middle Cumberland Mississippian; subsurface |

**Historic**

| class | grid | detectability | notes |
|---|---|---|---|
| `charcoal_hearth` | detection | direct | ~10 m circular platforms; Montgomery Bell |
| `iron_works` | detection | direct | furnace, forge, ore pits, race |
| `mill_seat` | detection | direct | race, dam abutment, headrace cut |
| `homestead` | detection | direct | cellar depression, chimney fall, terraced yard, springhouse |
| `family_cemetery` | detection | direct | enclosure wall, regular depressions; high public value |
| `road_trace` | detection | direct | sunken roadbeds, fords |
| `saltpeter_works` | detection | proxy | cave-linked; entrance plus historic record |
| `field_boundary` | detection | direct | stone fences, cleared-line edges |

### What this dissolves

- The README's project-wide caveat becomes a detectability column. Per class, honest, and
  not an apology.
- `montgomery-bell` stops being "the fine detection control" and becomes the first target
  class with its own model and its own parameters. Known broken **#2** is now scoped as
  `charcoal_hearth`.
- NRHP label bias toward monumental sites — previously a scope mismatch — largely resolves.
  `mound_earthwork` is a legitimate class now, so those labels match a class rather than
  mismatching the project.
- Burial risk becomes per class. It removes `midden` and `open_habitation` from
  consideration on a floodplain and does nothing at all to `rockshelter`.

**Acceptance.** `ref.target_class` populated; `midden score run` requires `--class`; no
unqualified score surface is produced or rendered.

**Downstream doc edits — done 2026-09-03.** `README.md` leads with the detectability table
instead of the project-wide midden caveat. `spec.md` carries the amendment inline in §§1, 2,
6, 7, 11, 12 and 13, with a banner in §0. `CLAUDE.md` carries the invariants. The four files
now agree; nothing in the code has changed.

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

Every one of those milestones was built against a single implicit target class. Under the
widened scope they are complete but *unqualified*: M5 and M6 produce a score surface and a
render with no `class_id` attached, which the Scope acceptance criteria now forbid.

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

## Known broken

Numbered in the order they were found, not the order to fix them — **Priority** below is the
work order, and it does not follow this numbering. Items 1–4 predate the scope widening;
5 and 6 came with it, and 5 is the binding constraint on 4.

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

The replacement is **B1** below: a permutation test, which is not a loosening. It reports an
effect size with an error bar instead of a threshold with neither, and it degrades honestly
at low n rather than passing or failing arbitrarily.

### 5. Labels — n=2, and historic cartography is the unlock

Two controls. Every validation method in **#4** and in **B** is statistically inert at n=2.
This is the binding constraint on the whole validation programme, and it is fixable from
public data without permission or fieldwork.

#### A1. Historic topographic quads as a label source — machinery built 2026-09-04

`midden histmap search/fetch/list/tiles/load-sites` (`src/midden/histmap.py`). Not an
intake driver after all: intake is vector-only end to end (GeoPackage cache, `to_postgis`
load), so the raster path mirrors terrain's fetch → warp → COG → catalogue → derivation
instead — the spec's `topoview` (§5) and `http_file` (§6) driver framings are both
retired by this. Sheets come from the TNM Access API (`urls.GeoTIFF` on each product is
the HTMC scan; GeoPDF-only editions are skipped), warp NAD27 → EPSG:26916 as RGB
nearest-neighbour, and land in `ref.histmap_sheet` with NMAS-derived
`positional_confidence_m` (12.2 m at 1:24,000, 31.8 m at 1:62,500, + 15 m georef margin —
all named parameters in the fetch derivation). Four sheets catalogued: White Bluff 1930 1:62,500
(harpeth-narrows), Burns 1936 and 1953 1:24,000 (montgomery-bell), Ridgetop 1931 1:62,500
(beaman-park, Highland Rim). Each verified to contain its AOI.

**Digitized 2026-09-04, machine pass (claude-vision), 37 points in `ref.control_sites`:**
22 from White Bluff 1930 (schools, churches, Travis Ford), 15 from Burns 1953 (nine family
cemeteries, three crossed-pick ore-pit symbols and "Bakersworks" as `iron_works`, two
churches). Label files tracked under `labels/<sheet_id>.geojson`; every point carries
per-point `positional_confidence_m` (sheet NMAS + pointing error, 45–150 m) and
`review_status='unreviewed'` — machine labels are never silently promoted. Eight points sit
*inside* detection AOIs (three ore pits + Jackson Cem in montgomery-bell; Cedar Hill Sch in
harpeth-narrows), which is what A2 runs against. **n=2 is retired: n=37 across four
classes** (23 homestead, 9 family_cemetery, 4 iron_works, 1 road_trace).

Findings from the pass, recorded: (a) no "Mill" label survives on the 1930/1953 editions —
mill culture predates them, so A2's vanished-structure test runs on `homestead` /
`family_cemetery` / `iron_works` instead of `mill_seat`, whose labels need an 1890s-1900s
edition (Greenbrier 1903 1:125,000 exists but its ~78 m NMAS error is marginal); (b) schools
and churches map to class `homestead` deliberately — the detection signature (building
foundation, cellar, terraced yard) is the same, and the name field keeps what it was.

Historic topo quads are listed under Not built as an `http_file` driver target, valued for
showing pre-impoundment floodplain and vanished roads. Under the widened scope they are
something more useful: **the label source that retires the n=2 problem.**

USGS topoView serves scanned quads back to the 1880s, public domain, with corner
coordinates. Every quad marks by symbol: mills, fords, churches, schools, cemeteries,
furnaces, mines, and individual homesteads. A single 15-minute quad over the Highland Rim
carries dozens of them.

1. `http_file` driver fetches quads by cell name and year into `ref.histmap_sheet` with
   year, scale, `source_url`, and a georeferencing transform.
2. Digitize symbols into `ref.control_sites` with `class_id`, `source = 'usgs_histmap'`,
   `source_sheet`, `map_year`, and `positional_confidence_m` — historic quads are not
   survey-grade and the error must travel with the point.
3. **Start manual.** Three quads digitized by hand is a bounded weekend and produces n in
   the dozens. CV symbol extraction is a later optimisation, not a prerequisite.

This is the highest-leverage item in the file. Everything in **B** becomes usable at n ≥ 30.

Secondary sources, same table, once the pattern works: GLO plats (section-line notes record
mills, fields, and improvements), 1930s–50s aerial photography, county atlases.

#### A2. The vanished-feature test

The strongest test available, and the project has nothing like it.

An 1895 quad shows a mill on a creek. The modern quad does not. Run the 0.5 m detection
chain there. Is there a headrace cut, a dam abutment, a leveled mill seat?

- Ground truth that is public, dated, and independent of the model.
- Tests the detection chain end to end, which **#2** identifies as currently unverified.
- Produces negatives as well as positives: a mapped symbol with nothing detectable is a
  genuine miss, and misses are what let you estimate recall.
- No permission and no fieldwork.

Do this immediately after A1, on one quad. It either validates the detection chain or
falsifies it, in one pass, against real features of known location and known type.

**Acceptance.** `midden validate histmap --sheet <sheet> --class mill_seat` reports, per
mapped symbol, whether detection fired within a tolerance radius. Report recall and the
false-negative list, not just hits.

**Executed 2026-09-04 — machinery works, and the first firing rule is falsified.**

`midden validate histmap` is built and ran against Burns 1953 for `iron_works` (4
symbols) and `family_cemetery` (9, one in an EPT coverage gap). It cuts
`control_detection` AOIs around symbol clusters, derives the 0.5 m chain per class from
the registry parameters, and applies the rule: a connected cluster of ≥ `min_cells`
cells beyond `threshold_pctile` of a 500 m background annulus, inside the symbol's
positional-tolerance disc, in the tail the class morphology predicts.

First pass, seeded rule (p95): **12/12 evaluable symbols HIT** — ore pits fired on both
openness signs (pit + spoil, exactly the catalog's pairing), cemeteries on negative
openness. Then the negative control: **94% of random background points fire the same
rule.** The 100% recall was an artifact of permissiveness — a 45 m disc holds ~25k
cells, ~5% exceed a p95 threshold by chance, and spatial autocorrelation clumps them
past any small `min_cells`.

The sweep (derivations 18/30 + ad-hoc, all on Burns 1953 clusters):

| rule | cemetery recall | cemetery bg fire | iron recall | iron bg fire |
|---|---|---|---|---|
| p95, seeded n | 8/8 | 94% | 4/4 | high |
| p99.0, n100 | 3/8 | 24% | 1/4 | 13% |
| p99.5, n200 | 0/8 | 14% | 0/4 | 0% |
| p99.9, n100 | 1/8 | 3% | 0/4 | 0% |

**No configuration is both sensitive and quiet.** The percentile-cluster rule cannot
separate a grave-scale or pit-scale anomaly from Highland Rim background texture at a
45 m tolerance disc. That falsifies the rule design, not the chain: the anomalies are
present at the symbols (p99–100 extremes), they are just not rarer than background
texture at that scale. Recorded consequences:

1. The registry's `detect` blocks are placeholders for a rule that needs to be
   shape-aware (rectangularity for cellar holes, ring/row regularity for cemeteries,
   pit-plus-spoil pairing for ore pits), not merely amplitude-based.
2. Shrinking the tolerance disc is the other lever: at 45 m the disc is mostly
   background. Reviewing machine-digitized label positions against the renders (the
   `review_status` loop) buys sensitivity without loosening anything.
3. The negative control must ship inside `midden validate` rather than as an ad-hoc
   script — a recall number without a background fire rate is exactly the
   pass-with-no-error-bar failure B1 exists to prevent (see `spatial-validation`).
4. `USGS_LPC_TN_Middle_B1/B2` seam: Burns 1953 straddles it; validate reports a
   coverage-gap symbol as "no data", never as a miss.

#### A3. NRHP for the monumental precontact classes

`ref.control_sites` seeded from NRHP archaeological listings intersecting the Central Basin
and Highland Rim; address-restricted rows excluded rather than approximated. Under the
registry these are labels for `mound_earthwork` specifically, which is what they are.

#### A4. Confuser registry

The classes above have look-alikes, and a detection chain that cannot separate them will
spend field days on 20th-century earthmoving. Log them deliberately.

`ref.confuser` — logging deck landings, skid trails, CCC-era terraces and picnic platforms,
bulldozer push piles, wildlife food plots, borrow pits, well pads, modern pond dams.

Every one is a flat or circular anthropogenic platform in the size range of a charcoal
hearth or a small mound. Catalogue them while working Montgomery Bell and Harpeth Narrows
anyway — marginal cost is zero and they are the hard negatives that set precision.

### 6. Validation is per class, and currently has no error bars

Every test below runs per `class_id`, and **A1** is what makes any of them meaningful.

#### B1. Permutation test replaces the pass/fail threshold

The current test asks "is the mean percentile above 95." That is a threshold with no error
bar, on footprints that **#4** already shows cannot average that high.

Compute observed enrichment; build a null by drawing k random footprints of matched area and
landform class from the same AOI; report observed, null distribution, and empirical p.
Degrades gracefully — a weak honest answer at low n, a strong one at high n.

**Acceptance.** `midden score validate --aoi <aoi> --class <class>` emits enrichment, null
summary, and p. `control_check.py` wraps this or is deleted.

#### B2. Feature ablation

Hold each feature out in turn, refit, report delta-enrichment. A feature whose removal does
not move enrichment is not carrying signal regardless of its weight. This is the
quantitative version of the `terrace_class` finding in **#1**, reached without manual
comparison of normalised means.

**Acceptance.** `midden score ablate --aoi <aoi> --class <class>` → feature → delta.

#### B3. Cross-physiography holdout

Fit on Central Basin, evaluate on Highland Rim, report separately. The only test that
catches the failure `spec.md` §2 names — the model learning "Middle Tennessee means big
river terrace." Blocked by **#3** (`beaman-park` has no terrain), which makes that item a
dependency of the validation strategy, not a coverage gap.

#### B4. Access-bias audit

Keep `dist_to_road` out of the feature stack. Excluding the variable does not remove access
bias, it removes the ability to see it — roads follow terrace edges, gentle slope, and water
access, so the bias re-enters through `slope_deg` and `dist_to_stream_m`.

Measure it: compare the distance-to-road distribution of top-5% cells against the AOI
background, and report the ratio on every scoring run. If the top 5% sits systematically
closer to roads than chance, the stack is laundering accessibility and the result carries
that caveat.

This is measurement, not correction. Correction needs survey-coverage polygons that are not
public. Keep the distinction explicit so it does not blur in a later write-up.

#### B5. Define the background frame

"Regional" and "surrounding buffered extent" appear in the **#1** diagnosis with no written
definition, and they determine every enrichment number here. Define once in `spec.md`,
record the frame used per run in the provenance ledger, and have B1's null draw from it.

---

## Not built

| Item | Where specified | Note |
|---|---|---|
| ~~`ref.target_class` registry~~ | Scope, above | **Built 2026-09-04** (`sql/003_target_class.sql`, `registry.py`). `--class` threading in flight. |
| `priest-drawdown` AOI | §7, the worked example | Derived, not fetched: NHD waterbody minus a pool-elevation contour. **Carries the NAVD88/NGVD29 datum trap** — an unconfirmed datum makes the figure unusable. |
| Historical topo quads | §6 | `http_file` driver target. **Promoted: this is the label source — see A1.** Also changes the interpretation of every drawdown AOI: pre-impoundment floodplain, fords, mills, vanished roads. |
| 1930s–50s aerial photography, GLO plats | §6 | Availability varies by county. Secondary label sources behind A1. |
| NLCD canopy (`canopy_pct`) | §7 | Companion band: a predictor of data quality, not of settlement. Distinguishes a weak result in forest from a weak result in an open field. |
| `midden_render_chart` | §9 | Needs a chart backend dependency (Altair or similar). |
| Evals actually executed | §9 | `plugin/mcp/evals.xml` is written with hand-checked answers but has never been run against the server. See **G1**. |
| Ranked polygon output | §11 M5 | Scoring produces a raster; polygonising the top percentile is not implemented. See **F1** — this gap is the product. |

The lettered sections below are the design for the items above and for the feature families
the widened scope opens up.

### C. Features

#### C1. Delete `terrace_class` rather than repair it

The fix proposed under Known broken **#1** — anchor HAND modes to SSURGO `flood_freq` — is
better than reweighting and should still not be built. `terrace_class` is a human
interpretive category encoded as an ordinal integer carrying a hand-assigned weight of 3.0.
That discards the continuous information in HAND, inherits mode-counting fragility
(`castalian-springs` has two modes, so ordinal position means something different there than
at `mound-bottom`), and forces a weight onto a variable whose units are "rank."

Feed continuous HAND and `flood_freq` as separate features and let the response curve be
fitted. Keep the terrace concept for the write-up, where a reader can see the reasoning, and
out of the feature stack, where it is silently load-bearing.

Sequence it after **B2**, so the deletion is recorded with the ablation number that justifies
it rather than with an argument.

#### C2. Karst family

Middle Tennessee is limestone and the feature stack does not know it.

- **Sinkholes.** Closed depressions from the 10 m DEM via `sink`, `depth_in_sink`, and
  `stochastic_depression_analysis`. Prefer the stochastic version — it returns a probability
  surface, which is more honest than a binary mask on a noisy DEM.
- **Springs.** NHD point features, already fetched alongside flowlines.
- **Cave entrances.** Sinkhole margins and bluff-base concavities on the 0.5 m grid. Feeds
  `cave_entrance` and `saltpeter_works` directly.

New features: `dist_to_sinkhole_m`, `dist_to_spring_m`, `sinkhole_density`.

#### C3. Rockshelter potential — 0.5 m grid

Bluff-line overhangs from negative openness plus slope plus a bluff mask.

This matters disproportionately: a class the detection grid can find *directly* rather than
by proxy, and a reason for the 0.5 m chain to exist on the Highland Rim margin, where
terrace-based prediction is weakest.

#### C4. Lithic raw material

Distance to chert source is a standard strong predictor in eastern woodlands settlement
models and is absent. Tennessee Geological Survey publishes statewide surficial geology;
Fort Payne and St. Louis formation outcrops are the relevant units. A join against a public
layer, not new computation.

New feature: `dist_to_chert_outcrop_m`. Also defines where `chert_quarry` can plausibly
occur, which is a hard constraint worth encoding rather than learning.

#### C5. Aspect and insolation

South-facing terraces and bluff bases. `aspect` is in the WhiteboxTools open core;
`time_in_daylight` is better-conditioned if the compute is acceptable.

#### C6. Portage nodes

Same shape as the existing confluence feature — a point layer of travel nodes plus a
distance band — so it rides existing machinery rather than adding any.

Derive from `ref.nhd_flowline` on `stream_order >= 4` (a canoe river, not a creek). Walk the
channel; wherever two points are within `neck_max_m` straight-line but ≥ `loop_min_m` along
the channel, emit a node at the neck midpoint weighted by the ratio of those two distances.

Defaults: `neck_max_m = 300`, `loop_min_m = 2000`.

The distance band then attaches to the landings at the bluff base, which is where the record
would be, rather than to the ridge over the neck.

Two conditions.

1. **Companion band, not scored**, until tested the honest way: does `mound-bottom`'s own
   horseshoe register as a node, and do the controls move when the band is included?
   Promotion to a scored feature requires both answers, recorded.
2. **The ethnographic footing is thinner than for confluences.** Dugout travel in the
   interior Southeast is well attested. A source specifically documenting neck portages on
   rivers of this size has not been found. That gap goes in the sources file rather than
   being papered over, and it stays recorded until it is closed.

### D. Per-class detection parameters — done 2026-09-04

Built with the registry: values live in `ref.target_class.params`, detection runs take
`--class`, `terrain/params.py` keeps only the parameter schema, and sweeps record their
class. See the Scope section above for the full acceptance record. The original argument,
kept for the reader:

`terrain.openness.search_radius_m` was a single global value. It cannot be.

A charcoal hearth is a ~10 m circular platform. A mound platform is 30–100 m. A mill race is
a metre-wide linear cut. One radius serves none of them well — and the parameter that Known
broken **#2** says Montgomery Bell exists to set is a parameter for the hearth class, not for
the project.

Move openness search radius, SLRM radius, and any minimum-area threshold into
`ref.target_class.params`. Detection runs take `--class` and read parameters from the
registry.

**Acceptance.** No detection parameter read from global config. A parameter sweep records
which class it was swept for.

### E. Cascade the two grids

The 10 m modelling grid and the 0.5 m detection grid never inform each other. Known broken
**#2** notes Montgomery Bell is 10.9 km² (~44 M cells at 0.5 m). That number is the argument:
exhaustive detection does not scale past a handful of parks, and there is no triage step.

1. **Stage 1, recall.** 10 m suitability for the class selects candidates. Tuned for recall —
   a false positive here costs compute, not a field day.
2. **Stage 2, precision.** 0.5 m detection runs only inside stage-1 candidates, with that
   class's parameters from **D**.
3. **Feedback.** Stage-2 detections become weak labels for stage 1, flagged by provenance so
   they are never confused with `ref.control_sites` ground truth.

Some classes skip stage 1 — `rockshelter` is constrained to bluff lines, a cheaper mask than
a suitability surface. Record which classes cascade and which gate on a hard constraint.

### F. Product — ranked polygons, then the survey plan

`README.md` promises "a ranked set of polygons worth walking." Ranked polygon output is in
the table above as not built. That gap is the product.

1. **Polygonise.** Top percentile → polygons with area, mean and max score, dominant landform
   class, `class_id`, and the burial-risk companion band as a separate attribute (never
   summed, per the existing invariant).
2. **Survey plan.** Given N person-days: which polygons, in what order. An optimisation over
   the score surface — expected discoveries per unit effort subject to access, walk time, and
   parcel boundaries. `travelling_salesman_problem` is in the WhiteboxTools open core and
   covers routing.

Item 2 is the differentiator. Suitability surfaces are common; a defensible survey design
derived from one is not.

### G. MCP and plugin layer — amendment to M4

**Scope note.** The agent layer is the interpretive surface for doing geoarchaeology without
geoarchaeology training. That is its purpose and it is not overhead. Judge it on whether it
produces correct and traceable interpretations, not on whether it improves model accuracy.

That raises the correctness bar rather than lowering it. A query tool that is occasionally
wrong wastes a minute. An interpretive tool that is occasionally wrong installs a false
belief that then shapes feature design. The openness sign convention is the worst case: a
confidently inverted explanation flips every downstream reading silently, which is exactly
why the invariant exists.

#### G1. Run the evals

`plugin/mcp/evals.xml` has hand-checked answers and has never been executed against the
server. Under the interpretive framing this is the only thing standing between the tool and
confidently teaching the wrong sign convention.

**Acceptance.** One-command eval run, in CI if the server starts headless, with the openness
sign convention, the two-grids rule, and per-class detectability as explicit cases.

#### G2. Ground the skills in citable sources

Skills encode technique. For interpretation they must also encode *why*, with references —
landform association, terrace formation, burial and site visibility, industrial archaeology
signatures. An interpretation should be traceable to a source rather than to model priors, so
it can be checked and so it can go into a methods appendix later.

**C6**'s recorded portage gap is the template: where a source is missing, the skill says so.

#### G3. Tools the interpretive use case needs

- **`midden_explain_cell`** — AOI plus coordinates returns per-feature values, their
  normalised percentiles, and each feature's contribution to the score. Feature attribution
  at a point. The core learning loop: the model ranks something, you ask why, you get a
  decomposition rather than an assertion.
- **`midden_compare_landform`** — contrast two locations' feature vectors and landform
  context. "How is this unlike Mound Bottom" builds intuition fastest.
- **`midden_describe_aoi`** — physiographic context, drainage, dominant soils, terrain
  coverage state. Orientation before interpretation.
- **`midden_class_brief`** — for a `class_id`, return morphology, expected size, detection
  parameters, detectability, confusers, and sources. The registry is only useful as a
  learning tool if it is legible from inside the conversation.

#### G4. Closing the loop

Longer horizon, recorded now: an agent that reads `ROADMAP.md`, proposes the next falsifiable
experiment, runs it, and writes the outcome back into the ledger — including when it fails.
Provenance ledger, CLI, and write tools already exist. Distinct from querying, and genuinely
novel for geospatial work.

---

## Priority

1. ~~**Scope**~~ — done 2026-09-04. `ref.target_class` built; everything takes `--class`.
2. ~~**A1**~~ — done 2026-09-04, machine pass: 4 sheets, 37 points, n=2 retired.
   Open residue: review the unreviewed labels in QGIS.
3. ~~**A2**~~ — executed 2026-09-04: machinery shipped, first firing rule falsified by
   its own negative control (see A2 above). Next: shape-aware rules + in-command
   negative control. The original framing, kept: validates or falsifies the chain against
   public ground truth, no permission and no fieldwork.
4. ~~**D**~~ — done 2026-09-04, with item 1.
5. **Known broken #2** — hearth-scale AOI at Montgomery Bell, now as `charcoal_hearth` with
   its own radius rather than a global one.
6. **B1 + B2** — permutation and ablation. Retires the pass/fail threshold, answers the
   `terrace_class` question with evidence.
7. **C1** — delete `terrace_class`, after B2 records why.
8. **G1** — run the evals.
9. **C2–C5** — feature families. Cheapest accuracy available.
10. **A4** — confuser registry, opportunistically while working existing AOIs.
11. **B3 + Known broken #3** — `beaman-park` terrain, then holdout.
12. **C6** — portage, as a companion band with its test.
13. **F1** polygonise, **E** cascade, then **F2**, **G3**, **G4**.

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

Added with the scope widening:

- **Correcting survey bias.** Needs survey-coverage polygons that are not public. **B4**
  measures it instead. The distinction between *measured* and *corrected* stays explicit.
- **Fitting on non-public site data.** Out of scope for this repo by design. Nothing in the
  scope widening depends on it.
- **CV symbol extraction from scanned quads.** Not until manual digitisation of three sheets
  has proven the label pipeline worth automating.

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
- **`USGS_LPC_TN_Middle_B1_2018_LAS_2019` does not cover Montgomery Bell.** The recorded
  claim that it "covers all four control AOIs" was never tested for the park (Known broken
  #2 — no detection run ever happened there) and is false: the ept.json cube bounds
  contain the park but the actual flight coverage is `..._B2_...`. PDAL reports it as
  "Unable to write GDAL data with no points". Per-AOI coverage lives in
  hobu/usgs-lidar `boundaries/resources.geojson`; check it, not the cube bounds.
  Discovered 2026-09-04 by the first Montgomery Bell detection run.
- **HTMC contains partial "advance sheets" that georeference correctly and are mostly
  blank paper.** Burns 1936 covers only the western third of its cell; Montgomery Bell
  falls in the blank part, discovered only by checking per-tile ink fraction. Check
  coverage (the `_tn.jpg` preview, or ink density) before digitizing from a fetched sheet.
- **`postgis/postgis:17-3.5` publishes no arm64 manifest.** On Apple Silicon the compose
  build fails with "no match for platform in manifest" until `platform: linux/amd64` is
  pinned on the service; OrbStack then runs it under Rosetta, which is fine for a local
  POC. Pinned in `compose.yaml` 2026-09-04.

---

## Resuming

### Where this was left — 2026-09-04, Priority items 1–4 executed

Branch `feat/target-class` (off `docs/target-class-scope`). Items 1 (registry), 4 (D,
per-class parameters), 2 (A1 labels), and 3 (A2 machinery + first runs) are done; every
acceptance and every negative result is recorded in its own section above. Headlines:

- `ref.target_class` seeded (15 classes); everything takes `--class`; no unqualified
  score surface is produced or rendered; detection values come only from the registry.
- 37 histmap control points across four classes (n=2 retired), machine-digitized,
  `unreviewed`, tracked under `labels/`.
- The vanished-feature test ran twice on Burns 1953: 12/12 hits at the seeded rule,
  then the negative control showed a 94% background fire rate — the rule, not the
  chain, is falsified, with the sweep recorded under A2.
- Environment rebuilt from scratch on this machine (the 2026-09-02 database volume did
  not survive): compose platform pin, PDAL 2.10.2, fresh AOI seed + intake. The
  pipeline reproduced the recorded HAND modes (0.38/3.38/10.62) and the weight-set
  falsification (76.8th pctile vs 74.6 recorded — SSURGO/NHD drift, same verdict).

Nothing is half-built. In-flight residue, deliberately left: the score `variant`
convention means old unqualified assets are simply invisible to scenes (none exist in
the fresh DB); `terrain preview` still picks the first variant of a kind.

Suggested next action, in order:

1. **Make the negative control part of `midden validate histmap`** (a `--null n`
   option reporting background fire rate beside recall) — a recall without it is the
   pass-with-no-error-bar failure. See `spatial-validation`.
2. **Review the 37 unreviewed labels in QGIS** (`render-qa` / `histmap-digitize`
   loop): confirmed positions shrink tolerance discs, which is the cheapest
   sensitivity gain available.
3. **Shape-aware firing rules** for cemetery/homestead/ore-pit (rectangularity,
   row-regularity, pit-plus-spoil pairing) — amplitude alone is falsified.
4. Then item 5 (hearth-scale Montgomery Bell as `charcoal_hearth` — note the park is
   in EPT project `..._B2_...`, not B1) and item 6 (B1+B2).
