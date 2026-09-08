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
    disc_m: float  # tolerance + the class's feature radius: the disc actually searched
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
        # Seam-aware project selection: EPT coverage is a patchwork whose true
        # footprints live in the published boundary index, NOT in a project's own
        # cube bounds. Try the covering candidates in order so a cluster on a block
        # seam reaches the neighbouring collection instead of reporting a false gap.
        from midden.terrain.coverage import covering_projects
        from midden.terrain.dem import buffered_bounds

        candidates = covering_projects(
            buffered_bounds(aoi, 50.0), config.raw_dir, prefer=ept_project
        ) or [ept_project]
        failures = []
        for candidate in candidates:
            try:
                run_detection_grid(
                    conn,
                    aoi,
                    ept_project=candidate,
                    class_id=cls.class_id,
                    config=config,
                )
            except RuntimeError as exc:
                failures.append(f"{candidate}: {str(exc).splitlines()[0]}")
                continue
            have = _catalogued()
            if set(have) == set(surfaces):
                break
        if set(have) != set(surfaces) and failures:
            raise RuntimeError(
                f"{aoi.slug}: no covering EPT project produced points. Tried "
                + "; ".join(failures)
            )
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
    try:
        clipped = window.intersection(
            rasterio.windows.Window(0, 0, src.width, src.height)
        )
    except rasterio.windows.WindowError:
        # rasterio RAISES on an empty intersection rather than returning a
        # zero-size window — happens on sliver rasters at an EPT coverage edge.
        return None
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
    detect: dict | None = None,
    kind: str = "",
) -> dict[str, Any]:
    """Apply the firing rule on one surface. Pure.

    `tail` is which extreme the class's morphology lives in: a mill race is LOW in SLRM
    (a cut) but HIGH in negative openness (concave). The threshold is a percentile of
    the annulus (local background), and the hit requires a connected cluster of
    `min_cells` beyond it inside the disc that also passes the class's shape gates
    (`_cluster_qualifies`) — one lucky cell proves nothing, and neither does a gully.
    """
    detect = detect or {}
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

    clusters = _cluster_morphometry(beyond)
    largest = max((c["cells"] for c in clusters), default=0)
    result: dict[str, Any] = {
        "valid": True,
        "cluster_cells": largest,
        "pctile_max": round(pctile, 1),
    }
    multi = detect.get("multi")
    if multi and multi.get("surface") == kind:
        # Multi-element classes fire on arrangement, not on any single cluster:
        # one big blob at cemetery scale is exactly the wrong shape.
        outcome = _multi_satisfied(clusters, multi)
        result["multi"] = outcome
        result["fired"] = outcome["satisfied"]
        return result
    qualifying = [c for c in clusters if _cluster_qualifies(c, detect, min_cells)]
    result["fired"] = bool(qualifying)
    result["clusters"] = qualifying[:5]
    return result


def _cluster_morphometry(beyond: np.ndarray) -> list[dict[str, Any]]:
    """Connected clusters of beyond-threshold cells, with shape metrics. Pure.

    Elongation is the square root of the covariance eigenvalue ratio of the cluster's
    cell coordinates — 1.0 for a disc, large for a gully. This is the metric that
    separates the background's linear texture (drainage, roadbeds) from the compact
    anomalies most classes predict: the recorded false-fires (Jackson Cem's creek,
    94% background rates) were overwhelmingly linear.
    """
    labelled, n = ndimage.label(np.nan_to_num(beyond.astype(float)) > 0)
    clusters = []
    for label_id in range(1, n + 1):
        rows, cols = np.nonzero(labelled == label_id)
        cells = int(rows.size)
        if cells < 4:
            elongation, fill = 1.0, 1.0
        else:
            coords = np.stack([rows, cols]).astype(float)
            cov = np.cov(coords)
            eig, vec = np.linalg.eigh(cov)
            elongation = float(np.sqrt(eig[1] / max(eig[0], 1e-9)))
            # Fill ratio of the PCA-oriented bounding box: near 1 for a clean
            # rectangle or disc, low for a ragged natural blob. Rectangularity at
            # building scale is a strong cultural indicator (feature catalog).
            rotated = vec.T @ (coords - coords.mean(axis=1, keepdims=True))
            extent = rotated.max(axis=1) - rotated.min(axis=1) + 1.0
            fill = float(cells / max(extent[0] * extent[1], 1.0))
        # Enclosure: does this cluster ring something? A fence line, wall, or ditch
        # around a cemetery plot CLOSES; a gully, roadbed, or tree-throw scatter does
        # not. Filling interior holes and comparing areas measures exactly that, and
        # it is the shape the owner's review reported seeing at three cemeteries
        # where the grave-scale rule scored zero (2026-09-08).
        member = labelled == label_id
        filled = int(ndimage.binary_fill_holes(member).sum())
        span_cells = 0.0 if cells < 4 else float(max(extent))
        clusters.append(
            {
                "cells": cells,
                "elongation": round(elongation, 1),
                "fill_ratio": round(fill, 2),
                "enclosure_ratio": round(filled / max(cells, 1), 2),
                "span_cells": round(span_cells, 1),
                "centroid_rc": (float(rows.mean()), float(cols.mean())),
            }
        )
    return clusters


