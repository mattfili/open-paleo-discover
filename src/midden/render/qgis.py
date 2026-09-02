"""QGIS project emitter (spec.md §8).

QGIS is the interactive surface for this project. It reads COGs natively, windowed and with
overviews, straight off disk; it connects to PostGIS natively; it does dynamic symbology and
on-the-fly reprojection. For a single-operator proof of concept that is everything a web
explorer would have provided, at zero engineering cost.

What this saves is the thing you would otherwise do at the start of every session:
re-adding a dozen layers and re-styling them. Plain XML templating, no PyQGIS dependency —
which matters because PyQGIS is only importable from inside a QGIS install.

Raster paths are absolute. A `.qgs` is gitignored precisely because it embeds them.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

from midden.render.core import RasterLayer, Scene, VectorLayer

__all__ = ["render_qgis_project"]

_CRS_AUTHID = "EPSG:26916"
_CRS_SRSID = "3083"          # QGIS internal id for EPSG:26916
_CRS_WKT = 'PROJCRS["NAD83 / UTM zone 16N"]'

#: Colour ramps per palette, as (position, r, g, b) stops matching render.preview.
_RAMPS = {
    "grey": [(0.0, 0, 0, 0), (1.0, 255, 255, 255)],
    "viridis": [(0.0, 68, 1, 84), (0.25, 59, 82, 139), (0.5, 33, 145, 140),
                (0.75, 94, 201, 98), (1.0, 253, 231, 37)],
    "terrace": [(0.0, 40, 40, 46), (0.25, 70, 100, 130), (0.5, 250, 200, 60),
                (0.75, 150, 180, 110), (1.0, 110, 130, 120)],
}


def _crs(parent: ET.Element) -> ET.Element:
    """Append the project CRS block QGIS expects on a layer."""
    srs = ET.SubElement(parent, "srs")
    spatial = ET.SubElement(srs, "spatialrefsys")
    spatial.set("nativeFormat", "Wkt")
    for tag, text in (
        ("wkt", _CRS_WKT), ("proj4", "+proj=utm +zone=16 +datum=NAD83 +units=m +no_defs"),
        ("srsid", _CRS_SRSID), ("srid", "26916"), ("authid", _CRS_AUTHID),
        ("description", "NAD83 / UTM zone 16N"), ("projectionacronym", "utm"),
        ("ellipsoidacronym", "EPSG:7019"), ("geographicflag", "false"),
    ):
        ET.SubElement(spatial, tag).text = text
    return srs


def _raster_layer(layer: RasterLayer, order: int) -> ET.Element:
    """One raster maplayer element, styled with a single-band pseudocolour ramp."""
    element = ET.Element("maplayer")
    element.set("type", "raster")
    element.set("hasScaleBasedVisibilityFlag", "0")
    ET.SubElement(element, "id").text = f"{layer.kind}_{order}"
    ET.SubElement(element, "layername").text = f"{layer.name} ({layer.resolution_m:g} m)"
    ET.SubElement(element, "datasource").text = str(layer.path.resolve())
    ET.SubElement(element, "provider").text = "gdal"
    if layer.legend:
        ET.SubElement(element, "abstract").text = layer.legend
    _crs(element)

    low, high = layer.window or (0.0, 1.0)
    renderer = ET.SubElement(element, "pipe")
    raster = ET.SubElement(renderer, "rasterrenderer")
    raster.set("type", "singlebandpseudocolor")
    raster.set("band", "1")
    raster.set("opacity", str(layer.opacity))
    raster.set("classificationMin", str(low))
    raster.set("classificationMax", str(high))

    shader = ET.SubElement(raster, "rastershader")
    ramp_shader = ET.SubElement(shader, "colorrampshader")
    ramp_shader.set("colorRampType", "DISCRETE" if layer.palette == "terrace" else "INTERPOLATED")
    ramp_shader.set("classificationMode", "1")
    for position, red, green, blue in _RAMPS.get(layer.palette, _RAMPS["grey"]):
        item = ET.SubElement(ramp_shader, "item")
        item.set("value", str(low + position * (high - low)))
        item.set("color", f"#{red:02x}{green:02x}{blue:02x}")
        item.set("alpha", "255")
        item.set("label", f"{low + position * (high - low):.2f}")
    return element


def _vector_layer(layer: VectorLayer, order: int, project_dir: Path) -> ET.Element:
    """One vector maplayer, sourced from a GeoJSON written beside the project."""
    source = project_dir / f"{layer.name.lower().replace(' ', '_')}.geojson"
    import json

    source.write_text(json.dumps(layer.geojson))

    element = ET.Element("maplayer")
    element.set("type", "vector")
    element.set("geometry", layer.geometry.capitalize())
    ET.SubElement(element, "id").text = f"vec_{order}"
    ET.SubElement(element, "layername").text = layer.name
    ET.SubElement(element, "datasource").text = f"./{source.name}"
    ET.SubElement(element, "provider").text = "ogr"
    if layer.legend:
        ET.SubElement(element, "abstract").text = layer.legend
    _crs(element)

    symbol_type = {"point": "marker", "line": "line", "polygon": "fill"}[layer.geometry]
    renderer = ET.SubElement(element, "renderer-v2")
    renderer.set("type", "singleSymbol")
    symbols = ET.SubElement(renderer, "symbols")
    symbol = ET.SubElement(symbols, "symbol")
    symbol.set("type", symbol_type)
    symbol.set("name", "0")
    sub = ET.SubElement(symbol, "layer")
    sub.set("class", {"marker": "SimpleMarker", "line": "SimpleLine",
                      "fill": "SimpleFill"}[symbol_type])
    props = {
        "color": _rgba(layer.fill or layer.stroke, 60 if layer.fill else 0),
        "outline_color": _rgba(layer.stroke, 255),
        "outline_width": str(layer.width / 4),
        "line_color": _rgba(layer.stroke, 255),
        "line_width": str(layer.width / 4),
        "size": "2",
    }
    for key, value in props.items():
        option = ET.SubElement(sub, "prop")
        option.set("k", key)
        option.set("v", value)
    return element


def _rgba(colour: str, alpha: int) -> str:
    """Convert #rrggbb to the r,g,b,a string QGIS symbol properties use."""
    value = colour.lstrip("#")
    red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"{red},{green},{blue},{alpha}"


