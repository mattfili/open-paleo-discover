"""Shared fixtures. The database tests need a live Postgres; they skip without one."""

from __future__ import annotations

import pytest

from midden.config import settings
from midden.db import connect


@pytest.fixture(scope="session")
def db():
    """A connection to the project database, or skip if it is not up."""
    try:
        with connect(settings()) as conn:
            yield conn
    except Exception as exc:  # noqa: BLE001 - a missing database is a skip, not a failure
        pytest.skip(f"database unavailable ({type(exc).__name__}: {exc}). Run: docker compose up -d")
