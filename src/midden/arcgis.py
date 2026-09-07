"""Minimal ArcGIS REST client for boundary and feature queries.

Used by the AOI seeder (`midden.aoi`) and by the `arcgis_rest` intake driver. Kept
separate from both because seeding an AOI and fetching a source are different jobs that
happen to speak the same protocol.

The server is asked for GeoJSON in the project CRS and the geometry is handed straight to
shapely. Requesting Esri JSON instead would mean reimplementing ring-orientation and hole
containment, which the server already does correctly.
"""

from __future__ import annotations

from typing import Any

import httpx
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from midden import PROJECT_CRS

__all__ = ["ArcGisError", "count_features", "query_layer"]

#: ArcGIS caps a single page; the server reports `exceededTransferLimit` when it truncates.
_PAGE_SIZE = 1000
_TIMEOUT = httpx.Timeout(90.0, connect=30.0)


class ArcGisError(RuntimeError):
    """An ArcGIS REST endpoint returned an error or an unusable response."""


def _srid(crs: str) -> int:
    """Return the numeric SRID from an `EPSG:NNNN` string."""
    return int(crs.split(":", 1)[1])


def _get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """Issue one GET and return parsed JSON, turning ArcGIS error payloads into raises.

    ArcGIS answers errors with HTTP 200 and an `error` key, so checking the status code
    alone would let a failed query through as an empty result.
    """
    try:
        response = httpx.get(
            url, params=params, timeout=_TIMEOUT, follow_redirects=True
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise ArcGisError(f"{url}: {exc}") from exc
    except ValueError as exc:
        raise ArcGisError(f"{url}: response was not JSON ({exc})") from exc

    if isinstance(payload, dict) and "error" in payload:
        detail = payload["error"]
        raise ArcGisError(
            f"{url}: ArcGIS error {detail.get('code')} — {detail.get('message')}. "
            f"{'; '.join(detail.get('details') or [])}"
        )
    return payload


def count_features(layer_url: str, where: str = "1=1") -> int:
    """Return how many features match, without transferring any of them."""
    payload = _get(
        layer_url.rstrip("/") + "/query",
        {"where": where, "returnCountOnly": "true", "f": "json"},
    )
    return int(payload.get("count", 0))


def query_layer(
    layer_url: str,
    where: str = "1=1",
    *,
    out_fields: str = "*",
    out_crs: str = PROJECT_CRS,
    envelope: tuple[float, float, float, float] | None = None,
) -> list[tuple[dict[str, Any], BaseGeometry]]:
    """Query a layer and return `(attributes, geometry)` pairs in `out_crs`.

    Pages until the server stops reporting a transfer limit, so a large layer comes back
    whole rather than silently truncated at the first 1000 features. `envelope` is a
    server-side bbox filter in `out_crs` — required for national layers (TIGER roads),
    where fetch-everything-then-clip is not an option.
    """
    url = layer_url.rstrip("/") + "/query"
    base = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "true",
        "outSR": _srid(out_crs),
        "f": "geojson",
    }
    if envelope is not None:
        xmin, ymin, xmax, ymax = envelope
        base.update(
            {
                "geometry": f"{xmin},{ymin},{xmax},{ymax}",
                "geometryType": "esriGeometryEnvelope",
                "inSR": _srid(out_crs),
                "spatialRel": "esriSpatialRelIntersects",
            }
        )

    results: list[tuple[dict[str, Any], BaseGeometry]] = []
    offset = 0
    while True:
        payload = _get(
            url, {**base, "resultOffset": offset, "resultRecordCount": _PAGE_SIZE}
        )
        features = payload.get("features") or []
        for feature in features:
            geometry = feature.get("geometry")
            if geometry is None:
                # A null geometry cannot be an AOI or a spatial feature. Say so rather
                # than dropping it silently.
                raise ArcGisError(
                    f"{layer_url}: a feature matching {where!r} has no geometry."
                )
            results.append((feature.get("properties") or {}, shape(geometry)))

        if not payload.get("exceededTransferLimit") or not features:
            return results
        offset += len(features)
