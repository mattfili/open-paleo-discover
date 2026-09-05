"""`midden features` and `midden score` — the 10 m stack, the overlay, and the controls."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from midden.aoi import get_aoi
from midden.config import settings
from midden.db import connect, fetch_all
from midden.features.score import (
    load_weights,
    publish_score,
    score_stack,
    write_score_raster,
)
from midden.features.stack import build_feature_stack, register_stack
from midden.registry import get_class
from midden.skills import script_path
from midden.terrain.cog import list_assets

features_app = typer.Typer(help="Build the 10 m feature stack.", no_args_is_help=True)
score_app = typer.Typer(
    help="Weighted overlay and control validation.", no_args_is_help=True
)


def _hand_template(conn, aoi) -> Path:
    """The modelling-grid raster whose grid a score surface is burnt back onto."""
    rows = [
        r for r in list_assets(conn, aoi_id=aoi.id, kind="hand") if r["grid"] == "model"
    ]
    if not rows:
        raise typer.BadParameter(
            f"{aoi.slug}: no modelling-grid HAND raster. "
            f"Run `midden terrain run --aoi {aoi.slug} --grid model` first."
        )
    return Path(rows[0]["path"])


@features_app.command("build")
def features_build(
    aoi: Annotated[str, typer.Option("--aoi", help="AOI slug.")],
    regional: Annotated[
        bool,
        typer.Option(
            "--regional",
            help="Keep the full buffered extent instead of clipping "
            "to the AOI. Needed for a control test.",
        ),
    ] = False,
) -> None:
    """Assemble the 10 m feature stack for an AOI and write it to Parquet."""
    with connect() as conn:
        area = get_aoi(conn, aoi)
        result = build_feature_stack(conn, area, clip_to_aoi=not regional)
        if not regional:
            register_stack(conn, area, result)
    typer.secho(
        f"{result.aoi_slug}: {result.rows:,} cells -> {result.path}",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"  columns: {', '.join(result.columns)}")


def _class_weights(class_id: str, weights: Path | None) -> Path:
    """Resolve a class's weight-set path, erroring with the fix rather than a fallback."""
    if weights is not None:
        return weights
    path = settings().weights_dir / f"{class_id}.yml"
    if not path.exists():
        raise typer.BadParameter(
            f"No weight set for class {class_id!r} at {path}. A score surface is a "
            f"per-class hypothesis: write one (see weights/open_habitation.yml) or pass "
            f"--weights explicitly."
        )
    return path


@score_app.command("run")
def score_run(
    aoi: Annotated[str, typer.Option("--aoi", help="AOI slug.")],
    class_id: Annotated[
        str,
        typer.Option(
            "--class", help="Target class the surface scores for. See `midden classes`."
        ),
    ],
    weights: Annotated[
        Path | None,
        typer.Option(
            "--weights", help="Weight-set YAML; defaults to weights/<class>.yml."
        ),
    ] = None,
    regional: Annotated[
        bool,
        typer.Option(
            "--regional",
            help="Score the buffered extent. A control test needs "
            "this: ranking a site against itself is not a test.",
        ),
    ] = False,
) -> None:
    """Apply a class's weight set to an AOI's feature stack and write a score raster.

    Every score surface is qualified by a target class: the features that predict a
    Mississippian mound platform are not the features that predict a charcoal hearth.
    """
    from midden import __version__
    from midden.derivation import open_derivation

    weights_path = _class_weights(class_id, weights)
    weight_set = load_weights(weights_path)
    with connect() as conn:
        area = get_aoi(conn, aoi)
        cls = get_class(conn, class_id)
        if cls.grid not in ("model", "both"):
            raise typer.BadParameter(
                f"Class {class_id!r} is on the {cls.grid!r} grid; a 10 m suitability "
                f"surface for it would be blind to its signature. Use the detection "
                f"chain instead."
            )
        stack = build_feature_stack(conn, area, clip_to_aoi=not regional)
        template = _hand_template(conn, area)

    frame = pd.read_parquet(stack.path)
    result = score_stack(frame, weight_set)
    suffix = "_regional" if regional else ""
    destination = settings().aoi_cog_dir(aoi) / f"score{suffix}_10m_{class_id}.tif"
    write_score_raster(result.frame, template, destination)
    with connect() as conn:
        area = get_aoi(conn, aoi)
        with open_derivation(
            conn,
            operation="score.overlay",
            tool="midden.features.score",
            tool_version=__version__,
            aoi_id=area.id,
            params={
                "class_id": class_id,
                "weights": str(weights_path),
                "weight_set": result.weight_set,
                "regional": regional,
            },
            inputs=[str(stack.path)],
        ) as derivation_id:
            if not regional:
                publish_score(
                    conn,
                    area,
                    destination,
                    class_id=class_id,
                    derivation_id=derivation_id,
                )

    typer.secho(
        f"{aoi}: scored {len(frame):,} cells for {class_id} with '{result.weight_set}'",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        f"  mean {result.frame.score.mean():.3f}  "
        f"range {result.frame.score.min():.3f}..{result.frame.score.max():.3f}"
    )
    typer.echo("  mean normalised contribution per feature:")
    for name, value in sorted(result.contributions.items(), key=lambda kv: -kv[1]):
        typer.echo(f"    {name:<24}{value:.4f}  (weight {result.weights[name]:.3f})")
    typer.echo(f"  -> {destination}")


