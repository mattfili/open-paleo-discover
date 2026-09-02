-- Confluence extraction from a hydrography network.
--
-- A confluence is where a tributary meets a main stem: two water sources, two habitat
-- zones, a travel node, good fishing. One of the strongest single predictors in eastern
-- US site models.
--
-- Assumes: NHD (or equivalent) flowlines loaded as ref.nhd_flowline with columns
--   comid          bigint
--   stream_order   int
--   geom           geometry(LineString, 26916)
--
-- Two caveats before you use the output:
--
-- 1. Not all confluences are equal. A first-order joining a first-order is a damp spot,
--    not a node. The scoring below weights by the orders involved.
--
-- 2. Modern hydrography is not ancient hydrography. Channels migrate and reservoirs have
--    drowned or beheaded confluences across the mid-South. Where a pre-impoundment
--    historical quad exists, digitize from it and run this against that network instead.
--    The confluence that mattered may be under sixty feet of water, or exposed in a
--    drawdown zone.

-- ---------------------------------------------------------------------------
-- 1. Raw confluence points
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS ref.confluence;

CREATE TABLE ref.confluence AS
WITH pairs AS (
    SELECT
        a.comid                            AS comid_a,
        b.comid                            AS comid_b,
        a.stream_order                     AS order_a,
        b.stream_order                     AS order_b,
        ST_Intersection(a.geom, b.geom)    AS geom
    FROM ref.nhd_flowline a
    JOIN ref.nhd_flowline b
      ON ST_Intersects(a.geom, b.geom)
     AND a.comid < b.comid          -- each pair once, and never self-intersect
),
points AS (
    -- An intersection can be a point, a multipoint, or (for co-located segments) a
    -- line. Keep only point geometries; dump multipoints into their components.
    SELECT
        comid_a, comid_b, order_a, order_b,
        (ST_Dump(geom)).geom AS geom
    FROM pairs
    WHERE GeometryType(geom) IN ('POINT', 'MULTIPOINT')
)
SELECT
    row_number() OVER ()                       AS id,
    comid_a,
    comid_b,
    order_a,
    order_b,
    LEAST(order_a, order_b)                    AS order_minor,
    GREATEST(order_a, order_b)                 AS order_major,
    -- Weight: the smaller of the two orders dominates, because a big river with a
    -- ditch running into it is still just a big river. Scaled 0-1 with 4 as the
    -- practical ceiling for a "major" tributary junction.
    LEAST(LEAST(order_a, order_b)::numeric / 4.0, 1.0) AS weight,
    geom::geometry(Point, 26916)               AS geom
FROM points;

CREATE INDEX ON ref.confluence USING gist (geom);
CREATE INDEX ON ref.confluence (order_minor);

-- ---------------------------------------------------------------------------
-- 2. Distance-to-confluence, for the feature stack
-- ---------------------------------------------------------------------------
-- Run against the 10 m modelling grid, not the detection grid.
--
-- Only confluences at or above a minimum order are considered, so that the metric
-- means "distance to a junction worth walking to" rather than "distance to the
-- nearest damp intersection".

CREATE OR REPLACE FUNCTION derived.dist_to_confluence(
    cell geometry,
    min_order int DEFAULT 2
) RETURNS double precision AS $$
    SELECT ST_Distance(cell, c.geom)
    FROM ref.confluence c
    WHERE c.order_minor >= min_order
    ORDER BY cell <-> c.geom      -- KNN operator; needs the gist index above
    LIMIT 1;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------------
-- 3. Sanity check
-- ---------------------------------------------------------------------------
-- Run this before using the output. A network of any size should produce hundreds of
-- confluences with a long tail toward low orders. Zero rows means the flowlines are not
-- actually noded at junctions -- some hydrography sources snap only to within a
-- tolerance, in which case ST_Intersects finds nothing and you need ST_DWithin with a
-- small distance instead.

-- SELECT order_minor, order_major, count(*)
-- FROM ref.confluence
-- GROUP BY 1, 2
-- ORDER BY 1 DESC, 2 DESC;
