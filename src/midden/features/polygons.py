"""F1: the top percentile of a class's score surface as ranked polygons.

"A ranked set of polygons worth walking" is the README's promise and this is the
half that turns a raster into it. The other half — F2, effort-constrained survey
ordering — builds on these rows.

Rules carried from the invariants:

- Every zone is class-qualified; there is no unqualified candidate.
- `burial_risk` rides as a separate attribute, never summed: a low-scoring buried
  cell and a low-scoring wrong cell are different findings, and a HIGH-scoring zone
  with high burial risk means "right landform, invisible to LiDAR" — walk it with a
  probe, not a quadcopter.
- Ranking is by mean cell percentile (the same statistic the validation machinery
  uses), tie-broken by area: a big merely-good zone should not outrank a small
  excellent one on bulk alone.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import psycopg
import shapely
import shapely.geometry

__all__ = ["build_zones", "store_zones"]

#: Cell edge on the model grid, metres. Zones are unions of 10 m cells.
CELL_M = 10.0


def build_zones(
    frame: pd.DataFrame, *, top_pct: float = 5.0, min_cells: int = 4
) -> list[dict[str, Any]]:
    """Polygonise the top `top_pct` percent of scored cells into ranked zones. Pure.

    Cells are squares on the model grid; touching top-percentile cells merge into one
    zone. Zones under `min_cells` are dropped — a single hot cell is the raster
    equivalent of one lucky anomaly, and the discipline says one anomaly is not a
    finding.
    """
    ranks = frame["score"].rank(pct=True).to_numpy() * 100.0
    cut = 100.0 - top_pct
    top = frame[ranks >= cut].copy()
    top["pct"] = ranks[ranks >= cut]
    if top.empty:
        return []

    half = CELL_M / 2.0
    boxes = [
        shapely.geometry.box(x - half, y - half, x + half, y + half)
        for x, y in zip(top["easting"], top["northing"])
    ]
    merged = shapely.union_all(boxes)
    parts = (
        list(shapely.get_parts(merged))
        if merged.geom_type == "MultiPolygon"
        else [merged]
    )

    xs = top["easting"].to_numpy()
    ys = top["northing"].to_numpy()
    zones = []
    for part in parts:
        inside = shapely.contains_xy(part, xs, ys)
        n = int(inside.sum())
        if n < min_cells:
            continue
        members = top[inside]
        zones.append(
            {
                "geom_wkt": part.wkt,
                "area_m2": float(part.area),
                "n_cells": n,
                "score_mean": round(float(members["score"].mean()), 4),
                "score_max": round(float(members["score"].max()), 4),
                "pct_mean": round(float(members["pct"].mean()), 1),
                "hand_mean_m": round(float(members["hand_m"].mean()), 1)
                if "hand_m" in members
                else None,
                "burial_risk": round(float(members["burial_risk"].mean()), 2)
                if "burial_risk" in members
                and np.isfinite(members["burial_risk"]).any()
                else None,
            }
        )

    zones.sort(key=lambda z: (-z["pct_mean"], -z["area_m2"]))
    for rank, zone in enumerate(zones, start=1):
        zone["rank"] = rank
    return zones


def store_zones(
    conn: psycopg.Connection,
    aoi,
    class_id: str,
    zones: list[dict[str, Any]],
    *,
    derivation_id: int,
) -> int:
    """Replace this (aoi, class)'s zones with a fresh ranked set."""
    conn.execute(
        "DELETE FROM derived.candidate_zone WHERE aoi_id = %s AND class_id = %s",
        (aoi.id, class_id),
    )
    for z in zones:
        conn.execute(
            """
            INSERT INTO derived.candidate_zone
                (aoi_id, class_id, rank, area_m2, score_mean, score_max, pct_mean,
                 hand_mean_m, burial_risk, geom, derivation_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                    ST_GeomFromText(%s, 26916), %s)
            """,
            (
                aoi.id,
                class_id,
                z["rank"],
                z["area_m2"],
                z["score_mean"],
                z["score_max"],
                z["pct_mean"],
                z["hand_mean_m"],
                z["burial_risk"],
                z["geom_wkt"],
                derivation_id,
            ),
        )
    return len(zones)
