"""Interpretive MCP tools (ROADMAP G3): the learning loop, as decompositions.

The agent layer is the interpretive surface for doing geoarchaeology without
geoarchaeology training, and the standing invariant is attribution over assertion:
when explaining why a cell scores highly, return the per-feature decomposition —
values, normalised percentiles, contributions — not a narrative. The narrative is
the user's job; the numbers are the tool's.

All four tools are read-only. explain/compare read the clipped stack parquet the
features CLI writes; when it is absent they say how to build it rather than
computing behind a read-only hint.
"""

from __future__ import annotations

from typing import Annotated, Any

import pandas as pd
from pydantic import Field

from midden.config import settings
from midden.db import connect, fetch_all

READ_ONLY = {"readOnlyHint": True}


def midden_class_brief(
    class_id: Annotated[str, Field(description="Class id from ref.target_class.")],
) -> dict[str, Any]:
    """One class's registry entry, made legible: morphology, parameters, detectability,
    known confusers, label counts, and its latest validation numbers.

    The registry is only useful for learning if it is readable from inside a
    conversation. Detectability is declared, not assumed: a proxy class's hits are
    surrogate signal, never detections, and this brief says so.
    """
    from midden.registry import get_class

    with connect() as conn:
        cls = get_class(conn, class_id)
        confusers = fetch_all(
            conn,
            """SELECT kind, assessment, basis, extent_m FROM ref.confuser
               WHERE imitates = %s ORDER BY confuser_id""",
            (class_id,),
        )
        labels = fetch_all(
            conn,
            """SELECT source, review_status, count(*) AS n FROM ref.control_sites
               WHERE class_id = %s GROUP BY source, review_status ORDER BY source""",
            (class_id,),
        )
        validations = fetch_all(
            conn,
            """SELECT params->>'sheet_id' AS sheet, params->>'recall' AS recall,
                      params->>'null_rate_laplace' AS background_fire_rate,
                      started_at::date AS run_on
               FROM derived.derivation
               WHERE operation = 'validate.histmap' AND status = 'ok'
                 AND params->>'class_id' = %s
               ORDER BY id DESC LIMIT 5""",
            (class_id,),
        )
    return {
        "class_id": cls.class_id,
        "period": cls.period,
        "morphology": cls.morphology,
        "grid": cls.grid,
        "detectability": cls.detectability,
        "detectability_meaning": {
            "direct": "a LiDAR signature exists; detections are candidate features",
            "proxy": "only surrogate/landform signal exists; a hit is NEVER a "
            "detection of the class itself",
            "invisible": "no signature; absence is never evidence",
        }[cls.detectability],
        "burial_sensitivity": cls.burial_sensitivity,
        "label_source": cls.label_source,
        "params": cls.params,
        "known_confusers": confusers or "none logged yet — see ref.confuser (A4)",
        "labels": labels or "none",
        "recent_validations": validations
        or "none — this class has not been through validate histmap",
        "notes": cls.notes,
        "sourcing": "morphology and parameter rationale live in the registry notes "
        "and the landform-archaeology skill; where a claim is unsourced "
        "the notes say so rather than asserting it",
    }


