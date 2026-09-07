-- Ranked candidate polygons (ROADMAP F1). Idempotent: safe to re-run.
--
-- The product the README promises: the top percentile of one class's score surface,
-- polygonised, ranked, and carrying the burial-risk companion as a separate attribute
-- (never summed into the score - the standing invariant). A zone without a class is
-- meaningless; the class is NOT NULL by construction.

CREATE TABLE IF NOT EXISTS derived.candidate_zone (
    zone_id        serial PRIMARY KEY,
    aoi_id         int NOT NULL REFERENCES derived.aoi(id) ON DELETE CASCADE,
    class_id       text NOT NULL REFERENCES ref.target_class(class_id),
    rank           int NOT NULL,           -- 1 = best, within (aoi, class, derivation)
    area_m2        real NOT NULL,
    score_mean     real NOT NULL,
    score_max      real NOT NULL,
    pct_mean       real NOT NULL,          -- mean percentile of member cells
    hand_mean_m    real,                   -- landform context
    burial_risk    real,                   -- companion: mean band value, NEVER summed
    geom           geometry(Polygon, 26916) NOT NULL,
    derivation_id  int REFERENCES derived.derivation(id) ON DELETE SET NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS candidate_zone_geom_idx
    ON derived.candidate_zone USING gist (geom);
CREATE INDEX IF NOT EXISTS candidate_zone_lookup_idx
    ON derived.candidate_zone (aoi_id, class_id, rank);

COMMENT ON TABLE derived.candidate_zone IS
    'Ranked survey-candidate polygons from one class''s score surface. burial_risk '
    'is a companion attribute: a low-scoring buried cell and a low-scoring wrong '
    'cell are different findings.';
