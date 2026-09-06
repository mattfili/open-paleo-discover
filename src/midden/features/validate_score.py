"""B1 and B2: the permutation test and feature ablation (ROADMAP §6).

B1 replaces the pass/fail percentile threshold with an effect size and an error bar.
The unit of permutation is the whole footprint, never the cell (spatial-validation §1):
cells are spatially autocorrelated, so shuffling them produces p-values that are
confidently too small. The null here translates (and right-angle-rotates) the actual
control footprint to random positions inside the background frame, keeping its area
and shape, and accepts a draw only when its landform composition matches the
control's — otherwise the test answers "are terraces different from channels", which
is already known, rather than "is this location special".

The background frame (B5) is the AOI's regional buffered extent — the same frame the
regional score surface is computed on — and is recorded in every derivation.

B2 refits the overlay with each feature held out (weights renormalised) and reports
the delta in the control statistic, with the same footprint-level null on each refit
surface. Two recorded traps: correlated features share signal, so a small solo delta
is not "no signal" (the correlation matrix ships with the result), and a feature
whose removal *raises* enrichment is actively harmful — the quantitative form of the
terrace_class finding.

Empirical p is (r+1)/(k+1): k draws can bound a rate, never prove zero.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import shapely
import shapely.affinity

__all__ = [
    "ablate",
    "cells_in_geom",
    "footprint_stats",
    "normalized_correlations",
    "permutation_test",
]

#: HAND cut separating valley bottom from upland for landform matching, metres.
#: A judgment call, so it is a named parameter recorded in every derivation.
LOWLAND_HAND_CUT_M = 15.0

#: Maximum difference in lowland fraction between a null footprint and the control
#: for the draw to count as landform-matched.
LOWLAND_MATCH_TOL = 0.15


def cells_in_geom(frame: pd.DataFrame, geom) -> np.ndarray:
    """Boolean mask of stack cells whose centres fall inside a geometry. Pure."""
    x = frame["easting"].to_numpy()
    y = frame["northing"].to_numpy()
    xmin, ymin, xmax, ymax = shapely.bounds(geom)
    candidate = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
    mask = np.zeros(len(frame), dtype=bool)
    if candidate.any():
        mask[candidate] = shapely.contains_xy(geom, x[candidate], y[candidate])
    return mask


def footprint_stats(
    scores: np.ndarray, ranks_pct: np.ndarray, top5_cut: float, mask: np.ndarray
) -> dict[str, float]:
    """Mean percentile and top-5% enrichment of one footprint. Pure.

    Mean rather than max, as in control_check.py: one lucky cell proves nothing.
    Enrichment is (fraction of footprint cells in the global top 5%) / 0.05 — the
    Kvamme-gain-style ratio the 2026-09-02 diagnosis reported (4.0x at mound-bottom).
    """
    n = int(mask.sum())
    if n == 0:
        return {"n_cells": 0, "pct_mean": float("nan"), "top5_enrich": float("nan")}
    return {
        "n_cells": n,
        "pct_mean": float(ranks_pct[mask].mean()),
        "top5_enrich": float((scores[mask] >= top5_cut).mean() / 0.05),
    }


def _lowland_fraction(hand: np.ndarray, mask: np.ndarray) -> float:
    """Fraction of a footprint's cells with HAND below the lowland cut. Pure."""
    if not mask.any():
        return float("nan")
    values = hand[mask]
    valid = np.isfinite(values)
    return (
        float((values[valid] < LOWLAND_HAND_CUT_M).mean())
        if valid.any()
        else float("nan")
    )


def _null_masks(
    rng: np.random.Generator,
    frame: pd.DataFrame,
    control_geom,
    *,
    k: int,
    target_lowland: float,
    min_cells: int,
    max_tries: int,
):
    """Yield up to k matched null-footprint masks. See module docstring for why
    the unit is the footprint and why draws are landform-matched."""
    hand = frame["hand_m"].to_numpy()
    fx0, fy0 = frame["easting"].min(), frame["northing"].min()
    fx1, fy1 = frame["easting"].max(), frame["northing"].max()
    gx0, gy0, gx1, gy1 = shapely.bounds(control_geom)
    produced = 0
    for _ in range(max_tries):
        if produced >= k:
            return
        geom = control_geom
        if rng.integers(4):  # right-angle rotations keep area and cell alignment
            geom = shapely.affinity.rotate(
                geom, int(rng.integers(1, 4)) * 90, origin="centroid"
            )
        rx0, ry0, rx1, ry1 = shapely.bounds(geom)
        if fx1 - fx0 <= rx1 - rx0 or fy1 - fy0 <= ry1 - ry0:
            return  # control larger than frame; no null is drawable
        dx = rng.uniform(fx0 - rx0, fx1 - rx1)
        dy = rng.uniform(fy0 - ry0, fy1 - ry1)
        candidate = shapely.affinity.translate(geom, dx, dy)
        mask = cells_in_geom(frame, candidate)
        if mask.sum() < min_cells:
            continue  # fell across a frame hole or edge
        if not np.isfinite(target_lowland):
            pass  # control has no HAND signal to match on; accept by area alone
        elif abs(_lowland_fraction(hand, mask) - target_lowland) > LOWLAND_MATCH_TOL:
            continue
        produced += 1
        yield mask