def _cluster_qualifies(cluster: dict, detect: dict, min_cells: int) -> bool:
    """Shape gates from the class's morphology priors. Pure.

    min/max cells bound the feature's plausible footprint; min/max elongation encode
    whether the class IS linear (a mill race wants elongation, a cemetery rejects
    it). Gates come from the registry's morphology column, never from tuning against
    the controls.
    """
    if cluster["cells"] < min_cells:
        return False
    max_cells = detect.get("max_cells")
    if max_cells is not None and cluster["cells"] > max_cells:
        return False
    max_elong = detect.get("max_elongation")
    if max_elong is not None and cluster["elongation"] > max_elong:
        return False
    min_elong = detect.get("min_elongation")
    if min_elong is not None and cluster["elongation"] < min_elong:
        return False
    # Enclosure and span gates: an enclosed plot boundary at cemetery/homestead
    # scale, rather than any compact blob past the threshold.
    min_enclosure = detect.get("min_enclosure_ratio")
    if min_enclosure is not None and cluster["enclosure_ratio"] < min_enclosure:
        return False
    span = detect.get("span_cells_range")
    if span is not None and not (span[0] <= cluster["span_cells"] <= span[1]):
        return False
    min_fill = detect.get("min_fill_ratio")
    if min_fill is not None and cluster["fill_ratio"] < min_fill:
        return False
    return True


def _multi_satisfied(
    clusters: list[dict], multi: dict, cell_m: float = 0.5
) -> dict[str, Any]:
    """The multi-element rule: N regular small elements, not one blob. Pure.

    Encodes the cemetery identifier from the feature catalog — rows of small regular
    depressions. Elements are grave-scale clusters; the rule needs at least
    `min_elements` of them with mean nearest-neighbour spacing under `nn_max_m` and
    spacing regularity (CV of NN distances) under `nn_cv_max`. Regular spacing is
    what a tree-throw carpet does not have: windthrow is Poisson in position, so its
    NN-distance CV sits near 1, while graves in rows sit near constant spacing.
    """
    elements = [
        c
        for c in clusters
        if multi["element_min_cells"] <= c["cells"] <= multi["element_max_cells"]
        and c["elongation"] <= multi["element_max_elongation"]
    ]
    result: dict[str, Any] = {"elements": len(elements)}
    if len(elements) < int(multi["min_elements"]):
        result["satisfied"] = False
        return result
    pts = np.array([c["centroid_rc"] for c in elements])
    d2 = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[:, None, 1] - pts[None, :, 1])
    np.fill_diagonal(d2, np.inf)
    nn_m = d2.min(axis=1) * cell_m
    result["nn_mean_m"] = round(float(nn_m.mean()), 1)
    result["nn_cv"] = round(float(nn_m.std() / max(nn_m.mean(), 1e-9)), 2)
    result["satisfied"] = result["nn_mean_m"] <= float(multi["nn_max_m"]) and result[
        "nn_cv"
    ] <= float(multi["nn_cv_max"])
    return result


