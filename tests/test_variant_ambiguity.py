"""MCP raster resolution refuses an ambiguous variant, as `midden terrain preview` does."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from midden.mcp.tools import spatial


def _rows(*variants):
    return [{"kind": "openness_pos", "variant": v, "path": f"/x/{v or 'u'}.tif"} for v in variants]


@pytest.fixture
def fake_catalog(monkeypatch):
    """Point the resolver at an in-memory catalog (no database)."""
    def install(rows):
        monkeypatch.setattr(spatial, "get_aoi", lambda conn, slug: SimpleNamespace(id=1))
        monkeypatch.setattr(spatial, "list_assets", lambda conn, aoi_id=None, kind=None: rows)
    return install


def test_several_variants_without_a_choice_raises(fake_catalog):
    """Two class variants and no variant argument: refuse, naming the choices."""
    fake_catalog(_rows("charcoal_hearth", "mound_earthwork"))
    with pytest.raises(ValueError, match="2 variants"):
        spatial._resolve_raster(None, "any-aoi", "openness_pos", None)


def test_explicit_variant_and_single_variant_resolve(fake_catalog):
    """A named variant resolves; so does the only variant when none is named."""
    fake_catalog(_rows("charcoal_hearth", "mound_earthwork"))
    row = spatial._resolve_raster(None, "any-aoi", "openness_pos", "mound_earthwork")
    assert row["variant"] == "mound_earthwork"
    fake_catalog(_rows(""))
    assert spatial._resolve_raster(None, "any-aoi", "openness_pos", None)["variant"] == ""
