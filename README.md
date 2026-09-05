# midden

LiDAR-derived modelling of the archaeological and historical landscape record of Middle
Tennessee, for survey planning. Proof of concept, local only.

A pipeline that turns public LiDAR and environmental data into a ranked set of polygons
worth walking, plus an MCP layer so an AI can query, configure, and *look at* the result.

**Detectability is declared per target class, not claimed for the project.** LiDAR finds
mounds, earthworks, charcoal hearths and mill races well. It finds middens poorly — most
Archaic shell-bearing sites in the Cumberland and Harpeth drainages are buried with no
surface expression. Both are true, so each target class in `ref.target_class` declares which
it is:

| detectability | what it means |
|---|---|
| **direct** | a LiDAR signature exists; the 0.5 m detection chain looks for it |
| **proxy** | no surface expression; only a landform-and-soils suitability surface, and a negative result is not evidence of absence |
| **invisible** | do not run a detection chain, and do not report the absence as a finding |

Middens are one class among many — buried, proxy-only, and the least detectable thing here.
Mounds and earthworks, rockshelters, chert quarries and cave entrances are precontact classes
the detection grid can find directly. Charcoal hearths, iron works, mill seats, homesteads,
family cemeteries and road traces are historic classes that are directly visible *and* have a
public, dated label source in historic USGS topographic quads.

The project name predates the scope. It stayed because renaming a repo is not free.

## Where to look

| File | What it is |
|---|---|
| **[`ROADMAP.md`](ROADMAP.md)** | **Canonical project state** — what is built, what is not, what is known broken. Start here. |
| [`spec.md`](spec.md) | Architecture and design decisions. What the project *should* be. |
| [`CLAUDE.md`](CLAUDE.md) | How to work in this repo: invariants, tools, conventions. |
| `.claude/skills/` | Technique skills: WhiteboxTools, PDAL, landform archaeology, and interpretation. |
| `plugin/` | Claude Code plugin: MCP server config, four skills, glossary, evals. |

## Quick start

```bash
cp .env.example .env          # set POSTGRES_PASSWORD and MIDDEN_RO_PASSWORD
docker compose up -d          # Postgres 17 + PostGIS 3.5 + hypopg
uv sync
uv run midden db init         # schemas, roles, read-only role password
uv run midden doctor          # postgres, PDAL, WhiteboxTools tool set
uv run midden aoi seed        # 13 AOIs from the authoritative boundary services
```

`uv run midden doctor` downloads the WhiteboxTools binary (~100 MB) on first run.

## A worked pass

```bash
uv run midden intake run nhd_flowline --aoi mound-bottom
uv run midden intake run ssurgo       --aoi mound-bottom
uv run midden terrain run --aoi mound-bottom --grid model
uv run midden features build --aoi mound-bottom
uv run midden score run   --aoi mound-bottom
uv run midden render map  --aoi mound-bottom      # self-contained HTML
uv run midden render qgis --aoi mound-bottom      # QGIS project
```

The 0.5 m detection grid needs the LiDAR point cloud and an EPT project name:

```bash
uv run midden terrain run --aoi harpeth-narrows --grid detection \
  --ept-project USGS_LPC_TN_Middle_B1_2018_LAS_2019
```

## Invariants

Violating any of these produces output that looks fine and is wrong.

- **EPSG:26916** (NAD83 / UTM 16N, metres) everywhere. WhiteboxTools does not reproject and
  will process degrees as if they were metres.
- **Two grids, two jobs.** Detection renders at 0.5 m; predictive modelling at 10 m. A model
  fitted at 0.5 m is noise; feature detection at 10 m is blind.
- **No unqualified score.** Every scoring, detection, validation and render operation takes a
  `class_id`. The features that predict a Mississippian mound platform are not the features
  that predict a charcoal hearth, so a score surface with no class attached is meaningless.
- **Detection parameters are per class, never global.** Openness search radius, SLRM radius
  and minimum-area thresholds come from `ref.target_class.params`. A hearth is ~10 m, a mound
  platform 30–100 m, a mill race a metre wide; one global radius serves none of them.
- **Detectability is declared, not assumed.** Never present a proxy result as a detection.
- **Historic-map evidence carries a date and a positional error.** Historic quads are not
  survey-grade, so `positional_confidence_m` travels with every point derived from one and
  sets the tolerance radius in validation.
- **Openness sign convention.** Positive openness is high on *convex* ground (mounds,
  charcoal hearths, ridges); negative is high on *concave* (pits, ditches, relict channels).
  A flat plane is 90° in both, whatever its slope. Getting this backwards silently inverts
  every interpretation downstream.
- **Burial risk is a companion band, never summed into the score — and it is per class.** A
  cell scores low either because the landform is wrong or because anything there is under
  metres of overbank silt. Those are different findings. Overbank burial removes a midden and
  does nothing to a rockshelter.
- **`dist_to_road` is never a feature.** It predicts where archaeologists have looked, not
  where people lived. Keeping it out does not remove access bias, though — it only removes
  the ability to see it, so it is reported as a diagnostic on every scoring run.

## Status

All seven milestones in `spec.md` §11 are implemented and the pipeline runs end to end.
The predictive output is **not yet trustworthy**, for two reasons.

The seed weight set is falsified by its own controls, and the cause is diagnosed in
[`ROADMAP.md`](ROADMAP.md). That is the loop working — a weighted overlay is a hypothesis
whose only claim to validity is whether it ranks published sites highly.

Underneath that, there are **two controls**, and every validation statistic worth computing
is inert at n = 2. That is the binding constraint, not the weight set. The fix does not need
permission or fieldwork: historic USGS topographic quads are public domain, mark mills, fords,
furnaces, cemeteries and homesteads by symbol, and take n into the dozens from three
hand-digitized sheets. The symbols that have *vanished* from the modern quad then give the
detection chain a public, dated ground truth to be tested against — including its misses,
which is what makes recall estimable.

The scope widened on 2026-09-03 and the work is recorded but not started. `ROADMAP.md` has
the priority order; nothing in the CLI takes `--class` yet.

## Attribution

Openness is computed with horizon-scan functions vendored from the
[Relief Visualization Toolbox](https://github.com/EarthObservation/RVT_py) (Apache-2.0).
The artifact exporter inlines a vendored copy of
[Leaflet](https://github.com/Leaflet/Leaflet)'s stylesheet (BSD-2-Clause). See
[`NOTICE`](NOTICE).

Data: USGS 3DEP, USGS NHDPlus HR, USDA SSURGO, TDEC Public Access Lands, Nashville Metro
Parks, TNMap National Register boundaries.
