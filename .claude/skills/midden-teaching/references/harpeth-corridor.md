# The lower Harpeth corridor, taught

The stretch from Mound Bottom down past the Narrows to Hidden Lake and Kingston Springs,
Cheatham County. Three midden AOIs sit on it (`mound-bottom`, `harpeth-narrows`,
`harpeth-hidden-lake`). This is the worked example for the teaching style: first the
geology-forward reading, then the same ground read for the people.

Verified against data in this repo where stated. Dates are orientation, not authority.

---

## The setting, in one paragraph

Middle Tennessee is a bowl inside a bigger bowl. Three hundred million years ago the rocks
under Nashville were pushed up into a dome; domes erode from the top, and once rivers cut
through the resistant cap they stripped out the softer, older limestone beneath. The dome's
centre is now a low basin (the **Central Basin**, floor 150-200 m) and its rim still stands
100-200 m higher all round (the **Highland Rim**). The lower Harpeth runs along the western
edge of that boundary. **The USGS State Geologic Map Compilation puts the Narrows neck and
Hidden Lake on Silurian limestone and shale (Wayne, Brownsport and Decatur units) with the
Mississippian Fort Payne chert on the uplands either side** -- the river has cut down through
the chert into older rock. This is why one province label per AOI is too coarse here, and
why `sources/sgmc_geology.yml` exists.

## The Narrows: geology-forward

**Strahler order 6.** Stream order counts generations of equal merging: two order-1 streams
make a 2, two 2s make a 3, and a 1 joining a 3 leaves it a 3. Order 6 here means
**1,785 km^2 of catchment above the upstream channel at the neck and 1,811 km^2 at the
downstream one** (NHDPlus HR `totdasqkm`, read at the neck 2026-09-04; the earlier figure of
~1,130 km^2 in this file was wrong). It is why the
confluence feature only counts junctions where the *smaller* stream is order 2 or more, and
why 41 order-6-meets-order-6 "confluences" in `ref.confluence` are reach breaks, not
junctions.

**Incised meander.** A river on a floodplain wanders sideways and its bends migrate. A river
forced to cut *down* faster than it can wander (base level dropped, land rose) carves its
bends into bedrock and they lock in place. The Harpeth inherited its loops on a gentle
surface and cut them into limestone as the Basin was excavated. On a floodplain the river
would eventually breach the neck in a flood and leave an oxbow; in rock it cannot, so the
loop persists.

**Five miles around, a hundred metres across.** Measured 2026-09-04 along the NHD
centreline between the two closest approaches: **8.221 km (5.11 miles) around, 118 m centre
to centre** at the neck. Published accounts range from four miles (Tennessee Encyclopedia)
to five and a half (ASCE); the Encyclopedia's "one-hundred-yard-wide rock ridge" is bank to
bank. The neck is a ridge with 35 m of relief (10 m 3DEP along the neck line: 128.75 m at the
lower channel, 164.1 m on the crest -- 35.4 m; consistent with the earlier 0.5 m figures). Slope
scores it near zero; terrace class is 0 for three quarters of the park unit; median HAND is
21 m. That is correct: nobody lived on the neck.

**The tunnel.** Around the loop the river drops 16-17 feet by the published accounts;
the 3DEP water surface at the two neck channels differs by **4.49 m (14.7 ft)**, which is the
DEM's indirect read of the same head (it sees water surface, not bed). In 1819 Montgomery Bell had
enslaved workers drill and blast a tunnel 290 ft long, about 8 ft high and 15 ft wide,
through the neck, and dropped that head onto the wheels of Pattison Forge. First full-scale
water-diversion tunnel in the United States; National Historic Landmark. In the detection
rasters the cut reads as a 50 m body of negative openness above 96 degrees across a crest
that otherwise sits at 75-83 degrees, with a dark saddle in SLRM splitting the ridge. What
LiDAR sees is the surface expression of the approach cuts and collapsed cover, not the bore.
Category: likely modern (1819), by rectilinearity across a natural ridge.

**Inside the loop.** Nested concentric bright arcs in negative openness along the inner
bank are meander scroll bars: swales between successive point-bar ridges left as the
channel migrated outward. They are the physical proof that the modern NHD flowline is not
the past shoreline, and the reason `dist_to_stream_m` from modern hydrography is a
first-order approximation.

**Data quality.** `ground_count` shows a straight horizontal band across the AOI where
return density halves: a flight-line seam, single coverage between two overlapping swaths.
Any straight feature parallel to it is acquisition geometry. Median 2 ground returns per
0.5 m cell at the neck, so 1 m is the honest resolution there.

## The same ground, read for the people

**The Basin as a reason people were here.** Springs everywhere from the limestone, two big
rivers, deep alluvium on every floodplain, nut mast, mussel beds, and premier tool stone
(Fort Payne and St. Louis cherts) on the Rim a day's walk away. That combination is why the
Cumberland drainage names a Paleoindian fluted point (the Cumberland point, roughly 12,500
years old) and why fluted-point density here rivals anywhere on the continent. Basin
terraces hold the long-occupied base camps, shell middens and later towns; Rim hollows hold
hunting camps, rockshelters and chert quarries. midden's score is good at the first kind
only.

