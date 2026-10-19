"""Runtime configuration and the canonical set of on-disk paths.

Pure: nothing here touches the network or the database. `Settings` is read once and
passed down, so no module reaches for the environment on its own.
"""

from __future__ import annotations

import os
from functools import cached_property, lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Repo root, resolved from this file's location: src/midden/config.py -> repo.
#: Under a non-editable install this lands in site-packages, where the bundled SQL,
#: sources and skills do not exist; `Settings.check_resources` says so rather than
#: letting a run fail deep inside.
REPO_ROOT = Path(__file__).resolve().parents[2]


class ResourceDirectoryError(RuntimeError):
    """A directory bundled with the repository is missing (non-editable install)."""


class Settings(BaseSettings):
    """Connection details and derived paths, read from the environment and `.env`."""

    # The .env location is chosen at construction in `settings()` (MIDDEN_ENV_FILE, then
    # MIDDEN_HOME/.env, then <repo>/.env), so importing this module reads nothing.
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    # Where the project's mutable state lives. Unset, everything stays under the repo,
    # exactly as before. MIDDEN_HOME relocates data/, scratch/ and exports/ together and
    # looks for .env there; the per-path variables below override it one at a time.
    midden_home: Path | None = None
    midden_data_dir: Path | None = None
    midden_scratch_dir: Path | None = None
    midden_exports_dir: Path | None = None

    postgres_user: str = "midden"
    postgres_password: str = ""
    postgres_db: str = "midden"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    midden_ro_user: str = "midden_ro"
    midden_ro_password: str = ""

    def dsn(self, *, read_only: bool = False) -> str:
        """Return a libpq connection string.

        `read_only=True` selects the midden_ro role, which has SELECT and nothing else.
        That role is what backs midden_sql and the mcp-postgis server.
        """
        user = self.midden_ro_user if read_only else self.postgres_user
        password = self.midden_ro_password if read_only else self.postgres_password
        return (
            f"postgresql://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def sqlalchemy_url(self, *, read_only: bool = False) -> str:
        """Return a SQLAlchemy URL pinned to the psycopg 3 dialect.

        SQLAlchemy's default driver for `postgresql://` is psycopg2, which is not
        installed and is not what this project uses. GeoPandas' `to_postgis` goes through
        SQLAlchemy, so the dialect has to be named explicitly.
        """
        return self.dsn(read_only=read_only).replace(
            "postgresql://", "postgresql+psycopg://", 1
        )

    # -- paths ---------------------------------------------------------------
    # Declared here so no other module hardcodes a directory layout.

    @cached_property
    def repo_root(self) -> Path:
        """Repository root."""
        return REPO_ROOT

    @cached_property
    def sql_dir(self) -> Path:
        """Numbered DDL files, applied in filename order."""
        return REPO_ROOT / "sql"

    @cached_property
    def sources_dir(self) -> Path:
        """Intake YAML, one per dataset (spec.md §5)."""
        return REPO_ROOT / "sources"

    @cached_property
    def semantic_dir(self) -> Path:
        """Boring-semantic-layer YAML, one per model (spec.md §5)."""
        return REPO_ROOT / "semantic"

    @cached_property
    def weights_dir(self) -> Path:
        """Weighted-overlay weight sets (spec.md §7)."""
        return REPO_ROOT / "weights"

    @cached_property
    def skills_dir(self) -> Path:
        """Bundled technique skills whose scripts midden imports rather than copies."""
        return REPO_ROOT / ".claude" / "skills"

    def _state_dir(self, override: Path | None, name: str) -> Path:
        """Resolve a mutable-state directory: per-path override, then MIDDEN_HOME, then repo."""
        if override is not None:
            return override.expanduser()
        if self.midden_home is not None:
            return self.midden_home.expanduser() / name
        return REPO_ROOT / name

    @cached_property
    def data_dir(self) -> Path:
        """Root of all generated data. Gitignored."""
        return self._state_dir(self.midden_data_dir, "data")

    @cached_property
    def exports_dir(self) -> Path:
        """Rendered artifacts, QGIS projects and previews. Gitignored."""
        return self._state_dir(self.midden_exports_dir, "exports")

    @cached_property
    def raw_dir(self) -> Path:
        """Cached source fetches, keyed by content hash."""
        return self.data_dir / "raw"

    @cached_property
    def cogs_dir(self) -> Path:
        """Derived rasters as Cloud-Optimized GeoTIFFs, per spec.md §4."""
        return self.data_dir / "cogs"

    @cached_property
    def parquet_dir(self) -> Path:
        """Feature stacks, read by DuckDB."""
        return self.data_dir / "parquet"

    @cached_property
    def scratch_dir(self) -> Path:
        """WhiteboxTools intermediates. Safe to delete; never an input to anything."""
        return self._state_dir(self.midden_scratch_dir, "scratch")

    def check_resources(self) -> None:
        """Raise `ResourceDirectoryError` if the bundled repo directories are absent.

        The SQL, intake sources, semantic models, weight sets and technique-skill scripts
        are read from the repository checkout, not packaged into the wheel. A normal
        (non-editable) install therefore points them into site-packages, where they do
        not exist, and the failure would otherwise surface halfway through a run.
        """
        missing = {
            name: path
            for name, path in (
                ("sql_dir", self.sql_dir),
                ("sources_dir", self.sources_dir),
                ("semantic_dir", self.semantic_dir),
                ("weights_dir", self.weights_dir),
                ("skills_dir", self.skills_dir),
            )
            if not path.is_dir()
        }
        if missing:
            listing = "\n".join(f"  {name}: {path}" for name, path in missing.items())
            raise ResourceDirectoryError(
                f"midden's bundled directories are missing:\n{listing}\n"
                f"midden reads these from its repository checkout and is not installable "
                f"as a plain wheel. Install it editable from a checkout instead, e.g. "
                f"`uv add --editable /path/to/open-paleo-discover` (or "
                f"`pip install -e`). Use MIDDEN_HOME to keep data/, scratch/, exports/ "
                f"and .env outside the checkout."
            )

    def aoi_cog_dir(self, slug: str) -> Path:
        """Return the COG directory for one AOI, per spec.md §4's path convention."""
        return self.cogs_dir / slug


def env_file_path() -> Path:
    """Locate the `.env` file: MIDDEN_ENV_FILE, then $MIDDEN_HOME/.env, then <repo>/.env."""
    explicit = os.environ.get("MIDDEN_ENV_FILE")
    if explicit:
        return Path(explicit).expanduser()
    home = os.environ.get("MIDDEN_HOME")
    if home:
        return Path(home).expanduser() / ".env"
    return REPO_ROOT / ".env"


@lru_cache(maxsize=1)
def settings() -> Settings:
    """Return the process-wide settings, read once.

    Fails with an actionable message if the repo's bundled directories are absent, rather
    than letting a non-editable install fail deep inside a run.
    """
    loaded = Settings(_env_file=env_file_path())
    loaded.check_resources()
    return loaded
