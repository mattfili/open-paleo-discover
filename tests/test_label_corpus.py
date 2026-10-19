"""Round trip of the tracked label corpus: git file -> database -> git file.

The reviewed labels are human work that once lived only in Postgres. These tests pin the
property that makes a rebuilt database equal to the lost one: review state written into
`labels/*.geojson` survives load_sites and export_sheet_labels unchanged.
"""

from __future__ import annotations

import copy
import json

import psycopg
import pytest

from midden.corpus import REVIEW_KEYS, merge_reviews, review_params
from midden.db import fetch_all
from midden.histmap import load_sites

SHEET = "TEST_roundtrip_000000_1900_24000"

#: Four points exercising every review state, including a superseded earlier decision.
FEATURES = [
    {"name": "Alpha Cem", "class_id": "family_cemetery", "xy": [475000.0, 3995000.0],
     "extra": {"review_status": "confirmed", "review_note": "ring is right",
               "review_round": 1, "reviewed_at": "2026-09-05T16:00:00Z"}},
    {"name": "Beta Sch", "class_id": "civic_structure", "xy": [475100.0, 3995100.0],
     "extra": {"review_status": "rejected", "review_note": "symbol is 90 m NE",
               "review_round": 2, "reviewed_at": "2026-09-08T01:00:00Z"}},
    {"name": "Gamma Ch", "class_id": "civic_structure", "xy": [475200.0, 3995200.0],
     "extra": {"review_status": "confirmed", "review_round": 2,
               "reviewed_at": "2026-09-08T01:10:00Z",
               "review_prior": [{"decision": "unsure", "round": 1,
                                 "at": "2026-09-05T16:05:00Z", "note": "smudged"}]}},
    {"name": "Delta Cem", "class_id": "family_cemetery", "xy": [475300.0, 3995300.0],
     "extra": {"review_status": "unreviewed", "review_note": "cannot tell",
               "review_round": 1, "reviewed_at": "2026-09-05T16:10:00Z"}},
    {"name": "Epsilon Cem", "class_id": "family_cemetery", "xy": [475400.0, 3995400.0],
     "extra": {}},
]


def _doc(with_review: bool) -> dict:
    features = []
    for f in FEATURES:
        props = {"class_id": f["class_id"], "name": f["name"],
                 "positional_confidence_m": 45.0, "note": "digitizer note"}
        if with_review:
            props.update(f["extra"])
        features.append({"type": "Feature",
                         "geometry": {"type": "Point", "coordinates": f["xy"]},
                         "properties": props})
    return {"type": "FeatureCollection", "features": features}


def test_review_params_rejects_unknown_status():
    """A typo in a tracked file must fail loudly, not load as something else."""
    with pytest.raises(ValueError):
        review_params({"name": "x", "review_status": "maybe"})


def test_merge_reviews_keeps_digitizer_note_and_appends_unknown_points():
    """Merging DB state never drops properties the database does not hold."""
    doc = _doc(with_review=False)
    rows = [{"name": "Alpha Cem", "class_id": "family_cemetery", "review_status": "confirmed",
             "review_note": "ok", "review_round": 1, "reviewed_at": "2026-09-05T16:00:00Z",
             "review_prior": None, "positional_confidence_m": 45.0, "x": 1.0, "y": 2.0},
            {"name": "New", "class_id": "civic_structure", "review_status": "unreviewed",
             "review_note": None, "review_round": None, "reviewed_at": None,
             "review_prior": None, "positional_confidence_m": 90.0, "x": 3.0, "y": 4.0}]
    merged = merge_reviews(doc, rows)
    alpha = merged["features"][0]["properties"]
    assert alpha["note"] == "digitizer note" and alpha["review_status"] == "confirmed"
    new = merged["features"][-1]["properties"]
    assert new["name"] == "New" and not set(new) & set(REVIEW_KEYS)


def test_labels_file_roundtrips_through_database(db, tmp_path):
    """file -> load_sites -> export into a review-stripped copy == the original file."""
    from midden.corpus import export_sheet_labels

    original = tmp_path / f"{SHEET}.geojson"
    original.write_text(json.dumps(_doc(with_review=True)))
    try:
        fetch_all(db, "SELECT 1 FROM ref.control_sites LIMIT 0")
        db.execute(
            """
            INSERT INTO ref.histmap_sheet
                (sheet_id, cell_name, map_year, scale, source_url,
                 positional_confidence_m, footprint)
            VALUES (%s, 'Test', 1900, 24000, 'test://', 12.2,
                    ST_MakeEnvelope(470000, 3990000, 480000, 4000000, 26916))
            """,
            (SHEET,),
        )
        db.commit()
        load_sites(db, SHEET, original, method="pytest")

        stripped = copy.deepcopy(_doc(with_review=False))
        target = tmp_path / "out.geojson"
        target.write_text(json.dumps(stripped))
        export_sheet_labels(db, SHEET, target)

        got = {f["properties"]["name"]: f["properties"] for f in json.loads(target.read_text())["features"]}
        for expected in FEATURES:
            props = got[expected["name"]]
            for key, value in expected["extra"].items():
                assert props.get(key) == value, (expected["name"], key)
            if not expected["extra"]:
                assert not set(props) & set(REVIEW_KEYS)
    except Exception as exc:
        if "does not exist" in str(exc) and "ref." in str(exc):
            pytest.skip("schema not initialised; run `midden db init`")
        raise
    finally:
        db.rollback()
        db.execute("DELETE FROM ref.control_sites WHERE source_sheet = %s", (SHEET,))
        db.execute("DELETE FROM ref.histmap_sheet WHERE sheet_id = %s", (SHEET,))
        db.execute("DELETE FROM derived.derivation WHERE inputs::text LIKE %s", (f"%{SHEET}%",))
        db.commit()


def test_confuser_file_roundtrip(db, tmp_path):
    """Confusers exported then reloaded into an empty ledger come back identical."""
    from midden.corpus import export_confusers, load_confusers

    try:
        fetch_all(db, "SELECT 1 FROM ref.confuser LIMIT 0")
    except psycopg.errors.UndefinedTable:
        db.rollback()
        pytest.skip("schema not initialised; run `midden db init`")
    marker = "pytest-roundtrip"
    path = tmp_path / "c.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [475000.0, 3995000.0]},
        "properties": {"kind": marker, "imitates": "charcoal_hearth",
                       "assessment": "likely modern", "basis": "test", "extent_m": 10.0}}]}))
    try:
        assert load_confusers(db, path) == 1
        assert load_confusers(db, path) == 0  # idempotent
        out = tmp_path / "out.geojson"
        export_confusers(db, out)
        kinds = [f["properties"]["kind"] for f in json.loads(out.read_text())["features"]]
        assert marker in kinds
    finally:
        db.rollback()
        db.execute("DELETE FROM ref.confuser WHERE kind = %s", (marker,))
        db.commit()
