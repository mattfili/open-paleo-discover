# Why the model looks like this

`spec.md` says what the project should be. `ROADMAP.md` says where it is. This file
says **why** — the reasoning behind each design decision, the measurement that
produced it, and what it means archaeologically. It exists because a future reader
meeting `min_enclosure_ratio: 1.2` or a band from 2 to 12 m HAND deserves the argument
and the number, not a magic constant.

Every finding below is falsifiable and was recorded when it came out, including when it
came out badly. Several of the most useful ones are failures.

---

## 1. The first weight set was wrong, and the way it was wrong mattered

The opening hypothesis scored six landform features, with `terrace_class` carrying the
heaviest weight (3.0). It failed its controls: Mound Bottom reached the 74.6th
percentile where the test demanded 95.

The tempting move was reweighting. The discipline says otherwise — **prefer fixing a
feature over reweighting around it** — so the question became *which* feature was
lying. Ablation answered it: holding `terrace_class` out **raised** Mound Bottom by
2.5 percentile points and doubled top-5% enrichment from 4.15× to 8.36×. The feature
was not merely uninformative, it was actively harmful.

*Why archaeologically.* `terrace_class` labelled HAND modes by ordinal position — "the
second-lowest mode is T1". That encodes a human interpretive category as an integer and
then asks a weight to be attached to a rank. It also inherits mode-counting fragility:
Castalian Springs has two HAND modes where Mound Bottom has three, so "class 2" means a
different landform at each site, and Old Stone Fort has **ten** modes, where the concept
dissolves entirely.

*What changed.* The feature was deleted (C1). The terrace *concept* returned as two
continuous, separately-testable features: `hand_m` with a **band** response — full score
from 2 to 12 m, tapering over 15 m — because habitation concentrates on the lowest
non-flooding surface (Smith 1978), which is a hump rather than a slope; and `flood_freq`
from SSURGO, because T0 is definitionally the surface that floods. One principled
change, tested once across four control frames: **every frame improved** (Mound Bottom
78.0, Castalian 95.5, Fewkes 92.9, Old Stone Fort 87.9).

---

## 2. A pass with no error bar is not a result

The original control test asked whether a site's mean score percentile exceeded 95. That
is a threshold with no error bar, applied to footprints — whole management units
including river channel and bluff — that arguably cannot average that high even for a
good model.

It was replaced (B1) with a **matched-footprint permutation test**: take the control's
own footprint, translate and rotate it to random positions in the background frame,
accept only draws whose landform composition matches, and report where the observed
value sits in that null. The unit of permutation is the footprint, never the cell,
because cells are spatially autocorrelated and a cell-level null produces p-values that
are confidently, silently too small.

*Why this matters.* The old test said "FAIL". The new one says "76.8th percentile,
p = 0.13" — the same conclusion, but now with a magnitude and an uncertainty, and it
degrades honestly at low n instead of passing or failing arbitrarily.

The same principle became structural on the detection side: `midden validate histmap`
draws matched null discs on **every** run and grades itself. A recall without a
background fire rate is not reported.

---

## 3. Three rule families failed before one worked, and the pattern is the finding

The detection question — can the 0.5 m chain find features? — was attacked four ways.
Each was tested against its own negative control.

| the rule asks | recall | background fires | verdict |
|---|---|---|---|
| is this cell extreme? (amplitude, p95) | 12/12 | 94–100% | uninformative |
| is this blob the right size and shape? | 6/6 | 97% | uninformative |
| are the parts regularly arranged? (graves) | 0/6 | 16% | quiet but blind |
| **do two things pair?** (ore pit + spoil) | **2/4** | **11%** | **informative** |
| **does a boundary close?** (cemetery plot) | **3/9** | **4%** | **informative** |

The first row is the trap this project exists to avoid: **100% recall that means
nothing**, because the rule fires on essentially all ground. Middle Tennessee is
carpeted with tree throws, gullies, karst, and twentieth-century earthmoving; anything
"unusual" is common.

*The pattern.* Both winners ask about a **relation**, not a property. An excavation
makes spoil, so an ore pit and its spoil pile occur together — while a dissolution
sinkhole, which looks similar, has no spoil. A burial plot is *enclosed* by a fence,
wall, or ditch — while a gully or a tree-throw scatter never closes on itself.

*The instructive failure.* The grave-arrangement rule was the most faithful to the
archaeological literature — cemeteries genuinely are rows of regular depressions — and
it scored zero. Individual graves do not resolve as separate clusters in 0.5 m LiDAR
under forest canopy. **Check that the parts are resolvable before betting on their
pattern.**

*How the fix arrived.* Human review. The owner, checking labels, reported seeing plot
outlines in the LiDAR at three cemeteries where the rule scored 0/8. That observation
specified the enclosure rule directly, and one of its three hits is a point the same
reviewer had rejected in an earlier round and which was then re-digitized onto the
correct symbol. The loop closed end to end.

---

## 4. Label precision is a variable, and it is measurable

Two sheets, same class, same rule, different outcomes. On Burns 1953 (1:24,000, ~45 m
tolerance) the rectangularity gate helped: 2/2 recall against a 32% background. On
White Bluff 1930 (1:62,500, ~95–150 m tolerance) the same gate broke: 1/3 against 71%.

