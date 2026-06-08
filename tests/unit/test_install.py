"""Integration tests for the Unix installer (install.sh).

These tests build a local "remote" git repository containing a minimal
Calixto workspace, then exercise install.sh against an empty target
directory. They verify:

- The fresh-install mode copies all required files (including dotfiles)
- The installed target contains every workspace marker
- A non-empty target directory is rejected
- A botched install (markers missing) exits nonzero and preserves staging
- The update mode preserves user-owned data, repository metadata, and
  config overrides; replaces toolkit-owned entries; does not abort on
  non-empty directory collisions

The tests require a POSIX shell environment where install.sh can be run
with the bash host's native path semantics. They are skipped on Windows
because the Git-for-Windows MSYS2 layer mangles backslash-containing
paths in argument and environment-variable values, which makes it
impractical to drive install.sh from a Windows Python test harness.
"""
from __future__ import annotations

import os
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"


def _is_windows() -> bool:
    return sys.platform == "win32"


def _have_bash_and_git() -> bool:
    return shutil.which("bash") is not None and shutil.which("git") is not None


pytestmark = [
    pytest.mark.skipif(
        _is_windows(),
        reason="install.sh integration tests need a POSIX shell host; skipped on Windows",
    ),
    pytest.mark.skipif(
        not _have_bash_and_git(),
        reason="install.sh tests require bash and git on PATH",
    ),
]


WORKSPACE_MARKERS = [
    "PHILOSOPHY.md",
    "requirements.md",
    "AGENTS.md",
    "setup.sh",
    "setup.ps1",
    "templates",
    "scripts",
    "providers",
    "skills",
]


def _run_bash(script: str, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", script],
        cwd=cwd or REPO_ROOT,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
    )


def _build_remote_repo(remote: Path) -> None:
    """Create a local git repo at `remote` populated with the toolkit's tracked files."""
    if remote.exists():
        shutil.rmtree(remote)
    remote.mkdir(parents=True)
    for marker in WORKSPACE_MARKERS:
        src = REPO_ROOT / marker
        if not src.exists():
            continue
        dst = remote / marker
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    # Add a dotfile to exercise the dotglob path
    (remote / ".calixto-dotfile").write_text("dot\n", encoding="utf-8")
    _run_bash(
        "git init -q -b main && "
        "git config user.email 'ci@example.com' && "
        "git config user.name 'CI' && "
        "git add -A && "
        "git commit -q -m 'fixture'",
        cwd=remote,
    )


def _invoke_installer(target: Path, remote: Path) -> subprocess.CompletedProcess:
    """Run install.sh with the given target directory.

    The installer's TARGET_DIR is its own pwd, so we cd into target first
    inside the wrapper script. The script path is passed via the
    CALIXTO_INSTALL_SH env var to avoid the host's argv parsing.
    """
    return _run_bash(
        'cd "$CALIXTO_TARGET" && '
        'CALIXTO_REPO_URL="$CALIXTO_REMOTE" '
        'bash "$CALIXTO_INSTALL_SH" --non-interactive --skip-deps',
        env={
            "CALIXTO_TARGET": str(target),
            "CALIXTO_REMOTE": str(remote),
            "CALIXTO_INSTALL_SH": str(INSTALL_SH),
        },
        cwd=REPO_ROOT,
    )


