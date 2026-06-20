from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import harnesses  # noqa: E402


class TestHarnessLaunchArguments:
    def test_opencode_uses_powershell_for_ps1_launcher_on_windows(self, monkeypatch) -> None:
        workspace = Path(r"D:\Repos\calixto-research-workspace\workspaces\sample")

        def fake_which(name: str) -> str | None:
            if name == "opencode":
                return r"C:\Program Files\nodejs\opencode.ps1"
            if name == "pwsh":
                return r"C:\Program Files\PowerShell\7\pwsh.exe"
            return None

        monkeypatch.setattr(harnesses.shutil, "which", fake_which)
        monkeypatch.setattr(harnesses.sys, "platform", "win32")

        argv = harnesses.launch_arguments(
            "opencode",
            workspace=workspace,
            prompt="read the workspace",
        )

        assert argv == [
            r"C:\Program Files\PowerShell\7\pwsh.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            r"C:\Program Files\nodejs\opencode.ps1",
            str(workspace),
            "--prompt",
            "read the workspace",
        ]

    def test_codex_uses_resolved_executable_path(self, monkeypatch) -> None:
        workspace = Path("/tmp/workspace")
        resolved_codex = str(Path("/usr/local/bin/codex"))

        monkeypatch.setattr(
            harnesses.shutil,
            "which",
            lambda name: resolved_codex if name == "codex" else None,
        )
        monkeypatch.setattr(harnesses.sys, "platform", "linux")

        argv = harnesses.launch_arguments(
            "codex",
            workspace=workspace,
            prompt="resume work",
        )

        assert argv == [
            resolved_codex,
            "--cd",
            str(workspace),
            "resume work",
        ]
