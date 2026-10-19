-- Review provenance on control sites (stabilization pass, 2026-10-19). Idempotent.
--
-- The reviewed label corpus is human work that cost days and previously lived only in
-- Postgres, so one lost database volume would have erased it. These columns let the
-- review round and timestamp travel with a point into the tracked labels/*.geojson files
-- (see src/midden/corpus.py) and back out again on a rebuilt database.
ALTER TABLE ref.control_sites ADD COLUMN IF NOT EXISTS review_round int;
ALTER TABLE ref.control_sites ADD COLUMN IF NOT EXISTS reviewed_at timestamptz;
-- Superseded earlier decisions on the same point (e.g. round-1 'unsure' later confirmed
-- in round 2), oldest first: [{"decision", "round", "at", "note"}].
ALTER TABLE ref.control_sites ADD COLUMN IF NOT EXISTS review_prior jsonb;
