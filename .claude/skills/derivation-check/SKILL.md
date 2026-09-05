---
name: derivation-check
description: >
  Verify that a just-produced artifact has a complete provenance row in
  derived.derivation. Use after ANY operation that writes a raster, loads
  labels, runs a score, or performs a sweep — before reporting the work done.
  Catches the silent gap where an artifact exists on disk but is not
  reproducible (score runs shipped derivation_id=None for months).
---

# Derivation check — is this artifact reproducible?

CLAUDE.md: every derived artifact gets a `derivation` row — operation, tool,
tool version, parameters, inputs, git SHA. This skill is the verification
half: run it after the work, not instead of it. An artifact that fails these
checks is **not finished**, even if the file looks right.

## The checks

Run against the live database (psql via `docker compose exec db`, the
mcp-postgis server, or `uv run python -c` with `midden.db.connect`).

**1. The row exists and is closed.**

```sql
SELECT id, operation, tool, tool_version, status, git_sha,
       params, inputs, started_at, finished_at
FROM derived.derivation
ORDER BY started_at DESC LIMIT 5;
```

The operation you just ran must be at the top with `status = 'ok'`. A row
stuck at `'running'` means the context manager never closed — the operation
crashed after writing output, and the artifact is orphaned.

**2. Nothing rides with a NULL git SHA.** `git_sha IS NULL` means the run
happened outside a git checkout or the lookup failed. Either way the result
cannot be tied to code. Flag it; do not silently accept it.

**3. Params are the real params.** `params` must contain every value that
would change the output — including the `class_id` for any scoring,
detection, or sweep operation, and the swept parameter values for a sweep.
An empty `{}` on a parameterized operation is a bug in the calling code, not
a cosmetic gap: it makes the sweep unreusable ("Any parameter sweep records
which class it was swept for, or the result cannot be reused").

**4. The artifact points back.**

```sql
SELECT id, kind, grid, resolution_m, variant, path, derivation_id
FROM derived.raster_asset
ORDER BY created_at DESC LIMIT 5;
```

`derivation_id` must not be NULL on anything just created. For score
surfaces, `variant` must carry the class. For control-site loads, check
`ref.control_sites.derivation_id` instead.

**5. Failures are recorded as failures.** If the operation failed, the row
must say `status='failed'` with `error` populated — a deleted or missing row
for a failed run erases exactly the negative result CLAUDE.md says is worth
the most.

## Reporting

One line per check, pass/fail, in the final summary of whatever work invoked
this skill. If any check fails, the work is reported as incomplete with the
failing check named — never "done, except the provenance".
