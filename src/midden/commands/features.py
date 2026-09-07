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


def _regional_fit(aoi: str, class_id: str, weights: Path | None):
    """Score the regional frame and collect control footprints inside it.

    Returns (scored ScoreResult, raw stack frame, weight_set, {slug: geom}, frame
    descriptor for provenance). The background frame (B5) is the AOI's regional
    buffered extent — the same frame the regional surface is computed on.
    """
    import shapely

    weights_path = _class_weights(class_id, weights)
    weight_set = load_weights(weights_path)
    with connect() as conn:
        area = get_aoi(conn, aoi)
        stack = build_feature_stack(conn, area, clip_to_aoi=False)
        raw = pd.read_parquet(stack.path)
        controls = {
            r["slug"]: shapely.from_wkb(bytes(r["wkb"]))
            for r in fetch_all(
                conn,
                """SELECT slug, ST_AsBinary(geom) AS wkb FROM derived.aoi
                   WHERE role = 'control_positive'
                     AND ST_Intersects(geom, ST_MakeEnvelope(%s, %s, %s, %s, 26916))""",
                (
                    raw.easting.min(),
                    raw.northing.min(),
                    raw.easting.max(),
                    raw.northing.max(),
                ),
            )
        }
    if not controls:
        raise typer.BadParameter(
            f"No control_positive AOI intersects {aoi}'s regional frame; the test "
            "has nothing to measure. Seed controls or pick another AOI."
        )
    result = score_stack(raw, weight_set)
    frame_desc = {
        "frame": f"regional buffered extent of {aoi} (clip_to_aoi=false)",
        "frame_cells": len(raw),
        "weights": str(weights_path),
    }
    return result, raw, weight_set, controls, frame_desc


@score_app.command("validate")
def score_validate(
    aoi: Annotated[
        str, typer.Option("--aoi", help="AOI whose regional frame to test.")
    ],
    class_id: Annotated[
        str, typer.Option("--class", help="Class whose surface to test.")
    ],
    weights: Annotated[Path | None, typer.Option("--weights")] = None,
    draws: Annotated[
        int, typer.Option("--draws", help="Matched null footprints per control.")
    ] = 199,
    seed: Annotated[int, typer.Option("--seed")] = 42,
) -> None:
    """B1: matched-footprint permutation test — effect size with an error bar.

    The null translates each control's own footprint to random landform-matched
    positions in the background frame; the unit of permutation is the footprint,
    never the cell. Replaces the pass/fail threshold: reports observed, the null
    distribution, and empirical p = (r+1)/(k+1).
    """
    from midden import __version__
    from midden.derivation import open_derivation
    from midden.features.validate_score import permutation_test

    result, _raw, _ws, controls, frame_desc = _regional_fit(aoi, class_id, weights)
    outcomes = {
        slug: permutation_test(result.frame, geom, draws=draws, seed=seed)
        for slug, geom in controls.items()
    }
    with connect() as conn:
        area = get_aoi(conn, aoi)
        with open_derivation(
            conn,
            operation="score.validate",
            tool="midden.features.validate_score",
            tool_version=__version__,
            aoi_id=area.id,
            params={
                "class_id": class_id,
                "draws": draws,
                "seed": seed,
                **frame_desc,
                "results": outcomes,
            },
            inputs=[f"controls: {sorted(controls)}"],
        ):
            pass

    typer.secho(
        f"\nB1 permutation test — {class_id} on {aoi}'s regional frame", bold=True
    )
    typer.echo(
        f"{'control':<20}{'obs pct':>9}{'null pct (q05-q95)':>22}"
        f"{'obs enr':>9}{'null q95':>10}{'p(pct)':>9}"
    )
    typer.echo("-" * 82)
    for slug, o in outcomes.items():
        if "error" in o:
            typer.echo(f"{slug:<20}  {o['error']}")
            continue
        null = o["null"]
        typer.echo(
            f"{slug:<20}{o['observed']['pct_mean']:>9.1f}"
            f"{null['pct_mean']['q05']:>13.1f}-{null['pct_mean']['q95']:<7.1f}"
            f"{o['observed']['top5_enrich']:>7.2f}x"
            f"{null['top5_enrich']['q95']:>9.2f}x"
            f"{o['p_pct_mean']:>9}"
        )
    typer.echo(
        "\nHow to read this. 'obs pct' is the footprint's mean score percentile; the "
        "null range is what same-shaped, landform-matched footprints score elsewhere "
        "in the frame. p is one-sided and floored at 1/(draws+1) — a small p says the "
        "control sits high relative to matched ground, not that the model is right. "
        "Enrichment is top-5% occupancy over chance (1.0x = chance)."
    )


