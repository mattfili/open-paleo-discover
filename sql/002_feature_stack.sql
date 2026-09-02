-- Catalog of 10 m feature stacks (spec.md §7). Idempotent.
--
-- The stack itself is Parquet on disk, read by DuckDB: a few counties at 10 m is tens of
-- millions of rows by ~20 columns, which Postgres will do slowly and DuckDB will do in a
-- second on a laptop. Only the metadata lives here.

CREATE TABLE IF NOT EXISTS derived.feature_stack (
    id            serial PRIMARY KEY,
    aoi_id        int NOT NULL REFERENCES derived.aoi(id) ON DELETE CASCADE,
    resolution_m  double precision NOT NULL,
    path          text NOT NULL,
    row_count     bigint NOT NULL,
    columns       jsonb NOT NULL,
    footprint     geometry(Polygon, 26916) NOT NULL,
    derivation_id int REFERENCES derived.derivation(id) ON DELETE SET NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT feature_stack_unique UNIQUE (aoi_id, resolution_m)
);
CREATE INDEX IF NOT EXISTS feature_stack_footprint_idx
    ON derived.feature_stack USING gist (footprint);

GRANT SELECT ON derived.feature_stack TO midden_ro;
