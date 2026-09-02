---
name: midden-semantic
description: >-
  Query midden's semantic layer and extend it. Use when asking a counting or aggregating
  question about AOIs, flowlines, confluences, the raster catalog, or the derivation
  ledger; when writing or editing a boring-semantic-layer YAML model in semantic/; or when
  deciding between midden_query and raw SQL.
---

# Querying and extending the semantic layer

## Which tool

**`midden_query`** for the curated vocabulary — named dimensions and measures that carry
descriptions. This is the semantic layer's whole reason to exist.

**mcp-postgis `execute_sql`** for arbitrary SQL, spatial predicates, `EXPLAIN`, and
`create_layer` (which publishes a result as a view that QGIS picks up automatically).
midden deliberately does **not** ship a competing `midden_sql`, because two plausible
answers to "query the database" makes tool selection unreliable.

## The workflow, in order

1. `midden_list_semantic_models` — see what exists.
2. `midden_get_model_schema(model)` — **required before querying.** Field names must match
   exactly. They are curated names, not column names, and cannot be guessed from the
   underlying tables.
3. `midden_query(...)` — dimensions group, measures aggregate.

Filters are strings of the form `field OP value`, where OP is one of `=`, `!=`, `>`, `>=`,
`<`, `<=`. Values that look numeric are compared as numbers. Example: `stream_order>=3`.

## What the models cover

| Model | Grain | Useful for |
|---|---|---|
| `aoi` | one area of interest | area by role, what is seeded, which are controls |
| `nhd_flowline` | one reach | stream order distribution, named streams, total length |
| `confluence` | one junction | how many junctions, at what orders |
| `derivation` | one run | what ran, with which tool version, and whether it failed |
| `raster_asset` | one COG | what has been derived, on which grid, at what resolution |

`derivation` is worth more than it looks. It is the provenance ledger, so "which runs
failed and why" and "what tool version produced this raster" are both single queries.

## Extending it

Models live in `semantic/*.yml`, one file per subject area. The shape:

```yaml
model_name:
  table: some_alias_tbl        # resolved by POSTGRES_TABLES in semantic/build.py
  description: What this model is.
  dimensions:
    field_name:
      expr: _.column
      description: What it means.
  measures:
    measure_name:
      expr: _.column.sum()
      description: What it counts.
```

Constraints that will bite otherwise:

- **YAML uses unbound `_.field` syntax only.** No lambdas.
- `ibis.cases()` is **plural**. `ibis.case` does not exist.
- Every model in a join tree needs a unique name.
- `group_by()` and `aggregate()` take **string names**, not expressions.
- Write a `description` on every dimension and measure. Those strings are what
  `midden_get_model_schema` hands a model, and an undescribed field is a field nobody will
  use correctly.

## One backend, two stores

DuckDB is the single Ibis connection. Ibis has no cross-backend joins, so `ref.*` and
`derived.*` are attached into the DuckDB session with `read_postgres`, and Parquet feature
stacks are read in the same session. The consequence worth knowing: the semantic layer
reads Postgres *through* DuckDB, so if Postgres is down, BSL is down.