def _pair_satisfied(detail: dict[str, dict], detect: dict, cell_m: float = 0.5) -> bool:
    """The pairing rule: qualifying clusters on both named surfaces within reach.

    Encodes pit-plus-spoil for ore pits (a dissolution sinkhole has no spoil; the
    pairing is what separates them, per the feature catalog). Centroids are compared
    in the shared window's row/col space, so both surfaces must cover the disc.
    """
    pair = detect.get("pair")
    if not pair:
        return True
    a, b = pair["surfaces"]
    ca = (detail.get(a) or {}).get("clusters") or []
    cb = (detail.get(b) or {}).get("clusters") or []
    max_gap = float(pair["max_gap_m"]) / cell_m
    return any(
        np.hypot(
            p["centroid_rc"][0] - q["centroid_rc"][0],
            p["centroid_rc"][1] - q["centroid_rc"][1],
        )
        <= max_gap
        for p in ca
        for q in cb
    )


def _apply_rule(
    x: float,
    y: float,
    disc_m: float,
    surfaces: dict[str, Path],
    tails: dict[str, str],
    detect: dict,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Apply the firing rule at one location. Returns (fired kinds, per-surface detail)."""
    detail: dict[str, dict[str, Any]] = {}
    fired: list[str] = []
    for kind, path in surfaces.items():
        with rasterio.open(path) as src:
            masks = _disc_masks(src, x, y, disc_m, BACKGROUND_RADIUS_M)
        if masks is None:
            detail[kind] = {"valid": False, "why": "outside raster"}
            continue
        outcome = _fire_on_surface(
            *masks,
            tail=tails[kind],
            threshold_pctile=float(detect["threshold_pctile"]),
            min_cells=int(detect["min_cells"]),
            detect=detect,
            kind=kind,
        )
        detail[kind] = outcome
        if outcome.get("fired"):
            fired.append(kind)
    if fired and not _pair_satisfied(detail, detect):
        for kind in fired:
            detail[kind]["pair_failed"] = True
        fired = []
    return fired, detail


def _evaluate_symbol(
    point: dict, surfaces: dict[str, Path], tails: dict[str, str], detect: dict
) -> SymbolResult:
    """Run the firing rule for one symbol across its class's surfaces.

    The searched disc is the label's positional confidence plus the class's feature
    radius: a point-sized disc on a 40 m-wide feature would miss the feature's own
    edges even with a perfect label (spatial-validation §2).
    """
    tolerance = float(point["positional_confidence_m"])
    disc_m = tolerance + float(detect["feature_radius_m"])
    fired, detail = _apply_rule(point["x"], point["y"], disc_m, surfaces, tails, detect)
    return SymbolResult(
        site_id=point["site_id"],
        name=point["name"],
        tolerance_m=tolerance,
        disc_m=disc_m,
        review_status=point["review_status"],
        hit=bool(fired),
        fired_surfaces=tuple(fired),
        detail=detail,
    )


def _null_draws(
    rng: np.random.Generator,
    bounds: tuple[float, float, float, float],
    exclude: list[tuple[float, float]],
    disc_radii: list[float],
    surfaces: dict[str, Path],
    tails: dict[str, str],
    detect: dict,
    *,
    per_cluster: int,
) -> tuple[int, int]:
    """Background fire rate for one cluster: (draws evaluated, draws that fired).

    Nulls follow the spatial-validation design: the unit is the whole disc, radii are
    sampled from the symbols' own disc radii so the null matches what the symbols were
    tested with, draws stay >=150 m from every control site, and accepted draws are
    thinned to at least one disc diameter apart so overlap does not understate null
    variance.
    """
    xmin, ymin, xmax, ymax = bounds
    margin = min(100.0, (xmax - xmin) / 4, (ymax - ymin) / 4)
    accepted: list[tuple[float, float, float]] = []
    fired_n = 0
    attempts = 0
    while len(accepted) < per_cluster and attempts < per_cluster * 60:
        attempts += 1
        x = rng.uniform(xmin + margin, xmax - margin)
        y = rng.uniform(ymin + margin, ymax - margin)
        radius = float(rng.choice(disc_radii))
        if any(np.hypot(x - ex, y - ey) < 150.0 for ex, ey in exclude):
            continue
        if any(np.hypot(x - ax, y - ay) < (radius + ar) for ax, ay, ar in accepted):
            continue
        fired, detail = _apply_rule(x, y, radius, surfaces, tails, detect)
        if not any(d.get("valid") for d in detail.values()):
            continue
        accepted.append((x, y, radius))
        fired_n += bool(fired)
    return len(accepted), fired_n


def validate_histmap(
    conn: psycopg.Connection,
    sheet_id: str,
    class_id: str,
    *,
    ept_project: str,
    aoi_slug: str | None = None,
    null_per_cluster: int = 12,
    seed: int = 42,
    config=None,
) -> dict[str, Any]:
    """Run the vanished-feature test for one class on one sheet.

    Returns the full report dict; also writes a `validate.histmap` derivation row so
    the recall number is reproducible. Cuts `control_detection` AOIs around the
    symbol clusters unless an existing AOI is named. Alongside recall it always runs
    the negative control — matched-radius null discs drawn from the same clusters — a
    recall without a background fire rate is a pass with no error bar.
    """
    from midden import __version__
    from midden.aoi import SeedSpec, get_aoi, to_multipolygon, upsert_aoi
    from midden.config import settings
    from midden.derivation import open_derivation, param_variant

    config = config or settings()
    cls = get_class(conn, class_id)
    detect = detect_params(cls)
    tails = dict(detect["surfaces"])
    points = _load_points(conn, sheet_id, class_id)
    scan_id = sheet_id.split("_")[-3] if sheet_id.count("_") >= 3 else sheet_id
    rng = np.random.default_rng(seed)
    # Null discs must avoid every control site of every class, not just this one's.
    all_sites = [
        (r["x"], r["y"])
        for r in fetch_all(
            conn, "SELECT ST_X(geom) x, ST_Y(geom) y FROM ref.control_sites"
        )
    ]
    null_total = null_fired = 0

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
                # Content-addressed, NOT positional. An ordinal slug is reused when
                # the point set changes (a review rejection, a relocation), so the
                # cluster inherits rasters derived for DIFFERENT ground; the symbol
                # then falls outside its own raster and is reported as a coverage
                # gap. Hashing the envelope makes a changed cluster a new AOI and
                # leaves the old one as a harmless orphan (found 2026-09-08).
                digest = param_variant(
                    {"wkt": shapely.to_wkt(envelope, rounding_precision=0)}, 8
                )
                slug = f"histmap-{scan_id}-{class_id.replace('_', '-')}-{digest}"
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
                        disc_m=float(p["positional_confidence_m"])
                        + float(detect["feature_radius_m"]),
                        review_status=p["review_status"],
                        hit=False,
                        fired_surfaces=(),
                        detail={"detection": {"valid": False, "why": why}},
                    )
                    for p in members
                )
                continue
            cluster_results = [
                _evaluate_symbol(p, surfaces, tails, detect) for p in members
            ]
            results.extend(cluster_results)
            disc_radii = [
                r.disc_m
                for r in cluster_results
                if any(d.get("valid") for d in r.detail.values())
            ]
            if disc_radii and null_per_cluster > 0:
                with rasterio.open(next(iter(surfaces.values()))) as src0:
                    bounds = tuple(src0.bounds)
                drawn, fired_n = _null_draws(
                    rng,
                    bounds,
                    all_sites,
                    disc_radii,
                    surfaces,
                    tails,
                    detect,
                    per_cluster=null_per_cluster,
                )
                null_total += drawn
                null_fired += fired_n

        evaluable = [
            r for r in results if any(d.get("valid") for d in r.detail.values())
        ]
        hits = [r for r in evaluable if r.hit]
        recall = len(hits) / len(evaluable) if evaluable else float("nan")
        # Empirical rate as (r+1)/(k+1): k draws can bound the rate, never prove zero.
        null_rate = (null_fired + 1) / (null_total + 1) if null_total else None
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
                        "null_draws": null_total,
                        "null_fired": null_fired,
                        "null_rate_laplace": round(null_rate, 3) if null_rate else None,
                        "null_seed": seed,
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
        "detectability": cls.detectability,
        "null_draws": null_total,
        "null_fired": null_fired,
        "null_rate": null_rate,
    }
