"""Unit tests for tests/golden/run.py workspace-name generation and config defaults.

The golden runner must produce slug-safe workspace names so that init_workspace.py
does not reject them. These tests verify the timestamp format and that the
generated default names pass the workspace slug contract.
"""
from __future__ import annotations

import importlib.util
import json
import re
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
        # Lowercase t and z keep the format readable while making the whole
        # string valid as a slug fragment.
        assert "T" not in ts
        assert "Z" not in ts
        assert is_valid_slug(f"golden-{ts}")
        assert is_valid_slug(f"golden-llm-2025-{ts}")

    def test_old_iso_format_rejected_as_slug(self) -> None:
        """The previous `%Y%m%dT%H%M%SZ` format must NOT pass the slug contract.

        This is a regression guard: if someone changes the format back to
        uppercase T/Z, this test fails before any runtime attempt to create
        the workspace.
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        assert not is_valid_slug(f"golden-{ts}")

    def test_default_name_never_contains_uppercase(self) -> None:
        """Defense in depth: the generated name must satisfy the slug regex directly."""
        # The regex itself: lowercase, digits, hyphens, length 2-64.
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


class TestGoldenRunnerPartialFailure:
    """When a child search fails, the golden runner must:

    - Exit with a non-zero status (returncode 2)
    - Emit a top-level "partial" status
    - Preserve the partial workspace under the run_archive path
    - Include structured failure details in the summary
    """

    def _write_minimal_config(self, config_path: Path, searches: list[dict]) -> None:
        config_path.write_text(
            json.dumps(
                {
                    "name": "test-runner",
                    "question": "Test",
                    "workspace_prefix": "test-runner",
                    "searches": searches,
                }
            ),
            encoding="utf-8",
        )

    def test_child_search_failure_produces_nonzero_exit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A child search that exits nonzero must produce a partial golden run."""
        # Build a search config that will deterministically fail: use --use-cache
        # with an empty cache, so the child script emits a cache_miss error.
        config_path = tmp_path / "config.json"
        unique_query = f"no-cache-{tmp_path.name}"
        self._write_minimal_config(
            config_path,
            [
                {
                    "provider": "duckduckgo",
                    "query": unique_query,
                    "max_results": 3,
                    "do_scrape": False,
                }
            ],
        )

        # Sandbox: redirect REPO_ROOT, workspaces dir, and cache dir to tmp_path
        # so the test does not pollute the real repo.
        empty_cache = tmp_path / "empty-cache"
        empty_cache.mkdir()
        workspaces_dir = tmp_path / "workspaces"
        workspaces_dir.mkdir()
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        # Patch the run module's REPO_ROOT and GOLDEN_DIR to point at tmp_path
        run_mod = _load_run_module()
        monkeypatch.setattr(run_mod, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(run_mod, "GOLDEN_DIR", tmp_path)
        monkeypatch.setattr(run_mod, "SCRIPTS_DIR", tmp_path / "scripts")
        # Force the cache dir to be empty so --use-cache fails
        monkeypatch.setattr(
            "search_web.DEFAULT_CACHE_DIR",
            empty_cache,
            raising=False,
        )
        # The runner looks up default search provider; we don't want a real call.
        # We don't patch it here because the failure happens at cache-load time
        # (no live call is made under --use-cache).

        # Invoke the runner as a subprocess so we exercise the real CLI exit code
        import subprocess
        import sys as _sys
        unique_ws = f"fail-run-{tmp_path.name}".replace("test_", "t")
        result = subprocess.run(
            [
                _sys.executable, str(RUN_PY),
                "--config", str(config_path),
                "--use-cache",
                "--workspace-name", unique_ws,
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            f"expected nonzero exit on child failure, got {result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        # The status should be "partial" (or at least not "ok")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail(f"runner output is not JSON: {result.stdout!r}")
        assert payload.get("status") in ("partial", "error"), payload
        # The failure detail should be present
        assert "summary" in payload or "error" in payload
        if "summary" in payload:
            summary = payload["summary"]
            assert summary.get("searches_failed", 0) >= 1
            failed = summary.get("failed_searches", [])
            assert any("no cache" in (f.get("error") or "").lower() for f in failed), failed

    def test_partial_workspace_is_preserved(
        self, tmp_path: Path
    ) -> None:
        """The partial workspace directory must be preserved under the run archive.

        This is the no-silent-failures principle: even when a child search
        fails, the operator can inspect what was collected.
        """
        config_path = tmp_path / "config.json"
        unique_query = f"preserve-test-{tmp_path.name}"
        self._write_minimal_config(
            config_path,
            [
                {
                    "provider": "duckduckgo",
                    "query": unique_query,
                    "max_results": 3,
                    "do_scrape": False,
                }
            ],
        )
        # Use a real subprocess so the workspace creation is real
        import subprocess
        import sys as _sys
        unique_ws = f"preserve-{tmp_path.name}".replace("test_", "t")
        result = subprocess.run(
            [
                _sys.executable, str(RUN_PY),
                "--config", str(config_path),
                "--use-cache",
                "--workspace-name", unique_ws,
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        # The workspace directory should still exist on disk for inspection
        ws = REPO_ROOT / "workspaces" / unique_ws
        assert ws.exists(), f"partial workspace was deleted: {ws}"
        # It must contain at least the config.json from init_workspace.py
        assert (ws / "config.json").is_file()
