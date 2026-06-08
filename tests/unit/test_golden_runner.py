"""Unit tests for tests/golden/run.py workspace-name generation and config defaults.

The golden runner must produce slug-safe workspace names so that init_workspace.py
does not reject them. These tests verify the timestamp format and that the
generated default names pass the workspace slug contract.

It also includes integration tests that exercise the golden runner end-to-end
against a temporary repository root. The temp root is fully isolated, so:
- the runner cannot pollute the real workspaces/ or tests/golden/runs/
- leftover artifacts from a previous run cannot break a new run
- cleanup is exact: the temp dir is removed when the test exits, no other
  files on the developer's machine are touched
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUN_PY = REPO_ROOT / "tests" / "golden" / "run.py"
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))
from _common import is_valid_slug  # noqa: E402

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


def _load_run_module() -> object:
    """Load tests/golden/run.py without executing its __main__ guard."""
    spec = importlib.util.spec_from_file_location("calixto_golden_run", RUN_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestGoldenTimestampSlug:
    """The golden runner's auto-generated workspace name must be a valid slug."""

    def test_default_timestamp_format_is_slug_safe(self) -> None:
        """The format `%Y%m%dt%H%M%Sz` uses lowercase t/z, both allowed by slug regex."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz")
        assert "T" not in ts
        assert "Z" not in ts
        assert is_valid_slug(f"golden-{ts}")
        assert is_valid_slug(f"golden-llm-2025-{ts}")

    def test_old_iso_format_rejected_as_slug(self) -> None:
        """The previous `%Y%m%dT%H%M%SZ` format must NOT pass the slug contract."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        assert not is_valid_slug(f"golden-{ts}")

    def test_default_name_never_contains_uppercase(self) -> None:
        for _ in range(20):
            ts = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz")
            name = f"golden-{ts}"
            assert _SLUG_RE.match(name), f"name {name!r} is not slug-safe"
            assert 2 <= len(name) <= 64


class TestRunModuleImports:
    """Smoke test: tests/golden/run.py must import without side effects."""

    def test_run_module_loads(self) -> None:
        module = _load_run_module()
        assert hasattr(module, "run_golden")
        assert hasattr(module, "main")


# ---------------------------------------------------------------------------
# Helpers for integration tests that need an isolated repo root.
# ---------------------------------------------------------------------------


def _build_isolated_repo(tmp_repo_root: Path) -> None:
    """Build a minimal copy of the toolkit under tmp_repo_root.

    The runner is invoked with cwd=tmp_repo_root, so its `REPO_ROOT` and
    `GOLDEN_DIR` resolve inside the temp dir. Any workspace or run
    archive the runner creates stays inside tmp_repo_root, and the
    developer's real workspaces/ and tests/golden/runs/ are never
    touched.
    """
    tmp_repo_root.mkdir(parents=True, exist_ok=True)
    # The runner imports from these locations relative to REPO_ROOT.
    # copytree(..., dirs_exist_ok=True) lets us re-run a partially
    # populated test without FileExistsError.
    for sub in ("scripts", "providers", "tests", "templates"):
        src = REPO_ROOT / sub
        if not src.exists():
            continue
        dst = tmp_repo_root / sub
        if dst.exists():
            # Refresh content from source. Useful for tests that
            # re-enter the same tmp_path fixture scope.
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)


