---
name: holocene-geomorphology
description: >
  Deep-time companion to landform-archaeology: when Middle Tennessee's
  surfaces formed, how fast floodplains bury things, terrace chronology,
  karst evolution. Use when justifying the burial-risk band's values, when
  reasoning about which terrace was occupiable in which period, when
  interpreting HAND modes as landforms with ages, or when a class's
  detectability depends on sedimentation (midden, open_habitation).
---

# Holocene geomorphology — surfaces have ages, and ages gate the record

`landform-archaeology` covers what landforms look like; this skill covers
*when they existed and what has happened to their surfaces since*. Burial
risk, terrace occupiability, and the meaning of a HAND mode are all
chronology claims, and chronology claims cite.

**Verification note (G2):** written from model knowledge of standard works;
verify before a methods appendix. *[unverified]* marks uncertain details.

## The load-bearing local source

Brakenridge's Duck River work is the closest thing Middle Tennessee has to
a dated alluvial template: Holocene alluvial fills and terraces on a
Central Basin river, radiocarbon-dated, showing that the modern floodplain
is a young (late Holocene) construction and that low terraces carry
early-to-mid Holocene surfaces.

- Brakenridge, G.R. 1984. Alluvial stratigraphy and radiocarbon dating
  along the Duck River, Tennessee: implications regarding flood-plain
  origin. *GSA Bulletin* 95. *[verify volume/pages]*

Consequences the model already half-encodes:

1. **T0 (the active floodplain) is definitionally late Holocene at
   surface.** Anything older than a few centuries on it is *in* it, not on
   it. This is why `flood_freq` anchoring beats mode counting — T0 is the
   surface that floods, whatever ordinal position its HAND mode holds — and
   it is the sourced footing for the burial-sensitivity gating of `midden`
   and `open_habitation`.
2. **The lowest non-flooding terrace (T1) is the archaeological prize**:
   old enough to carry Archaic surfaces, low enough for the
   floodplain-and-water catchment. Its HAND height varies by reach — 3 m on
   one river, 11 m on another — which is exactly why ordinal mode position
   failed at mound-bottom vs castalian-springs.
3. **Age increases upward, but preservation of *surface visibility* does
   not**: high terraces are old but eroded and plow-truncated; the record
   there is lithic scatter, not stratified deposit. A proxy-class
   suitability hit on T2+ predicts a different *kind* of record than the
   same hit on T1 — say this when explaining scores.

## Burial rates — the numbers behind the band

Overbank sedimentation in Holocene alluvial valleys of the mid-continent
runs from ~0.1 mm/yr on stable distal floodplain to centimetres per year
near channels and post-settlement. Two anchors:

- Ferring, C.R. 1986. Rates of fluvial sedimentation: implications for
  archaeological variability. *Geoarchaeology* 1(3). (The variability
  argument: burial is reach- and position-specific, not a valley constant.)
- **Post-settlement alluvium (PSA)** — 19th–20th century deforestation and
  row-cropping deposited decimetres to metres of legacy sediment across
  much of the eastern US; on Middle Tennessee floodplains, a precontact
  surface can lie under a metre of historic sediment *deposited since
  1800*. This is the single strongest reason a floodplain "low score /
  nothing visible" is an absence-of-evidence finding. General treatments:
  Waters 1992; Holliday 2004; the Happ/Trimble legacy-sediment literature.
  *[regional PSA thickness for the Cumberland basin specifically:
  unsourced — treat as a gap to close, portage-style]*
- Waters, M.R. 1992. *Principles of Geoarchaeology*. Arizona.
- Holliday, V.T. 2004. *Soils in Archaeological Research*. Oxford.

Rule already in CLAUDE.md, now with its footing: burial removes `midden`
and `open_habitation` from floodplain consideration and does nothing to
`rockshelter` — because the process is overbank deposition, which reaches
neither bluff-base overhangs nor upland hearth platforms.

## Karst — the C2 footing

Middle Tennessee limestone (Ordovician on the Basin floor, Mississippian on
the Rim) dissolves along joints; sinkholes, springs, and cave entrances are
the surface expression, and the karst drainage does not respect surface
watersheds. Three project-relevant facts:

1. **Closed depressions are real landforms here, not DEM noise** — the
   breach-don't-fill invariant's geological justification.
2. **Sinkholes and springs are persistent-place attractors**: reliable
   water on an otherwise dry karst upland, plus shelter (cave entrances)
   and mineral resources (saltpeter, chert in residuum). C2's distance
   bands have the same catchment logic as the river features.
3. **Sinkhole age is mostly unknowable from LiDAR** — a depression may
   postdate the occupation it appears to attract. State this when
   explaining a karst-feature score.

- White, W.B. 1988. *Geomorphology and Hydrology of Karst Terrains*.
  Oxford.
- Crawford, N.C. — Tennessee/Kentucky karst hydrology studies (Western
  Kentucky University). *[specific citation to be selected when C2 is
  built]*

## Chert — the C4 footing

Fort Payne (Mississippian-age, Highland Rim) and Bigby-Cannon/Ordovician
cherts (Central Basin) are the regional toolstone sources; Fort Payne chert
in particular moves far from outcrop, so `dist_to_chert_outcrop_m` is a
*production-site* predictor (quarries, workshops) more than a
*habitation* predictor. Encode it as a hard constraint for `chert_quarry`
(the class cannot occur off-outcrop) and a weak band for habitation.
Sources: Tennessee Geological Survey surficial/bedrock mapping for outcrop
extents; Amick, D.S. on Fort Payne chert procurement in the mid-South
*[unverified — locate the specific paper when C4 is built]*.

## When were which periods on which surfaces — the one-paragraph version

Paleoindian and Early Archaic surfaces are deeply buried in alluvium or
deflated on uplands; Middle–Late Archaic occupations are the oldest
commonly preserved on T1 treads and in rockshelters; Woodland and
Mississippian sit on T1/T0-margin surfaces shallow enough for LiDAR-visible
architecture (mounds) where not plowed flat. Historic-period features
postdate all alluvial surfaces and are the only classes reliably *on* the
modern floodplain surface. This ordering — not any single date — is what
the per-class `burial_sensitivity` column encodes.
