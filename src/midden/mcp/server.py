"""FastMCP server exposing the midden tool surface over stdio (spec.md §9).

Scope, and one deliberate omission
----------------------------------
spec.md §9 lists `midden_sql`, "a read-only SQL escape hatch against a read-only role".
It is not built here. CLAUDE.md says to try the `mcp-postgis` server first because it may
already cover it, and it does: `execute_sql` under `MCP_POSTGIS_MODE=read_only`, alongside
`explain`, `features_in_bbox`, `nearest_features`, `within_distance` and `create_layer`
(which publishes a result as a view QGIS picks up automatically). Building a second,
overlapping SQL tool would make tool selection unreliable for exactly the reason CLAUDE.md
gives — "three plausible answers to 'query the database'".

`midden_query` *is* built, because it is not a second way to write SQL. BSL exposes a
curated vocabulary of named dimensions and measures with descriptions attached, which is
the whole reason the semantic layer exists.

Every tool carries `readOnlyHint` honestly: reads are marked, and anything that fetches,
computes, or writes is not.
"""

from __future__ import annotations

from fastmcp import FastMCP

from midden import __version__

INSTRUCTIONS = """\
midden models where prehistoric people are likely to have camped in Middle Tennessee,
from LiDAR-derived landform and soils.

Read this before using the tools:

1. Two grids, two jobs, and they are never mixed. Detection renders are 0.5 m and exist
   to be *looked at*. Predictive modelling is 10 m. A model fitted at 0.5 m is noise; a
   feature hunted at 10 m is invisible.

2. Openness sign convention. Positive openness is HIGH (>90 deg) on CONVEX features -
   mounds, charcoal hearths, ridges. Negative openness is HIGH on CONCAVE features - pits,
   ditches, relict channels, the tunnel cut at the Narrows. A flat plane is 90 deg in both,
   whatever its slope. Getting this backwards silently inverts every interpretation.
   Negative openness is not the inverse of positive: render and read both.

3. Most sites are not visible in LiDAR. The primary product is a landform-and-soils
   suitability surface, not a feature detector. A low score means either the landform is
   wrong or anything there is under metres of overbank silt - burial_risk is reported as a
   companion band precisely so those two are never collapsed into one number.

4. Tune against controls, never against a prospect. control_detection AOIs validate the
   render chain; control_positive AOIs falsify a weight set.

5. One anomaly is not a finding. Look for spatial pattern, and report uncertainty as a
   category - likely cultural, ambiguous, likely natural, likely modern - not as a hedge.

For raw SQL and spatial predicates against the database, prefer the mcp-postgis server's
tools. midden_query is for the curated semantic vocabulary, not for arbitrary SQL.
"""

mcp: FastMCP = FastMCP(
    name="midden",
    instructions=INSTRUCTIONS,
    version=__version__,
)


def _register_all() -> None:
    """Attach every tool module to the server."""
    from midden.mcp.tools import compute, interpret, semantic, spatial, visual

    for module in (semantic, spatial, compute, visual, interpret):
        module.register(mcp)


_register_all()


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
