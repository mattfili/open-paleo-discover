# What every feature means

For each: what it physically measures, how midden computes it, why it is in an
archaeological model, and how it fails. Read the relevant entries before interpreting.

---

## HAND — Height Above Nearest Drainage (`hand_m`, metres)

**Physically.** How far a cell sits above the stream it actually drains to, measured
*along the flow path* rather than as straight-line distance to the nearest blue line. A
cell 20 m from a creek but draining away from it over a divide has a large HAND, correctly.

**Computed.** Breach depressions (never fill — see below) → D8 flow pointer → flow
accumulation → threshold to extract a stream network → elevation above that network.
WhiteboxTools, on the 10 m modelling grid.

**Why it is in the model.** HAND is the best single proxy for two things people cared
about simultaneously and in tension: *access to water* and *freedom from flooding*. Low
HAND means water is close and the walk is short; it also means the ground floods. The
whole terrace argument is a statement about HAND.

**How it fails.** Everything depends on `flow_accum_threshold`, which decides what counts
as a stream. Too high and small drainages vanish, so HAND is measured against a distant
main stem and reads far too large. Too low and every hillside rill becomes a stream, so
HAND collapses toward zero everywhere. It is the single most consequential parameter in
the project. HAND is also wrong near the edge of any computed extent, which is why every
AOI is buffered by 2 km before the hydrology runs.

**Breach, never fill.** `fill_depressions` raises every pit to its spill elevation. In
karst — which is most of Middle Tennessee — closed depressions are real landforms, and in
this domain they may be the target. Filling destroys them silently.

---

## Terrace class (`terrace_class`, 0–4)

**Physically.** Rivers cut downward over geologic time and abandon their old floodplains as
flat benches stepping up from the modern channel. T0 is the active floodplain, flooding
most years. T1 is the first abandoned surface, flooding rarely. T2 and above are older and
higher.

**Computed.** Low slope plus a discrete mode in the HAND histogram. Cells within
`hand_mode_tolerance_m` of an ascending mode, with slope at or below `max_slope_deg`, take
that mode's index.

**Why it is in the model.** **T1 is where sites are**, and this is one of the most robust
generalisations in eastern North American settlement archaeology. T1 is flat, well drained,
close to water, and above the annual flood. Its alluvial soils are deep and workable —
which matters enormously once Woodland horticulture and then Mississippian maize
agriculture arrive. T0 floods: occupations there are scoured away or buried. T2 and above
are further from water and often carry thinner, older soils.

**How it fails — and it currently does.** The class is an **ordinal of HAND modes, not a
geomorphic identification**. "Class 2" means second-lowest mode. It does not mean T1. At
`mound-bottom` the mound complex sits nearest the *third* mode; at `castalian-springs` the
histogram has only two modes at all. A weight set that scores class 2 as the target is
therefore scoring the wrong surface at some AOIs. See `ROADMAP.md` — this is the known
cause of the falsified weight set, and the proposed fix anchors the labelling to SSURGO
flooding frequency instead of to mode counting.

Also: fewer than two modes usually means the stream threshold is wrong for that landscape —
but a dissected upland with only headwater streams genuinely has no low terrace, and that
is a real result rather than a failure.

---

## Slope (`slope_deg`, degrees)

**Physically.** Steepest rate of elevation change, from the conditioned DEM.

**Why it is in the model.** Habitable ground is flat. This is not subtle and it is not
culturally specific: you cannot comfortably sleep, cook, store, or build on a steep slope,
and you do not choose to when flat ground is available nearby. Below about 3° is
comfortable; past about 12° it is not living space.

In midden's current controls, slope is one of the two features doing most of the actual
discriminating.

**How it fails.** At 10 m it is an average over a 10 m cell, so it will not see a small
flat platform cut into a hillside — exactly the kind of construction that indicates
effort and therefore significance. That is a detection-grid question, not a modelling-grid
one.

---

## Distance to stream (`dist_to_stream_m`, metres)

**Physically.** Euclidean distance to the nearest NHDPlus HR flowline, computed on the
modelling grid.

