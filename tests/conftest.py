"""Shared pytest configuration for the unit test suite."""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_MARKER_COUNTS: Counter[str] = Counter()


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:
    if call.when != "setup" or call.excinfo is not None:
        return
    for marker in item.iter_markers():
        _MARKER_COUNTS[marker.name] += 1


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    raw = os.environ.get("CALIXTO_REQUIRED_MARKERS", "")
    required = [name.strip() for name in raw.split(",") if name.strip()]
    missing = [name for name in required if _MARKER_COUNTS.get(name, 0) == 0]
    if missing:
        session.exitstatus = 1
        terminal = session.config.pluginmanager.get_plugin("terminalreporter")
        if terminal is not None:
            terminal.write_line(
                "Required marked tests did not execute: " + ", ".join(sorted(missing)),
                red=True,
            )