@score_app.command("controls")
def score_controls(
    aoi: Annotated[
        str, typer.Option("--aoi", help="AOI whose regional score surface to test.")
    ],
    class_id: Annotated[
        str,
        typer.Option(
            "--class",
            help="Class whose score surface to test. Validation "
            "is per class: a mound control says nothing "
            "about a hearth surface.",
        ),
    ],
    top_pct: Annotated[
        float, typer.Option("--top-pct", help="Percentile a control must reach.")
    ] = 5.0,
) -> None:
    """Run the control falsification test over one class's regional score surface.

    Invokes `control_check.py` from the landform-archaeology skill as a subprocess: it
    exits non-zero on failure by design, so it can gate a weight-set change.
    """
    config = settings()
    controls = config.data_dir / "controls.geojson"
    if not controls.exists():
        _write_controls(controls)

    surface = config.aoi_cog_dir(aoi) / f"score_regional_10m_{class_id}.tif"
    if not surface.exists():
        raise typer.BadParameter(
            f"No regional score surface at {surface}. "
            f"Run `midden score run --aoi {aoi} --class {class_id} --regional` first."
        )
    outcome = subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(script_path("landform-archaeology", "control_check")),
            str(surface),
            str(controls),
            "--top-pct",
            str(top_pct),
        ],
        check=False,
    )
    raise typer.Exit(code=outcome.returncode)


def _write_controls(destination: Path) -> None:
    """Export the control AOIs as GeoJSON for control_check.py."""
    import json

    with connect() as conn:
        rows = fetch_all(
            conn,
            """SELECT slug, role, source, ST_AsGeoJSON(geom) AS gj
               FROM derived.aoi WHERE role LIKE 'control%' ORDER BY slug""",
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "name": r["slug"],
                            "role": r["role"],
                            "source": r["source"],
                        },
                        "geometry": json.loads(r["gj"]),
                    }
                    for r in rows
                ],
            }
        )
    )


@score_app.command("weights")
def score_weights(
    class_id: Annotated[
        str | None,
        typer.Option(
            "--class", help="Class whose weight set to show (weights/<class>.yml)."
        ),
    ] = None,
    weights: Annotated[
        Path | None, typer.Option("--weights", help="Explicit weight-set YAML path.")
    ] = None,
) -> None:
    """Show a weight set: what it scores, at what weight, and what it reports alongside."""
    if class_id is None and weights is None:
        raise typer.BadParameter(
            "Pass --class (weights/<class>.yml) or --weights <path>."
        )
    weight_set = load_weights(
        weights if weights is not None else _class_weights(class_id, None)
    )
    typer.secho(f"{weight_set.name}", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  {weight_set.description.strip()}\n")
    total = sum(float(s.get("weight", 0)) for s in weight_set.scored_features.values())
    typer.echo(f"{'feature':<24}{'weight':>8}{'share':>8}  normalisation")
    typer.echo("-" * 72)
    for name, spec in weight_set.features.items():
        weight = float(spec.get("weight", 0.0))
        method = (spec.get("normalize") or {}).get("method", "-")
        share = f"{weight / total:.1%}" if weight else "excl."
        typer.echo(f"{name:<24}{weight:>8.1f}{share:>8}  {method}")
    typer.echo("\ncompanion bands (reported alongside, never summed into the score):")
    for name in weight_set.companion_bands:
        typer.echo(f"  {name}")
