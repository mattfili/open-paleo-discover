"""Round-trip on the intake YAML loader (spec.md §3).

`sources/*.yml` is the file a human edits most often. A loader that silently drops an
unrecognised key loses work, so the parse is strict and the round trip is pinned.
"""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from midden.config import settings
from midden.intake.schema import Source, load_all_sources, load_source

SOURCE_PATHS = sorted(settings().sources_dir.glob("*.yml"))


@pytest.mark.parametrize("path", SOURCE_PATHS, ids=lambda p: p.stem)
def test_round_trip_is_stable(path):
    """parse -> dump -> parse produces an identical structure."""
    first = load_source(path)
    second = Source.model_validate(yaml.safe_load(first.to_yaml()))
    assert first.as_yaml() == second.as_yaml()


@pytest.mark.parametrize("path", SOURCE_PATHS, ids=lambda p: p.stem)
def test_name_matches_filename(path):
    """The runner resolves sources by filename, so the two must agree."""
    assert load_source(path).name == path.stem


def test_unknown_keys_are_rejected():
    """An unrecognised key is an error, never a silent drop."""
    with pytest.raises(ValidationError):
        Source.model_validate(
            {
                "name": "x",
                "fetch": {"driver": "pynhd"},
                "load": {"target": "ref.x"},
                "typo_key": 1,
            }
        )


def test_upsert_without_key_is_rejected():
    """An upsert with no conflict target would silently become an append."""
    with pytest.raises(ValidationError):
        Source.model_validate(
            {
                "name": "x",
                "fetch": {"driver": "pynhd"},
                "load": {"target": "ref.x", "mode": "upsert"},
            }
        )


def test_all_sources_load():
    """Every YAML in sources/ parses."""
    assert load_all_sources(settings().sources_dir)
