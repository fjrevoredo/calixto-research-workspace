from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import calixto  # noqa: E402
from _common import is_valid_slug  # noqa: E402


def _run_cli(*args: str):
    import subprocess

    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "calixto.py"), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


class TestCalixtoResearchJson:
    def test_research_json_writes_question(self, tmp_path: Path) -> None:
        result = _run_cli(
            "research",
            "What should we test?",
            "--agent",
            "none",
            "--json",
            "--skip-update-check",
            "--path",
            str(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["command"] == "research"
        assert payload["question"] == "What should we test?"
        workspace = Path(payload["workspace"])
        config = json.loads((workspace / "config.json").read_text(encoding="utf-8"))
        assert config["question"] == "What should we test?"
        assert payload["runtime_mode"] == "standalone_setup_required"

    def test_research_rejects_json_with_launching_agent(self, tmp_path: Path) -> None:
        result = _run_cli(
            "research",
            "Question text",
            "--agent",
            "codex",
            "--json",
            "--skip-update-check",
            "--path",
            str(tmp_path),
        )
        assert result.returncode == 1
        error = json.loads(result.stdout)
        assert error["error"] == "invalid_arguments"

    def test_research_uses_hash_fallback_for_symbol_only_question(self, tmp_path: Path) -> None:
        result = _run_cli(
            "research",
            "!!!",
            "--agent",
            "none",
            "--json",
            "--skip-update-check",
            "--path",
            str(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["workspace_name"].startswith("research-")
        assert is_valid_slug(payload["workspace_name"])

    def test_research_auto_collision_adds_suffix(self, tmp_path: Path) -> None:
        first = _run_cli(
            "research",
            "Same question",
            "--agent",
            "none",
            "--json",
            "--skip-update-check",
            "--path",
            str(tmp_path),
        )
        second = _run_cli(
            "research",
            "Same question",
            "--agent",
            "none",
            "--json",
            "--skip-update-check",
            "--path",
            str(tmp_path),
        )
        assert first.returncode == 0, first.stderr
        assert second.returncode == 0, second.stderr
        first_payload = json.loads(first.stdout)
        second_payload = json.loads(second.stdout)
        assert first_payload["workspace_name"] == "same-question"
        assert second_payload["workspace_name"] == "same-question-2"


class TestHarnessMirrorGeneration:
    def test_create_workspace_generates_codex_skill_mirror(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(calixto, "ensure_harness_available", lambda name: "codex")
        args = Namespace(
            question="Mirror generation question",
            name=None,
            path=str(tmp_path),
            agent="codex",
            json=False,
            setup_local=False,
            force_harness_mirrors=False,
            check_updates=False,
            skip_update_check=True,
            require_update_check=False,
            update_before_create=False,
        )

        created = calixto._create_workspace(args)
        workspace = Path(created["workspace"])
        for skill_name in ("deep-research", "literature-review", "research-preparation"):
            assert (workspace / ".agents" / "skills" / skill_name / "SKILL.md").exists()
            canonical = (workspace / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
            mirrored = (workspace / ".agents" / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
            assert mirrored == canonical

    def test_existing_mirror_is_preserved_by_default(self, tmp_path: Path) -> None:
        import init_workspace

        init_workspace.init_workspace("existing", tmp_path)
        workspace = tmp_path / "existing"
        mirror_dir = workspace / ".agents" / "skills" / "deep-research"
        mirror_dir.mkdir(parents=True)
        shutil_source = workspace / "skills" / "deep-research" / "SKILL.md"
        (mirror_dir / "SKILL.md").write_text(shutil_source.read_text(encoding="utf-8"), encoding="utf-8")
        marker = mirror_dir / "custom-note.txt"
        marker.write_text("keep me", encoding="utf-8")

        report = calixto._generate_harness_skill_mirrors(workspace, "codex", force=False)

        assert str(mirror_dir) in report["preserved"]
        assert marker.exists()
        assert str(workspace / ".agents" / "skills" / "research-preparation") in report["created"]

    def test_existing_mirror_can_be_replaced_with_force(self, tmp_path: Path) -> None:
        import init_workspace

        init_workspace.init_workspace("existing", tmp_path)
        workspace = tmp_path / "existing"
        mirror_dir = workspace / ".agents" / "skills" / "deep-research"
        mirror_dir.mkdir(parents=True)
        source = workspace / "skills" / "deep-research" / "SKILL.md"
        (mirror_dir / "SKILL.md").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        marker = mirror_dir / "custom-note.txt"
        marker.write_text("overwrite me", encoding="utf-8")

        report = calixto._generate_harness_skill_mirrors(workspace, "codex", force=True)

        assert str(mirror_dir) in report["replaced"]
        assert not marker.exists()
        assert (mirror_dir / "SKILL.md").read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
        assert str(workspace / ".agents" / "skills" / "research-preparation") in report["created"]

    def test_open_prepare_harness_generates_claude_mirror(self, tmp_path: Path, monkeypatch) -> None:
        import init_workspace

        init_workspace.init_workspace("existing", tmp_path)
        workspace = tmp_path / "existing"

        monkeypatch.setattr(calixto, "ensure_harness_available", lambda name: "claude")
        monkeypatch.setattr(
            calixto,
            "_prepare_runtime_for_workspace",
            lambda workspace, setup_local: {
                "runtime_mode": "local",
                "runtime_key": "abc",
                "runtime_display_key": "abc",
                "environment_path": str(workspace / ".venv"),
            },
        )

        class _FakeProcess:
            def wait(self) -> int:
                return 0

        monkeypatch.setattr(calixto, "launch_harness_process", lambda *args, **kwargs: _FakeProcess())

        rc = calixto.main(
            [
                "open",
                str(workspace),
                "--agent",
                "claude",
                "--prepare-harness",
            ]
        )
        assert rc == 0
        for skill_name in ("deep-research", "literature-review", "research-preparation"):
            assert (workspace / ".claude" / "skills" / skill_name / "SKILL.md").exists()

    def test_open_json_emits_structured_payload(self, tmp_path: Path, monkeypatch, capsys) -> None:
        import init_workspace

        init_workspace.init_workspace("existing", tmp_path)
        workspace = tmp_path / "existing"

        monkeypatch.setattr(
            calixto,
            "_prepare_runtime_for_workspace",
            lambda workspace, setup_local: {
                "runtime_mode": "local",
                "runtime_key": "abc",
                "runtime_display_key": "abc123",
                "environment_path": str(workspace / ".venv"),
            },
        )

        rc = calixto.main(
            [
                "open",
                str(workspace),
                "--agent",
                "none",
                "--json",
            ]
        )

        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "ok"
        assert payload["command"] == "open"
        assert payload["workspace"] == str(workspace)
        assert payload["runtime_mode"] == "local"

    def test_open_rejects_json_with_launching_agent(self, tmp_path: Path) -> None:
        import init_workspace

        init_workspace.init_workspace("existing", tmp_path)
        workspace = tmp_path / "existing"

        result = _run_cli(
            "open",
            str(workspace),
            "--agent",
            "codex",
            "--json",
        )

        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["error"] == "invalid_arguments"

    def test_runtime_list_json_emits_structured_payload(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(
            calixto,
            "list_managed_runtimes",
            lambda: [
                {
                    "runtime_display_key": "abc123",
                    "runtime_key": "abc123full",
                    "runtime_dir": "/tmp/runtime",
                    "is_current_key": True,
                    "valid": True,
                    "apparent_size_bytes": 123,
                    "referenced_workspaces": [],
                }
            ],
        )

        rc = calixto.main(["runtime", "list", "--json"])

        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "ok"
        assert payload["command"] == "runtime_list"
        assert payload["count"] == 1

    def test_runtime_prune_json_reports_partial_when_protected(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(
            calixto,
            "prune_managed_runtimes",
            lambda **kwargs: {
                "dry_run": False,
                "force": False,
                "deleted": [],
                "kept": ["abc123"],
                "reasons": {"abc123": "current_key_protected"},
            },
        )

        rc = calixto.main(["runtime", "prune", "--json"])

        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "partial"
        assert payload["command"] == "runtime_prune"
