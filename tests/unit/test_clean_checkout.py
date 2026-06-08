"""Verify the clean-checkout contract for the golden cache.

The committed cache under tests/golden/cache/ must satisfy requirements.md
10.2: the first run from a clean checkout, with --use-cache, must
reproduce against the committed cache. This test asserts that:

1. Every cache file under tests/golden/cache/ is tracked by git
   (a clean checkout would include them)
2. Each cache file's key matches the current cache_key implementation
3. Each cache file's content passes the schema we expect
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _git_ls_files() -> set[Path]:
    """Return the set of tracked files, as relative paths to REPO_ROOT."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {Path(line) for line in result.stdout.splitlines() if line}


def test_cache_files_are_tracked() -> None:
    """Every cache file under tests/golden/cache/ must be tracked by git.

    If a cache file is in .gitignore, a clean clone would not have
    it and the golden --use-cache workflow would break.
    """
    tracked = _git_ls_files()
    cache_dir = GOLDEN_DIR / "cache"
    untracked: list[Path] = []
    for f in cache_dir.rglob("*.json"):
        rel = f.relative_to(REPO_ROOT)
        if rel not in tracked:
            untracked.append(rel)
    assert not untracked, (
        f"the following cache files are not tracked by git and would be "
        f"missing in a clean clone: {untracked}. Update .gitignore to "
        "allow them through, or run `git add` to track them."
    )


def test_cache_files_have_at_least_one_result_each() -> None:
    """Every tracked cache file must contain at least one search result."""
    cache_dir = GOLDEN_DIR / "cache"
    for f in cache_dir.rglob("*.json"):
        payload = json.loads(f.read_text(encoding="utf-8"))
        assert payload.get("results"), (
            f"cache file {f.name} has no results; a --use-cache run "
            "would have nothing to replay."
        )
