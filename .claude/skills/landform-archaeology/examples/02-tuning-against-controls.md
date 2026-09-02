# Example 2 — Tuning parameters against a control

The discipline that separates a result from a story you told yourself.

## The rule

Tune on a location where you know what is there. Apply the result to prospects unchanged.

Tuning on a prospect means adjusting parameters until an ambiguous blob resembles what you
hoped for. It does not feel like cheating while you are doing it. That is the problem.

## Two kinds of control

**Detection control** — a known surface feature. Tests the render chain. Best case is
something at the same scale as your real targets.

**Positive control** — a known site. Tests the suitability model. Use published sites
only: historical markers, literature, public coordinates. Never a restricted state
inventory.

## Tuning a detection control

Take an iron district with relict charcoal hearths — 8–15 m circular platforms, clustered
on slopes, cut-and-fill lens shape where the ground is steep.

Sweep SLRM radius:

```bash
python scripts/detection_renders.py dem.tif sweep/ --slrm-radius 8 10 15 20 25 30
```

Open all six at a fixed stretch. You are looking for the radius where hearth-scale
features are crisp and tree-throw-scale noise has not swallowed them:

- 8–10 m — hearths visible, but so is every stump hole. Noisy.
- 15 m — usually the sweet spot at this feature scale.
- 25–30 m — hearths softening, larger landforms dominating.

Then sweep openness radius at the SLRM value you picked. Remember it is in cells: 20 cells
at 0.5 m is a 10 m search, about one hearth.

**Why this is the important control:** a charcoal hearth is 8–15 m and 0.2–0.5 m of
relief. A plowed-down mound is 20–40 m and 0.3–0.8 m. If your renders resolve hearths,
they will resolve the mound. If they do not, no amount of tuning on the mound AOI will
help — you would just be tuning against something you cannot verify.

Guard against the obvious confusion while you are there. Log landings are also flat
circular clearings. They are 20–40 m, less regular, and connected to a skid trail network.
Trace the connections.

## Testing a positive control

```bash
python scripts/control_check.py score.tif controls.geojson --top-pct 5
```

A major published site should land in the top few percent of its own AOI. If it does not,
the weight set is falsified.

When it fails, check in this order:

1. **Is a feature in the stack broken?** A unimodal HAND histogram makes the terrace
   feature useless and will sink a control on its own. Check that first — it is a bug, not
   a modelling disagreement.
2. **Is the site's setting actually what you modelled?** A bluff-top Woodland mound
   complex will fail a weight set built for riverine terraces, and correctly so. That is
   information: you may need two weight sets for two site types rather than one bad
   compromise.
3. **Only then, adjust weights.**

What you must not do is move the control, loosen `--top-pct`, or exclude the failing site.
Those all convert a falsification into a pass without changing anything real.

## After it passes

Passing is a floor, not a result. It means the weight set is not obviously wrong.

The interesting question is the next one: **what else ranks up there with the control?**
Those cells are the actual output. Look at them.
