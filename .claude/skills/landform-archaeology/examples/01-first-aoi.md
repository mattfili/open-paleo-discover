# Example 1 — First pass on a new AOI

Walkthrough on a small AOI. Use the smallest one you have; the point is to shake out the
chain, not to find anything.

## 1. Brief it first

Copy `templates/aoi-brief.md` and fill it in before running anything. Ten minutes here
saves a day. The land-use history section is the one that matters most: it tells you what
your false positives are going to be before you see them.

Worked example, an AOI in a 19th-century iron district:

```
Province:            Western Highland Rim, dissected
Forest history:      logged, second growth
Industrial history:  iron — furnace within 3 km
Expectation:         charcoal hearths, 8-15 m, clustered on slopes
Falsified if:        no circular anomalies at that scale anywhere in the AOI
Dominant FP class:   log landings (larger, connected to skid trails)
```

Now you have a prediction. That is what makes the next step a test rather than a
fishing expedition.

## 2. DEM first, at low effort

Pull a 3DEP DEM by geometry before committing to a point-cloud extraction. It is roughly
two orders of magnitude faster and it tells you whether the AOI boundary, CRS, and
plumbing are right. Only go to the LAZ or EPT path once the chain runs end to end.

## 3. Terraces

```bash
python scripts/terrace_extract.py dem.tif out/ --threshold 5000
```

**Look at the histogram in `terrace_report.json` before anything else.** Real terraces
show as separated humps. If you get one broad hump, the stream threshold is wrong and
nothing downstream means anything yet:

- Unimodal and everything near zero → threshold too low, every swale became a stream.
- Unimodal and broad → threshold too high, HAND is measured to a distant channel.

Sweep it: 1000, 2500, 5000, 10000. Pick the value that gives the clearest mode
separation, not the one that gives the most terrace area.

In dissected upland with no floodplain, you may legitimately get no modes. That is a real
answer — the AOI has no terraces — not a failure. The brief should have predicted it.

## 4. Detection renders

```bash
python scripts/detection_renders.py dem.tif out/ \
    --slrm-radius 10 15 25 --openness-cells 20 40
```

Six SLRM/openness combinations. Load them in QGIS, stretch each to a 2–98 percentile clip,
and hold the stretch constant while comparing.

Sanity check: **can you see individual tree throws in mature forest?** If not, the renders
are too smoothed to find a plowed mound either. Their visibility is annoying but
diagnostic.

## 5. Scan

SLRM first — it is the most legible at a glance. Anything that catches your eye, confirm
against both openness bands. Remember the convention: positive openness bright means
convex, negative openness bright means concave.

Log candidates in `templates/anomaly-log.md`. Work the checklist honestly. A first pass on
a forested AOI that produces thirty `likely natural` and two `ambiguous` is a good result.
A first pass that produces fifteen `likely cultural` means you skipped the checklist.

## 6. Fill in the findings

Close the brief. Did the expectation hold? If you predicted hearths and found none, say
so — a recorded negative is worth more than an unrecorded maybe, and it is what stops you
re-running the same AOI in three months having forgotten.
