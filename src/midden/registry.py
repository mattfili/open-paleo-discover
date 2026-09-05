"""Target-class registry access (ROADMAP "Scope" and D).

`ref.target_class` is the single source of truth for what each class is, how detectable
it is, and which parameters its detection chain runs with. Detection parameters are per
class, never global: `terrain/params.py` remains the *schema* of known parameter names
(unit, why, grid), but the **values** for detection derivations come from the registry
row and nowhere else. A class whose registry params omit a known detection parameter is
a registry bug and raises, because silently falling back to a global default is exactly
the failure the invariant forbids.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg

from midden.db import fetch_all
from midden.terrain.params import defaults_for

__all__ = [
    "TargetClass",
    "detect_params",
    "get_class",
    "list_classes",
    "resolve_class_params",
]

#: derivation name -> key of the parameter block inside target_class.params.
_DERIVATION_BLOCKS = {
    "terrain.openness": "openness",
    "terrain.slrm": "slrm",
}


@dataclass(frozen=True, slots=True)
class TargetClass:
    """One row of ref.target_class."""

    class_id: str
    period: str
    morphology: str
    grid: str
    detectability: str
    burial_sensitivity: bool
    label_source: str
    params: dict[str, Any]
    notes: str | None


def _row_to_class(row: dict[str, Any]) -> TargetClass:
    """Build a TargetClass from a ref.target_class row. Pure."""
    return TargetClass(
        class_id=row["class_id"],
        period=row["period"],
        morphology=row["morphology"],
        grid=row["grid"],
        detectability=row["detectability"],
        burial_sensitivity=row["burial_sensitivity"],
        label_source=row["label_source"],
        params=row["params"] or {},
        notes=row["notes"],
    )


def list_classes(conn: psycopg.Connection) -> list[TargetClass]:
    """Return every registered target class, precontact first, then alphabetical."""
    rows = fetch_all(
        conn,
        "SELECT class_id, period, morphology, grid, detectability, burial_sensitivity,"
        "       label_source, params, notes"
        "  FROM ref.target_class ORDER BY period, class_id",
    )
    return [_row_to_class(row) for row in rows]


def get_class(conn: psycopg.Connection, class_id: str) -> TargetClass:
    """Return one target class, or raise naming the valid ids.

    The error lists the registry contents because the caller is usually a CLI user who
    typed a class name; "no such class" without the list is a dead end.
    """
    rows = fetch_all(
        conn,
        "SELECT class_id, period, morphology, grid, detectability, burial_sensitivity,"
        "       label_source, params, notes"
        "  FROM ref.target_class WHERE class_id = %s",
        (class_id,),
    )
    if not rows:
        known = [
            r["class_id"]
            for r in fetch_all(
                conn, "SELECT class_id FROM ref.target_class ORDER BY class_id"
            )
        ]
        raise KeyError(
            f"No target class {class_id!r} in ref.target_class. Known: {known}. "
            "Run `midden db init` if the registry is empty."
        )
    return _row_to_class(rows[0])


def resolve_class_params(
    cls: TargetClass, derivation: str, overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Resolve one detection derivation's parameters from a class's registry row. Pure.

    The known parameter names for the derivation come from terrain.params.PARAMETERS;
    every one of them must be present in the class's params block. Overrides merge on
    top (a sweep), and unknown names are rejected for the same reason `resolve` rejects
    them: a typo would otherwise run the whole sweep at the registry value and look
    like a null result.
    """
    block_key = _DERIVATION_BLOCKS.get(derivation)
    if block_key is None:
        raise KeyError(
            f"{derivation!r} is not a per-class detection derivation. "
            f"Per-class: {sorted(_DERIVATION_BLOCKS)}. Model-grid derivations keep "
            "their global defaults via terrain.params.resolve."
        )

    known = set(defaults_for(derivation))
    block = cls.params.get(block_key, {})
    missing = known - set(block)
    if missing:
        raise KeyError(
            f"Class {cls.class_id!r} params block {block_key!r} is missing "
            f"{sorted(missing)}. Detection parameters are per class, never global: "
            "fix the registry row rather than falling back to a default."
        )

    overrides = overrides or {}
    unknown = (set(block) | set(overrides)) - known
    if unknown:
        raise KeyError(
            f"{cls.class_id}/{derivation}: unknown parameter(s) {sorted(unknown)}. "
            f"Known: {sorted(known)}"
        )
    return {**{name: block[name] for name in known}, **overrides}


def detect_params(cls: TargetClass) -> dict[str, Any]:
    """Return a class's firing-rule block (surfaces, threshold_pctile, min_cells).

    Raises for classes with no detect block — a model-grid proxy class cannot fire,
    and asking it to is a caller bug, not an empty result.
    """
    detect = cls.params.get("detect")
    if not detect:
        raise KeyError(
            f"Class {cls.class_id!r} has no detect block (detectability="
            f"{cls.detectability}, grid={cls.grid}). Only detection-grid classes with "
            "a firing rule can be validated against point labels."
        )
    required = {"surfaces", "threshold_pctile", "min_cells"}
    missing = required - set(detect)
    if missing:
        raise KeyError(
            f"Class {cls.class_id!r} detect block is missing {sorted(missing)}."
        )
    return detect