def render_qgis_project(scene: Scene, dest: Path) -> Path:
    """Write a `.qgs` project with the AOI's rasters and vectors pre-loaded and styled."""
    if scene.is_empty:
        raise ValueError(
            f"{scene.aoi_slug}: nothing to add to a project. Derive terrain first."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("qgis")
    root.set("projectname", f"midden — {scene.title}")
    root.set("version", "3.34.0")
    ET.SubElement(root, "title").text = f"midden — {scene.title}"

    xmin, ymin, xmax, ymax = scene.bounds
    extent = ET.SubElement(root, "extent")
    for tag, value in (("xmin", xmin), ("ymin", ymin), ("xmax", xmax), ("ymax", ymax)):
        ET.SubElement(extent, tag).text = f"{value:.4f}"
    _crs(ET.SubElement(root, "projectCrs"))

    tree = ET.SubElement(root, "layer-tree-group")
    layers = ET.SubElement(root, "projectlayers")

    entries: list[tuple[str, ET.Element, bool]] = []
    for order, raster in enumerate(scene.rasters):
        entries.append((f"{raster.kind}_{order}", _raster_layer(raster, order), raster.visible))
    for order, vector in enumerate(scene.vectors):
        entries.append((f"vec_{order}", _vector_layer(vector, order, dest.parent), vector.visible))

    for identifier, element, visible in entries:
        layers.append(element)
        node = ET.SubElement(tree, "layer-tree-layer")
        node.set("id", identifier)
        node.set("name", element.find("layername").text)
        node.set("checked", "Qt::Checked" if visible else "Qt::Unchecked")
        node.set("source", element.find("datasource").text)
        node.set("providerKey", element.find("provider").text)

    pretty = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
    dest.write_text(pretty, encoding="utf-8")
    return dest