**Why it is in the model.** Water is the first constraint on settlement: drinking,
cooking, transport, and aquatic food. But *immediately* adjacent is floodplain, so the
scoring uses an optimum with a falloff rather than "closer is always better" — full score
at roughly 150 m, decaying to zero by about 1200 m.

**Why from NHD rather than the derived stream raster.** The WhiteboxTools stream raster is
whatever `flow_accum_threshold` says is a stream. A distance measured against it would move
every time that knob moved, which would make the feature un-comparable between runs. NHD is
published hydrography and holds still.

**How it fails.** Modern hydrography is not past hydrography. Rivers migrate, and three
mid-twentieth-century impoundments — Percy Priest, Old Hickory, Cheatham — drowned large
stretches of the Cumberland floodplain. A cell that is now 50 m from a reservoir may have
been 2 km from water when it was occupied, or may be under it. Relict channels visible in
the detection renders are the direct evidence of this.

---

## Distance to confluence (`dist_to_confluence_m`, metres)

**Physically.** Distance to the nearest junction of two flowlines of different Strahler
order.

**Why it is in the model.** Confluences are among the strongest empirical predictors in
eastern North American settlement models, and the reason is ecological rather than
mystical. A junction gives you two water sources, two aquatic resource zones, and — because
habitat diversity concentrates at boundaries — an ecotone. It is also a travel node: rivers
are the highways, and a confluence is an interchange. Mound Bottom and Castalian Springs
are both positioned with respect to drainage junctions.

**How it fails.** The naive definition counts *any* intersection of two flowline records,
including where two consecutive reaches of the same river meet end to end. Those are
reach breaks, not confluences, and at one AOI they were 38 of 94 "confluences." midden's
feature stack filters on `order_minor >= 2 AND order_minor < order_major` — a genuine
tributary junction joins a smaller stream to a larger one. Note that `ref.confluence`
itself still contains the unfiltered set.

---

## TWI — Topographic Wetness Index (`twi`, unitless)

**Physically.** `ln(specific contributing area / tan(slope))`. High where a lot of upslope
area drains into a flat place: hollows, swales, valley bottoms. Low on steep, convex,
shedding ground.

**Computed.** WhiteboxTools `wetness_index`, from a specific-contributing-area raster and a
slope raster in degrees. Not from a DEM — handing it a DEM is a silent failure that
produces plausible nonsense.

**Why it is in the model, at low weight.** It catches locally wet ground that slope and
drainage class miss. It carries weight 0.5 deliberately, because it partly restates both.

**How it fails.** In midden's controls the site cells score *worse* on TWI than the
background. That is not necessarily an error: a well-drained terrace tread should be
drier than its surroundings, so a feature built to reward wetness will penalise it. Watch
for whether this is signal or a sign the feature is pointing the wrong way.

---

## Drainage class (`drainage_class`, SSURGO phrase)

**Physically.** SSURGO's dominant-condition soil drainage class — "Well drained",
"Somewhat excessively drained", "Moderately well drained", "Somewhat poorly drained", and
so on. A statement about how long water stands in the soil profile.

**Why it is in the model.** Dry feet. Well-drained soil is workable, storable, and
habitable; poorly drained ground is seasonally wet and was not chosen for occupation when
alternatives existed. It also proxies for soil workability, which matters once people are
cultivating.

**How it fails.** In the current AOIs it barely discriminates — the soils around these
control sites are almost uniformly well drained, so the feature separates nothing. That is
a property of these particular places, not a defect, but it means the 1.5 weight is
currently buying very little. SSURGO is also mapped at survey scale: a map unit is a
generalisation over an area, not a measurement at a point.

---

## Burial risk (`burial_risk`, 0–1) — **companion band, never scored**

**Physically.** Alluvial parent material × flooding frequency. 1.0 means alluvium that
floods frequently; 0.0 means residuum that does not flood.

**Why it exists.** It is what makes a negative result interpretable, and it is arguably the
most intellectually important band in the project. Archaeological visibility is not evenly
distributed: in an aggrading alluvial setting, sites are *buried*, sometimes several metres
down. Absence of surface or LiDAR evidence there is uninformative.

