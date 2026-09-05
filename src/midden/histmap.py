"""Historic USGS topographic quads as a label source (ROADMAP A1).

Fetches Historical Topographic Map Collection (HTMC) GeoTIFF scans through the TNM
Access API, warps them to the project CRS, catalogues them in `ref.histmap_sheet`, and
loads symbols digitized from them into `ref.control_sites`.

This is deliberately not an intake driver: the intake pipeline is vector-only end to
end (its cache is a GeoPackage and its load is `to_postgis`), and a scanned map is a
raster. The pattern mirrored here is terrain's fetch -> warp -> COG -> catalogue ->
derivation instead. spec.md §5 names a `topoview` driver and §6 an `http_file` one;
neither fits, and ROADMAP records why.

The load-bearing number is `positional_confidence_m`: a historic quad is not
survey-grade, so every point digitized from a sheet inherits the sheet's error and
that error is the tolerance radius in validation. The value is NMAS horizontal
accuracy for the scale (CE90 of 1/50 inch at publication scale for 1:20,000 and
smaller) plus a georeferencing margin, both recorded in the fetch derivation.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import psycopg
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

from midden import PROJECT_CRS
from midden.aoi import Aoi
from midden.db import fetch_all

__all__ = [
    "SheetInfo",
    "fetch_sheet",
    "get_sheet",
    "load_sites",
    "nmas_confidence_m",
    "search_sheets",
    "tile_sheet",
]

_TNM_PRODUCTS = "https://tnmaccess.nationalmap.gov/api/v1/products"
_TNM_DATASET = "Historical Topographic Maps"
_TITLE_RE = re.compile(r"USGS 1:(\d+)-scale Quadrangle for (.+?),? (\d{4})$")

#: Extra horizontal error budget for the scan's own georeferencing, on top of NMAS.
#: A judgment call, so it is a named parameter recorded in every fetch derivation.
GEOREF_MARGIN_M = 15.0


@dataclass(frozen=True, slots=True)
class SheetInfo:
    """One HTMC sheet as the TNM API describes it."""

    sheet_id: str  # e.g. TN_Burns_149363_1936_24000
    cell_name: str
    map_year: int
    scale: int
    geotiff_url: str
    bbox_wgs84: tuple[float, float, float, float]


def nmas_confidence_m(scale: int, *, georef_margin_m: float = GEOREF_MARGIN_M) -> float:
    """Horizontal error for a sheet at `scale`, in metres. Pure.

    NMAS (1947): 90% of well-defined points within 1/50 inch at publication scale for
    scales of 1:20,000 and smaller — 12.2 m at 1:24,000, 31.8 m at 1:62,500. The
    georeferencing margin covers the scan-to-world fit on top of that.
    """
    return round(scale * (0.0254 / 50.0) + georef_margin_m, 1)


def _parse_item(item: dict) -> SheetInfo | None:
    """Turn one TNM product item into a SheetInfo. Pure.

    Items without a GeoTIFF URL (GeoPDF-only products) are dropped — that is a format
    gap, not an error, and the caller reports how many were skipped.
    """
    geotiff = (item.get("urls") or {}).get("GeoTIFF")
    match = _TITLE_RE.match(item.get("title", ""))
    if not geotiff or not match:
        return None
    scale, cell, year = int(match[1]), match[2], int(match[3])
    # Unquoted so 'White%20Bluff' stays 'White Bluff': TN_Burns_149363_1936_24000_geo
    stem = Path(urllib.parse.unquote(urllib.parse.urlparse(geotiff).path)).stem
    box = item.get("boundingBox") or {}
    return SheetInfo(
        sheet_id=stem.removesuffix("_geo"),
        cell_name=cell.removesuffix(", TN"),
        map_year=year,
        scale=scale,
        geotiff_url=geotiff,
        bbox_wgs84=(box.get("minX"), box.get("minY"), box.get("maxX"), box.get("maxY")),
    )


def search_sheets(aoi: Aoi, *, max_items: int = 100) -> list[SheetInfo]:
    """List HTMC sheets intersecting an AOI, oldest edition first.

    The TNM bbox is WGS84 lon/lat; the AOI is project-CRS metres, so the bounds are
    transformed on the way out. GeoPDF-only items are silently absent from the result
    by construction (see _parse_item) — the count difference is visible in the CLI.
    """
    transformer = Transformer.from_crs(PROJECT_CRS, "EPSG:4326", always_xy=True)
    xmin, ymin, xmax, ymax = aoi.geom.bounds
    west, south = transformer.transform(xmin, ymin)
    east, north = transformer.transform(xmax, ymax)
    query = urllib.parse.urlencode(
        {
            "datasets": _TNM_DATASET,
            "bbox": f"{west},{south},{east},{north}",
            "max": max_items,
            "outputFormat": "JSON",
        }
    )
    with urllib.request.urlopen(f"{_TNM_PRODUCTS}?{query}", timeout=60) as response:
        payload = json.load(response)
    sheets = [s for s in (_parse_item(i) for i in payload.get("items", [])) if s]
    # One scan id per sheet_id already; sort oldest first, largest scale last.
    return sorted(sheets, key=lambda s: (s.map_year, s.scale, s.sheet_id))


def _read_rgb(src: rasterio.DatasetReader) -> np.ndarray:
    """Read a scan as (3, h, w) uint8, expanding a palette if the file carries one."""
    if src.count >= 3:
        return src.read([1, 2, 3])
    band = src.read(1)
    try:
        colormap = src.colormap(1)
    except ValueError:
        # Greyscale single band: replicate rather than invent colour.
        return np.stack([band, band, band]).astype("uint8")
    lut = np.zeros((256, 3), dtype="uint8")
    for value, rgba in colormap.items():
        lut[value] = rgba[:3]
    return np.moveaxis(lut[band], -1, 0)


def _warp_scan(src_path: Path, dest: Path) -> Path:
    """Warp a quad scan to EPSG:26916 as 3-band RGB at its native resolution.

    Nearest resampling: a scanned map is symbology, not a continuous surface, and
    interpolating ink produces colours that exist on no edition. This is deliberately
    not dem.py's warp — that one is single-band float32 bilinear with a
    WhiteboxTools-safe profile, and a quad never goes to WhiteboxTools.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(src_path) as src:
        rgb = _read_rgb(src)
        transform, width, height = calculate_default_transform(
            src.crs, PROJECT_CRS, src.width, src.height, *src.bounds
        )
        profile = {
            "driver": "GTiff",
            "crs": PROJECT_CRS,
            "transform": transform,
            "width": width,
            "height": height,
            "count": 3,
            "dtype": "uint8",
            "compress": "DEFLATE",
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256,
            "photometric": "RGB",
        }
        with rasterio.open(dest, "w", **profile) as dst:
            for band in range(3):
                reproject(
                    source=rgb[band],
                    destination=rasterio.band(dst, band + 1),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=PROJECT_CRS,
                    resampling=Resampling.nearest,
                )
    return dest


