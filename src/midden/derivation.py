"""The provenance ledger (spec.md §4).

Every derived artifact points at a `derived.derivation` row recording the operation, the
tool and its version, the parameters, the inputs, and the git SHA. CLAUDE.md: this "is what
makes a result reproducible six months later, and it is what turns 'should we use X or Y'
into a swept parameter rather than an argument."

A derivation is opened before the work and closed after, so a crash leaves a row with
status 'running' rather than no evidence that anything was attempted.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg

from midden.db import fetch_all

__all__ = ["cache_key", "git_sha", "open_derivation", "param_variant"]


def git_sha() -> str | None:
    """Return the current commit SHA, or None outside a repo / before the first commit."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def _canonical(payload: Any) -> str:
    """Return a stable JSON encoding, so equal inputs always hash equally."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def cache_key(driver: str, params: dict[str, Any], aoi_wkb: bytes | None) -> str:
    """Content hash of (driver, params, AOI geometry) — spec.md §5's idempotency rule.

    A re-run with unchanged inputs is a no-op. This matters more than it sounds: intake
    gets re-run dozens of times while tuning steps downstream of it.
    """
    digest = hashlib.sha256()
    digest.update(driver.encode())
    digest.update(_canonical(params).encode())
    if aoi_wkb is not None:
        digest.update(aoi_wkb)
    return digest.hexdigest()


def param_variant(params: dict[str, Any], length: int = 10) -> str:
    """Short digest of a parameter set, used as `raster_asset.variant`.

    A sweep writes several assets at the same (aoi, kind, resolution); this is what keeps
    them distinct and addressable by the parameters that produced them.
    """
    return hashlib.sha256(_canonical(params).encode()).hexdigest()[:length]


@contextmanager
def open_derivation(
    conn: psycopg.Connection,
    *,
    operation: str,
    tool: str,
    tool_version: str,
    aoi_id: int | None = None,
    params: dict[str, Any] | None = None,
    inputs: list[Any] | None = None,
    key: str | None = None,
) -> Iterator[int]:
    """Open a derivation row, yield its id, and close it as 'ok' or 'failed'.

    The row is committed before the work starts so that a process killed mid-derivation
    still leaves a 'running' row pointing at what was attempted and with which parameters.
    """
    row = fetch_all(
        conn,
        """
        INSERT INTO derived.derivation
            (aoi_id, operation, tool, tool_version, params, inputs, cache_key, git_sha, status)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, 'running')
        RETURNING id
        """,
        (aoi_id, operation, tool, tool_version,
         _canonical(params or {}), _canonical(inputs or []), key, git_sha()),
    )
    derivation_id = row[0]["id"]
    conn.commit()

    try:
        yield derivation_id
    except Exception as exc:
        conn.rollback()
        conn.execute(
            "UPDATE derived.derivation SET status='failed', finished_at=now(), error=%s "
            "WHERE id=%s",
            (f"{type(exc).__name__}: {exc}"[:4000], derivation_id),
        )
        conn.commit()
        raise
    conn.execute(
        "UPDATE derived.derivation SET status='ok', finished_at=now() WHERE id=%s",
        (derivation_id,),
    )
    conn.commit()
