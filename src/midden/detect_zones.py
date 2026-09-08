"""Promote detection-grid clusters to candidate zones — the cascade's missing stage.

`midden validate histmap` applies a class's firing rule at LABELLED points. This
applies the same rule across a whole detection raster and writes what qualifies into
`derived.candidate_zone`, which is what makes a detection usable downstream: as survey
candidates (F1/F2), and as an evidence layer for classes that cannot be detected at
all (`midden score evidence`).

The rule is deliberately the same code path as validation — `_cluster_morphometry` and
`_cluster_qualifies` — so a class cannot detect one way when measured and another way
when used. What differs is only the background: validation compares a disc against a
surrounding annulus, while here the threshold is taken over the whole raster, so the
percentile is a statement about this AOI rather than about a neighbourhood. That
difference is recorded in every derivation, because it changes what the number means.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import psycopg
import rasterio
import rasterio.features
import shapely

from midden.db import fetch_all
from midden.registry import TargetClass, detect_params
from midden.validate import _cluster_morphometry, _cluster_qualifies

__all__ = ["detect_zones"]


def _qualifying_mask(
    values: np.ma.MaskedArray, tail: str, detect: dict
) -> tuple[np.ndarray, list[dict]]:
    """Cells belonging to clusters that pass the class's shape gates. Pure."""
    data = np.ma.filled(values, np.nan)
    finite = np.isfinite(data)
    if finite.sum() < 100:
        return np.zeros(data.shape, bool), []

    pct = float(detect["threshold_pctile"])
    if tail == "high":
        cut = np.nanpercentile(data[finite], pct)
        beyond = finite & (data >= cut)
    else:
        cut = np.nanpercentile(data[finite], 100.0 - pct)
        beyond = finite & (data <= cut)

    from scipy import ndimage

    labelled, n = ndimage.label(beyond)
    keep = np.zeros(data.shape, bool)
    kept: list[dict] = []
    clusters = _cluster_morphometry(beyond)
    for index, cluster in enumerate(clusters, start=1):
        if index > n:
            break
        if _cluster_qualifies(cluster, detect, int(detect["min_cells"])):
            keep |= labelled == index
            kept.append(cluster)
    return keep, kept


def _exclusion_mask(
    conn: psycopg.Connection, spec: dict, transform, shape: tuple[int, int]
) -> np.ndarray | None:
    """Cells to REJECT because they coincide with a feature the class excludes. Pure-ish.

    `relict` means abandoned: a linear concave trace on the mapped stream is the
    ACTIVE channel, and one alongside a road is a ditch. Both fire the same
    amplitude-and-shape rule, so the class is defined partly by what it is not —
    a relational discriminator, like every other rule that has worked here.
    """
    import rasterio.features
    import shapely

    bounds = rasterio.transform.array_bounds(shape[0], shape[1], transform)
    rows = fetch_all(
        conn,
        f"SELECT ST_AsBinary(geom) AS wkb FROM {spec['source']} "
        "WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 26916)",
        bounds,
    )
    if not rows:
        # A declared exclusion whose source is empty here is a DATA GAP, not a
        # no-op: silently keeping every cluster would catalogue active channels as
        # relict. The caller raises with the fix rather than shipping the wrong set.
        return None
    buffered = [
        shapely.from_wkb(bytes(r["wkb"])).buffer(float(spec["min_dist_m"]))
        for r in rows
    ]
    burnt = rasterio.features.rasterize(
        ((g, 1) for g in buffered), out_shape=shape, transform=transform,
        fill=0, all_touched=True, dtype="uint8",
    )
    return burnt.astype(bool)


