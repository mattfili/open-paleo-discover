# Glossary

One definition per term. If a term drifts between two meanings anywhere in the project, this
file is the arbiter.

## Terrain

**DEM / DTM** — Bare-earth digital elevation model. In this project always ground-classified
returns only (LAS classification 2), never first-return surface.

**HAND** — Height Above Nearest Drainage. Vertical distance from a cell to the stream cell it
drains to, following the flow path. Not the same as height above the nearest stream in
straight-line distance. The basis for terrace identification.

**Terrace** — An abandoned floodplain surface, left as a flat bench when a river cut downward.
Numbered upward from the active floodplain: T0 floods annually, T1 floods rarely, T2 and above
are older and higher. Computationally: low slope plus a discrete mode in the HAND histogram.

**T0 / T1 / T2** — See terrace. T1 is where sites concentrate: flat, drained, close to water,
above the annual flood.

**Relict channel** — An abandoned river course, visible as a sinuous shallow depression on a
floodplain. Also called a paleochannel or, when a closed loop, an oxbow.

**Confluence** — Where a tributary meets a main stem. Two water sources, two habitat zones, a
natural travel node. One of the strongest single predictors in eastern US site models.

**TWI** — Topographic Wetness Index. `ln(a / tan β)` where `a` is upslope contributing area per
unit contour length and β is slope. High values mean water accumulates. Proxy for drainage.

**Slope** — Steepest descent gradient. Reported in degrees throughout this project, never
percent. Habitable ground is generally under 3–5°.

**Karst** — Terrain formed by dissolution of soluble bedrock, producing sinkholes, springs, and
caves. The Central Basin and Highland Rim of Middle Tennessee are karst. This matters because
sinkholes are the dominant natural circular anomaly in the region.

**Alluvium** — Sediment deposited by flowing water. Overbank alluvium accumulates on
floodplains during floods and is the mechanism that buries sites beyond the reach of LiDAR.

**Burial risk** — Derived indicator combining alluvial parent material and flooding frequency.
Answers "would a site here be visible if it existed?" Kept as a separate band from the
suitability score, never summed into it.

## Visualization

**Hillshade** — Simulated illumination from a single sun position. Directional bias hides
features whose orientation is unlucky. Not used for detection in this project.

**Multidirectional hillshade** — Hillshade blended across several azimuths. Removes most
directional bias. Good for context and legibility, weaker than openness for subtle features.

**SVF (Sky-View Factor)** — Proportion of the sky hemisphere visible from a point, within a
search radius. Illumination-independent. Delineates mainly concave features. Not used here;
openness is preferred. See `visualization-guide.md` for why.

**Openness** — Mean horizon angle over N azimuth directions within a search radius
(Yokoyama et al. 2002). Two signs:
- **Positive openness** — mean of zenith angles. High on convex features (ridges, mounds,
  hearth platforms). Above 90° means convex.
- **Negative openness** — mean of nadir angles. High on concave features (pits, ditches, valley
  bottoms). Above 90° means concave.
On a flat plane, both equal 90° regardless of slope. Negative openness is *not* the inverse of
positive openness; they carry different information and both are rendered.

**SLRM (Simple Local Relief Model)** — DEM minus a low-pass-filtered DEM. Removes regional
topography and leaves local relief. Positive values are locally high, negative locally low.
Sensitive to the smoothing radius, which sets the size of features it reveals.

**LRM / MSRM** — Local Relief Model and Multi-Scale Relief Model. Related to SLRM with more
sophisticated trend removal. Not used in this project; SLRM is sufficient and is three lines.

**Local dominance** — How much a location dominates its surroundings from an observer height.
Good for low, broad features. Available in RVT, not in WhiteboxTools open core.

**Detection grid** — 0.5 m rasters used for visual anomaly review. Statistically meaningless,
visually essential.

**Modeling grid** — 10 m rasters used for the predictive surface. All features resampled here.

## Archaeology

**Midden** — An accumulated refuse deposit: shell, bone, ash, fire-cracked rock, artifacts.
Shell middens along rivers in the mid-South are typically Archaic. Often has little or no
surface expression and is frequently buried, which is why this project does not treat midden
detection as its primary goal despite the name.

**Mound** — A deliberately constructed earthen feature. In the mid-South usually Mississippian
platform mounds (flat-topped, rectangular, sometimes ramped) or Woodland burial mounds
(conical). Mounds are the easiest archaeological feature to detect in LiDAR.

**Archaic** — Roughly 8000–1000 BC in the mid-South. Riverine, seasonally mobile. Shell middens
and shell-bearing sites date to this period.

**Woodland** — Roughly 1000 BC–AD 1000. Pottery, horticulture, conical burial mounds.

**Mississippian** — Roughly AD 1000–1500. Maize agriculture, platform mounds, palisaded towns,
plaza-and-mound site plans. Mound Bottom and Castalian Springs are Mississippian.

**Paleoindian** — Before roughly 8000 BC. Rare, usually deeply buried or in special contexts.
Not a realistic remote-sensing target and not what this project is about, despite the repo name.

**Charcoal hearth (relict)** — A flat circular platform, roughly 8–15 m across, where wood was
converted to charcoal for iron smelting. Ubiquitous in 19th-century iron districts. On slopes
they are built by cut-and-fill, giving a distinctive lens shape. The canonical
LiDAR-detectable feature class and an excellent detection control.

**Ore pit** — Shallow extraction pit, 2–8 m across, usually with an adjacent spoil mound.
Clusters along ore-bearing outcrop contours. The pit-and-mound pairing is the identifier.

**Site file** — A state's inventory of recorded archaeological sites. Restricted from public
disclosure in most states.

**Survey coverage** — Polygons recording where archaeological survey has actually been
conducted, regardless of whether anything was found. Distinct from, and more useful for
modelling than, the site file alone.

**Presence-background modelling** — Fitting a model with known site locations as presences and
randomly sampled cells as pseudo-absences. Standard in species distribution modelling; adopted
for archaeological prediction. Requires site data this project does not have.
