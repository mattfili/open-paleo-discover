-- midden core schema. Idempotent: safe to re-run.
--
-- Two schemas (spec.md §4). §11's "three schemas" is a leftover from a draft that included
-- `restricted`, which §13 explicitly defers along with everything that would need it.
--
-- Two roles: the POSTGRES_USER role (default `midden`) owns everything and is the
-- read-write identity; `midden_ro` is a genuine read-only login used by midden_sql (§9)
-- and by the mcp-postgis server. A separate no-login `midden_rw` group would add an
-- identity that buys nothing here — the owner already is that role.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS hypopg;

CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS derived;

COMMENT ON SCHEMA ref IS
    'Reference data: boundaries, hydrology, soils, land cover, streets.';
COMMENT ON SCHEMA derived IS
    'AOIs, raster catalog, feature stacks, model runs, scores, derivation ledger.';

-- ---------------------------------------------------------------------------
-- Areas of interest. Drives every fetch, derivation, and model run.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS derived.aoi (
    id           serial PRIMARY KEY,
    slug         text UNIQUE NOT NULL,
    name         text NOT NULL,
    kind         text NOT NULL,
    role         text NOT NULL DEFAULT 'prospect',
    source       text,                   -- boundary service this geometry came from
    geom         geometry(MultiPolygon, 26916) NOT NULL,
    geom_wgs84   geometry(MultiPolygon, 4326) GENERATED ALWAYS AS
                     (ST_Transform(geom, 4326)) STORED,
    area_km2     double precision GENERATED ALWAYS AS
                     (ST_Area(geom) / 1e6) STORED,
    created_at   timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT aoi_kind_check CHECK (kind IN
        ('state_park', 'metro_park', 'county', 'watershed', 'custom')),
    -- prospect          : a real candidate area
    -- control_positive  : known published site; validates the predictive model
    -- control_detection : known surface feature; validates the render chain
    -- shakeout          : small AOI used for fast iteration; ignore its scores
    CONSTRAINT aoi_role_check CHECK (role IN
        ('prospect', 'control_positive', 'control_detection', 'shakeout'))
);
CREATE INDEX IF NOT EXISTS aoi_geom_idx ON derived.aoi USING gist (geom);

-- ---------------------------------------------------------------------------
-- The provenance ledger. Every derived artifact points at one of these rows.
-- This is what makes a result reproducible six months later and what turns
-- "should we use X or Y" into a swept parameter rather than an argument.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS derived.derivation (
    id           serial PRIMARY KEY,
    aoi_id       int REFERENCES derived.aoi(id) ON DELETE CASCADE,
    operation    text NOT NULL,          -- e.g. 'terrain.openness'
    tool         text NOT NULL,          -- e.g. 'WhiteboxTools'
    tool_version text NOT NULL,          -- WBT argument names drift between releases
    params       jsonb NOT NULL DEFAULT '{}'::jsonb,
    inputs       jsonb NOT NULL DEFAULT '[]'::jsonb,
    cache_key    text,                   -- content hash of (driver, params, aoi geom)
    git_sha      text,
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    status       text NOT NULL DEFAULT 'running',
    error        text,

    CONSTRAINT derivation_status_check CHECK (status IN ('running', 'ok', 'failed'))
);
CREATE INDEX IF NOT EXISTS derivation_aoi_op_idx
    ON derived.derivation (aoi_id, operation, started_at DESC);
CREATE INDEX IF NOT EXISTS derivation_cache_key_idx
    ON derived.derivation (cache_key) WHERE cache_key IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Raster catalog. Pixels live on disk as COGs; only metadata lives here, so
-- "which rasters cover this AOI" is a PostGIS query and reading pixels is rasterio.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS derived.raster_asset (
    id            serial PRIMARY KEY,
    aoi_id        int NOT NULL REFERENCES derived.aoi(id) ON DELETE CASCADE,
    kind          text NOT NULL,         -- dem | hillshade_multi | slrm | openness_pos
                                         -- | openness_neg | hand | slope | aspect | twi
                                         -- | streams | terrace | score | ground_count
    grid          text NOT NULL,         -- 'detection' (0.5 m) | 'model' (10 m)
    resolution_m  double precision NOT NULL,
    -- A sweep writes N rasters at the same (aoi, kind, resolution) that differ only by
    -- parameters, so the spec's 3-column unique key would make sweeps impossible.
    -- `variant` is a short digest of the parameters that produced this asset; '' is the
    -- default/unswept output.
    variant       text NOT NULL DEFAULT '',
    path          text NOT NULL,
    footprint     geometry(Polygon, 26916) NOT NULL,
    derivation_id int REFERENCES derived.derivation(id) ON DELETE SET NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT raster_asset_grid_check CHECK (grid IN ('detection', 'model')),
    CONSTRAINT raster_asset_unique UNIQUE (aoi_id, kind, resolution_m, variant)
);
CREATE INDEX IF NOT EXISTS raster_asset_footprint_idx
    ON derived.raster_asset USING gist (footprint);
CREATE INDEX IF NOT EXISTS raster_asset_lookup_idx
    ON derived.raster_asset (aoi_id, kind);

-- ---------------------------------------------------------------------------
-- Read-only role. Created without a password here; db.py sets it from .env so no
-- credential ever lands in a tracked file.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'midden_ro') THEN
        CREATE ROLE midden_ro LOGIN;
    END IF;
END
$$;

-- GRANT ... ON DATABASE takes an identifier, not an expression, so the database name
-- has to be interpolated rather than written as CURRENT_CATALOG.
DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO midden_ro', current_database());
END
$$;

GRANT USAGE ON SCHEMA ref, derived, public TO midden_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA ref, derived, public TO midden_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA ref   GRANT SELECT ON TABLES TO midden_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA derived GRANT SELECT ON TABLES TO midden_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public  GRANT SELECT ON TABLES TO midden_ro;
