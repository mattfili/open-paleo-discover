---
name: experiment-loop
description: Run one iteration of the falsifiable-experiment loop (ROADMAP G4) - read the roadmap, pick ONE runnable falsifiable item, execute it with the existing verbs, and write the outcome back in the same commit, including when it fails. Use when asked to "keep moving", "run the next experiment", or advance the roadmap autonomously; also the discipline reference for what counts as a completed experiment.
---

# The experiment loop — one honest iteration

G4's promise: an agent that reads `ROADMAP.md`, proposes the next falsifiable
experiment, runs it, and writes the outcome back into the ledger — **including when
it fails**. A recorded failure is worth more than an unrecorded success; the
falsified firing rules and the hand_mode_tolerance_m entry are the models.

## One iteration, exactly

1. **Read state, not vibes.** `ROADMAP.md` is canonical for what is built, broken,
   and blocked. Do not re-derive it from the tree.
2. **Pick ONE item** by these criteria, in order:
   - *Falsifiable*: the run can produce a number that could say "no".
   - *Runnable now*: not label-blocked, not human-blocked (review is a human step).
   - *Smallest effort per falsifiable claim* — a measured small answer beats a
     half-built large one.
3. **Run it with the existing verbs.** Do not build a new mechanism when a verb
   exists:
   `midden score validate|ablate|polygons|plan`, `midden validate histmap`,
   `midden_sweep` (records its class), `midden terrain run --class`,
   `midden labels seed-nrhp`, `midden histmap ...`, `midden evals`.
4. **Gate before "done".** raster-qa after any raster; derivation-check after any
   artifact; render-qa after any render. A result without its provenance row does
   not exist.
5. **Write back in the same commit**: the ROADMAP section it touches, the numbers
   (both statistics where two exist), the caveats, and any new environment gotcha.
   Push.

## What counts as an experiment (and what does not)

- Every recall/enrichment ships **with its error bar**: B1's matched-footprint null,
  or validate-histmap's built-in negative control. A pass with no error bar is the
  failure this repo exists to prevent.
- **One principled change, tested once, recorded either way** — never iterate
  parameters against the controls until they pass (that is tuning, and the
  hand_mode_tolerance_m entry shows the honest form).
- Detection parameters come from the registry; sweeps record their class; scores
  and renders are class-qualified. If a command runs without `--class`, that is a
  bug, not a shortcut.
- Blocked is a finding: an item blocked on labels or a human review is recorded as
  such, never worked around by lowering the bar.

## Stop conditions

Stop after one completed, recorded iteration — or immediately when the only
runnable items are human-blocked (say which), or when an iteration's result
invalidates the plan for the next (record the fork instead of choosing silently).
