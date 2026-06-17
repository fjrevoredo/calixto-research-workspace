"""Git-backed toolkit metadata and update-check helpers.

These helpers are toolkit-root only. They support:

- recording commit/build metadata in newly generated workspaces
- checking whether the local toolkit checkout is behind the remote default branch
- generating the exact installer command to update the toolkit root safely

All helpers degrade gracefully when git metadata or remote access is unavailable.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
_LS_REMOTE_HEAD_RE = re.compile(r"^ref:\s+refs/heads/(?P<branch>[^\s]+)\s+HEAD$")


def _run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str] | None:
    """Run one git command in the repository root.

    Returns None when git itself is unavailable.
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=check,
        )
    except FileNotFoundError:
        return None
    except subprocess.CalledProcessError as exc:
        if check:
            raise
        return exc


def _git_output(*args: str) -> str | None:
    """Return stripped git stdout, or None when unavailable/failing."""
    result = _run_git(*args, check=False)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _git_error_text(result: subprocess.CompletedProcess[str] | None) -> str:
    if result is None:
        return "git is not installed or not on PATH"
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    return stderr or stdout or f"git exited with code {result.returncode}"


def normalize_installer_repo_url(raw_url: str | None) -> str | None:
    """Normalize common GitHub remote URL forms to the installer HTTPS contract."""
    if not raw_url:
        return None
    value = raw_url.strip()
    if value.startswith("git@github.com:"):
        path = value.removeprefix("git@github.com:")
        return f"https://github.com/{path}"
    if value.startswith("ssh://git@github.com/"):
        path = value.removeprefix("ssh://git@github.com/")
        return f"https://github.com/{path}"
    if value.startswith("https://github.com/"):
        return value
    return None


def toolkit_commit() -> str | None:
    """Return the local HEAD commit SHA, or None when unavailable."""
    return _git_output("rev-parse", "HEAD")


def toolkit_build_number(ref: str = "HEAD") -> int | None:
    """Return the git commit-count build number for a ref, or None when unavailable."""
    output = _git_output("rev-list", "--count", ref)
    if output is None:
        return None
    try:
        return int(output)
    except ValueError:
        return None


def toolkit_ref_name() -> str | None:
    """Return the symbolic branch name for HEAD, or None in detached/non-git states."""
    return _git_output("symbolic-ref", "--short", "-q", "HEAD")


def toolkit_remote_url(remote_name: str = "origin") -> str | None:
    """Return the configured remote URL for the toolkit repository."""
    return _git_output("remote", "get-url", remote_name)


def installer_repo_url(remote_name: str = "origin") -> str | None:
    """Return the normalized repo URL acceptable to the installer, when possible."""
    return normalize_installer_repo_url(toolkit_remote_url(remote_name))


def _commit_object_available(commit_sha: str) -> bool:
    result = _run_git("cat-file", "-e", f"{commit_sha}^{{commit}}", check=False)
    return result is not None and result.returncode == 0


def _is_ancestor(left: str, right: str) -> bool | None:
    """Return whether left is an ancestor of right.

    Returns None when git cannot determine the relationship.
    """
    result = _run_git("merge-base", "--is-ancestor", left, right, check=False)
    if result is None:
        return None
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def _resolve_local_tracking_ref(remote_name: str, branch_name: str) -> tuple[str | None, str | None]:
    ref_name = f"refs/remotes/{remote_name}/{branch_name}"
    resolved = _git_output("rev-parse", ref_name)
    if resolved is None:
        return None, None
    return ref_name, resolved


def discover_default_branch(remote_name: str = "origin") -> dict[str, Any]:
    """Discover the remote default branch and latest commit SHA."""
    remote_url = toolkit_remote_url(remote_name)
    normalized_repo_url = normalize_installer_repo_url(remote_url)
    result = _run_git("ls-remote", "--symref", remote_name, "HEAD", check=False)
    if result is None:
        return {
            "status": "unavailable",
            "reason": "git_unavailable",
            "message": "git is not installed or not on PATH",
            "remote_name": remote_name,
            "remote_url": remote_url,
            "installer_repo_url": normalized_repo_url,
        }
    if result.returncode != 0:
        return {
            "status": "unavailable",
            "reason": "remote_lookup_failed",
            "message": _git_error_text(result),
            "remote_name": remote_name,
            "remote_url": remote_url,
            "installer_repo_url": normalized_repo_url,
        }

    branch_name: str | None = None
    head_commit: str | None = None
    for line in result.stdout.splitlines():
        match = _LS_REMOTE_HEAD_RE.match(line.strip())
        if match:
            branch_name = match.group("branch")
            continue
        parts = line.strip().split()
        if len(parts) == 2 and parts[1] == "HEAD":
            head_commit = parts[0]

    if not branch_name or not head_commit:
        return {
            "status": "unavailable",
            "reason": "remote_head_parse_failed",
            "message": "could not parse remote HEAD metadata from git ls-remote",
            "remote_name": remote_name,
            "remote_url": remote_url,
            "installer_repo_url": normalized_repo_url,
        }

    tracking_ref_name, tracking_ref_sha = _resolve_local_tracking_ref(remote_name, branch_name)
    return {
        "status": "ok",
        "remote_name": remote_name,
        "remote_url": remote_url,
        "installer_repo_url": normalized_repo_url,
        "default_branch": branch_name,
        "default_branch_ref": f"refs/heads/{branch_name}",
        "latest_commit": head_commit,
        "tracking_ref": tracking_ref_name,
        "tracking_ref_commit": tracking_ref_sha,
    }


