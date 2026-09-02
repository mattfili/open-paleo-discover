"""Driver registry for intake sources (spec.md §5).

Each driver implements one method, `fetch(params, aoi, dest) -> Path`, and writes a
GeoPackage. Adding a source should never require touching the runner — it needs a YAML in
`sources/` and, if the protocol is new, a driver registered here.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from midden.aoi import Aoi

__all__ = ["Driver", "DriverError", "get_driver", "register", "registered_drivers"]


class DriverError(RuntimeError):
    """A driver could not retrieve its source."""


class Driver(Protocol):
    """Fetch a source to a GeoPackage on disk."""

    def __call__(self, params: dict, aoi: Aoi | None, dest: Path) -> Path:
        """Retrieve the source and write it to `dest`, returning `dest`."""
        ...


_REGISTRY: dict[str, Driver] = {}


def register(name: str) -> Callable[[Driver], Driver]:
    """Register a driver under the name used in `sources/*.yml` `fetch.driver`."""

    def decorate(fn: Driver) -> Driver:
        if name in _REGISTRY:
            raise ValueError(f"Driver {name!r} is already registered.")
        _REGISTRY[name] = fn
        return fn

    return decorate


def registered_drivers() -> list[str]:
    """Return the registered driver names, sorted."""
    _load_builtin()
    return sorted(_REGISTRY)


def get_driver(name: str) -> Driver:
    """Return a driver by name, or raise listing what is available."""
    _load_builtin()
    try:
        return _REGISTRY[name]
    except KeyError:
        raise DriverError(
            f"No driver {name!r}. Registered: {', '.join(sorted(_REGISTRY)) or '(none)'}. "
            f"Add one in midden/intake/drivers/ and decorate it with @register({name!r})."
        ) from None


def _load_builtin() -> None:
    """Import the driver modules so their @register decorators run."""
    from midden.intake.drivers import (  # noqa: F401  (import for side effect)
        arcgis,
        nhd,
    )