*Why.* The searched disc is the label's positional confidence plus the feature's own
radius. At 45 m the disc is mostly feature; at 150 m it is mostly background, and any
rule will find something in it.

*What changed.* All 22 coarse points were re-examined against 1966 1:24,000 editions.
Seven surviving features were relocated at 35–45 m confidence — one was **187 m** from
its 1930-derived position — three previously unknown cemeteries were harvested, and
fifteen features present in 1930 and absent by 1966 became **dated vanishings**, which
is exactly the public, falsifiable ground truth the vanished-feature test consumes.

Then the payoff: Taylortown Cemetery, at 40 m confidence, became the **first cemetery
ever to carry information** (1/1 against a 23% background) using the very multi-element
rule that had scored 0/6 on coarse discs. The signature was always there; the tolerance
was drowning it.

---

## 5. The chain sees razed features better than standing ones

The surviving 1966 churches all *missed*, on quiet backgrounds. The vanished ones did
better.

*Why.* Ground classification removes buildings from a bare-earth DEM. A standing church
is deleted by the very processing that makes the surface readable; a razed church leaves
a levelled pad and a cellar depression, which are ground.

*Consequence.* The vanished-feature test is strongest exactly where features vanished —
a pleasing property for an archaeological instrument, and a caution against reading a
miss at a standing structure as a failure of the chain.

---

## 6. The model launders accessibility, and now says so

`dist_to_road` is permanently barred from the weight set: it predicts where
archaeologists have looked, not where people lived. But excluding it never removed the
bias — roads follow terrace edges, gentle slope, and water access, so accessibility
re-enters through the scored features.

Measured (B4): the top-5% cells sit at a median **143 m** from a road against a
background median of **236 m** — a ratio of 0.61, and 0.62 at Castalian. The model's
best ground is about 40% closer to roads than chance.

*What this is and is not.* It is a **measurement**, reported on every scoring run and
inherited by every survey plan as a stated caveat. It is not a correction: correcting
would require survey-coverage polygons that are not public. The distinction stays
explicit, because "measured" and "corrected" are different claims.

---

## 7. Independence is necessary and not sufficient

Relations beat properties (finding 3), which raised the obvious next question: do
several relations compound? They can — but only if they are independent, so
`midden score evidence` **measures** the redundancy rather than assuming it, collapsing
correlated layers toward a single effective layer.

Two results, from opposite directions:

- **Stream proximity dilutes.** It covers 98% of the frame. Water access is real,
  well-sourced, and useless as a discriminator here, because it describes Middle
  Tennessee rather than a site. Ubiquity disqualifies.
- **Chert proximity is perfectly independent and still dilutes.** Distance to
  chert-bearing bedrock measured r = 0.00 against both hydrography layers — exactly as
  predicted — and *still* hurt, because every cell in the frame lies within 783 m of
  chert-bearing outcrop and 60% sit on it. At 1:250,000 the Fort Payne polygon alone is
  2,224 km².

*Why archaeologically.* In the Central Basin and along the Highland Rim margin,
chert-bearing carbonate **is** the bedrock. "Near chert" is a regional constant, not a
local choice — and a 250k geologic compilation cannot resolve variation relevant to a
10 m model regardless.

*The correction, and where it came from.* The owner's original observation was worked
material in a dry **gravel** creek. The chert that mattered to people was cobbles in
stream gravel, not bedrock outcrop — localized, transported, and sitting in exactly the
landform they described. So the lithic feature is not geology at all; it is the
channel. This is the clearest case in the project of a field observation correcting a
plausible desk decision.

---

## 8. What a proxy class can and cannot be given

Some classes have no LiDAR signature at all — middens, buried habitation, stone-box
cemeteries. They are declared `proxy` in the registry, detection runs for them are
refused by the tool, and a proxy result is never reported as a detection.

They can still be *argued for*, through a chain of indirection:

    invisible evidence   →   visible context   →   detectable landform
    worked flakes            dry gravel channel     linear concave trace

The flakes are centimetres and no grid will ever hold them. Their **presence** is what
the association encodes. This produced **context classes** — landforms detected as
evidence rather than as targets, `relict_channel` being the first — and gave the
two-grid cascade its first real motivation: detect the context at 0.5 m, promote it to
candidate zones at 10 m, survey those.

---

## 9. Physiography changes the background, not just the model

Under identical rules, Highland Rim upland fired at a **65%** background rate where
valley-bottom Basin ground fired at 96–100%. Dissected uplands simply produce fewer
compact high-percentile anomalies than floodplain terrain.

*Consequence.* A detection threshold tuned in one physiographic province is not
transferable to another, and neither is a recall number. It is also the detection-side
echo of a model-side problem: the four control frames disagree about which features
matter — HAND carries at Mound Bottom and is harmful at Castalian; slope is the reverse
— which is precisely what a cross-physiography holdout (B3) exists to settle, and why
no further reweighting is licensed on four controls.

---

## How to use this file

When explaining any output, the obligation is to say what the number means, what would
fool you, and what it does not claim (see the `midden-interpretation` skill). This file
supplies the *why* behind the machinery doing the measuring:

- a parameter's value → the finding that set it,
- a rule's shape → the rule families that failed first,
- a caveat in a report → the measurement that made it necessary.

If a finding here is contradicted by new evidence, the correction goes in with its
number and its date. Nothing in this file is settled by argument.
