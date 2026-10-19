"""Importing midden must be free of side effects (stabilization pass, section 4d).

A downstream project pins midden as a dependency. If merely importing it opened a database
connection, read `.env`, touched the network or downloaded the WhiteboxTools binary, that
project could not import it in CI, in a notebook, or on a machine with no Postgres. The
check runs in a fresh interpreter with an audit hook so the verdict does not depend on what
this test process already imported.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

_PROBE = textwrap.dedent(
    """
    import importlib, json, os, pkgutil, sys
    from pathlib import Path

    # midden's own .env locations: the repo default and the override sentinel. A bare
    # relative ".env" is fastmcp's own cwd lookup (pydantic-settings, at fastmcp import),
    # which midden cannot control, so it is not counted against midden.
    import midden.config as _config
    watched = {str(_config.REPO_ROOT / ".env"), os.environ["MIDDEN_ENV_FILE"]}

    events = []

    def hook(event, args):
        if event == "socket.connect" or event == "socket.getaddrinfo":
            events.append(f"network: {event} {args[1:] if event == 'socket.connect' else args[0]}")
        elif event == "open":
            target = str(args[0]) if args else ""
            if str(Path(target).resolve()) in {str(Path(w).resolve()) for w in watched}:
                events.append(f"env read: {target}")
            if "WBT/whitebox_tools" in target or target.endswith("whitebox_tools.zip"):
                events.append(f"whitebox binary: {target}")
        elif event == "subprocess.Popen":
            events.append(f"subprocess: {args[0]}")

    sys.addaudithook(hook)

    import midden
    failed = {}
    for mod in pkgutil.walk_packages(midden.__path__, "midden."):
        try:
            importlib.import_module(mod.name)
        except Exception as exc:  # an optional heavy dependency missing is reported, not hidden
            failed[mod.name] = f"{type(exc).__name__}: {exc}"
    print(json.dumps({"events": events, "failed": failed, "n": len(sys.modules)}))
    """
)


def test_import_has_no_side_effects(tmp_path):
    """Import every midden submodule with an audit hook: no network, .env read or subprocess."""
    # The sentinel must exist, or a premature settings() would skip it without opening it.
    sentinel = tmp_path / "sentinel.env"
    sentinel.write_text("POSTGRES_USER=sentinel\n")
    env = {**os.environ, "MIDDEN_ENV_FILE": str(sentinel)}
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE], capture_output=True, text=True, timeout=300,
        check=False, cwd=tmp_path, env=env,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    report = json.loads(proc.stdout.strip().splitlines()[-1])
    assert not report["failed"], f"modules failed to import: {report['failed']}"
    assert not report["events"], f"import-time side effects: {report['events']}"
