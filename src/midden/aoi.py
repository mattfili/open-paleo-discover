"""Areas of interest: the seed table, the seeder, and read access.

Every fetch, derivation, and model run is AOI-scoped (spec.md §2), so this is the table
everything else hangs off.

spec.md §2: "Do not hardcode bounding boxes. Seed `derived.aoi` by querying the
authoritative boundary services and matching on name, so unit boundaries and spellings
come from the agency that owns them rather than from this document." The seed table below
therefore holds a *query*, never a coordinate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from midden import PROJECT_CRS
from midden.arcgis import query_layer
from midden.db import fetch_all

__all__ = ["SEED", "Aoi", "SeedSpec", "get_aoi", "list_aois", "seed_aois"]

# --- boundary services ------------------------------------------------------
#
# TNMap's ENVIRONMENTAL/PUBLIC_LANDS MapServer, which spec.md §2 names, currently answers
# "Service ... not started". These are the live authoritative equivalents; the National
# Register layer is on TNMap and is up.

TDEC_PUBLIC_ACCESS = (
    "https://services5.arcgis.com/bPacKTm9cauMXVfn/arcgis/rest/services"
    "/TDEC_Public_Access_Lands/FeatureServer/0"
)
NASHVILLE_PARKS = (
    "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services"
    "/Park_Boundary_View/FeatureServer/6"
)
TNMAP_NRHP = (
    "https://tnmap.tn.gov/arcgis/rest/services/HISTORICAL"
    "/NATIONAL_REGISTER_TN/MapServer/2"
)


@dataclass(frozen=True, slots=True)
class SeedSpec:
    """One AOI to seed: what to call it and how to find its boundary."""

    slug: str
    name: str
    county: str
    kind: str
    role: str
    layer: str
    where: str
    note: str = ""


@dataclass(frozen=True, slots=True)
class Aoi:
    """An area of interest as stored, geometry in the project CRS."""

    id: int
    slug: str
    name: str
    kind: str
    role: str
    area_km2: float
    geom: BaseGeometry
    source: str | None = None

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(xmin, ymin, xmax, ymax) in the project CRS, metres."""
        return self.geom.bounds


