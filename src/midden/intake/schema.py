"""Pydantic model of `sources/*.yml` — the intake contract (spec.md §5).

Two YAMLs per source, deliberately: this one is midden's schema (fetch, transform, load),
and `semantic/<name>.yml` is boring-semantic-layer's. They are linked by table name. The
seam is kept clean so a BSL upgrade never becomes a migration of an envelope we invented.

Everything here is pure. Nothing fetches, connects, or writes.

The round trip `parse -> dump -> parse` is stable, which is what `tests/
test_intake_roundtrip.py` pins. That matters because these files are the thing a human
edits most often, and a loader that silently drops an unrecognised key is a loader that
loses work.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "IndexSpec",
    "Join",
    "LoadMode",
    "LoadSpec",
    "Source",
    "TransformStep",
    "load_all_sources",
    "load_source",
]

_INDEX_RE = re.compile(r"^(?P<method>gist|btree|hash|gin|brin)\((?P<column>[a-z_][a-z0-9_]*)\)$")


class LoadMode(StrEnum):
    """How a load writes into its target table."""

    REPLACE = "replace"
    APPEND = "append"
    UPSERT = "upsert"


class Strict(BaseModel):
    """Base for every node: unknown keys are an error, never a silent drop."""

    model_config = ConfigDict(extra="forbid")


class FetchSpec(Strict):
    """Which driver retrieves this source, with what parameters, cached where."""

    driver: str
    params: dict[str, Any] = Field(default_factory=dict)
    cache: Path | None = None


class TransformStep(Strict):
    """One ordered transform, written in YAML as a single-key mapping.

    The four forms, all of which round-trip back to exactly what was written:

        - reproject: {to: EPSG:26916}
        - select: [comid, gnis_name, geometry]
        - rename: {streamorde: stream_order}
        - filter: "stream_order >= 1"
    """

    op: Literal["reproject", "select", "rename", "filter"]
    value: Any

    @model_validator(mode="before")
    @classmethod
    def _unwrap(cls, data: Any) -> Any:
        """Accept the single-key mapping form that the YAML actually uses."""
        if not isinstance(data, dict) or set(data) <= {"op", "value"}:
            return data
        if len(data) != 1:
            raise ValueError(
                f"A transform step must be a single-key mapping; got keys {sorted(data)}. "
                f"Write each operation as its own list item."
            )
        (op, value), = data.items()
        return {"op": op, "value": value}

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        """Reject a step whose payload cannot mean anything for that operation."""
        expected = {
            "reproject": dict,
            "select": list,
            "rename": dict,
            "filter": str,
        }[self.op]
        if not isinstance(self.value, expected):
            raise TypeError(
                f"transform step {self.op!r} expects a {expected.__name__}, "
                f"got {type(self.value).__name__}"
            )
        if self.op == "reproject" and "to" not in self.value:
            raise ValueError("transform step 'reproject' needs a 'to' key, e.g. {to: EPSG:26916}")
        return self

    def as_yaml(self) -> dict[str, Any]:
        """Return the single-key mapping this step was written as."""
        return {self.op: self.value}


class IndexSpec(Strict):
    """A single index, written in YAML as `gist(geom)` or `btree(stream_order)`."""

    method: str
    column: str

    @model_validator(mode="before")
    @classmethod
    def _parse(cls, data: Any) -> Any:
        """Accept the compact `method(column)` string form."""
        if not isinstance(data, str):
            return data
        match = _INDEX_RE.match(data.strip())
        if not match:
            raise ValueError(
                f"Cannot parse index {data!r}. Expected method(column), "
                f"e.g. gist(geom) or btree(stream_order)."
            )
        return match.groupdict()

    def as_yaml(self) -> str:
        """Return the compact string form."""
        return f"{self.method}({self.column})"


class LoadSpec(Strict):
    """Where the transformed data lands and how."""

    target: str
    geometry_column: str = "geom"
    mode: LoadMode = LoadMode.REPLACE
    upsert_key: list[str] = Field(default_factory=list)
    index: list[IndexSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _upsert_needs_key(self) -> Self:
        """An upsert with no key would silently become an append."""
        if self.mode is LoadMode.UPSERT and not self.upsert_key:
            raise ValueError(
                f"load.mode is 'upsert' for target {self.target!r} but upsert_key is empty. "
                f"Without a key there is nothing to conflict on and rows would duplicate."
            )
        return self

    @property
    def schema_name(self) -> str:
        """Schema half of `target`."""
        return self.target.split(".", 1)[0]

    @property
    def table_name(self) -> str:
        """Table half of `target`."""
        return self.target.split(".", 1)[1]


class Join(Strict):
    """A join declared here and consumed by the BSL generator (spec.md §5)."""

    to: str
    type: str
    predicate: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)


class Source(Strict):
    """One `sources/*.yml` file."""

    name: str
    description: str = ""
    fetch: FetchSpec
    transform: list[TransformStep] = Field(default_factory=list)
    load: LoadSpec
    joins: list[Join] = Field(default_factory=list)

    def as_yaml(self) -> dict[str, Any]:
        """Return the plain structure this source was written as.

        Emitted key-for-key so `parse -> dump -> parse` is stable and a hand-edited file
        survives a round trip through the loader unchanged.
        """
        fetch: dict[str, Any] = {"driver": self.fetch.driver}
        if self.fetch.params:
            fetch["params"] = self.fetch.params
        if self.fetch.cache is not None:
            fetch["cache"] = str(self.fetch.cache)

        load: dict[str, Any] = {
            "target": self.load.target,
            "geometry_column": self.load.geometry_column,
            "mode": self.load.mode.value,
        }
        if self.load.upsert_key:
            load["upsert_key"] = self.load.upsert_key
        if self.load.index:
            load["index"] = [i.as_yaml() for i in self.load.index]

        out: dict[str, Any] = {"name": self.name}
        if self.description:
            out["description"] = self.description
        out["fetch"] = fetch
        if self.transform:
            out["transform"] = [t.as_yaml() for t in self.transform]
        out["load"] = load
        if self.joins:
            out["joins"] = [j.model_dump(exclude_none=True, exclude_defaults=True)
                            for j in self.joins]
        return out

    def to_yaml(self) -> str:
        """Serialise back to YAML text."""
        return yaml.safe_dump(self.as_yaml(), sort_keys=False, default_flow_style=False)


def load_source(path: Path) -> Source:
    """Parse one source YAML. Raises on any unrecognised key."""
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise TypeError(f"{path} does not contain a YAML mapping.")
    try:
        return Source.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"{path}: {exc}") from exc


def load_all_sources(sources_dir: Path) -> dict[str, Source]:
    """Parse every source YAML in a directory, keyed by source name."""
    sources = {}
    for path in sorted(sources_dir.glob("*.yml")):
        source = load_source(path)
        if source.name != path.stem:
            raise ValueError(
                f"{path}: name is {source.name!r} but the filename says {path.stem!r}. "
                f"They must agree — the runner resolves sources by filename."
            )
        sources[source.name] = source
    return sources
