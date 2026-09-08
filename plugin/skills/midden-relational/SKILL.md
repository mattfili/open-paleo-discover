---
name: midden-relational
description: >-
  Read and reason about midden's detection results using the relational principle:
  a property is not evidence, a relationship is. Use when interpreting why a class
  detects well or badly, when asked whether something could be found in LiDAR, when
  a proxy or invisible class is involved, or when proposing what to look for next.
---

# Relational evidence — what midden measured, and what it means for an answer

Middle Tennessee ground is textured everywhere: tree throws, gullies, karst,
20th-century earthmoving. Anything a detector calls "unusual" is common here. midden
measured this three times with negative controls before finding the way out.

| what the rule asks | recall | background fires | verdict |
|---|---|---|---|
| is this cell extreme (amplitude) | 12/12 | 94-100% | uninformative |
| is this blob the right shape | 6/6 | 97% | uninformative |
| are the parts regularly arranged | 0/6 | 16% | quiet but blind |
| **do two things pair** (pit + spoil) | **2/4** | **11%** | **informative** |
| **does a boundary close** (cemetery plot) | **3/9** | **4%** | **informative** |

**A high percentile is not a finding.** When you report a detection, say what
RELATION supports it, not how extreme it was. "Fires at p99" describes most of the
landscape; "a concave cluster that closes around a plot-sized interior" does not.

## Answering "could X be found in LiDAR?"

Ask three questions in order, and answer honestly at the first failure:

1. **Scale.** The detection grid is 0.5 m. Artifacts, flakes, and surface scatters
   are centimetres — never visible, at any tuning. Say so plainly.
2. **Expression.** Does the thing deform the ground surface at all? Middens, buried
   habitation, and stone-box cemeteries largely do not: they are declared `proxy` in
   `ref.target_class`, and a detection run for them is refused by the tool, on
   purpose. A proxy result is never reported as a detection.
3. **Association.** If 1 or 2 fails, the thing may still be *argued for* by a
   detectable landform it sits beside — the chain is
   `invisible evidence -> visible context -> detectable landform`. Worked material on
   a dry gravel channel is the worked example: the flakes cannot be seen, the channel
   can, and in Middle Tennessee gravel bars carry chert, so the same landform argues
   for both a camp and a raw-material source.

`ref.target_class` carries **context classes** for exactly this — `relict_channel`
is the first. They are detectable landforms whose purpose is evidence for another
class. Use `midden_class_brief` to see a class's detectability, its parameters, its
known confusers, and its latest recall-vs-background numbers before saying anything
about what it can find.

## When a class detects badly

Do not reach for a higher threshold; that is the failure already measured. Ask which
relation the morphology implies and whether the parts are resolvable at 0.5 m — the
grave-scale rule failed precisely because individual graves do not resolve in forest,
while the plot boundary around them does. Misses that reach p99.8-100 and still fail
are gate problems, not threshold problems.

## Reporting discipline

Every recall number in this project ships with a background fire rate from matched
null discs; quote both or neither. A hit is a candidate for the confuser ledger
(`ref.confuser`), not a find — one anomaly is not a finding, and the classification
categories are `likely cultural`, `ambiguous`, `likely natural`, `likely modern`.
