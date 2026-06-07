"""Unit tests for the CLI scripts.

These tests exercise init_workspace.py, search_web.py (caching only), and
workspace_info.py against a temporary directory. Network-dependent code paths
(search provider calls) are not exercised here; those are validated end-to-end
in tests/golden/run.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


def run_script(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a Calixto script and return the completed process."""
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
    )


class TestInitWorkspace:
    def test_creates_workspace(self, tmp_path: Path) -> None:
        result = run_script(
            str(SCRIPTS_DIR / "init_workspace.py"),
            "my-test",
            "--path",
            str(tmp_path),
        )
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["status"] == "ok"
        assert (tmp_path / "my-test" / "config.json").exists()
        assert (tmp_path / "my-test" / "sources" / "index.json").exists()

    def test_rejects_invalid_name(self, tmp_path: Path) -> None:
        result = run_script(
            str(SCRIPTS_DIR / "init_workspace.py"),
            "InvalidName",
            "--path",
            str(tmp_path),
        )
        assert result.returncode == 1
        err = json.loads(result.stderr)
        assert err["status"] == "error"
        assert err["error"] == "invalid_name"

    def test_rejects_duplicate(self, tmp_path: Path) -> None:
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "dup", "--path", str(tmp_path))
        result = run_script(
            str(SCRIPTS_DIR / "init_workspace.py"),
            "dup",
            "--path",
            str(tmp_path),
        )
        assert result.returncode == 1
        err = json.loads(result.stderr)
        assert err["error"] == "workspace_exists"

    def test_config_has_required_keys(self, tmp_path: Path) -> None:
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "cfg-test", "--path", str(tmp_path))
        cfg = json.loads((tmp_path / "cfg-test" / "config.json").read_text())
        assert "name" in cfg
        assert cfg["name"] == "cfg-test"
        assert "scope" in cfg
        assert "providers" in cfg
        assert "next_source_id" in cfg
        assert "searches" in cfg
        assert "created_at" in cfg
        assert "updated_at" in cfg


class TestWorkspaceInfo:
    def _make_workspace(self, tmp_path: Path, name: str = "wi-test") -> Path:
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), name, "--path", str(tmp_path))
        return tmp_path / name

    def test_list_empty(self, tmp_path: Path) -> None:
        (tmp_path / "workspaces").mkdir()
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"), "list", "--path", str(tmp_path / "workspaces")
        )
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["status"] == "ok"
        assert out["count"] == 0

    def test_list_with_workspace(self, tmp_path: Path) -> None:
        self._make_workspace(tmp_path)
        (tmp_path / "workspaces").mkdir()
        # Use the parent that contains our test workspace
        # Simpler: pass tmp_path directly since init puts the ws at tmp_path/<name>
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"), "list", "--path", str(tmp_path)
        )
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["count"] == 1
        assert out["workspaces"][0]["name"] == "wi-test"

    def test_show(self, tmp_path: Path) -> None:
        self._make_workspace(tmp_path)
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "show",
            "wi-test",
            "--path",
            str(tmp_path),
        )
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["status"] == "ok"
        assert out["name"] == "wi-test"
        assert "source_counts" in out
        assert out["total_sources"] == 0

    def test_show_missing(self, tmp_path: Path) -> None:
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "show",
            "does-not-exist",
            "--path",
            str(tmp_path),
        )
        assert result.returncode == 1
        err = json.loads(result.stderr)
        assert err["error"] == "workspace_not_found"

    def test_audit_clean_workspace(self, tmp_path: Path) -> None:
        self._make_workspace(tmp_path)
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "audit",
            "wi-test",
            "--path",
            str(tmp_path),
        )
        assert result.returncode == 0
        out = json.loads(result.stdout)
        # A fresh workspace with no sources has no orphans or invalid refs
        assert out["status"] == "ok"
        assert out["sources_in_index"] == 0
        assert out["invalid_references"]["source_in_findings"] == []
        assert out["invalid_references"]["source_in_report"] == []
        assert out["id_counter_valid"] is True

    def test_delete_with_force(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, name="to-delete")
        assert ws.exists()
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "delete",
            "to-delete",
            "--path",
            str(tmp_path),
            "--force",
        )
        assert result.returncode == 0
        assert not ws.exists()


class TestSearchWebCaching:
    """Test that search_web.py respects --use-cache correctly.

    These tests use a known cache file to avoid hitting the network. They do
    not validate the network search itself (that is tested in the golden run).
    """

    def test_uses_cache_when_present(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # 1. Create a workspace
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "cache-test", "--path", str(tmp_path))
        ws = tmp_path / "cache-test"

        # 2. Write a fake cache file in the default cache dir for the test query
        import hashlib
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        provider = "duckduckgo"
        query = "unit test query"
        max_results = 2
        key = hashlib.sha256(f"{provider}|{query}|{max_results}".encode()).hexdigest()[:16]
        cache_file = cache_dir / provider / f"{key}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps(
                {
                    "provider": provider,
                    "query": query,
                    "max_results": max_results,
                    "results": [
                        {
                            "url": "https://example.com/cached",
                            "title": "Cached Title",
                            "snippet": "Cached snippet",
                            "score": 0.0,
                            "metadata": {},
                        }
                    ],
                }
            )
        )

        # 3. Run search_web.py with --use-cache and a custom cache dir
        result = run_script(
            str(SCRIPTS_DIR / "search_web.py"),
            query,
            "--workspace",
            str(ws),
            "--max-results",
            str(max_results),
            "--no-scrape",
            "--use-cache",
            "--cache-dir",
            str(cache_dir),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        out = json.loads(result.stdout)
        assert out["status"] == "ok"
        assert "src_001" in out["source_ids"]
        # The cached source should have been persisted
        assert (ws / "sources" / "web" / "src_001.md").exists()
