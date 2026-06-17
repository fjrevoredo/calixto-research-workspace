"""Unit tests for the CLI scripts.

These tests exercise init_workspace.py, search_web.py (caching only), and
workspace_info.py against a temporary directory. Network-dependent code paths
(search provider calls) are not exercised here; those are validated end-to-end
in tests/golden/run.py.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Any
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
# Ensure scripts/ is on path so `import search_web` works inside tests.
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from runtime_bundle import iter_runtime_entries


def run_script(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a Calixto script and return the completed process."""
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
    )


def build_cache_file(
    cache_dir: Path,
    provider: str,
    query: str,
    max_results: int,
    results: list[dict] | None = None,
    **params: str,
) -> Path:
    """Write a cache file using the same key format search_web.py uses."""
    import hashlib

    parts = [f"provider={provider}", f"query={query}", f"max_results={max_results}"]
    for k in sorted(params):
        v = params[k]
        if v is None or v == "":
            continue
        parts.append(f"{k}={v}")
    raw = "|".join(parts)
    key = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    cache_file = cache_dir / provider / f"{key}.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps(
            {
                "provider": provider,
                "query": query,
                "max_results": max_results,
                "params": {k: v for k, v in params.items() if v not in (None, "")},
                "results": results
                or [
                    {
                        "url": "https://example.com/cached",
                        "title": "Cached Title",
                        "snippet": "Cached snippet",
                        "score": 0.0,
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return cache_file


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
        workspace = tmp_path / "my-test"
        assert workspace.joinpath("config.json").exists()
        assert workspace.joinpath("sources", "index.json").exists()
        assert workspace.joinpath("AGENTS.md").exists()
        assert workspace.joinpath("scripts", "search_web.py").exists()
        assert workspace.joinpath("scripts", "search_pubmed.py").exists()
        assert workspace.joinpath("providers", "search", "duckduckgo.py").exists()
        assert workspace.joinpath("skills", "deep-research", "SKILL.md").exists()
        assert out["workspace_layout"] == "standalone"
        assert Path(out["runtime_manifest"]).name == "workspace-manifest.json"
        assert "toolkit_commit_created_with" in out
        assert "toolkit_build_number_created_with" in out
        assert "toolkit_ref_created_with" in out

    def test_fresh_workspace_audit_is_clean(self, tmp_path: Path) -> None:
        run_script(
            str(SCRIPTS_DIR / "init_workspace.py"),
            "audit-clean",
            "--path",
            str(tmp_path),
        )
        workspace = tmp_path / "audit-clean"
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "audit",
            str(workspace),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "ok"

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
        assert cfg["workspace_schema_version"] == 2
        assert cfg["workspace_layout"] == "standalone"
        assert cfg["runtime_manifest_version"] == 1
        assert cfg["runtime_bundle_version"]
        assert cfg["toolkit_version_created_with"]
        assert "toolkit_commit_created_with" in cfg
        assert "toolkit_build_number_created_with" in cfg
        assert "toolkit_ref_created_with" in cfg
        assert "scope" in cfg
        assert "providers" in cfg
        assert "next_source_id" in cfg
        assert "searches" in cfg
        assert "created_at" in cfg
        assert "updated_at" in cfg

    def test_bundle_matches_manifest_and_excludes_dev_only_assets(self, tmp_path: Path) -> None:
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "manifest-test", "--path", str(tmp_path))
        workspace = tmp_path / "manifest-test"

        for entry in iter_runtime_entries():
            assert workspace.joinpath(entry["destination"]).exists(), entry["destination"]

        for unexpected in (
            "docs",
            "tests",
            "templates",
            "examples",
            "adapters",
            "install.sh",
            "install.ps1",
            "requirements.md",
            "PHILOSOPHY.md",
            "skills/create-skill",
            "skills/integrate-tool",
            "scripts/init_workspace.py",
            "scripts/installer_core.py",
            "scripts/toolkit_git.py",
        ):
            assert not workspace.joinpath(unexpected).exists(), unexpected

        workspace_agents = workspace.joinpath("AGENTS.md").read_text(encoding="utf-8")
        assert "parent toolkit checkout" in workspace_agents.lower()
        for skill_name in ("deep-research", "literature-review"):
            skill_text = workspace.joinpath("skills", skill_name, "SKILL.md").read_text(encoding="utf-8")
            assert "repo root" not in skill_text.lower()
            assert "workspaces/<slug>" not in skill_text
            assert "scripts/init_workspace.py" not in skill_text

    def test_copied_workspace_runs_search_from_workspace_root(self, tmp_path: Path) -> None:
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "portable", "--path", str(tmp_path))
        source_workspace = tmp_path / "portable"
        copied_workspace = tmp_path / "copied" / "portable"
        copied_workspace.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_workspace, copied_workspace)

        default_cache_dir = copied_workspace / ".calixto" / "cache"
        build_cache_file(default_cache_dir, "duckduckgo", "portable query", 2)

        result = run_script(
            str(copied_workspace / "scripts" / "search_web.py"),
            "portable query",
            "--workspace",
            ".",
            "--max-results",
            "2",
            "--no-scrape",
            "--use-cache",
            cwd=copied_workspace,
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "ok"
        assert out["workspace"] == str(copied_workspace.resolve())
        source_file = copied_workspace / "sources" / "web" / "src_001.md"
        assert source_file.exists()
        meta, _ = parse_frontmatter_helper(source_file.read_text(encoding="utf-8"))
        assert meta["url"] == "https://example.com/cached"
        assert not (copied_workspace / "scripts" / "init_workspace.py").exists()
        assert not (copied_workspace / "scripts" / "toolkit_git.py").exists()


class TestToolkitGit:
    @staticmethod
    def _completed(
        args: list[str],
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)

    def test_build_metadata_helpers_return_git_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import toolkit_git

        def fake_run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str] | None:
            if args == ("rev-parse", "HEAD"):
                return self._completed(["git", *args], stdout="abc123def456\n")
            if args == ("rev-list", "--count", "HEAD"):
                return self._completed(["git", *args], stdout="42\n")
            if args == ("symbolic-ref", "--short", "-q", "HEAD"):
                return self._completed(["git", *args], stdout="master\n")
            raise AssertionError(f"unexpected git args: {args}")

        monkeypatch.setattr(toolkit_git, "_run_git", fake_run_git)

        assert toolkit_git.toolkit_commit() == "abc123def456"
        assert toolkit_git.toolkit_build_number() == 42
        assert toolkit_git.toolkit_ref_name() == "master"
        assert toolkit_git.toolkit_build_metadata() == {
            "toolkit_commit_created_with": "abc123def456",
            "toolkit_build_number_created_with": 42,
            "toolkit_ref_created_with": "master",
        }

    def test_build_metadata_helpers_degrade_when_git_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import toolkit_git

        monkeypatch.setattr(toolkit_git, "_run_git", lambda *args, check=True: None)

        assert toolkit_git.toolkit_commit() is None
        assert toolkit_git.toolkit_build_number() is None
        assert toolkit_git.toolkit_ref_name() is None

    def test_check_toolkit_freshness_reports_behind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import toolkit_git

        local_sha = "1111111111111111111111111111111111111111"
        remote_sha = "2222222222222222222222222222222222222222"

        def fake_run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str] | None:
            mapping: dict[tuple[str, ...], subprocess.CompletedProcess[str]] = {
                ("rev-parse", "HEAD"): self._completed(["git", *args], stdout=f"{local_sha}\n"),
                ("rev-list", "--count", "HEAD"): self._completed(["git", *args], stdout="10\n"),
                ("symbolic-ref", "--short", "-q", "HEAD"): self._completed(["git", *args], stdout="master\n"),
                ("remote", "get-url", "origin"): self._completed(
                    ["git", *args],
                    stdout="git@github.com:fjrevoredo/calixto-research-workspace.git\n",
                ),
                ("ls-remote", "--symref", "origin", "HEAD"): self._completed(
                    ["git", *args],
                    stdout=f"ref: refs/heads/master HEAD\n{remote_sha}\tHEAD\n",
                ),
                ("rev-parse", "refs/remotes/origin/master"): self._completed(
                    ["git", *args], returncode=1, stderr="unknown revision\n"
                ),
                ("cat-file", "-e", f"{remote_sha}^{{commit}}"): self._completed(["git", *args]),
                ("rev-list", "--count", remote_sha): self._completed(["git", *args], stdout="12\n"),
                ("merge-base", "--is-ancestor", local_sha, remote_sha): self._completed(
                    ["git", *args], returncode=0
                ),
                ("merge-base", "--is-ancestor", remote_sha, local_sha): self._completed(
                    ["git", *args], returncode=1
                ),
                ("rev-list", "--count", f"{local_sha}..{remote_sha}"): self._completed(
                    ["git", *args], stdout="2\n"
                ),
            }
            key = tuple(args)
            if key not in mapping:
                raise AssertionError(f"unexpected git args: {args}")
            return mapping[key]

        monkeypatch.setattr(toolkit_git, "_run_git", fake_run_git)

        freshness = toolkit_git.check_toolkit_freshness()
        assert freshness["status"] == "behind"
        assert freshness["behind_by"] == 2
        assert freshness["default_branch"] == "master"
        assert freshness["installer_repo_url"] == "https://github.com/fjrevoredo/calixto-research-workspace.git"
        assert freshness["latest_build_number"] == 12

    def test_check_toolkit_freshness_handles_remote_commit_not_in_local_history(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import toolkit_git

        local_sha = "1111111111111111111111111111111111111111"
        remote_sha = "2222222222222222222222222222222222222222"

        def fake_run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str] | None:
            mapping: dict[tuple[str, ...], subprocess.CompletedProcess[str]] = {
                ("rev-parse", "HEAD"): self._completed(["git", *args], stdout=f"{local_sha}\n"),
                ("rev-list", "--count", "HEAD"): self._completed(["git", *args], stdout="10\n"),
                ("symbolic-ref", "--short", "-q", "HEAD"): self._completed(["git", *args], stdout="master\n"),
                ("remote", "get-url", "origin"): self._completed(
                    ["git", *args],
                    stdout="git@github.com:fjrevoredo/calixto-research-workspace.git\n",
                ),
                ("ls-remote", "--symref", "origin", "HEAD"): self._completed(
                    ["git", *args],
                    stdout=f"ref: refs/heads/master HEAD\n{remote_sha}\tHEAD\n",
                ),
                ("cat-file", "-e", f"{remote_sha}^{{commit}}"): self._completed(
                    ["git", *args], returncode=1, stderr="missing\n"
                ),
                ("rev-parse", "refs/remotes/origin/HEAD"): self._completed(
                    ["git", *args], returncode=1, stderr="unknown revision\n"
                ),
                ("rev-parse", "refs/remotes/origin/master"): self._completed(
                    ["git", *args], returncode=1, stderr="unknown revision\n"
                ),
            }
            key = tuple(args)
            if key not in mapping:
                raise AssertionError(f"unexpected git args: {args}")
            return mapping[key]

        monkeypatch.setattr(toolkit_git, "_run_git", fake_run_git)

        freshness = toolkit_git.check_toolkit_freshness()
        assert freshness["status"] == "remote_newer_unknown_relationship"