def midden_describe_aoi(
    aoi: Annotated[str, Field(description="AOI slug.")],
) -> dict[str, Any]:
    """Orientation before interpretation: what an AOI is, and what exists for it.

    Physiographic context (HAND/slope summary where a stack exists), soils mix,
    terrain coverage by grid and class variant, labels inside the boundary, and
    candidate zones — the state a reader needs before any number means anything.
    """
    from midden.aoi import get_aoi

    with connect() as conn:
        area = get_aoi(conn, aoi)
        rasters = fetch_all(
            conn,
            """SELECT kind, grid, variant, resolution_m FROM derived.raster_asset
               WHERE aoi_id = %s ORDER BY grid, kind, variant""",
            (area.id,),
        )
        soils = fetch_all(
            conn,
            """SELECT drainage_class, flood_freq, count(*) AS map_units
               FROM ref.ssurgo_mapunit
               WHERE geom && (SELECT geom FROM derived.aoi WHERE id = %s)
               GROUP BY 1, 2 ORDER BY map_units DESC LIMIT 8""",
            (area.id,),
        )
        labels = fetch_all(
            conn,
            """SELECT c.class_id, c.review_status, count(*) AS n
               FROM ref.control_sites c, derived.aoi a
               WHERE a.id = %s AND ST_Within(c.geom, a.geom)
               GROUP BY 1, 2""",
            (area.id,),
        )
        zones = fetch_all(
            conn,
            """SELECT class_id, count(*) AS zones, max(pct_mean) AS best_pct
               FROM derived.candidate_zone WHERE aoi_id = %s GROUP BY 1""",
            (area.id,),
        )

    stack_path = settings().parquet_dir / f"{area.slug}_10m.parquet"
    terrain_summary: Any = "no clipped stack parquet; run `midden features build`"
    if stack_path.exists():
        frame = pd.read_parquet(stack_path)
        terrain_summary = {
            "cells_10m": len(frame),
            "hand_median_m": round(float(frame["hand_m"].median()), 1),
            "hand_p90_m": round(float(frame["hand_m"].quantile(0.9)), 1),
            "slope_median_deg": round(float(frame["slope_deg"].median()), 1),
        }

    return {
        "slug": area.slug,
        "name": area.name,
        "kind": area.kind,
        "role": area.role,
        "area_km2": round(area.area_km2, 3),
        "role_meaning": {
            "prospect": "a real candidate area",
            "control_positive": "published site; falsifies a weight set",
            "control_detection": "known surface features; validates the render chain",
            "shakeout": "fast-iteration acre; ignore its scores",
        }.get(area.role, area.role),
        "terrain": terrain_summary,
        "raster_coverage": rasters or "no terrain derived yet",
        "soils_mix": soils or "no SSURGO loaded for this extent",
        "labels_inside": labels or "none",
        "candidate_zones": zones or "none — run `midden score polygons`",
    }


def _cell_decomposition(
    frame: pd.DataFrame, easting: float, northing: float, weight_set
) -> dict[str, Any]:
    """Score one stack cell and decompose it feature by feature. Pure-ish."""
    from midden.features.score import score_stack

    d2 = (frame["easting"] - easting) ** 2 + (frame["northing"] - northing) ** 2
    idx = int(d2.idxmin())
    if float(d2.loc[idx]) > 10.0**2:
        raise ValueError(
            f"({easting:.0f}, {northing:.0f}) is more than one cell from the stack — "
            "outside the clipped AOI extent?"
        )
    scored = score_stack(frame, weight_set)
    row = scored.frame.loc[idx]

    def raw(v):
        # Categorical features (drainage_class, flood_freq) carry label strings —
        # including SSURGO's literal 'None' — which are values, not absences.
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        try:
            return round(float(v), 3)
        except TypeError, ValueError:
            return str(v)

    features = {}
    for name, weight in scored.weights.items():
        features[name] = {
            "value": raw(row[name]),
            "normalized": round(float(row[f"norm_{name}"]), 3)
            if pd.notna(row[f"norm_{name}"])
            else None,
            "weight_share": round(weight, 3),
            "contribution": round(float(weight * (row[f"norm_{name}"] or 0.0)), 4),
        }
    return {
        "cell": {
            "easting": round(float(row["easting"])),
            "northing": round(float(row["northing"])),
        },
        "score": round(float(row["score"]), 4),
        "score_percentile_in_aoi": round(float(row["score_pct"]), 1),
        "features": features,
        "companion_bands": {
            "burial_risk": round(float(row["burial_risk"]), 2)
            if "burial_risk" in row and pd.notna(row["burial_risk"])
            else None,
        },
    }


