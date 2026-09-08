---
name: settlement-ecology
description: >
  The method literature behind settlement-pattern features — site catchment,
  cost distance and least-cost paths, viewshed, ideal free distribution,
  landform association in the Eastern Woodlands. Use when proposing,
  reviewing, or explaining any C-series feature (aspect, portage, karst
  distance bands, chert distance), when writing a weight-set rationale, or
  when an interpretation needs a citation instead of a model prior (G2).
---

# Settlement ecology — the citable footing for feature design

CLAUDE.md: interpretations cite, or say the claim is unsourced. This skill
carries the method literature that turns "distance to confluence feels
right" into a sourced design decision — and marks where the footing is
thin, portage-style, rather than papering it over.

**Verification note (G2):** citations here are written from model knowledge
of standard works. Before any of them enters a methods appendix or an
artifact's sources block, verify against the actual publication. Anything
marked *[unverified]* has a plausible but unchecked detail.

## Site catchment — why distance bands are features at all

Vita-Finzi & Higgs (1970) formalized the idea that a settlement's location
is legible from the resources reachable within a daily working radius —
conventionally 5 km / 1 hr walking for agriculturalists, larger for
foragers. Every `dist_to_*` feature in the stack is a catchment argument in
miniature: the feature asserts that proximity to the resource mattered at
settlement-decision time. Corollary that guards feature design: a distance
band is justified by a *resource or affordance* (water, chert, portage
landing, spring), never by a modern convenience (roads — which is exactly
why `dist_to_road` is permanently a diagnostic).

- Vita-Finzi, C. & Higgs, E.S. 1970. Prehistoric economy in the Mount
  Carmel area: site catchment analysis. *Proc. Prehistoric Society* 36.
- Roper, D.C. 1979. The method and theory of site catchment analysis: a
  review. *Advances in Archaeological Method and Theory* 2.

## Cost distance — straight-line distance is the wrong metric on the Rim

On the Central Basin floor, Euclidean distance bands are an acceptable
approximation. In dissected Highland Rim terrain they are not: 300 m across
a hollow can cost more than 2 km along a bench. When B3's cross-physiography
holdout underperforms on Beaman-type terrain, cost-distance versions of the
water/confluence bands are the literature-supported fix — Tobler's hiking
function or a slope-based cost surface, computed once per AOI.

- Tobler, W. 1993. Three presentations on geographical analysis and
  modeling. NCGIA Technical Report 93-1. (The hiking function.)
- Herzog, I. 2014. A review of case studies in archaeological least-cost
  analysis. *Archeologia e Calcolatori* 25. *[unverified volume]*
- Conolly, J. & Lake, M. 2006. *Geographical Information Systems in
  Archaeology*. Cambridge. (Chapter-level treatment of cost surfaces and
  their failure modes.)

## Ideal free distribution — the ranking logic behind suitability

The IFD (from behavioral ecology, applied to settlement by Kennett,
Winterhalder and colleagues) predicts that the *best* habitat patches are
occupied first and longest; later or subordinate settlement fills
progressively poorer patches. Two consequences for this project: (1) a
suitability surface is implicitly a first-occupancy ranking, so persistent
multi-component sites should sit at its top — which is why controls like
Mound Bottom are fair tests; (2) *time-depth stratifies suitability*: late,
short-lived occupations legitimately sit on middling landforms, so a
middling score at a known minor site is consistent with the model, not
evidence against it. State this when explaining a low score at a real site.

- Kennett, D.J. & Winterhalder, B. (eds) 2006. *Behavioral Ecology and the
  Transition to Agriculture*. California.
- Jochim, M. 1976. *Hunter-Gatherer Subsistence and Settlement: A
  Predictive Model*. Academic Press.

## Landform association in the interior Southeast

The empirical regularities the feature stack encodes, with their sources:

- **Terrace-edge preference**: habitation concentrates on the outer edge of
  the lowest non-flooding terrace, adjacent to both floodplain fields and
  the channel. Smith (1978) for Mississippian floodplain settlement
  ("meander-belt" positioning); Brakenridge's Duck River alluvial
  chronology (see `holocene-geomorphology`) for which surfaces existed to
  be occupied.
- **Confluence preference**: resource-edge overlap plus travel-network
  position. Well attested as a pattern in Eastern Woodlands survey data
  (Smith 1978; regional survey literature), though the *causal* weighting
  of ecotone vs. travel remains interpretive — say so when explaining
  `dist_to_confluence_m`.
- **South/southeast aspect preference** for winter insolation at
  habitation sites — commonly reported in Eastern Woodlands predictive
  models (e.g. the Kvamme tradition) but weaker and more setting-dependent
  than the terrace and water associations. Treat C5 as a candidate that
  must earn promotion through B2 ablation, not an established prior.
- **Middle Cumberland Mississippian specifics** — stone-box cemeteries
  paired with habitation, mound-town spacing along the Cumberland: Smith,
  K.E. 1992, *The Middle Cumberland Region: Mississippian Archaeology in
  North Central Tennessee* (PhD dissertation, Vanderbilt). *[unverified
  title details]*
- Smith, B.D. 1978. Variation in Mississippian settlement patterns. In
  Smith (ed), *Mississippian Settlement Patterns*. Academic Press.
- Anderson, D.G. & Sassaman, K.E. 2012. *Recent Developments in
  Southeastern Archaeology*. SAA Press. (Period-by-period settlement
  overviews.)

## Portage and water travel — the recorded gap, unchanged

Dugout travel in the interior Southeast is well attested; neck portages on
rivers of the Cumberland/Harpeth's size are **not specifically sourced**,
and C6's `neck_max_m` / `loop_min_m` stay flagged as unsourced parameters
until a documentary or ethnohistoric source is found. This skill does not
close that gap; it preserves it. Candidate source types worth checking:
early travel accounts (Donelson party journals), trade-route
reconstructions (Myer, W.E. 1928, *Indian Trails of the Southeast*, BAE
42nd Annual Report — a real and directly relevant compilation for
Tennessee; verify plate/page before citing).

## How to use this in a feature proposal

A C-series feature proposal cites: (1) the mechanism (which association
above, with source), (2) the metric choice (Euclidean vs cost, with the
physiography argument), (3) the falsifier (which control should register,
which B2 ablation number would justify removal). A proposal that cannot
fill slot 1 goes in as a companion band with the gap recorded — the portage
pattern is the template.

## Independence beats strength (added 2026-09-08)

Every association above is a candidate line of evidence, and the project has
now MEASURED how they combine (`midden score evidence`; see the
`relational-evidence` skill). That reshapes what makes a good proposal:

- **Prefer a weak independent line to a strong correlated one.** Catchment
  features drawn from the same hydrography — stream distance, confluence
  distance, floodplain position — largely restate each other; the effective
  layer count collapses toward one and the second line adds almost nothing.
  A line from another domain (lithic geology beside hydrology, insolation
  beside water) adds nearly a full layer. Say what a proposed feature is
  independent OF.
- **Ubiquity disqualifies.** A band covering most of the frame describes
  Middle Tennessee, not a site: `dist_to_stream_m` at 98% coverage measured
  as DILUTION (-0.096 separation) though water access is real and sourced.
  A true association can still be a useless feature if it is everywhere.
  Choose the association distance so the layer is selective; report coverage.
- **The falsifier is separation, not the mean.** Control value minus frame
  mean is the only statistic that distinguishes a site from the landscape.

So a proposal now has a fourth slot: (4) what it is independent of, and its
expected frame coverage. A proposal that cannot fill slot 4 is probably a
restatement of something already in the stack.
