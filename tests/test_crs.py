"""The cheapest bug prevention in the project (spec.md §3).

CRS bugs are silent: WhiteboxTools does not reproject and will process degrees as if they
were metres, producing a slope raster that looks plausible and is nonsense.
"""

from __future__ import annotations

from midden.db import OWNED_SCHEMAS, crs_violations, fetch_all

GEOMETRY_COLUMNS = """
    SELECT f_table_schema, f_table_name, f_geometry_column, srid
    FROM geometry_columns
    WHERE f_table_schema = ANY(%s)
"""


def test_all_geometry_columns_are_26916(db):
    """Every geometry column we own is EPSG:26916, bar explicit *_wgs84 export columns.

    Scoped to `ref` and `derived`: the base postgis image installs postgis_tiger_geocoder,
    whose `tiger` schema ships a dozen EPSG:4269 tables that are not ours and are never
    read by this project.
    """
    rows = fetch_all(db, GEOMETRY_COLUMNS, (list(OWNED_SCHEMAS),))
    assert rows, "no geometry columns found — has `midden db init` been run?"
    assert not crs_violations(rows), crs_violations(rows)


def test_wgs84_columns_are_named_for_it(db):
    """A 4326 column is only legitimate if its name says so, so nobody models against it."""
    rows = fetch_all(db, GEOMETRY_COLUMNS, (list(OWNED_SCHEMAS),))
    misnamed = [
        r for r in rows if r["srid"] == 4326 and not r["f_geometry_column"].endswith("_wgs84")
    ]
    assert not misnamed, misnamed