#: The seeded AOIs (spec.md §2). Two deviations from the table in the spec, both forced by
#: what the authoritative layers actually contain:
#:
#: - `harpeth-highway-100` does not exist. TDEC lists eight Harpeth River SP units and none
#:   is "Highway 100"; the Highway 70 Canoe Access is the river-access unit the spec
#:   describes, so the slug follows the agency's spelling.
#: - `castalian-springs` is not TDEC land and is absent from Public Access Lands. It is on
#:   TNMap's National Register layer as two nested polygons under REFNUM 71000838. The
#:   tight National Historic Landmark boundary carries the control_positive role; the wider
#:   National Register district is seeded alongside it for context and is not scored.
#:
#: `priest-drawdown` is deliberately absent: it is derived, not fetched (spec.md §7), and
#: arrives in M5.
SEED: tuple[SeedSpec, ...] = (
    SeedSpec("radnor-lake", "Radnor Lake State Natural Area", "Davidson",
             "state_park", "prospect", TDEC_PUBLIC_ACCESS,
             "NAME_2='Radnor Lake State Natural Area'",
             "Mature forest, minimal disturbance. Good bare-earth test case."),
    SeedSpec("harpeth-hidden-lake", "Harpeth River SP - Hidden Lake", "Cheatham",
             "state_park", "prospect", TDEC_PUBLIC_ACCESS,
             "NAME_2='Hidden Lake Entrance'",
             "Former quarry and resort. Expect 20th-c. earthmoving beside real terrace."),
    SeedSpec("harpeth-highway-70", "Harpeth River SP - Highway 70 Canoe Access", "Cheatham",
             "state_park", "shakeout", TDEC_PUBLIC_ACCESS,
             "NAME_2='Highway 70 Canoe Access'",
             "1 acre. Fast iteration only; too small for meaningful hydrology unbuffered."),
    SeedSpec("harpeth-newsoms-mill", "Harpeth River SP - Newsom's Mill", "Davidson",
             "state_park", "prospect", TDEC_PUBLIC_ACCESS,
             "NAME_2='Newsom''s Mill Site'",
             "Historic mill. Mills mean fords, and fords are long-duration crossings."),
    SeedSpec("beaman-park", "Alvin G. Beaman Park", "Davidson",
             "metro_park", "prospect", NASHVILLE_PARKS,
             "Name='Alvin G. Beaman Park'",
             "Metro Parks, not TDEC. Dissected Highland Rim - the one non-Central-Basin AOI."),
    SeedSpec("long-hunter", "Long Hunter State Park", "Wilson",
             "state_park", "prospect", TDEC_PUBLIC_ACCESS,
             "NAME_1='Long Hunter State Park' AND NAME_2 IS NULL",
             "Percy Priest shoreline. Main unit only; the glade and Sellars Farm are separate."),
    SeedSpec("harpeth-narrows", "Harpeth River SP - Narrows of the Harpeth", "Cheatham",
             "state_park", "control_detection", TDEC_PUBLIC_ACCESS,
             "NAME_2='Narrows of the Harpeth'",
             "Montgomery Bell Tunnel, c.1819. A cut earthwork that must appear in openness."),
    SeedSpec("mound-bottom", "Mound Bottom State Archaeological Area", "Cheatham",
             "state_park", "control_positive", TDEC_PUBLIC_ACCESS,
             "NAME_2='Mound Bottom State Archaeological Area'",
             "Mississippian mound complex. Managed access, guided tours only."),
    SeedSpec("castalian-springs", "Castalian Springs Mound Site (NHL)", "Sumner",
             "custom", "control_positive", TNMAP_NRHP,
             "Resource_Name='Castalian Springs (NHL Boundary)'",
             "NHL boundary, REFNUM 71000838. The scored control_positive footprint."),
    SeedSpec("castalian-springs-nr", "Castalian Springs (NR district)", "Sumner",
             "custom", "prospect", TNMAP_NRHP,
             "Resource_Name='Castalian Springs (NR Boundary)'",
             "Wider National Register district. Context only; not the scored control."),
    SeedSpec("bledsoe-creek", "Bledsoe Creek State Park", "Sumner",
             "state_park", "prospect", TDEC_PUBLIC_ACCESS,
             "NAME_1='Bledsoe Creek State Park'",
             "Old Hickory shoreline; pairs with Castalian Springs."),
    SeedSpec("cedars-of-lebanon", "Cedars of Lebanon State Park", "Wilson",
             "state_park", "prospect", TDEC_PUBLIC_ACCESS,
             "NAME_1='Cedars of Lebanon State Park'",
             "Cedar glade / karst. Different landform regime - useful contrast."),
    SeedSpec("montgomery-bell", "Montgomery Bell State Park", "Dickson",
             "state_park", "control_detection", TDEC_PUBLIC_ACCESS,
             "NAME_1='Montgomery Bell State Park' AND NAME_2 IS NULL",
             "19th-c. iron district. Charcoal hearths set search_radius_m."),
)


def to_multipolygon(geom: BaseGeometry, *, slug: str) -> tuple[MultiPolygon, bool]:
    """Coerce a boundary to a valid MultiPolygon. Returns (geometry, was_repaired).

    Boundary services publish self-intersecting rings often enough that this is routine —
    Radnor Lake is one. An invalid polygon does not raise in PostGIS; it silently returns
    wrong areas and wrong intersections, so it is repaired here and the repair is reported
    rather than done quietly.
    """
    repaired = False
    if not geom.is_valid:
        geom = shapely.make_valid(geom)
        repaired = True

    if isinstance(geom, Polygon):
        geom = MultiPolygon([geom])
    elif not isinstance(geom, MultiPolygon):
        # make_valid can return a GeometryCollection; keep only the polygonal parts.
        parts = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon | MultiPolygon)]
        if not parts:
            raise ValueError(
                f"{slug}: boundary has no polygonal component after repair "
                f"(got {geom.geom_type}). The layer query is probably matching the wrong "
                f"feature."
            )
        polygons: list[Polygon] = []
        for part in parts:
            polygons.extend(part.geoms if isinstance(part, MultiPolygon) else [part])
        geom = MultiPolygon(polygons)
        repaired = True

    if not geom.is_valid:
        raise ValueError(f"{slug}: boundary is still invalid after make_valid().")
    return geom, repaired


