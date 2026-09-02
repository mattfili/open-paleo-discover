# The landform model

Why each feature is in the model, what it proxies for, and how it fails.

## The underlying claim

People chose where to live, and the criteria were stable enough over millennia to be modelled:
flat, well-drained ground, close to fresh water, above the annual flood, near the boundary
between two or more resource zones, and on a natural travel route.

Every feature in the stack is a computable proxy for one of those. None of them is a proxy for
"there is a site here" — they are proxies for "a person choosing a camp would have liked this
spot." That distinction governs how results should be read.

## Terraces

**The concept.** A river cuts downward over geologic time. Each time base level drops, the old
floodplain is abandoned and left as a flat bench above the new channel. The result is a
staircase of surfaces of increasing age and height.

**Why it predicts.** T1 — the first bench above the active floodplain — is flat, drained, close
to water, and floods rarely. It is overwhelmingly where sites are. T0 sites get scoured or
buried. T2 and above are older surfaces and can hold older material, but are further from water
and often have thinner soils.

**How to compute.** A terrace is low slope plus a discrete, repeating height band above the
drainage network:

1. Hydrologically condition the DEM (breach, do not fill — see below).
2. Flow pointer, flow accumulation, extract streams at a threshold.
3. HAND: elevation above nearest drainage, following flow paths.
4. Histogram HAND within the AOI. Terraces appear as modes.
5. Mask to slope below ~3°, polygonize, label T0/T1/T2 by ascending HAND mode.

**Breach, do not fill.** Depression filling raises pits to their spill elevation, which
destroys exactly the small closed depressions you may care about and distorts HAND near them.
Least-cost breaching carves a drainage path instead. Use breaching.

**How it fails.** The whole chain hangs off the stream-extraction threshold:

- *Threshold too high* → few streams → HAND measured to a distant channel → terrace bands smear
  together → histogram is unimodal.
- *Threshold too low* → every swale becomes a stream → HAND compressed toward zero everywhere →
  no modes at all.

The diagnostic is the histogram itself. **If HAND is unimodal within an AOI that visibly has
terraces, the threshold is wrong.** Sweep it before doing anything else; nothing downstream is
meaningful until the histogram has structure.

**Regional note.** In karst terrain — most of the Central Basin and Highland Rim — surface
drainage is discontinuous. Streams sink and resurface. Flow accumulation over a karst DEM
produces confident nonsense in places, and HAND inherits it. Treat terrace extraction in karst
uplands with suspicion; it works well in the main-stem river valleys and poorly on the
dissected plateau.

## Confluences

**Why it predicts.** Two water sources, two habitat zones, a natural node in a travel network,
and good fishing. Empirically one of the strongest single predictors in eastern US site models.

**How to compute.** Self-intersection of the hydrography network, then buffer. See
`../scripts/confluence_extract.sql`.

**How it fails.** Modern hydrography is not ancient hydrography. Channels migrate, and reservoir
construction has drowned or beheaded confluences across the mid-South. Where a historical
topographic quad exists showing pre-impoundment drainage, prefer it — the confluence that
mattered may be under sixty feet of water or, in a drawdown zone, exposed and walkable.

Also: not all confluences are equal. A first-order tributary joining a first-order tributary is
not a node. Weight by stream order.

## Relict channels

**Why it matters.** Two uses, and they are different. A site sitting on a relict channel bank
was waterfront when that channel was live, which is a dateable relationship. Separately, the
presence of relict channels tells you the floodplain is aggrading — which means sites there are
*buried*, not absent.

**How to compute.** Sinuous linear negative relief in SLRM and high negative openness. Look for
continuity and meander geometry; a randomly-shaped depression is not a channel.

## Burial risk

**This is the feature that makes negative results interpretable, and it is the one most often
omitted.**

A cell can score low for two reasons that have nothing to do with each other:

1. The landform is genuinely unsuitable. Steep, wet, far from water.
2. The landform is fine but any site there is under metres of overbank alluvium and no
   surface-based method will ever see it.

Collapse these into a single score and you have destroyed the only genuinely useful distinction
in the output. Keep burial risk as a separate band, reported alongside the score, never summed
into it.

**How to compute.** From soil survey attributes: alluvial parent material combined with flooding
frequency. In SSURGO the relevant columns are `drainagecl` (drainage class), `flodfreqdcd`
(flooding frequency, dominant condition), and parent material in the component tables.

High burial risk plus low suitability means "we cannot say." High burial risk plus high
suitability means "this is a good spot and it may well have a deeply buried site that geophysics
or coring would be the right tool for." Those are useful things to be able to say.

## Soils

Beyond burial risk, drainage class carries direct predictive weight. Well-drained to moderately
well-drained soils are habitable; poorly drained and very poorly drained are not, and were not.
Depth to bedrock matters in karst uplands where thin soils over limestone are common.

Soil survey is mapped at a coarse scale — map units are generalized and boundaries are
approximate. Do not treat a SSURGO polygon edge as a real line on the ground. It is a
regionalization, useful at 10 m modelling resolution and misleading at 0.5 m.

## Land cover and canopy

Not a predictor of past settlement. It is a predictor of *data quality*: dense canopy means
fewer ground returns, which means a noisier bare-earth DEM and worse detection. Carry canopy
percentage in the stack so that a weak detection result in heavy forest can be distinguished
from a weak result in an open field.

## Features deliberately excluded

**Viewshed and cost-distance.** Popular in the literature, expensive to compute, and weakly
supported at this scale. Viewshed in particular assumes a vegetation history nobody has, and
the results are usually a restatement of elevation and slope. Left out on purpose.

**Aspect.** Frequently included, rarely earns its place in the eastern US where the seasonal
argument for south-facing slopes is much weaker than in mountainous or high-latitude settings.
Compute it, do not weight it heavily without evidence.

**Distance to modern roads.** Never include this. It correlates with the *survey* record, not
the archaeological record, and it is the single fastest way to build a model that predicts where
archaeologists have already looked.

## What a weight set is worth

A weighted overlay is an expression of a hypothesis, not a measurement. Its value comes entirely
from whether it ranks known sites highly. A weight set that does not put Mound Bottom and
Castalian Springs in the top few percent of their AOIs has been falsified and should be
discarded, not defended. See `../scripts/control_check.py`.