def check_toolkit_freshness(remote_name: str = "origin") -> dict[str, Any]:
    """Compare local HEAD to the remote default branch without mutating the checkout."""
    local_commit = toolkit_commit()
    local_build = toolkit_build_number()
    local_ref = toolkit_ref_name()
    detached_head = local_ref is None and local_commit is not None

    if local_commit is None:
        return {
            "status": "unavailable",
            "reason": "local_git_metadata_unavailable",
            "message": "could not determine local toolkit commit metadata",
            "local_commit": None,
            "local_build_number": None,
            "local_ref": None,
            "detached_head": False,
        }

    remote = discover_default_branch(remote_name)
    if remote["status"] != "ok":
        return {
            "status": "unavailable",
            "reason": remote["reason"],
            "message": remote["message"],
            "local_commit": local_commit,
            "local_build_number": local_build,
            "local_ref": local_ref,
            "detached_head": detached_head,
            "remote_name": remote.get("remote_name"),
            "remote_url": remote.get("remote_url"),
            "installer_repo_url": remote.get("installer_repo_url"),
        }

    latest_commit = remote["latest_commit"]
    result: dict[str, Any] = {
        "status": "unknown",
        "local_commit": local_commit,
        "local_build_number": local_build,
        "local_ref": local_ref,
        "detached_head": detached_head,
        "remote_name": remote["remote_name"],
        "remote_url": remote["remote_url"],
        "installer_repo_url": remote["installer_repo_url"],
        "default_branch": remote["default_branch"],
        "latest_commit": latest_commit,
        "latest_build_number": None,
        "behind_by": None,
    }

    if local_commit == latest_commit:
        result["status"] = "up_to_date"
        result["latest_build_number"] = local_build
        return result

    comparison_ref = latest_commit
    if not _commit_object_available(latest_commit):
        tracking_ref = remote.get("tracking_ref")
        tracking_ref_commit = remote.get("tracking_ref_commit")
        if tracking_ref and tracking_ref_commit == latest_commit:
            comparison_ref = tracking_ref
        else:
            result["status"] = "remote_newer_unknown_relationship"
            result["message"] = (
                "remote default branch has a newer commit, but its history is not present locally "
                "so the relationship to HEAD could not be classified"
            )
            return result

    latest_build_number = toolkit_build_number(str(comparison_ref))
    result["latest_build_number"] = latest_build_number

    local_behind = _is_ancestor(local_commit, str(comparison_ref))
    remote_behind = _is_ancestor(str(comparison_ref), local_commit)
    if local_behind is True:
        result["status"] = "behind"
        behind_text = _git_output("rev-list", "--count", f"{local_commit}..{comparison_ref}")
        if behind_text is not None:
            try:
                result["behind_by"] = int(behind_text)
            except ValueError:
                result["behind_by"] = None
        return result
    if remote_behind is True:
        result["status"] = "ahead"
        return result
    if local_behind is False and remote_behind is False:
        result["status"] = "diverged"
        return result

    result["status"] = "unknown"
    result["message"] = "could not determine commit ancestry between local HEAD and remote default branch"
    return result


def toolkit_build_metadata() -> dict[str, Any]:
    """Return the Git-derived metadata recorded in new workspaces."""
    return {
        "toolkit_commit_created_with": toolkit_commit(),
        "toolkit_build_number_created_with": toolkit_build_number(),
        "toolkit_ref_created_with": toolkit_ref_name(),
    }


def format_short_commit(commit_sha: str | None) -> str:
    """Return a short human-readable commit display."""
    if not commit_sha:
        return "unknown"
    return commit_sha[:12]


def build_toolkit_update_command(
    *,
    repo_url: str | None,
    branch: str | None,
    windows: bool | None = None,
) -> str:
    """Return the exact installer command for updating the current toolkit root."""
    is_windows = sys.platform.startswith("win") if windows is None else windows
    if is_windows:
        command = ".\\install.ps1"
        if repo_url:
            command += f' -RepoUrl "{repo_url}"'
        if branch:
            command += f' -Branch "{branch}"'
        return command

    command = "./install.sh"
    if repo_url:
        command += f' --repo "{repo_url}"'
    if branch:
        command += f' --branch "{branch}"'
    return command
