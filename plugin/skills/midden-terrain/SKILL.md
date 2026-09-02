---
name: midden-terrain
description: >-
  Read midden's terrain products and decide what an anomaly is. Use when looking at
  openness, SLRM, or hillshade renders; when asking whether a bump or hollow is cultural;
  when choosing a search radius or smoothing radius; or when deciding which grid a
  question belongs on. Also use before running midden_derive_terrain or midden_sweep.
---

# Reading midden terrain

## Two grids, and the question decides which

**Detection, 0.5 m** — openness, SLRM, hillshade. For *looking at*. Comes from the LiDAR
point cloud; the fast 3DEP path tops out at 10 m and cannot produce it.

**Modelling, 10 m** — HAND, slope, streams, and every predictive feature. For *fitting*.

Never mix them. A model fitted at 0.5 m is noise; a feature hunted at 10 m is invisible.
`midden_list_rasters` reports the grid of every asset.

## The openness sign convention

This is the single easiest thing to get backwards, and it fails silently — nothing errors,
every interpretation just inverts.

| Surface | High (>90 deg) means | Look here for |
|---|---|---|
| `openness_pos` | **convex** | mounds, charcoal hearths, platforms, ridges |
| `openness_neg` | **concave** | pits, ditches, borrow areas, relict channels, cut earthworks |

A flat plane is exactly 90 in both, *regardless of its slope*. That is the property that
makes openness illumination-independent, and it is the first thing to check on a new
render: `midden_raster_stats` should report a median near 90.

Negative openness is not the inverse of positive. Render and read both. A mound with a
surrounding borrow ditch shows its top in positive and the ditch ring in negative — and
that pairing is far more diagnostic than either alone.

**Feature shape changes which surface carries the signal.** A smooth mound reads strongest
at its summit in positive openness. A flat-topped platform — which is what a charcoal
hearth is — reads only as a thin bright rim in positive, while negative openness darkens
across the whole disc. On a synthetic 10 m hearth the rim contrast is about +0.85 deg in
positive and the disc about -1.9 deg in negative. Check both before concluding nothing is
there.

## Choosing a radius

`search_radius_m` (openness) and `smoothing_radius_m` (SLRM) are declared in metres and
converted to grid cells against whichever raster is being processed, so the same value
means the same physical distance on either grid.

- 5-10 m finds hearths and small mounds.
- 15-25 m finds house platforms and larger earthworks, and smooths small things away.
- Much larger and you are measuring the landform, not the feature on it.

Tune with `midden_sweep` against a **control**, then `midden_preview_raster` on each
variant. Openness previews use a display window fixed on 90 degrees rather than a
per-image stretch, so variants are directly comparable.

Never tune against a prospect AOI. There is no ground truth there, so a parameter fitted
to it is fitted to noise.

## Before calling anything cultural

Most sites are not visible in LiDAR at all. The primary product of this project is a
landform-and-soils suitability surface; visual anomaly detection is a secondary,
human-in-the-loop mode.

Rule out, in roughly this order: tree throw (paired mound and hollow), karst sinkhole,
log landing, flight-line seam, modern conservation terracing, a building pad, a spoil
heap. Check whether the area has sparse ground returns — `midden_raster_stats` on
`ground_count` says how much of the surface is measured rather than interpolated.

**One anomaly is not a finding.** Look for spatial pattern: repetition, alignment, a
relationship to the terrace edge or a confluence.

Report uncertainty as a category, never as a hedge: `likely cultural`, `ambiguous`,
`likely natural`, `likely modern`.

## Terraces

Terraces are low slope plus a discrete mode in the HAND histogram. `midden_derive_terrain`
on the modelling grid returns `hand_diagnostics` with the modes it found. Two or more modes
is a plausible terrace sequence; fewer than two usually means the stream threshold is wrong
for that landscape rather than that the landscape has no terraces.

Ascending modes label T0, T1, T2. **T1 is where sites are.** Expect a main-stem valley to
show T1 around 3-4 m above the stream; a dissected upland with only headwater streams will
not show a low terrace at all, and that is a real result rather than a failure.
