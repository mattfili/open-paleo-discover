# Deep time in Middle Tennessee

What happened here over roughly thirteen thousand years, what each period would leave
behind, and — the part that matters for interpretation — **whether this pipeline could
possibly see it**.

Dates are approximate and conventions vary; treat them as orientation, not authority. Where
a claim is contested, say so rather than smoothing it over.

---

## The land first

Two physiographic provinces, and every AOI sits in one of them. Knowing which changes what
you should expect.

**The Central Basin** is an eroded structural dome — the top was worn off, leaving a low
basin ringed by higher ground. Ordovician limestone, often close to the surface. Soils are
fertile but can be thin, and where bedrock is shallowest you get **cedar glades**: open,
rocky, drought-stressed plant communities with a distinctive flora. Nashville, the lower
Harpeth, and the Cumberland's middle course are all here.

**The Highland Rim** surrounds the basin at higher elevation, on Mississippian-age
limestone and chert. It is dissected — deep hollows, steep slopes, headwater streams
rather than broad floodplains. `beaman-park` is Highland Rim; almost everything else in the
seeded set is Central Basin river valley. That contrast is the point of including it.

**Karst runs through both.** Sinkholes, caves, springs and losing streams are everywhere.
This matters twice over: springs were a primary settlement attractor, and sinkholes are an
inexhaustible source of circular depressions that look like features and are not.

**Chert matters.** The limestones here carry high-quality chert — Fort Payne, St. Louis and
others. Stone tool raw material was abundant and good, which is one reason this region is
so densely occupied so early.

---

## Paleoindian, roughly 13,500–11,700 years ago

Small, highly mobile groups at the end of the Pleistocene, in a landscape that was cooler
and more open than today.

**Middle Tennessee is genuinely exceptional for this period.** The Cumberland and Tennessee
drainages are among the densest concentrations of Paleoindian material in eastern North
America — the **Cumberland point**, a fluted form, is named for the river. The combination
of abundant high-quality chert, springs, and river corridors is the usual explanation.

**What it leaves.** Lithic scatters. Occasionally a quarry or workshop at a chert source.
Sometimes material at springs and sinkholes, where animals and people both concentrated.

**Can this pipeline see it? No.** Nothing here has topographic expression. Worse, thirteen
thousand years of alluviation means river-margin Paleoindian material is often deeply
buried — which is precisely the situation `burial_risk` exists to flag. If a landform
scores low and burial risk is high, the honest statement is that the method is blind there,
not that nothing is present.

---

## Archaic, roughly 11,700–3,000 years ago

The long middle, and the period the project is named for.

As the climate warmed and modern forests established, subsistence broadened from
large-game hunting toward a wide spectrum: deer, turkey, nuts, fish, and — increasingly —
**freshwater mussels**. By the Late Archaic, riverine adaptation is intensive, and along
the major rivers of the mid-South this produces **shell-bearing middens**: accumulated
shell, bone, ash, fire-cracked rock and refuse, built up over generations of repeated
occupation at the same favoured spot.

A midden is an occupation deposit. It is the single most informative thing an eastern
Archaic site can contain, because the shell buffers soil acidity and preserves bone and
plant remains that would otherwise be gone.

Late Archaic also sees the first cultivation in the region — the **Eastern Agricultural
Complex** of native domesticates: chenopod, maygrass, erect knotweed, sumpweed, squash.
This is independent domestication, not introduction, and it is the beginning of the tie
between settlement and workable alluvial soil that drives everything afterwards.

**What it leaves.** Middens. Hearths. Burials. Lithic and ceramic-free artefact scatters.
Occasionally shell mounds with real topographic relief.

**Can this pipeline see it? Almost never, and this is the central limitation.** Most
Archaic sites in the Cumberland and Harpeth have no surface expression, and many are metres
deep in alluvium. **This is why midden produces a landform suitability surface rather than
a feature detector, and why the project is named for a deposit it largely cannot see.**

A shell mound large enough to have topographic expression is the exception, and would show
as a convex anomaly in positive openness.

---

## Woodland, roughly 3,000–1,000 years ago

Pottery, more sedentism, and the first constructed earthworks.

Burial mounds appear — conical earthen mounds over interments, a fundamentally different
proposition archaeologically because they are *built* and therefore visible. Middle
Tennessee sits between better-known traditions: **Copena** in the Tennessee Valley to the
south, and locally the **Owl Hollow phase** in the Middle Woodland of this region, with its
distinctive keyhole-shaped structures.

