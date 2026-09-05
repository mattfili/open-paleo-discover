---
name: survey-design
description: >
  Sampling theory and detection-probability reasoning for turning a score
  surface into a defensible survey plan — F2, the product differentiator.
  Use when building F1/F2 (ranked polygons, survey optimisation), when
  computing recall for A2's vanished-feature test, when setting tolerance
  radii for hit/miss calls, or when anyone asks how many person-days a
  polygon list is worth.
---

# Survey design — discovery is a probability, not a walk

F2 promises "given N person-days: which polygons, in what order." That is
an optimisation over *expected discoveries per unit effort*, and every term
in it — detection probability, site size, obtrusiveness, coverage — has a
sampling literature. Without it, F2 is a TSP solver wearing an archaeology
hat.

**Verification note (G2):** standard works cited from model knowledge;
verify before a methods appendix. *[unverified]* marks uncertain details.

## The core decomposition

Expected discoveries in a polygon =
(probability the polygon contains a target) ×
(probability the survey method intersects it) ×
(probability the crew recognizes it when intersected).

The score surface only estimates the first term. The second is geometry —
transect spacing vs. target diameter (a 10 m hearth is invisible to 30 m
spaced transects roughly two passes out of three). The third is
obtrusiveness and surface visibility — a stone-box cemetery reads from
metres away in winter woods; a plowed-down lithic scatter requires shovel
tests. **These multiply.** A high-score polygon surveyed with the wrong
method contributes near-zero expected discoveries, and the plan must show
that arithmetic rather than hide it.

- Banning, E.B. 2002. *Archaeological Survey*. Kluwer. (The synthesis —
  intersection vs. discovery probability, sweep widths.)
- Banning, E.B., Hawkins, A. & Stewart, S.T. 2006. Detection functions for
  archaeological survey. *American Antiquity* 71(4). *[unverified issue]*
- McManamon, F.P. 1984. Discovering sites unseen. *Advances in
  Archaeological Method and Theory* 7. (Obtrusiveness/visibility framing.)

## Shovel-test math, because most of this landscape is forested

For subsurface classes (all the proxy classes), discovery runs through
shovel-test grids, and the numbers are sobering and citable: intersection
probability for a 20 m site on a 30 m grid is well under 1, and *artifact
recovery given intersection* cuts it again (density-dependent). The
literature to cite when a client asks why the plan costs what it costs:

- Krakker, J.J., Shott, M.J. & Welch, P.D. 1983. Design and evaluation of
  shovel-test sampling in regional archaeological survey. *Journal of
  Field Archaeology* 10.
- Nance, J.D. & Ball, B.F. 1986. No surprises? The reliability and
  validity of test pit sampling. *American Antiquity* 51.
- Shott, M.J. 1989. Shovel-test sampling in archaeological survey:
  comments on Nance and Ball, and Lightfoot. *American Antiquity* 54.
  *[unverified year/volume]*

Direct-detectability classes invert this: for `mound_earthwork` or
`charcoal_hearth` the LiDAR *is* the survey instrument, fieldwork is
verification of ranked candidates, and the per-candidate cost is minutes,
not grid-days. The plan should therefore route direct classes and proxy
classes differently — verification runs vs. discovery grids — and say so.

## Tolerance radii and recall (A2) — the same math, run backwards

The vanished-feature test is a detection-probability experiment with the
roles reversed: labels are ground truth, the detection chain is the survey
method, and recall = discoveries / labels. Rules:

1. **Tolerance radius = label positional confidence + half expected
   feature size**, per class, recorded in the validation output. Not a
   convenience number — it is the disc the label actually occupies (see
   `spatial-validation` §2).
2. **Report misses with as much care as hits.** A mapped mill with no
   detectable race or abutment is a real negative: either the feature was
   destroyed (dated by later map editions — say which), it is below the
   detection floor (state the floor), or the chain failed (the finding).
   Distinguishing those three is the report.
3. **Recall stratified by class and sheet scale**, never pooled: 12.2 m
   labels and 31.8 m labels are different experiments.

## Effort allocation — the actual F2 objective

With per-polygon expected-discovery estimates, allocation under an N
person-day budget is a knapsack/ordering problem, and two honest
constraints from sampling theory apply:

- **Diminishing returns within a polygon**: expected *new* discoveries fall
  as coverage rises; visiting the 3rd-ranked polygon usually beats
  saturating the 1st. Adaptive cluster sampling (Thompson 1990, *JASA* 85)
  is the formal version — allocate a reconnaissance pass, then concentrate
  where hits occur.
- **The plan must buy information, not only sites**: reserve a fraction of
  effort (10–20%) for low-score cells matched on access — the only way the
  survey can *falsify* the model rather than confirm it. A plan that only
  visits top-ranked polygons can never learn the model is wrong, which is
  survey bias manufacturing its own validation. This line item goes in the
  plan explicitly, labeled as the control sample.
- Orton, C. 2000. *Sampling in Archaeology*. Cambridge.

## Access bias, again, at plan time

Routing on `travelling_salesman_problem` over road access will
preferentially verify near-road candidates, feeding B4's measured bias
forward into the label set the plan produces. Report the planned polygons'
distance-to-road distribution against the candidate pool's before the plan
ships — the same statistic as B4, applied to the plan instead of the
model.
