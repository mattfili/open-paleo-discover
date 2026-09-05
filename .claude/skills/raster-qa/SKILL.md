---
name: raster-qa
description: >
  Mechanical sanity checks for any raster the pipeline produces — CRS, pixel
  size, units, nodata, constant output, value ranges by kind, WBT predictor
  compatibility. Use IMMEDIATELY after any terrain run, DEM build, score run,
  or warp, before cataloguing or interpreting the result. The failure modes it
  catches all exit 0 and look plausible.
---

# Raster QA — run the script, then read the checklist

Every failure this skill catches has the same shape: the tool exits 0, the
file exists, and the contents are wrong. The check is cheap; debugging the
downstream consequence is a day.

## The script

```
uv run python .claude/skills/raster-qa/scripts/check_raster.py <path> \
    [--grid detection|model] [--kind dem|openness_pos|openness_neg|slope|aspect|hand|twi|slrm|score]
```

Always pass `--grid` and `--kind` when known — the resolution and range
checks are the highest-value ones. Exit 0 means all checks pass; failures
print with the observed value. Run it on **every** raster you produce, and
paste the output into your summary. A raster that fails is not catalogued
and not interpreted; fix the producer.

What it checks and why each check exists:

| check | failure it catches |
|---|---|
| CRS = EPSG:26916 | 3DEP arrives EPSG:4269; historic quads NAD27; WBT treats degrees as metres |
| pixel > 0.01 units | a degree-sized pixel that survived an unwarped fetch |
| resolution matches grid | detection (0.5 m) and model (10 m) rasters must never mix |
| elevation 50–700 m (dem) | a DEM in feet (~360–1900 here) or other wrong units |
| openness in [0°, 180°] | wrong output scale from a reimplemented visualization |
| nodata declared, ≥5% valid, non-constant | empty-bounds fetches, panicked tools writing flat rasters |
| sentinel values inside valid data | -9999/-32768 leaking through as real elevations |
| no float PREDICTOR | WBT exits 0 while panicking on predictor-compressed input |

## What the script cannot check — eyeball these

1. **The openness sign.** Both openness rasters pass the range check even if
   swapped. Verify against a known landform: positive openness must be
   *high* (bright) on the Mound Bottom platform edge and ridge crests, and
   negative openness high in relict channels and sinkholes. Sample 2–3 cells
   at known coordinates (rasterio `sample`, or qgis-mcp
   `sample_raster_values`) — see the `render-qa` skill.
2. **Alignment across a stack.** Two rasters can each pass alone and still
   be offset by half a cell. Compare `bounds` and `transform` of every layer
   feeding one computation; they must be identical, not merely overlapping.
3. **Flat-plane openness ≈ 90°.** On any broad floodplain cell, both
   openness bands should read near 90°. A flat plane far from 90° means the
   implementation, not the landscape, is wrong.
4. **HAND = 0 on the channel.** Sample a cell on a mapped NHD flowline; HAND
   materially above zero there means the stream burn or pointer chain is off.

## When a check fails

Do not adjust the checker's bounds to pass. The ranges encode Middle
Tennessee physics (Cumberland pool ~110 m NAVD88, Highland Rim < 600 m) and
tool conventions. A legitimate exception — a new AOI outside those bounds, a
new kind — is an edit to the script *with the reasoning in the commit*, not
a skipped check.