def fetch_boundary(spec: SeedSpec) -> tuple[MultiPolygon, bool, dict[str, Any]]:
    """Fetch one AOI boundary from its authoritative service.

    Raises when the query matches anything other than exactly one feature — a seed spec
    that matches two units would otherwise pick one arbitrarily and look fine.
    """
    rows = query_layer(spec.layer, spec.where, out_crs=PROJECT_CRS)
    if len(rows) != 1:
        raise ValueError(
            f"{spec.slug}: expected exactly 1 feature from {spec.layer} for "
            f"{spec.where!r}, got {len(rows)}. The layer's names may have changed; "
            f"query the service and update SEED rather than hardcoding a boundary."
        )
    attributes, geometry = rows[0]
    multipolygon, repaired = to_multipolygon(geometry, slug=spec.slug)
    return multipolygon, repaired, attributes


def upsert_aoi(conn: psycopg.Connection, spec: SeedSpec, geom: MultiPolygon) -> str:
    """Insert or update one AOI by slug. Returns 'inserted' or 'updated'."""
    row = fetch_all(
        conn,
        """
        INSERT INTO derived.aoi (slug, name, kind, role, source, geom)
        VALUES (%s, %s, %s, %s, %s, ST_GeomFromText(%s, 26916))
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name, kind = EXCLUDED.kind, role = EXCLUDED.role,
            source = EXCLUDED.source, geom = EXCLUDED.geom
        RETURNING (xmax = 0) AS inserted
        """,
        (spec.slug, spec.name, spec.kind, spec.role, spec.layer, geom.wkt),
    )
    return "inserted" if row[0]["inserted"] else "updated"


def seed_aois(
    conn: psycopg.Connection, specs: tuple[SeedSpec, ...] = SEED
) -> list[tuple[str, str, bool]]:
    """Seed every AOI from its authoritative service.

    Returns one `(slug, action, was_repaired)` per AOI. Idempotent: re-running refreshes
    geometry from the service, which is the point — the agency owns the boundary.
    """
    results = []
    for spec in specs:
        geom, repaired, _ = fetch_boundary(spec)
        results.append((spec.slug, upsert_aoi(conn, spec, geom), repaired))
    return results


def _row_to_aoi(row: dict[str, Any]) -> Aoi:
    """Build an Aoi from a query row carrying WKT geometry."""
    return Aoi(
        id=row["id"], slug=row["slug"], name=row["name"], kind=row["kind"],
        role=row["role"], area_km2=row["area_km2"], source=row.get("source"),
        geom=shapely.from_wkt(row["wkt"]),
    )


_SELECT = """
    SELECT id, slug, name, kind, role, area_km2, source, ST_AsText(geom) AS wkt
    FROM derived.aoi
"""


def list_aois(conn: psycopg.Connection, role: str | None = None) -> list[Aoi]:
    """Return every AOI, optionally filtered by role, largest first."""
    where, params = ("WHERE role = %s", (role,)) if role else ("", ())
    return [_row_to_aoi(r) for r in
            fetch_all(conn, f"{_SELECT} {where} ORDER BY area_km2 DESC", params)]


def get_aoi(conn: psycopg.Connection, slug: str) -> Aoi:
    """Return one AOI by slug, or raise with the available slugs listed."""
    rows = fetch_all(conn, f"{_SELECT} WHERE slug = %s", (slug,))
    if not rows:
        known = [r["slug"] for r in fetch_all(conn, "SELECT slug FROM derived.aoi ORDER BY slug")]
        raise KeyError(
            f"No AOI {slug!r}. Known: {', '.join(known) or '(none - run: midden aoi seed)'}"
        )
    return _row_to_aoi(rows[0])