Horticulture of the Eastern Agricultural Complex intensifies. Settlement ties more firmly
to alluvial terraces.

**What it leaves.** Burial mounds, habitation sites, middens, ceramics.

**Can this pipeline see it? Sometimes.** A burial mound that survives ploughing has
topographic expression and should read as a convex anomaly in positive openness —
circular, a few metres to tens of metres across, with no adjacent borrow pit necessarily.
Ploughed-down mounds may survive only as soil marks, which LiDAR will not see but
historical aerial photography sometimes does.

---

## Mississippian, roughly AD 1000–1450

Maize agriculture, hierarchy, and monumental construction. This is the period both of
midden's `control_positive` sites belong to.

Intensive maize farming supports far larger and more permanent settlements. Society becomes
hierarchical — chiefdoms. Towns are laid out around **platform mounds**: flat-topped
earthen pyramids supporting structures for elites and ritual, often around a plaza, often
palisaded.

The **Middle Cumberland region** was densely settled. `mound-bottom` in the Harpeth valley
is a major mound complex; `castalian-springs` in Sumner County is another, and both are
published, mapped and historically marked. The regionally diagnostic mortuary form is the
**stone-box grave** — a burial in a box of limestone slabs, which the local geology makes
easy.

Then, around AD 1450–1475, the Middle Cumberland is **depopulated**. The broader pattern
across the central Mississippi and lower Ohio valleys is sometimes called the "Vacant
Quarter." Why is genuinely contested — climate, warfare, resource depletion, political
collapse have all been argued. Do not present a single cause as settled.

**What it leaves.** Platform and burial mounds, plazas, palisade lines, borrow pits,
house basins, dense middens, stone-box cemeteries.

**Can this pipeline see it? Yes — this is what LiDAR is good at.** Platform mounds are
large convex features. Borrow pits, from which the mound fill was dug, are concave and
usually nearby. Palisade lines may survive as low linear ridges or ditches. **The
mound-plus-adjacent-borrow-pit signature is the most diagnostic thing in this whole
method**, because natural processes do not produce a discrete rise beside a discrete pit.

This is exactly why Mound Bottom and Castalian Springs are the controls: if the predictive
stack cannot rank their landform highly, something upstream is broken.

---

## Historic, late 1700s onward

Euro-American settlement, and then industry.

**The iron district** matters directly here. Early-nineteenth-century Middle Tennessee had
a substantial charcoal-iron industry, and Montgomery Bell was its central figure. Iron
production consumed enormous quantities of charcoal, and charcoal was made on site at
**relict charcoal hearths**: flat circular platforms roughly 10 m across, cut into slopes,
where wood was slowly carbonised under earth cover.

These are the canonical success story of LiDAR archaeology — they show beautifully in
relief visualisations in the iron districts of Pennsylvania and New Jersey — and they sit
at almost exactly the scale of the prehistoric features this project cares about. **That is
why `montgomery-bell` is the control that should set the openness search radius: if the
detection grid resolves hearths, it will resolve a low mound.**

The **Montgomery Bell Tunnel** at the Narrows of the Harpeth, cut around 1819 to divert
river water to power a forge, is the coarse control: a large, unambiguous, precisely dated
cut through a ridge. If negative openness does not show it, something is badly wrong.

**The reservoirs matter too.** Percy Priest, Old Hickory and Cheatham flooded large
stretches of the Cumberland floodplain in the mid-twentieth century. Modern topography does
not show what was there; historical topographic quadrangles do, which is why they are on
the roadmap.

---

## What this means for how you write

**Say which periods a landform could plausibly hold, and which it could not.** A
well-drained T1 terrace near a confluence is a good candidate for essentially every period
from Archaic onward. A steep Highland Rim hollow is not, for any of them.

**Be explicit that the visible record is biased toward the recent and the constructed.**
Mississippian mounds are visible; Archaic middens mostly are not; Paleoindian scatters
never are. A ranking is therefore not a statement about all of prehistory equally.

**Never state a site's period from topography alone.** A circular rise is a form, not a
culture. Period attribution needs artefacts, stratigraphy, or dates, and none of those come
from a DEM.

**Keep the legal and ethical floor in view.** Surface observation and remote sensing are
unrestricted. Excavation and subsurface testing require a permit under the Tennessee
Antiquities Act. State site-file locations are protected from public disclosure, and a
predictive surface fitted on non-public site data is itself a form of disclosure — model
output inherits the sensitivity of its inputs. Every control this project uses is a
published, mapped, historically marked site, which is what keeps the validation loop
self-contained and publishable.