@score_app.command("ablate")
def score_ablate(
    aoi: Annotated[
        str, typer.Option("--aoi", help="AOI whose regional frame to test.")
    ],
    class_id: Annotated[
        str, typer.Option("--class", help="Class whose weight set to ablate.")
    ],
    weights: Annotated[Path | None, typer.Option("--weights")] = None,
    draws: Annotated[
        int, typer.Option("--draws", help="Null footprints per refit surface.")
    ] = 99,
    seed: Annotated[int, typer.Option("--seed")] = 42,
) -> None:
    """B2: hold each feature out, refit, and report delta-enrichment per control.

    A feature whose removal does not move the statistic is not carrying signal
    regardless of its weight; one whose removal raises it is actively harmful. The
    correlation matrix ships alongside because correlated features share signal —
    a small solo delta can mean 'shared', never only 'absent'.
    """
    from midden import __version__
    from midden.derivation import open_derivation
    from midden.features.validate_score import ablate

    _result, raw, weight_set, controls, frame_desc = _regional_fit(
        aoi, class_id, weights
    )
    report = ablate(raw, weight_set, controls, draws=draws, seed=seed)
    with connect() as conn:
        area = get_aoi(conn, aoi)
        with open_derivation(
            conn,
            operation="score.ablate",
            tool="midden.features.validate_score",
            tool_version=__version__,
            aoi_id=area.id,
            params={
                "class_id": class_id,
                "draws": draws,
                "seed": seed,
                **frame_desc,
                "results": report["ablations"],
                "baseline": report["baseline"],
                "correlations": report["correlations"],
            },
            inputs=[f"controls: {sorted(controls)}"],
        ):
            pass

    typer.secho(
        f"\nB2 ablation — {class_id} on {aoi}'s regional frame "
        f"(delta vs full model; negative = surface got worse without it)",
        bold=True,
    )
    for slug, base in report["baseline"].items():
        typer.echo(
            f"\n[{slug}]  full model: pct {base['observed']['pct_mean']:.1f}, "
            f"enrich {base['observed']['top5_enrich']:.2f}x, p {base.get('p_pct_mean')}"
        )
        typer.echo(
            f"{'feature held out':<24}{'pct':>7}{'delta':>8}{'enrich':>9}{'delta':>8}"
        )
        typer.echo("-" * 58)
        rows = sorted(
            report["ablations"].items(), key=lambda kv: kv[1][slug]["delta_pct_mean"]
        )
        for name, per in rows:
            r = per[slug]
            flag = "  <- harmful in the stack" if r["delta_pct_mean"] > 0.5 else ""
            typer.echo(
                f"{name:<24}{r['pct_mean']:>7.1f}{r['delta_pct_mean']:>+8.1f}"
                f"{r['top5_enrich']:>8.2f}x{r['delta_top5_enrich']:>+8.2f}{flag}"
            )
    typer.echo(
        "\nnormalised-feature correlations (shared signal makes solo deltas small):"
    )
    names = list(report["correlations"])
    typer.echo(" " * 24 + "".join(f"{n[:10]:>11}" for n in names))
    for a in names:
        typer.echo(
            f"{a:<24}"
            + "".join(
                f"{v:>11.2f}" if v is not None else f"{'-':>11}"
                for v in (report["correlations"][a][b] for b in names)
            )
        )


