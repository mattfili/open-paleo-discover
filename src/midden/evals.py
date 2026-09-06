"""G1: run the MCP evals (`plugin/mcp/evals.xml`) against the live surface.

The evals were written with hand-checked answers and had never been executed — which,
for an interpretive layer, is the only thing standing between the tools and
confidently teaching the wrong sign convention (ROADMAP G1).

Two kinds of check, both mechanical:

- **Fact evals (1-6)** call the same tool functions the MCP server registers and
  assert the answer's load-bearing facts against the live database. A mismatch is
  reported with the live truth so the XML can be corrected — a drifted eval is a
  finding, not a silent skip.
- **Convention evals (7-12)** assert the convention where it is *encoded*: render
  legends for the openness sign, the weight set for burial-risk-never-summed, the
  registry for per-class detectability, `terrain.params` for the two-grids rule.
  They cannot test whether a model *narrates* the convention correctly — that is the
  LLM-driving half, which `claude plugin eval` covers and this runner deliberately
  does not fake.

Each checker returns (ok, live_note). The command exits non-zero on any failure so it
can gate in CI once the database is seedable there.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

import psycopg

from midden.db import fetch_all

__all__ = ["run_evals"]

Checker = Callable[[psycopg.Connection], tuple[bool, str]]


def _aois(conn, role=None):
    where = "WHERE role = %s" if role else ""
    return fetch_all(
        conn,
        f"SELECT slug, role, area_km2 FROM derived.aoi {where} ORDER BY slug",
        (role,) if role else (),
    )


def _check_1(conn):
    slugs = {r["slug"] for r in _aois(conn, "control_positive")}
    expected = {"castalian-springs", "mound-bottom", "fewkes-group", "old-stone-fort"}
    return slugs == expected, f"live control_positive: {sorted(slugs)}"


def _check_2(conn):
    rows = sorted(_aois(conn), key=lambda r: -r["area_km2"])
    top = rows[0]
    ok = top["slug"] == "cedars-of-lebanon" and abs(top["area_km2"] - 12.44) < 0.2
    return ok, f"largest: {top['slug']} at {top['area_km2']:.2f} km2"


def _check_3(conn):
    rows = _aois(conn, "shakeout")
    ok = [r["slug"] for r in rows] == ["harpeth-highway-70"]
    return ok, f"shakeout: {[r['slug'] for r in rows]}"


def _check_4(conn):
    rows = fetch_all(
        conn,
        "SELECT gnis_name, max(stream_order) AS o FROM ref.nhd_flowline "
        "WHERE gnis_name IS NOT NULL GROUP BY gnis_name ORDER BY o DESC LIMIT 4",
    )
    top_order = rows[0]["o"]
    carriers = {r["gnis_name"].strip() for r in rows if r["o"] == top_order}
    # The Duck River joined at order 6 when the old-stone-fort frame's flowlines
    # arrived (A3) — intake is AOI-scoped, so this answer grows with coverage.
    ok = top_order == 6 and "Harpeth River" in carriers
    return ok, f"max named order {top_order}, carried by {sorted(carriers)}"


def _check_5(conn):
    from midden.mcp.tools.semantic import midden_get_model_schema

    schema = midden_get_model_schema("derivation")
    dims = set(schema.get("dimensions") or {})
    return "status" in dims, f"derivation dimensions: {sorted(dims)[:6]}"


def _check_6(conn):
    # The claim under test is structural: rasters are computed on a buffered extent,
    # so the catalogued HAND raster covers more ground than the AOI polygon.
    rows = fetch_all(
        conn,
        """SELECT ST_Area(ra.footprint) / ST_Area(a.geom) AS ratio
           FROM derived.raster_asset ra JOIN derived.aoi a ON a.id = ra.aoi_id
           WHERE a.slug = 'mound-bottom' AND ra.kind = 'hand' AND ra.grid = 'model'""",
    )
    ok = bool(rows) and rows[0]["ratio"] > 1.5
    note = (
        f"hand footprint / AOI area = {rows[0]['ratio']:.1f}x"
        if rows
        else "no hand raster"
    )
    return ok, note


def _check_7(conn):
    from midden.render.core import RASTER_STYLES

    pos = RASTER_STYLES["openness_pos"]["legend"].lower()
    neg = RASTER_STYLES["openness_neg"]["legend"].lower()
    ok = "convex" in pos and "concave" in neg and "mound" in pos and "pit" in neg
    return ok, f"legends: pos={pos!r} neg={neg!r}"


def _check_8(conn):
    from midden.config import settings
    from midden.features.score import load_weights

    ws = load_weights(settings().weights_dir / "open_habitation.yml")
    ok = "burial_risk" in ws.companion_bands and "burial_risk" not in ws.features
    return ok, "burial_risk is a companion band and not a scored feature"


def _check_9(conn):
    from midden.mcp import server as _server_mod  # registration module

    names = {n for n in dir(_server_mod) if n.startswith("midden_")}
    import midden.mcp.tools.compute as c
    import midden.mcp.tools.semantic as s
    import midden.mcp.tools.spatial as sp
    import midden.mcp.tools.visual as v

    all_tools = {
        n for m in (c, s, sp, v) for n in dir(m) if n.startswith("midden_")
    } | names
    ok = "midden_sql" not in all_tools
    return ok, "no midden_sql tool exists; SQL belongs to mcp-postgis"


def _check_10(conn):
    rows = _aois(conn, "control_detection")
    slugs = {r["slug"] for r in rows}
    return (
        "montgomery-bell" in slugs,
        f"control_detection includes montgomery-bell: {sorted(slugs)[:4]}...",
    )


def _check_11(conn):
    from midden.terrain.params import DETECTION_RES_M, MODEL_RES_M

    grids = {
        r["grid"]
        for r in fetch_all(conn, "SELECT DISTINCT grid FROM derived.raster_asset")
    }
    ok = (
        DETECTION_RES_M == 0.5
        and MODEL_RES_M == 10.0
        and grids <= {"detection", "model"}
    )
    return ok, f"grids in catalog: {sorted(grids)}; res {DETECTION_RES_M}/{MODEL_RES_M}"


def _check_12(conn):
    rows = fetch_all(conn, "SELECT class_id, detectability FROM ref.target_class")
    d = {r["class_id"]: r["detectability"] for r in rows}
    ok = (
        d.get("saltpeter_works") == "proxy"
        and d.get("midden") == "proxy"
        and d.get("charcoal_hearth") == "direct"
        and set(d.values()) <= {"direct", "proxy", "invisible"}
    )
    return (
        ok,
        f"detectability: saltpeter={d.get('saltpeter_works')}, midden={d.get('midden')}",
    )


CHECKERS: dict[str, Checker] = {
    "1": _check_1,
    "2": _check_2,
    "3": _check_3,
    "4": _check_4,
    "5": _check_5,
    "6": _check_6,
    "7": _check_7,
    "8": _check_8,
    "9": _check_9,
    "10": _check_10,
    "11": _check_11,
    "12": _check_12,
}


def run_evals(conn: psycopg.Connection, evals_path: Path) -> list[dict[str, Any]]:
    """Run every eval with a checker; report unchecked qa_pairs rather than skip them."""
    tree = ET.parse(evals_path)
    results = []
    seen = set()
    for qa in tree.getroot().iter("qa_pair"):
        qa_id = qa.get("id")
        seen.add(qa_id)
        question = (qa.findtext("question") or "").strip()
        checker = CHECKERS.get(qa_id)
        if checker is None:
            results.append(
                {
                    "id": qa_id,
                    "ok": None,
                    "question": question,
                    "note": "no mechanical checker — needs the LLM-driving harness",
                }
            )
            continue
        try:
            ok, note = checker(conn)
        except Exception as exc:  # noqa: BLE001 - an eval that errors is a failure with a reason
            ok, note = False, f"checker raised: {exc}"
        results.append({"id": qa_id, "ok": ok, "question": question, "note": note})
    for extra in sorted(set(CHECKERS) - seen, key=int):
        # Checkers for conventions the XML does not carry yet (two-grids, detectability):
        # run them anyway and report that the XML should grow the case.
        try:
            ok, note = CHECKERS[extra](conn)
        except Exception as exc:  # noqa: BLE001
            ok, note = False, f"checker raised: {exc}"
        results.append(
            {
                "id": extra,
                "ok": ok,
                "question": "(convention case not yet in evals.xml)",
                "note": note,
            }
        )
    return results
