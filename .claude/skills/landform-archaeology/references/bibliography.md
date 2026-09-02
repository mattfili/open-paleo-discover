# Bibliography

Sources behind the claims in this skill. Annotated with what each is actually useful for, so
you know which to open.

## Visualization technique

**Yokoyama, R., Shirasawa, M., Pike, R.J. (2002).** "Visualizing Topography by Openness: A New
Application of Image Processing to Digital Elevation Models." *Photogrammetric Engineering &
Remote Sensing* 68(3): 257–266.
→ The original definition of positive and negative openness. Go here for the maths and the sign
convention.

**Doneus, M. (2013).** "Openness as Visualization Technique for Interpretative Mapping of
Airborne Lidar Derived Digital Terrain Models." *Remote Sensing* 5(12): 6427–6442.
DOI: 10.3390/rs5126427
→ **The load-bearing citation for this skill.** Argues openness over SVF for archaeological
interpretation: no directional bias, no horizontal displacement, and the key point that SVF
delineates mainly concave features while openness delineates both. Also establishes that
negative openness is not the inverse of positive. Open access.

**Zakšek, K., Oštir, K., Kokalj, Ž. (2011).** "Sky-View Factor as a Relief Visualization
Technique." *Remote Sensing* 3(2): 398–415.
→ The SVF reference. Useful for understanding what you are choosing not to use, and the source
of the observation that openness is less "intuitive" because it does not show general
topography.

**Kokalj, Ž., Hesse, R. (2017).** *Airborne Laser Scanning Raster Visualization: A Guide to Good
Practice.* Ljubljana: Založba ZRC.
→ Open-access book from the RVT authors. The practical manual for choosing and parameterizing
visualizations. If you read one thing on technique, read this.

**Hesse, R. (2010).** "LiDAR-derived Local Relief Models — a new tool for archaeological
prospection." *Archaeological Prospection* 17(2): 67–72.
→ Origin of the local relief model approach that SLRM implements.

**Kokalj, Ž., Somrak, M. (2019).** "Why Not a Single Image? Combining Visualizations to
Facilitate Fieldwork and On-Screen Mapping." *Remote Sensing* 11(7): 747.
→ The VAT blend. Relevant if you want to compose a blended render.

**Challis, K., Forlin, P., Kincey, M. (2011).** "A Generic Toolkit for the Visualization of
Archaeological Features on Airborne LiDAR Elevation Data." *Archaeological Prospection* 18(4):
279–289.
→ Comparative evaluation of hillshade, openness, and SVF.

**Bennett, R., Welham, K., Hill, R.A., Ford, A. (2012).** "A Comparison of Visualization
Techniques for Models Created from Airborne Laser Scanned Data." *Archaeological Prospection*
19(1): 41–48.
→ Established that no single technique reveals all features, and that a combination is
necessary. The reason this skill specifies four renders rather than one.

## Charcoal hearths

The relict charcoal hearth literature is concentrated in the Pennsylvania and New Jersey iron
districts. Search terms: "relict charcoal hearth", "RCH", "LiDAR", "iron plantation". Work by
Raab, Johnson, and colleagues on Pennsylvania hearths is the usual entry point, and the German
literature on *Meilerplätze* covers the same feature class in Europe.

→ Useful for expected size distributions, cut-and-fill morphology on slopes, and spacing
statistics — the last of which is what lets you distinguish a hearth field from scattered
landings.

## Predictive modelling

**Kohler, T.A., Parker, S.C. (1986).** "Predictive Models for Archaeological Resource Location."
*Advances in Archaeological Method and Theory* 9: 397–452.
→ The foundational review. Old but still the clearest statement of what these models are and are
not.

**Verhagen, P., Whitley, T.G. (2012).** "Integrating Archaeological Theory and Predictive
Modeling." *Journal of Archaeological Method and Theory* 19(1): 49–100.
→ The main critique. Read it before defending any model.

**Wachtel, I., Zidon, R., Garti, S., Shelach-Lavi, G. (2018).** "Predictive modeling for
archaeological site locations: Comparing logistic regression and maximal entropy." *Journal of
Archaeological Science* 92: 28–36.
→ Practical comparison of the two standard approaches.

On **survey coverage bias**: the general problem is well covered in the CRM and sampling
literature. The short version — inventories reflect where survey happened, which reflects
development and land use, not past settlement. Any model trained on raw site inventories without
coverage correction learns the survey pattern.

On **site location confidentiality**: the argument that a high-resolution predictive surface
fitted on protected site data constitutes a disclosure of those locations is live and
well-argued. Search "archaeological predictive model" plus "site location confidentiality" or
"looting risk".

## Geomorphology and burial

**Waters, M.R. (1992).** *Principles of Geoarchaeology: A North American Perspective.* University
of Arizona Press.
→ Standard reference on alluvial site burial, terrace formation, and site formation processes.
The chapters on fluvial environments are directly relevant to why midden detection fails.

**Nobre Silva et al. and related work** on lidar visualization for geoarchaeological deposit
modelling in alluvial environments — see *Geoarchaeology* 37(1), 2022 (DOI 10.1002/gea.21959) for
a systematic evaluation of visualization techniques specifically in alluvial settings, including
the parameter table this skill's defaults are broadly consistent with.

## Regional context — Middle Tennessee

Primary sources are the Tennessee Division of Archaeology, the Tennessee Archaeological Society,
and *Tennessee Archaeology* (the state journal, largely open access). For Mississippian Middle
Tennessee specifically, the literature on Mound Bottom, Castalian Springs, and the Middle
Cumberland region is substantial and mostly published.

For iron-industry context in the Western Highland Rim, look for the Montgomery Bell and Cumberland
Furnace historical literature.

## Software

**WhiteboxTools** — Lindsay, J.B. Open core is GPL. Manual at whiteboxgeo.com. Openness and the
hydrology tools used here are open core; SkyViewFactor is in the paid Toolset Extension.

**RVT (Relief Visualization Toolbox)** — ZRC SAZU and University of Ljubljana. Not a dependency
of this project, but `rvt.vis` is pure numpy and the reference implementation for every technique
named above. Worth reading even if unused.
