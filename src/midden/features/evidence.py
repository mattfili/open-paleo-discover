"""Co-occurrence stacking: combining independent lines of contextual evidence.

The relational finding says a relationship beats a property. This is the next
question: do SEVERAL relationships compound, and by how much?

The trap is that summing more layers is the weighted overlay again — and the overlay
was measured mediocre. Evidence only compounds when the layers are INDEPENDENT.
A relict channel and a floodplain surface largely restate each other; a relict
channel and a chert source do not. So this module measures its own redundancy rather
than assuming it, and reports what each layer *added* rather than a single number
that hides the answer.

Method, stated plainly:

1. Each declared association becomes a 0-1 evidence indicator per cell — presence
   within its association distance, with a linear taper to zero at twice that
   distance (a sharp cutoff would make the combined score jump at an arbitrary line).
2. Independence is measured, not assumed: the pairwise correlation matrix of those
   indicators over the frame gives an **effective layer count**,
   `n_eff = n^2 / sum(R)` — the standard effective-sample-size form. Three perfectly
   correlated layers give n_eff = 1 and count once; three independent layers give
   n_eff = 3 and compound fully.
3. The combined evidence is the mean indicator scaled by `n_eff / n`, so redundant
   stacks cannot inflate themselves.
4. The report is the product: per-layer coverage, the correlation matrix, n_eff, and
   each layer's MARGINAL contribution (combined score with the layer held out) —
   B2's ablation logic applied to evidence instead of features.

A combined score is never a probability and never a detection: it ranks how many
independent arguments point at a place. Context detections are evidence for a class,
never detections of it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import psycopg
import shapely
from shapely.strtree import STRtree

from midden.db import fetch_all
from midden.registry import TargetClass

__all__ = ["EvidenceLayer", "evidence_report", "stack_evidence"]


class EvidenceLayer:
    """One association: a name, its indicator per cell, and where it came from."""

    def __init__(self, name: str, indicator: np.ndarray, source: str, note: str):
        self.name = name
        self.indicator = indicator
        self.source = source
        self.note = note

    @property
    def coverage(self) -> float:
        """Fraction of frame cells carrying any of this evidence."""
        return float((self.indicator > 0).mean())


def _taper(distance_m: np.ndarray, max_dist_m: float) -> np.ndarray:
    """1 inside the association distance, tapering linearly to 0 at twice it. Pure."""
    return np.clip((2.0 * max_dist_m - distance_m) / max_dist_m, 0.0, 1.0)


def _distance_to_geoms(frame: pd.DataFrame, geoms: list) -> np.ndarray:
    """Distance from every cell centre to the nearest geometry, metres."""
    if not geoms:
        return np.full(len(frame), np.inf)
    tree = STRtree(geoms)
    points = shapely.points(frame["easting"].to_numpy(), frame["northing"].to_numpy())
    nearest = tree.geometries[tree.nearest(points)]
    return shapely.distance(points, nearest)


def _class_evidence(
    conn: psycopg.Connection, frame: pd.DataFrame, spec: dict
) -> EvidenceLayer | None:
    """Evidence from a context class's catalogued detections (candidate zones)."""
    source_class = spec["source"]
    rows = fetch_all(
        conn,
        """SELECT ST_AsBinary(geom) AS wkb FROM derived.candidate_zone
           WHERE class_id = %s""",
        (source_class,),
    )
    geoms = [shapely.from_wkb(bytes(r["wkb"])) for r in rows]
    if not geoms:
        return None
    distance = _distance_to_geoms(frame, geoms)
    return EvidenceLayer(
        source_class,
        _taper(distance, float(spec["max_dist_m"])),
        f"derived.candidate_zone class={source_class}",
        spec.get("rationale", ""),
    )


def _feature_evidence(frame: pd.DataFrame, spec: dict) -> EvidenceLayer | None:
    """Evidence from a distance column already in the feature stack."""
    column = spec["source"]
    if column not in frame.columns:
        return None
    return EvidenceLayer(
        column,
        _taper(frame[column].to_numpy(dtype="float64"), float(spec["max_dist_m"])),
        f"feature stack column {column}",
        spec.get("rationale", ""),
    )


def stack_evidence(
    conn: psycopg.Connection, frame: pd.DataFrame, cls: TargetClass
) -> tuple[list[EvidenceLayer], list[dict]]:
    """Build every declared evidence layer for a class. Returns (layers, missing)."""
    specs = cls.params.get("context") or []
    layers, missing = [], []
    for spec in specs:
        kind = spec.get("kind", "class")
        layer = (
            _class_evidence(conn, frame, spec)
            if kind == "class"
            else _feature_evidence(frame, spec)
        )
        if layer is None:
            missing.append(
                {
                    "source": spec["source"],
                    "kind": kind,
                    "why": "no detections catalogued yet"
                    if kind == "class"
                    else "column not in the feature stack",
                }
            )
        else:
            layers.append(layer)
    return layers, missing


