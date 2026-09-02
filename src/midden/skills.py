"""Loader for the technique scripts bundled in `.claude/skills/`.

CLAUDE.md: "`wbt_helpers.py`, `hydro_chain.py`, `run_pipeline.py`, `dem_from_ept.py`,
`inspect.py`, and `control_check.py` are meant to be imported or invoked, not
paraphrased." Those scripts are not importable by name — the skill directories contain
hyphens, there are no `__init__.py` files, and the modules import their siblings bare
(`from wbt_helpers import ...`). This module is the single seam that bridges that gap.

The coupling is deliberate and contained: midden depends on the layout of
`.claude/skills/<skill>/scripts/`. If the skills move, this file changes and nothing else
does.

Two rules the implementation enforces:

1. The scripts directory is *appended* to `sys.path`, never prepended, so the standard
   library and site-packages always win a name contest.
2. `load()` refuses any module whose name shadows a standard-library module.
   `pdal-pipelines/scripts/inspect.py` is exactly that case; importing it would poison
   `inspect` for pydantic, typer, and everything else. Use `script_path()` and run it as a
   subprocess instead.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from midden.config import settings

__all__ = ["SkillScriptError", "load", "script_path", "scripts_dir"]

_CACHE: dict[tuple[str, str], ModuleType] = {}


class SkillScriptError(RuntimeError):
    """A bundled skill script could not be located or loaded."""


def scripts_dir(skill: str) -> Path:
    """Return the `scripts/` directory of one bundled skill."""
    path = settings().skills_dir / skill / "scripts"
    if not path.is_dir():
        raise SkillScriptError(
            f"No scripts directory for skill {skill!r} at {path}. "
            f"Expected the bundled skills under {settings().skills_dir}."
        )
    return path


def script_path(skill: str, module: str) -> Path:
    """Return the path to one script, for subprocess invocation.

    Use this rather than `load()` for scripts that are command-line tools in their own
    right — `control_check.py` calls `sys.exit(1)` to gate a weight-set change, and
    `inspect.py` shadows a standard-library module.
    """
    path = scripts_dir(skill) / f"{module}.py"
    if not path.is_file():
        raise SkillScriptError(f"No script {module!r} in skill {skill!r} (looked at {path}).")
    return path


def load(skill: str, module: str) -> ModuleType:
    """Import a bundled skill script and return the module object.

    The module is cached, so repeated calls return the same object and the script's
    top-level cost is paid once.
    """
    cached = _CACHE.get((skill, module))
    if cached is not None:
        return cached

    if module in sys.stdlib_module_names:
        raise SkillScriptError(
            f"Refusing to import {skill}/scripts/{module}.py: {module!r} shadows a "
            f"standard-library module and importing it would break unrelated code. "
            f"Invoke it as a subprocess via script_path({skill!r}, {module!r}) instead."
        )

    path = script_path(skill, module)

    # These scripts import their siblings bare, so the directory must be importable.
    # Append, never insert(0, ...), so stdlib and site-packages keep priority.
    directory = str(path.parent)
    if directory not in sys.path:
        sys.path.append(directory)

    spec = importlib.util.spec_from_file_location(f"midden._skill_{module}", path)
    if spec is None or spec.loader is None:
        raise SkillScriptError(f"Could not build an import spec for {path}.")

    loaded = importlib.util.module_from_spec(spec)
    # Register before exec so any self-reference during execution resolves.
    sys.modules[spec.name] = loaded
    try:
        spec.loader.exec_module(loaded)
    except Exception as exc:
        del sys.modules[spec.name]
        raise SkillScriptError(f"Failed to execute {path}: {exc}") from exc

    _CACHE[(skill, module)] = loaded
    return loaded
