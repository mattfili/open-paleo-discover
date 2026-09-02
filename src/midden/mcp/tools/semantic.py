"""Semantic-layer MCP tools: what models exist, what they hold, and querying them."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from midden.config import settings
from midden.semantic.build import build_layer

READ_ONLY = {"readOnlyHint": True}


def _describe(model: Any) -> dict[str, Any]:
    """Summarise one semantic model's dimensions and measures with their descriptions."""

    def fields(collection) -> dict[str, str]:
        return {
            name: (getattr(collection[name], "description", None) or "")
            for name in collection
        }

    return {
        "description": getattr(model, "description", None) or "",
        "dimensions": fields(model.dimensions),
        "measures": fields(model.measures),
    }


def midden_list_semantic_models() -> dict[str, Any]:
    """List the semantic models available, with their dimensions and measures.

    Start here. Every other semantic tool needs a model name from this list.
    """
    layer = build_layer(settings())
    return {
        "models": {name: _describe(m) for name, m in sorted(layer.models.items())},
        "unavailable_sources": layer.missing_tables,
    }


def midden_get_model_schema(
    model: Annotated[str, Field(description="Model name from midden_list_semantic_models.")],
) -> dict[str, Any]:
    """Return one model's dimensions and measures, each with its description.

    Call this before midden_query. Field names must match exactly; they are not
    column names and cannot be guessed from the underlying tables.
    """
    layer = build_layer(settings())
    return {"model": model} | _describe(layer.model(model))


def _check_fields(model, target, dimensions, measures) -> None:
    """Reject unknown field names before building a query.

    Field names are curated, not column names, so a typo would otherwise surface as an
    opaque Ibis error rather than as the one instruction that fixes it.
    """
    known = set(target.dimensions) | set(target.measures)
    unknown = (set(dimensions or []) | set(measures or [])) - known
    if unknown:
        raise ValueError(
            f"{model}: unknown field(s) {sorted(unknown)}. "
            f"Call midden_get_model_schema({model!r}) for the exact names."
        )


def midden_query(  # cq-allow: 53 lines, of which 32 are logic; the remainder is the
    # Annotated signature and docstring, which are the tool's interface contract - they
    # are what an LLM reads to call it correctly, and shortening them makes it worse.
    model: Annotated[str, Field(description="Model name.")],
    dimensions: Annotated[
        list[str] | None, Field(description="Dimension names to group by.")
    ] = None,
    measures: Annotated[
        list[str] | None, Field(description="Measure names to aggregate.")
    ] = None,
    filters: Annotated[
        list[str] | None,
        Field(description="Predicates as 'field OP value', e.g. 'stream_order>=3'."),
    ] = None,
    order_by: Annotated[str | None, Field(description="Field to sort by.")] = None,
    descending: Annotated[bool, Field(description="Sort descending.")] = False,
    limit: Annotated[int, Field(description="Maximum rows returned.", ge=1, le=5000)] = 100,
) -> dict[str, Any]:
    """Query a semantic model by named dimensions and measures.

    This is the curated vocabulary, not SQL. For arbitrary SQL against the database,
    use the mcp-postgis server's execute_sql instead.
    """
    from ibis import _ as deferred

    from midden.commands.semantic import parse_filter

    layer = build_layer(settings())
    target = layer.model(model)

    known = set(target.dimensions) | set(target.measures)
    requested = set(dimensions or []) | set(measures or [])
    unknown = requested - known
    if unknown:
        raise ValueError(
            f"{model}: unknown field(s) {sorted(unknown)}. "
            f"Call midden_get_model_schema({model!r}) for the exact names."
        )

    query = target
    for clause in filters or []:
        query = query.filter(parse_filter(clause))
    if dimensions:
        query = query.group_by(*dimensions)
    query = query.aggregate(*(measures or list(target.measures)[:1]))
    if order_by:
        column = getattr(deferred, order_by)
        query = query.order_by(column.desc() if descending else column)

    frame = query.limit(limit).execute()
    return {
        "model": model,
        "row_count": len(frame),
        "rows": frame.to_dict(orient="records"),
    }


#: Tools that only read. Marked readOnlyHint so a client can reason about
#: which calls are safe to retry or run speculatively.
READ_TOOLS = (midden_list_semantic_models, midden_get_model_schema, midden_query)

#: Tools that fetch from a network service, write rasters, or insert rows.
WRITE_TOOLS = ()


def register(mcp) -> None:
    """Attach this module's tools to a FastMCP server."""
    for tool in READ_TOOLS:
        mcp.tool(tool, annotations=READ_ONLY)
    for tool in WRITE_TOOLS:
        mcp.tool(tool)
