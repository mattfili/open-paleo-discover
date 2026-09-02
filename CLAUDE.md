# open-paleo-discover

LiDAR-derived landform suitability modelling for archaeological survey planning in Middle
Tennessee. Proof of concept, local only.

**`spec.md` is the source of truth for architecture.** Read it before building anything. This
file covers how to work in the repo, not what to build.

---

## Use the skills. They exist because the docs do not cover this.

Three skills in `.claude/skills/`. They encode failure modes that are invisible until they
have already cost you a day, and several of them fail *silently* — wrong output, exit code
zero, no error.

Consult them on both sides of the work:

- **Build side** — while writing code that calls these tools. The conventions and traps
  belong in the code you generate, not in a debugging session afterwards.
- **Execution side** — while running the pipeline, interpreting output, or answering a
  question about what a result means.

| Skill | Load it when |
|---|---|
| `landform-archaeology` | Anything about terraces, HAND, openness interpretation, what an anomaly might be, whether a low score is meaningful, or how to tune against a control. Also when writing or reviewing a weight set. |
| `whiteboxtools` | Any `wbt.*` call. Before writing a hydrology chain. Whenever a WBT call produced nothing, or produced something that looks plausible and is wrong. |
| `pdal-pipelines` | Any pipeline JSON. Reading LAS/LAZ/EPT/COPC. Producing a DEM. Debugging an empty raster or a DEM full of holes. |

Do not reimplement what is in `scripts/` inside those skills. `wbt_helpers.py`,
`hydro_chain.py`, `run_pipeline.py`, `dem_from_ept.py`, `inspect.py`, and `control_check.py`
are meant to be imported or invoked, not paraphrased.

---

## Invariants

These are load-bearing. Violating any of them produces output that looks fine and is wrong.

**Project CRS is EPSG:26916** (NAD83 / UTM 16N, metres). Everything reprojects to it on
intake. WhiteboxTools does not reproject and will process degrees as if they were metres.

**Two grids, two jobs.** Detection renders at 0.5 m. Predictive modelling at 10 m. Never mix
them. A model fitted at 0.5 m is noise and will not fit in memory; detection at 10 m is blind.

**Openness sign convention.** Positive openness is high on *convex* features (mounds,
hearths, ridges). Negative openness is high on *concave* (pits, ditches, valleys). Flat plane
is 90° for both. Getting this backwards silently inverts every interpretation downstream.

**`pntr=True`** on `d8_flow_accumulation` when the input is a pointer raster. Without it the
tool reads directions as elevations, returns 0, and writes plausible nonsense.

**EPT bounds are in the EPT's own CRS**, which is EPSG:3857 for the USGS public bucket. Pass
UTM and you get zero points with no error.

**Breach, do not fill.** `fill_depressions` raises pits to their spill elevation, destroying
small closed depressions — which in karst is most of the landscape and in this domain may be
the target.

**Burial risk is a companion band, never summed into the score.** A cell scores low either
because the landform is wrong or because anything there is under metres of overbank silt.
Those are different findings.

---

## Tools available

### MCP servers

**`context7`** — library documentation on demand. Prefer it over recalling API details for
rasterio, geopandas, pynhd, ibis, or the PDAL Python API. Current docs beat a frozen snapshot.

**`qgis-mcp`** — drives a running QGIS Desktop session: load layers, run Processing
algorithms, style, render, author layouts. QGIS is the interactive surface for this project
(there is no web explorer — see `spec.md` §8), so this is how visual inspection happens.
Exposes arbitrary PyQGIS execution; fine locally, do not leave it running.

**`postgis`** (mcp-postgis) — read-only PostGIS introspection and spatial query. Publishes
results as views that QGIS picks up automatically. **Try this before building `midden_sql`
and possibly `midden_query`** — it may already cover them.

### Registering mcp-postgis — you do this yourself, after M0

The server requires `MCP_POSTGIS_DATABASE_URL` and will not start without it. The database
does not exist until `compose.yaml` is up and the schemas are created, so registration is a
step at the end of M0, not part of environment setup.

Once Postgres is running and `ref` and `derived` exist:

```bash
claude mcp add --transport stdio \
  --env MCP_POSTGIS_DATABASE_URL="postgresql://USER:PASS@localhost:5432/DBNAME" \
  --env MCP_POSTGIS_MODE=read_only \
  --scope user \
  postgis -- uvx --with 'mcp<2' --python 3.12 mcp-postgis
```

Three things about that command:

- **`--with 'mcp<2'` is required.** The package imports `mcp.server.fastmcp`, removed in MCP
  SDK 2.x. Without the pin it fails at import.
- **`--scope user`, not project.** This repo is public. A connection string in a
  project-scoped MCP config would be committed.
- Use the credentials from your local `.env`, which is gitignored. Do not hardcode them
  anywhere tracked.

Verify with `/mcp` and restart Claude Code.

### Deferred

**`postgres-mcp`** (Crystal DBA) — index tuning, EXPLAIN with hypothetical indexes, health
checks. Add when the 10 m feature stack queries get slow. Load `pg_stat_statements` and
`hypopg` in the Docker image now so they are there when needed.

### Avoid running everything at once

`mcp-postgis`, `postgres-mcp`, and the eventual `midden` server all hit the same database
with overlapping tools. Three plausible answers to "query the database" makes tool selection
unreliable. Use `mcp-postgis` during exploration, `postgres-mcp` only when tuning, `midden`
for domain operations.

---

## Environment

Installed via Homebrew: `uv`, `gdal`, `pdal`, `qgis`, and Docker (OrbStack or Desktop).

**WhiteboxTools is not a brew install.** The `whitebox` PyPI package downloads its binary on
first import. On Apple Silicon it may be quarantined:

```bash
xattr -dr com.apple.quarantine "$(python -c 'import whitebox, os; print(os.path.dirname(whitebox.__file__))')"
```

**Call PDAL as a subprocess, not via the Python bindings.** The bindings compile against
libpdal and the version match breaks regularly on macOS. `run_pipeline.py` in the
`pdal-pipelines` skill wraps the CLI. The pipeline is JSON either way, so nothing is lost.

**Python is managed by `uv`.** `uv sync`, `uv run`. No pip, no conda.

---

## Repo conventions

**Nothing large or generated goes in git.** Feature stacks are multi-million-row coordinate
tables, COGs run to hundreds of megabytes, and QGIS project files embed local absolute paths.

```gitignore
data/
*.qgs
*.qgz
exports/
.env
```

**Three tests only** (`spec.md` §3): CRS uniformity, DEM units, intake YAML round-trip. No
CI. CRS and unit bugs are silent and poison everything downstream; the rest you catch by
looking at maps.

**Every derived artifact gets a `derivation` row** — operation, tool, tool version,
parameters, inputs, git SHA. This is what makes a result reproducible six months later, and
it is what turns "should we use X or Y" into a swept parameter rather than an argument.

**Judgment calls become parameters, not decisions.** If a choice would otherwise be settled
once in prose, make it a named parameter with the value recorded in `derivation.params`, and
sweep it. `midden_sweep` exists for this.

---

## Working style

Terse and direct. Push back on bad approaches rather than implementing them. Prove things out
rather than hand-waving — if a claim about a library, a CRS, or a tool's behaviour is
load-bearing, verify it against the installed version rather than recalling it.

Python and SQL server-side. macOS, terminal is cmux. No emoji.