def permutation_test(
    frame: pd.DataFrame,
    control_geom,
    *,
    draws: int = 199,
    seed: int = 42,
) -> dict[str, Any]:
    """B1 for one control footprint on one scored frame. Pure given its inputs.

    Returns observed stats, the null distribution summary, and empirical p for both
    statistics (one-sided: null >= observed).
    """
    scores = frame["score"].to_numpy()
    ranks_pct = frame["score"].rank(pct=True).to_numpy() * 100.0
    top5_cut = float(np.percentile(scores, 95))
    hand = frame["hand_m"].to_numpy()

    observed_mask = cells_in_geom(frame, control_geom)
    observed = footprint_stats(scores, ranks_pct, top5_cut, observed_mask)
    if observed["n_cells"] == 0:
        return {"observed": observed, "error": "control footprint outside the frame"}

    rng = np.random.default_rng(seed)
    target_lowland = _lowland_fraction(hand, observed_mask)
    null_pct, null_enr = [], []
    for mask in _null_masks(
        rng,
        frame,
        control_geom,
        k=draws,
        target_lowland=target_lowland,
        min_cells=max(10, int(observed["n_cells"] * 0.9)),
        max_tries=draws * 60,
    ):
        stats = footprint_stats(scores, ranks_pct, top5_cut, mask)
        null_pct.append(stats["pct_mean"])
        null_enr.append(stats["top5_enrich"])

    k_eff = len(null_pct)
    result = {
        "observed": observed,
        "control_lowland_fraction": round(target_lowland, 3)
        if np.isfinite(target_lowland)
        else None,
        "null_draws": k_eff,
        "requested_draws": draws,
        "lowland_hand_cut_m": LOWLAND_HAND_CUT_M,
        "lowland_match_tol": LOWLAND_MATCH_TOL,
        "seed": seed,
    }
    if k_eff == 0:
        result["error"] = "no matched null footprint could be drawn from this frame"
        return result
    pct = np.array(null_pct)
    enr = np.array(null_enr)
    result["null"] = {
        "pct_mean": {
            "mean": round(float(pct.mean()), 1),
            "sd": round(float(pct.std()), 1),
            "q05": round(float(np.quantile(pct, 0.05)), 1),
            "q95": round(float(np.quantile(pct, 0.95)), 1),
        },
        "top5_enrich": {
            "mean": round(float(enr.mean()), 2),
            "sd": round(float(enr.std()), 2),
            "q95": round(float(np.quantile(enr, 0.95)), 2),
        },
    }
    result["p_pct_mean"] = round(
        (int((pct >= observed["pct_mean"]).sum()) + 1) / (k_eff + 1), 4
    )
    result["p_top5_enrich"] = round(
        (int((enr >= observed["top5_enrich"]).sum()) + 1) / (k_eff + 1), 4
    )
    return result


def normalized_correlations(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Correlation matrix of the normalised scored features. Pure.

    Ships with every ablation: correlated features share signal, so a small solo
    ablation delta can mean "shared", never only "absent".
    """
    cols = [c for c in frame.columns if c.startswith("norm_")]
    corr = frame[cols].corr()

    def cell(a: str, b: str):
        # A constant feature (e.g. uniformly well-drained soils) has no defined
        # correlation; None survives JSON where NaN does not.
        v = float(corr.loc[a, b])
        return round(v, 2) if np.isfinite(v) else None

    return {
        a.removeprefix("norm_"): {b.removeprefix("norm_"): cell(a, b) for b in cols}
        for a in cols
    }


def ablate(
    raw_frame: pd.DataFrame,
    weight_set,
    control_geoms: dict[str, Any],
    *,
    draws: int = 99,
    seed: int = 42,
) -> dict[str, Any]:
    """B2: hold each scored feature out, refit, and re-run B1 per control.

    Returns per-feature, per-control observed pct_mean, its delta against the full
    model, and the ablated surface's own empirical p — the same footprint-level null
    on every refit surface, never a shared one.
    """
    from midden.features.score import WeightSet, score_stack

    full = score_stack(raw_frame, weight_set)
    baseline = {}
    for slug, geom in control_geoms.items():
        baseline[slug] = permutation_test(full.frame, geom, draws=draws, seed=seed)

    ablations: dict[str, Any] = {}
    for name in weight_set.scored_features:
        remaining = {k: v for k, v in weight_set.features.items() if k != name}
        reduced = WeightSet(
            name=f"{weight_set.name} minus {name}",
            description=f"ablation: {name} held out",
            features=remaining,
            companion_bands=weight_set.companion_bands,
            path=weight_set.path,
        )
        refit = score_stack(raw_frame, reduced)
        per_control = {}
        for slug, geom in control_geoms.items():
            outcome = permutation_test(refit.frame, geom, draws=draws, seed=seed)
            base = baseline[slug]
            per_control[slug] = {
                "pct_mean": outcome["observed"]["pct_mean"],
                "delta_pct_mean": round(
                    outcome["observed"]["pct_mean"] - base["observed"]["pct_mean"], 1
                ),
                "top5_enrich": outcome["observed"]["top5_enrich"],
                "delta_top5_enrich": round(
                    outcome["observed"]["top5_enrich"]
                    - base["observed"]["top5_enrich"],
                    2,
                ),
                "p_pct_mean": outcome.get("p_pct_mean"),
            }
        ablations[name] = per_control

    return {
        "baseline": baseline,
        "ablations": ablations,
        "correlations": normalized_correlations(full.frame),
        "draws": draws,
        "seed": seed,
    }
