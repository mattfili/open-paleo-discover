# midden

LiDAR-derived landform suitability modelling for archaeological survey planning in Middle
Tennessee. Proof of concept, local only.

A pipeline that turns public LiDAR and environmental data into a ranked set of polygons
worth walking, plus an MCP layer so an AI can query, configure, and *look at* the result.

**The honest limit, and it shapes the whole design:** LiDAR finds mounds, earthworks and
historic features well. It finds middens poorly — most Archaic shell-bearing sites in the
Cumberland and Harpeth drainages are buried with no surface expression. So the primary
output is a *landform-and-soils suitability surface*, not a feature detector.

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
- **Openness sign convention.** Positive openness is high on *convex* ground (mounds,
  charcoal hearths, ridges); negative is high on *concave* (pits, ditches, relict channels).
  A flat plane is 90° in both, whatever its slope. Getting this backwards silently inverts
  every interpretation downstream.
- **Burial risk is a companion band, never summed into the score.** A cell scores low either
  because the landform is wrong or because anything there is under metres of overbank silt.
  Those are different findings.
- **`dist_to_road` is never a feature.** It predicts where archaeologists have looked, not
  where people lived.

## Status

All seven milestones in `spec.md` §11 are implemented and the pipeline runs end to end.
The predictive output is **not yet trustworthy**: the seed weight set is falsified by its
own controls, and the cause is diagnosed in [`ROADMAP.md`](ROADMAP.md). That is the loop
working — a weighted overlay is a hypothesis whose only claim to validity is whether it
ranks published sites highly.

## Attribution

Openness is computed with horizon-scan functions vendored from the
[Relief Visualization Toolbox](https://github.com/EarthObservation/RVT_py) (Apache-2.0).
The artifact exporter inlines a vendored copy of
[Leaflet](https://github.com/Leaflet/Leaflet)'s stylesheet (BSD-2-Clause). See
[`NOTICE`](NOTICE).

Data: USGS 3DEP, USGS NHDPlus HR, USDA SSURGO, TDEC Public Access Lands, Nashville Metro
Parks, TNMap National Register boundaries.
