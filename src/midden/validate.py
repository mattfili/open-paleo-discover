"""The vanished-feature test (ROADMAP A2).

Symbols digitized from a historic quad are dated, public ground truth that is independent
of the model. This module runs the 0.5 m detection chain over them and asks, per symbol:
did anything fire within the symbol's positional tolerance?

The firing rule — the piece that did not exist before this module; detection previously
meant "produce rasters for a human to look at":

    A symbol HITS on a surface when a connected cluster of at least `min_cells` cells
    inside the tolerance disc lies beyond `threshold_pctile` of the surrounding
    background, in the tail (high/low) that the class's morphology predicts. The disc
    radius is the point's recorded `positional_confidence_m` — a hit inside a tolerance
    that was never recorded is not a hit — and the background is an annulus around the
    disc, so the threshold is local ground, not the whole AOI.

Misses are the point: a mapped symbol with nothing detectable is a genuine miss, and
misses are what let recall be estimated. A miss can mean the feature is truly gone,
buried, below the radius swept for the class, or mislocated by the digitization — the
report says so rather than collapsing those.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import psycopg
import rasterio
import rasterio.windows
import shapely
from scipy import ndimage

from midden.db import fetch_all
from midden.registry import TargetClass, detect_params, get_class

__all__ = ["SymbolResult", "ensure_detection", "validate_histmap"]

#: Radius of the background annulus around each symbol, metres. A judgment call, so it
#: is a named parameter recorded in every validate derivation.
BACKGROUND_RADIUS_M = 500.0

#: Padding added around a point cluster when cutting its validation AOI, metres. At
#: least the background radius, so every symbol's annulus is computed on real ground.
AOI_PAD_M = BACKGROUND_RADIUS_M + 100.0


@dataclass(frozen=True, slots=True)
class SymbolResult:
    """One symbol's outcome against every surface of its class's firing rule."""

    site_id: int
    name: str
    tolerance_m: float
    review_status: str
    hit: bool
    fired_surfaces: tuple[str, ...]
    detail: dict[str, dict[str, Any]]  # surface -> {pctile_max, cluster_cells, valid}


def _cluster_points(
    points: list[dict], pad_m: float
) -> list[tuple[shapely.Geometry, list[dict]]]:
    """Group symbols into spatial clusters and return (envelope, members) per cluster.

    Points whose padded discs touch share a cluster, so one detection run covers them;
    scattered symbols get separate small AOIs instead of one giant rectangle that would
    trip the 25 km2 detection guard.
    """
    geoms = [shapely.Point(p["x"], p["y"]).buffer(pad_m) for p in points]
    merged = shapely.union_all(geoms)
    parts = (
        shapely.get_parts(merged) if merged.geom_type == "MultiPolygon" else [merged]
    )
    clusters = []
    for part in parts:
        members = [p for p, g in zip(points, geoms) if g.intersects(part)]
        clusters.append((shapely.envelope(part), members))
    return clusters


def _load_points(conn: psycopg.Connection, sheet_id: str, class_id: str) -> list[dict]:
    """Load the sheet's symbols for one class, rejected labels excluded."""
    rows = fetch_all(
        conn,
        """
        SELECT site_id, name, positional_confidence_m, review_status,
               ST_X(geom) AS x, ST_Y(geom) AS y
        FROM ref.control_sites
        WHERE source_sheet = %s AND class_id = %s AND review_status <> 'rejected'
        ORDER BY site_id
        """,
        (sheet_id, class_id),
    )
    if not rows:
        raise ValueError(
            f"No control points for class {class_id!r} on sheet {sheet_id!r}. "
            "Digitize and `midden histmap load-sites` first, or pick another class."
        )
    return rows


def ensure_detection(
    conn: psycopg.Connection, aoi, cls: TargetClass, *, ept_project: str, config
) -> dict[str, Path]:
    """Return the AOI's detection surfaces for a class, deriving them if absent."""
    from midden.terrain.cog import list_assets
    from midden.terrain.run import run_detection_grid

    surfaces = detect_params(cls)["surfaces"]

    def _catalogued() -> dict[str, Path]:
        rows = list_assets(conn, aoi_id=aoi.id)
        return {
            r["kind"]: Path(r["path"])
            for r in rows
            if r["kind"] in surfaces and (r["variant"] or "") == cls.class_id
        }

    have = _catalogued()
    if set(have) != set(surfaces):
        run_detection_grid(
            conn, aoi, ept_project=ept_project, class_id=cls.class_id, config=config
        )
        have = _catalogued()
    missing = set(surfaces) - set(have)
    if missing:
        raise RuntimeError(
            f"{aoi.slug}: detection ran but surfaces {sorted(missing)} are not in the "
            "catalog — the chain produced different kinds than the registry expects."
        )
    return have


