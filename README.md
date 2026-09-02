# midden

LiDAR-derived landform suitability modelling for archaeological survey planning in Middle
Tennessee. Proof of concept, local only.

- **`spec.md`** — architecture and design decisions. The source of truth.
- **`CLAUDE.md`** — how to work in this repo.

## Quick start

```bash
cp .env.example .env      # then set POSTGRES_PASSWORD and MIDDEN_RO_PASSWORD
docker compose up -d      # Postgres 17 + PostGIS 3.5 + hypopg
uv sync
uv run midden db init     # apply schema, set the read-only role password
uv run midden doctor      # verify postgres, PDAL, and the WhiteboxTools tool set
uv run midden db check    # inventory + the project-CRS assertion
```

`uv run midden doctor` downloads the WhiteboxTools binary (~100 MB) on first run.

## Notes

Everything is EPSG:26916 (NAD83 / UTM 16N, metres). Detection renders are 0.5 m; predictive
modelling is 10 m. The two never mix.

## Attribution

Openness is computed with horizon-scan functions vendored from the
[Relief Visualization Toolbox](https://github.com/EarthObservation/RVT_py) (Apache-2.0).
See `NOTICE`.
