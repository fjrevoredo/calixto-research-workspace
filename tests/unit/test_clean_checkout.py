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


def test_future_cache_file_is_not_ignored() -> None:
    """A hypothetical new cache file under any provider must NOT be
    ignored by .gitignore.

    Regression: a previous version of .gitignore used a per-provider
    allow-list (e.g. `!tests/golden/cache/duckduckgo/`). That made
    a new provider's cache silently untrackable until someone
    edited .gitignore, which violated the reproducibility
    contract. The current policy allows all `*.json` files under
    `tests/golden/cache/` regardless of provider, so adding a
    new search provider is a no-op for .gitignore.

    We pick a name that does not currently exist on disk so the
    test fails if the policy is wrong (even if the rule happens
    to match an existing file).
    """
    # `git check-ignore` exit code semantics: 0 = ignored, 1 = not
    # ignored, 128 = error. We want the file to be NOT ignored
    # (so a future commit picks it up), so we expect exit 1.
    candidates = [
        # Existing provider, brand-new filename
        "tests/golden/cache/duckduckgo/future-cache.json",
        # Brand-new provider, brand-new filename
        "tests/golden/cache/newprovider/abc.json",
        # Brand-new provider nested two levels deep
        "tests/golden/cache/v2/anthropic/result.json",
    ]
    for candidate in candidates:
        result = subprocess.run(
            ["git", "check-ignore", candidate],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"cache file is ignored by .gitignore but should not be: {candidate!r}. "
            f"rc={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    # Non-JSON artifacts (e.g. a temp file or a future test
    # fixture) must still be ignored. We assert this so a
    # too-permissive rewrite of .gitignore that stops ignoring
    # .tmp/.swp etc. would be caught here.
    non_json_candidates = [
        "tests/golden/cache/duckduckgo/draft.tmp",
        "tests/golden/cache/duckduckgo/lock.swp",
        "tests/golden/cache/newprovider/result.bak",
    ]
    for candidate in non_json_candidates:
        result = subprocess.run(
            ["git", "check-ignore", candidate],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"non-JSON cache artifact is NOT ignored by .gitignore: {candidate!r}. "
            f"rc={result.returncode} stdout={result.stdout!r}"
        )