class TestGoldenRunnerPartialFailure:
    """End-to-end tests for the partial-failure path, isolated to a temp
    repo root. The temp root is removed at the end of each test, so:

    - no leftover workspaces in the developer's real workspaces/
    - no leftover run archives in tests/golden/runs/
    - re-running the test does not depend on prior state
    """

    def _write_minimal_config(
        self, config_path: Path, searches: list[dict], workspace_prefix: str
    ) -> None:
        config_path.write_text(
            json.dumps(
                {
                    "name": "test-runner",
                    "question": "Test",
                    "workspace_prefix": workspace_prefix,
                    "searches": searches,
                }
            ),
            encoding="utf-8",
        )

    def _run_in_isolated_repo(
        self,
        tmp_path: Path,
        searches: list[dict],
        workspace_name: str,
    ) -> subprocess.CompletedProcess:
        """Build an isolated repo under tmp_path and run the golden runner there.

        Returns the subprocess.CompletedProcess for the runner. The
        workspace name must be a slug-safe string. The temp dir is
        removed by `_cleanup_isolated_repo` (or by pytest) regardless
        of pass/fail.

        The runner computes REPO_ROOT from CALIXTO_REPO_ROOT, so the
        isolated copy receives the workspaces/, run-archive writes,
        and cache reads.
        """
        isolated_repo = tmp_path / "repo"
        _build_isolated_repo(isolated_repo)
        config_path = tmp_path / "config.json"
        self._write_minimal_config(config_path, searches, workspace_prefix=workspace_name)
        env = {**os.environ, "CALIXTO_REPO_ROOT": str(isolated_repo)}
        return subprocess.run(
            [
                sys.executable, str(RUN_PY),
                "--config", str(config_path),
                "--use-cache",
                "--workspace-name", workspace_name,
            ],
            cwd=str(isolated_repo),
            env=env,
            capture_output=True,
            text=True,
        )

    def _cleanup_isolated_repo(self, tmp_path: Path) -> None:
        """Remove the isolated repo (workspace + run archive are inside)."""
        isolated_repo = tmp_path / "repo"
        if isolated_repo.exists():
            shutil.rmtree(isolated_repo, ignore_errors=True)
        # The config was also written into tmp_path; tmp_path is
        # managed by pytest and cleaned up automatically, but be
        # explicit so a failure here is visible.
        config = tmp_path / "config.json"
        if config.exists():
            config.unlink(missing_ok=True)

    def test_child_search_failure_produces_nonzero_exit(self, tmp_path: Path) -> None:
        """A child search that exits nonzero must produce a partial golden run.

        We force the failure deterministically by passing --use-cache
        with a query that has no cache entry. The child search_web.py
        emits a structured cache_miss error (exit 1). The runner must
        catch this as a child failure, archive the partial workspace,
        and exit 2 with a "partial" status on stdout.
        """
        import uuid
        ws_name = f"fail-partial-{uuid.uuid4().hex[:8]}"
        assert is_valid_slug(ws_name)
        # Use a query that is guaranteed to be absent from any committed cache.
        unique_query = f"unique-uncached-{uuid.uuid4().hex[:8]}"
        result = self._run_in_isolated_repo(
            tmp_path,
            [{"provider": "duckduckgo", "query": unique_query, "max_results": 3, "do_scrape": False}],
            workspace_name=ws_name,
        )
        try:
            assert result.returncode != 0, (
                f"expected nonzero exit on child failure, got {result.returncode}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )
            payload = json.loads(result.stdout)
            assert payload.get("status") == "partial", payload
            summary = payload.get("summary", {})
            assert summary.get("searches_failed", 0) >= 1, summary
            failed = summary.get("failed_searches", [])
            assert any("no cache" in (f.get("error") or "").lower() for f in failed), failed
        finally:
            self._cleanup_isolated_repo(tmp_path)

    def test_partial_workspace_is_preserved(self, tmp_path: Path) -> None:
        """The partial workspace directory must be preserved under the run archive.

        Even when a child search fails, the operator must be able to
        inspect what was collected. This is the no-silent-failures
        principle from PHILOSOPHY.md.
        """
        import uuid
        # Use a uuid-based workspace name so we don't depend on
        # tmp_path.name's slug-safety (pytest puts underscores in it).
        ws_name = f"fail-preserve-{uuid.uuid4().hex[:8]}"
        assert is_valid_slug(ws_name), ws_name
        unique_query = f"preserve-{ws_name}"
        isolated_repo = tmp_path / "repo"
        _build_isolated_repo(isolated_repo)
        env = {**os.environ, "CALIXTO_REPO_ROOT": str(isolated_repo)}
        try:
            config_path = tmp_path / "config.json"
            self._write_minimal_config(
                config_path,
                [{"provider": "duckduckgo", "query": unique_query, "max_results": 3, "do_scrape": False}],
                workspace_prefix=ws_name,
            )
            result = subprocess.run(
                [
                    sys.executable, str(RUN_PY),
                    "--config", str(config_path),
                    "--use-cache",
                    "--workspace-name", ws_name,
                ],
                cwd=str(isolated_repo),
                env=env,
                capture_output=True,
                text=True,
            )
            assert result.returncode != 0, (
                f"expected nonzero exit on child failure, got {result.returncode}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )
            # The workspace + run archive live inside the isolated
            # repo. The run archive is at tests/golden/runs/<ts>/. The
            # workspace is at workspaces/<name>/. Both must exist.
            ws = isolated_repo / "workspaces" / ws_name
            assert ws.exists(), f"partial workspace was not created: {ws}"
            assert (ws / "config.json").is_file()
            # The run archive is a directory whose name is a timestamp
            # we don't know in advance; we just assert at least one was
            # written.
            runs = isolated_repo / "tests" / "golden" / "runs"
            archived = [p for p in runs.iterdir() if p.is_dir()] if runs.exists() else []
            assert archived, f"no run archive was written under {runs}"
        finally:
            self._cleanup_isolated_repo(tmp_path)
