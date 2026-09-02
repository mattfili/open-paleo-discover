# Feature catalog

What things look like in relief visualization, and — more importantly — what they are usually
not.

**Read the false positives section first.** In forested Middle Tennessee terrain, natural and
modern features outnumber archaeological ones by something like three orders of magnitude. The
skill being practised here is mostly elimination.

---

# False positives

## Tree throw (windthrow) mound-and-pit

**The single most common false positive in forested LiDAR.** Learn this one cold.

- **Form:** A paired pit and mound. The root plate levers out of the ground, leaving a pit, and
  the soil on the plate drops beside it as a mound.
- **Size:** 2–5 m across, 0.3–1 m relief.
- **Signature:** Adjacent bright and dark blobs in SLRM, always paired, always asymmetric.
- **Distribution:** Random in position and orientation. Density scales with forest age — mature
  unlogged stands are carpeted with them.
- **How to dismiss:** The pairing is the tell. A pit *and* a mound, touching, at small scale. An
  archaeological mound does not come with a matching pit immediately beside it (a borrow ditch
  is a ring or an arc, not a single adjacent hole). If you see hundreds across an AOI in random
  orientation, they are tree throws.

Expect Radnor Lake and Beaman Park to be dense with these.

## Log landing

**The dangerous one, because it mimics a charcoal hearth.**

- **Form:** Flat cleared circular-to-irregular platform where logs were stacked for loading.
- **Size:** 20–40 m — larger than a hearth.
- **How to distinguish from a hearth:** Landings are bigger, less regular in outline, and
  *connected* — a skid trail network converges on them and they sit at the end of a haul road.
  Hearths are smaller (8–15 m), more circular, and sited by proximity to timber and furnace, not
  by road access. Trace the connections before deciding.

## Skid trails and logging roads

- **Form:** Linear, often braided, following contours and converging downhill.
- **Signature:** Shallow linear depressions in negative openness, faint parallel sets.
- **Note:** Historic haul roads and modern skid trails look similar. Age is not readable from
  form alone; check historical aerials and quads.

## Karst sinkhole

**The dominant natural circular anomaly in Middle Tennessee.** The Central Basin and Highland
Rim are karst.

- **Form:** Closed circular to elliptical depression, funnel or pan shaped.
- **Size:** 3 m to hundreds of metres.
- **Signature:** Strong high negative openness, deep negative SLRM.
- **How to distinguish from an ore pit or cellar hole:** No spoil. Excavation produces a pile;
  dissolution does not. Sinkholes also cluster along bedding planes and fracture traces, giving
  an alignment that follows geology rather than human logic, and often show internal drainage.

Cedars of Lebanon will be full of these.

## Stump hole and stump mound

- 1–3 m, circular, very common in previously logged ground. Too small to be an archaeological
  feature at the scales of interest, but numerous enough to clutter a render at a tight SLRM
  radius.

## Agricultural terracing

- **Form:** Contour-parallel benches at regular spacing, often with a raised outer lip.
- **Origin:** 20th-century soil conservation practice, extremely common on Highland Rim slopes.
- **How to dismiss:** Regularity. Natural terraces are irregular in width and spacing;
  conservation terraces are evenly spaced and follow contour with machine precision. They also
  stop abruptly at property lines.

## Bedrock structure

- Differential erosion of horizontal limestone and shale beds produces natural benches that can
  read as terraces, and jointing produces linear features that can read as walls.
- **How to dismiss:** Continuity across the landscape at a consistent elevation, and alignment
  with regional structural trend rather than with drainage or human access.

## DEM artifacts

- **Flight-line seams:** Perfectly straight linear features crossing an entire tile at the flight
  heading. Nothing archaeological is that straight over that distance.
- **Interpolation artifacts:** Smooth blobby patches in areas of low ground-return density —
  dense canopy, water, dense understory. Look for correlation with canopy cover.
- **Removal scars:** Buildings and bridges removed during classification leave flat patches or
  odd pits.
- **Tile edge mismatch:** Step discontinuities along tile boundaries where projects meet.

## Modern earthmoving

Golf courses, ponds, borrow pits, road cuts, utility corridors, building pads, septic fields,
graded house lots. All produce clean geometric anomalies. Check current and historical aerials
before spending any thought on a geometric feature near modern development.

---

# Archaeological features

## Charcoal hearth (relict)

**The best detection control available, and a genuine target in iron districts.**

- **Form:** Flat circular platform. On level ground, a slight raised disc. On slopes, built by
  cut-and-fill — the upslope side is cut into the hill and the downslope side is a fill lobe,
  giving a distinctive lens or "D" shape.
