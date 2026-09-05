"""`midden validate` — tests that can falsify, starting with the vanished-feature test."""

from __future__ import annotations

from typing import Annotated

import typer

from midden.db import connect
from midden.validate import validate_histmap

validate_app = typer.Typer(
    help="Validation that can falsify. Every test runs per class.",
    no_args_is_help=True,
)

#: The EPT project covering the Middle Tennessee control AOIs.
DEFAULT_EPT_PROJECT = "USGS_LPC_TN_Middle_B1_2018_LAS_2019"


@validate_app.command("histmap")
def validate_histmap_cmd(  # cq-allow: report printing is deliberately verbose — output
    # that is not explained is not finished (midden-interpretation), and the prose is
    # most of the line count.
    sheet_id: Annotated[
        str, typer.Option("--sheet", help="Catalogued histmap sheet_id.")
    ],
    class_id: Annotated[
        str, typer.Option("--class", help="Class whose symbols to test.")
    ],
    aoi: Annotated[
        str | None,
        typer.Option(
            "--aoi",
            help="Existing AOI to test within; default cuts AOIs "
            "around the symbol clusters.",
        ),
    ] = None,
    ept_project: Annotated[
        str, typer.Option("--ept-project", help="EPT project for the detection grid.")
    ] = DEFAULT_EPT_PROJECT,
    null_per_cluster: Annotated[
        int,
        typer.Option(
            "--null",
            help="Matched background discs drawn per cluster "
            "for the negative control; 0 disables (the "
            "report then says recall is unverified).",
        ),
    ] = 12,
) -> None:
    """The vanished-feature test: does detection fire where the historic map says?

    Per mapped symbol, reports whether the class's detection surfaces fired within the
    symbol's positional tolerance, then recall and the false-negative list. Misses are
    as much the result as hits — they are what let recall be estimated.
    """
    with connect() as conn:
        report = validate_histmap(
            conn,
            sheet_id,
            class_id,
            ept_project=ept_project,
            aoi_slug=aoi,
            null_per_cluster=null_per_cluster,
        )

    typer.secho(
        f"\nvanished-feature test — {class_id} on {sheet_id} "
        f"(derivation {report['derivation_id']})",
        bold=True,
    )
    if report["detectability"] == "proxy":
        typer.secho(
            f"PROXY CLASS: {class_id} has no direct LiDAR signature. A HIT below is "
            "surrogate-landform signal (e.g. a cave entrance for saltpeter_works), "
            "never a detection of the class itself.",
            fg=typer.colors.YELLOW,
            bold=True,
        )
    typer.echo(
        f"{'symbol':<28}{'tol_m':>6}{'disc_m':>8}  {'hit':<5}{'fired on':<28}detail"
    )
    typer.echo("-" * 106)
    for r in report["results"]:
        parts = []
        for kind, d in r.detail.items():
            if not d.get("valid"):
                parts.append(f"{kind}: no data")
            else:
                parts.append(f"{kind}: p{d['pctile_max']} n{d['cluster_cells']}")
        typer.echo(
            f"{r.name:<28}{r.tolerance_m:>6.0f}{r.disc_m:>8.0f}  "
            f"{'HIT' if r.hit else 'miss':<5}"
            f"{','.join(r.fired_surfaces) or '-':<28}{'; '.join(parts)}"
        )

    evaluable, hits = report["evaluable"], report["hits"]
    # Only evaluable symbols can be false negatives; a coverage gap is a data gap.
    misses = [
        r.name
        for r in report["results"]
        if not r.hit and any(d.get("valid") for d in r.detail.values())
    ]
    typer.echo("")
    if evaluable:
        typer.secho(
            f"recall {hits}/{evaluable} = {report['recall']:.0%} "
            f"(false negatives: {', '.join(misses) or 'none'})",
            fg=typer.colors.GREEN if hits else typer.colors.YELLOW,
        )
    else:
        typer.secho(
            "no symbol had enough valid raster to evaluate", fg=typer.colors.RED
        )
    if report["null_draws"]:
        rate = report["null_rate"]
        exceeds = bool(evaluable) and (report["recall"] > rate)
        quiet = rate <= 0.25
        if exceeds and quiet:
            verdict, colour = (
                "Recall exceeds a quiet background — the rule carries information "
                "here.",
                typer.colors.GREEN,
            )
        elif exceeds:
            verdict, colour = (
                "Recall exceeds the background rate, but the background itself fires "
                "often — weakly informative at best; a hit here is closer to 'ground "
                "is textured' than 'feature found'.",
                typer.colors.YELLOW,
            )
        else:
            verdict, colour = (
                "Recall does NOT exceed the background rate — this recall is "
                "uninformative; the rule fires on ordinary ground as readily as on "
                "mapped symbols.",
                typer.colors.RED,
            )
        typer.secho(
            f"negative control: {report['null_fired']}/{report['null_draws']} matched "
            f"background discs fire (rate <= {rate:.0%}, Laplace). " + verdict,
            fg=colour,
            bold=not (exceeds and quiet),
        )
    else:
        typer.secho(
            "negative control: no null discs could be drawn — treat recall as "
            "unverified.",
            fg=typer.colors.RED,
        )

    # What this does and does not claim — nothing ships unexplained.
    typer.echo(
        "\nHow to read this. Each symbol came off the historic sheet with a recorded\n"
        "positional error; that error is the disc the rule searched, so a HIT means a\n"
        "connected anomaly of the class's expected sign and size lies within where the\n"
        "map said the feature was — not that the feature is confirmed. A nearby modern\n"
        "pad, a tree throw cluster, or a karst depression can fire the same rule: a HIT\n"
        "is a candidate for the confuser ledger, not a find. A MISS can mean the feature\n"
        "was razed below LiDAR relief, lies buried, sits outside the recorded tolerance\n"
        "(digitization error), or that the class's search radius and thresholds are\n"
        "wrong — the per-surface percentiles above separate 'nothing there' (low p) from\n"
        "'something there but under min_cells' (high p, small n)."
    )
    if report["unreviewed"]:
        typer.secho(
            f"\ncaveat: {report['unreviewed']} of {len(report['results'])} symbols are "
            "machine-digitized and unreviewed; a miss may be a mislocated label rather "
            "than a missing feature.",
            fg=typer.colors.YELLOW,
        )
