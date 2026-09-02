---
name: midden-scoring
description: >-
  Build, read, and tune midden's weighted-overlay suitability score. Use when writing or
  editing a weight set, normalising a feature, interpreting a low score, or validating
  weights against the control sites. Also use before treating any ranked output as a
  finding.
---

# Scoring and tuning

## What the score is, and is not

A weighted overlay of normalised landform and soils features. Not a probability, not a
classifier, and not fitted to known site locations — statistical site-prediction is
deliberately out of scope, because recorded site inventories are a biased sample of where
people *looked* and a surface fitted to them is functionally a treasure map.

Treat the output as a ranking of *where the landform is right*, and nothing more.

## Burial risk is a companion band, never a term in the sum

A cell can score low for two unrelated reasons: the landform is wrong, or anything there
is under three metres of overbank silt. Those are different findings and collapsing them
into one number destroys the only genuinely interesting distinction in the output.

`burial_risk` (alluvial parent material x flooding frequency) rides alongside the score as
a separate band. A low score with high burial risk is not a negative result — it is a
statement that LiDAR cannot see there.

## Never include distance to road

It correlates with the **survey record**, not with settlement. A model that includes it
learns "sites are near highways", which is a fact about archaeologists rather than about
the past.

## Normalisation

Every feature is scaled to 0-1 before weighting. The methods a weight set may name:

- `categorical` — an explicit value map, e.g. terrace class to a score.
- `inverse_linear` — full score at an optimum, decaying to zero at a falloff distance.
- `threshold_decay` — full score below a threshold, zero above a ceiling.

Weights are relative and normalised at runtime; they need not sum to 1.

## Tuning against controls, which is the whole validation loop

There is no ground-truth site dataset here. Published sites are the check, and they are
free, so run them on **every** parameter change.

`control_positive` — Mound Bottom and Castalian Springs. Major Mississippian centres on
public land, published for over a century. **If your stack does not rank their landform in
the top few percent, the weight set is falsified.** Not "needs a look" — falsified.

`control_detection` — Narrows of the Harpeth and Montgomery Bell. These validate the
*render chain*, not the score. The Montgomery Bell Tunnel is a large, precisely dated cut:
if negative openness does not show it, something is badly wrong. Montgomery Bell's relict
charcoal hearths are the fine check and are what should set `search_radius_m`.

`shakeout` — small, fast, and its scores are meaningless by design. Ignore them.

Tune against controls, never against a prospect. A prospect has no ground truth, so a
parameter tuned there is tuned to noise.

## Reading a ranked output

Rank tells you where to look, not what is there. Before reporting a candidate:

- Check `burial_risk` — is a negative even interpretable there?
- Check `ground_count` on the detection grid — is the surface measured or interpolated?
- Look at `openness_pos`, `openness_neg`, and `slrm` together; one surface is not enough.
- Ask what else ranks with it. A single high cell is a rounding artifact; a cluster on a
  terrace edge near a confluence is a reason to walk.

Report uncertainty as a category — `likely cultural`, `ambiguous`, `likely natural`,
`likely modern` — never as a hedge.

## Legal and ethical floor

Surface observation and remote sensing are unrestricted. Excavation and subsurface testing
require a permit under the Tennessee Antiquities Act. State site-file locations are
protected from public disclosure, and a predictive surface fitted on non-public sites is
itself a disclosure — model output inherits the sensitivity of its training data. Every
control this project uses is a published, mapped, historically marked site.