- **Size:** 8–15 m diameter, 0.2–0.5 m relief.
- **Signature:** Circular positive anomaly in SLRM with a flat interior; a bright ring edge in
  positive openness.
- **Distribution — this is the identifier:** Hearths cluster. Charcoal was made within economical
  hauling distance of a furnace, so a working district contains dozens to hundreds, typically
  50–200 m apart, concentrated on slopes within a few kilometres of the furnace site.
- **Confusion:** Log landings (see above). Size and connectivity separate them.

Montgomery Bell State Park sits in a 19th-century iron district and should have these.

## Mississippian platform mound

- **Form:** Flat-topped, rectangular to sub-rectangular, sometimes with a ramp on one side.
- **Size:** 20–80 m at the base, 1–8 m high. Large ones are unmistakable.
- **Setting:** Terrace surfaces near main-stem rivers, usually in a plaza arrangement with other
  mounds. **The site plan is the strongest identifier** — a single isolated rectangular rise is
  much more likely to be natural or modern than a mound; a set of rises arranged around an open
  flat area is not.
- **Detection difficulty:** Easy when intact. Hard when plowed down — a century of cultivation
  can reduce a 2 m mound to 0.3–0.8 m of residual relief with softened edges.

## Woodland burial mound

- Conical rather than flat-topped, 5–25 m diameter, 0.5–3 m high. Often on ridge tops and bluff
  edges rather than terraces, which distinguishes their setting from Mississippian mounds.
- Easily confused with natural knolls. Look for regularity of form and, again, clustering.

## Earthwork enclosure

- Ditch-and-bank enclosures, geometric or following terrain.
- **Signature:** This is where rendering both openness signs pays off — the bank shows in
  positive openness, the ditch in negative, and together they outline the feature cleanly where
  either alone would be ambiguous.

## Shell midden

**Be honest about this one.**

- **Form:** Low convex lens of accumulated shell and refuse.
- **Size:** Tens of metres across, 0.5–1.5 m above the surrounding floodplain when it survives.
- **Setting:** Cutbanks, point bars, terrace edges along major rivers.
- **Detection difficulty: high to impossible.** Most are buried under overbank alluvium, eroded
  by channel migration, or plowed flat. Many were destroyed by 19th and 20th century shell
  mining. When one is visible it is a subtle convex lens easily confused with a natural point-bar
  ridge.
- **Practical consequence:** Do not treat midden absence in a LiDAR render as evidence of
  absence. This is exactly what the burial risk band exists to communicate.

## Historic house site / farmstead

- **Form:** Rectangular depression (cellar hole), 3–6 m, often with an associated chimney fall
  mound, plus linear features — fence lines, lanes, field boundaries.
- **Signature:** Sharp rectangular negative anomaly. Rectangularity at small scale is a strong
  cultural indicator; nature rarely produces clean right angles at 4 m.
- **Best cross-reference:** Historical topographic quads mark structures. A cellar hole where an
  1890s quad shows a building is confirmed with near-certainty.

## Ore pit

- 2–8 m irregular depression **with an adjacent spoil mound**. The pit-and-mound pairing
  distinguishes it from a sinkhole, which has no spoil.
- Clusters along outcrop contours, giving an elevation-following alignment.

## Cemetery

- Rows of small regular depressions, sometimes with a low enclosing wall or fence line. Regular
  spacing and alignment in rows is the tell.
- Historic family cemeteries are common on Middle Tennessee farmsteads and frequently
  unrecorded. Treat any suspected burial ground with appropriate care and report rather than
  investigate.

## Mill site, ford, ferry

- **Form:** Race and dam alignments, cut banks, approach cuts on both sides of a channel.
- **Why they matter disproportionately:** A river crossing is a crossing regardless of period.
  Fords are frequently multi-component, with material spanning millennia at the same spot,
  because the reason to cross there does not change. A historic mill or ford marked on an old
  quad is one of the highest-value prospecting targets available.

---

# Classification discipline

Assign every anomaly one of four categories. Do not hedge in prose.

| Category | Meaning |
|---|---|
| `likely cultural` | Form, scale, setting, and spatial pattern all consistent; natural and modern explanations considered and rejected |
| `ambiguous` | Consistent with a cultural origin but a natural or modern explanation cannot be excluded |
| `likely natural` | Best explained by a geomorphic or biological process |
| `likely modern` | Best explained by 20th-century land use |

Most anomalies are `likely natural` or `likely modern`. If your log is mostly `likely cultural`,
you are being too generous — go back through the false-positive list.

Log candidates with `../templates/anomaly-log.md`.
