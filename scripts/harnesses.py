"""
harnesses.py: supported coding-agent harness definitions for Calixto.

This module centralizes:
- executable discovery
- harness-specific project skill mirror locations
- interactive launch argument construction
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HarnessAdapter:
    name: str
    executable: str | None
    project_skill_dirs: tuple[str, ...]
    supports_prompt: bool
    description: str

    def resolve_executable(self) -> str | None:
        if not self.executable:
            return None
        return shutil.which(self.executable)


HARNESSES: dict[str, HarnessAdapter] = {
    "none": HarnessAdapter(
        name="none",
        executable=None,
        project_skill_dirs=(),
        supports_prompt=False,
        description="Prepare the workspace without launching an external coding agent.",
    ),
    "opencode": HarnessAdapter(
        name="opencode",
        executable="opencode",
        project_skill_dirs=(".agents/skills", ".opencode/skills"),
        supports_prompt=True,
        description="Launch OpenCode in the workspace and pass a short initial prompt.",
    ),
    "claude": HarnessAdapter(
        name="claude",
        executable="claude",
        project_skill_dirs=(".claude/skills",),
        supports_prompt=True,
        description="Launch Claude Code in the workspace and pass a short initial prompt.",
    ),
    "codex": HarnessAdapter(
        name="codex",
        executable="codex",
        project_skill_dirs=(".agents/skills",),
        supports_prompt=True,
        description="Launch Codex in the workspace and pass a short initial prompt.",
    ),
}


def supported_harness_names() -> list[str]:
    return sorted(HARNESSES)


def get_harness(name: str) -> HarnessAdapter:
    try:
        return HARNESSES[name]
    except KeyError as exc:
        supported = ", ".join(supported_harness_names())
        raise ValueError(f"unsupported harness '{name}'. Supported values: {supported}") from exc


def ensure_harness_available(name: str) -> str | None:
    adapter = get_harness(name)
    if adapter.executable is None:
        return None
    resolved = adapter.resolve_executable()
    if resolved is None:
        raise FileNotFoundError(
            f"required harness executable '{adapter.executable}' is not available on PATH"
        )
    return resolved


def project_skill_dirs_for(name: str) -> tuple[str, ...]:
    return get_harness(name).project_skill_dirs


def _resolved_launch_prefix(adapter: HarnessAdapter) -> list[str]:
    if adapter.executable is None:
        return []
    resolved = adapter.resolve_executable()
    if resolved is None:
        raise FileNotFoundError(
            f"required harness executable '{adapter.executable}' is not available on PATH"
        )

    resolved_path = Path(resolved)
    if sys.platform.startswith("win") and resolved_path.suffix.lower() == ".ps1":
        shell_host = shutil.which("pwsh") or shutil.which("powershell")
        if shell_host is None:
            raise FileNotFoundError(
                f"PowerShell is required to launch harness script '{resolved_path.name}'"
            )
        return [shell_host, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(resolved_path)]

    return [str(resolved_path)]


def launch_arguments(
    name: str,
    *,
    workspace: Path,
    prompt: str,
) -> list[str]:
    adapter = get_harness(name)
    launch_prefix = _resolved_launch_prefix(adapter)
    if adapter.name == "none":
        return []
    if adapter.name == "opencode":
        return [*launch_prefix, str(workspace), "--prompt", prompt]
    if adapter.name == "claude":
        return [*launch_prefix, prompt]
    if adapter.name == "codex":
        return [*launch_prefix, "--cd", str(workspace), prompt]
    raise ValueError(f"unsupported harness '{name}'")


def initial_handoff_prompt(question: str) -> str:
    return (
        "Read AGENTS.md in this workspace, load the relevant research skill from skills/, "
        f"and answer the exact research question recorded in config.json: {question}"
    )


def launch_harness_process(
    name: str,
    *,
    workspace: Path,
    environment: dict[str, str],
    prompt: str,
) -> subprocess.Popen[str]:
    adapter = get_harness(name)
    if adapter.name == "none":
        raise ValueError("cannot launch harness 'none'")
    argv = launch_arguments(name, workspace=workspace, prompt=prompt)
    return subprocess.Popen(
        argv,
        cwd=str(workspace),
        env=environment,
        text=True,
    )


def cursor_agent_cli_available() -> bool:
    """Return True only if a distinct Cursor agent CLI can be confirmed.

    As of 2026-06-20 the observed `cursor` CLI on this machine is still the
    editor launcher surface, so Calixto keeps Cursor support gated.
    """

    return False


def observed_help_metadata() -> dict[str, Any]:
    """Return static notes recorded in the decision log/tests for help surfaces."""
    return {
        "verified_at": "2026-06-20",
        "platform": sys.platform,
        "guaranteed_harnesses": ["none", "opencode", "claude", "codex"],
        "cursor_agent_cli_supported": cursor_agent_cli_available(),
    }
