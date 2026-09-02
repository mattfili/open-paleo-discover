# Anomaly log — <AOI name>

Renders reviewed: <parameter values used>
Reviewed by: <name / model>
Date: <YYYY-MM-DD>

One row per candidate. Every anomaly gets a category — no prose hedging. Most entries
should be `likely natural` or `likely modern`; if most of yours are `likely cultural`,
go back through `references/feature-catalog.md` and be harder on yourself.

| ID | Easting | Northing | Size (m) | Form | Visible in | Category | Best explanation | Notes |
|----|---------|----------|----------|------|-----------|----------|------------------|-------|
| A-001 | | | | | slrm / opn+ / opn- | | | |

Coordinates in EPSG:26916. Do not record coordinates of any restricted-inventory site here.

---

## Categories

| Category | Meaning |
|---|---|
| `likely cultural` | Form, scale, setting, and spatial pattern all consistent; natural and modern explanations considered and rejected |
| `ambiguous` | Consistent with cultural origin, but a natural or modern explanation cannot be excluded |
| `likely natural` | Best explained by a geomorphic or biological process |
| `likely modern` | Best explained by 20th-century land use |

## Before logging anything as `likely cultural`

Work down this list. Each one has talked someone out of a false positive before.

- [ ] **Is it paired with an adjacent pit or mound at 2–5 m scale?** Tree throw. The most
      common false positive in forested LiDAR.
- [ ] **Is it a closed depression with no spoil?** Karst sinkhole. Excavation makes a
      pile; dissolution does not. Middle Tennessee is karst.
- [ ] **Is it circular, 20–40 m, and connected to a trail network?** Log landing, not a
      charcoal hearth. Size and connectivity separate them.
- [ ] **Is it perfectly straight over a long distance?** Flight-line seam or modern
      infrastructure. Nothing archaeological is that straight that far.
- [ ] **Are there parallel evenly-spaced contour-following benches?** 20th-century
      conservation terracing.
- [ ] **Does it sit in a low-ground-return area?** Check canopy cover — it may be an
      interpolation artifact.
- [ ] **Have you checked current and historical aerials?** Modern earthmoving is the
      single largest source of clean geometric anomalies.
- [ ] **Have you checked a historical topographic quad?** A structure symbol at that spot
      converts a guess into near-certainty — and often tells you it is a 1920s barn.
- [ ] **Is it isolated?** Archaeological features are spatially patterned. Hearths cluster,
      house sites line a lane, mounds sit in defined arrangements. One anomaly with no
      context is overwhelmingly likely to be natural or modern.
- [ ] **Is it visible in at least two of SLRM, positive openness, negative openness?**
      Single-layer anomalies are usually processing artifacts.

## Spatial pattern

Fill this in once per AOI, not per anomaly. It is usually more informative than any
individual row.

- Number of candidates by category:
- Clustering observed (spacing, alignment, relationship to terrain):
- Relationship to terrace class, water, confluences:
- Anything that looks like a site plan rather than scattered points:

## Follow-up

- [ ] Cross-referenced against historical topographic quads
- [ ] Cross-referenced against historical aerial photography
- [ ] Checked against published site literature for the area
- [ ] Flagged for ground observation (surface only — excavation needs a permit)
