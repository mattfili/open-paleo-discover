"""F2: an effort-constrained survey plan over ranked candidate zones.

Expected discoveries in a zone decompose as (survey-design skill; Banning 2002):

    P(zone contains a target) x P(method intersects it) x P(crew recognises it)

The score surface only speaks to the first term, and only as a relative rank —
so the plan works in relative expected-value units and SAYS so, rather than
manufacturing probabilities. The second and third terms come from the class:

- **direct** classes (mound, hearth): LiDAR was the survey instrument; fieldwork is
  a verification visit per zone. Minutes per candidate, high recognition.
- **proxy** classes (open_habitation, midden): discovery runs through shovel-test
  grids, where intersection and recovery both cut hard (Krakker et al. 1983;
  Nance & Ball 1986), and burial risk cuts recognition again — a buried surface
  is auger work, not a walkover.

Two sampling-theory constraints are structural, not optional:

- **The control sample.** A fixed fraction of the budget goes to low-score ground
  matched on landform, drawn the way B1 draws its nulls. A plan that only visits
  top-ranked zones can never learn the model is wrong — that is survey bias
  manufacturing its own validation (Orton 2000). The line item ships labeled.
- **Access bias at plan time** is reported, not corrected: the plan points its
  zones at the surface's measured B4 ratio (top-5% vs background road distance,
  recorded on every score run) and asks that access-skips be logged as such.
"""

from __future__ import annotations

from typing import Any

import psycopg

from midden.db import fetch_all
from midden.registry import TargetClass

__all__ = ["PARAMS", "build_plan"]

#: Named effort-model parameters, recorded in every plan derivation. Judgment calls
#: become parameters, not decisions.
PARAMS: dict[str, float] = {
    "field_hours_per_person_day": 6.0,
    "verify_hours_per_zone": 0.75,  # direct classes: walk + assess one candidate
    "shovel_test_spacing_m": 15.0,  # proxy classes: grid interval
    "minutes_per_shovel_test": 20.0,  # dig, screen, record
    "zone_overhead_hours": 0.5,  # access, setup, notes per zone
    "control_budget_fraction": 0.15,  # the falsification line item
    "burial_visibility_floor": 0.25,  # recognition multiplier at burial_risk = 1
}


def _zone_effort_hours(zone: dict, cls: TargetClass) -> float:
    """Hours to survey one zone with the class-appropriate method. Pure."""
    if cls.detectability == "direct":
        return PARAMS["verify_hours_per_zone"] + PARAMS["zone_overhead_hours"]
    spacing = PARAMS["shovel_test_spacing_m"]
    n_tests = max(1, round(zone["area_m2"] / (spacing * spacing)))
    return (
        n_tests * PARAMS["minutes_per_shovel_test"] / 60.0
        + PARAMS["zone_overhead_hours"]
    )


def _zone_ev(zone: dict, cls: TargetClass) -> float:
    """Relative expected-value of a zone. Pure, and openly relative.

    Rank weight: how far above the top-percentile floor the zone's mean cell sits.
    Recognition: burial risk linearly degrades surface visibility toward a floor —
    at burial_risk 1.0 only subsurface method fragments remain (McManamon 1984's
    obtrusiveness/visibility framing).
    """
    rank_weight = max(zone["pct_mean"] - 95.0, 0.1)
    burial = zone["burial_risk"] or 0.0
    recognition = 1.0 - burial * (1.0 - PARAMS["burial_visibility_floor"])
    return rank_weight * recognition


def build_plan(
    conn: psycopg.Connection, aoi, cls: TargetClass, *, person_days: float
) -> dict[str, Any]:
    """Greedy EV-per-hour ordering under a person-day budget, control sample carved out.

    Greedy on EV/cost is the honest v1 of the knapsack; diminishing returns inside a
    zone (Thompson 1990's adaptive logic) is future work and recorded as such.
    """
    zones = fetch_all(
        conn,
        """SELECT zone_id, rank, area_m2, pct_mean, hand_mean_m, burial_risk
           FROM derived.candidate_zone
           WHERE aoi_id = %s AND class_id = %s ORDER BY rank""",
        (aoi.id, cls.class_id),
    )
    if not zones:
        raise ValueError(
            f"No candidate zones for {cls.class_id!r} in {aoi.slug!r}. "
            f"Run `midden score polygons --aoi {aoi.slug} --class {cls.class_id}` first."
        )

    total_hours = person_days * PARAMS["field_hours_per_person_day"]
    control_hours = total_hours * PARAMS["control_budget_fraction"]
    budget = total_hours - control_hours

    priced = []
    for z in zones:
        effort = _zone_effort_hours(z, cls)
        ev = _zone_ev(z, cls)
        priced.append(
            {
                **z,
                "effort_hours": round(effort, 2),
                "ev_relative": round(ev, 2),
                "ev_per_hour": round(ev / effort, 2),
            }
        )
    priced.sort(key=lambda z: -z["ev_per_hour"])

    itinerary, spent = [], 0.0
    for z in priced:
        if spent + z["effort_hours"] > budget:
            continue
        spent += z["effort_hours"]
        itinerary.append({**z, "cumulative_hours": round(spent, 1)})

    return {
        "class_id": cls.class_id,
        "detectability": cls.detectability,
        "method": (
            "verification visits of LiDAR candidates"
            if cls.detectability == "direct"
            else f"shovel-test grid at {PARAMS['shovel_test_spacing_m']:g} m"
        ),
        "person_days": person_days,
        "field_hours": total_hours,
        "itinerary": itinerary,
        "skipped": [
            z["rank"] for z in priced if z["rank"] not in {i["rank"] for i in itinerary}
        ],
        "control_sample": {
            "hours": round(control_hours, 1),
            "instruction": (
                "Spend these hours on low-score cells matched on landform (drawn as "
                "B1 draws nulls: same lowland fraction, inside the frame). This is "
                "the only part of the plan that can falsify the model rather than "
                "confirm it; log its outcomes with the same care as the candidates."
            ),
        },
        "access_bias": (
            "The zones inherit the surface's measured access bias — see the B4 line "
            "on this class's latest `score run` (top-5% vs background road-distance "
            "ratio, recorded in its derivation). Routing convenience adds bias on "
            "top; log any zone skipped for access as skipped-for-access."
        ),
        "params": dict(PARAMS),
    }
