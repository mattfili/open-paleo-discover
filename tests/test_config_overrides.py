"""Path overrides and the non-editable-install guard (stabilization pass, section 4)."""

from __future__ import annotations

import pytest

from midden.config import REPO_ROOT, ResourceDirectoryError, Settings, env_file_path


def _clean(monkeypatch):
    for name in (
        "MIDDEN_HOME", "MIDDEN_DATA_DIR", "MIDDEN_SCRATCH_DIR", "MIDDEN_EXPORTS_DIR",
        "MIDDEN_ENV_FILE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_the_repo_layout(monkeypatch):
    """With nothing set, every mutable path stays under the repo, as before."""
    _clean(monkeypatch)
    s = Settings(_env_file=None)
    assert s.data_dir == REPO_ROOT / "data"
    assert s.scratch_dir == REPO_ROOT / "scratch"
    assert s.exports_dir == REPO_ROOT / "exports"
    assert env_file_path() == REPO_ROOT / ".env"


def test_midden_home_relocates_state_and_env(monkeypatch, tmp_path):
    """MIDDEN_HOME moves data/, scratch/, exports/ and the .env lookup together."""
    _clean(monkeypatch)
    monkeypatch.setenv("MIDDEN_HOME", str(tmp_path))
    s = Settings(_env_file=None)
    assert (s.data_dir, s.scratch_dir, s.exports_dir) == (
        tmp_path / "data", tmp_path / "scratch", tmp_path / "exports")
    assert s.cogs_dir == tmp_path / "data" / "cogs"
    assert env_file_path() == tmp_path / ".env"


def test_per_path_override_beats_midden_home(monkeypatch, tmp_path):
    """A per-path variable wins over MIDDEN_HOME, and MIDDEN_ENV_FILE over its .env."""
    _clean(monkeypatch)
    monkeypatch.setenv("MIDDEN_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MIDDEN_DATA_DIR", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("MIDDEN_ENV_FILE", str(tmp_path / "my.env"))
    s = Settings(_env_file=None)
    assert s.data_dir == tmp_path / "elsewhere"
    assert s.scratch_dir == tmp_path / "home" / "scratch"
    assert env_file_path() == tmp_path / "my.env"


def test_env_file_is_read_from_the_override(monkeypatch, tmp_path):
    """Connection settings come from the relocated .env."""
    _clean(monkeypatch)
    env = tmp_path / "x.env"
    env.write_text("POSTGRES_USER=relocated\nPOSTGRES_PORT=5999\n")
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    s = Settings(_env_file=env)
    assert (s.postgres_user, s.postgres_port) == ("relocated", 5999)


def test_missing_resource_dirs_fail_with_an_actionable_message(monkeypatch, tmp_path):
    """A non-editable install (bundled dirs absent) raises naming the dirs and the fix."""
    _clean(monkeypatch)
    s = Settings(_env_file=None)
    s.__dict__["sql_dir"] = tmp_path / "no-sql"
    s.__dict__["skills_dir"] = tmp_path / "no-skills"
    with pytest.raises(ResourceDirectoryError) as err:
        s.check_resources()
    message = str(err.value)
    assert "sql_dir" in message and "skills_dir" in message
    assert "uv add --editable" in message


def test_resources_present_in_a_checkout(monkeypatch):
    """In this checkout the bundled directories exist and the check passes."""
    _clean(monkeypatch)
    Settings(_env_file=None).check_resources()
