# Reading and tuning detection renders

## Sign convention — read this before anything else

This is the most common error in the whole domain and it fails silently.

| | Convex feature (mound, hearth platform, ridge) | Concave feature (pit, ditch, channel, valley) | Flat plane |
|---|---|---|---|
| **Positive openness** | **High** (> 90°) | Low (< 90°) | 90° |
| **Negative openness** | Low (< 90°) | **High** (> 90°) | 90° |

On a flat plane both equal 90° *regardless of slope*. That is the property that makes openness
illumination-independent and free of directional bias, and it is why openness outlines features
without the horizontal displacement that hillshade introduces.

**Negative openness is not the inverse of positive openness.** They carry different information.
A mound with a surrounding borrow ditch shows the mound top in positive openness and the ditch
ring in negative openness. Rendering both is how you get the full outline of a feature — which
is precisely Doneus's argument for openness over SVF.

If your renders look inverted from what this table says, you have swapped the output bands. Fix
that before interpreting anything.

## Why openness and not sky-view factor

SVF is the better-known technique and the wrong default here.

SVF quantifies the visible portion of the sky hemisphere, weighted by solid angle. That
weighting suppresses features close to horizontal, and the practical consequence is that **SVF
delineates mainly concave features**. Ditches and hollows show well; low convex features show
poorly.

The primary targets in this project — mounds, platforms, charcoal hearths — are convex. Using
SVF means choosing the technique with a known bias against the thing you are looking for.

Openness delineates both concave and convex, carries no directional bias, and introduces no
horizontal displacement of feature edges. Doneus (2013) proposed it for exactly this reason.
Later comparative work found no meaningful gap in automatic-extraction success rates between the
two, so there is no accuracy cost to the switch.

Practical bonus: openness is in WhiteboxTools open core. SVF is in the paid Toolset Extension.

## The standard render set

Four rasters at 0.5 m for every detection AOI:

| Render | Purpose |
|---|---|
| Positive openness | Convex features. Primary mound and hearth layer. |
| Negative openness | Concave features. Pits, ditches, relict channels, cellar holes. |
| SLRM | Local relief, scale-tunable. Best all-round single layer for scanning. |
| Multidirectional hillshade | Context and legibility. Not for detection — for orientation. |

Scan SLRM first because it is the most legible at a glance, then confirm anything interesting
against both openness bands. A real feature is usually visible in at least two of the three.

## Parameters and what they do

### Openness search radius

Expressed in **cells, not metres**, in WhiteboxTools. At 0.5 m resolution, a radius of 20 cells
is a 10 m search — roughly the diameter of one charcoal hearth.

The search radius sets the scale of feature the render is sensitive to. Too small and everything
looks like noise; too large and small features are swamped by regional relief.

Rule of thumb: set the radius to roughly the size of the feature you are hunting. For hearths
and small mounds at 0.5 m, 20–40 cells. For large earthworks, 60–100. Render more than one
radius; features have characteristic scales and a two-radius pair separates them.

### SLRM smoothing radius

```
slrm = dem - gaussian_filter(dem, sigma=radius_m / resolution_m)
```

- 10 m radius — small features and a lot of noise. Tree throws dominate.
- 15 m — good default for hearth-and-small-mound scale.
- 25 m — larger features, small ones smoothed away.

**The NoData trap.** NaN propagates through a Gaussian kernel. Any NoData hole will grow by the
kernel radius and eat outward, and the AOI edge will develop a soft halo that looks like a real
broad anomaly. Fill or mask NoData before smoothing, then reapply the mask. This is not a subtle
artifact — it has been mistaken for archaeology.

### Stream extraction threshold

Not a visualization parameter but it belongs in the same sweep, because it governs HAND and
therefore terraces. See `landform-model.md`.

## Tuning discipline

**Tune on a control, never on a prospect.** Pick a location where you know what is there, sweep
the parameter, and choose the value that resolves the known feature most cleanly. Then apply it
to prospects unchanged.

Tuning on a prospect means adjusting parameters until an ambiguous blob looks more like what you
hope it is. That is not tuning; it is generating the answer you wanted. It is also very easy to
do without noticing.

Good controls, in ascending order of difficulty:

1. **A large cut earthwork** — a tunnel, a canal, a railway cut. Coarse check: if this does not
   show, something is badly broken.
2. **Charcoal hearths in an iron district** — 8–15 m circular platforms, clustered. This is the
   real test, because it is at the same scale as the features you actually care about. **If your
   renders resolve hearths, they will resolve a low mound. If they do not, no amount of tuning
   elsewhere will help.**
3. **A plowed-down mound** — 0.3–0.8 m residual relief. The hardest realistic target.

## Contrast and stretch

Openness and SLRM both have narrow useful ranges surrounded by outliers. A linear stretch across
the full data range will render as flat grey.

Use a percentile clip — 2nd to 98th is a reasonable start, tighter for SLRM. Set the stretch
once per AOI and hold it constant while comparing parameter sweeps, or you are comparing
stretches rather than parameters.

For SLRM specifically, a diverging colour ramp centred on zero reads better than greyscale:
positive relief one colour, negative the other, zero neutral. The eye picks up the sign
immediately.

## Blending

RVT's VAT (Visualisation for Archaeological Topography) is a standardized blend designed for
this task and it is genuinely good. It is not available without RVT, but the idea is portable: a
multiply blend of an illumination-independent layer over a hillshade at modest opacity gives
both feature legibility and terrain context in one image.

If you want it, compose it yourself: multidirectional hillshade as base, positive openness
multiplied over it at ~25% opacity. Do not treat a blended image as a measurement — blends are
for the eye, analysis runs on the single-band rasters.

## What a good render looks like

You should be able to see the drainage network, individual tree-throw mounds in mature forest,
and modern features like roads and building pads. If tree throws are invisible, your renders are
too smoothed to find a plowed mound either. Their visibility is a useful sensitivity check —
annoying as they are as false positives, they prove the render is working.
