---
name: histmap-digitize
description: >
  Digitize symbols from a catalogued historic USGS quad into ref.control_sites
  with full provenance. Use whenever digitizing a sheet (roadmap A1), reviewing
  digitized points, re-loading a sheet, or deciding which map symbol maps to
  which class_id. Encodes the provenance invariants so every sheet is digitized
  identically.
---

# Digitizing a historic quad into control sites

This is roadmap **A1** — the label source that retires the n=2 problem. The
workflow is convention-heavy and every convention is an invariant: a point
without provenance is not a label, and a symbol misread into the wrong class
poisons that class's validation set.

## The pipeline, end to end

1. `uv run midden histmap list` — confirm the sheet is catalogued and note its
   exact `sheet_id`, `map_year`, scale, and `positional_confidence_m`. Never
   type a sheet_id from memory; the id embeds year and scale, and the labels/
   directory has already shown a remembered year to be wrong.
2. Get eyes on the sheet:
   - **claude-vision**: `uv run midden histmap tiles <sheet_id>` writes
     georeferenced tiles under the data dir. Read each tile image, locate
     symbols, convert pixel positions to EPSG:26916 using the tile's
     georeferencing. Work tile by tile; record a `name` for every symbol from
     the map's own lettering ("Wallace Mill", "Cem.", "Old Furnace").
   - **by-hand**: load the warped COG in QGIS (qgis-mcp `add_raster_layer`),
     drop points in a scratch layer, export GeoJSON in EPSG:26916.
3. Build the GeoJSON: Point features, coordinates in **EPSG:26916** (never
   lon/lat), properties `class_id` and `name`. Optional per-feature
   `positional_confidence_m` if the pointing error exceeds the sheet's — the
   loader takes the max of feature and sheet, so a point can never claim more
   certainty than the map it came from. File goes in `labels/` named
   `<sheet_id>.geojson`.
4. `uv run midden histmap load-sites <sheet_id> labels/<sheet_id>.geojson
   --method claude-vision` (or `by-hand`). The method lands in provenance.
5. Verify: count loaded rows per class, and spot-check 2–3 points against the
   sheet render. All rows land `review_status='unreviewed'`.

## Symbol → class_id mapping

Only classes in `uv run midden classes` are loadable — the loader raises on
unknown ids. Standard USGS topographic symbols of the 1890s–1950s:

| map symbol / label | class_id | notes |
|---|---|---|
| "Mill", "Gristmill", "Sawmill", mill wheel symbol | `mill_seat` | the A2 vanished-feature test target |
| "Furnace", "Forge", "Iron Works" | `iron_works` | Montgomery Bell district |
| "Cem", cross-in-square, small fenced plot | `family_cemetery` | high symbol density on 1:24k sheets |
| filled black square (dwelling) | `homestead` | digitize selectively — every farmhouse is one; prioritize those absent from modern maps |
| dashed/unimproved road, "Ford" | `road_trace` | digitize the ford point or a representative node, not the whole line |
| "Saltpeter Cave", "Cave" with works | `saltpeter_works` | proxy class — the label is the evidence, not a LiDAR signature |
| "Mound", "Indian Mound" | `mound_earthwork` | rare but gold when present |
| church cross, "Sch", "School", "Ch." | `civic_structure` | same detection signature as homestead (foundation, terraced ground), different siting model (crossroads/centrality); owner decision 2026-09-05 after 23 such symbols on the first two sheets |

Symbols with no registry class are **not** loaded, but note them in the
session summary — repeated unmappable symbols are an argument for a registry
addition, made with counts. `civic_structure` is the precedent: 23 symbols
across two sheets, added by owner decision rather than silently absorbed
into `homestead`.

## Rules that are not optional

- **The map's date is the point's date.** A feature on the 1930 sheet and
  absent from the modern quad is dated to that window — that is the A2
  vanished-feature fuel. Put "(vanished)" context in `name` when checked.
- **Do not snap to modern features.** Digitize where the symbol sits on the
  historic sheet, even when a modern road or pond suggests the "real" spot.
  The positional error is declared in `positional_confidence_m`; silently
  correcting it destroys the error model that A2's tolerance radius uses.
- **Re-loading replaces only unreviewed rows.** Confirmed/rejected rows
  survive and the loader reports them. Never UPDATE review_status yourself —
  review is a human step; the machine only proposes.
- **One sheet per session-unit of work.** Digitize, load, verify, then stop
  and record the count per class in the session summary so ROADMAP.md's A1
  entry can be updated in the same commit.