def _disc_masks(
    src: rasterio.DatasetReader, x: float, y: float, r_disc: float, r_bg: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Read the window around a point and return (values, disc_mask, annulus_mask).

    Returns None when the point falls outside the raster entirely. Masks exclude
    nodata; partial coverage at the AOI edge shows up as fewer valid cells, which the
    caller reports rather than hides.
    """
    row, col = src.index(x, y)
    half = int(np.ceil(r_bg / src.res[0]))
    window = rasterio.windows.Window(col - half, row - half, 2 * half + 1, 2 * half + 1)
    clipped = window.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
    if clipped.width <= 0 or clipped.height <= 0:
        return None
    values = src.read(1, window=clipped, masked=True)
    transform = src.window_transform(clipped)
    rows_idx, cols_idx = np.mgrid[0 : values.shape[0], 0 : values.shape[1]]
    # Cell-centre coordinates from the affine directly: rasterio.transform.xy
    # flattens 2D index arrays, which breaks the mask broadcasting downstream.
    xs = transform.c + (cols_idx + 0.5) * transform.a + (rows_idx + 0.5) * transform.b
    ys = transform.f + (cols_idx + 0.5) * transform.d + (rows_idx + 0.5) * transform.e
    dist = np.hypot(xs - x, ys - y)
    valid = ~values.mask if np.ma.is_masked(values) else np.ones(values.shape, bool)
    return values, (dist <= r_disc) & valid, (dist > r_disc) & (dist <= r_bg) & valid


def _fire_on_surface(
    values: np.ma.MaskedArray,
    disc: np.ndarray,
    annulus: np.ndarray,
    *,
    tail: str,
    threshold_pctile: float,
    min_cells: int,
) -> dict[str, Any]:
    """Apply the firing rule on one surface. Pure.

    `tail` is which extreme the class's morphology lives in: a mill race is LOW in SLRM
    (a cut) but HIGH in negative openness (concave). The threshold is a percentile of
    the annulus (local background), and the hit requires a connected cluster of
    `min_cells` beyond it inside the disc — one lucky cell proves nothing.
    """
    data = np.ma.filled(values, np.nan)
    bg = data[annulus]
    disc_vals = data[disc]
    if bg.size < 100 or disc_vals.size < min_cells:
        return {"valid": False, "why": "insufficient valid cells (AOI edge or nodata)"}

    if tail == "high":
        cut = np.nanpercentile(bg, threshold_pctile)
        beyond = np.where(disc, data >= cut, False)
        extreme = float(np.nanmax(disc_vals))
        pctile = float((bg < extreme).mean() * 100.0)
    else:
        cut = np.nanpercentile(bg, 100.0 - threshold_pctile)
        beyond = np.where(disc, data <= cut, False)
        extreme = float(np.nanmin(disc_vals))
        pctile = float((bg > extreme).mean() * 100.0)

    labelled, n = ndimage.label(np.nan_to_num(beyond.astype(float)) > 0)
    largest = int(np.bincount(labelled.ravel())[1:].max()) if n else 0
    return {
        "valid": True,
        "fired": largest >= min_cells,
        "cluster_cells": largest,
        "pctile_max": round(pctile, 1),
    }


def _evaluate_symbol(
    point: dict, surfaces: dict[str, Path], tails: dict[str, str], detect: dict
) -> SymbolResult:
    """Run the firing rule for one symbol across its class's surfaces."""
    detail: dict[str, dict[str, Any]] = {}
    fired = []
    tolerance = float(point["positional_confidence_m"])
    for kind, path in surfaces.items():
        with rasterio.open(path) as src:
            masks = _disc_masks(
                src, point["x"], point["y"], tolerance, BACKGROUND_RADIUS_M
            )
        if masks is None:
            detail[kind] = {"valid": False, "why": "outside raster"}
            continue
        outcome = _fire_on_surface(
            *masks,
            tail=tails[kind],
            threshold_pctile=float(detect["threshold_pctile"]),
            min_cells=int(detect["min_cells"]),
        )
        detail[kind] = outcome
        if outcome.get("fired"):
            fired.append(kind)
    return SymbolResult(
        site_id=point["site_id"],
        name=point["name"],
        tolerance_m=tolerance,
        review_status=point["review_status"],
        hit=bool(fired),
        fired_surfaces=tuple(fired),
        detail=detail,
    )


def validate_histmap(
    conn: psycopg.Connection,
    sheet_id: str,
    class_id: str,
    *,
    ept_project: str,
    aoi_slug: str | None = None,
    config=None,
) -> dict[str, Any]:
    """Run the vanished-feature test for one class on one sheet.

    Returns the full report dict; also writes a `validate.histmap` derivation row so
    the recall number is reproducible. Cuts `control_detection` AOIs around the
    symbol clusters unless an existing AOI is named.
    """
    from midden import __version__
    from midden.aoi import SeedSpec, get_aoi, to_multipolygon, upsert_aoi
    from midden.config import settings
    from midden.derivation import open_derivation

    config = config or settings()
    cls = get_class(conn, class_id)
    detect = detect_params(cls)
    tails = dict(detect["surfaces"])
    points = _load_points(conn, sheet_id, class_id)
    scan_id = sheet_id.split("_")[-3] if sheet_id.count("_") >= 3 else sheet_id

    if aoi_slug:
        clusters = [(get_aoi(conn, aoi_slug).geom, points)]
    else:
        clusters = _cluster_points(points, AOI_PAD_M)

    results: list[SymbolResult] = []
    aois_used: list[str] = []
    with open_derivation(
        conn,
        operation="validate.histmap",
        tool="midden.validate",
        tool_version=__version__,
        params={
            "sheet_id": sheet_id,
            "class_id": class_id,
            "n_symbols": len(points),
            "background_radius_m": BACKGROUND_RADIUS_M,
            "aoi_pad_m": AOI_PAD_M,
            **{k: detect[k] for k in ("surfaces", "threshold_pctile", "min_cells")},
        },
        inputs=[sheet_id],
    ) as derivation_id:
        for i, (envelope, members) in enumerate(clusters):
            if aoi_slug:
                area = get_aoi(conn, aoi_slug)
            else:
                slug = f"histmap-{scan_id}-{class_id.replace('_', '-')}-{i}"
                multipolygon, _ = to_multipolygon(envelope, slug=slug)
                upsert_aoi(
                    conn,
                    SeedSpec(
                        slug=slug,
                        name=f"validate {class_id} on {sheet_id} #{i}",
                        county="",
                        kind="custom",
                        role="control_detection",
                        layer=f"validate.histmap derivation {derivation_id}",
                        where="",
                    ),
                    multipolygon,
                )
                area = get_aoi(conn, slug)
            aois_used.append(area.slug)
            try:
                surfaces = ensure_detection(
                    conn, area, cls, ept_project=ept_project, config=config
                )
            except RuntimeError as exc:
                # A cluster with no EPT points (coverage seam) is a data gap, not a
                # miss and not a reason to lose the clusters that did run. Its
                # symbols are excluded from recall and reported explicitly.
                why = f"detection failed for {area.slug}: {exc}".splitlines()[0]
                results.extend(
                    SymbolResult(
                        site_id=p["site_id"],
                        name=p["name"],
                        tolerance_m=float(p["positional_confidence_m"]),
                        review_status=p["review_status"],
                        hit=False,
                        fired_surfaces=(),
                        detail={"detection": {"valid": False, "why": why}},
                    )
                    for p in members
                )
                continue
            results.extend(
                _evaluate_symbol(p, surfaces, tails, detect) for p in members
            )

        evaluable = [
            r for r in results if any(d.get("valid") for d in r.detail.values())
        ]
        hits = [r for r in evaluable if r.hit]
        recall = len(hits) / len(evaluable) if evaluable else float("nan")
        conn.execute(
            "UPDATE derived.derivation SET params = params || %s::jsonb WHERE id = %s",
            (
                json.dumps(
                    {
                        "recall": round(recall, 3) if evaluable else None,
                        "hits": len(hits),
                        "evaluable": len(evaluable),
                        "misses": [r.name for r in evaluable if not r.hit],
                        "aois": aois_used,
                    }
                ),
                derivation_id,
            ),
        )

    return {
        "sheet_id": sheet_id,
        "class_id": class_id,
        "derivation_id": derivation_id,
        "aois": aois_used,
        "results": results,
        "evaluable": len(evaluable),
        "hits": len(hits),
        "recall": recall,
        "unreviewed": sum(1 for r in results if r.review_status == "unreviewed"),
    }