def _download(url: str, dest: Path) -> Path:
    """Download a URL to a file if it is not already there (content is immutable)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        with urllib.request.urlopen(url, timeout=300) as response:
            dest.write_bytes(response.read())
    return dest


def fetch_sheet(conn: psycopg.Connection, sheet: SheetInfo, *, config=None) -> Path:
    """Download, warp, COG, and catalogue one sheet. Returns the local COG path."""
    from midden.config import settings
    from midden.derivation import open_derivation
    from midden.terrain.cog import write_cog

    config = config or settings()
    confidence = nmas_confidence_m(sheet.scale)
    raw = config.raw_dir / "histmap" / f"{sheet.sheet_id}.tif"
    dest = config.cogs_dir / "histmap" / f"{sheet.sheet_id}.tif"

    with open_derivation(
        conn,
        operation="histmap.fetch",
        tool="TNM Access API + rasterio",
        tool_version=rasterio.__version__,
        params={
            "sheet_id": sheet.sheet_id,
            "map_year": sheet.map_year,
            "scale": sheet.scale,
            "positional_confidence_m": confidence,
            "georef_margin_m": GEOREF_MARGIN_M,
            "resampling": "nearest",
        },
        inputs=[sheet.geotiff_url],
    ) as derivation_id:
        _download(sheet.geotiff_url, raw)
        warped = _warp_scan(raw, dest.with_suffix(".warped.tif"))
        write_cog(warped, dest)
        warped.unlink()
        with rasterio.open(dest) as cog:
            xmin, ymin, xmax, ymax = cog.bounds
        conn.execute(
            """
            INSERT INTO ref.histmap_sheet
                (sheet_id, cell_name, map_year, scale, source_url, path,
                 positional_confidence_m, footprint, derivation_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s,
                    ST_MakeEnvelope(%s, %s, %s, %s, 26916), %s)
            ON CONFLICT (sheet_id) DO UPDATE SET
                path = EXCLUDED.path,
                positional_confidence_m = EXCLUDED.positional_confidence_m,
                footprint = EXCLUDED.footprint,
                derivation_id = EXCLUDED.derivation_id
            """,
            (
                sheet.sheet_id,
                sheet.cell_name,
                sheet.map_year,
                sheet.scale,
                sheet.geotiff_url,
                str(dest),
                confidence,
                xmin,
                ymin,
                xmax,
                ymax,
                derivation_id,
            ),
        )
    return dest


def get_sheet(conn: psycopg.Connection, sheet_id: str) -> dict:
    """Return one catalogued sheet row, or raise naming what is catalogued."""
    rows = fetch_all(
        conn, "SELECT * FROM ref.histmap_sheet WHERE sheet_id = %s", (sheet_id,)
    )
    if not rows:
        known = [
            r["sheet_id"]
            for r in fetch_all(
                conn, "SELECT sheet_id FROM ref.histmap_sheet ORDER BY sheet_id"
            )
        ]
        raise KeyError(
            f"No sheet {sheet_id!r} in ref.histmap_sheet. Catalogued: {known or '(none)'}. "
            "Run `midden histmap fetch` first."
        )
    return rows[0]


def tile_sheet(
    path: Path, out_dir: Path, *, tile_px: int = 1400, overlap_px: int = 100
) -> Path:
    """Cut a warped sheet into PNG tiles for visual digitization.

    Writes `<out_dir>/<row>_<col>.png` per tile plus `index.json` mapping each tile to
    its affine transform, so a pixel picked on a tile converts to project-CRS metres
    without reopening the raster. Native resolution — downsampling a 1:24,000 scan
    erases exactly the symbols being digitized.
    """
    from PIL import Image
    from rasterio.windows import Window
    from rasterio.windows import transform as window_transform

    out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    step = tile_px - overlap_px
    with rasterio.open(path) as src:
        for row_off in range(0, src.height, step):
            for col_off in range(0, src.width, step):
                window = Window(
                    col_off,
                    row_off,
                    min(tile_px, src.width - col_off),
                    min(tile_px, src.height - row_off),
                )
                name = f"{row_off}_{col_off}.png"
                data = np.moveaxis(src.read(window=window), 0, -1)
                Image.fromarray(data).save(out_dir / name)
                t = window_transform(window, src.transform)
                index.append(
                    {
                        "tile": name,
                        "width": int(window.width),
                        "height": int(window.height),
                        "transform": [t.a, t.b, t.c, t.d, t.e, t.f],
                    }
                )
    (out_dir / "index.json").write_text(
        json.dumps({"crs": PROJECT_CRS, "source": str(path), "tiles": index}, indent=1)
    )
    return out_dir


def load_sites(
    conn: psycopg.Connection, sheet_id: str, geojson_path: Path, *, method: str
) -> int:
    """Load digitized symbols from a GeoJSON file into ref.control_sites.

    Each feature: Point geometry in EPSG:26916 with properties `class_id` and `name`.
    Provenance is mandatory and comes from the sheet row: source_sheet, map_year, and
    positional_confidence_m travel with every point. Points land as
    review_status='unreviewed' — machine digitization is never silently promoted.
    Re-loading a sheet replaces that sheet's unreviewed points rather than duplicating
    them; confirmed or rejected rows are left alone and reported.
    """
    from midden.derivation import open_derivation

    sheet = get_sheet(conn, sheet_id)
    features = json.loads(geojson_path.read_text())["features"]
    classes = {
        r["class_id"] for r in fetch_all(conn, "SELECT class_id FROM ref.target_class")
    }
    unknown = {f["properties"]["class_id"] for f in features} - classes
    if unknown:
        raise ValueError(
            f"Unknown class_id(s) {sorted(unknown)}; see `midden classes`."
        )

    # CRS trap: RFC 7946 GeoJSON is WGS84 by definition, and most tools export lon/lat.
    # Degrees stamped as UTM metres would poison ref.control_sites silently — points
    # would sit near the false origin and later read as EPT "data gaps", not errors.
    degreeish = [
        f["properties"]["name"]
        for f in features
        if abs(f["geometry"]["coordinates"][0]) <= 360
        and abs(f["geometry"]["coordinates"][1]) <= 90
    ]
    if degreeish:
        raise ValueError(
            f"{geojson_path}: coordinates for {degreeish} look like lon/lat degrees. "
            f"Sites files must be EPSG:26916 metres (the tiles' index.json CRS)."
        )
    outside = [
        f["properties"]["name"]
        for f in features
        if not fetch_all(
            conn,
            "SELECT ST_Contains(footprint, ST_SetSRID(ST_MakePoint(%s, %s), 26916)) AS ok "
            "FROM ref.histmap_sheet WHERE sheet_id = %s",
            (*f["geometry"]["coordinates"], sheet_id),
        )[0]["ok"]
    ]
    if outside:
        raise ValueError(
            f"{geojson_path}: {outside} fall outside sheet {sheet_id}'s footprint — "
            f"wrong sheet, wrong CRS, or a bad tile transform."
        )

    with open_derivation(
        conn,
        operation="histmap.digitize",
        tool=method,
        tool_version="-",
        params={"sheet_id": sheet_id, "n_features": len(features), "method": method},
        inputs=[str(geojson_path)],
    ) as derivation_id:
        reviewed = fetch_all(
            conn,
            "SELECT count(*) AS n FROM ref.control_sites "
            "WHERE source_sheet = %s AND review_status <> 'unreviewed'",
            (sheet_id,),
        )[0]["n"]
        conn.execute(
            "DELETE FROM ref.control_sites "
            "WHERE source_sheet = %s AND review_status = 'unreviewed'",
            (sheet_id,),
        )
        for feature in features:
            x, y = feature["geometry"]["coordinates"]
            props = feature["properties"]
            conn.execute(
                """
                INSERT INTO ref.control_sites
                    (class_id, name, source, source_sheet, map_year,
                     positional_confidence_m, review_status, geom, derivation_id)
                VALUES (%s, %s, 'usgs_histmap', %s, %s, %s, 'unreviewed',
                        ST_SetSRID(ST_MakePoint(%s, %s), 26916), %s)
                """,
                (
                    props["class_id"],
                    props["name"],
                    sheet_id,
                    sheet["map_year"],
                    # A feature may carry its own confidence — sheet error plus the
                    # digitization method's pointing error — but never less than the
                    # sheet's: a point cannot be more certain than the map it came from.
                    max(
                        float(props.get("positional_confidence_m") or 0.0),
                        sheet["positional_confidence_m"],
                    ),
                    x,
                    y,
                    derivation_id,
                ),
            )
    if reviewed:
        # Not silent: reviewed rows for this sheet were kept, and the caller should know.
        print(f"note: {reviewed} reviewed point(s) for {sheet_id} left untouched")
    return len(features)
