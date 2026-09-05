---
name: spatial-validation
description: >
  Statistical methodology for validating spatial predictions with spatially
  autocorrelated data and few, positionally uncertain labels. Use when
  writing or reviewing B1 (permutation test), B2 (ablation), B3
  (cross-physiography holdout), B4 (access-bias audit), any enrichment
  number, or any claim that a model "works". Encodes what generic statistics
  gets wrong on rasters.
---

# Spatial validation — what generic statistics gets wrong here

Every observation in a raster is correlated with its neighbors, every label
carries 12–32 m of positional error, and n is small. Standard methods
silently assume away all three. This skill is consulted when *writing* the
validation code, so the traps land in the design rather than in a
post-hoc caveat.

## 1. The null must be spatial, or the p-value is fiction

A naive permutation test (shuffle cell labels independently) treats ~7,000
AOI cells as ~7,000 independent draws. They are nowhere near independent —
slope, HAND, and distance bands vary smoothly, so the effective sample size
is orders of magnitude smaller, and the naive null produces p-values that
are confidently, silently too small (Legendre 1993).

The B1 design is right and must be kept: draw **whole footprints** of
matched area — and matched landform composition — from the background
frame, and compare the observed footprint statistic against that
distribution. The unit of permutation is the footprint, never the cell.
Requirements:

- **Matched on area and landform class.** A random footprint that lands
  half-in-river is not a fair draw against a control that is half-in-river
  — matching is what makes the null answer "is this *location* special"
  rather than "are terraces different from channels" (which is already
  known).
- **Non-overlapping draws, or thinned enough that overlap is rare**;
  heavily overlapping null footprints understate null variance.
- **Report observed, the null distribution summary (mean, sd, quantiles),
  and empirical p as (r+1)/(k+1)** — never p=0 from k draws; with k=999 the
  floor is p=0.001 and the report must say so.
- **The background frame is B5 and is recorded per run.** Enrichment is
  relative; a number without its frame is not a result.

## 2. Positional error eats small classes

A label with `positional_confidence_m = 31.8` (1:62,500 sheet) is a disc,
not a point. For A2's hit/miss calls, the tolerance radius is the label's
positional confidence **plus** half the expected feature size — and a "hit"
is detection *anywhere in that disc*, which also inflates false-hit chances
as the disc grows. Report per-class tolerance radii with the recall figure,
and never pool 1:24,000 and 1:62,500 labels in one recall number without
reporting both strata: at 31.8 m, a 10 m hearth is genuinely ambiguous while
a 100 m earthwork is barely perturbed.

## 3. What n ≥ 30 buys, and what it does not

A1's dozens of labels make enrichment CIs and recall estimates meaningful.
They do **not** license fitting: labels digitized from historic quads skew
historic-period, near-settlement, and near-road (the map-maker's own access
bias). Using them for *validation of a class they belong to* is sound; using
them as training data imports the cartographer's sampling into the model.
Label provenance pooling stays recorded per the CLAUDE.md invariant.

## 4. Holdout must be blocked in space (B3)

Random cell- or site-level train/test splits leak: a held-out cell 30 m
from a training cell is not held out at all (Roberts et al. 2017). The only
honest split at this scale is the physiographic block — fit Central Basin,
evaluate Highland Rim, report separately, never averaged. A blocked score
that drops relative to the in-region score is the *expected* honest
outcome, not a failure of the split.

## 5. Ablation reads (B2)

Refit with each feature held out; report delta-enrichment per feature with
the same footprint-level null each time. Two traps: correlated features
(slope and TWI share information — a small solo delta does not mean "no
signal", it can mean "shared signal"; report the correlation matrix
alongside), and asymmetric direction (a feature whose removal *raises*
enrichment is actively harmful and is the quantitative form of the
terrace_class finding).

## 6. Access bias is reported, never corrected (B4)

Compare the distance-to-road distribution of top-5% cells against the
background frame; report the ratio on every scoring run. This measures the
laundering of accessibility through slope/stream proximity. Correction
would need survey-coverage polygons that are not public — the
measured-vs-corrected distinction stays explicit.

## Sources

Standard works; verify volume/page details before citing in a methods
appendix (written from model knowledge, per the G2 rule that unverified
claims are flagged):

- Legendre, P. 1993. Spatial autocorrelation: trouble or new paradigm?
  *Ecology* 74(6).
- Roberts, D.R. et al. 2017. Cross-validation strategies for data with
  temporal, spatial, hierarchical, or phylogenetic structure. *Ecography*
  40.
- Valavi, R. et al. 2019. blockCV: spatial and environmental blocking for
  k-fold cross-validation. *Methods in Ecology and Evolution* 10.
- Kvamme, K.L. 1988. Development and testing of quantitative models. In
  Judge & Sebastian (eds), *Quantifying the Present and Predicting the
  Past*. (The gain statistic — the ancestor of the enrichment ratio.)
- Verhagen, P. 2007. *Case Studies in Archaeological Predictive Modelling*.
  Leiden.
- Fortin, M.-J. & Dale, M. 2005. *Spatial Analysis: A Guide for
  Ecologists*. Cambridge. (Restricted/matched permutation designs.)
