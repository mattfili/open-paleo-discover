"""Feature normalisation for the weighted overlay (spec.md §7).

Every feature is scaled to 0-1 before weighting. Pure throughout: these functions take
arrays and a spec and return arrays, so a weight set can be unit-tested without a database.

The three methods are the ones a weight set may name. Their parameter names differ between
features by design — distances use `optimum_m`/`falloff_m`, unitless indices use
`optimum`/`falloff` — so both spellings are accepted and a spec naming neither is an error
rather than a silent zero.
"""

from __future__ import annotations

from typing import Any

import numpy as np

__all__ = ["METHODS", "normalize", "normalize_categorical", "normalize_inverse_linear",
           "normalize_threshold_decay"]


def _require(spec: dict[str, Any], *names: str) -> float:
    """Return the first present key among `names`, or raise naming all of them."""
    for name in names:
        if name in spec:
            return float(spec[name])
    raise KeyError(
        f"normalize spec is missing {' or '.join(names)}; got keys {sorted(spec)}."
    )


def _slug(value: Any) -> str:
    """Fold a class label to a comparable form: lowercase, underscores, no padding."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def normalize_categorical(values: np.ndarray, spec: dict[str, Any]) -> np.ndarray:
    """Map discrete classes to scores via an explicit table.

    A class present in the data but absent from the table scores 0 and is *counted*, not
    ignored — an unmapped class is usually a weight set that has drifted from the data.
    """
    table = spec.get("values")
    if not table:
        raise KeyError("categorical normalize needs a 'values' mapping.")

    lookup = {}
    for key, score in table.items():
        try:
            lookup[float(key)] = float(score)
        except (TypeError, ValueError):
            lookup[str(key)] = float(score)

    out = np.full(values.shape, np.nan, dtype="float32")
    if values.dtype.kind in "OUS":
        # String classes, e.g. SSURGO drainage class. Normalised to snake_case so a weight
        # set can be written in one spelling and match the agency's in another.
        normalised = np.array([_slug(v) for v in values], dtype=object)
        present = normalised != ""
        for key, score in lookup.items():
            out[present & (normalised == _slug(key))] = score
        out[present & np.isnan(out)] = 0.0
        return out

    finite = np.isfinite(values)
    for key, score in lookup.items():
        if isinstance(key, float):
            out[finite & (values == key)] = score
    out[finite & np.isnan(out)] = 0.0
    return out


def normalize_inverse_linear(values: np.ndarray, spec: dict[str, Any]) -> np.ndarray:
    """Full score at an optimum, falling linearly to zero at a falloff distance.

    Below the optimum the score stays at 1: for distance to water, "closer than ideal" is
    floodplain, and that is penalised by the terrace and HAND features rather than twice
    here.
    """
    optimum = _require(spec, "optimum_m", "optimum")
    falloff = _require(spec, "falloff_m", "falloff")
    if falloff <= optimum:
        raise ValueError(f"inverse_linear needs falloff > optimum, got {falloff} <= {optimum}.")
    scaled = 1.0 - (values - optimum) / (falloff - optimum)
    return np.clip(scaled, 0.0, 1.0).astype("float32")


def normalize_threshold_decay(values: np.ndarray, spec: dict[str, Any]) -> np.ndarray:
    """Full score below a threshold, zero above a ceiling, linear between."""
    full_below = _require(spec, "full_below")
    zero_above = _require(spec, "zero_above")
    if zero_above <= full_below:
        raise ValueError(
            f"threshold_decay needs zero_above > full_below, got {zero_above} <= {full_below}."
        )
    scaled = 1.0 - (values - full_below) / (zero_above - full_below)
    return np.clip(scaled, 0.0, 1.0).astype("float32")


METHODS = {
    "categorical": normalize_categorical,
    "inverse_linear": normalize_inverse_linear,
    "threshold_decay": normalize_threshold_decay,
}


def normalize(values: np.ndarray, spec: dict[str, Any]) -> np.ndarray:
    """Apply the normalisation a feature's spec names."""
    method = spec.get("method")
    if method not in METHODS:
        raise KeyError(
            f"Unknown normalize method {method!r}. Available: {sorted(METHODS)}."
        )
    if method == "categorical" and values.dtype.kind in "OUS":
        return normalize_categorical(values, spec)
    return METHODS[method](values.astype("float64"), spec)