def _independence(layers: list[EvidenceLayer]) -> tuple[dict, float]:
    """Pairwise correlation of the indicators and the effective layer count. Pure.

    `n_eff = n^2 / sum(R)` is the standard effective-sample-size form: perfectly
    correlated layers collapse to one, independent layers count fully. Constant
    layers have undefined correlation and are treated as independent (0), which is
    the conservative reading for a layer that covers everything or nothing.
    """
    n = len(layers)
    if n == 0:
        return {}, 0.0
    matrix = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = layers[i].indicator, layers[j].indicator
            if a.std() < 1e-12 or b.std() < 1e-12:
                r = 0.0
            else:
                r = float(np.corrcoef(a, b)[0, 1])
                r = 0.0 if not np.isfinite(r) else r
            matrix[i, j] = matrix[j, i] = r
    total = float(np.abs(matrix).sum())
    n_eff = (n * n) / total if total > 0 else float(n)
    named = {
        layers[i].name: {
            layers[j].name: round(float(matrix[i, j]), 2) for j in range(n)
        }
        for i in range(n)
    }
    return named, min(float(n), n_eff)


def _combined(layers: list[EvidenceLayer], n_eff: float) -> np.ndarray:
    """Mean indicator scaled by the redundancy discount. Pure."""
    if not layers:
        return np.zeros(0)
    mean = np.mean([layer.indicator for layer in layers], axis=0)
    return mean * (n_eff / len(layers))


def evidence_report(
    conn: psycopg.Connection,
    frame: pd.DataFrame,
    cls: TargetClass,
    *,
    control_geom=None,
) -> dict[str, Any]:
    """Stack a class's evidence and report what each layer actually added.

    With a control footprint, also reports the evidence enrichment there — the
    honest test of whether stacking helps, since a combined score that does not
    separate a known site from its frame has compounded nothing.
    """
    layers, missing = stack_evidence(conn, frame, cls)
    if not layers:
        return {
            "class_id": cls.class_id,
            "layers": 0,
            "missing": missing,
            "verdict": "no evidence layer is available yet — declared associations "
            "exist but nothing to stack; build the context detections or "
            "features they name",
        }

    correlations, n_eff = _independence(layers)
    combined = _combined(layers, n_eff)

    def _at_control(values: np.ndarray) -> float | None:
        if control_geom is None:
            return None
        from midden.features.validate_score import cells_in_geom

        mask = cells_in_geom(frame, control_geom)
        return round(float(values[mask].mean()), 4) if mask.any() else None

    def _separation(values: np.ndarray) -> float | None:
        # The metric that matters: how far the control sits ABOVE its own frame. A
        # raw mean delta is dominated by coverage — a layer present on 98% of cells
        # moves the mean hugely while distinguishing nothing (found by running it).
        at_control = _at_control(values)
        return (
            None if at_control is None else round(at_control - float(values.mean()), 4)
        )

    full_separation = _separation(combined)
    marginal = {}
    for i, layer in enumerate(layers):
        held_out = layers[:i] + layers[i + 1 :]
        if held_out:
            _, n_eff_out = _independence(held_out)
            without = _combined(held_out, n_eff_out)
            without_separation = _separation(without)
        else:
            without, without_separation = np.zeros(len(frame)), 0.0
        marginal[layer.name] = {
            "separation_without": without_separation,
            "separation_delta": (
                None
                if full_separation is None or without_separation is None
                else round(full_separation - without_separation, 4)
            ),
            "frame_mean_delta": round(float(combined.mean() - without.mean()), 4),
        }

    return {
        "class_id": cls.class_id,
        "layers": [
            {
                "name": layer.name,
                "source": layer.source,
                "coverage": round(layer.coverage, 3),
                "rationale": layer.note,
            }
            for layer in layers
        ],
        "missing": missing,
        "correlations": correlations,
        "n_layers": len(layers),
        "n_effective": round(n_eff, 2),
        "redundancy_discount": round(n_eff / len(layers), 2),
        "combined_frame_mean": round(float(combined.mean()), 4),
        "combined_at_control": _at_control(combined),
        "separation": full_separation,
        "marginal_contribution": marginal,
        "how_to_read": (
            "n_effective is how many INDEPENDENT layers the stack really carries: "
            "correlated layers collapse toward 1 and cannot inflate the score. "
            "separation is the control's value MINUS its frame mean: the only "
            "number that says the stack distinguishes a site rather than describing "
            "the landscape. marginal is each layer held out, scored on separation, "
            "so a layer covering most of the frame cannot look important by volume. "
            "This ranks how many independent arguments point at a place; it is not a "
            "probability, and context evidence is never a detection of the class."
        ),
    }
