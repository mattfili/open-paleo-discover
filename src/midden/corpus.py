"""Tracked label corpus: export reviewed control sites and confusers to git, restore them.

Human review is the expensive, irreproducible part of the label set. The tracked
`labels/<sheet_id>.geojson` files are therefore the durable copy: each point carries its
review state as extra feature properties, and `histmap load-sites` restores it into a
rebuilt database. A sidecar file per sheet was rejected because it would need a join key
(name + class, which is not unique across a sheet's relocations), whereas properties on the
feature cannot drift away from the geometry they judge.

Review properties on a feature: `review_status` (unreviewed | confirmed | rejected),
`review_note`, `review_round`, `reviewed_at` (ISO 8601), `review_prior` (superseded earlier
decisions). A point a reviewer marked "can't tell" stays `unreviewed` with its note and
round recorded: the bench's rule is that "can't tell" asserts nothing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import psycopg

from midden.db import fetch_all

__all__ = [
    "REVIEW_KEYS",
    "export_confusers",
    "export_sheet_labels",
    "load_confusers",
    "review_params",
]

REVIEW_KEYS = ("review_status", "review_note", "review_round", "reviewed_at", "review_prior")


def review_params(props: dict[str, Any]) -> dict[str, Any]:
    """Normalise a feature's review properties into column values (pure)."""
    status = props.get("review_status") or "unreviewed"
    if status not in {"unreviewed", "confirmed", "rejected"}:
        raise ValueError(f"unknown review_status {status!r} on {props.get('name')!r}")
    prior = props.get("review_prior")
    return {
        "review_status": status,
        "review_note": props.get("review_note") or None,
        "review_round": props.get("review_round"),
        "reviewed_at": props.get("reviewed_at"),
        "review_prior": json.dumps(prior) if prior else None,
    }


def _site_rows(conn: psycopg.Connection, sheet_id: str) -> list[dict[str, Any]]:
    """All control sites for a sheet, with review state, in stable order."""
    return fetch_all(
        conn,
        """
        SELECT name, class_id, positional_confidence_m, review_status, review_note,
               review_round, to_char(reviewed_at AT TIME ZONE 'UTC',
                   'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS reviewed_at,
               review_prior, ST_X(geom) AS x, ST_Y(geom) AS y
        FROM ref.control_sites
        WHERE source = 'usgs_histmap' AND source_sheet = %s
        ORDER BY site_id
        """,
        (sheet_id,),
    )


def merge_reviews(doc: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge DB review state into a labels document, keyed by (name, class_id) (pure).

    Existing properties the database does not hold (the digitizer's free-text `note`) are
    preserved; DB points absent from the file are appended so nothing reviewed is dropped.
    """
    by_key = {(f["properties"]["name"], f["properties"]["class_id"]): f for f in doc["features"]}
    for row in rows:
        feature = by_key.get((row["name"], row["class_id"]))
        if feature is None:
            feature = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["x"], row["y"]]},
                "properties": {
                    "class_id": row["class_id"],
                    "name": row["name"],
                    "positional_confidence_m": row["positional_confidence_m"],
                },
            }
            doc["features"].append(feature)
            by_key[(row["name"], row["class_id"])] = feature
        props = feature["properties"]
        # Unreviewed, never-noted points carry no review keys: the file stays minimal.
        if row["review_status"] == "unreviewed" and not row["review_round"]:
            continue
        props["review_status"] = row["review_status"]
        for key in ("review_note", "review_round", "reviewed_at", "review_prior"):
            if row[key] not in (None, ""):
                props[key] = row[key]
    return doc


def export_sheet_labels(conn: psycopg.Connection, sheet_id: str, path: Path) -> int:
    """Merge a sheet's DB review state into its tracked labels file; return point count."""
    doc = (
        json.loads(path.read_text())
        if path.exists()
        else {"type": "FeatureCollection", "features": []}
    )
    merge_reviews(doc, _site_rows(conn, sheet_id))
    path.write_text(json.dumps(doc, indent=1) + "\n")
    return len(doc["features"])


def export_confusers(conn: psycopg.Connection, path: Path) -> int:
    """Write ref.confuser to a GeoJSON file (EPSG:26916 metres); return the row count."""
    rows = fetch_all(
        conn,
        """
        SELECT kind, imitates, assessment, basis, extent_m,
               ST_X(geom) AS x, ST_Y(geom) AS y
        FROM ref.confuser ORDER BY confuser_id
        """,
    )
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["x"], r["y"]]},
            "properties": {k: r[k] for k in ("kind", "imitates", "assessment", "basis", "extent_m")},
        }
        for r in rows
    ]
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, indent=1) + "\n"
    )
    return len(features)


def load_confusers(conn: psycopg.Connection, path: Path) -> int:
    """Restore ref.confuser from `export_confusers` output; idempotent on (kind, geom).

    Returns the number of rows inserted (rows already present are left alone).
    """
    features = json.loads(path.read_text())["features"]
    inserted = 0
    for feature in features:
        x, y = feature["geometry"]["coordinates"]
        if abs(x) <= 360 and abs(y) <= 90:
            raise ValueError(f"{path}: confuser coordinates look like lon/lat, need EPSG:26916")
        p = feature["properties"]
        cur = conn.execute(
            """
            INSERT INTO ref.confuser (kind, imitates, assessment, basis, extent_m, geom)
            SELECT %(kind)s, %(imitates)s, %(assessment)s, %(basis)s, %(extent_m)s,
                   ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 26916)
            WHERE NOT EXISTS (
                SELECT 1 FROM ref.confuser
                WHERE kind = %(kind)s AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 26916), 0.5)
            )
            """,
            {**p, "x": x, "y": y},
        )
        inserted += cur.rowcount
    return inserted
