# Frozen state — v0.1.0-research

This is the state the January blind test starts from. Nothing below is to be changed
before that test: no weight set, parameter or rule. Changing any of it afterwards is a new
version with its own record.

## Identity

| | |
|---|---|
| Code state | git commit `56650b576da6d84b2ad032274973481aa29908c9` (branch `chore/stabilize`; the tag `v0.1.0-research` is applied after merge, so check the merge commit contains this tree's `weights/` and `src/` unchanged) |
| Weight set | `weights/open_habitation.yml`, version 4 |
| SHA-256 of the weight set | `82ce43e8ef6c9cac699afc1ffb1c62784018bca7407463feb93dda7fd30e123e` |
| Package version | 0.1.0 |

Verify the weight set: `shasum -a 256 weights/open_habitation.yml`.

## Control-frame numbers (open_habitation, v4)

Rebuilt from scratch in a fresh clone on 2026-10-19 against live upstream data (ROADMAP,
"Clean-clone reproduction"). The test starts from the **rebuilt** column; the recorded
column is what the 2026-09-06 run reported.

| frame | recorded mean pctile | rebuilt mean pctile | enrichment | empirical p |
|---|---|---|---|---|
| mound-bottom | 79.3 | 79.5 | 8.80x | 0.10 |
| castalian-springs | 95.5 | 95.5 | 14.01x | 0.08 |
| fewkes-group | 92.9 | 92.2 | 9.37x | 0.115 |
| old-stone-fort | 87.9 | 87.9 | 2.62x | 0.045 |

Mean pctile is the mean percentile of the frame's regional score surface over the control's
footprint; the p value is from the matched-footprint permutation test (`midden score
validate`, seed 42, default draws). Only old-stone-fort clears p < 0.05. This weight set is
not shown to work; it is the fixed thing the blind test measures.

Differences between recorded and rebuilt are upstream data drift (SSURGO, NHD, TIGER are live
services), not code changes. Access bias (B4) top-5% vs background road distance ratios:
0.60 / 0.59 / 0.94 / 1.78; the first two show the stack sitting closer to roads than chance.

## Other fixed inputs

- Label corpus: 72 historic-map points, 57 confirmed / 13 rejected / 2 open, as tracked in
  `labels/`. Confuser ledger: empty file (the two original rows were not recoverable).
- Gates passing on the freeze: `midden evals` 13/13; `pytest` 20 passed; ruff clean.
- Install: editable from a checkout (README, "Using midden from another project").
