# Changelog

## 0.1.0 (2026-10-19) — research freeze

A hardening pass, not a feature release: no model, weight, parameter or rule changed. The
version string was already 0.1.0 in `pyproject.toml` and `midden.__version__`; this entry is
the first to describe it. See `docs/frozen-v0.1.md` for the exact state the January blind
test starts from.

### Added
- `MIDDEN_HOME`, `MIDDEN_DATA_DIR`, `MIDDEN_SCRATCH_DIR`, `MIDDEN_EXPORTS_DIR`,
  `MIDDEN_ENV_FILE`: relocate mutable state and `.env`. Defaults unchanged.
- `settings()` raises `ResourceDirectoryError` with the fix when the repo's bundled
  directories are absent (non-editable install).
- Review state for labels (`review_status`, `review_note`, `review_round`, `reviewed_at`,
  `review_prior`) in the tracked `labels/*.geojson`, restored by `midden histmap load-sites`;
  `midden histmap export-labels`; `midden labels export-confusers` / `load-confusers`;
  `labels/confusers.geojson`; `sql/006_review_provenance.sql`.
- Guard in the hydrology chain: the D8 accumulation raster's minimum must be 1 cell.
- Tests: label/confuser round trip, import hygiene, config overrides, D8 guard, variant
  ambiguity.
- `docs/scaling.md` (with a status note) and the `midden-teaching` skill, with candidate
  coordinates removed.

### Changed
- `pdal-pipelines/scripts/inspect.py` renamed `inspect_pc.py` (it shadowed the stdlib).
- MCP raster resolution refuses an ambiguous variant, as `terrain preview` already did.
- Intake caches declared as `data/...` follow `data_dir`.
- `catalogued raster paths` are re-rooted under `data_dir` when a file has moved.
- `features build` raises an actionable error when `ref.confluence` is missing.
- ruff clean (behavior-neutral fixes only).

### Removed
- `sources/geology.yml` (superseded by `sources/sgmc_geology.yml`).

### Known gaps
- Install editable from a checkout; a wheel or plain git dependency fails by design.
- `ref.confluence` needs `confluence_extract.sql` run by hand after flowline intake.
- `sgmc_geology` intake fails on its second AOI (unit_id is not unique per polygon).
- Both original `ref.confuser` rows and four never-reviewed labels were lost with the
  2026-09-02 database and could not be recovered.
