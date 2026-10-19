# Sources for teaching and further analysis

Curated, by topic. Add to this file whenever a new source is used in a writeup, with one
line on what it is good for. Prefer primary and regional literature; encyclopaedias are
fine for orientation and dates.

## The Narrows and the iron district

- ASCE, Montgomery Bell's Tunnel (Historic Civil Engineering Landmark page):
  https://www.asce.org/about-civil-engineering/history-and-heritage/historic-landmarks/montgomery-bells-tunnel
  -- 290 ft, 1818/1819, 5.5-mile loop, 17 ft drop, hand drills and black powder, enslaved labour.
- Wikipedia, Montgomery Bell Tunnel: https://en.wikipedia.org/wiki/Montgomery_Bell_Tunnel
  -- portal and bore dimensions, NHL 1994, "dug entirely through limestone".
- Tennessee Encyclopedia, Patterson Forge / Narrows of the Harpeth:
  https://tennesseeencyclopedia.net/entries/patterson-forge-narrows-harpeth-state-historical-area/
- HMDB marker text: https://www.hmdb.org/m.asp?m=248944

## Mound Bottom and the Middle Cumberland Mississippian

- Tennessee Encyclopedia, Mound Bottom: https://tennesseeencyclopedia.net/entries/mound-bottom/
  -- AD 950-1300, 29+ mounds, five miles of palisade, horseshoe bend setting, Pack site.
- O'Brien & Kuttruff, "The 1974-75 Excavations at Mound Bottom, a Palisaded Mississippian
  Center in Cheatham County, Tennessee", Southeastern Archaeology 31(1), 2012:
  https://www.tandfonline.com/doi/abs/10.1179/sea.2012.31.1.005 -- the primary excavation report.
- TDEC, Mound Bottom State Archaeological Area:
  https://www.tn.gov/environment/program-areas/arch-archaeology/state-archaeological-parks-areas/mound-bottom-state-archaeological-area.html
- Kevin E. Smith, Mound Bottom articles (Tennessee Archaeology Net):
  https://capone.mtsu.edu/kesmith/TNARCH/MoundBottom.html -- regional specialist's overview;
  also the place to start on stone-box graves and Middle Cumberland chronology.

## Geology

- USGS State Geologic Map Compilation (SGMC), Horton, Tommy & Shaw 2017, USGS Data Series
  1052: https://pubs.usgs.gov/ds/1052/ds1052.pdf ; state files at
  https://mrdata.usgs.gov/geology/state/ (TN.zip is the shapefile the retired `sources/geology.yml` pointed at; the live source is `sources/sgmc_geology.yml`, which reads the same compilation over WFS).
  -- 1:250,000 compilation; unit, age, lithology per polygon. Used 2026-09-03 to establish
  that the Narrows neck and Hidden Lake are Silurian (Wayne/Brownsport/Decatur), not Ordovician
  or Fort Payne, with Fort Payne chert on the surrounding uplands.
- Fort Payne Formation (orientation): https://en.wikipedia.org/wiki/Fort_Payne_Formation

## Elevation and hydrography services (used 2026-09-04)

- USGS 3DEP Elevation ImageServer `exportImage`:
  https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer -- 10 m DEM
  straight to a projected GeoTIFF; the fast path when seamless-3dep is unavailable.
- USGS Elevation Point Query Service: https://epqs.nationalmap.gov/v1/json -- independent
  spot-check of a DEM. Agreed with 3DEP to within 14 cm at all five Narrows points.
- NHDPlus HR MapServer, layer 3 NetworkNHDFlowline:
  https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer -- carries
  `streamorde` and `totdasqkm` per reach, which is what the confluence and order features need.

## Method

- Doneus, M. 2013. "Openness as Visualization Technique for Interpretative Mapping of
  Airborne Lidar Derived Digital Terrain Models." Remote Sensing 5(12). -- the openness
  sign convention and why it beats sky-view factor for convex features.
- Relief Visualization Toolbox (RVT), EarthObservation/RVT_py -- the horizon scan midden vendors.

## To add (not yet used in a writeup)

- Tennessee Division of Archaeology site-file *summaries* (locations are protected; do not
  request or store them).
- Regional syntheses on Late Archaic shell middens of the Cumberland (e.g. work on the
  Anderson site and the Cumberland River shell-mound archaic) for the burial-risk argument.
- Ethnohistoric accounts of dugout canoe travel in the interior Southeast, to ground the
  portage feature in something other than plausibility.
