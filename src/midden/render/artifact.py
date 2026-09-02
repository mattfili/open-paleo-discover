"""Self-contained HTML export (spec.md §8).

One file, no server, no tile requests. That constraint is not stylistic: Claude artifacts
run in a sandboxed cross-origin iframe whose content-security policy allows external
*scripts* from a short CDN allowlist but blocks external *stylesheets* from everywhere
except fonts.googleapis.com, and blocks runtime fetch/XHR to other hosts entirely. So:

- Leaflet's script loads from cdnjs; its stylesheet is inlined from a vendored copy.
- Vector layers are inlined as GeoJSON.
- Raster overlays are base64 PNGs, warped to Web Mercator so Leaflet places them where the
  ground actually is, and downsampled to at most 1500 px on the long edge.
- There is no basemap, because tile requests would be blocked. The multidirectional
  hillshade is the ground the other layers sit on.
- Circle markers, not Leaflet's default icons: the inlined stylesheet's relative `url()`
  references to `images/` are dead, so anything relying on them would render as a gap.

The exporter asserts on the finished byte count and fails loudly, because an artifact that
is too large does not degrade — it simply does not load.
"""

from __future__ import annotations

import base64
import html
import json
import tempfile
from pathlib import Path

from midden.render.core import RasterLayer, Scene
from midden.render.preview import Stretch, percentile_stretch, to_web_png

__all__ = ["MAX_ARTIFACT_BYTES", "render_artifact"]

#: Hard ceiling on the finished file. The artifact runtime rejects anything larger, and a
#: rejected artifact fails silently from the reader's point of view.
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024

#: Warn well before the ceiling: base64 inflates by about a third, so a file that looks
#: comfortable as PNGs on disk may not be once encoded.
WARN_ARTIFACT_BYTES = 8 * 1024 * 1024

_LEAFLET_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"
_LEAFLET_CSS = Path(__file__).with_name("_leaflet.css")