def _load_stack_and_weights(aoi_slug: str, class_id: str):
    """Shared read path for explain/compare. Read-only: absent inputs raise with the fix."""
    from midden.features.score import load_weights

    stack_path = settings().parquet_dir / f"{aoi_slug}_10m.parquet"
    if not stack_path.exists():
        raise ValueError(
            f"No stack parquet at {stack_path}. Run "
            f"`midden features build --aoi {aoi_slug}` first — this tool only reads."
        )
    weights_path = settings().weights_dir / f"{class_id}.yml"
    if not weights_path.exists():
        raise ValueError(
            f"No weight set for {class_id!r} at {weights_path}; a decomposition is "
            "per class because the score is."
        )
    return pd.read_parquet(stack_path), load_weights(weights_path)


def midden_explain_cell(
    aoi: Annotated[str, Field(description="AOI slug (its clipped stack is read).")],
    easting: Annotated[float, Field(description="EPSG:26916 easting, metres.")],
    northing: Annotated[float, Field(description="EPSG:26916 northing, metres.")],
    target_class: Annotated[str, Field(description="Class whose weight set explains.")],
) -> dict[str, Any]:
    """Why does this cell score what it scores? Per-feature decomposition, no narrative.

    Returns each scored feature's raw value, normalised value, weight share, and
    contribution, plus the cell's score and in-AOI percentile and the companion
    bands. Attribution over assertion: the numbers are the answer; reading them is
    the caller's job. A low score with high burial_risk means LiDAR-blind, not empty.
    """
    frame, weight_set = _load_stack_and_weights(aoi, target_class)
    result = _cell_decomposition(frame, easting, northing, weight_set)
    result["how_to_read"] = (
        "contribution = weight_share x normalized; contributions sum to the score. "
        "The percentile ranks this cell inside the clipped AOI only — regional "
        "context needs `midden score validate`'s frame."
    )
    return result


def midden_compare_landform(
    aoi_a: Annotated[str, Field(description="First AOI slug.")],
    easting_a: Annotated[float, Field(description="First point easting (26916).")],
    northing_a: Annotated[float, Field(description="First point northing.")],
    aoi_b: Annotated[str, Field(description="Second AOI slug (may equal the first).")],
    easting_b: Annotated[float, Field(description="Second point easting.")],
    northing_b: Annotated[float, Field(description="Second point northing.")],
    target_class: Annotated[
        str, Field(description="Class whose weight set frames both.")
    ],
) -> dict[str, Any]:
    """Two cells side by side: 'how is this unlike Mound Bottom' as numbers.

    Same decomposition as midden_explain_cell for both points, plus per-feature
    normalised deltas (a - b). Percentiles are each relative to their own AOI, so
    compare the feature vectors, not the percentiles, across different AOIs.
    """
    frame_a, weight_set = _load_stack_and_weights(aoi_a, target_class)
    a = _cell_decomposition(frame_a, easting_a, northing_a, weight_set)
    frame_b = (
        frame_a if aoi_b == aoi_a else _load_stack_and_weights(aoi_b, target_class)[0]
    )
    b = _cell_decomposition(frame_b, easting_b, northing_b, weight_set)
    deltas = {
        name: round(
            (a["features"][name]["normalized"] or 0.0)
            - (b["features"][name]["normalized"] or 0.0),
            3,
        )
        for name in a["features"]
    }
    return {
        "a": {"aoi": aoi_a, **a},
        "b": {"aoi": aoi_b, **b},
        "normalized_delta_a_minus_b": deltas,
        "how_to_read": (
            "Deltas are on normalised features (0-1), so they compare like with "
            "like. Percentiles are per-AOI and NOT comparable across AOIs."
        ),
    }


READ_TOOLS = (
    midden_class_brief,
    midden_describe_aoi,
    midden_explain_cell,
    midden_compare_landform,
)


def register(mcp) -> None:
    """Attach this module's tools to a FastMCP server."""
    for tool in READ_TOOLS:
        mcp.tool(tool, annotations=READ_ONLY)
