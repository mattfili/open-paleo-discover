---
name: midden-interpretation
description: >-
  Explain what midden's output actually means, at length and without hand-waving. Use
  EVERY time an artifact, map, render, preview, chart or score is produced or discussed;
  whenever asked what a feature is, why it is in the model, or what a number implies;
  and whenever an anomaly, ranking or control result needs interpreting. Covers what each
  feature measures physically, why it matters archaeologically, what the deep-time record
  of Middle Tennessee looks like, and how to state uncertainty honestly. Verbosity is the
  point: prefer a paragraph that teaches over a sentence that gestures.
---

# Interpreting midden output

## The standing obligation

**No artifact ships without an explanation of itself.** A map that a reader cannot
interpret is a decoration, and a ranked surface handed over without its caveats is worse
than nothing, because it invites confident action on a number whose meaning the reader has
had to guess.

Every render, preview, artifact, or score discussion carries, in prose:

1. **What each layer physically measures**, in units, and how it was computed.
2. **What bright and dark mean** on that specific layer — never assume the convention is
   obvious, because for openness it is genuinely counter-intuitive and inverting it
   inverts every conclusion.
3. **Why the feature is in the model at all** — the archaeological reasoning, not just the
   geomorphic definition.
4. **What would fool you** — the false positives and the failure modes for that layer.
5. **What the output does *not* claim.**

Err long. A reader who skims a thorough explanation loses nothing; a reader given a thin
one forms a wrong belief.

## Two things that must appear in every interpretation

### Most sites are not visible in LiDAR

This is the frame for everything else. LiDAR resolves *topography*. It finds mounds,
earthworks, borrow pits, terraces, charcoal hearths, historic roadbeds and quarry cuts —
things with surface expression.

It does not find middens, lithic scatters, hearth features, post moulds, or anything
buried. Most Archaic occupation in the Cumberland and Harpeth drainages has **no surface
expression at all**, and a great deal of it is under metres of alluvium.

So midden's primary product is a **landform-and-soils suitability surface**: a statement
about where the ground has the properties people preferred. It is not a site detector.
Visual anomaly review is a secondary, human-in-the-loop mode.

Say this. Every time. A reader who thinks they are looking at a site-detection map will
misread every part of the output.

### A low score has two completely different meanings

A cell scores low because:

- **the landform is wrong** — steep, wet, far from water, badly drained; or
- **the landform may be fine and anything on it is buried** under overbank alluvium.

These are not the same finding and must never be collapsed. That is why `burial_risk`
(alluvial parent material × flooding frequency) rides alongside the score as a companion
band and is never summed into it.

**A low score with high burial risk is not evidence of absence. It is a statement that this
method cannot see there.** Report it that way explicitly.

## Structure for interpreting an artifact

Work through these in order. Skipping straight to the anomalies is how people talk
themselves into finding things.

**1. Setting.** Where is this, physiographically? Central Basin river valley or dissected
Highland Rim? Which drainage, and what order of stream? What is the relief? A reader who
does not know they are looking at a floodplain versus an upland bench cannot evaluate
anything else you say.

**2. Land-use history.** What has happened to this ground since? Ploughing, impoundment,
quarrying, logging, road building, golf-course construction, conservation terracing. This
determines what could still be preserved and what every anomaly is *most likely* to be.
Most anomalies in Middle Tennessee are twentieth-century.

**3. Data quality, before interpretation.** How much of the surface is measured rather than
interpolated? The `ground_count` raster answers this — under canopy at QL2, 0.5 m is often
optimistic and 1 m honest. A "feature" in a zone with no ground returns is an artefact of
interpolation. Check this before you look at anything.

**4. Layer by layer.** For each, what it measures, what bright means, what to look for.

**5. Landform reading.** Where are the terraces, what is the HAND structure, where is the
water, where are the confluences. This is the archaeological argument.

**6. Anomalies, if any.** With false positives ruled out explicitly and individually.

**7. What this does not tell you.**

## Uncertainty is a category, never a hedge

Four categories, and use them by name:

- **`likely cultural`** — form, scale, setting and context all fit, false positives ruled
  out individually, and there is spatial pattern rather than one isolated thing.
- **`ambiguous`** — genuinely could go either way; say precisely what would settle it.
- **`likely natural`** — tree throw, karst sinkhole, slump, channel scar, bedrock outcrop.
- **`likely modern`** — logging landing, road, pond, fence line, utility cut, terracing.

Never write "possibly", "may indicate", "could suggest" as a way of avoiding commitment.
Commit to a category and give the reasoning. If the evidence will not support a category,
say that, and say what additional observation would.

**One anomaly is not a finding.** A single circular rise is noise. Three on the same
terrace tread at consistent spacing, with a borrow area between them, is an argument.

## The false-positive checklist, applied individually

Do not write "natural causes ruled out." Name each and say why it does or does not fit:

| Looks like | Actually | Tell |
|---|---|---|
| Low mound + adjacent hollow | **Tree throw** | Paired, irregular, hollow is upslope-random; mound is diffuse. Very common in mature forest. |
| Circular depression | **Karst sinkhole** | Middle Tennessee is limestone. Sinkholes are abundant, often aligned on joints, and can be very regular. |
| Flat circular platform | **Log landing** | Modern, near a haul road, often cut-and-fill on a slope. |
| Linear parallel ridges | **Conservation terracing** | 1930s–50s soil conservation, follows contour, mechanically regular over long distances. |
| Rectilinear scar | **Building pad or foundation** | Sharp corners; natural processes rarely make right angles. |
| Straight-edged tonal band | **Flight-line seam** | Artefact of LiDAR acquisition, not ground. Runs the length of the tile. |
| Regular mound cluster | **Spoil heaps** | Associated with a cut or a quarry face. |

Rectilinearity and repetition are the strongest cultural signals **and** the strongest
modern signals. That ambiguity is the whole difficulty.

## Depth

- `references/feature-meanings.md` — every feature in the stack: what it measures, how it
  is computed, what it means archaeologically, and how it fails.
- `references/deep-time-context.md` — 13,000 years of Middle Tennessee occupation, and
  what each period would leave that this pipeline could or could not see.

Read the relevant reference before writing an interpretation. Do not paraphrase from
memory: the point of this skill is that the explanation is *correct*, not merely fluent.
