---
name: render-qa
description: >
  Visual QA of rendered map output through qgis-mcp — verify symbology matches
  the openness sign convention, sample values at known control coordinates,
  and confirm a render shows what its explanation claims. Use after any
  midden render, QGIS styling operation, or Leaflet artifact export, before
  the output is explained or shared.
---

# Render QA — the map must agree with its own caption

The MCP evals (G1) test the *server's answers*; nothing tests the *maps*. A
correctly computed raster styled backwards teaches the wrong sign convention
just as effectively as an inverted computation — and CLAUDE.md's rule is
that output which is not explained is not finished, which makes a render
whose explanation contradicts its pixels worse than no render.

## The procedure

1. **Load and sample before styling judgments.** With qgis-mcp: load the
   layer (`add_raster_layer`), then `sample_raster_values` at 2–3 coordinates
   where the answer is known. The standing anchors:
   - Mound Bottom platform / any ridge crest: **positive openness high**,
     negative openness low.
   - A relict channel, sinkhole, or incised ravine: **negative openness
     high**, positive low.
   - Broad floodplain: both openness bands **near 90°** (flat-plane rule).
   - A cell on a mapped NHD flowline: HAND ≈ 0.
   - Any control site footprint: the class's score surface should not be at
     its regional minimum there (if it is, say so — that is a finding, not a
     rendering choice).
2. **Check the styling direction.** Read the layer's renderer (color ramp
   min/max, inversion flag). "Bright = high value" is the project
   convention; an inverted ramp must be deliberate and stated in the
   artifact prose. For openness layers specifically, confirm the caption's
   "bright means convex/concave" sentence matches the ramp direction *and*
   the band actually loaded — `openness_pos` vs `openness_neg` mixups
   survive every numeric check.
3. **Render and look.** `render_map` at the AOI extent. Compare against what
   the explanation claims the reader will see: if the caption says "the
   platform edge reads bright," it must actually read bright in the render.
4. **Grid check on composites.** In any multi-layer scene, confirm no
   detection-grid (0.5 m) layer is composited into a model-grid (10 m)
   interpretation or vice versa; a scene mixing grids needs the caption to
   say which layer answers which question.
5. **Class qualification.** Every score layer in a scene carries its
   class in the layer name and the caption (`score_10m_<class>`). A render
   showing an unqualified score surface violates the registry acceptance and
   is not shipped.

## Reporting

Paste the sampled values (coordinate, layer, value, expected direction,
verdict) into the artifact's explanation or the session summary. A render
passes render-QA only when the sampled values, the ramp direction, and the
caption all tell the same story. Then apply the `midden-interpretation`
skill for the full explanation — this skill checks the map is honest;
that one makes it legible.
