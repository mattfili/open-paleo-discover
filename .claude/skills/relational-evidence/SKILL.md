---
name: relational-evidence
description: Design detection rules and features around RELATIONS between things rather than the properties of one thing. Use when proposing or reviewing any detection rule, when a class detects poorly, when adding a C-series feature, when deciding what to label, or when an invisible/proxy class needs leverage. Encodes the project's strongest measured finding: single-object amplitude and shape rules fire everywhere in textured ground, while relational rules separate signal from background.
---

# Relational evidence — the measured design principle

Middle Tennessee ground is textured everywhere. Tree throws, gullies, karst, and
20th-century earthmoving fill every percentile band a detector might reach for. The
project measured this the expensive way, three times, and then measured the way out.

## The evidence (all with negative controls, all in ROADMAP)

| rule asks | example | recall | background fires | verdict |
|---|---|---|---|---|
| is this cell extreme? | amplitude p95 | 12/12 | 94-100% | uninformative |
| is this blob the right shape? | size + elongation gates | 6/6 | 97% | uninformative |
| are the parts arranged right? | graves, regular spacing | 0/6 | 16% | quiet but blind |
| **do two things PAIR?** | **ore pit + spoil, 30 m** | **2/4** | **11%** | **carries information** |
| **does a boundary CLOSE?** | **cemetery plot enclosure** | **3/9** | **4%** | **carries information** |

Two independent classes, two independent morphologies, one lesson: **a property is not
evidence; a relationship is.** A compact anomaly past p95 exists nearly everywhere. A
compact anomaly that *encloses* something, or that *pairs* with its complement at the
right distance, does not.

## The taxonomy — pick the relation the morphology actually implies

1. **Pairing** — two signatures that are causally joined and must co-occur within a
   distance. Excavation makes spoil (a sinkhole has none); a mill has a race AND a dam
   abutment; a homestead has a cellar AND a chimney fall. Registry: `detect.pair`
   `{surfaces, max_gap_m}`.
2. **Enclosure** — a boundary that closes around something. Fences, walls, ditches,
   embankments do; gullies and scatters do not. Registry: `min_enclosure_ratio` plus a
   plot-scale `span_cells_range`.
3. **Arrangement** — N elements in a regular pattern. Powerful in principle (windthrow
   is Poisson, rows are not) but it FAILED here on graves, because the elements did not
   resolve at 0.5 m in forest. Check that the parts are resolvable before betting on
   their pattern.
4. **Context / adjacency** — the target is invisible, but the ground it sits beside is
   not. This is the one that unlocks proxy classes; see below.
5. **Co-occurrence stacking** — several weak, INDEPENDENT associations compounding.
   Untested here as of 2026-09-08 and the obvious next experiment: two associations
   that share a cause (channel and floodplain) compound far less than two that do not
   (channel and chert source).

## Context classes: how an invisible class gets leverage

A `proxy` or `invisible` class can never be detected — that is what the declaration
means, and running a detection chain for one is refused by design. It can still be
*argued for*, through a landform that is detectable and associated:

    invisible evidence  ->  visible context  ->  detectable landform
    worked flakes           dry gravel channel     linear concave trace

The flakes are centimetres and no grid will ever hold them; their PRESENCE is what the
association encodes. `ref.target_class` therefore carries **context classes** —
`relict_channel` is the first — declared `direct` and detection-grid, but whose purpose
is evidence for another class rather than being a target. A context class earns its
place the same way any feature does: `dist_to_<context>_m` must pass a B2 ablation, and
a context detection is NEVER reported as a detection of the class it argues for.

This is also the concrete motivation for the two-grid cascade (E): detect the context
at 0.5 m, promote it to candidate zones at 10 m, survey those.

## Building one

- Put the relation in `ref.target_class.params.detect` — it is a per-class parameter
  like any other, and the class gates the run.
- Derive gate values from the **morphology column and the feature catalog**, never from
  tuning against controls until they pass. One principled change, tested once,
  recorded either way.
- Ship it with its negative control. `midden validate histmap` draws matched null discs
  automatically; a recall without a background fire rate is the pass-with-no-error-bar
  failure this repo exists to prevent.
- Read the misses. Every cemetery miss reached p99.8-100 in negative openness and failed
  a *gate*, not the threshold — that says tune gates against confirmed labels, not
  invent a fourth rule family.

## What this implies for labelling

Confirm/reject on map symbols teaches copying accuracy. It does not teach discrimination,
because it never labels what is actually on the ground. An **open pass** — label every
visible feature, modern and historic and ancient, target and confuser alike — produces
the hard negatives that set precision and makes the modern-versus-old axis learnable.
`ref.confuser` is the destination for the negatives.

One cost, and it is structural: labels drawn from what is VISIBLE are selection-biased
toward detectable things. Excellent for precision and confusers; never poolable with
map-derived labels for a recall estimate. Provenance stays recorded per the label
invariant.

## Sensitive locations

A site known from fieldwork or a state site file is not public data and this repo is
public. `data/` and the database are gitignored; `labels/` is tracked. A
personally-known location belongs in `ref.control_sites` with a source that says so, and
never in a committed file.
