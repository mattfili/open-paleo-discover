# AOI brief — <name>

Fill this out before running anything. It takes ten minutes and it stops you from
spending a day rendering a golf course.

## Identity

- **Slug:**
- **Name:**
- **County:**
- **Managing agency:**
- **Role:** `prospect` | `control_positive` | `control_detection` | `shakeout`
- **Area (km²):**
- **Boundary source:** (authoritative service, not a hand-drawn box)

## Physiography

- **Province:** Central Basin / Highland Rim / other
- **Main drainage:**
- **Karst?** If yes, expect sinkholes as the dominant circular anomaly and treat
  flow-accumulation output in the uplands with suspicion.
- **Terrace development:** does this AOI actually have a terraced valley, or is it
  dissected upland? Determines whether HAND-based terrace extraction is meaningful here.

## Land-use history — the part that determines your false-positive load

- **Forest history:** mature/unlogged (expect dense tree throws), logged (expect stumps,
  skid trails, landings), or open?
- **Cultivated?** Plowing flattens mounds and erases middens. A plowed AOI needs the
  detection grid more than the suitability surface.
- **Industrial history:** iron, quarrying, mining? Iron districts mean charcoal hearths
  and ore pits — which is good for detection controls and noisy for everything else.
- **Modern earthmoving:** golf courses, ponds, borrow pits, graded lots, utility
  corridors, impoundment?
- **Impoundment:** is any of this AOI in a reservoir drawdown zone? If so, the historical
  topographic quad is not optional.

## Data

- **LiDAR project and year:**
- **Nominal point density / quality level:**
- **Canopy cover at acquisition:** leaf-on acquisitions give sparser ground returns
- **Historical quads available (editions):**
- **Historical aerials available (years):**

## Expectations, written down before you look

State these in advance. It is the only defence against seeing what you hoped to see.

- What features would you expect here if the landform model is right?
- What would falsify that?
- What is the dominant false-positive class you will have to argue against?

## Findings

- Terrace extraction: HAND modes found, threshold used
- Detection review: see `anomaly-log.md`
- Suitability: control percentile if applicable
- Burial risk summary:
