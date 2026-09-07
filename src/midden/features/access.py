"""B4: the access-bias audit. Measurement, never correction.

Excluding `dist_to_road` from the stack does not remove access bias — roads follow
terrace edges, gentle slope, and water access, so the bias re-enters through the
scored features. This module measures it: how much closer the model's top cells sit
to roads than matched chance. Correction would need survey-coverage polygons that
are not public; the measured-vs-corrected distinction stays explicit (ROADMAP B4).

`dist_to_road` remains permanently unpromotable to a scored feature — it predicts
where archaeologists have looked, not where people lived — and score.py's
FORBIDDEN_FEATURES enforces that independently of anything here.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import psycopg
import shapely
from shapely.strtree import STRtree

from midden.db import fetch_all

__all__ = ["access_bias_report"]

#: Background cells sampled for the comparison distribution. A named parameter.
BACKGROUND_SAMPLE = 2000


def _roads_tree(conn: psycopg.Connection, bounds) -> STRtree | None:
    """STRtree of road geometries intersecting the frame, or None when none loaded."""
    rows = fetch_all(
        conn,
        """SELECT ST_AsBinary(geom) AS wkb FROM ref.tiger_road
           WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 26916)""",
        bounds,
    )
    if not rows:
        return None
    return STRtree([shapely.from_wkb(bytes(r["wkb"])) for r in rows])


def _distances(tree: STRtree, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Distance from each point to its nearest road, metres."""
    points = shapely.points(xs, ys)
    nearest = tree.geometries[tree.nearest(points)]
    return shapely.distance(points, nearest)


def access_bias_report(
    conn: psycopg.Connection,
    frame: pd.DataFrame,
    *,
    top_pct: float = 5.0,
    seed: int = 42,
) -> dict[str, Any]:
    """Distance-to-road distribution of the top cells vs the frame background.

    A ratio under 1 means the top cells sit closer to roads than chance: the stack
    is laundering accessibility through its scored features, and every result
    carries that caveat. Reported on every scoring run per the B4 acceptance.
    """
    bounds = (
        frame["easting"].min(),
        frame["northing"].min(),
        frame["easting"].max(),
        frame["northing"].max(),
    )
    tree = _roads_tree(conn, bounds)
    if tree is None:
        return {
            "computable": False,
            "why": "no roads in ref.tiger_road for this frame — run "
            "`midden intake run tiger_roads --aoi <slug>`",
        }

    ranks = frame["score"].rank(pct=True).to_numpy() * 100.0
    top = frame[ranks >= 100.0 - top_pct]
    sample = frame.sample(min(BACKGROUND_SAMPLE, len(frame)), random_state=seed)

    d_top = _distances(tree, top["easting"].to_numpy(), top["northing"].to_numpy())
    d_bg = _distances(tree, sample["easting"].to_numpy(), sample["northing"].to_numpy())
    ratio = float(np.median(d_top) / max(np.median(d_bg), 1e-9))
    return {
        "computable": True,
        "top_median_m": round(float(np.median(d_top))),
        "top_q1_m": round(float(np.quantile(d_top, 0.25))),
        "background_median_m": round(float(np.median(d_bg))),
        "median_ratio": round(ratio, 2),
        "n_top": len(d_top),
        "n_background": len(d_bg),
        "reading": (
            "top cells sit CLOSER to roads than chance — the stack launders "
            "accessibility through its features; results carry that caveat"
            if ratio < 0.9
            else "top cells are no closer to roads than matched chance at this frame"
        ),
    }