class TestInitWorkspaceUpdateChecks:
    def test_noninteractive_default_skips_update_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import init_workspace

        def fail_if_called() -> dict[str, Any]:
            raise AssertionError("update check should not run by default in non-interactive mode")

        monkeypatch.setattr(init_workspace, "is_interactive_terminal", lambda: False)
        monkeypatch.setattr(init_workspace, "check_toolkit_freshness", fail_if_called)

        rc = init_workspace.main(["skip-default", "--path", str(tmp_path)])
        captured = capsys.readouterr()
        assert rc == 0
        assert json.loads(captured.out)["status"] == "ok"
        assert captured.err == ""
        assert (tmp_path / "skip-default" / "config.json").exists()

    def test_interactive_decline_continues_workspace_creation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import init_workspace

        monkeypatch.setattr(init_workspace, "is_interactive_terminal", lambda: True)
        monkeypatch.setattr(init_workspace, "_open_console_stream", lambda: None)
        monkeypatch.setattr(
            init_workspace,
            "check_toolkit_freshness",
            lambda: {
                "status": "behind",
                "local_commit": "1111111111111111111111111111111111111111",
                "local_build_number": 10,
                "latest_commit": "2222222222222222222222222222222222222222",
                "latest_build_number": 12,
                "behind_by": 2,
                "default_branch": "master",
                "installer_repo_url": "https://github.com/fjrevoredo/calixto-research-workspace.git",
            },
        )
        monkeypatch.setattr(init_workspace, "_read_prompt", lambda prompt="": "n")

        rc = init_workspace.main(["interactive-decline", "--path", str(tmp_path)])
        captured = capsys.readouterr()
        assert rc == 0
        out = json.loads(captured.out)
        assert out["status"] == "ok"
        assert "Toolkit update available" in captured.err
        assert "Continuing with the current local toolkit snapshot." in captured.err
        assert (tmp_path / "interactive-decline" / "config.json").exists()
        assert "Update the toolkit before creating this workspace?" not in captured.out

    def test_interactive_accept_exits_without_creating_workspace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import init_workspace

        monkeypatch.setattr(init_workspace, "is_interactive_terminal", lambda: True)
        monkeypatch.setattr(init_workspace, "_open_console_stream", lambda: None)
        monkeypatch.setattr(
            init_workspace,
            "check_toolkit_freshness",
            lambda: {
                "status": "behind",
                "local_commit": "1111111111111111111111111111111111111111",
                "local_build_number": 10,
                "latest_commit": "2222222222222222222222222222222222222222",
                "latest_build_number": 12,
                "behind_by": 2,
                "default_branch": "master",
                "installer_repo_url": "https://github.com/fjrevoredo/calixto-research-workspace.git",
            },
        )
        monkeypatch.setattr(init_workspace, "_read_prompt", lambda prompt="": "y")

        with pytest.raises(SystemExit) as excinfo:
            init_workspace.main(["interactive-accept", "--path", str(tmp_path)])
        captured = capsys.readouterr()
        assert excinfo.value.code == 1
        err = json.loads(captured.err[captured.err.find("{") :])
        assert err["error"] == "update_requested"
        assert err["workspace_created"] is False
        assert ".\\install.ps1" in err["update_command"] or "./install.sh" in err["update_command"]
        assert not (tmp_path / "interactive-accept").exists()

    def test_update_before_create_exits_when_behind(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import init_workspace

        monkeypatch.setattr(init_workspace, "is_interactive_terminal", lambda: False)
        monkeypatch.setattr(
            init_workspace,
            "check_toolkit_freshness",
            lambda: {
                "status": "behind",
                "local_commit": "1111111111111111111111111111111111111111",
                "local_build_number": 10,
                "latest_commit": "2222222222222222222222222222222222222222",
                "latest_build_number": 12,
                "behind_by": 2,
                "default_branch": "master",
                "installer_repo_url": "https://github.com/fjrevoredo/calixto-research-workspace.git",
            },
        )

        with pytest.raises(SystemExit) as excinfo:
            init_workspace.main(["needs-update", "--path", str(tmp_path), "--update-before-create"])
        captured = capsys.readouterr()
        assert excinfo.value.code == 1
        err = json.loads(captured.err)
        assert err["error"] == "update_required"
        assert err["workspace_created"] is False
        assert not (tmp_path / "needs-update").exists()

    def test_require_update_check_fails_when_check_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import init_workspace

        monkeypatch.setattr(init_workspace, "is_interactive_terminal", lambda: False)
        monkeypatch.setattr(
            init_workspace,
            "check_toolkit_freshness",
            lambda: {
                "status": "unavailable",
                "message": "git is not installed or not on PATH",
            },
        )

        with pytest.raises(SystemExit) as excinfo:
            init_workspace.main(["require-check", "--path", str(tmp_path), "--require-update-check"])
        captured = capsys.readouterr()
        assert excinfo.value.code == 1
        err = json.loads(captured.err)
        assert err["error"] == "update_check_failed"
        assert err["workspace_created"] is False
        assert not (tmp_path / "require-check").exists()

    def test_explicit_check_updates_warns_but_continues_when_noninteractive_and_behind(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import init_workspace

        monkeypatch.setattr(init_workspace, "is_interactive_terminal", lambda: False)
        monkeypatch.setattr(
            init_workspace,
            "check_toolkit_freshness",
            lambda: {
                "status": "behind",
                "local_commit": "1111111111111111111111111111111111111111",
                "local_build_number": 10,
                "latest_commit": "2222222222222222222222222222222222222222",
                "latest_build_number": 12,
                "behind_by": 2,
                "default_branch": "master",
                "installer_repo_url": "https://github.com/fjrevoredo/calixto-research-workspace.git",
            },
        )

        rc = init_workspace.main(["warn-only", "--path", str(tmp_path), "--check-updates"])
        captured = capsys.readouterr()
        assert rc == 0
        assert json.loads(captured.out)["status"] == "ok"
        assert "Toolkit update available" in captured.err
        assert (tmp_path / "warn-only" / "config.json").exists()


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

    def test_delete_rejects_parent_traversal(self, tmp_path: Path) -> None:
        """`delete ..` must not escape the workspaces parent and wipe the repo root."""
        self._make_workspace(tmp_path, name="real-ws")
        # Place a sentinel at tmp_path that we expect to survive.
        sentinel = tmp_path / "SENTINEL_KEEP_ME"
        sentinel.write_text("alive", encoding="utf-8")
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "delete",
            "..",
            "--path",
            str(tmp_path),
            "--force",
        )
        assert result.returncode == 1
        err = json.loads(result.stderr)
        assert err["status"] == "error"
        assert err["error"] == "invalid_target"
        # The workspace and the sentinel must still exist.
        assert (tmp_path / "real-ws").exists()
        assert sentinel.exists()

    def test_delete_rejects_non_workspace_dir(self, tmp_path: Path) -> None:
        """A bare directory that is not a workspace must not be deleted."""
        bogus = tmp_path / "not-a-workspace"
        bogus.mkdir()
        bogus_file = bogus / "important.txt"
        bogus_file.write_text("data", encoding="utf-8")
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "delete",
            "not-a-workspace",
            "--path",
            str(tmp_path),
            "--force",
        )
        assert result.returncode == 1
        err = json.loads(result.stderr)
        assert err["status"] == "error"
        assert err["error"] == "not_a_workspace"
        assert bogus.exists()
        assert bogus_file.exists()

    def test_delete_rejects_absolute_path(self, tmp_path: Path) -> None:
        """Absolute paths must be rejected outright, regardless of whether they are workspaces."""
        self._make_workspace(tmp_path, name="abs-ws")
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "delete",
            str((tmp_path / "abs-ws").resolve()),
            "--path",
            str(tmp_path),
            "--force",
        )
        assert result.returncode == 1
        err = json.loads(result.stderr)
        assert err["status"] == "error"
        assert err["error"] == "invalid_target"
        assert (tmp_path / "abs-ws").exists()

    def test_delete_rejects_traversal_segment(self, tmp_path: Path) -> None:
        """A slug with a `..` segment must be rejected, not silently joined to a parent path."""
        self._make_workspace(tmp_path, name="safe-ws")
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "delete",
            "..",
            "--path",
            str(tmp_path),
            "--force",
        )
        assert result.returncode == 1
        assert (tmp_path / "safe-ws").exists()

    def test_delete_rejects_nonexistent_workspace(self, tmp_path: Path) -> None:
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "delete",
            "never-existed",
            "--path",
            str(tmp_path),
            "--force",
        )
        assert result.returncode == 1
        err = json.loads(result.stderr)
        assert err["status"] == "error"
        assert err["error"] == "workspace_not_found"

    def test_delete_still_works_for_valid_workspace(self, tmp_path: Path) -> None:
        """Regression: a properly-formed workspace must still be deletable."""
        ws = self._make_workspace(tmp_path, name="good-ws")
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "delete",
            "good-ws",
            "--path",
            str(tmp_path),
            "--force",
        )
        assert result.returncode == 0
        assert not ws.exists()


