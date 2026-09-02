# Glossary

Not filler. Each of these means something specific here and will otherwise drift between
skills and between conversations.

**AOI** — area of interest. Every fetch, derivation, and model run is scoped to one.
Seeded from the authoritative boundary service that owns the unit, never from a hardcoded
extent.

**Detection grid** — 0.5 m. Openness, SLRM, multidirectional hillshade. Exists for a human
or a model to *look at* and spot anomalies. Statistically meaningless, visually essential.
Requires the LiDAR point cloud; the fast 3DEP path cannot reach it.

**Modelling grid** — 10 m. Every predictive feature is resampled here. Fitting a model at
0.5 m produces noise and a feature matrix nobody can hold in memory. Middle Tennessee at
10 m is ~414 M cells; at 0.5 m it would be ~166 B.

**HAND** — Height Above Nearest Drainage. Elevation of a cell above the stream it drains
to, measured *along the flow path*, not as straight-line distance to the nearest water.
Computed from flow accumulated out of the surrounding catchment, which is why every AOI is
buffered before derivation.

**Terrace (T0 / T1 / T2)** — rivers cut downward over geologic time, abandoning old
floodplains as flat benches. T0 floods yearly, T1 rarely, T2+ is older and higher. T1 is
where sites are. Detected as low slope plus a discrete mode in the HAND histogram.

**Openness** — the mean angle to the horizon over many azimuths, in degrees.
*Positive* openness is high (>90) on **convex** ground: mounds, charcoal hearths, ridges.
*Negative* openness is high (>90) on **concave** ground: pits, ditches, relict channels,
cut earthworks. A flat plane is exactly 90 in both, whatever its slope — that is what
makes openness illumination-independent. Negative is **not** the inverse of positive: a
mound with a surrounding borrow ditch shows its top in positive and the ditch ring in
negative. Getting this backwards silently inverts every interpretation downstream.

**SLRM** — Simple Local Relief Model. The DEM minus a Gaussian-smoothed copy of itself.
Positive is locally high. Radius is in metres and sets what size of feature survives.

**Relict channel** — an abandoned river course, still faintly visible as a sinuous shallow
depression. Reads clearly in negative openness across a floodplain.

**Confluence** — where a tributary meets a main stem. Two water sources, two habitats, and
a travel node; a strong empirical predictor in the eastern US.

**Burial risk** — the chance that anything present is under metres of overbank silt,
derived from alluvial parent material and flooding frequency. Reported as a **companion
band and never summed into the score**, because a cell scores low either because the
landform is wrong or because a site there is buried, and those are different findings.

**Midden** — an occupation deposit: accumulated shell, bone, ash, and refuse. Most Archaic
shell-bearing sites in the Cumberland and Harpeth drainages are buried with no surface
expression, which is exactly why this project's primary output is a landform-and-soils
suitability surface rather than a feature detector.

**QL2** — a USGS LiDAR quality level, nominally 2 points per square metre. Pulse density
is not ground-return density: under canopy, far fewer returns reach the ground, which is
why every point-cloud DEM is written alongside a `ground_count` raster.

**Control** — a published, mapped site used to check the pipeline.
`control_positive` (Mound Bottom, Castalian Springs) falsifies a weight set: if the model
does not rank their landform highly, the weights are wrong. `control_detection` (Narrows
of the Harpeth, Montgomery Bell) validates the render chain. `shakeout` is a small AOI for
fast iteration whose scores are meaningless by design.

**Derivation** — one row in the provenance ledger: operation, tool, tool version,
parameters, inputs, git SHA. Opened before the work and closed after, so a crash leaves
evidence rather than silence.

**Variant** — a short digest of the parameters behind one raster. What makes a sweep
addressable: several assets at the same AOI, kind, and resolution that differ only by the
values that produced them.