**Order 6 as a resource index.** An order-1 branch is drinking water. An order-3 creek has
fish and a floodplain to camp on. An order-6 river is a highway for dugouts, a permanent
mussel fishery, deep farmable soil, and, at every tributary junction, an overlap of two
resource sets. Mound Bottom, 8 km upstream, and Castalian Springs are both
junction-and-terrace positions.

**The loop as a fortress the river half-built.** A meander loop is a flat alluvial
peninsula nearly surrounded by water with one narrow land approach. Mound Bottom (roughly
AD 950-1300, at least 29 platform and burial mounds, several thousand people, an estimated
five miles of palisade and embankment) sits in exactly such a horseshoe bend. A loop is
also a sediment trap: every overtopping flood lays silt on its floor, so an Archaic camp
there can be two metres down. That is `burial_risk`, and it is why "nothing visible" on a
loop floor means "cannot see", never "nobody was here".

**The neck as a portage.** Anyone travelling by canoe could carry across the neck in
minutes and skip 5.5 miles of paddling. Places where a portage is obvious get used for
thousands of years and accumulate things: dropped and cached tools, hearths at the
landings, and in this region rock art, which clusters at river-bluff landmarks (Mace Bluff
near Mound Bottom is the local example). The neck is a *node in a travel network*, not a
place to live. The score is right to rank the ridge low; the archaeology is at the base of
the bluff, at the two landings, and under any overhang. This is the argument for a
`dist_to_portage_m` feature: see ROADMAP "Not built".

**Height sorts kind of site.** T0 (HAND under a metre) floods yearly; anything there is
scoured or buried. T1 (about 4 m at Hidden Lake) is where people slept, cooked, and from
about 3,000 years ago gardened chenopod, maygrass, sumpweed and squash, then maize. T2
remnants and bluff shoulders hold burial mounds and cemeteries rather than houses;
Mississippian stone-box graves (limestone slab boxes, the diagnostic burial form of the
Middle Cumberland) cluster on well-drained terrace edges overlooking the towns. Bluff crests
are overlooks, and where the rock is Fort Payne, quarries. So a 35 m ridge is not empty of
meaning; it is a different category of place.

**The historic layer as a ruler.** Everything prehistoric the pipeline could see is a
convex feature metres to tens of metres across. The tunnel is a large, dated, concave cut.
If it did not show in negative openness, no claim about a 1 m mound would be worth
anything. It does show. The finer ruler, still unrun, is the charcoal-hearth field at
Montgomery Bell State Park: flat 10 m platforms cut into hillsides for the same forges, at
almost exactly the size and relief of a ploughed-down Woodland burial mound.

## Hidden Lake, briefly (2026-09-02 field brief)

Ninety-acre unit east of the Narrows; former quarry and resort, so expect 20th-century
earthmoving beside real terrace. The south-east of the unit is one T1 bench about 4 m above
the Harpeth (NHD-referenced HAND modes 0.38 / 3.88 / 9.88 m). Three patches clear the 99th
percentile of the surrounding 2 km. The one on Armour silt loam (no mapped flooding, burial
risk 0) is where the surface is worth reading; the two on Arrington silt loam (occasionally
flooded alluvium, burial risk 0.7) are where the landform is right and anything on it is
under silt, so the cut bank of the order-2 tributary between them is the only window.
Details in `exports/hidden-lake/`.

## The Narrows ranked for habitation (2026-09-04)

Run outside Postgres in a cloud container over a 41.4 km^2 window at 10 m, NHD-referenced
HAND, `weights/default.yml` unmodified. HAND modes 0.38 / 4.12 / 11.38 m -- the same three-bench
structure as Hidden Lake, and here the threshold-referenced modes agree (0.38 / 4.12 / 11.12),
unlike Hidden Lake.

The park unit is bimodal and averaging it describes neither half: median cell at the 7.6th
percentile of the window (the neck ridge, 76% no terrace, median slope 10.2 deg, median HAND
19.4 m), but its 90th percentile is at the 96.1st -- 10.6 ha of T1 on the loop floor at the
western tenth of the unit. The best cell (0.821) and a smaller pocket (0.838) both sit on
that loop floor, both burial risk 0.7. Coordinates are deliberately not recorded: this repo is public and these are model-ranked
precontact candidates on private land.

Top five in the loop, all T1, all on non-public land, ranked by patch mean:
1. The T1 bench at the Trace Creek mouth, order 3 into 6 at 72 m, 4.13 ha, Arrington, burial 0.7
2. The south bench, mid-loop, 2.56 ha, Nolin, burial 0.7
3. The far bank opposite the Trace Creek mouth, flattest (1.76 deg), Nolin, burial 0.7
4. The bench nearest the neck (1.95 km), 2.55 ha, Nolin, burial 0.7
5. The patch on Armour silt loam, **burial risk 0**: the only one whose surface is readable

Control positive in the same window: Mound Bottom's median cell ranks at the 71.3rd percentile,
its 90th at 92.5, its best cell is the highest in all 41.4 km^2. Mace Bluff ranks at the 44.1st
median and should -- it is a petroglyph bluff, not a village.

Two deviations to record: nothing was written to `derivation`, and confluences were found with a
20 m snap tolerance rather than strict intersection (2 junctions strict, 16 tolerant; all five
ranked spots depend on the tolerant version). `confluence_extract.sql` warns about exactly this.
