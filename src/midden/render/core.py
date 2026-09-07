"""The scene spec: the only thing render adapters consume (spec.md §8).

Two targets, neither a web app. `qgis.py` emits a `.qgs` project for the interactive
surface; `artifact.py` emits a single self-contained HTML file for sharing and for the AI
layer. Keeping the scene the sole interface means a third adapter — and there will be one —
requires no changes outside `render/`.

Everything here is pure. Building a scene reads the catalog; it does not read pixels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import psycopg

from midden.aoi import Aoi
from midden.db import fetch_all
from midden.terrain.cog import list_assets

__all__ = ["RasterLayer", "Scene", "VectorLayer", "build_scene"]

#: How each raster kind should be displayed, and what a reader is looking at when they do.
#: Openness gets a window fixed on 90 degrees rather than a percentile stretch, so two
#: renders of different ground stay comparable and flat is always mid-grey.
RASTER_STYLES: dict[str, dict[str, Any]] = {
    "openness_pos": {
        "palette": "grey",
        "window": (84.0, 96.0),
        "legend": "bright = convex (mounds, hearths, ridges)",
    },
    "openness_neg": {
        "palette": "grey",
        "window": (84.0, 96.0),
        "legend": "bright = concave (pits, ditches, relict channels)",
    },
    "slrm": {
        "palette": "grey",
        "percentile": (2, 98),
        "legend": "local relief; bright = locally high",
    },
    "hillshade_multi": {
        "palette": "grey",
        "percentile": (2, 98),
        "legend": "multi-azimuth shaded relief (context only)",
    },
    "score": {
        "palette": "viridis",
        "percentile": (1, 99),
        "legend": "suitability, high = better landform (not a probability)",
    },
    "hand": {
        "palette": "viridis",
        "percentile": (2, 98),
        "legend": "height above nearest drainage, metres",
    },
    "slope": {"palette": "viridis", "percentile": (2, 98), "legend": "slope, degrees"},
    "terrace": {
        "palette": "terrace",
        "window": (0.0, 4.0),
        "legend": "0 none, 1 T0, 2 T1, 3 T2",
    },
    "dem": {"palette": "grey", "percentile": (2, 98), "legend": "elevation, metres"},
    "ground_count": {
        "palette": "viridis",
        "percentile": (2, 98),
        "legend": "ground returns per cell; 0 means interpolated, not measured",
    },
}

#: What a reader needs told about these surfaces before they read anything into them.
SCENE_NOTES = (
    (
        "Openness: positive is high on CONVEX ground (mounds, hearths); negative is high "
        "on CONCAVE ground (pits, ditches, relict channels). Flat is 90 degrees in both, "
        "whatever the slope."
    ),
    (
        "A suitability score ranks where the landform is right. It is not a probability, "
        "and a low score may mean the ground is buried rather than wrong."
    ),
)

#: Raster kinds a scene shows by default, in draw order (bottom first).
DEFAULT_RASTERS = (
    "hillshade_multi",
    "dem",
    "hand",
    "slope",
    "terrace",
    "score",
    "openness_neg",
    "openness_pos",
    "slrm",
)


@dataclass(frozen=True, slots=True)
class RasterLayer:
    """One raster in a scene."""

    name: str
    kind: str
    path: Path
    grid: str
    resolution_m: float
    legend: str = ""
    palette: str = "grey"
    window: tuple[float, float] | None = None
    percentile: tuple[float, float] | None = None
    opacity: float = 1.0
    visible: bool = False


@dataclass(frozen=True, slots=True)
class VectorLayer:
    """One vector overlay, carried as GeoJSON so both adapters can use it."""

    name: str
    geojson: dict[str, Any]
    geometry: Literal["point", "line", "polygon"]
    stroke: str = "#38bdf8"
    fill: str | None = None
    width: float = 1.5
    legend: str = ""
    visible: bool = True


@dataclass(frozen=True, slots=True)
class Scene:
    """Everything an adapter needs to draw one AOI."""

    aoi_slug: str
    title: str
    subtitle: str
    bounds: tuple[float, float, float, float]
    rasters: list[RasterLayer] = field(default_factory=list)
    vectors: list[VectorLayer] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """Whether there is anything to draw."""
        return not self.rasters and not self.vectors


def _vector(
    conn: psycopg.Connection, name: str, sql: str, params, **style
) -> VectorLayer | None:
    """Build a vector layer from a query returning GeoJSON geometries."""
    rows = fetch_all(conn, sql, params)
    if not rows:
        return None
    import json

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(row.pop("gj")),
            "properties": {k: v for k, v in row.items()},
        }
        for row in rows
    ]
    return VectorLayer(
        name=name, geojson={"type": "FeatureCollection", "features": features}, **style
    )


#: Kinds whose content depends on per-class parameters (openness radius, SLRM radius,
#: weight set). These are never substituted across classes: a global-radius openness
#: render shown under a class's label would present the wrong parameters as that
#: class's, which is what per-class parameters exist to prevent.
CLASS_QUALIFIED_KINDS = frozenset({"openness_pos", "openness_neg", "slrm", "score"})


def _select_assets(rows: list[dict], class_id: str | None) -> dict[str, Any]:
    """Pick one catalog row per kind, honouring class qualification. Pure.

    A class's own variant wins over the unqualified ('') asset, and class-qualified
    kinds NEVER fall back to an unqualified asset: with a class given, a legacy
    global-parameter openness/slrm/score render stays out of the scene rather than
    masquerading under the class's label. Assets carrying another class's variant (or
    a sweep digest) are skipped. A score surface is never selected without a class —
    an unqualified score render is forbidden (CLAUDE.md).
    """
    unqualified = {
        r["kind"]: r
        for r in rows
        if not (r["variant"] or "")
        and r["kind"] != "score"
        and not (class_id and r["kind"] in CLASS_QUALIFIED_KINDS)
    }
    class_rows = (
        {r["kind"]: r for r in rows if (r["variant"] or "") == class_id}
        if class_id
        else {}
    )
    return {**unqualified, **class_rows}


def build_scene(
    conn: psycopg.Connection,
    aoi: Aoi,
    *,
    kinds: tuple[str, ...] = DEFAULT_RASTERS,
    visible: str | None = None,
    class_id: str | None = None,
) -> Scene:
    """Assemble a scene for one AOI from the raster catalog and PostGIS vectors.

    Only catalogued rasters appear, so a scene never points at a file that a derivation
    did not actually produce. Layers a reader most likely wants on top are ordered last.
    Pass `class_id` to see class-qualified surfaces (score, detection renders); without
    it the scene shows only unqualified terrain.
    """
    catalogued = _select_assets(list_assets(conn, aoi_id=aoi.id), class_id)
    rasters = _raster_layers(catalogued, kinds, visible)
    xmin, ymin, xmax, ymax = aoi.geom.bounds
    vectors = _vector_layers(conn, aoi)
    if class_id:
        zones = _vector(
            conn,
            f"Candidate zones ({class_id})",
            """SELECT rank, round(pct_mean::numeric, 1) AS pct_mean, burial_risk,
                      ST_AsGeoJSON(ST_Transform(cz.geom, 4326)) AS gj
               FROM derived.candidate_zone cz
               WHERE cz.aoi_id = %s AND cz.class_id = %s ORDER BY rank""",
            (aoi.id, class_id),
            geometry="polygon",
            stroke="#f59e0b",
            fill="#f59e0b",
            width=2.0,
            legend="ranked survey candidates (F1); burial_risk is a separate finding",
        )
        if zones is not None:
            vectors.append(zones)
    qualifier = f" · class: {class_id}" if class_id else ""
    return Scene(
        aoi_slug=aoi.slug,
        title=aoi.name,
        subtitle=f"{aoi.role} · {aoi.area_km2:.2f} km² · EPSG:26916{qualifier}",
        bounds=(xmin, ymin, xmax, ymax),
        rasters=rasters,
        vectors=vectors,
        notes=list(SCENE_NOTES),
    )


def _raster_layers(
    catalogued: dict[str, Any], kinds: tuple[str, ...], visible: str | None
) -> list[RasterLayer]:
    """Turn catalog rows into styled raster layers, skipping anything not derived yet."""
    chosen = visible or _default_visible(catalogued)
    layers = []
    for kind in kinds:
        row = catalogued.get(kind)
        if row is None:
            continue
        style = RASTER_STYLES.get(kind, {"palette": "grey", "percentile": (2, 98)})
        layers.append(
            RasterLayer(
                name=kind.replace("_", " "),
                kind=kind,
                path=Path(row["path"]),
                grid=row["grid"],
                resolution_m=row["resolution_m"],
                legend=style.get("legend", ""),
                palette=style.get("palette", "grey"),
                window=style.get("window"),
                percentile=style.get("percentile"),
                visible=(kind == chosen),
            )
        )
    return layers


def _vector_layers(conn: psycopg.Connection, aoi: Aoi) -> list[VectorLayer]:
    """Build the AOI boundary, hydrography, and confluence overlays."""
    xmin, ymin, xmax, ymax = aoi.geom.bounds
    return [
        layer
        for layer in (
            _vector(
                conn,
                "AOI boundary",
                "SELECT slug, ST_AsGeoJSON(geom_wgs84) AS gj FROM derived.aoi WHERE id = %s",
                (aoi.id,),
                geometry="polygon",
                stroke="#f472b6",
                fill=None,
                width=2.5,
                legend="area of interest",
            ),
            _vector(
                conn,
                "Flowlines",
                """SELECT gnis_name, stream_order,
                              ST_AsGeoJSON(ST_Transform(geom, 4326)) AS gj
                       FROM ref.nhd_flowline
                       WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 26916)""",
                (xmin, ymin, xmax, ymax),
                geometry="line",
                stroke="#38bdf8",
                width=1.6,
                legend="NHDPlus HR flowlines",
            ),
            _vector(
                conn,
                "Confluences",
                """SELECT order_minor, order_major,
                              ST_AsGeoJSON(ST_Transform(geom, 4326)) AS gj
                       FROM ref.confluence
                       WHERE order_minor >= 2 AND order_minor < order_major
                         AND geom && ST_MakeEnvelope(%s, %s, %s, %s, 26916)""",
                (xmin, ymin, xmax, ymax),
                geometry="point",
                stroke="#fbbf24",
                fill="#fbbf24",
                width=1.0,
                legend="tributary junctions",
            ),
        )
        if layer is not None
    ]


def _default_visible(catalogued: dict[str, Any]) -> str:
    """Pick the layer to show first: the score if there is one, else the best render."""
    for kind in ("score", "openness_neg", "hillshade_multi", "hand", "dem"):
        if kind in catalogued:
            return kind
    return next(iter(catalogued), "")