def test_fresh_install_copies_all_files(tmp_path: Path) -> None:
    """A fresh install into an empty directory must copy every workspace marker and dotfile."""
    remote = tmp_path / "remote.git"
    target = tmp_path / "install-target"
    target.mkdir()
    _build_remote_repo(remote)

    result = _invoke_installer(target, remote)
    assert result.returncode == 0, (
        f"installer failed (rc={result.returncode})\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    for marker in WORKSPACE_MARKERS:
        assert (target / marker).exists(), f"marker missing: {marker}"
    # Dotfiles must have been copied by the dotglob step
    assert (target / ".calixto-dotfile").is_file()
    assert (target / ".calixto-dotfile").read_text(encoding="utf-8") == "dot\n"
    # Staging artifacts must be cleaned up after a successful install
    assert not (target / ".calixto-tmp").exists()
    assert not any(target.glob(".calixto-stage*"))
    assert not (target / ".calixto.tar.gz").exists()


def test_fresh_install_rejects_non_empty_target(tmp_path: Path) -> None:
    """A non-empty target must trigger fresh-install refusal before any fetch."""
    remote = tmp_path / "remote.git"
    target = tmp_path / "install-target"
    target.mkdir()
    (target / "pre-existing.txt").write_text("keep", encoding="utf-8")
    _build_remote_repo(remote)

    result = _invoke_installer(target, remote)
    assert result.returncode != 0
    assert (target / "pre-existing.txt").exists()
    assert not (target / "AGENTS.md").exists()


def test_fresh_install_fails_on_incomplete_install(tmp_path: Path) -> None:
    """If the staged clone is missing required markers, the installer must fail
    and preserve the staging directory for inspection.
    """
    remote = tmp_path / "remote.git"
    target = tmp_path / "install-target"
    target.mkdir()

    # Build a remote that is intentionally missing several required markers
    missing_markers = {"AGENTS.md", "skills", "providers"}
    partial_markers = [m for m in WORKSPACE_MARKERS if m not in missing_markers]
    if remote.exists():
        shutil.rmtree(remote)
    remote.mkdir(parents=True)
    for marker in partial_markers:
        src = REPO_ROOT / marker
        if not src.exists():
            continue
        dst = remote / marker
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    _run_bash(
        "git init -q -b main && "
        "git config user.email 'ci@example.com' && "
        "git config user.name 'CI' && "
        "git add -A && "
        "git commit -q -m 'partial'",
        cwd=remote,
    )

    result = _invoke_installer(target, remote)
    assert result.returncode != 0, "installer should fail on incomplete install"
    # The missing markers must still be missing in the target
    assert not (target / "AGENTS.md").exists()
    # Staging dir preserved
    assert (target / ".calixto-tmp").exists()


def test_update_preserves_user_data_and_replaces_toolkit(tmp_path: Path) -> None:
    """Update mode must:
    - preserve user-owned data: workspaces/, notes/, outputs/, config.json, *.local
    - preserve repository metadata: .git/
    - replace toolkit-owned entries: scripts/, providers/, etc.
    - succeed when the target already contains a non-empty scripts/ tree
      (collision handling must not abort on non-empty directories)
    """
    remote = tmp_path / "remote.git"
    target = tmp_path / "install-target"
    target.mkdir()
    _build_remote_repo(remote)

    # Pre-populate the target with a "previous" version of the toolkit
    # plus user-owned data. The "previous" scripts/ has files the
    # current toolkit will replace.
    for marker in WORKSPACE_MARKERS:
        src = REPO_ROOT / marker
        if not src.exists():
            continue
        dst = target / marker
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    # User-owned data must be preserved verbatim
    user_workspaces = target / "workspaces" / "user-research"
    user_workspaces.mkdir(parents=True)
    user_notes = user_workspaces / "notes"
    user_notes.mkdir()
    (user_notes / "findings.md").write_text(
        "## fnd_001\n**Source:** src_001\n**Fact:** user fact\n",
        encoding="utf-8",
    )
    # User-owned config
    (target / "config.json").write_text(
        '{"user_overrides": "preserved"}',
        encoding="utf-8",
    )
    (target / "settings.local").write_text(
        "user-controlled data",
        encoding="utf-8",
    )
    # A .git directory (the developer's repo metadata)
    git_dir = target / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "config").write_text("[user]\n\tname = test\n", encoding="utf-8")

    # Sanity: the marker under test is present before update
    assert (target / "scripts" / "init_workspace.py").is_file()
    user_facts_before = (user_notes / "findings.md").read_text(encoding="utf-8")
    user_config_before = (target / "config.json").read_text(encoding="utf-8")
    user_local_before = (target / "settings.local").read_text(encoding="utf-8")
    user_git_head_before = (git_dir / "HEAD").read_text(encoding="utf-8")

    # The installer enters update mode when the target already looks
    # like a Calixto workspace. Run it with --skip-deps so we only
    # exercise the file-move / restore logic, not the (potentially
    # network-dependent) setup step.
    env = {**os.environ, "CALIXTO_REPO_URL": str(remote), "CALIXTO_SKIP_DEPS": "1"}
    # Use --non-interactive so the confirmation prompt does not block
    # in the test environment.
    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--non-interactive", "--skip-deps"],
        cwd=str(target),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"update installer failed (rc={result.returncode})\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    # User-owned workspace data must be intact
    assert (target / "workspaces" / "user-research" / "notes" / "findings.md").is_file()
    user_facts_after = (user_notes / "findings.md").read_text(encoding="utf-8")
    assert user_facts_after == user_facts_before, "user notes content was modified"
    # config.json must be preserved
    user_config_after = (target / "config.json").read_text(encoding="utf-8")
    assert user_config_after == user_config_before, "config.json was modified"
    # *.local must be preserved
    user_local_after = (target / "settings.local").read_text(encoding="utf-8")
    assert user_local_after == user_local_before, "*.local file was modified"
    # .git/ must be preserved
    assert (git_dir / "HEAD").is_file()
    assert (git_dir / "HEAD").read_text(encoding="utf-8") == user_git_head_before, (
        ".git/HEAD was modified by the update"
    )
    # Toolkit-owned entries must be replaced with the new remote's
    # content. We can't easily check byte equality against the remote,
    # but we can check that scripts/init_workspace.py is still present
    # and parses.
    assert (target / "scripts" / "init_workspace.py").is_file()
    py_compile.compile(
        str(target / "scripts" / "init_workspace.py"),
        doraise=True,
    )