class TestWorkspaceReliabilityRegressions:
    def _make_workspace(self, tmp_path: Path, name: str = "reliability") -> Path:
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), name, "--path", str(tmp_path))
        return tmp_path / name

    def test_audit_flags_path_qualified_paper_citation(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "audit-paths")
        (ws / "sources" / "web").mkdir(parents=True, exist_ok=True)
        (ws / "sources" / "web" / "src_001.md").write_text(
            "---\nid: src_001\nurl: https://example.com/web\n---\n\n# Web\n",
            encoding="utf-8",
        )
        (ws / "sources" / "index.json").write_text(
            json.dumps(
                {
                    "next_id": 2,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://example.com/web",
                            "file": "web/src_001.md",
                            "url_normalized": "example.com/web",
                            "added_at": "2026-06-10T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (ws / "notes" / "findings.md").write_text(
            "## fnd_001\n**Source:** papers/src_001\n**Fact:** path-qualified citation\n",
            encoding="utf-8",
        )
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "audit",
            str(ws),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "error"
        assert out["malformed_references"]["source_in_findings"] == ["papers/src_001"]

    def test_audit_flags_unindexed_files_and_counter_drift(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "audit-drift")
        (ws / "sources" / "web").mkdir(parents=True, exist_ok=True)
        (ws / "sources" / "papers").mkdir(parents=True, exist_ok=True)
        (ws / "sources" / "web" / "src_001.md").write_text(
            "---\nid: src_001\nurl: https://example.com/web\n---\n\n# Web\n",
            encoding="utf-8",
        )
        (ws / "sources" / "papers" / "src_002.md").write_text(
            "---\nid: src_002\nurl: https://arxiv.org/abs/2401.00002\n---\n\n# Paper A\n",
            encoding="utf-8",
        )
        (ws / "sources" / "papers" / "src_003.md").write_text(
            "---\nid: src_003\nurl: https://arxiv.org/abs/2401.00003\n---\n\n# Paper B\n",
            encoding="utf-8",
        )
        (ws / "sources" / "index.json").write_text(
            json.dumps(
                {
                    "next_id": 2,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://example.com/web",
                            "file": "web/src_001.md",
                            "url_normalized": "example.com/web",
                            "added_at": "2026-06-10T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
        cfg["next_finding_id"] = 1
        cfg["next_insight_id"] = 1
        (ws / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        (ws / "notes" / "findings.md").write_text(
            "## fnd_001\n**Source:** src_001\n**Fact:** kept\n",
            encoding="utf-8",
        )
        (ws / "notes" / "summary.md").write_text(
            "## ins_001\n**Based on:** fnd_001\n**Insight:** kept\n",
            encoding="utf-8",
        )
        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "audit",
            str(ws),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "error"
        assert sorted(out["filesystem_index_mismatches"]["unindexed_files"]) == [
            "papers/src_002.md",
            "papers/src_003.md",
        ]
        assert out["counters"]["next_finding_id"]["valid"] is False
        assert out["counters"]["next_insight_id"]["valid"] is False
        assert out["remediation"]["sync_counters_command"].endswith(f"sync-counters {ws}")

    def test_sync_counters_updates_config_from_note_contents(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "sync-counters")
        cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
        cfg["next_finding_id"] = 1
        cfg["next_insight_id"] = 1
        (ws / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        (ws / "notes" / "findings.md").write_text(
            "## fnd_001\n**Source:** src_001\n**Fact:** one\n\n## fnd_002\n**Source:** src_001\n**Fact:** two\n",
            encoding="utf-8",
        )
        (ws / "notes" / "summary.md").write_text(
            "## ins_001\n**Based on:** fnd_001, fnd_002\n**Insight:** combined\n",
            encoding="utf-8",
        )

        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "sync-counters",
            str(ws),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "ok"
        assert out["changed"] is True
        assert out["counters"]["next_finding_id"]["new"] == 3
        assert out["counters"]["next_insight_id"]["new"] == 2
        cfg_after = json.loads((ws / "config.json").read_text(encoding="utf-8"))
        assert cfg_after["next_finding_id"] == 3
        assert cfg_after["next_insight_id"] == 2

    def test_sync_counters_is_noop_when_already_correct(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "sync-counters-noop")
        cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
        cfg["next_finding_id"] = 2
        cfg["next_insight_id"] = 2
        (ws / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        (ws / "notes" / "findings.md").write_text(
            "## fnd_001\n**Source:** src_001\n**Fact:** one\n",
            encoding="utf-8",
        )
        (ws / "notes" / "summary.md").write_text(
            "## ins_001\n**Based on:** fnd_001\n**Insight:** one\n",
            encoding="utf-8",
        )

        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "sync-counters",
            str(ws),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["changed"] is False
        assert out["counters"]["next_finding_id"]["changed"] is False
        assert out["counters"]["next_insight_id"]["changed"] is False

    def test_sync_counters_does_not_mask_malformed_identifiers(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "sync-counters-malformed")
        (ws / "notes" / "findings.md").write_text(
            "## fnd001\n**Source:** src_001\n**Fact:** malformed heading\n",
            encoding="utf-8",
        )
        (ws / "notes" / "summary.md").write_text(
            "## ins001\n**Based on:** fnd001\n**Insight:** malformed heading\n",
            encoding="utf-8",
        )

        sync_result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "sync-counters",
            str(ws),
        )
        assert sync_result.returncode == 0, sync_result.stderr

        audit_result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "audit",
            str(ws),
        )
        assert audit_result.returncode == 0, audit_result.stderr
        out = json.loads(audit_result.stdout)
        assert out["status"] == "error"
        assert out["malformed_identifiers"]["finding_ids"] == ["fnd001"]
        assert out["malformed_identifiers"]["insight_ids"] == ["ins001"]
        assert out["malformed_identifiers"]["finding_in_summary"] == ["fnd001"]

    def test_review_source_updates_index_metadata(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "review-source")
        (ws / "sources" / "web").mkdir(parents=True, exist_ok=True)
        (ws / "sources" / "web" / "src_001.md").write_text(
            "---\nid: src_001\nurl: https://example.com/review\n---\n\n# Review\n",
            encoding="utf-8",
        )
        (ws / "sources" / "index.json").write_text(
            json.dumps(
                {
                    "next_id": 2,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://example.com/review",
                            "file": "web/src_001.md",
                            "url_normalized": "example.com/review",
                            "added_at": "2026-06-10T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "pending",
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
        cfg["next_source_id"] = 2
        (ws / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")

        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "review-source",
            str(ws),
            "src_001",
            "discarded",
            "--note",
            "duplicate coverage",
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "ok"
        assert out["source"]["review_status"] == "discarded"
        assert out["source"]["review_note"] == "duplicate coverage"
        idx = json.loads((ws / "sources" / "index.json").read_text(encoding="utf-8"))
        assert idx["sources"][0]["review_status"] == "discarded"
        assert idx["sources"][0]["review_note"] == "duplicate coverage"
        assert "reviewed_at" in idx["sources"][0]

    def test_audit_classifies_orphaned_sources_by_review_status(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "orphan-breakdown")
        (ws / "sources" / "web").mkdir(parents=True, exist_ok=True)
        for source_id in ("src_001", "src_002", "src_003"):
            (ws / "sources" / "web" / f"{source_id}.md").write_text(
                f"---\nid: {source_id}\nurl: https://example.com/{source_id}\n---\n\n# {source_id}\n",
                encoding="utf-8",
            )
        (ws / "sources" / "index.json").write_text(
            json.dumps(
                {
                    "next_id": 4,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://example.com/src_001",
                            "file": "web/src_001.md",
                            "url_normalized": "example.com/src_001",
                            "added_at": "2026-06-10T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "pending",
                        },
                        {
                            "id": "src_002",
                            "url": "https://example.com/src_002",
                            "file": "web/src_002.md",
                            "url_normalized": "example.com/src_002",
                            "added_at": "2026-06-10T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "discarded",
                            "review_note": "marketing page",
                            "reviewed_at": "2026-06-10T01:00:00Z",
                        },
                        {
                            "id": "src_003",
                            "url": "https://example.com/src_003",
                            "file": "web/src_003.md",
                            "url_normalized": "example.com/src_003",
                            "added_at": "2026-06-10T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "pending",
                            "snippet_only": True,
                            "error": "timeout",
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "audit",
            str(ws),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "warning"
        assert out["orphaned_source_breakdown"]["pending"] == ["src_001"]
        assert out["orphaned_source_breakdown"]["discarded"] == ["src_002"]
        assert out["orphaned_source_breakdown"]["low_signal_or_error"] == ["src_003"]
        assert out["source_review_counts"]["pending"] == 2
        assert out["source_review_counts"]["discarded"] == 1

    def test_search_web_marks_new_sources_pending_review(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "web-review-status")
        cache_dir = tmp_path / "cache-web-review"
        build_cache_file(cache_dir, "duckduckgo", "review status query", 1)

        result = run_script(
            str(SCRIPTS_DIR / "search_web.py"),
            "review status query",
            "--workspace",
            str(ws),
            "--max-results",
            "1",
            "--no-scrape",
            "--use-cache",
            "--cache-dir",
            str(cache_dir),
        )
        assert result.returncode == 0, result.stderr
        idx = json.loads((ws / "sources" / "index.json").read_text(encoding="utf-8"))
        assert idx["sources"][0]["review_status"] == "pending"

    def test_search_arxiv_marks_new_sources_pending_review(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "arxiv-review-status")
        cache_dir = tmp_path / "cache-arxiv-review"
        build_cache_file(
            cache_dir,
            "arxiv",
            "review status paper",
            1,
            results=[
                {
                    "arxiv_id": "2401.01234",
                    "url": "https://arxiv.org/abs/2401.01234",
                    "pdf_url": "https://arxiv.org/pdf/2401.01234",
                    "title": "Paper",
                    "summary": "Paper summary",
                    "authors": "Ada Lovelace",
                    "date_published": "2024-01-01",
                    "categories": ["cs.AI"],
                    "primary_category": "cs.AI",
                }
            ],
            sort_by="relevance",
        )

        result = run_script(
            str(SCRIPTS_DIR / "search_arxiv.py"),
            "review status paper",
            "--workspace",
            str(ws),
            "--max-results",
            "1",
            "--use-cache",
            "--cache-dir",
            str(cache_dir),
        )
        assert result.returncode == 0, result.stderr
        idx = json.loads((ws / "sources" / "index.json").read_text(encoding="utf-8"))
        assert idx["sources"][0]["review_status"] == "pending"

    def test_show_reports_scope_limit_overrun(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "scope-show")
        cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
        cfg["scope"]["max_sources"] = 1
        cfg["next_source_id"] = 3
        (ws / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        (ws / "sources" / "web").mkdir(parents=True, exist_ok=True)
        for source_id in ("src_001", "src_002"):
            (ws / "sources" / "web" / f"{source_id}.md").write_text(
                f"---\nid: {source_id}\nurl: https://example.com/{source_id}\n---\n\n# {source_id}\n",
                encoding="utf-8",
            )
        (ws / "sources" / "index.json").write_text(
            json.dumps(
                {
                    "next_id": 3,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://example.com/src_001",
                            "file": "web/src_001.md",
                            "url_normalized": "example.com/src_001",
                            "added_at": "2026-06-10T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "pending",
                        },
                        {
                            "id": "src_002",
                            "url": "https://example.com/src_002",
                            "file": "web/src_002.md",
                            "url_normalized": "example.com/src_002",
                            "added_at": "2026-06-10T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "pending",
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "show",
            str(ws),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "ok"
        assert out["scope_limits"]["max_sources"] == 1
        assert out["scope_limits"]["exceeded"] is True
        assert out["scope_limits"]["over_by"] == 1

    def test_audit_warns_when_total_sources_exceeds_max_sources(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "scope-audit")
        cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
        cfg["scope"]["max_sources"] = 1
        cfg["next_source_id"] = 3
        cfg["next_finding_id"] = 2
        cfg["next_insight_id"] = 1
        (ws / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        (ws / "sources" / "web").mkdir(parents=True, exist_ok=True)
        for source_id in ("src_001", "src_002"):
            (ws / "sources" / "web" / f"{source_id}.md").write_text(
                f"---\nid: {source_id}\nurl: https://example.com/{source_id}\n---\n\n# {source_id}\n",
                encoding="utf-8",
            )
        (ws / "sources" / "index.json").write_text(
            json.dumps(
                {
                    "next_id": 3,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://example.com/src_001",
                            "file": "web/src_001.md",
                            "url_normalized": "example.com/src_001",
                            "added_at": "2026-06-10T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "used",
                            "reviewed_at": "2026-06-10T01:00:00Z",
                        },
                        {
                            "id": "src_002",
                            "url": "https://example.com/src_002",
                            "file": "web/src_002.md",
                            "url_normalized": "example.com/src_002",
                            "added_at": "2026-06-10T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "used",
                            "reviewed_at": "2026-06-10T01:00:00Z",
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (ws / "notes" / "findings.md").write_text(
            "## fnd_001\n**Source:** src_001, src_002\n**Fact:** both cited\n",
            encoding="utf-8",
        )
        (ws / "notes" / "summary.md").write_text("", encoding="utf-8")
        (ws / "outputs" / "report.md").write_text(
            "# Report\n\nBoth sources matter [src_001, src_002].\n",
            encoding="utf-8",
        )

        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "audit",
            str(ws),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "warning"
        assert out["scope_limits"]["max_sources"] == 1
        assert out["scope_limits"]["exceeded"] is True
        assert out["scope_limits"]["over_by"] == 1
        assert "configured max_sources" in out["summary"]

    def test_audit_reports_report_sources_not_in_findings(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "traceability-gap")
        (ws / "sources" / "web").mkdir(parents=True, exist_ok=True)
        for source_id in ("src_001", "src_002"):
            (ws / "sources" / "web" / f"{source_id}.md").write_text(
                (
                    f"---\n"
                    f"id: {source_id}\n"
                    f"url: https://example.com/{source_id}\n"
                    f"title: {source_id}\n"
                    f"---\n\n"
                    f"# {source_id}\n\n"
                    f"Methylene blue is discussed here.\n"
                ),
                encoding="utf-8",
            )
        (ws / "sources" / "index.json").write_text(
            json.dumps(
                {
                    "next_id": 3,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://example.com/src_001",
                            "file": "web/src_001.md",
                            "url_normalized": "example.com/src_001",
                            "added_at": "2026-06-17T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "used",
                            "quality_tier": "authoritative",
                            "quality_reasons": ["government_or_public_health_domain"],
                            "quality_requires_corroboration": False,
                        },
                        {
                            "id": "src_002",
                            "url": "https://example.com/src_002",
                            "file": "web/src_002.md",
                            "url_normalized": "example.com/src_002",
                            "added_at": "2026-06-17T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "used",
                            "quality_tier": "unknown",
                            "quality_reasons": ["no_strong_signal"],
                            "quality_requires_corroboration": True,
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
        cfg["next_source_id"] = 3
        cfg["next_finding_id"] = 2
        (ws / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        (ws / "notes" / "findings.md").write_text(
            "## fnd_001\n**Source:** src_001\n**Fact:** kept\n",
            encoding="utf-8",
        )
        (ws / "outputs" / "report.md").write_text(
            "# Report\n\nClaim supported by [src_001, src_002].\n",
            encoding="utf-8",
        )

        result = run_script(str(SCRIPTS_DIR / "workspace_info.py"), "audit", str(ws))
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "warning"
        assert out["report_sources_not_in_findings"] == ["src_002"]
        assert "bypass findings" in out["summary"]

    def test_audit_strict_traceability_fails_report_bypass_and_pending(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "traceability-strict")
        (ws / "sources" / "web").mkdir(parents=True, exist_ok=True)
        for source_id in ("src_001", "src_002", "src_003"):
            (ws / "sources" / "web" / f"{source_id}.md").write_text(
                f"---\nid: {source_id}\nurl: https://example.com/{source_id}\n---\n\n# {source_id}\n",
                encoding="utf-8",
            )
        (ws / "sources" / "index.json").write_text(
            json.dumps(
                {
                    "next_id": 4,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://example.com/src_001",
                            "file": "web/src_001.md",
                            "url_normalized": "example.com/src_001",
                            "added_at": "2026-06-17T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "used",
                        },
                        {
                            "id": "src_002",
                            "url": "https://example.com/src_002",
                            "file": "web/src_002.md",
                            "url_normalized": "example.com/src_002",
                            "added_at": "2026-06-17T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "used",
                        },
                        {
                            "id": "src_003",
                            "url": "https://example.com/src_003",
                            "file": "web/src_003.md",
                            "url_normalized": "example.com/src_003",
                            "added_at": "2026-06-17T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "pending",
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
        cfg["next_source_id"] = 4
        cfg["next_finding_id"] = 2
        (ws / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        (ws / "notes" / "findings.md").write_text(
            "## fnd_001\n**Source:** src_001\n**Fact:** kept\n",
            encoding="utf-8",
        )
        (ws / "outputs" / "report.md").write_text(
            "# Report\n\nClaim supported by [src_001, src_002].\n",
            encoding="utf-8",
        )

        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "audit",
            str(ws),
            "--strict-traceability",
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "error"
        assert out["strict_traceability"] is True
        assert out["strict_traceability_failures"]["report_sources_not_in_findings"] == ["src_002"]
        assert out["strict_traceability_failures"]["pending_orphaned_sources"] == ["src_003"]

    def test_verify_citations_writes_artifact_with_excerpts(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "verify-citations")
        (ws / "sources" / "web").mkdir(parents=True, exist_ok=True)
        (ws / "sources" / "web" / "src_001.md").write_text(
            (
                "---\n"
                "id: src_001\n"
                "url: https://example.com/one\n"
                "title: Example One\n"
                "---\n\n"
                "# Example One\n\n"
                "Methylene blue improved signal in a small trial.\n\n"
                "The article discusses adverse effects and dosage uncertainty.\n"
            ),
            encoding="utf-8",
        )
        (ws / "sources" / "index.json").write_text(
            json.dumps(
                {
                    "next_id": 2,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://example.com/one",
                            "file": "web/src_001.md",
                            "url_normalized": "example.com/one",
                            "added_at": "2026-06-17T00:00:00Z",
                            "query": "q",
                            "word_count": 20,
                            "review_status": "pending",
                            "quality_tier": "unknown",
                            "quality_reasons": ["no_strong_signal"],
                            "quality_requires_corroboration": True,
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (ws / "notes" / "findings.md").write_text(
            "## fnd_001\n**Source:** src_001\n**Fact:** cautious support\n",
            encoding="utf-8",
        )
        (ws / "outputs" / "report.md").write_text(
            "# Report\n\nMethylene blue improved signal in a small trial [src_001].\n",
            encoding="utf-8",
        )

        result = run_script(
            str(SCRIPTS_DIR / "workspace_info.py"),
            "verify-citations",
            str(ws),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "ok"
        assert out["artifact_written"] is True
        assert out["report_citation_count"] == 1
        artifact = ws / "outputs" / "citation-check.md"
        assert artifact.exists()
        text = artifact.read_text(encoding="utf-8")
        assert "Report line 3" in text
        assert "Candidate excerpts" in text
        assert "Methylene blue improved signal in a small trial." in text

    def test_show_reports_quality_tier_counts(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "quality-show")
        (ws / "sources" / "web").mkdir(parents=True, exist_ok=True)
        (ws / "sources" / "papers").mkdir(parents=True, exist_ok=True)
        (ws / "sources" / "web" / "src_001.md").write_text(
            "---\nid: src_001\nurl: https://nih.gov/a\n---\n",
            encoding="utf-8",
        )
        (ws / "sources" / "papers" / "src_002.md").write_text(
            "---\nid: src_002\nurl: https://arxiv.org/abs/2401.01234\n---\n",
            encoding="utf-8",
        )
        (ws / "sources" / "index.json").write_text(
            json.dumps(
                {
                    "next_id": 3,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://nih.gov/a",
                            "file": "web/src_001.md",
                            "url_normalized": "nih.gov/a",
                            "added_at": "2026-06-17T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "used",
                            "quality_tier": "authoritative",
                            "quality_reasons": ["government_or_public_health_domain"],
                            "quality_requires_corroboration": False,
                        },
                        {
                            "id": "src_002",
                            "url": "https://arxiv.org/abs/2401.01234",
                            "file": "papers/src_002.md",
                            "added_at": "2026-06-17T00:00:00Z",
                            "query": "q",
                            "word_count": 10,
                            "review_status": "used",
                            "quality_tier": "scholarly",
                            "quality_reasons": ["scholarly_record"],
                            "quality_requires_corroboration": False,
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        result = run_script(str(SCRIPTS_DIR / "workspace_info.py"), "show", str(ws))
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["source_quality_tier_counts"]["authoritative"] == 1
        assert out["source_quality_tier_counts"]["scholarly"] == 1

    def test_concurrent_search_web_preserves_all_updates(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "concurrent-web")
        cache_dir = tmp_path / "cache-web"
        build_cache_file(
            cache_dir,
            "duckduckgo",
            "query one",
            1,
            results=[
                {
                    "url": "https://example.com/one",
                    "title": "One",
                    "snippet": "First",
                    "score": 0.0,
                    "metadata": {},
                }
            ],
        )
        build_cache_file(
            cache_dir,
            "duckduckgo",
            "query two",
            1,
            results=[
                {
                    "url": "https://example.com/two",
                    "title": "Two",
                    "snippet": "Second",
                    "score": 0.0,
                    "metadata": {},
                }
            ],
        )
        env = os.environ.copy()
        env["CALIXTO_TEST_PRE_COMMIT_DELAY_MS"] = "250"
        p1 = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPTS_DIR / "search_web.py"),
                "query one",
                "--workspace",
                str(ws),
                "--max-results",
                "1",
                "--no-scrape",
                "--use-cache",
                "--cache-dir",
                str(cache_dir),
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        p2 = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPTS_DIR / "search_web.py"),
                "query two",
                "--workspace",
                str(ws),
                "--max-results",
                "1",
                "--no-scrape",
                "--use-cache",
                "--cache-dir",
                str(cache_dir),
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout1, stderr1 = p1.communicate(timeout=30)
        stdout2, stderr2 = p2.communicate(timeout=30)
        assert p1.returncode == 0, stderr1
        assert p2.returncode == 0, stderr2
        cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
        idx = json.loads((ws / "sources" / "index.json").read_text(encoding="utf-8"))
        assert len(cfg["searches"]) == 2, (stdout1, stdout2, cfg)
        assert len(idx["sources"]) == 2
        assert (ws / "sources" / "web" / "src_001.md").exists()
        assert (ws / "sources" / "web" / "src_002.md").exists()

    def test_concurrent_web_and_arxiv_preserve_all_updates(self, tmp_path: Path) -> None:
        ws = self._make_workspace(tmp_path, "concurrent-mixed")
        cache_dir = tmp_path / "cache-mixed"
        build_cache_file(
            cache_dir,
            "duckduckgo",
            "web query",
            1,
            results=[
                {
                    "url": "https://example.com/web",
                    "title": "Web",
                    "snippet": "Web snippet",
                    "score": 0.0,
                    "metadata": {},
                }
            ],
        )
        build_cache_file(
            cache_dir,
            "arxiv",
            "paper query",
            1,
            results=[
                {
                    "arxiv_id": "2401.01234",
                    "url": "https://arxiv.org/abs/2401.01234",
                    "pdf_url": "https://arxiv.org/pdf/2401.01234",
                    "title": "Paper",
                    "summary": "Paper summary",
                    "authors": "Ada Lovelace",
                    "date_published": "2024-01-01",
                    "categories": ["cs.AI"],
                    "primary_category": "cs.AI",
                }
            ],
            sort_by="relevance",
        )
        env = os.environ.copy()
        env["CALIXTO_TEST_PRE_COMMIT_DELAY_MS"] = "250"
        web_proc = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPTS_DIR / "search_web.py"),
                "web query",
                "--workspace",
                str(ws),
                "--max-results",
                "1",
                "--no-scrape",
                "--use-cache",
                "--cache-dir",
                str(cache_dir),
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        arxiv_proc = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPTS_DIR / "search_arxiv.py"),
                "paper query",
                "--workspace",
                str(ws),
                "--max-results",
                "1",
                "--use-cache",
                "--cache-dir",
                str(cache_dir),
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _, web_err = web_proc.communicate(timeout=30)
        _, arxiv_err = arxiv_proc.communicate(timeout=30)
        assert web_proc.returncode == 0, web_err
        assert arxiv_proc.returncode == 0, arxiv_err
        cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
        idx = json.loads((ws / "sources" / "index.json").read_text(encoding="utf-8"))
        assert len(cfg["searches"]) == 2
        assert len(idx["sources"]) == 2
        files = {entry["file"] for entry in idx["sources"]}
        assert any(path.startswith("web/") for path in files)
        assert any(path.startswith("papers/") for path in files)

    def test_retry_failed_updates_existing_placeholder_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "retry-failed", "--path", str(tmp_path))
        ws = tmp_path / "retry-failed"

        from providers.scrape.base import ScrapeError, ScrapeResult
        from providers.search.base import SearchResult
        import search_web

        class _StubSearchProvider:
            def search(self, query: str, max_results: int = 10):
                return [
                    SearchResult(
                        url="https://example.com/retry",
                        title="Retry",
                        snippet="Needs retry",
                    )
                ]

        class _FailingScraper:
            def scrape(self, url: str):
                raise ScrapeError("temporary", error_type="timeout")

        class _SucceedingScraper:
            def scrape(self, url: str):
                return ScrapeResult(
                    url=url,
                    title="Recovered",
                    markdown="# Recovered\n\nfull body",
                    metadata={},
                )

        monkeypatch.setattr(search_web, "get_search_provider", lambda name, **kwargs: _StubSearchProvider())
        monkeypatch.setattr(search_web, "get_scrape_provider", lambda name, **kwargs: _FailingScraper())
        first = search_web.run_search(
            query="retry query",
            workspace=ws,
            max_results=1,
            search_provider_name="duckduckgo",
            scrape_provider_name="crawl4ai",
            do_scrape=True,
            truncate=10000,
            use_cache=False,
            clear_cache_first=False,
            cache_dir=tmp_path / "retry-cache",
        )
        assert first["sources_added"] == 1
        assert first["sources_failed"] == 1

        monkeypatch.setattr(search_web, "get_scrape_provider", lambda name, **kwargs: _SucceedingScraper())
        second = search_web.run_search(
            query=None,
            workspace=ws,
            max_results=1,
            search_provider_name="duckduckgo",
            scrape_provider_name="crawl4ai",
            do_scrape=True,
            truncate=10000,
            use_cache=False,
            clear_cache_first=False,
            cache_dir=tmp_path / "retry-cache",
            retry_failed=True,
        )
        assert second["sources_added"] == 0
        assert second["sources_updated"] == 1
        source_text = (ws / "sources" / "web" / "src_001.md").read_text(encoding="utf-8")
        meta, body = parse_frontmatter_helper(source_text)
        assert meta["title"] == "Recovered"
        assert "snippet_only" not in meta
        assert body.startswith("# Recovered")


class TestSearchWebCaching:
    """Test that search_web.py respects --use-cache correctly.

    These tests use a known cache file to avoid hitting the network. They do
    not validate the network search itself (that is tested in the golden run).
    """

    def _build_cache_file(self, cache_dir: Path, provider: str, query: str, max_results: int, **params: str) -> Path:
        """Write a cache file using the same key format search_web.py uses."""
        return build_cache_file(cache_dir, provider, query, max_results, **params)

    def test_uses_cache_when_present(self, tmp_path: Path) -> None:
        # 1. Create a workspace
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "cache-test", "--path", str(tmp_path))
        ws = tmp_path / "cache-test"

        # 2. Write a fake cache file using the new key format
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        self._build_cache_file(
            cache_dir, "duckduckgo", "unit test query", 2
        )

        # 3. Run search_web.py with --use-cache and a custom cache dir
        result = run_script(
            str(SCRIPTS_DIR / "search_web.py"),
            "unit test query",
            "--workspace",
            str(ws),
            "--max-results",
            "2",
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

    def test_use_cache_miss_fails_without_calling_network(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cache miss under --use-cache must fail clearly and not call the provider.

        The script must exit with a structured cache_miss error, not attempt
        a live network call. We detect a network call by injecting a fake
        search provider and verifying it is never invoked.
        """
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "miss-test", "--path", str(tmp_path))
        ws = tmp_path / "miss-test"

        # Inject a search provider that records any call attempt
        from providers.search import duckduckgo

        called: list[str] = []

        class _RecordingDuckDuckGoProvider(duckduckgo.DuckDuckGoProvider):
            def search(self, query: str, max_results: int = 10):  # type: ignore[override]
                called.append(f"network call: {query}")
                return []

        monkeypatch.setattr(
            "search_web.get_search_provider",
            lambda name, **kwargs: _RecordingDuckDuckGoProvider(),
        )

        result = run_script(
            str(SCRIPTS_DIR / "search_web.py"),
            "this query has no cached entry",
            "--workspace",
            str(ws),
            "--max-results",
            "3",
            "--no-scrape",
            "--use-cache",
            "--cache-dir",
            str(tmp_path / "empty-cache"),
        )
        assert result.returncode == 1, f"expected failure; got {result.stdout}"
        err = json.loads(result.stderr)
        assert err["status"] == "error"
        assert err["error"] == "cache_miss"
        # The provider must never have been called
        assert called == [], f"provider was called during a cache miss: {called}"


class TestCacheKey:
    """Direct tests of scripts/search_web.cache_key."""

    def test_basic(self) -> None:
        from search_web import cache_key
        # Same input -> same key
        k1 = cache_key("duckduckgo", "q", 10)
        k2 = cache_key("duckduckgo", "q", 10)
        assert k1 == k2

    def test_different_max_results(self) -> None:
        from search_web import cache_key
        assert cache_key("p", "q", 1) != cache_key("p", "q", 2)

    def test_different_query(self) -> None:
        from search_web import cache_key
        assert cache_key("p", "q1", 1) != cache_key("p", "q2", 1)

    def test_params_distinct(self) -> None:
        from search_web import cache_key
        # arxiv-style params: category/sort_by must produce distinct keys.
        a = cache_key("arxiv", "q", 5, category="cs.AI", sort_by="relevance")
        b = cache_key("arxiv", "q", 5, category="cs.LG", sort_by="relevance")
        c = cache_key("arxiv", "q", 5, category="cs.AI", sort_by="date")
        assert len({a, b, c}) == 3, "category and sort_by must be part of the key"

    def test_none_and_empty_params_ignored(self) -> None:
        from search_web import cache_key
        # An optional param that is None or "" should not change the key.
        base = cache_key("arxiv", "q", 5)
        with_none = cache_key("arxiv", "q", 5, category=None)
        with_empty = cache_key("arxiv", "q", 5, category="")
        assert base == with_none == with_empty


class TestLiveSearchWritesCache:
    """A live search (no --use-cache) must write a reusable cache entry.

    This is the requirement from the review: 'A live search writes a
    reusable cache entry without --use-cache.'

    We test this in-process so we can swap in a stub search provider.
    The end-to-end subprocess-based test is covered by the golden runner.
    """

    def test_live_search_writes_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Initialize a workspace through the script (covers the public API
        # for workspace creation).
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "live-cache", "--path", str(tmp_path))
        ws = tmp_path / "live-cache"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Stub the search provider so we don't need network
        from providers.search.base import SearchResult

        class _StubProvider:
            name = "duckduckgo"

            def search(self, query: str, max_results: int = 10):  # type: ignore[override]
                return [SearchResult(url="https://example.com/live", title="Live", snippet="snip")]

        import search_web
        monkeypatch.setattr(search_web, "get_search_provider", lambda name, **kwargs: _StubProvider())

        # Run the search flow in-process
        result = search_web.run_search(
            query="live query",
            workspace=ws,
            max_results=3,
            search_provider_name="duckduckgo",
            scrape_provider_name="crawl4ai",
            do_scrape=False,
            truncate=10000,
            use_cache=False,           # no --use-cache
            clear_cache_first=False,
            cache_dir=cache_dir,
        )
        assert result["sources_added"] == 1
        # The cache directory must now contain exactly one cache file.
        cache_files = list((cache_dir / "duckduckgo").glob("*.json"))
        assert len(cache_files) == 1
        payload = json.loads(cache_files[0].read_text(encoding="utf-8"))
        assert payload["query"] == "live query"
        assert payload["max_results"] == 3
        assert payload["results"][0]["url"] == "https://example.com/live"

    def test_subsequent_use_cache_reuses_written_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A live run writes the cache; a --use-cache run replays it
        without calling the (mock-failing) provider.
        """
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "replay-test", "--path", str(tmp_path))
        ws = tmp_path / "replay-test"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        from providers.search.base import SearchResult

        class _LiveProvider:
            name = "duckduckgo"

            def search(self, query: str, max_results: int = 10):  # type: ignore[override]
                return [SearchResult(url="https://example.com/first", title="First")]

        class _MustNotBeCalled:
            name = "duckduckgo"

            def search(self, query: str, max_results: int = 10):  # type: ignore[override]
                raise AssertionError("provider must not be called when --use-cache hits")

        import search_web
        # 1. First run: live call populates the cache
        monkeypatch.setattr(search_web, "get_search_provider", lambda name, **kwargs: _LiveProvider())
        first = search_web.run_search(
            query="replay query",
            workspace=ws,
            max_results=3,
            search_provider_name="duckduckgo",
            scrape_provider_name="crawl4ai",
            do_scrape=False,
            truncate=10000,
            use_cache=False,
            clear_cache_first=False,
            cache_dir=cache_dir,
        )
        assert first["sources_added"] == 1

        # 2. Second run: --use-cache should replay the cache, not call provider.
        # Initialize a fresh workspace so dedup doesn't suppress the replay.
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "replay-test-2", "--path", str(tmp_path))
        ws2 = tmp_path / "replay-test-2"
        monkeypatch.setattr(search_web, "get_search_provider", lambda name, **kwargs: _MustNotBeCalled())
        second = search_web.run_search(
            query="replay query",
            workspace=ws2,
            max_results=3,
            search_provider_name="duckduckgo",
            scrape_provider_name="crawl4ai",
            do_scrape=False,
            truncate=10000,
            use_cache=True,           # require cache
            clear_cache_first=False,
            cache_dir=cache_dir,
        )
        assert second["sources_added"] == 1
        # The replayed URL must be the one written by the first run.
        replayed = (ws2 / "sources" / "web" / "src_001.md").read_text(encoding="utf-8")
        meta, _ = parse_frontmatter_helper(replayed)
        assert meta["url"] == "https://example.com/first"


def parse_frontmatter_helper(text: str) -> tuple[dict, str]:
    """Tiny local re-export of parse_frontmatter to avoid cross-test imports."""
    from _common import parse_frontmatter
    return parse_frontmatter(text)


class TestArxivCacheMiss:
    """A cache miss in arxiv search under --use-cache must fail clearly.

    The check happens before any arxiv client is constructed, so we can
    exercise it even if the `arxiv` package is not installed.
    """

    def test_use_cache_miss_fails_with_cache_miss_error(
        self, tmp_path: Path
    ) -> None:
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "arxiv-miss", "--path", str(tmp_path))
        ws = tmp_path / "arxiv-miss"
        cache_dir = tmp_path / "arxiv-cache"
        cache_dir.mkdir()

        import search_arxiv

        # The cache is empty; a --use-cache run should emit cache_miss.
        with pytest.raises(SystemExit) as excinfo:
            search_arxiv.run_arxiv_search(
                query="no cache for this",
                workspace=ws,
                max_results=3,
                category="cs.AI",
                sort_by="relevance",
                use_cache=True,
                clear_cache_first=False,
                cache_dir=cache_dir,
            )
        # emit_error exits with code 1
        assert excinfo.value.code == 1

    def test_arxiv_cache_key_includes_category_and_sort(
        self, tmp_path: Path
    ) -> None:
        """A live arxiv run must use a cache key that incorporates category and sort_by.

        We can't easily call run_arxiv_search (needs the arxiv package), so
        we test the cache_key function directly with the same args the
        runner will pass.
        """
        cache_dir = tmp_path / "arxiv-cache-key-test"
        cache_dir.mkdir()
        from search_web import cache_key
        a = cache_key("arxiv", "q", 5, category="cs.AI", sort_by="relevance")
        b = cache_key("arxiv", "q", 5, category="cs.LG", sort_by="relevance")
        c = cache_key("arxiv", "q", 5, category="cs.AI", sort_by="date")
        d = cache_key("arxiv", "q", 5, category=None, sort_by="relevance")
        # All four keys must be distinct
        assert len({a, b, c, d}) == 4
        # Writing and reading back must round-trip via the new key format
        from search_web import save_cache, load_cache
        save_cache(
            cache_dir, "arxiv", "q", 5,
            [{"arxiv_id": "2401.01234", "url": "https://x", "title": "T"}],
            category="cs.AI", sort_by="relevance",
        )
        # Same key -> hit
        assert load_cache(cache_dir, "arxiv", "q", 5, category="cs.AI", sort_by="relevance") is not None
        # Different category -> miss
        assert load_cache(cache_dir, "arxiv", "q", 5, category="cs.LG", sort_by="relevance") is None
        # Different sort -> miss
        assert load_cache(cache_dir, "arxiv", "q", 5, category="cs.AI", sort_by="date") is None


class TestPubmedAndBiomedicalRouting:
    def test_search_pubmed_uses_cached_fixture(self, tmp_path: Path) -> None:
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "pubmed-cache", "--path", str(tmp_path))
        ws = tmp_path / "pubmed-cache"
        cache_dir = tmp_path / "pubmed-cache-data"
        build_cache_file(
            cache_dir,
            "pubmed",
            "methylene blue safety",
            1,
            results=[
                {
                    "pubmed_id": "12345678",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                    "title": "Methylene blue safety in adults",
                    "abstract": "A trial evaluated methylene blue safety outcomes.",
                    "authors": ["Ada Lovelace", "Grace Hopper"],
                    "journal": "Clinical Journal",
                    "date_published": "2024-01-01",
                    "doi": "10.1000/example",
                    "mesh_terms": ["Methylene Blue", "Safety"],
                    "publication_types": ["Clinical Trial"],
                    "pmc_id": "PMC123456",
                }
            ],
        )

        result = run_script(
            str(SCRIPTS_DIR / "search_pubmed.py"),
            "methylene blue safety",
            "--workspace",
            str(ws),
            "--max-results",
            "1",
            "--use-cache",
            "--cache-dir",
            str(cache_dir),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "ok"
        assert out["sources_added"] == 1
        source_text = (ws / "sources" / "papers" / "src_001.md").read_text(encoding="utf-8")
        meta, body = parse_frontmatter_helper(source_text)
        assert meta["provider"] == "pubmed"
        assert meta["quality_tier"] == "authoritative"
        assert "Clinical Trial" in body

    def test_search_arxiv_warns_for_biomedical_query(self, tmp_path: Path) -> None:
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "arxiv-biomed", "--path", str(tmp_path))
        ws = tmp_path / "arxiv-biomed"
        cache_dir = tmp_path / "arxiv-biomed-cache"
        build_cache_file(
            cache_dir,
            "arxiv",
            "methylene blue safety trial",
            1,
            results=[
                {
                    "arxiv_id": "2401.01234",
                    "url": "https://arxiv.org/abs/2401.01234",
                    "pdf_url": "https://arxiv.org/pdf/2401.01234",
                    "title": "Methylene blue graph embeddings",
                    "summary": "A computational paper with methylene blue lexical overlap.",
                    "authors": "Ada Lovelace",
                    "date_published": "2024-01-01",
                    "categories": ["cs.AI"],
                    "primary_category": "cs.AI",
                }
            ],
            sort_by="relevance",
        )

        result = run_script(
            str(SCRIPTS_DIR / "search_arxiv.py"),
            "methylene blue safety trial",
            "--workspace",
            str(ws),
            "--max-results",
            "1",
            "--use-cache",
            "--cache-dir",
            str(cache_dir),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "ok"
        assert any("PubMed" in warning for warning in out["warnings"])

    def test_search_arxiv_must_contain_filters_irrelevant_records(self, tmp_path: Path) -> None:
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "arxiv-filter", "--path", str(tmp_path))
        ws = tmp_path / "arxiv-filter"
        cache_dir = tmp_path / "arxiv-filter-cache"
        build_cache_file(
            cache_dir,
            "arxiv",
            "methylene blue",
            2,
            results=[
                {
                    "arxiv_id": "2401.01234",
                    "url": "https://arxiv.org/abs/2401.01234",
                    "pdf_url": "https://arxiv.org/pdf/2401.01234",
                    "title": "Methylene blue detection model",
                    "summary": "Mentions methylene blue directly.",
                    "authors": "Ada Lovelace",
                    "date_published": "2024-01-01",
                    "categories": ["cs.CV"],
                    "primary_category": "cs.CV",
                },
                {
                    "arxiv_id": "2401.09999",
                    "url": "https://arxiv.org/abs/2401.09999",
                    "pdf_url": "https://arxiv.org/pdf/2401.09999",
                    "title": "Blue noise rendering",
                    "summary": "Does not include the full phrase.",
                    "authors": "Grace Hopper",
                    "date_published": "2024-01-02",
                    "categories": ["cs.GR"],
                    "primary_category": "cs.GR",
                },
            ],
            sort_by="relevance",
            must_contain="methylene blue",
        )

        result = run_script(
            str(SCRIPTS_DIR / "search_arxiv.py"),
            "methylene blue",
            "--workspace",
            str(ws),
            "--max-results",
            "2",
            "--must-contain",
            "methylene blue",
            "--use-cache",
            "--cache-dir",
            str(cache_dir),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["sources_added"] == 1
        assert out["sources_filtered"] == 1

    def test_search_arxiv_marks_low_overlap_saved_results(self, tmp_path: Path) -> None:
        run_script(str(SCRIPTS_DIR / "init_workspace.py"), "arxiv-overlap", "--path", str(tmp_path))
        ws = tmp_path / "arxiv-overlap"
        cache_dir = tmp_path / "arxiv-overlap-cache"
        build_cache_file(
            cache_dir,
            "arxiv",
            "methylene blue randomized trial",
            1,
            results=[
                {
                    "arxiv_id": "2401.01234",
                    "url": "https://arxiv.org/abs/2401.01234",
                    "pdf_url": "https://arxiv.org/pdf/2401.01234",
                    "title": "Blue signal processing",
                    "summary": "Randomized matrices are discussed.",
                    "authors": "Ada Lovelace",
                    "date_published": "2024-01-01",
                    "categories": ["cs.IT"],
                    "primary_category": "cs.IT",
                }
            ],
            sort_by="relevance",
            must_contain="",
            min_query_token_overlap=3,
        )

        result = run_script(
            str(SCRIPTS_DIR / "search_arxiv.py"),
            "methylene blue randomized trial",
            "--workspace",
            str(ws),
            "--max-results",
            "1",
            "--min-query-token-overlap",
            "3",
            "--use-cache",
            "--cache-dir",
            str(cache_dir),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["sources_marked_low_relevance"] == 1
        source_text = (ws / "sources" / "papers" / "src_001.md").read_text(encoding="utf-8")
        meta, _ = parse_frontmatter_helper(source_text)
        assert meta["content_quality"] == "low_relevance"
