"""Toolkit metadata and update-check helpers.

These helpers are toolkit-root only. They support:

- recording commit/build metadata in newly generated workspaces
- checking whether the local toolkit snapshot is behind the selected remote source
- generating the exact installer command to update the toolkit root safely

Developer checkouts use live git state. Installed toolkit roots fall back to
installer-written provenance metadata when they are not themselves git repos.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLKIT_INSTALL_METADATA_PATH = REPO_ROOT / ".calixto-toolkit-install.json"
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


def load_toolkit_install_metadata() -> dict[str, Any] | None:
    """Load installer-written toolkit metadata when present."""
    if not TOOLKIT_INSTALL_METADATA_PATH.exists():
        return None
    try:
        payload = json.loads(TOOLKIT_INSTALL_METADATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


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


def installed_toolkit_commit() -> str | None:
    metadata = load_toolkit_install_metadata()
    if not metadata:
        return None
    value = metadata.get("toolkit_commit")
    return value if isinstance(value, str) and value else None


def installed_toolkit_build_number() -> int | None:
    metadata = load_toolkit_install_metadata()
    if not metadata:
        return None
    value = metadata.get("toolkit_build_number")
    return value if isinstance(value, int) and value > 0 else None


def installed_toolkit_ref_name() -> str | None:
    metadata = load_toolkit_install_metadata()
    if not metadata:
        return None
    value = metadata.get("toolkit_ref_name")
    return value if isinstance(value, str) and value else None


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


def _local_git_identity(remote_name: str = "origin") -> dict[str, Any] | None:
    local_commit = toolkit_commit()
    if local_commit is None:
        return None
    return {
        "source": "git",
        "local_commit": local_commit,
        "local_build_number": toolkit_build_number(),
        "local_ref": toolkit_ref_name(),
        "detached_head": toolkit_ref_name() is None,
        "repo_url": toolkit_remote_url(remote_name),
        "selector_kind": "default_branch",
        "selector_value": None,
    }


def _installed_toolkit_identity() -> dict[str, Any] | None:
    metadata = load_toolkit_install_metadata()
    if not metadata:
        return None
    local_commit = installed_toolkit_commit()
    return {
        "source": "install_metadata",
        "local_commit": local_commit,
        "local_build_number": installed_toolkit_build_number(),
        "local_ref": installed_toolkit_ref_name(),
        "detached_head": False,
        "repo_url": metadata.get("repo_url"),
        "selector_kind": metadata.get("selector_kind") or "default_branch",
        "selector_value": metadata.get("selector_value"),
        "install_metadata": metadata,
    }


def _ls_remote(*args: str) -> subprocess.CompletedProcess[str] | None:
    return _run_git("ls-remote", *args, check=False)


def _discover_remote_head(repo_target: str) -> dict[str, Any]:
    result = _ls_remote("--symref", repo_target, "HEAD")
    if result is None:
        return {
            "status": "unavailable",
            "reason": "git_unavailable",
            "message": "git is not installed or not on PATH",
            "remote_url": repo_target,
            "installer_repo_url": normalize_installer_repo_url(repo_target),
        }
    if result.returncode != 0:
        return {
            "status": "unavailable",
            "reason": "remote_lookup_failed",
            "message": _git_error_text(result),
            "remote_url": repo_target,
            "installer_repo_url": normalize_installer_repo_url(repo_target),
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
            "remote_url": repo_target,
            "installer_repo_url": normalize_installer_repo_url(repo_target),
        }
    return {
        "status": "ok",
        "remote_name": "origin",
        "remote_url": repo_target,
        "installer_repo_url": normalize_installer_repo_url(repo_target),
        "default_branch": branch_name,
        "default_branch_ref": f"refs/heads/{branch_name}",
        "latest_commit": head_commit,
    }


def _discover_remote_branch(repo_target: str, branch_name: str) -> dict[str, Any]:
    result = _ls_remote(repo_target, f"refs/heads/{branch_name}")
    if result is None:
        return {
            "status": "unavailable",
            "reason": "git_unavailable",
            "message": "git is not installed or not on PATH",
            "remote_url": repo_target,
            "installer_repo_url": normalize_installer_repo_url(repo_target),
        }
    if result.returncode != 0:
        return {
            "status": "unavailable",
            "reason": "remote_lookup_failed",
            "message": _git_error_text(result),
            "remote_url": repo_target,
            "installer_repo_url": normalize_installer_repo_url(repo_target),
        }
    line = result.stdout.strip()
    if not line:
        return {
            "status": "unavailable",
            "reason": "remote_branch_not_found",
            "message": f"could not find remote branch '{branch_name}'",
            "remote_url": repo_target,
            "installer_repo_url": normalize_installer_repo_url(repo_target),
        }
    parts = line.split()
    if len(parts) < 1:
        return {
            "status": "unavailable",
            "reason": "remote_branch_parse_failed",
            "message": f"could not parse remote branch metadata for '{branch_name}'",
            "remote_url": repo_target,
            "installer_repo_url": normalize_installer_repo_url(repo_target),
        }
    return {
        "status": "ok",
        "remote_name": "origin",
        "remote_url": repo_target,
        "installer_repo_url": normalize_installer_repo_url(repo_target),
        "default_branch": branch_name,
        "default_branch_ref": f"refs/heads/{branch_name}",
        "latest_commit": parts[0],
    }


def discover_default_branch(remote_name: str = "origin") -> dict[str, Any]:
    """Discover the remote default branch and latest commit SHA for a git checkout."""
    remote_url = toolkit_remote_url(remote_name)
    if not remote_url:
        return {
            "status": "unavailable",
            "reason": "remote_not_configured",
            "message": f"could not determine remote URL for '{remote_name}'",
            "remote_name": remote_name,
            "remote_url": None,
            "installer_repo_url": None,
        }
    remote = _discover_remote_head(remote_name)
    if remote["status"] != "ok":
        remote["remote_name"] = remote_name
        remote["remote_url"] = remote_url
        remote["installer_repo_url"] = normalize_installer_repo_url(remote_url)
        return remote
    tracking_ref_name, tracking_ref_sha = _resolve_local_tracking_ref(remote_name, remote["default_branch"])
    remote["remote_name"] = remote_name
    remote["remote_url"] = remote_url
    remote["installer_repo_url"] = normalize_installer_repo_url(remote_url)
    remote["tracking_ref"] = tracking_ref_name
    remote["tracking_ref_commit"] = tracking_ref_sha
    return remote


def _discover_remote_for_installed_toolkit(identity: dict[str, Any]) -> dict[str, Any]:
    repo_url = identity.get("repo_url")
    if not isinstance(repo_url, str) or not repo_url:
        return {
            "status": "unavailable",
            "reason": "installed_repo_url_unavailable",
            "message": "installed toolkit metadata does not include a repository URL",
            "remote_url": None,
            "installer_repo_url": None,
        }
    selector_kind = identity.get("selector_kind")
    selector_value = identity.get("selector_value")
    if selector_kind == "version":
        version_value = selector_value if isinstance(selector_value, str) and selector_value else "unknown"
        return {
            "status": "unavailable",
            "reason": "pinned_version_install",
            "message": f"toolkit was installed from pinned version '{version_value}', so default-branch freshness is not applicable",
            "remote_url": repo_url,
            "installer_repo_url": normalize_installer_repo_url(repo_url),
        }
    if selector_kind == "branch" and isinstance(selector_value, str) and selector_value:
        remote = _discover_remote_branch(repo_url, selector_value)
        remote["selected_ref_kind"] = "branch"
        remote["selected_ref_value"] = selector_value
        return remote
    remote = _discover_remote_head(repo_url)
    remote["selected_ref_kind"] = "default_branch"
    remote["selected_ref_value"] = None
    return remote


def check_toolkit_freshness(remote_name: str = "origin") -> dict[str, Any]:
    """Compare the current toolkit snapshot to the selected remote update source."""
    identity = _local_git_identity(remote_name) or _installed_toolkit_identity()
    if identity is None:
        return {
            "status": "unavailable",
            "reason": "local_toolkit_metadata_unavailable",
            "message": "could not determine local toolkit commit metadata from git or installer metadata",
            "local_commit": None,
            "local_build_number": None,
            "local_ref": None,
            "detached_head": False,
        }

    local_commit = identity["local_commit"]
    local_build = identity["local_build_number"]
    local_ref = identity["local_ref"]
    detached_head = bool(identity["detached_head"])

    if local_commit is None:
        return {
            "status": "unavailable",
            "reason": "local_toolkit_commit_unavailable",
            "message": "could not determine the installed toolkit commit metadata",
            "local_commit": None,
            "local_build_number": local_build,
            "local_ref": local_ref,
            "detached_head": detached_head,
            "repo_url": identity.get("repo_url"),
            "selected_ref_kind": identity.get("selector_kind"),
            "selected_ref_value": identity.get("selector_value"),
        }

    if identity["source"] == "git":
        remote = discover_default_branch(remote_name)
        selected_ref_kind = "default_branch"
        selected_ref_value = None
    else:
        remote = _discover_remote_for_installed_toolkit(identity)
        selected_ref_kind = remote.get("selected_ref_kind", identity.get("selector_kind"))
        selected_ref_value = remote.get("selected_ref_value", identity.get("selector_value"))

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
            "selected_ref_kind": selected_ref_kind,
            "selected_ref_value": selected_ref_value,
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
        "selected_ref_kind": selected_ref_kind,
        "selected_ref_value": selected_ref_value,
    }

    if local_commit == latest_commit:
        result["status"] = "up_to_date"
        result["latest_build_number"] = local_build
        return result

    if identity["source"] != "git":
        result["status"] = "update_available"
        result["message"] = (
            "installed toolkit commit differs from the currently selected remote reference, "
            "but ancestry cannot be computed without local git history"
        )
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
    """Return toolkit metadata recorded in new workspaces.

    Prefer live git metadata in developer checkouts. Fall back to installer
    provenance metadata in installed non-git toolkits.
    """
    commit = toolkit_commit()
    build_number = toolkit_build_number()
    ref_name = toolkit_ref_name()
    if commit is None:
        commit = installed_toolkit_commit()
        build_number = installed_toolkit_build_number()
        ref_name = installed_toolkit_ref_name()
    return {
        "toolkit_commit_created_with": commit,
        "toolkit_build_number_created_with": build_number,
        "toolkit_ref_created_with": ref_name,
    }


def format_short_commit(commit_sha: str | None) -> str:
    """Return a short human-readable commit display."""
    if not commit_sha:
        return "unknown"
    return commit_sha[:12]


def build_toolkit_update_command(
    *,
    repo_url: str | None,
    selector_kind: str | None,
    selector_value: str | None,
    windows: bool | None = None,
) -> str:
    """Return the exact installer command for updating the current toolkit root."""
    is_windows = sys.platform.startswith("win") if windows is None else windows
    if is_windows:
        command = ".\\install.ps1"
        if repo_url:
            command += f' -RepoUrl "{repo_url}"'
        if selector_kind == "branch" and selector_value:
            command += f' -Branch "{selector_value}"'
        elif selector_kind == "version" and selector_value:
            command += f' -Version "{selector_value}"'
        return command

    command = "./install.sh"
    if repo_url:
        command += f' --repo "{repo_url}"'
    if selector_kind == "branch" and selector_value:
        command += f' --branch "{selector_value}"'
    elif selector_kind == "version" and selector_value:
        command += f' --version "{selector_value}"'
    return command
