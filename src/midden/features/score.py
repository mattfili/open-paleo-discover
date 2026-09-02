"""Weighted-overlay suitability scoring (spec.md §7).

A weighted overlay is a hypothesis, not a measurement. Its only claim to validity is
whether it ranks known sites highly, which is what `control_check.py` tests.

Two rules the implementation enforces rather than trusts:

1. **A weight set naming a feature the stack does not have is an error.** Silently
   dropping it and renormalising the remaining weights would change the hypothesis without
   saying so, and the result would look like a finding.
2. **`burial_risk` is never summed into the score.** It rides alongside as a companion
   band, because a cell scores low either because the landform is wrong or because
   anything there is under metres of overbank silt, and collapsing those two into one
   number destroys the only genuinely useful distinction in the output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

import numpy as np
import pandas as pd
import rasterio
import yaml

from midden.features.normalize import normalize

__all__ = ["ScoreResult", "WeightSet", "load_weights", "score_stack", "write_score_raster"]

#: Features that must never be scored, whatever a weight set says. `dist_to_road`
#: correlates with the survey record rather than the archaeological one — it is the
#: fastest way to build a model that predicts where archaeologists have already been.
FORBIDDEN_FEATURES = frozenset({"dist_to_road", "dist_to_roads", "distance_to_road"})


class WeightSet(NamedTuple):
    """A parsed weight set."""

    name: str
    description: str
    features: dict[str, dict[str, Any]]
    companion_bands: dict[str, Any]
    path: Path

    @property
    def scored_features(self) -> dict[str, dict[str, Any]]:
        """Features with a non-zero weight. Zero-weighted entries document a decision."""
        return {
            name: spec for name, spec in self.features.items()
            if float(spec.get("weight", 0.0)) > 0.0
        }


class ScoreResult(NamedTuple):
    """A scored stack and the provenance of the scoring."""

    frame: pd.DataFrame
    weights: dict[str, float]
    weight_set: str
    contributions: dict[str, float]


def load_weights(path: Path) -> WeightSet:
    """Parse a weight-set YAML, rejecting anything that must never be scored."""
    raw = yaml.safe_load(path.read_text())
    features = raw.get("features") or {}

    forbidden = FORBIDDEN_FEATURES & set(features)
    if forbidden:
        raise ValueError(
            f"{path}: weight set names {sorted(forbidden)}, which must never be scored. "
            f"Distance to road correlates with where archaeologists have looked, not with "
            f"where people lived."
        )
    return WeightSet(
        name=raw.get("name", path.stem),
        description=raw.get("description", ""),
        features=features,
        companion_bands=raw.get("companion_bands") or {},
        path=path,
    )


def score_stack(frame: pd.DataFrame, weight_set: WeightSet) -> ScoreResult:
    """Apply a weight set to a feature stack, returning the frame with a `score` column.

    Weights are relative and normalised here, so a weight set need not sum to 1.
    """
    scored = weight_set.scored_features
    if not scored:
        raise ValueError(f"{weight_set.path}: no feature carries a non-zero weight.")

    missing = [name for name in scored if name not in frame.columns]
    if missing:
        raise ValueError(
            f"{weight_set.path}: the stack has no column(s) {missing}. Available: "
            f"{sorted(c for c in frame.columns if c not in ('easting', 'northing'))}. "
            f"Dropping them silently would change the hypothesis without saying so — "
            f"either derive the missing feature or use a weight set that does not name it."
        )

    total = sum(float(spec["weight"]) for spec in scored.values())
    weights = {name: float(spec["weight"]) / total for name, spec in scored.items()}

    out = frame.copy()
    accumulated = np.zeros(len(out), dtype="float64")
    contributions: dict[str, float] = {}
    for name, spec in scored.items():
        component = normalize(out[name].to_numpy(), spec["normalize"])
        out[f"norm_{name}"] = component
        accumulated += weights[name] * np.nan_to_num(component, nan=0.0)
        contributions[name] = float(np.nanmean(component) * weights[name])

    out["score"] = accumulated.astype("float32")
    out["score_pct"] = out["score"].rank(pct=True).astype("float32") * 100.0
    return ScoreResult(out, weights, weight_set.name, contributions)


def write_score_raster(
    frame: pd.DataFrame, template: Path, dest: Path, column: str = "score"
) -> Path:
    """Burn a scored stack back onto the modelling grid as a raster.

    A raster rather than a table because that is what `control_check.py` consumes: it
    clips the surface by each published control footprint and reports a percentile rank.
    """
    with rasterio.open(template) as src:
        profile = src.profile.copy()
        transform = src.transform
        height, width = src.height, src.width

    rows, cols = rasterio.transform.rowcol(transform, frame.easting, frame.northing)
    grid = np.full((height, width), np.nan, dtype="float32")
    grid[np.asarray(rows), np.asarray(cols)] = frame[column].to_numpy(dtype="float32")

    profile.update(
        driver="GTiff", dtype="float32", count=1, nodata=np.nan,
        compress="DEFLATE", tiled=True, blockxsize=256, blockysize=256,
    )
    profile.pop("predictor", None)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dest, "w", **profile) as handle:
        handle.write(grid, 1)
    return dest