def detect_zones(
    conn: psycopg.Connection, aoi, cls: TargetClass, *, config=None
) -> dict[str, Any]:
    """Run a class's firing rule over its whole detection raster and store the zones.

    Uses the FIRST surface the class names, which is its primary signature; a
    multi-surface class is served by its first named surface here and the pairing or
    enclosure gates still apply within it.
    """
    from midden import __version__
    from midden.config import settings
    from midden.derivation import open_derivation
    from midden.terrain.cog import list_assets

    config = config or settings()
    detect = detect_params(cls)
    surfaces = dict(detect["surfaces"])
    kind, tail = next(iter(surfaces.items()))

    rows = [
        r
        for r in list_assets(conn, aoi_id=aoi.id, kind=kind)
        if (r["variant"] or "") == cls.class_id and r["grid"] == "detection"
    ]
    if not rows:
        raise ValueError(
            f"{aoi.slug}: no {kind!r} detection raster for class {cls.class_id!r}. "
            f"Run `midden terrain run --aoi {aoi.slug} --grid detection "
            f"--class {cls.class_id}` first."
        )
    path = Path(rows[0]["path"])

    with rasterio.open(path) as src:
        values = src.read(1, masked=True)
        transform = src.transform
        resolution = abs(transform.a)
        keep, clusters = _qualifying_mask(values, tail, detect)
        exclude_spec = detect.get("exclude_near")
        excluded_cells = 0
        if exclude_spec:
            # A cluster is dropped whole when most of it sits in the exclusion
            # zone: trimming its edges would leave a fragment of an active
            # channel and call it relict.
            mask = _exclusion_mask(conn, exclude_spec, transform, keep.shape)
            if mask is None:
                raise ValueError(
                    f"{aoi.slug}: class {cls.class_id!r} declares exclude_near on "
                    f"{exclude_spec['source']}, but that table has no features in "
                    f"this frame. Load it for this AOI first (e.g. `midden intake "
                    f"run nhd_flowline --aoi {aoi.slug}`); without it every active "
                    f"channel would be catalogued as relict."
                )
            from scipy import ndimage as _nd

            lab, n_lab = _nd.label(keep)
            for idx in range(1, n_lab + 1):
                member = lab == idx
                if (mask & member).sum() > 0.5 * member.sum():
                    keep &= ~member
                    excluded_cells += int(member.sum())
        polygons = [
            shapely.geometry.shape(geom)
            for geom, value in rasterio.features.shapes(
                keep.astype("uint8"), mask=keep, transform=transform
            )
            if value == 1
        ]

    with open_derivation(
        conn,
        operation="detect.zones",
        tool="midden.detect_zones",
        tool_version=__version__,
        aoi_id=aoi.id,
        params={
            "class_id": cls.class_id,
            "surface": kind,
            "tail": tail,
            "resolution_m": resolution,
            "n_zones": len(polygons),
            # The background differs from validation's and that changes the meaning.
            "threshold_background": "whole raster (AOI-wide), not a local annulus",
            "excluded_cells": excluded_cells,
            **{k: detect[k] for k in detect if k != "surfaces"},
        },
        inputs=[str(path)],
    ) as derivation_id:
        conn.execute(
            "DELETE FROM derived.candidate_zone WHERE aoi_id = %s AND class_id = %s",
            (aoi.id, cls.class_id),
        )
        ranked = sorted(
            zip(polygons, clusters + [{}] * len(polygons), strict=False),
            key=lambda pair: -pair[0].area,
        )
        for rank, (polygon, cluster) in enumerate(ranked, start=1):
            conn.execute(
                """
                INSERT INTO derived.candidate_zone
                    (aoi_id, class_id, rank, area_m2, score_mean, score_max, pct_mean,
                     geom, derivation_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 26916), %s)
                """,
                (
                    aoi.id,
                    cls.class_id,
                    rank,
                    float(polygon.area),
                    # A detection zone has no suitability score; the percentile
                    # threshold it cleared is recorded instead, so the column means
                    # something honest rather than being left null.
                    float(detect["threshold_pctile"]),
                    float(detect["threshold_pctile"]),
                    float(detect["threshold_pctile"]),
                    polygon.wkt,
                    derivation_id,
                ),
            )

    return {
        "aoi": aoi.slug,
        "class_id": cls.class_id,
        "surface": kind,
        "tail": tail,
        "zones": len(polygons),
        "total_area_m2": round(sum(p.area for p in polygons)),
        "derivation_id": derivation_id,
    }
