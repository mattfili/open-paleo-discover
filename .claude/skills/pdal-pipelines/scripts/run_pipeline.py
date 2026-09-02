#!/usr/bin/env python3
"""
Run a PDAL pipeline via the CLI, with error handling and metadata capture.

Uses the CLI rather than the Python bindings on purpose: the bindings compile
against libpdal and the versions must match, which breaks regularly on macOS. The
pipeline is JSON either way, so nothing is lost.

Usage as a module:

    from run_pipeline import run, PdalError
    run({"pipeline": [...]}, metadata_out=Path("meta.json"))

Usage from the shell:

    python run_pipeline.py pipeline.json
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


class PdalError(RuntimeError):
    """A PDAL invocation failed."""


def ensure_pdal() -> str:
    """Locate the pdal binary, with an actionable message if it is missing."""
    exe = shutil.which("pdal")
    if exe is None:
        raise PdalError(
            "pdal not found on PATH. Install with `brew install pdal`. "
            "Do not fall back to the Python bindings -- they require a libpdal "
            "version match that breaks regularly on macOS."
        )
    return exe


def version() -> str:
    out = subprocess.run([ensure_pdal(), "--version"], capture_output=True, text=True)
    return out.stdout.strip() or out.stderr.strip()


def run(
    pipeline: dict | list | Path,
    *,
    stream: bool = False,
    metadata_out: Path | None = None,
    timeout: int | None = None,
) -> dict:
    """Execute a pipeline. Returns parsed metadata if requested, else {}.

    `pipeline` may be a dict, a bare list of stages, or a path to a JSON file.

    `stream` uses chunked processing with flat memory. It only works if every stage
    is streamable -- SMRF, outlier, sample and hag_delaunay are not. PDAL reports
    "Pipeline is not streamable" rather than silently using more memory.

    `metadata_out` writes what actually ran, including resolved paths and every
    stage's options. Keep it next to the output; it is the record of what produced
    a given DEM and it costs nothing.
    """
    exe = ensure_pdal()

    tmp: Path | None = None
    if isinstance(pipeline, Path):
        pipeline_path = pipeline
    else:
        spec = pipeline if isinstance(pipeline, dict) else {"pipeline": pipeline}
        fd = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(spec, fd, indent=2)
        fd.close()
        tmp = Path(fd.name)
        pipeline_path = tmp

    cmd = [exe, "pipeline", str(pipeline_path)]
    if stream:
        cmd.append("--stream")
    if metadata_out is not None:
        cmd += ["--metadata", str(metadata_out)]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise PdalError(
            f"pdal timed out after {timeout}s. For an EPT read this usually means the "
            "bounds landed outside the dataset -- the reader waits rather than failing. "
            "Check that bounds are in the EPT's own CRS (EPSG:3857 for the USGS public "
            "bucket), not your project CRS."
        ) from exc
    finally:
        if tmp is not None and metadata_out is None:
            tmp.unlink(missing_ok=True)

    if proc.returncode != 0:
        raise PdalError(
            f"pdal exited {proc.returncode}\n"
            f"--- stderr ---\n{proc.stderr.strip()}\n"
            f"--- stdout ---\n{proc.stdout.strip()}"
        )

    if metadata_out is not None and metadata_out.exists():
        return json.loads(metadata_out.read_text())
    return {}


def info(path: Path, *, stats: bool = False, dimensions: str | None = None) -> dict:
    """`pdal info` as a dict.

    Run this before any real work. Two questions it answers immediately: is the
    data ground-classified, and what CRS is it in. Skipping the check is how you
    end up debugging an empty DEM.
    """
    cmd = [ensure_pdal(), "info", str(path)]
    if stats:
        cmd.append("--stats")
    else:
        cmd.append("--summary")
    if dimensions:
        cmd += ["--dimensions", dimensions]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise PdalError(f"pdal info failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(__doc__)
        print(f"\nInstalled: {version()}")
        raise SystemExit(0)

    print(f"Using {version()}")
    run(Path(sys.argv[1]), metadata_out=Path(sys.argv[1]).with_suffix(".meta.json"))
    print("Pipeline completed.")
