"""NRHP archaeological listings as mound_earthwork labels (ROADMAP A3).

Seeds `ref.control_sites` from the TNMap National Register points layer — the same
authoritative service the AOI seeder queries for boundaries. Under the registry these
are labels for `mound_earthwork` specifically: NRHP archaeological listings skew
monumental, and that bias is the reason they match this one class rather than the
project (label provenance records `source='nrhp'` so the pooling rule can see it).

Two honesty rules, both structural here:

- **Address-restricted sites are excluded rather than approximated** — and on this
  service most are simply absent from the points layer (Mound Bottom itself does not
  appear). What loads is the public subset, and the derivation records the WHERE
  clause so the selection is reproducible.
- The layer has no resource-type field, so "archaeological" is a recorded
  name-pattern filter, not a metadata read. A miss (an archaeological listing whose
  name matches no pattern) stays missing until the pattern is widened — widening is
  a recorded parameter change.
"""

from __future__ import annotations

from typing import Any

import psycopg

from midden.arcgis import query_layer
from midden.db import fetch_all

__all__ = ["MIDDLE_TN_COUNTIES", "NRHP_POINTS_URL", "seed_nrhp"]

NRHP_POINTS_URL = (
    "https://tnmap.tn.gov/arcgis/rest/services/HISTORICAL"
    "/NATIONAL_REGISTER_TN/MapServer/0"
)

#: Name patterns that identify archaeological listings on a layer with no type field.
#: Recorded in the derivation; widen deliberately, never silently.
NAME_PATTERNS = (
    "%MOUND%",
    "%EARTHWORK%",
    "%ARCHAEOLOG%",
    "%ARCHEOLOG%",
    # The space in "%INDIAN %" is load-bearing: bare "%INDIAN%" matched "Indiana
    # Avenue Historic District" (saved only by the county filter).
    "%INDIAN %",
    "%PREHISTORIC%",
    "%STONE FORT%",
    "%VILLAGE SITE%",
    "SITE 40%",
    "CASTALIAN%",
)

#: Same-site duplicate listings (a boundary increase carries its own REFNUM); the
#: original listing's point is the label, the increase is excluded.
DUPLICATE_REFNUMS = frozenset({"12000121"})  # Fewkes Group boundary increase

#: Middle Tennessee (Central Basin + Highland Rim) counties, per spec.md §2's frame.
MIDDLE_TN_COUNTIES = (
    "Davidson",
    "Williamson",
    "Sumner",
    "Cheatham",
    "Dickson",
    "Wilson",
    "Rutherford",
    "Maury",
    "Robertson",
    "Montgomery",
    "Trousdale",
    "Smith",
    "Hickman",
    "Giles",
    "Marshall",
    "Bedford",
    "Cannon",
    "DeKalb",
    "Coffee",
    "Warren",
    "Franklin",
    "Lincoln",
    "Moore",
    "Lawrence",
    "Lewis",
    "Perry",
    "Humphreys",
    "Houston",
    "Stewart",
    "Macon",
    "Jackson",
    "Putnam",
    "Overton",
)

#: Horizontal error assigned to an NRHP point: the service points are placed on the
#: property, not surveyed to the monument. A judgment call, so a named parameter.
NRHP_POSITIONAL_CONFIDENCE_M = 150.0


def _where() -> str:
    """The recorded selection clause. Pure."""
    names = " OR ".join(f"UPPER(Resource_Name) LIKE '{p}'" for p in NAME_PATTERNS)
    counties = ", ".join(f"'{c}'" for c in MIDDLE_TN_COUNTIES)
    return f"({names}) AND County IN ({counties})"


def seed_nrhp(conn: psycopg.Connection) -> list[dict[str, Any]]:
    """Load public NRHP archaeological points as mound_earthwork control sites.

    Idempotent by REFNUM: an existing (source='nrhp', source_id) row is left alone —
    including its review_status — and reported as skipped. Address-restricted rows
    (the Address field says so) are excluded, not approximated.
    """
    from midden import __version__
    from midden.derivation import open_derivation

    rows = query_layer(NRHP_POINTS_URL, _where(), out_fields="*")
    existing = {
        r["source_id"]
        for r in fetch_all(
            conn,
            "SELECT source_id FROM ref.control_sites WHERE source = 'nrhp'",
        )
    }

    report: list[dict[str, Any]] = []
    with open_derivation(
        conn,
        operation="labels.seed_nrhp",
        tool="TNMap NRHP points + midden.nrhp",
        tool_version=__version__,
        params={
            "where": _where(),
            "positional_confidence_m": NRHP_POSITIONAL_CONFIDENCE_M,
            "class_id": "mound_earthwork",
        },
        inputs=[NRHP_POINTS_URL],
    ) as derivation_id:
        for attributes, geometry in rows:
            refnum = attributes.get("REFNUM")
            name = (attributes.get("Resource_Name") or "").strip()
            address = attributes.get("Address") or ""
            listed = (attributes.get("Listed_Date") or "").strip()
            if refnum in DUPLICATE_REFNUMS:
                report.append(
                    {
                        "refnum": refnum,
                        "name": name,
                        "action": "excluded",
                        "why": "same-site duplicate listing",
                    }
                )
                continue
            if "restricted" in address.lower():
                report.append(
                    {
                        "refnum": refnum,
                        "name": name,
                        "action": "excluded",
                        "why": "address restricted",
                    }
                )
                continue
            if refnum in existing:
                report.append(
                    {
                        "refnum": refnum,
                        "name": name,
                        "action": "skipped",
                        "why": "already seeded",
                    }
                )
                continue
            point = geometry.centroid  # points arrive as points; centroid is a no-op
            conn.execute(
                """
                INSERT INTO ref.control_sites
                    (class_id, name, source, source_id, positional_confidence_m,
                     review_status, review_note, geom, derivation_id)
                VALUES ('mound_earthwork', %s, 'nrhp', %s, %s, 'unreviewed',
                        %s, ST_SetSRID(ST_MakePoint(%s, %s), 26916), %s)
                """,
                (
                    name,
                    refnum,
                    NRHP_POSITIONAL_CONFIDENCE_M,
                    f"NRHP listed {listed}".strip() or None,
                    point.x,
                    point.y,
                    derivation_id,
                ),
            )
            existing.add(refnum)
            report.append({"refnum": refnum, "name": name, "action": "inserted"})
    return report
