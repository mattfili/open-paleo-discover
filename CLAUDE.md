# open-paleo-discover

LiDAR-derived landform suitability modelling for archaeological survey planning in Middle
Tennessee. Proof of concept, local only.

**`spec.md` is the source of truth for architecture.** Read it before building anything. It
was amended on 2026-09-03 for the widened scope; §0 carries a banner saying which sections
changed.

**@ROADMAP.md is the source of truth for state** — what is built, what is not, and what is
known to be broken. `spec.md` says what the project should be; the roadmap says where it
actually is. That `@` is an import: the roadmap is pulled into context with this file, so
it is already in front of you. Do not re-read it, and do not re-derive project status by
exploring the tree or re-running the pipeline.

This file covers how to work in the repo, not what to build and not where things stand.

**Keep the roadmap current.** Any commit that finishes something, breaks something, or
discovers a constraint updates `ROADMAP.md` in the same commit — **including when the result
is negative.** A recorded failure is worth more than an unrecorded success; the
`hand_mode_tolerance_m` entry is the model to follow. A roadmap that lags the code is worse
than none, because the next session will trust it.

---

## Scope

This project models the archaeological and historical landscape record of Middle Tennessee.
Middens are one target class within it, and the least detectable one. **Do not describe the
project as a midden finder, and do not treat midden detectability as the project's ceiling.**

Every target class has its own detectability, its own scale, its own label source, and its
own parameters. These live in `ref.target_class`, which is the single source of truth for all
of them.

---

## Use the skills. They exist because the docs do not cover this.

The four below live in `.claude/skills/`, alongside the two `bsl-*` skills that ship with
boring-semantic-layer. Three of the four encode failure modes that are invisible until they
have already cost you a day, and several of those fail *silently* — wrong output, exit code
zero, no error. The fourth governs how output is explained.

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
| `midden-interpretation` | **Every artifact, map, render, preview or score.** Any question of what a feature means, why it is in the model, or what a number implies. Non-optional: output that is not explained is not finished. |

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

**No unqualified score.** Every scoring, detection, validation, or render operation takes a
`class_id`. A score surface without a class attached is meaningless, because the features
that predict a Mississippian mound platform are not the features that predict a charcoal
hearth. If a command can run without `--class`, that is a bug.

**Detection parameters are per class, never global.** Openness search radius, SLRM radius,
and minimum-area thresholds come from `ref.target_class.params`. A hearth is ~10 m, a mound
platform is 30–100 m, a mill race is a metre wide. A single global radius silently serves
none of them. Any parameter sweep records which class it was swept for, or the result cannot
be reused.

**Detectability is declared, not assumed.** A class is *direct* (a LiDAR signature exists),
*proxy* (only landform suitability is available), or *invisible*. Never present a proxy
result as a detection, and never run a detection chain for an invisible class and report the
absence as evidence.

**Burial risk is a companion band, never summed into the score — and it is per class.** A
cell scores low either because the landform is wrong or because anything there is under
metres of overbank silt. Those are different findings. Overbank burial removes a midden and
does nothing to a rockshelter: the rule that it is a band and not a term stands unchanged,
but *which classes it applies to* is a registry field rather than a global assumption.

**Historic-map evidence carries a date and a positional error.** A feature on an 1895 quad
and absent in 1935 is dated to that window; say so. Historic quads are not survey-grade, so
`positional_confidence_m` travels with every point derived from one and is used as the
tolerance radius in validation. A detection "hit" inside a tolerance that was never recorded
is not a hit.

**Label provenance is mandatory.** Every row in `ref.control_sites` carries `source`,
`source_id` or `source_sheet`, and `class_id`. Labels from different sources are never pooled
without recording it, because they have different biases: NRHP skews monumental, historic
quads skew historic-period and near-settlement, model-derived weak labels skew toward
whatever the model already believes.

**Weak labels never become ground truth.** Stage-2 detections fed back into stage-1 training
are flagged as such in provenance and are excluded from any validation set. A model validated
against its own output is validated against nothing.

**Confusers are logged, not discarded.** When a candidate turns out to be a logging deck, a
CCC terrace, or a push pile, it goes into `ref.confuser` with its class-lookalike noted. These
are the hard negatives that set precision. Deleting them throws away the most expensive
information in the project.

**A companion band is promoted to a scored feature only by test, never by argument.** The
bar: does the feature register at a control where it should (a known example fires), and do
the controls move when it is included? Both answers recorded, including when they are no.
`dist_to_road` stays permanently unpromotable — it is a diagnostic. It predicts where
archaeologists have looked, not where people lived, and keeping it out of the stack does not
remove access bias, it only removes the ability to measure it.

**Where a source is missing, say so in the artifact.** If a feature rests on an ethnographic
or geomorphological claim that has not been sourced, the gap is recorded in the sources file
and surfaced by the skill that explains the feature. Portage nodes (`neck_max_m`,
`loop_min_m`) are the current example: dugout travel in the interior Southeast is well
attested, neck portages on rivers of this size are not sourced, and that stays visible until
it is closed.

**Nothing ships unexplained.** Every artifact, render and score carries prose saying what
each layer measures, what bright and dark mean on it, why the feature is in the model, what
would fool you, and what the output does not claim. Verbosity is correct here; a reader who
skims a thorough explanation loses nothing, while a reader given a thin one forms a wrong
belief. See the `midden-interpretation` skill.

---

## Interpretive-layer conventions

The MCP layer exists so that someone without geoarchaeology training can read what the
pipeline is saying. That makes correctness load-bearing in a way it would not be for a pure
query interface: a wrong query result wastes a minute, a wrong interpretation installs a
false belief that then shapes feature design.

**Interpretations cite.** A skill that explains a landform association, a terrace
relationship, or an industrial-archaeology signature carries references. If it cannot, it
says the claim is unsourced rather than asserting it.

**Attribution over assertion.** When explaining why a cell scores highly, return the
per-feature decomposition — values, normalised percentiles, contribution — not a narrative.
The narrative is the user's job; the numbers are the tool's.

**The sign convention is a test case, not a comment.** Positive openness is high on convex
ground, negative on concave, a flat plane is 90° in both. This is in `plugin/mcp/evals.xml`
and the evals must actually run. An interpretive tool that gets this backwards inverts every
downstream reading silently, which is the exact failure the invariant was written to prevent.

**Class briefs are first-class.** `midden_class_brief` returns a class's morphology, size
range, parameters, detectability, known confusers, and sources. The registry is only useful
for learning if it is legible from inside a conversation.

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

## Working conventions

**`ROADMAP.md` stays canonical for state.** Update it in the same commit as the work,
including when the result is negative. A recorded failure is worth more than an unrecorded
success — the `hand_mode_tolerance_m` entry is the model to follow.

**Prefer fixing a feature over reweighting around it.** `terrace_class` is the standing
example: the fix is deletion, not a better labeller.

**Prefer a test that can falsify over a test that can pass.** The vanished-feature test —
take a symbol off a historic quad, run the detection chain, count misses as well as hits — is
worth more than any number of controls that were chosen because they are known sites.

**Before adding a feature, ask what it would take to remove it.** If ablation cannot measure
its contribution, it is not ready to be scored.

---

## Working style

Terse and direct. Push back on bad approaches rather than implementing them. Prove things out
rather than hand-waving — if a claim about a library, a CRS, or a tool's behaviour is
load-bearing, verify it against the installed version rather than recalling it.

Python and SQL server-side. macOS, terminal is cmux. No emoji.
