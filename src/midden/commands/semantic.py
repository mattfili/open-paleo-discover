"""`midden semantic` — inspect and query the semantic layer."""

from __future__ import annotations

import operator
import re
from typing import Annotated, Any

import typer
from ibis import _ as deferred

from midden.config import settings
from midden.semantic.build import build_layer

semantic_app = typer.Typer(
    help="Boring-semantic-layer models over ref.* and derived.*.", no_args_is_help=True
)

#: Longest first, so `>=` is matched before `>`.
_OPERATORS = {
    ">=": operator.ge, "<=": operator.le, "!=": operator.ne,
    "=": operator.eq, ">": operator.gt, "<": operator.lt,
}
_FILTER_RE = re.compile(rf"^\s*(?P<field>[A-Za-z_][\w.]*)\s*(?P<op>{'|'.join(map(re.escape, _OPERATORS))})\s*(?P<value>.+?)\s*$")


def parse_filter(text: str):
    """Parse `field=value`, `field>=3` and friends into an Ibis predicate. Pure.

    Values that look numeric are compared as numbers; everything else as a string. That
    keeps `stream_order>=4` working without making the caller quote types.
    """
    match = _FILTER_RE.match(text)
    if not match:
        raise ValueError(
            f"Cannot parse filter {text!r}. Expected field OP value, "
            f"where OP is one of {', '.join(_OPERATORS)}."
        )
    field, symbol, raw = match["field"], match["op"], match["value"].strip("'\"")
    value: Any = raw
    for cast in (int, float):
        try:
            value = cast(raw)
            break
        except ValueError:
            continue
    return _OPERATORS[symbol](getattr(deferred, field), value)


def _split(value: str | None) -> list[str]:
    """Split a comma-separated option into a clean list. Pure."""
    return [part.strip() for part in (value or "").split(",") if part.strip()]


@semantic_app.command("list")
def semantic_list() -> None:
    """List the semantic models and their dimensions and measures."""
    layer = build_layer(settings())
    for name in sorted(layer.models):
        model = layer.models[name]
        typer.secho(f"\n{name}", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"  dimensions: {', '.join(model.dimensions)}")
        typer.echo(f"  measures  : {', '.join(model.measures)}")
    if layer.missing_tables:
        typer.secho("\nsource tables that could not be attached:", fg=typer.colors.YELLOW)
        for alias, reason in layer.missing_tables.items():
            typer.echo(f"  {alias}: {reason}")


@semantic_app.command("schema")
def semantic_schema(model: str) -> None:
    """Show one model's dimensions, measures, and descriptions."""
    layer = build_layer(settings())
    target = layer.model(model)
    typer.secho(model, fg=typer.colors.GREEN, bold=True)
    if getattr(target, "description", None):
        typer.echo(f"  {target.description}\n")
    for label, fields in (("dimensions", target.dimensions), ("measures", target.measures)):
        typer.secho(f"  {label}", bold=True)
        for field_name in fields:
            field = fields[field_name]
            description = getattr(field, "description", None) or ""
            typer.echo(f"    {field_name:<20} {description}")


@semantic_app.command("query")
def semantic_query(
    model: Annotated[str, typer.Argument(help="Model name.")],
    dimensions: Annotated[str | None, typer.Option("--dimensions", "-d", help="Comma-separated.")] = None,
    measures: Annotated[str | None, typer.Option("--measures", "-m", help="Comma-separated.")] = None,
    where: Annotated[list[str] | None, typer.Option("--where", "-w", help="field OP value; repeatable.")] = None,
    order_by: Annotated[str | None, typer.Option("--order-by", help="Field to sort by.")] = None,
    descending: Annotated[bool, typer.Option("--desc", help="Sort descending.")] = False,
    limit: Annotated[int, typer.Option("--limit", help="Row cap.")] = 50,
) -> None:
    """Query a semantic model and print the result."""
    layer = build_layer(settings())
    target = layer.model(model)

    dimension_names, measure_names = _split(dimensions), _split(measures)
    if not measure_names:
        measure_names = list(target.measures)[:1]

    query = target
    for clause in where or []:
        query = query.filter(parse_filter(clause))
    # group_by and aggregate take measure and dimension *names*, not expressions.
    query = query.group_by(*dimension_names) if dimension_names else query
    query = query.aggregate(*measure_names)
    if order_by:
        column = getattr(deferred, order_by)
        query = query.order_by(column.desc() if descending else column)
    frame = query.limit(limit).execute()

    if frame.empty:
        typer.secho("no rows", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)
    typer.echo(frame.to_string(index=False))
    typer.secho(f"\n{len(frame)} row(s)", fg=typer.colors.GREEN)
