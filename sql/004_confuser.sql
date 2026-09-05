-- Confuser ledger (ROADMAP A4). Idempotent: safe to re-run.
--
-- When a candidate turns out to be a logging deck, a CCC terrace, a campground loop,
-- or a push pile, it goes here with the class it imitates. These are the hard
-- negatives that set precision; deleting them throws away the most expensive
-- information in the project (CLAUDE.md invariant: confusers are logged, not
-- discarded).

CREATE TABLE IF NOT EXISTS ref.confuser (
    confuser_id     serial PRIMARY KEY,
    kind            text NOT NULL,      -- what it actually is
    imitates        text REFERENCES ref.target_class(class_id),  -- class it looks like
    -- The four-way classification from the landform-archaeology discipline; a
    -- confuser row is normally 'likely modern' or 'likely natural'.
    assessment      text NOT NULL,
    basis           text NOT NULL,      -- what the call rests on: render, map, field
    geom            geometry(Point, 26916) NOT NULL,
    extent_m        real,               -- rough size, metres
    derivation_id   int REFERENCES derived.derivation(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT confuser_assessment_check CHECK (assessment IN
        ('likely cultural', 'ambiguous', 'likely natural', 'likely modern'))
);
CREATE INDEX IF NOT EXISTS confuser_geom_idx ON ref.confuser USING gist (geom);

COMMENT ON TABLE ref.confuser IS
    'Hard negatives: anthropogenic and natural features that imitate a target class. '
    'Logged, never discarded — they are what sets detection precision.';