This also biases what is already known. Our picture of Archaic settlement in these
drainages is skewed toward places where sites happen to be visible, which means toward
eroding and stable surfaces and away from aggrading ones. A model trained or validated
naively against the known record inherits that bias.

**Why it is never summed into the score.** Adding it would produce a single number in which
"wrong landform" and "invisible landform" are indistinguishable, destroying the only
genuinely useful distinction the output has.

---

## Openness, positive and negative (degrees) — **detection grid, 0.5 m**

**Physically.** The mean angle to the horizon over many azimuths. *Positive* openness looks
upward and is high where the horizon falls away — convex ground. *Negative* openness looks
downward and is high where the ground rises around you — concave. A flat plane reads
exactly 90° in both, **whatever its slope**, which is what makes openness
illumination-independent.

| | High (>90°) means | Look for |
|---|---|---|
| `openness_pos` | **convex** | mounds, charcoal hearths, platforms, ridges, roadbeds |
| `openness_neg` | **concave** | pits, ditches, borrow areas, relict channels, cut earthworks |

**Negative openness is not the inverse of positive.** Doneus is explicit about this, and it
matters practically: a mound with a surrounding borrow ditch shows its top in positive and
the ditch ring in negative, and *that pairing* is far more diagnostic than either alone.
Natural processes rarely produce a discrete rise with a discrete adjacent pit.

**Feature shape decides which surface carries the signal.** A smooth mound reads strongest
at its summit in positive openness. A flat-topped platform — which is what a charcoal
hearth is — reads only as a thin bright rim in positive, while negative openness darkens
across the whole disc. On a synthetic 10 m hearth the rim contrast is about +0.85° positive
against −1.9° negative. Check both before concluding nothing is there.

**Why openness rather than sky-view factor.** Doneus (2013) proposed it specifically for
interpretive mapping of archaeological DTMs: no directional bias, no horizontal
displacement of features, and — the deciding point — SVF delineates mainly *concave*
features while openness delineates both. Mounds, platforms and hearths are convex.

**How it fails.** Radius sets what size of thing you see: 5–10 m for hearths and small
mounds, 15–25 m for platforms and larger earthworks. Too large and you are measuring the
landform rather than the feature on it. Canopy pits — small dark speckles — are pervasive
in forest and are individual trees, not features.

---

## SLRM — Simple Local Relief Model (`slrm`, metres) — **detection grid**

**Physically.** The DEM minus a Gaussian-smoothed copy of itself. Positive is locally high
relative to its surroundings. Removes regional topography so metre-scale relief is visible
on a hillside.

**Why it is in the model.** It is the most legible surface for subtle relief and the best
first look for earthworks and channel scars.

**How it fails.** NaN propagates through a Gaussian kernel and will eat the edges and every
nodata hole, so the surface must be filled before smoothing and re-masked after. The
smoothing radius sets the scale: 10 m finds small features and noise, 25 m finds large
features and smooths small ones away.

---

## Multidirectional hillshade — **context only, never detect from it**

Shaded relief from several illumination azimuths. It exists so a reader can orient
themselves. Do not identify features from it: single- and few-azimuth illumination hides
anything whose orientation is unlucky, which is the entire reason the detection set is
openness and SLRM.

---

## Ground count (`ground_count`) — **a data-quality band, not a terrain band**

Number of classified ground returns per cell. Zero means the elevation there is
*interpolated*, not measured.

Check this before interpreting anything on the detection grid. Under canopy at QL2, 0.5 m
is often optimistic and 1 m honest. An apparent feature in a zone with no ground returns is
an artefact of the interpolation, not a thing on the ground.

---

## The suitability score (`score`, 0–1)

**What it is.** A weighted sum of the normalised features above. A ranking of *where the
landform has the properties people preferred*.

**What it is not.** Not a probability. Not a detection. Not fitted to known sites — and
deliberately so, because a surface fitted to real site locations is functionally a treasure
map, and because the known record is a biased sample of where people *looked*.
`dist_to_road` is excluded for exactly this reason: it predicts where archaeologists have
been, not where people lived.

**How to report it.** Always with its companion bands, always with the control result, and
always as a ranking rather than a probability. A weight set that has not been checked
against the controls is a hypothesis nobody has tested.
