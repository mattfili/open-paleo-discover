"""Runtime configuration and the canonical set of on-disk paths.

Pure: nothing here touches the network or the database. `Settings` is read once and
passed down, so no module reaches for the environment on its own.
"""

from __future__ import annotations

from functools import cached_property, lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Repo root, resolved from this file's location: src/midden/config.py -> repo.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Connection details and derived paths, read from the environment and `.env`."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

    @cached_property
    def data_dir(self) -> Path:
        """Root of all generated data. Gitignored."""
        return REPO_ROOT / "data"

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
        return REPO_ROOT / "scratch"

    def aoi_cog_dir(self, slug: str) -> Path:
        """Return the COG directory for one AOI, per spec.md §4's path convention."""
        return self.cogs_dir / slug


@lru_cache(maxsize=1)
def settings() -> Settings:
    """Return the process-wide settings, read once."""
    return Settings()