def _encode_raster(layer: RasterLayer, work: Path, max_px: int) -> dict | None:
    """Warp, render, and base64-encode one raster. Returns None if it cannot be read."""
    stretch = Stretch.of(*layer.window) if layer.window else (
        percentile_stretch(layer.path, *(layer.percentile or (2, 98)))
    )
    png, bounds = to_web_png(
        layer.path, work / f"{layer.kind}.png",
        stretch=stretch, palette=layer.palette, max_px=max_px,
    )
    return {
        "id": layer.kind,
        "name": layer.name,
        "legend": layer.legend,
        "grid": layer.grid,
        "resolution_m": layer.resolution_m,
        "range": [round(stretch.low, 3), round(stretch.high, 3)],
        "visible": layer.visible,
        "bounds": [[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
        "data": base64.b64encode(png.read_bytes()).decode("ascii"),
    }


def _payload(scene: Scene, rasters: list[dict]) -> dict:
    """The JSON blob the page reads. Everything the map needs, and nothing it must fetch."""
    return {
        "title": scene.title,
        "subtitle": scene.subtitle,
        "slug": scene.aoi_slug,
        "notes": scene.notes,
        "rasters": rasters,
        "vectors": [
            {
                "name": v.name, "legend": v.legend, "geometry": v.geometry,
                "stroke": v.stroke, "fill": v.fill, "width": v.width,
                "visible": v.visible, "geojson": v.geojson,
            }
            for v in scene.vectors
        ],
    }


def resolve_max_px(layer_count: int, requested: int, budget: int = WARN_ARTIFACT_BYTES) -> int:
    """Shrink the per-layer resolution so a many-layer scene stays a loadable size. Pure.

    A 1500 px RGBA PNG of a terrain surface runs to roughly 1.3 MB once base64-encoded, so
    nine layers at full size clear 11 MB. File size scales with pixel count, hence the
    square root: halving the budget per layer costs about 30% of the linear resolution.
    """
    if layer_count <= 0:
        return requested
    per_layer = budget / layer_count
    allowed = int((per_layer / 1.3e6) ** 0.5 * 1500)
    return max(400, min(requested, allowed))


def render_artifact(
    scene: Scene, dest: Path, *, max_px: int = 1500, budget_bytes: int = WARN_ARTIFACT_BYTES
) -> Path:
    """Render a scene to a single self-contained HTML file."""
    if scene.is_empty:
        raise ValueError(
            f"{scene.aoi_slug}: nothing to render. Derive terrain for this AOI first."
        )

    effective = resolve_max_px(len(scene.rasters), max_px, budget_bytes)
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        rasters = [_encode_raster(layer, work, effective) for layer in scene.rasters]

    payload = _payload(scene, [r for r in rasters if r])
    document = _HTML.replace("__TITLE__", html.escape(scene.title)) \
                    .replace("__LEAFLET_CSS__", _LEAFLET_CSS.read_text()) \
                    .replace("__LEAFLET_JS__", _LEAFLET_JS) \
                    .replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(document, encoding="utf-8")

    size = dest.stat().st_size
    if effective < max_px:
        print(
            f"note: {len(scene.rasters)} raster layers, so each was rendered at "
            f"{effective} px rather than {max_px} px to keep the file loadable "
            f"({size / 1e6:.1f} MB)."
        )
    if size > MAX_ARTIFACT_BYTES:
        dest.unlink()
        raise ValueError(
            f"{scene.aoi_slug}: artifact is {size / 1e6:.1f} MB, over the "
            f"{MAX_ARTIFACT_BYTES / 1e6:.0f} MB ceiling. It would not load, so it was not "
            f"kept. Re-run with a smaller --max-px, or with fewer raster layers."
        )
    return dest


_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ &mdash; midden</title>
<style>
__LEAFLET_CSS__
</style>
<style>
  :root {
    --bg: #0f1115; --panel: #171a21; --line: #2a2f3a;
    --text: #e6e8ec; --muted: #98a2b3; --accent: #fbbf24;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--bg); color: var(--text);
    font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    display: grid; grid-template-columns: minmax(260px, 320px) 1fr; height: 100vh;
  }
  aside { background: var(--panel); border-right: 1px solid var(--line);
          overflow-y: auto; padding: 18px 18px 28px; }
  h1 { font-size: 17px; margin: 0 0 2px; letter-spacing: -0.01em; }
  .sub { color: var(--muted); font-size: 12px; margin-bottom: 18px; }
  h2 { font-size: 11px; text-transform: uppercase; letter-spacing: .08em;
       color: var(--muted); margin: 20px 0 8px; font-weight: 600; }
  .layer { display: flex; gap: 9px; align-items: flex-start; padding: 7px 0;
           border-bottom: 1px solid var(--line); }
  .layer:last-child { border-bottom: 0; }
  .layer input { margin-top: 3px; accent-color: var(--accent); }
  .layer label { cursor: pointer; }
  .layer .nm { font-weight: 600; }
  .layer .lg { color: var(--muted); font-size: 12px; display: block; margin-top: 1px; }
  .layer .meta { color: #6b7280; font-size: 11px; font-variant-numeric: tabular-nums; }
  .swatch { width: 11px; height: 11px; border-radius: 2px; margin-top: 5px; flex: none; }
  .note { color: var(--muted); font-size: 12px; border-left: 2px solid var(--line);
          padding-left: 10px; margin: 10px 0; }
  #map { height: 100vh; background: #0b0d11; }
  .leaflet-container { background: #0b0d11; font: inherit; }
  .leaflet-control-attribution { background: rgba(23,26,33,.85); color: var(--muted); }
  .leaflet-control-attribution a { color: var(--muted); }
  .opacity { width: 100%; margin: 6px 0 2px; accent-color: var(--accent); }
  @media (max-width: 760px) { body { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
                              #map { height: 60vh; } aside { max-height: 40vh; } }
</style>
</head>
<body>
<aside>
  <h1 id="ttl"></h1>
  <div class="sub" id="sub"></div>
  <h2>Raster layers</h2>
  <div id="rasters"></div>
  <h2>Vector layers</h2>
  <div id="vectors"></div>
  <h2>Reading this</h2>
  <div id="notes"></div>
</aside>
<div id="map"></div>
<script src="__LEAFLET_JS__"></script>
<script>
const DATA = __PAYLOAD__;

document.getElementById('ttl').textContent = DATA.title;
document.getElementById('sub').textContent = DATA.subtitle;
document.getElementById('notes').innerHTML =
  DATA.notes.map(n => '<div class="note">' + n + '</div>').join('');

const map = L.map('map', { zoomControl: true, attributionControl: true });
L.control.attribution({ prefix: false }).addTo(map);
map.attributionControl.addAttribution(
  'midden &middot; USGS 3DEP, NHDPlus HR, USDA SSURGO &middot; EPSG:26916');

let bounds = null;
const overlays = [];

DATA.rasters.forEach(r => {
  const layer = L.imageOverlay('data:image/png;base64,' + r.data, r.bounds,
                               { opacity: 1, interactive: false });
  overlays.push({ spec: r, layer });
  bounds = bounds ? bounds.extend(L.latLngBounds(r.bounds)) : L.latLngBounds(r.bounds);
  if (r.visible) layer.addTo(map);
});

// Circle markers, not default icons: the inlined stylesheet's relative image URLs are
// dead inside the sandbox, so a default marker would render as an empty box.
const vectorLayers = DATA.vectors.map(v => {
  const layer = L.geoJSON(v.geojson, {
    style: () => ({ color: v.stroke, weight: v.width,
                    fillColor: v.fill || v.stroke,
                    fillOpacity: v.fill ? 0.15 : 0 }),
    pointToLayer: (f, latlng) => L.circleMarker(latlng, {
      radius: 4, color: v.stroke, fillColor: v.fill || v.stroke,
      fillOpacity: 0.9, weight: 1.2 }),
    onEachFeature: (f, l) => {
      const p = f.properties || {};
      const rows = Object.entries(p).filter(([, val]) => val !== null && val !== '');
      if (rows.length) l.bindPopup(rows.map(([k, val]) => '<b>' + k + '</b>: ' + val).join('<br>'));
    }
  });
  if (v.visible) layer.addTo(map);
  bounds = bounds ? bounds.extend(layer.getBounds()) : layer.getBounds();
  return { spec: v, layer };
});

if (bounds && bounds.isValid()) map.fitBounds(bounds, { padding: [16, 16] });
else map.setView([36.1, -87.1], 12);

function control(container, entry, isRaster) {
  const s = entry.spec;
  const row = document.createElement('div');
  row.className = 'layer';
  const id = 'l_' + Math.random().toString(36).slice(2);
  const meta = isRaster
    ? s.grid + ' grid &middot; ' + s.resolution_m + ' m &middot; range ' + s.range.join(' to ')
    : '';
  row.innerHTML =
    '<input type="checkbox" id="' + id + '"' + (s.visible ? ' checked' : '') + '>' +
    (isRaster ? '' : '<span class="swatch" style="background:' + s.stroke + '"></span>') +
    '<label for="' + id + '"><span class="nm">' + s.name + '</span>' +
    (s.legend ? '<span class="lg">' + s.legend + '</span>' : '') +
    (meta ? '<span class="meta">' + meta + '</span>' : '') + '</label>';
  const box = row.querySelector('input');
  box.addEventListener('change', () => {
    if (box.checked) entry.layer.addTo(map); else map.removeLayer(entry.layer);
  });
  if (isRaster) {
    const slider = document.createElement('input');
    slider.type = 'range'; slider.min = 0; slider.max = 100; slider.value = 100;
    slider.className = 'opacity';
    slider.addEventListener('input', () => entry.layer.setOpacity(slider.value / 100));
    row.querySelector('label').appendChild(slider);
  }
  container.appendChild(row);
}

overlays.forEach(e => control(document.getElementById('rasters'), e, true));
vectorLayers.forEach(e => control(document.getElementById('vectors'), e, false));
</script>
</body>
</html>
"""