@score_app.command("polygons")
def score_polygons(
    aoi: Annotated[str, typer.Option("--aoi", help="AOI slug.")],
    class_id: Annotated[
        str, typer.Option("--class", help="Class whose surface to polygonise.")
    ],
    weights: Annotated[Path | None, typer.Option("--weights")] = None,
    top_pct: Annotated[
        float, typer.Option("--top-pct", help="Percent of cells to keep.")
    ] = 5.0,
    min_cells: Annotated[
        int, typer.Option("--min-cells", help="Drop zones smaller than this.")
    ] = 4,
) -> None:
    """F1: the class's top-percentile cells as ranked survey-candidate polygons.

    Clipped to the AOI (a survey zone outside the unit is not walkable permission-wise),
    ranked by mean cell percentile then area. burial_risk rides as a separate column:
    a high-scoring zone with high burial risk means right landform, invisible to
    LiDAR — probe it, don't image it.
    """
    from midden import __version__
    from midden.derivation import open_derivation
    from midden.features.polygons import build_zones, store_zones

    weight_set = load_weights(_class_weights(class_id, weights))
    with connect() as conn:
        area = get_aoi(conn, aoi)
        stack = build_feature_stack(conn, area, clip_to_aoi=True)
    frame = pd.read_parquet(stack.path)
    result = score_stack(frame, weight_set)
    zones = build_zones(result.frame, top_pct=top_pct, min_cells=min_cells)

    with connect() as conn:
        area = get_aoi(conn, aoi)
        with open_derivation(
            conn,
            operation="score.polygons",
            tool="midden.features.polygons",
            tool_version=__version__,
            aoi_id=area.id,
            params={
                "class_id": class_id,
                "top_pct": top_pct,
                "min_cells": min_cells,
                "weight_set": result.weight_set,
                "n_zones": len(zones),
            },
            inputs=[str(stack.path)],
        ) as derivation_id:
            stored = store_zones(
                conn, area, class_id, zones, derivation_id=derivation_id
            )

    if not zones:
        typer.secho(
            f"{aoi}/{class_id}: no zone of {min_cells}+ cells in the top "
            f"{top_pct:g}% — nothing worth walking at this threshold.",
            fg=typer.colors.YELLOW,
        )
        return
    typer.secho(
        f"\n{aoi} / {class_id}: {stored} ranked zone(s) "
        f"(top {top_pct:g}%, derivation {derivation_id})",
        bold=True,
    )
    typer.echo(
        f"{'rank':>4}{'area_m2':>10}{'pct':>7}{'score':>8}{'HAND m':>8}{'burial':>8}"
    )
    typer.echo("-" * 48)
    for z in zones[:15]:
        burial = f"{z['burial_risk']:.2f}" if z["burial_risk"] is not None else "-"
        hand = f"{z['hand_mean_m']:.1f}" if z["hand_mean_m"] is not None else "-"
        typer.echo(
            f"{z['rank']:>4}{z['area_m2']:>10.0f}{z['pct_mean']:>7.1f}"
            f"{z['score_mean']:>8.3f}{hand:>8}{burial:>8}"
        )
    if len(zones) > 15:
        typer.echo(f"  ... {len(zones) - 15} more in derived.candidate_zone")
    typer.echo(
        "\nHow to read this. Rank orders zones by mean cell percentile (area breaks "
        "ties): where the landform argues hardest for this class, per the current "
        "weight set — a hypothesis, not a probability. burial: mean companion-band "
        "value, deliberately not in the score — high burial on a high rank means "
        "'right ground, LiDAR-blind; survey by probe/auger'. Zones inherit every "
        "caveat of the weight set that made them (see score validate for its error "
        "bars)."
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
