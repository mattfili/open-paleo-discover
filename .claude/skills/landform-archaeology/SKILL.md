---
name: landform-archaeology
description: Interpret LiDAR-derived terrain for archaeological site prediction and feature detection in the eastern US, with a focus on Middle Tennessee. Use when working with HAND, terraces, openness, SLRM, or any question about what a terrain anomaly might be, whether a landform is a good site candidate, or how to tune a derivation against a known control. Also use when reading or writing weighted-overlay scoring, when deciding whether a low predictive score is meaningful, or when someone asks what a mound, charcoal hearth, midden, or tree-throw looks like in a relief visualization. Do NOT use for general GIS mechanics (CRS handling, file formats, GDAL invocation) — that is covered elsewhere.
---

# Landform archaeology

Domain knowledge for turning terrain rasters into archaeological interpretation. The GIS
mechanics live in other tools; this skill is about what the terrain *means*.

## The one thing to internalize

**Most sites are not visible in LiDAR.** Relief visualization finds mounds, earthworks,
hearths, borrow pits, and historic structures — things with surface expression. It does not
find the large majority of prehistoric sites in the eastern US, which are either plowed flat,
buried under alluvium, or were never topographically expressed to begin with.

This has a hard consequence for how you report results: **a negative result is only
interpretable if you know why.** A cell can fail to show a feature because nothing is there,
or because three metres of overbank silt is on top of whatever is there. Those are different
statements and must never be collapsed into one number. See `references/landform-model.md`
on burial risk.

The primary product is therefore a *landform-and-soils suitability surface* — where people
would have chosen to be — not a feature detector. Visual anomaly review is a secondary,
human-in-the-loop mode.

## Routing

| You are doing this | Read this |
|---|---|
| Any term you are unsure of | `references/glossary.md` |
| Terraces, HAND, confluences, burial risk, why a feature is in the model | `references/landform-model.md` |
| Reading an openness or SLRM render; tuning derivation parameters | `references/visualization-guide.md` |
| "What is this circular thing?" — identifying or dismissing an anomaly | `references/feature-catalog.md` |
| Citing something, or checking a claim in here | `references/bibliography.md` |
| Extracting terraces from a DEM | `scripts/terrace_extract.py` |
| Producing the detection-grid renders | `scripts/detection_renders.py` |
| Confluences from hydrography | `scripts/confluence_extract.sql` |
| Checking whether a weight set is any good | `scripts/control_check.py` |
| Writing a weight set | `templates/weights.yml` |
| Logging a candidate anomaly | `templates/anomaly-log.md` |
| Starting on a new area | `templates/aoi-brief.md` |
| Worked walkthroughs | `examples/` |

## Non-negotiables

**Two grids, two jobs.** Detection renders at 0.5 m; predictive modelling at 10 m. A model
fitted at 0.5 m is noise and will not fit in memory. Feature detection at 10 m is blind. Never
let the two mix.

**Openness sign convention.** Positive openness is high on *convex* features. Negative
openness is high on *concave* features. On a flat plane both equal 90°. Getting this backwards
silently inverts every interpretation downstream — see `references/visualization-guide.md`,
which opens with this because it is the most common error.

**Tune against controls, never against a prospect.** A parameter set is validated on a known
feature at a known location, not on the thing you are hoping to find. Tuning against a
prospect is how you talk yourself into a tree throw. `scripts/control_check.py`.

**One anomaly is not a finding.** Archaeological features are almost always spatially
patterned — hearths cluster within hauling distance of a furnace, house sites cluster along a
lane, mounds sit in defined relationships. An isolated circular anomaly with no context is
overwhelmingly likely to be natural or modern. Look for the pattern before you get excited.

**Report uncertainty as a category, not a hedge.** Every anomaly gets one of: `likely
cultural`, `ambiguous`, `likely natural`, `likely modern`. Prose hedging is not a
classification and does not survive being read by someone else.

## Legal and ethical floor

Excavation, subsurface testing, and artifact collection on state or federal land require a
permit. In Tennessee that is the Tennessee Antiquities Act, administered by the Division of
Archaeology. Surface observation and remote sensing are not restricted; digging is.

Site locations from state site files are protected from public disclosure in most US states.
Published sites with historical markers and literature are not. Keep the two apart and never
move a location from the restricted category to the public one.

If this project ever ingests a non-public site inventory, note that a predictive surface
*fitted on* those locations is itself a disclosure of them, however lossy. Treat model output
as inheriting the sensitivity of its training data.
